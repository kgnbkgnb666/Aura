from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from pathlib import Path
import threading

from .compiler import PromptCompiler
from .config import SettingsStore, is_deepseek_endpoint
from .history import HistoryStore
from .models import CompileRequest, Mode, Settings, Session
from .modes import ModeRegistry
from .providers.llm import OpenAICompatibleClient, RuleBasedCompiler
from .providers.stt import SenseVoiceSmallTranscriber, WhisperLargeV3Transcriber
from .providers.stt.dependencies import validate_stt_provider, get_available_stt_providers
from .session import SessionManager


TextCallback = Callable[[str], None]


class AuraService:
    def __init__(
        self,
        settings: Settings | None = None,
        modes: ModeRegistry | None = None,
    ) -> None:
        self.settings = settings or SettingsStore().load()
        self.modes = modes or ModeRegistry().load()
        self.settings.mode_id = self.modes.resolve_id(self.settings.mode_id)
        self.sessions = SessionManager(self.settings.mode_id)
        self.history = HistoryStore(self.settings.history_path)
        self.transcriber = self._build_transcriber()
        self.compiler = PromptCompiler(self._build_llm())
        self._warmup_lock = threading.Lock()
        self._warmup_thread: threading.Thread | None = None
        self._warmup_generation = 0

    @property
    def current_session(self) -> Session:
        return self.sessions.current

    @property
    def current_mode(self) -> Mode:
        return self.modes.get(self.current_session.mode_id)

    def _build_llm(self):
        is_deepseek = self.settings.llm_provider == "deepseek" or is_deepseek_endpoint(
            self.settings.llm_base_url
        )
        is_custom = not is_deepseek
        if self.settings.llm_api_key or (
            is_custom and self.settings.llm_base_url and self.settings.llm_model
        ):
            return OpenAICompatibleClient(
                base_url=self.settings.llm_base_url,
                api_key=self.settings.llm_api_key,
                model=self.settings.llm_model,
                temperature=self.settings.llm_temperature,
                timeout_seconds=self.settings.llm_timeout_seconds,
                allow_anonymous=is_custom and not self.settings.llm_api_key,
                thinking_enabled=(
                    self.settings.llm_thinking_enabled
                    if is_deepseek
                    else None
                ),
            )
        return RuleBasedCompiler()

    def _build_transcriber(self):
        """Build transcriber with validation and fallback."""
        requested_provider = self.settings.stt_provider

        # Validate the requested provider
        is_valid, error_msg = validate_stt_provider(requested_provider)

        if not is_valid:
            log = logging.getLogger("aura")
            log.warning(
                "Requested STT provider '%s' is not available: %s",
                requested_provider,
                error_msg
            )

            # Try to find an available fallback
            available = get_available_stt_providers()
            fallback_provider = None

            # Prefer sensevoice-small as fallback
            if available.get("sensevoice-small"):
                fallback_provider = "sensevoice-small"
            elif available.get("whisper-large-v3"):
                fallback_provider = "whisper-large-v3"

            if fallback_provider:
                log.info(
                    "Falling back to '%s' (available provider)",
                    fallback_provider
                )
                self.settings.stt_provider = fallback_provider
            else:
                # No provider available, raise error
                raise RuntimeError(
                    f"无法初始化任何 STT 模型。请安装依赖：\n\n"
                    f"- SenseVoice Small: pip install funasr modelscope\n"
                    f"- Whisper Large V3: pip install faster-whisper\n\n"
                    f"当前环境缺少必要的库。"
                )

        # Build the transcriber (may still fail due to network/download issues)
        if self.settings.stt_provider == "whisper-large-v3":
            try:
                return WhisperLargeV3Transcriber(cache_dir=self.settings.model_cache_dir)
            except Exception as exc:
                log = logging.getLogger("aura")
                error_str = str(exc)
                # Check if it's a network/download error
                if any(keyword in error_str for keyword in ["ConnectTimeout", "LocalEntryNotFoundError", "网络", "connection"]):
                    log.error("Whisper model download failed due to network error: %s", exc)
                    # Fall back to sensevoice-small
                    if get_available_stt_providers().get("sensevoice-small"):
                        log.warning("Falling back to sensevoice-small due to network error")
                        self.settings.stt_provider = "sensevoice-small"
                        return SenseVoiceSmallTranscriber(cache_dir=self.settings.model_cache_dir)
                # Re-raise if not a network error or no fallback available
                raise
        else:
            self.settings.stt_provider = "sensevoice-small"
            return SenseVoiceSmallTranscriber(cache_dir=self.settings.model_cache_dir)

    def replace_transcriber(self) -> None:
        """Replace the STT engine and invalidate any warmup for the previous one."""
        with self._warmup_lock:
            self._warmup_generation += 1
            try:
                self.transcriber = self._build_transcriber()
            except Exception as exc:
                # If build fails (e.g., network error during model download),
                # ensure we have a working fallback
                log = logging.getLogger("aura")
                log.error("Failed to build transcriber for '%s': %s",
                         self.settings.stt_provider, exc)

                # Try to fallback to sensevoice-small
                if self.settings.stt_provider != "sensevoice-small":
                    log.warning("Attempting fallback to sensevoice-small")
                    self.settings.stt_provider = "sensevoice-small"
                    try:
                        self.transcriber = SenseVoiceSmallTranscriber(
                            cache_dir=self.settings.model_cache_dir
                        )
                        log.info("Successfully fell back to sensevoice-small")
                    except Exception as fallback_exc:
                        log.critical("Fallback also failed: %s", fallback_exc)
                        raise RuntimeError(
                            f"无法初始化任何 STT 模型。原始错误: {exc}"
                        ) from fallback_exc
                else:
                    # Already on sensevoice-small and it failed
                    raise
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
        on_fallback: Callable[[], None] | None = None,
    ) -> None:
        with self._warmup_lock:
            # Use mutable wrappers so the closure can update them after fallback
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
                try:
                    _transcriber[0].load_model(status_callback=report_status)
                except Exception as exc:
                    tb = traceback.format_exc()
                    log = logging.getLogger("aura")
                    log.error("STT model warmup failed: %s\n%s", exc, tb)

                    # Check if it's a network/download error and we can fallback
                    error_str = str(exc)
                    is_network_error = any(keyword in error_str.lower() for keyword in
                                          ["connecttimeout", "localentrynotfound",
                                           "connection", "timeout", "网络"])

                    # Only attempt fallback if this is a network error and we're on whisper
                    if is_network_error and _transcriber[0].name == "whisper-large-v3":
                        with self._warmup_lock:
                            # Check if generation is still valid
                            if _generation[0] == self._warmup_generation:
                                log.warning("Whisper download failed due to network error, attempting fallback to sensevoice-small")

                                # Check if sensevoice is available
                                if get_available_stt_providers().get("sensevoice-small"):
                                    try:
                                        # Switch to sensevoice-small
                                        self.settings.stt_provider = "sensevoice-small"
                                        new_transcriber = SenseVoiceSmallTranscriber(
                                            cache_dir=self.settings.model_cache_dir
                                        )
                                        # Replace the transcriber
                                        self.transcriber = new_transcriber
                                        self._warmup_generation += 1

                                        # CRITICAL: Update the closure's references so
                                        # report_status will pass the generation check
                                        _transcriber[0] = self.transcriber
                                        _generation[0] = self._warmup_generation

                                        log.info("Successfully switched to sensevoice-small")

                                        # Notify sidecar to save updated config
                                        if on_fallback:
                                            try:
                                                on_fallback()
                                            except Exception as fc_exc:
                                                log.error("on_fallback callback failed: %s", fc_exc)

                                        # Now warm up the new transcriber
                                        # report_status works now because we synced _generation
                                        report_status("网络连接失败，已自动切换到 SenseVoice Small，正在加载...")
                                        new_transcriber.load_model(status_callback=report_status)
                                        log.info("Fallback to sensevoice-small completed successfully")
                                        return
                                    except Exception as fallback_exc:
                                        log.error("Fallback to sensevoice-small also failed: %s", fallback_exc)

                    # If we reach here, either no fallback was attempted or it failed
                    report_status(f"{_transcriber[0].name} 模型加载失败: {str(exc)[:100]}")

            self._warmup_thread = threading.Thread(target=work, daemon=True)
            self._warmup_thread.start()

    def transcribe(self, wav_path: Path, on_status: TextCallback | None = None) -> str:
        return self.transcriber.transcribe(wav_path, status_callback=on_status)

    def compile_transcript(self, transcript: str, on_chunk: TextCallback | None = None) -> str:
        request = CompileRequest(
            mode=self.current_mode,
            current_transcript=transcript,
            previous_compiled_text=self.sessions.previous_compiled_text(),
            previous_transcripts=self.sessions.previous_transcripts(),
            skills=self.settings.skills,
            merge_output=self.current_session.merge_output,
        )
        parts: list[str] = []
        for chunk in self.compiler.stream_compile(request):
            parts.append(chunk)
            if on_chunk:
                on_chunk(chunk)
        compiled = "".join(parts).strip()
        turn = self.current_session.add_turn(
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
        )
        parts: list[str] = []
        for chunk in self.compiler.stream_compile(request):
            parts.append(chunk)
            if on_chunk:
                on_chunk(chunk)
        compiled = "".join(parts).strip()
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
