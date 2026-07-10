from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import Settings


def app_data_dir(app_name: str = "Aura") -> Path:
    root = os.environ.get("APPDATA")
    if root:
        return Path(root) / app_name
    return Path.home() / f".{app_name.lower()}"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.base_dir = app_data_dir()
        self.path = path or self.base_dir / "config.json"
        self.legacy_path = app_data_dir("AgentVoice") / "config.json"

    def load(self) -> Settings:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        settings = Settings()
        settings.history_path = self.base_dir / "history.sqlite"
        settings.model_cache_dir = project_root() / "models"
        env_api_key = os.environ.get("DEEPSEEK_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
        source_path = self.path
        if not source_path.exists() and self.legacy_path.exists():
            source_path = self.legacy_path

        if not source_path.exists():
            self.save(settings)
            settings.llm_api_key = env_api_key
            return settings

        data = json.loads(source_path.read_text(encoding="utf-8"))
        for key, value in data.items():
            if hasattr(settings, key):
                if key == "history_path" and value:
                    value = Path(value)
                if key == "model_cache_dir" and value:
                    value = Path(value)
                setattr(settings, key, value)
        settings.app_name = "Aura"
        if source_path != self.path and settings.history_path:
            old_history_path = settings.history_path
            settings.history_path = self.base_dir / "history.sqlite"
            if old_history_path.exists() and not settings.history_path.exists():
                settings.history_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old_history_path, settings.history_path)
        if settings.history_path is None:
            settings.history_path = self.base_dir / "history.sqlite"
        if settings.model_cache_dir is None or settings.model_cache_dir.name == "huggingface":
            settings.model_cache_dir = project_root() / "models"
        if settings.stt_provider != "sensevoice-small":
            settings.stt_provider = "sensevoice-small"
        if not settings.llm_api_key:
            settings.llm_api_key = env_api_key
        if source_path != self.path:
            self.save(settings)
        return settings

    def save(self, settings: Settings) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = asdict(settings)
        if payload.get("history_path"):
            payload["history_path"] = str(payload["history_path"])
        if payload.get("model_cache_dir"):
            payload["model_cache_dir"] = str(payload["model_cache_dir"])
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
