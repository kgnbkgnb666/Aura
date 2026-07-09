from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid4().hex


@dataclass(slots=True)
class Mode:
    id: str
    name: str
    target: str
    description: str
    system_prompt: str
    output_hint: str = ""


@dataclass(slots=True)
class Settings:
    app_name: str = "AgentVoice"
    mode_id: str = "codex"
    auto_copy: bool = True
    save_history: bool = True
    keep_window_on_top: bool = False
    hotkey: str = "<ctrl>+<shift>+<space>"
    push_to_talk_key: str = "space"
    input_device_index: int | None = None
    stt_provider: str = "sensevoice-small"
    model_cache_dir: Path | None = None
    llm_provider: str = "openai_compatible"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.2
    llm_timeout_seconds: int = 60
    history_path: Path | None = None


@dataclass(slots=True)
class Turn:
    id: str
    session_id: str
    turn_index: int
    raw_transcript: str
    compiled_text: str
    mode_id: str
    stt_provider: str
    llm_provider: str
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class Session:
    id: str
    mode_id: str
    title: str = "Untitled"
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    turns: list[Turn] = field(default_factory=list)

    @property
    def latest_compiled_text(self) -> str:
        if not self.turns:
            return ""
        return self.turns[-1].compiled_text

    @property
    def full_raw_transcript(self) -> str:
        return "\n".join(turn.raw_transcript for turn in self.turns if turn.raw_transcript)

    def add_turn(
        self,
        raw_transcript: str,
        compiled_text: str,
        stt_provider: str,
        llm_provider: str,
    ) -> Turn:
        turn = Turn(
            id=new_id(),
            session_id=self.id,
            turn_index=len(self.turns) + 1,
            raw_transcript=raw_transcript,
            compiled_text=compiled_text,
            mode_id=self.mode_id,
            stt_provider=stt_provider,
            llm_provider=llm_provider,
        )
        self.turns.append(turn)
        self.updated_at = turn.created_at
        if self.title == "Untitled" and raw_transcript.strip():
            self.title = raw_transcript.strip()[:32]
        return turn


@dataclass(slots=True)
class CompileRequest:
    mode: Mode
    current_transcript: str
    previous_compiled_text: str = ""
    previous_transcripts: list[str] = field(default_factory=list)
    user_preferences: str = ""

    def as_messages(self) -> list[dict[str, str]]:
        history = "\n".join(
            f"{index + 1}. {text}" for index, text in enumerate(self.previous_transcripts)
        )
        user_parts = [
            "请把下面的语音转录整理成可直接发送给目标 agent 的 prompt。",
            "",
            f"目标模式：{self.mode.name}",
        ]
        if self.user_preferences:
            user_parts.extend(["", "用户偏好：", self.user_preferences])
        if history:
            user_parts.extend(["", "本会话之前的原始转录：", history])
        if self.previous_compiled_text:
            user_parts.extend(["", "上一版 AI 编译结果：", self.previous_compiled_text])
            user_parts.extend(
                [
                    "",
                    "这次输入是对上一版的补充或修订，请输出一版整合后的完整 prompt，不要只输出增量。",
                ]
            )
        user_parts.extend(["", "本次原始语音转录：", self.current_transcript.strip()])
        return [
            {"role": "system", "content": self.mode.system_prompt},
            {"role": "user", "content": "\n".join(user_parts).strip()},
        ]


@dataclass(slots=True)
class RecordingResult:
    wav_path: Path
    duration_seconds: float
    average_volume: float
    max_volume: int


@dataclass(slots=True)
class DeviceInfo:
    index: int
    name: str
    max_input_channels: int
    default_sample_rate: int
    is_default_input: bool = False


JsonDict = dict[str, Any]
