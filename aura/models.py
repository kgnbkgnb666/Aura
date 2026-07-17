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
class Skill:
    id: str
    name: str
    description: str
    example: str = ""
    category: str = "Custom"
    enabled: bool = True
    source_path: str = ""


@dataclass(slots=True)
class Settings:
    app_name: str = "Aura"
    mode_id: str = "coding_agent"
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
    auto_launch: bool = False
    history_path: Path | None = None
    skills: list[Skill] = field(default_factory=list)
    skill_scan_dir: str = ""


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

    def update_latest_turn(self, raw_transcript: str, compiled_text: str) -> Turn | None:
        """Update the latest turn's transcript and compiled text in-place (for recompile)."""
        if not self.turns:
            return None
        turn = self.turns[-1]
        turn.raw_transcript = raw_transcript
        turn.compiled_text = compiled_text
        self.updated_at = utc_now()
        return turn


@dataclass(slots=True)
class CompileRequest:
    mode: Mode
    current_transcript: str
    previous_compiled_text: str = ""
    previous_transcripts: list[str] = field(default_factory=list)
    user_preferences: str = ""
    skills: list[Skill] = field(default_factory=list)

    def as_messages(self) -> list[dict[str, str]]:
        history = "\n".join(
            f"{index + 1}. {text}" for index, text in enumerate(self.previous_transcripts)
        )
        enabled_skills = [skill for skill in self.skills if skill.enabled]
        skill_lines: list[str] = []
        for index, skill in enumerate(enabled_skills, start=1):
            parts = [
                f"{index}. {skill.name}",
                f"分类: {skill.category}",
                f"描述: {skill.description}",
            ]
            if skill.example.strip():
                parts.append(f"使用示例: {skill.example.strip()}")
            skill_lines.append("\n".join(parts))

        system_prompt = self.mode.system_prompt
        if enabled_skills:
            system_prompt = (
                f"{system_prompt.strip()}\n\n"
                "可用 Skill 匹配规则：先根据用户当前需求，逐项比较下列 Skill 的名称、描述和使用示例。"
                "只有需求与某个 Skill 的用途或示例明确匹配时，才在最终 prompt 中自然写明该 Skill 的准确名称，"
                "并补充调用它所需的任务目标、输入或上下文。"
                "仅有宽泛或表面相似时视为不匹配；不匹配时不要提及任何 Skill，也不要输出匹配分析过程。"
            )
        user_parts = [
            "请把下面的语音转录整理成可直接发送给目标 agent 的 prompt。",
            "",
            f"目标模式：{self.mode.name}",
        ]
        if enabled_skills:
            user_parts.extend(
                [
                    "",
                    "当前可使用 Skill（名称、描述、使用示例）：",
                    "\n\n".join(skill_lines),
                    "",
                    "请参考 Skill 的使用示例：当用户需求匹配某个 Skill 时，在最终编译结果中添加或引用该 Skill；不匹配时不要添加。",
                ]
            )
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
            {"role": "system", "content": system_prompt},
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
