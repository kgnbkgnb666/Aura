from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from pathlib import Path
import threading

from .compiler import PromptCompiler
from .config import SettingsStore, is_deepseek_endpoint
from .history import HistoryStore
from .models import ClarityAssessment, CompileRequest, Mode, Settings, Session, SupplementaryQuestion
from .modes import ModeRegistry
from .providers.llm import OpenAICompatibleClient, RuleBasedCompiler
from .providers.llm.base import UnsupportedLLMCapabilityError
from .providers.stt import SenseVoiceSmallTranscriber, WhisperLargeV3Transcriber
from .session import SessionManager
from .clarity import (
    build_clarity_messages,
    build_supplement_messages,
    parse_clarity_response,
    parse_supplement_response,
)


TextCallback = Callable[[str], None]


def _is_network_error(exc: Exception) -> bool:
    """Detect network-related errors from huggingface_hub, requests, urllib, etc."""
    message = str(exc).lower()
    exc_type_name = type(exc).__qualname__.lower()

    type_patterns = (
        "connecttimeout", "connecterror", "connectionerror",
        "timeout", "httperror", "localentrynotfounderror",
        "connectionrefusederror", "urlerror", "gaierror",
        "remotedisconnected", "protocolerror",
    )
    for pattern in type_patterns:
        if pattern in exc_type_name:
            return True

    message_patterns = (
        "connect timeout", "connection refused", "connection reset",
        "name or service not known", "network is unreachable",
        "no route to host", "temporary failure in name resolution",
        "timed out", "timeout", "could not resolve host",
        "failed to establish a new connection",
        "max retries exceeded", "nodename nor servname",
        "getaddrinfo failed",
    )
    for pattern in message_patterns:
        if pattern in message:
            return True

    if "401" in message or "403" in message or "404" in message:
        return True

    return False


class AuraService:
    def __init__(
        self,
        settings: Settings | None = None,
        modes: ModeRegistry | None = None,
        settings_store: SettingsStore | None = None,
    ) -> None:
        self.settings = settings or SettingsStore().load()
        self.modes = modes or ModeRegistry().load()
        self.settings.mode_id = self.modes.resolve_id(self.settings.mode_id)
        self.sessions = SessionManager(self.settings.mode_id)
        self.history = HistoryStore(self.settings.history_path)
        self.transcriber = self._build_transcriber()
        self.compiler = PromptCompiler(self._build_llm())
        self._warmup_lock = threading.Lock()
        self._llm_lock = threading.RLock()
        self._warmup_thread: threading.Thread | None = None
        self._warmup_generation = 0
        self._settings_store = settings_store

    @property
    def current_session(self) -> Session:
        return self.sessions.current

    @property
    def current_mode(self) -> Mode:
        return self.modes.get(self.current_session.mode_id)

    @property
    def supports_structured_analysis(self) -> bool:
        llm = self.compiler.llm
        return bool(
            getattr(llm, "is_configured", False)
            and getattr(llm, "supports_structured_output", False)
        )

    def _require_structured_analysis(self) -> None:
        if not self.supports_structured_analysis:
            raise UnsupportedLLMCapabilityError(
                "The configured LLM provider does not support structured analysis."
            )

    def _build_llm(self):
        is_deepseek = self.settings.llm_provider == "deepseek" or is_deepseek_endpoint(
            self.settings.llm_base_url
        )
        is_custom = not is_deepseek
        api_key = self.settings.deepseek_api_key if is_deepseek else self.settings.custom_api_key
        if api_key or (
            is_custom and self.settings.llm_base_url and self.settings.llm_model
        ):
            return OpenAICompatibleClient(
                base_url=self.settings.llm_base_url,
                api_key=api_key,
                model=self.settings.llm_model,
                temperature=self.settings.llm_temperature,
                timeout_seconds=self.settings.llm_timeout_seconds,
                allow_anonymous=is_custom and not api_key,
                thinking_enabled=(
                    self.settings.llm_thinking_enabled
                    if is_deepseek
                    else None
                ),
            )
        return RuleBasedCompiler()

    def _build_transcriber(self):
        if self.settings.stt_provider == "whisper-large-v3":
            return WhisperLargeV3Transcriber(cache_dir=self.settings.model_cache_dir)
        self.settings.stt_provider = "sensevoice-small"
        return SenseVoiceSmallTranscriber(cache_dir=self.settings.model_cache_dir)

    def replace_transcriber(self) -> None:
        """Replace the STT engine and invalidate any warmup for the previous one."""
        with self._warmup_lock:
            self._warmup_generation += 1
            self.transcriber = self._build_transcriber()
            # The old thread may still be finishing, but it must not prevent the
            # newly selected model from starting its own warmup.
            self._warmup_thread = None

    def new_session(self, mode_id: str | None = None) -> Session:
        resolved_mode_id = self.modes.resolve_id(mode_id or self.settings.mode_id)
        session = self.sessions.new_session(resolved_mode_id)
        return session

    def load_session(self, session_id: str) -> Session:
        session = self.history.load_session(session_id)
        session.mode_id = self.modes.resolve_id(session.mode_id)
        self.sessions.current = session
        self.settings.mode_id = session.mode_id
        return session

    def set_mode(self, mode_id: str) -> None:
        resolved_mode_id = self.modes.resolve_id(mode_id)
        self.settings.mode_id = resolved_mode_id
        self.sessions.set_mode(resolved_mode_id)

    def set_merge_output(self, enabled: bool) -> None:
        self.current_session.merge_output = enabled
        if self.settings.save_history and self.current_session.turns:
            self.history.save_session(self.current_session)

    def warm_up_transcriber(self, on_status: TextCallback | None = None) -> None:
        if self.transcriber.is_ready:
            if on_status:
                on_status(f"{self.transcriber.name} 模型已就绪")
            return
        self.transcriber.load_model(status_callback=on_status)

    def warm_up_transcriber_background(
        self,
        on_status: TextCallback | None = None,
        on_fallback: TextCallback | None = None,
    ) -> None:
        with self._warmup_lock:
            # Mutable wrappers so the closure sees updated values after fallback.
            _generation = [self._warmup_generation]
            _transcriber = [self.transcriber]
            if _transcriber[0].is_ready:
                if on_status:
                    on_status(f"{_transcriber[0].name} 模型已就绪")
                return
            if self._warmup_thread and self._warmup_thread.is_alive():
                return

            def report_status(message: str) -> None:
                with self._warmup_lock:
                    if _generation[0] != self._warmup_generation or _transcriber[0] is not self.transcriber:
                        return
                if on_status:
                    on_status(message)

            def work() -> None:
                logger = logging.getLogger("aura")
                try:
                    _transcriber[0].load_model(status_callback=report_status)
                except Exception as exc:
                    tb = traceback.format_exc()
                    logger.error("STT model warmup failed: %s\n%s", exc, tb)
                    report_status(f"{_transcriber[0].name} 模型加载失败: {str(exc)[:100]}")

                    # Only fallback from whisper-large-v3 — SenseVoice has no fallback target.
                    if _transcriber[0].name != "whisper-large-v3":
                        return

                    if not _is_network_error(exc):
                        return

                    fallback_model = None
                    with self._warmup_lock:
                        if _generation[0] != self._warmup_generation:
                            return  # Another warmup started, abandon fallback
                        if _transcriber[0] is not self.transcriber:
                            return  # Transcriber already replaced

                        self.settings.stt_provider = "sensevoice-small"
                        fallback_model = SenseVoiceSmallTranscriber(
                            cache_dir=self.settings.model_cache_dir,
                        )
                        self.transcriber = fallback_model
                        self._warmup_generation += 1
                        _generation[0] = self._warmup_generation
                        _transcriber[0] = fallback_model
                        self._warmup_thread = None

                    # Persist the fallback so next boot uses SenseVoice directly.
                    if self._settings_store:
                        try:
                            self._settings_store.save(self.settings)
                        except Exception as save_exc:
                            logger.warning("Failed to persist fallback setting: %s", save_exc)

                    # Call on_fallback OUTSIDE the lock.
                    if on_fallback:
                        try:
                            on_fallback(
                                "Whisper 下载失败，已自动切换回 SenseVoice Small"
                            )
                        except Exception:
                            pass

                    # Load the fallback model OUTSIDE the lock (Lock is NOT reentrant).
                    try:
                        report_status(
                            "Whisper 下载失败，已自动切换到 SenseVoice Small，正在加载..."
                        )
                        fallback_model.load_model(status_callback=report_status)
                    except Exception as fallback_exc:
                        logger.error(
                            "SenseVoice fallback also failed: %s\n%s",
                            fallback_exc,
                            traceback.format_exc(),
                        )
                        report_status(
                            f"SenseVoice Small 模型加载也失败: {str(fallback_exc)[:100]}"
                        )

            self._warmup_thread = threading.Thread(target=work, daemon=True)
            self._warmup_thread.start()

    def transcribe(self, wav_path: Path, on_status: TextCallback | None = None) -> str:
        return self.transcriber.transcribe(wav_path, status_callback=on_status)

    def _collect_compilation(
        self,
        request: CompileRequest,
        on_chunk: TextCallback | None,
    ) -> str:
        parts: list[str] = []
        with self._llm_lock:
            for chunk in self.compiler.stream_compile(request):
                parts.append(chunk)
                if on_chunk:
                    on_chunk(chunk)
        return "".join(parts).strip()

    def compile_transcript(self, transcript: str, on_chunk: TextCallback | None = None) -> str:
        request = CompileRequest(
            mode=self.current_mode,
            current_transcript=transcript,
            previous_compiled_text=self.sessions.previous_compiled_text(),
            previous_transcripts=self.sessions.previous_transcripts(),
            skills=self.settings.skills,
            merge_output=self.current_session.merge_output,
            output_language=self.settings.ui_language,
        )
        compiled = self._collect_compilation(request, on_chunk)
        self.current_session.add_turn(
            raw_transcript=transcript,
            compiled_text=compiled,
            stt_provider=self.settings.stt_provider,
            llm_provider=self.compiler.llm.name,
        )
        if self.settings.save_history:
            self.history.save_session(self.current_session)
        return compiled

    def compile_only(self, transcript: str, on_chunk: TextCallback | None = None) -> str:
        """Recompile by updating the latest turn, creating only the initial turn when needed."""
        previous_transcripts = self.sessions.previous_transcripts()
        if self.current_session.turns:
            previous_transcripts = previous_transcripts[:-1]
        previous_compiled_text = ""
        if len(self.current_session.turns) > 1:
            previous_compiled_text = self.current_session.turns[-2].compiled_text
        request = CompileRequest(
            mode=self.current_mode,
            current_transcript=transcript,
            previous_compiled_text=previous_compiled_text,
            previous_transcripts=previous_transcripts,
            skills=self.settings.skills,
            merge_output=self.current_session.merge_output,
            output_language=self.settings.ui_language,
        )
        compiled = self._collect_compilation(request, on_chunk)
        turn = self.current_session.update_latest_turn(
            raw_transcript=transcript,
            compiled_text=compiled,
        )
        if turn is None:
            self.current_session.add_turn(
                raw_transcript=transcript,
                compiled_text=compiled,
                stt_provider=self.settings.stt_provider,
                llm_provider=self.compiler.llm.name,
            )
        else:
            # Transcript changed — clear stale clarity so it gets re-assessed
            turn.clarity_score = None
            turn.clarity_level = None
            turn.clarity_label = None
        if self.settings.save_history:
            self.history.save_session(self.current_session)
        return compiled

    def transcribe_and_compile(
        self,
        wav_path: Path,
        on_chunk: TextCallback | None = None,
        on_status: TextCallback | None = None,
    ) -> tuple[str, str]:
        transcript = self.transcribe(wav_path, on_status=on_status)
        compiled = self.compile_transcript(transcript, on_chunk=on_chunk)
        return transcript, compiled

    def assess_clarity(self, transcript: str) -> ClarityAssessment:
        self._require_structured_analysis()
        messages = build_clarity_messages(transcript, self.settings.ui_language)
        with self._llm_lock:
            response = self.compiler.llm.chat(messages)
        parsed = parse_clarity_response(response, self.settings.ui_language)
        assessment = ClarityAssessment(
            score=int(parsed["score"]),
            level=str(parsed["level"]),
            label=str(parsed["label"]),
        )
        # Persist clarity on the latest turn
        if self.current_session.turns:
            turn = self.current_session.turns[-1]
            turn.clarity_score = assessment.score
            turn.clarity_level = assessment.level
            turn.clarity_label = assessment.label
            if self.settings.save_history:
                self.history.save_session(self.current_session)
        return assessment

    def generate_supplementary_questions(self, transcript: str) -> list[SupplementaryQuestion]:
        self._require_structured_analysis()
        history = [t.raw_transcript for t in self.current_session.turns]
        messages = build_supplement_messages(transcript, history, self.settings.ui_language)
        with self._llm_lock:
            response = self.compiler.llm.chat(messages)
        parsed = parse_supplement_response(response)
        return [SupplementaryQuestion(**item) for item in parsed]
