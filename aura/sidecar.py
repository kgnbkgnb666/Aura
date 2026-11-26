from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import secrets
import sys
import threading
import tempfile
import wave
import time
import traceback
from dataclasses import asdict, is_dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .voice_options import LANGUAGES, import_skills, validate_keys, validate_skills
from .compiler import PromptCompiler
from .config import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODELS,
    SUPPORTED_STT_PROVIDERS,
    SettingsStore,
    is_deepseek_endpoint,
)
from .models import DeviceInfo, Mode, RecordingResult, Session, Settings, Skill
from .modes import ModeRegistry
from .recorder import AudioRecorder
from .providers.stt.doubao import DoubaoStream, DoubaoTranscriber
from .runtime import ProcessingJobStore, RuntimeLog
from .service import AuraService

API_KEY_MASK = "********"
MAX_REQUEST_BODY_BYTES = 1024 * 1024
ALLOWED_WEBVIEW_ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "tauri://localhost",
}


class RequestBodyTooLarge(ValueError):
    pass


def _log_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "logs"
    return Path(__file__).resolve().parent.parent / "logs"


def _setup_logging() -> logging.Logger:
    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "aura-sidecar.log"

    logger = logging.getLogger("aura")
    logger.setLevel(logging.DEBUG)

    # Reinitialization can happen in tests or embedded launches; never duplicate writes.
    for handler in list(logger.handlers):
        if getattr(handler, "_aura_sidecar_file", False):
            logger.removeHandler(handler)
            handler.close()

    # File handler - always detailed, bounded to ~40 MB across eight files.
    fh = RotatingFileHandler(
        str(log_file),
        maxBytes=5 * 1024 * 1024,
        backupCount=7,
        encoding="utf-8",
    )
    fh._aura_sidecar_file = True  # type: ignore[attr-defined]
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)
    logger.propagate = False

    # Also capture uncaught exceptions
    def _excepthook(exc_type, exc_value, exc_tb):
        if exc_type is not None:
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
            logger.critical("UNCAUGHT: %s", "".join(tb_lines).strip())
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.excepthook = _excepthook

    logger.info("Logging initialized: %s", log_file)
    return logger


JsonDict = dict[str, Any]


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    return str(value)


def json_response(payload: Any, status: int = 200) -> bytes:
    body = json.dumps(payload, ensure_ascii=False, default=_json_default).encode("utf-8")
    return body


def settings_payload(
    settings: Settings,
) -> JsonDict:
    data = asdict(settings)
    data["deepseek_api_key"] = API_KEY_MASK if settings.deepseek_api_key else ""
    data["custom_api_key"] = API_KEY_MASK if settings.custom_api_key else ""
    data["ark_api_key"] = API_KEY_MASK if settings.ark_api_key else ""
    data["asr_api_key"] = API_KEY_MASK if settings.asr_api_key else ""
    data["deepseek_api_key_source"] = "config" if settings.deepseek_api_key else "unset"
    data["custom_api_key_source"] = "config" if settings.custom_api_key else "unset"
    data["ark_api_key_source"] = "config" if settings.ark_api_key else "unset"
    data["asr_api_key_source"] = "config" if settings.asr_api_key else "unset"
    if data.get("history_path"):
        data["history_path"] = str(data["history_path"])
    if data.get("model_cache_dir"):
        data["model_cache_dir"] = str(data["model_cache_dir"])
    return data


def mode_payload(mode: Mode) -> JsonDict:
    return asdict(mode)


def skill_payload(skill: Skill) -> JsonDict:
    return asdict(skill)


def _skill_id(name: str, source_path: str = "") -> str:
    base = f"{name}:{source_path}".strip(":")
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def _extract_skill(path: Path) -> Skill | None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = [line.strip() for line in text.splitlines()]
    name = path.parent.name
    description = ""
    examples: list[str] = []

    for line in lines:
        if line.startswith("# "):
            name = line.lstrip("#").strip()
            break

    for index, line in enumerate(lines):
        lower = line.lower()
        if lower.startswith("description:"):
            description = line.split(":", 1)[1].strip()
            break
        if "description" in lower and index + 1 < len(lines):
            description = lines[index + 1].strip("- ").strip()
            break
    if not description:
        for line in lines:
            if line and not line.startswith("#"):
                description = line.strip("- ").strip()
                break

    in_example = False
    for line in lines:
        lower = line.lower()
        if "example" in lower or "示例" in line:
            in_example = True
            continue
        if in_example:
            if line.startswith("#") and examples:
                break
            if line:
                examples.append(line.strip("- ").strip())
            if len(examples) >= 4:
                break

    if not name or not description:
        return None
    return Skill(
        id=_skill_id(name, str(path)),
        name=name,
        description=description,
        example="\n".join(examples).strip(),
        category=path.parent.parent.name if path.parent.parent != path.parent else "Imported",
        enabled=True,
        source_path=str(path),
    )


def session_payload(session: Session) -> JsonDict:
    return {
        "id": session.id,
        "mode_id": session.mode_id,
        "title": session.title,
        "merge_output": session.merge_output,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "turn_count": len(session.turns),
    }


def session_detail_payload(session: Session) -> JsonDict:
    latest_turn = session.turns[-1] if session.turns else None
    clarity = None
    if latest_turn and latest_turn.clarity_score is not None:
        clarity = {
            "score": latest_turn.clarity_score,
            "level": latest_turn.clarity_level or "medium",
            "label": latest_turn.clarity_label or "",
        }
    return {
        "session": session_payload(session),
        "transcript": latest_turn.raw_transcript if latest_turn else "",
        "compiled": latest_turn.compiled_text if latest_turn else "",
        "clarity": clarity,
    }


def device_payload(device: DeviceInfo) -> JsonDict:
    return asdict(device)


def recording_payload(result: RecordingResult) -> JsonDict:
    return {
        "wav_path": str(result.wav_path),
        "duration_seconds": result.duration_seconds,
        "average_volume": result.average_volume,
        "max_volume": result.max_volume,
    }


class AuraSidecar:
    def __init__(self, preload_stt: bool = False, settings_store: SettingsStore | None = None) -> None:
        self.settings_store = settings_store or SettingsStore()
        self.service = AuraService(
            settings=self.settings_store.load(),
            modes=ModeRegistry(local_modes_dir=self.settings_store.data_dir / "modes").load(),
            settings_store=self.settings_store,
        )
        self.logs = RuntimeLog()
        self.jobs = ProcessingJobStore()
        self._preview_lock = threading.Lock()
        self.recorder: AudioRecorder | None = None
        self.recording_stream: DoubaoStream | None = None
        self.last_test_wav: Path | None = None
        self.mic_test_recorder: AudioRecorder | None = None
        self.mic_test_volume = 0.0
        self.latest_status = "准备就绪"
        self.latest_volume = 0.0
        self._lock = threading.RLock()
        self.logs.info("sidecar", "Aura sidecar started")
        if preload_stt:
            self.warm_up_stt()

    def state(self) -> JsonDict:
        with self._lock:
            try:
                current_mode = mode_payload(self.service.current_mode)
            except RuntimeError:
                current_mode = {
                    "id": "",
                    "name": "暂无模式",
                    "target": "",
                    "description": "modes 目录不存在或为空",
                    "system_prompt": "",
                    "output_hint": "",
                    "source": "official",
                    "enabled": False,
                    "icon": "sparkles",
                    "base_mode_id": "",
                }
            return {
                "settings": settings_payload(self.service.settings),
                "modes": [mode_payload(mode) for mode in self.service.modes.all()],
                "skills": [skill_payload(skill) for skill in self.service.settings.skills],
                "current_mode": current_mode,
                "current_session": session_payload(self.service.current_session),
                "current_clarity": self.service.current_session.latest_clarity,
                "history": self.service.history.recent_sessions(),
                "service": {
                    "stt_provider": self.service.settings.stt_provider,
                    "llm_provider": self.service.compiler.llm.name,
                    "transcriber": self.service.transcriber.name,
                    "transcriber_ready": self.service.transcriber.is_ready,
                    "transcriber_status": self.service.transcriber.status,
                    "transcriber_progress": self.service.transcriber.progress,
                    "transcriber_error": self.service.transcriber.last_error,
                },
                "runtime": self.runtime_status(),
            }

    def runtime_status(self) -> JsonDict:
        with self._lock:
            return {"status": self.latest_status, "volume": self.latest_volume,
                    "mic_test_volume": self.mic_test_volume,
                    "recording": self.recorder is not None, "latest_job_id": self.jobs.latest_job_id,
                    "log_count": len(self.logs.recent())}

    def set_status(self, message: str, level: str = "info", source: str = "runtime") -> None:
        with self._lock:
            self.latest_status = message
        self.logs.add(level, source, message)

    def set_volume(self, volume: float) -> None:
        with self._lock:
            self.latest_volume = volume
            self.latest_status = f"录音中 {volume:.0f}"

    def _on_stt_fallback(self, message: str) -> None:
        """Called when STT warmup falls back from Whisper to SenseVoice."""
        self.set_status(message, level="warning", source="stt")
        self.logs.warning("stt", message)

    def list_devices(self) -> JsonDict:
        devices = [device_payload(device) for device in AudioRecorder.list_input_devices()]
        self.logs.info("audio", f"Loaded {len(devices)} input devices")
        return {"devices": devices}

    def new_session(self, payload: JsonDict) -> JsonDict:
        self._ensure_session_switch_allowed()
        with self._lock:
            session = self.service.new_session(payload.get("mode_id") or self.service.settings.mode_id)
            self.latest_status = "新会话"
            self.logs.info("session", f"New session: {session.id}")
            return {"session": session_payload(session), "state": self.state()}

    def load_session(self, payload: JsonDict) -> JsonDict:
        self._ensure_session_switch_allowed()
        session_id = str(payload.get("session_id") or "")
        if not session_id:
            raise ValueError("session_id is required")
        with self._lock:
            session = self.service.load_session(session_id)
            self.settings_store.save(self.service.settings)
            self.latest_status = f"已切换历史: {session.title}"
            self.logs.info("session", f"Loaded session: {session.id}")
            return {**session_detail_payload(session), "state": self.state()}

    def _ensure_session_switch_allowed(self) -> None:
        if self.recorder is not None:
            raise RuntimeError("录音期间不能切换会话。")
        latest_job_id = self.jobs.latest_job_id
        if latest_job_id and not self.jobs.get(latest_job_id).get("done", False):
            raise RuntimeError("当前需求仍在处理中，请完成后再切换会话。")

    def set_merge_output(self, payload: JsonDict) -> JsonDict:
        enabled = payload.get("merge_output")
        if not isinstance(enabled, bool):
            raise ValueError("merge_output must be a boolean")
        with self._lock:
            self.service.set_merge_output(enabled)
            self.latest_status = "合并需求输出已开启" if enabled else "仅输出本次需求"
            self.logs.info("session", f"Merge output: {enabled}")
            return {"state": self.state()}

    def set_mode(self, payload: JsonDict) -> JsonDict:
        mode_id = str(payload.get("mode_id") or "")
        if not mode_id:
            raise ValueError("mode_id is required")
        with self._lock:
            self.service.set_mode(mode_id)
            self.settings_store.save(self.service.settings)
            self.latest_status = f"模式: {self.service.current_mode.name}"
            self.logs.info("settings", f"Mode changed: {mode_id}")
            return {"state": self.state()}

    def save_modes(self, payload: JsonDict) -> JsonDict:
        raw_modes = payload.get("modes") or []
        modes: list[Mode] = []
        for item in raw_modes:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            system_prompt = str(item.get("system_prompt") or "").strip()
            if not name or not system_prompt:
                raise ValueError("Mode name and system prompt are required.")
            modes.append(
                Mode(
                    id=str(item.get("id") or name),
                    name=name,
                    target=str(item.get("target") or name),
                    description=str(item.get("description") or "").strip(),
                    system_prompt=system_prompt,
                    output_hint=str(item.get("output_hint") or name),
                    source=(
                        "official"
                        if str(item.get("source") or "custom") == "official"
                        else "custom"
                    ),
                    enabled=bool(item.get("enabled", True)),
                    icon=str(item.get("icon") or "sparkles"),
                    base_mode_id=str(item.get("base_mode_id") or ""),
                )
            )
        if not modes:
            raise ValueError("At least one valid mode is required.")
        with self._lock:
            self.service.modes.save_all(modes)
            saved_modes = self.service.modes.all()
            enabled_modes = [mode for mode in saved_modes if mode.enabled]
            available_ids = {mode.id for mode in enabled_modes}
            preferred_id = self.service.settings.mode_id
            if preferred_id not in available_ids:
                private_copy = next(
                    (
                        mode
                        for mode in enabled_modes
                        if mode.base_mode_id == preferred_id
                    ),
                    None,
                )
                if private_copy:
                    preferred_id = private_copy.id
                elif "coding_agent" in available_ids:
                    preferred_id = "coding_agent"
                else:
                    preferred_id = enabled_modes[0].id
            default_mode = next(mode for mode in enabled_modes if mode.id == preferred_id)
            self.service.settings.mode_id = default_mode.id
            self.service.sessions.set_mode(default_mode.id)
            self.settings_store.save(self.service.settings)
            self.latest_status = f"默认模式: {default_mode.name}"
            self.logs.info("settings", "Modes saved")
            return {"state": self.state()}

    def scan_skills(self, payload: JsonDict) -> JsonDict:
        directory = Path(str(payload.get("directory") or "")).expanduser()
        if not directory.exists() or not directory.is_dir():
            raise ValueError("Skill directory does not exist.")
        found: list[Skill] = []
        for path in directory.rglob("SKILL.md"):
            skill = _extract_skill(path)
            if skill:
                found.append(skill)
        with self._lock:
            # A folder selection represents the current scanned source. Keep
            # manually created entries, but replace results from older folders.
            existing = {
                skill.id: skill
                for skill in self.service.settings.skills
                if not skill.source_path
            }
            for skill in found:
                existing[skill.id] = skill
            self.service.settings.skills = list(existing.values())
            self.service.settings.skill_scan_dir = str(directory)
            self.settings_store.save(self.service.settings)
            self.latest_status = f"已提取 {len(found)} 个 Skill"
            self.logs.info("settings", f"Scanned skills: {len(found)} from {directory}")
            return {"skills": [skill_payload(skill) for skill in found], "state": self.state()}

    def save_skills(self, payload: JsonDict) -> JsonDict:
        raw_skills = payload.get("skills") or []
        skills: list[Skill] = []
        for item in raw_skills:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            description = str(item.get("description") or "").strip()
            if not name or not description:
                raise ValueError("Skill name and description are required.")
            source_path = str(item.get("source_path") or "").strip()
            skills.append(
                Skill(
                    id=str(item.get("id") or _skill_id(name, source_path)),
                    name=name,
                    description=description,
                    example=str(item.get("example") or "").strip(),
                    category=str(item.get("category") or "Custom").strip(),
                    enabled=bool(item.get("enabled", True)),
                    source_path=source_path,
                )
            )
        with self._lock:
            self.service.settings.skills = skills
            self.service.settings.skill_scan_dir = str(payload.get("skill_scan_dir") or self.service.settings.skill_scan_dir)
            self.settings_store.save(self.service.settings)
            self.latest_status = "Skill 配置已保存"
            self.logs.info("settings", "Skills saved")
            return {"state": self.state()}

    def save_general_settings(self, payload: JsonDict) -> JsonDict:
        with self._lock:
            settings = self.service.settings
            for key, choices in (("preview_mode", {"bar", "input"}), ("translation_language", LANGUAGES)):
                if key in payload:
                    if payload[key] not in choices:
                        raise ValueError("不支持该设置")
                    setattr(settings, key, payload[key])
            if "voice_shortcuts" in payload:
                settings.voice_shortcuts = validate_keys(payload["voice_shortcuts"])
            if "rewrite_skills" in payload:
                settings.rewrite_skills = validate_skills(payload["rewrite_skills"])
            if "vocabulary" in payload:
                words = payload["vocabulary"]
                if not isinstance(words, list) or len(words) > 200 or any(
                    not isinstance(word, str) or not word.strip() or len(word) > 80 for word in words
                ):
                    raise ValueError("词典最多 200 项，每项 1–80 个字符")
                settings.vocabulary = list(dict.fromkeys(word.strip() for word in words))
            settings.hotkey = str(payload.get("hotkey") or settings.hotkey)
            settings.push_to_talk_key = str(payload.get("push_to_talk_key") or settings.push_to_talk_key)
            settings.auto_copy = bool(payload.get("auto_copy", settings.auto_copy))
            settings.save_history = bool(payload.get("save_history", settings.save_history))
            settings.auto_launch = bool(payload.get("auto_launch", settings.auto_launch))
            theme = str(payload.get("ui_theme") or settings.ui_theme)
            settings.ui_theme = theme if theme in {"morning", "night"} else "morning"
            language = str(payload.get("ui_language") or settings.ui_language)
            settings.ui_language = language if language in {"zh-CN", "zh-TW", "en", "ja"} else "zh-CN"
            self.settings_store.save(settings)
            self.latest_status = "设置已保存"
            self.logs.info("settings", "General settings saved")
            return {"state": self.state()}

    def save_speech_settings(self, payload: JsonDict) -> JsonDict:
        with self._lock:
            settings = self.service.settings
            previous_cache_dir = settings.model_cache_dir
            previous_provider = settings.stt_provider
            settings.input_device_index = payload.get("input_device_index", settings.input_device_index)
            for field in ("asr_api_key", "asr_ws_url", "asr_resource_id"):
                if field in payload and payload[field] != API_KEY_MASK:
                    setattr(settings, field, str(payload[field] or "").strip())
            cache_dir = str(payload.get("model_cache_dir") or "").strip()
            if cache_dir:
                settings.model_cache_dir = Path(cache_dir)
            provider = str(payload.get("stt_provider") or settings.stt_provider)
            settings.stt_provider = (
                provider
                if provider in SUPPORTED_STT_PROVIDERS
                else "sensevoice-small"
            )
            if settings.model_cache_dir != previous_cache_dir or settings.stt_provider != previous_provider:
                self.service.replace_transcriber()
                self.service.warm_up_transcriber_background(
                    on_status=self.set_status,
                    on_fallback=self._on_stt_fallback,
                )
            self.settings_store.save(settings)
            self.latest_status = "语音设置已保存"
            self.logs.info("settings", "Speech settings saved")
            return {"state": self.state()}

    def save_llm_settings(self, payload: JsonDict) -> JsonDict:
        with self._lock:
            settings = self.service.settings
            settings.llm_provider = str(payload.get("llm_provider") or settings.llm_provider)
            settings.llm_base_url = str(payload.get("llm_base_url") or "").strip()
            settings.llm_model = str(payload.get("llm_model") or "").strip()
            # The mask means unchanged; empty input clears the selected key.
            for field in ("deepseek_api_key", "custom_api_key", "ark_api_key"):
                raw_value = payload.get(field)
                if raw_value is not None and raw_value != API_KEY_MASK:
                    setattr(settings, field, str(raw_value).strip())
            settings.llm_thinking_enabled = bool(
                payload.get("llm_thinking_enabled", settings.llm_thinking_enabled)
            )
            if settings.llm_provider == "deepseek" or is_deepseek_endpoint(settings.llm_base_url):
                settings.llm_provider = "deepseek"
                settings.llm_base_url = DEEPSEEK_BASE_URL
                if settings.llm_model not in DEEPSEEK_MODELS:
                    settings.llm_model = "deepseek-v4-flash"
            settings.llm_temperature = float(payload.get("llm_temperature", settings.llm_temperature))
            settings.llm_timeout_seconds = int(payload.get("llm_timeout_seconds", settings.llm_timeout_seconds))
            switch_to_doubao = payload.get("stt_provider") == "doubao-asr" and settings.stt_provider != "doubao-asr"
            if "asr_api_key" in payload and payload["asr_api_key"] != API_KEY_MASK:
                settings.asr_api_key = str(payload["asr_api_key"] or "").strip()
            if switch_to_doubao:
                settings.stt_provider = "doubao-asr"
            self.settings_store.save(settings)
            if switch_to_doubao:
                self.service.replace_transcriber()
            self.service.compiler = PromptCompiler(self.service._build_llm())
            self.latest_status = "LLM 设置已保存"
            self.logs.info("settings", "LLM settings saved")
            return {"state": self.state()}

    def clear_all_data(self, payload: JsonDict) -> JsonDict:
        """Clear all user data including config and history. Requires restart."""
        with self._lock:
            success = self.settings_store.clear_all_data()
            if success:
                self.latest_status = "所有数据已清除，请重启应用"
                self.logs.info("settings", "All user data cleared - restart required")
                return {"success": True, "message": "所有数据已清除，请重启应用"}
            else:
                self.latest_status = "清除数据失败"
                self.logs.error("settings", "Failed to clear user data")
                return {"success": False, "message": "清除数据失败"}

    def warm_up_stt(self) -> JsonDict:
        self.set_status("正在预加载转录模型")
        self.logs.info("stt", "STT preload requested")
        self.service.warm_up_transcriber_background(
            on_status=self.set_status,
            on_fallback=self._on_stt_fallback,
        )
        return {"state": self.state()}

    def test_llm_connection(self, _payload: JsonDict) -> JsonDict:
        """Send a minimal request to verify LLM connectivity and report the result."""
        settings = self.service.settings
        is_deepseek = settings.llm_provider == "deepseek" or is_deepseek_endpoint(settings.llm_base_url)
        is_custom = not is_deepseek and settings.llm_provider != "doubao"
        api_key = settings.deepseek_api_key if is_deepseek else settings.ark_api_key if settings.llm_provider == "doubao" else settings.custom_api_key
        base_url = (settings.llm_base_url or "").strip()
        model = (settings.llm_model or "").strip()

        if not base_url:
            return {"ok": False, "error": "llm.notConfigured"}
        if settings.llm_provider == "doubao" and not api_key:
            return {"ok": False, "error": "请先填写火山方舟 API Key"}
        if is_deepseek and not api_key:
            return {"ok": False, "error": "llm.notConfigured"}
        if is_custom and not api_key and not (base_url and model):
            return {"ok": False, "error": "llm.notConfigured"}

        try:
            audio_check = self.test_microphone({"duration_seconds": 1.2, "keep_audio": False, "transcribe": True})
            transcript = str(audio_check.get("transcript") or "").strip()
            if not transcript:
                return {"ok": False, "error": "语音识别未返回文字，请检查麦克风和 ASR 配置", "asr_ok": False, "llm_ok": False}
            from .providers.llm import OpenAICompatibleClient

            client = OpenAICompatibleClient(
                base_url=base_url,
                api_key=api_key,
                model=model,
                temperature=0.0,
                timeout_seconds=15,
                allow_anonymous=is_custom and not api_key,
                thinking_enabled=None if is_custom else False,
            )
            response = client.chat([
                {"role": "system", "content": "只回复 OK。"},
                {"role": "user", "content": transcript},
            ])
            if response.strip():
                return {"ok": True, "model": model, "provider": "custom" if is_custom else settings.llm_provider, "asr_ok": True, "llm_ok": True, "transcript": transcript}
            return {"ok": False, "error": "llm.emptyResponse"}
        except Exception as exc:
            message = str(exc)
            lower = message.lower()
            if "401" in lower or "unauthorized" in lower or "invalid api key" in lower:
                return {"ok": False, "error": "llm.invalidKey"}
            if "timeout" in lower or "timed out" in lower:
                return {"ok": False, "error": "llm.timeout"}
            if "connection" in lower or "refused" in lower or "resolve" in lower or "not configured" in lower:
                return {"ok": False, "error": "llm.connectionError"}
            return {"ok": False, "error": message[:200]}

    def start_recording(self) -> JsonDict:
        with self._lock:
            if self.recorder is not None:
                return {"state": self.state(), "recording_id": self.recorder.id}
            self.latest_volume = 0.0
            self.latest_status = "正在录音"
            self.logs.info("audio", "Recording started")
            self.recorder = AudioRecorder(
                input_device_index=self.service.settings.input_device_index,
                volume_callback=self.set_volume,
            )
            try:
                provider = self.service.transcriber
                if isinstance(provider, DoubaoTranscriber):
                    self.recording_stream = provider.open_stream()
                    self.recorder.audio_callback = self.recording_stream.feed
                self.recorder.start()
            except Exception:
                if self.recording_stream:
                    self.recording_stream.cancel()
                    self.recording_stream = None
                self.recorder = None
                raise
            return {"state": self.state(), "recording_id": self.recorder.id}

    def preview_recording(self, payload: JsonDict) -> JsonDict:
        if not self._preview_lock.acquire(blocking=False):
            return {"text": ""}
        try:
            with self._lock:
                recorder = self.recorder
                if recorder is None or recorder.id != payload.get("recording_id"):
                    return {"text": ""}
                if self.recording_stream:
                    return {"text": self.recording_stream.text, "snapshot": True}
                audio = recorder.preview_chunk()
            if not audio or not any(audio):
                return {"text": ""}
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "preview.wav"
                with wave.open(str(path), "wb") as wav:
                    wav.setparams((1, 2, recorder.rate, 0, "NONE", "not compressed"))
                    wav.writeframes(audio)
                return {"text": self.service.transcribe(path)}
        finally:
            self._preview_lock.release()

    def stop_recording(self, dictation: bool = False, selected: str = "", language: str = "") -> JsonDict:
        with self._lock:
            if self.recorder is None:
                raise RuntimeError("Recorder is not recording.")
            recorder = self.recorder
            self.recorder = None
            stream, self.recording_stream = self.recording_stream, None
            self.latest_status = "正在转录"
            self.logs.info("audio", "Recording stopped")

        try:
            result = recorder.stop(min_average_volume=1, boost_quiet=stream is None) if dictation else recorder.stop()
        except Exception:
            if stream:
                stream.cancel()
            raise
        job = self._create_job(result)
        thread = threading.Thread(
            target=self._process_recording_job,
            args=(job["id"], result.wav_path, dictation, selected, language, stream),
            daemon=True,
        )
        thread.start()
        return {"job": job, "state": self.state()}

    def cancel_recording(self) -> JsonDict:
        with self._lock:
            recorder = self.recorder
            self.recorder = None
            stream, self.recording_stream = self.recording_stream, None
            self.latest_volume = 0.0
            self.latest_status = "准备就绪"
        if stream:
            stream.cancel()
        if recorder is not None:
            recorder.cancel()
            self.logs.info("audio", "Recording cancelled")
        return {"state": self.state()}

    def _create_job(self, result: RecordingResult) -> JsonDict:
        job = self.jobs.create(recording_payload(result))
        with self._lock:
            self.latest_status = "正在转录"
        self.logs.info("job", f"Job created: {job['id']}")
        return dict(job)

    def _update_job(self, job_id: str, **updates: Any) -> None:
        self.jobs.update(job_id, **updates)

    def _append_job_chunk(self, job_id: str, chunk: str) -> None:
        self.jobs.append_chunk(job_id, chunk)

    def job_status(self, job_id: str) -> JsonDict:
        return {"job": self.jobs.get(job_id), "state": self.state()}

    def _process_recording_job(self, job_id: str, wav_path: Path, dictation: bool = False, selected: str = "", language: str = "", stream: DoubaoStream | None = None) -> None:
        try:
            transcript = (stream.finish() if stream else self.service.transcribe(wav_path, on_status=self.set_status)).strip()
            if not transcript:
                self._update_job(
                    job_id,
                    transcript="",
                    compiled="",
                    phase="done",
                    done=True,
                    error="transcriber.recordingTooQuiet",
                )
                self.set_status("未检测到有效语音，请靠近麦克风重试。")
                self.logs.warning("stt", "Empty transcription – possible microphone or input-device issue")
                return
            if dictation:
                self._update_job(job_id, transcript=transcript, phase="compiling")
                output = (self.service.translate_dictation(transcript, language) if language
                          else self.service.compose_dictation(transcript, selected))
                with self._lock:
                    if self.service.settings.save_history:
                        session = self.service.current_session
                        session.add_turn(
                            raw_transcript=transcript, compiled_text=output,
                            stt_provider=self.service.settings.stt_provider,
                            llm_provider="translation" if language else "voice-edit" if selected else "dictation",
                        )
                        self.service.history.save_session(session)
                    self.latest_status = "听写完成"
                self._update_job(job_id, transcript=transcript, compiled=output, phase="done", done=True)
                return
            self._update_job(job_id, transcript=transcript, phase="compiling")
            self.logs.info("stt", "Transcript ready", transcript)
            self.set_status("正在整理")

            compiled = self.service.compile_transcript(
                transcript,
                on_chunk=lambda chunk: self._append_job_chunk(job_id, chunk),
            ).strip()

            # When falling back to RuleBasedCompiler (no API key), the output is
            # a fixed structural template that looks misleadingly real. Replace it
            # with a clear prompt asking the user to configure their API key.
            if self.service.compiler.llm.name == "rule_based":
                self._update_job(
                    job_id,
                    transcript=transcript,
                    compiled="",
                    phase="done",
                    done=True,
                    error="llm.notConfigured",
                )
                self.set_status("LLM 未配置，请在设置中填写 API Key")
                self.logs.warning("llm", "RuleBasedCompiler blocked – no API key configured")
                return

            self._update_job(job_id, compiled=compiled, phase="done", done=True)
            self.logs.info("llm", "Compile completed", compiled[:1200])
            with self._lock:
                self.latest_status = "已复制" if self.service.settings.auto_copy else "整理完成"
        except Exception as exc:
            message = str(exc)
            # Translate common LLM errors into error codes the frontend can localize.
            error_code = message
            lower = message.lower()
            if "not configured" in lower or "api key" in lower:
                error_code = "llm.notConfigured"
            elif "401" in lower or "unauthorized" in lower or "invalid api key" in lower:
                error_code = "llm.invalidKey"
            elif "timeout" in lower or "timed out" in lower:
                error_code = "llm.timeout"
            elif "connection" in lower or "refused" in lower or "resolve" in lower:
                error_code = "llm.connectionError"
            self._update_job(job_id, phase="error", done=True, error=error_code)
            self.logs.error("job", message)
            self.set_status(message)
        finally:
            if wav_path.exists():
                wav_path.unlink(missing_ok=True)

    def test_microphone(self, payload: JsonDict) -> JsonDict:
        duration = max(0.5, min(float(payload.get("duration_seconds", 3)), 10.0))
        recorder = AudioRecorder(
            input_device_index=self.service.settings.input_device_index,
            volume_callback=self.set_volume,
        )
        with self._lock:
            self.latest_volume = 0.0
        self.set_status("正在测试麦克风")
        self.logs.info("audio", "Microphone test started")
        wav_path: Path | None = None
        try:
            recorder.start()
            time.sleep(duration)
            result = recorder.stop(min_duration_seconds=0.1, min_average_volume=0)
            wav_path = result.wav_path
            transcript = None
            if payload.get("transcribe"):
                transcript = self.service.transcribe(wav_path, on_status=self.set_status).strip()
            if payload.get("keep_audio", True):
                self.last_test_wav = wav_path
            else:
                wav_path.unlink(missing_ok=True)
            self.set_status("麦克风测试完成")
            self.logs.info("audio", "Microphone test completed", json.dumps(recording_payload(result), ensure_ascii=False))
            return {"recording": recording_payload(result), "state": self.state(), "transcript": transcript}
        except Exception:
            self.logs.error("audio", "Microphone test failed")
            if wav_path and wav_path.exists():
                wav_path.unlink(missing_ok=True)
            raise

    def start_microphone_test(self) -> JsonDict:
        with self._lock:
            if self.mic_test_recorder is None:
                self.mic_test_volume = 0.0
                recorder = AudioRecorder(
                    input_device_index=self.service.settings.input_device_index,
                    volume_callback=self._set_mic_test_volume,
                    meter_only=True,
                )
                recorder.start()
                self.mic_test_recorder = recorder
        return {"testing": True}

    def _set_mic_test_volume(self, volume: float) -> None:
        with self._lock:
            self.mic_test_volume = volume

    def stop_microphone_test(self) -> JsonDict:
        with self._lock:
            recorder = self.mic_test_recorder
            self.mic_test_recorder = None
        try:
            if recorder is not None:
                recorder.cancel()
        finally:
            with self._lock:
                self.mic_test_volume = 0.0
        return {"testing": False}

    def transcribe_test_audio(self) -> JsonDict:
        if not self.last_test_wav or not self.last_test_wav.exists():
            raise RuntimeError("请先完成一次麦克风测试。")
        self.set_status("正在转录测试音频")
        text = self.service.transcribe(self.last_test_wav, on_status=self.set_status).strip()
        self.set_status("测试转录完成")
        self.logs.info("stt", "Test transcription completed", text)
        return {"transcript": text, "state": self.state()}

    def update_latest_turn(self, payload: JsonDict) -> JsonDict:
        transcript = str(payload.get("transcript") or "").strip()
        compiled = str(payload.get("compiled") or "").strip()
        if not transcript and not compiled:
            return {"state": self.state()}
        turn = self.service.current_session.update_latest_turn(
            raw_transcript=transcript,
            compiled_text=compiled,
        )
        if turn and self.service.settings.save_history:
            self.service.history.save_session(self.service.current_session)
        return {"state": self.state()}

    def compile_text(self, payload: JsonDict) -> JsonDict:
        transcript = str(payload.get("transcript") or "").strip()
        if not transcript:
            raise ValueError("transcript is required")
        compiled = self.service.compile_only(transcript)
        self.set_status("重新编译完成")
        self.logs.info("llm", "Recompile completed", compiled[:1200])
        return {"transcript": transcript, "compiled": compiled, "state": self.state()}

    def assess_clarity(self, payload: JsonDict) -> JsonDict:
        transcript = str(payload.get("transcript") or "").strip()
        if not transcript or not self.service.supports_structured_analysis:
            return {"clarity": None}
        assessment = self.service.assess_clarity(transcript)
        self.logs.info("clarity", f"Clarity assessed: {assessment.score} ({assessment.level})")
        return {
            "clarity": {
                "score": assessment.score,
                "level": assessment.level,
                "label": assessment.label,
            }
        }

    def generate_questions(self, payload: JsonDict) -> JsonDict:
        transcript = str(payload.get("transcript") or "").strip()
        if not transcript or not self.service.supports_structured_analysis:
            return {"questions": []}
        questions = self.service.generate_supplementary_questions(transcript)
        self.logs.info("clarity", f"Generated {len(questions)} supplementary questions")
        return {
            "questions": [
                {"id": q.id, "question": q.question, "options": q.options, "multi_select": q.multi_select}
                for q in questions
            ]
        }

    def history_entries(self, payload: JsonDict) -> JsonDict:
        rows = self.service.history.entries(str(payload.get("query") or ""), max(0, int(payload.get("offset", 0))))
        return {"entries": rows[:40], "more": len(rows) > 40}

    def delete_entry(self, payload: JsonDict) -> JsonDict:
        entry_id = str(payload.get("id") or "")
        with self._lock:
            session = self.service.current_session
            self.service.history.delete_entry(entry_id)
            session.turns[:] = [turn for turn in session.turns if turn.id != entry_id]
            return {"state": self.state()}

    def clear_history(self) -> JsonDict:
        with self._lock:
            self.service.history.clear()
            self.service.current_session.turns.clear()
            self.latest_status = "历史已清空"
            self.logs.warning("history", "History cleared")
            return {"state": self.state()}

    def delete_history(self, payload: JsonDict) -> JsonDict:
        session_id = str(payload.get("session_id") or "").strip()
        if not session_id:
            raise ValueError("session_id is required")
        with self._lock:
            deleted_current = self.service.current_session.id == session_id
            deleted = self.service.history.delete_session(session_id)
            if deleted_current:
                self.service.new_session(self.service.current_mode.id)
            self.latest_status = "历史记录已删除" if deleted else "历史记录不存在"
            self.logs.info("history", f"History deleted: {session_id}")
            return {
                "deleted": deleted,
                "deleted_current": deleted_current,
                "state": self.state(),
            }

    def recent_logs(self) -> JsonDict:
        return {"logs": self.logs.recent(), "state": self.state()}

    def clear_logs(self) -> JsonDict:
        self.logs.clear()
        self.logs.info("logs", "Logs cleared")
        return {"logs": self.logs.recent(), "state": self.state()}


def build_handler(
    app: AuraSidecar,
    parent_pid: int | None = None,
    auth_token: str = "",
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "AuraSidecar/1.0"

        def _send(self, payload: Any, status: int = 200) -> None:
            body = json_response(payload, status=status)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            origin = self.headers.get("Origin", "")
            if origin in ALLOWED_WEBVIEW_ORIGINS:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Aura-Token")
            self.end_headers()
            self.wfile.write(body)

        def _payload(self) -> JsonDict:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length < 0 or length > MAX_REQUEST_BODY_BYTES:
                raise RequestBodyTooLarge("Request body is too large.")
            if length == 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw) if raw else {}
            if not isinstance(payload, dict):
                raise ValueError("JSON request body must be an object.")
            return payload

        def _authorized(self) -> bool:
            supplied = self.headers.get("X-Aura-Token", "")
            return bool(auth_token) and hmac.compare_digest(supplied, auth_token)

        def _require_authorization(self) -> bool:
            if self._authorized():
                return True
            self._send({"error": "Unauthorized"}, status=401)
            return False

        def do_OPTIONS(self) -> None:
            self._send({})

        def do_GET(self) -> None:
            if not self._require_authorization():
                return
            path = urlparse(self.path).path
            try:
                if path == "/api/health":
                    self._send({
                        "ok": True,
                        "app": "Aura",
                        "api_version": 7,
                        "parent_pid": parent_pid,
                    })
                elif path == "/api/state":
                    self._send(app.state())
                elif path == "/api/devices":
                    self._send(app.list_devices())
                elif path == "/api/status":
                    self._send(app.runtime_status())
                elif path == "/api/logs":
                    self._send(app.recent_logs())
                elif path.startswith("/api/jobs/"):
                    self._send(app.job_status(path.rsplit("/", 1)[-1]))
                else:
                    self._send({"error": f"Unknown endpoint: {path}"}, status=404)
            except Exception as exc:
                app.logs.error("http", str(exc), self.path)
                status = 400 if isinstance(exc, (ValueError, json.JSONDecodeError)) else 500
                self._send({"error": str(exc)}, status=status)

        def do_POST(self) -> None:
            if not self._require_authorization():
                return
            path = urlparse(self.path).path
            try:
                payload = self._payload()
                routes = {
                    "/api/session/new": app.new_session,
                    "/api/session/load": app.load_session,
                    "/api/session/merge-output": app.set_merge_output,
                    "/api/mode": app.set_mode,
                    "/api/modes": app.save_modes,
                    "/api/skills/scan": app.scan_skills,
                    "/api/skills/save": app.save_skills,
                    "/api/settings/skills/import": import_skills,
                    "/api/settings/general": app.save_general_settings,
                    "/api/settings/speech": app.save_speech_settings,
                    "/api/settings/llm": app.save_llm_settings,
                    "/api/settings/clear_all_data": app.clear_all_data,
                    "/api/compile": app.compile_text,
                    "/api/turn/update": app.update_latest_turn,
                    "/api/clarity/assess": app.assess_clarity,
                    "/api/clarity/questions": app.generate_questions,
                    "/api/record/preview": app.preview_recording,
                    "/api/record/start": lambda _: app.start_recording(),
                    "/api/record/stop": lambda payload: app.stop_recording(dictation=payload.get("dictation") is True, selected=str(payload.get("selected") or ""), language=str(payload.get("language") or "")),
                    "/api/record/cancel": lambda _: app.cancel_recording(),
                    "/api/stt/warmup": lambda _: app.warm_up_stt(),
                    "/api/llm/test": app.test_llm_connection,
                    "/api/microphone/test": app.test_microphone,
                    "/api/microphone/start": lambda _: app.start_microphone_test(),
                    "/api/microphone/stop": lambda _: app.stop_microphone_test(),
                    "/api/transcribe/test": lambda _: app.transcribe_test_audio(),
                    "/api/history/entries": app.history_entries,
                    "/api/history/delete-entry": app.delete_entry,
                    "/api/history/delete": app.delete_history,
                    "/api/history/clear": lambda _: app.clear_history(),
                    "/api/logs/clear": lambda _: app.clear_logs(),
                }
                handler = routes.get(path)
                if handler is None:
                    self._send({"error": f"Unknown endpoint: {path}"}, status=404)
                    return
                self._send(handler(payload))
            except Exception as exc:
                app.logs.error("http", str(exc), self.path)
                app.set_status(str(exc), level="error", source="http")
                if isinstance(exc, RequestBodyTooLarge):
                    status = 413
                elif isinstance(exc, (ValueError, json.JSONDecodeError)):
                    status = 400
                else:
                    status = 500
                self._send({"error": str(exc)}, status=status)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            return False
        try:
            exit_code = ctypes.c_ulong()
            return bool(ctypes.windll.kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code))) and exit_code.value == 259
        finally:
            ctypes.windll.kernel32.CloseHandle(process)
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    parent_pid: int | None = None,
    auth_token: str | None = None,
) -> None:
    file_log = _setup_logging()
    file_log.info("Aura sidecar starting... (host=%s port=%s)", host, port)

    try:
        app = AuraSidecar()
    except Exception:
        file_log.critical("Failed to initialize AuraSidecar: %s", traceback.format_exc())
        raise

    token = auth_token or os.environ.get("AURA_SIDECAR_TOKEN") or secrets.token_urlsafe(32)
    server = ThreadingHTTPServer(
        (host, port),
        build_handler(app, parent_pid=parent_pid, auth_token=token),
    )

    # Hook RuntimeLog to also write to file
    _original_add = app.logs.add
    def _add_with_file(level, source, message, details=""):
        log_func = getattr(file_log, level if level in ("debug","info","warning","error","critical") else "info")
        log_func("[%s] %s %s", source, message, details)
        return _original_add(level, source, message, details)
    app.logs.add = _add_with_file  # type: ignore[method-assign]

    print(
        json.dumps(
            {"status": "listening", "host": host, "port": server.server_port, "token": token},
            ensure_ascii=False,
        ),
        flush=True,
    )
    file_log.info("Aura sidecar listening on %s:%s", host, server.server_port)
    if parent_pid is not None:
        def watch_parent() -> None:
            while True:
                time.sleep(0.75)
                if not _process_is_alive(parent_pid):
                    file_log.info("Aura parent process %s exited; stopping sidecar", parent_pid)
                    server.shutdown()
                    return

        threading.Thread(target=watch_parent, name="aura-parent-watch", daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Aura Python sidecar")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--parent-pid", type=int)
    args = parser.parse_args()
    serve(host=args.host, port=args.port, parent_pid=args.parent_pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
