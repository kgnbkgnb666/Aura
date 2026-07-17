from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import threading

from .compiler import PromptCompiler
from .config import SettingsStore
from .history import HistoryStore
from .models import CompileRequest, Mode, Settings, Session
from .modes import ModeRegistry
from .providers.llm import OpenAICompatibleClient, RuleBasedCompiler
from .providers.stt import SenseVoiceSmallTranscriber
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
        self.sessions = SessionManager(self.settings.mode_id)
        self.history = HistoryStore(self.settings.history_path)
        self.transcriber = self._build_transcriber()
        self.compiler = PromptCompiler(self._build_llm())
        self._warmup_thread: threading.Thread | None = None

    @property
    def current_session(self) -> Session:
        return self.sessions.current

    @property
    def current_mode(self) -> Mode:
        return self.modes.get(self.current_session.mode_id)

    def _build_llm(self):
        if self.settings.llm_api_key:
            return OpenAICompatibleClient(
                base_url=self.settings.llm_base_url,
                api_key=self.settings.llm_api_key,
                model=self.settings.llm_model,
                temperature=self.settings.llm_temperature,
                timeout_seconds=self.settings.llm_timeout_seconds,
            )
        return RuleBasedCompiler()

    def _build_transcriber(self):
        self.settings.stt_provider = "sensevoice-small"
        return SenseVoiceSmallTranscriber(cache_dir=self.settings.model_cache_dir)

    def new_session(self, mode_id: str | None = None) -> Session:
        session = self.sessions.new_session(mode_id or self.settings.mode_id)
        return session

    def load_session(self, session_id: str) -> Session:
        session = self.history.load_session(session_id)
        self.sessions.current = session
        self.settings.mode_id = session.mode_id
        return session

    def set_mode(self, mode_id: str) -> None:
        self.settings.mode_id = mode_id
        self.sessions.set_mode(mode_id)

    def warm_up_transcriber(self, on_status: TextCallback | None = None) -> None:
        if self.transcriber.is_ready:
            if on_status:
                on_status(f"{self.transcriber.name} 模型已就绪")
            return
        self.transcriber.load_model(status_callback=on_status)

    def warm_up_transcriber_background(self, on_status: TextCallback | None = None) -> None:
        if self.transcriber.is_ready:
            if on_status:
                on_status(f"{self.transcriber.name} 模型已就绪")
            return
        if self._warmup_thread and self._warmup_thread.is_alive():
            return

        def work() -> None:
            try:
                self.warm_up_transcriber(on_status=on_status)
            except Exception as exc:
                if on_status:
                    on_status(f"{self.transcriber.name} 模型加载失败: {exc}")

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
        request = CompileRequest(
            mode=self.current_mode,
            current_transcript=transcript,
            previous_compiled_text=self.sessions.previous_compiled_text(),
            previous_transcripts=previous_transcripts,
            skills=self.settings.skills,
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
