from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import Settings, Skill


def app_data_dir(app_name: str = "Aura") -> Path:
    root = os.environ.get("APPDATA")
    if root:
        return Path(root) / app_name
    return Path.home() / f".{app_name.lower()}"


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        # PyInstaller bundle: project root is the exe directory
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.base_dir = app_data_dir()
        self.path = path or self.base_dir / "config.json"
        # Removed legacy AgentVoice migration to prevent data leakage

    def clear_all_data(self) -> bool:
        """Delete all user data including config and history. Returns True if successful."""
        try:
            if self.base_dir.exists():
                shutil.rmtree(self.base_dir)
            return True
        except Exception as e:
            import logging
            logging.getLogger("aura").error(f"Failed to clear user data: {e}")
            return False

    def load(self) -> Settings:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        settings = Settings()
        settings.history_path = self.base_dir / "history.sqlite"
        settings.model_cache_dir = project_root() / "models"
        env_api_key = os.environ.get("DEEPSEEK_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")

        if not self.path.exists():
            self.save(settings)
            settings.llm_api_key = env_api_key
            return settings

        data = json.loads(self.path.read_text(encoding="utf-8"))
        for key, value in data.items():
            if hasattr(settings, key):
                if key == "history_path" and value:
                    value = Path(value)
                if key == "model_cache_dir" and value:
                    value = Path(value)
                if key == "skills" and value:
                    value = [Skill(**item) for item in value if isinstance(item, dict)]
                setattr(settings, key, value)
        settings.app_name = "Aura"
        # Removed legacy AgentVoice migration logic
        if settings.history_path is None:
            settings.history_path = self.base_dir / "history.sqlite"
        # When running as a frozen (PyInstaller) bundle, always pin model_cache_dir
        # to the install directory.  config.json may carry a stale dev-mode path
        # from a previous development run, which would point to the source tree
        # instead of <install>/models and break FunASR's tokenizer registry.
        if getattr(sys, "frozen", False):
            settings.model_cache_dir = project_root() / "models"
        elif settings.model_cache_dir is None or settings.model_cache_dir.name == "huggingface":
            settings.model_cache_dir = project_root() / "models"
        if settings.stt_provider != "sensevoice-small":
            settings.stt_provider = "sensevoice-small"
        if not settings.llm_api_key:
            settings.llm_api_key = env_api_key
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
