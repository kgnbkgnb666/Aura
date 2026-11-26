from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import Settings, Skill
from .voice_options import upgrade_default_skills


LOCAL_CONFIG_NAME = "config.local.json"
LOCAL_DATA_DIR_NAME = ".aura-local"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODELS = {"deepseek-v4-flash", "deepseek-v4-pro"}
SUPPORTED_STT_PROVIDERS = {"doubao-asr", "deepseek-asr", "sensevoice-small", "whisper-large-v3"}
SUPPORTED_UI_THEMES = {"morning", "night"}
SUPPORTED_UI_LANGUAGES = {"zh-CN", "zh-TW", "en", "ja"}


def is_deepseek_endpoint(value: str) -> bool:
    normalized = value.strip().lower().rstrip("/")
    return normalized in {DEEPSEEK_BASE_URL, f"{DEEPSEEK_BASE_URL}/v1"}


def legacy_app_data_dir(app_name: str = "Aura") -> Path:
    """Return the pre-0.1 local-data location, used only for one-way migration."""
    root = os.environ.get("APPDATA")
    if root:
        return Path(root) / app_name
    return Path.home() / f".{app_name.lower()}"


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        # Packaged: store all data (config, models, history, API keys)
        # next to the executable so everything lives inside the install
        # directory — easy to manage, back up, or migrate.
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


class SettingsStore:
    def __init__(
        self,
        path: Path | None = None,
        legacy_dir: Path | None = None,
    ) -> None:
        self.root_dir = path.parent.resolve() if path else project_root()
        self.path = path.resolve() if path else self.root_dir / LOCAL_CONFIG_NAME
        self.data_dir = self.root_dir / LOCAL_DATA_DIR_NAME
        self.history_path = self.data_dir / "history.sqlite"
        self.legacy_dir = legacy_dir or (
            legacy_app_data_dir() if path is None else self.root_dir / ".legacy-aura"
        )
    def clear_all_data(self) -> bool:
        """Delete project-local settings and history. Returns True if successful."""
        try:
            self.path.unlink(missing_ok=True)
            if self.data_dir.exists():
                shutil.rmtree(self.data_dir)
            return True
        except Exception as exc:
            import logging

            logging.getLogger("aura").error("Failed to clear user data: %s", exc)
            return False

    def _copy_history(self, source: Path) -> None:
        if not source.exists() or self.history_path.exists():
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, self.history_path)
        for suffix in ("-wal", "-shm"):
            companion = Path(f"{source}{suffix}")
            if companion.exists():
                shutil.copy2(companion, Path(f"{self.history_path}{suffix}"))

    def _migrate_legacy_data(self) -> None:
        """Copy old AppData settings/history once without deleting the originals."""
        if self.path.exists():
            return
        if getattr(sys, "frozen", False):
            # A clean packaged install must never import credentials, history, or
            # settings from an older AppData-based installation. Besides being a
            # privacy surprise, it makes a new install appear preconfigured.
            return
        legacy_config = self.legacy_dir / "config.json"
        if not legacy_config.exists():
            return

        try:
            data = json.loads(legacy_config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        raw_history_path = data.get("history_path")
        source_history = Path(raw_history_path) if raw_history_path else self.legacy_dir / "history.sqlite"
        self._copy_history(source_history)
        legacy_key = str(data.get("llm_api_key") or "").strip()
        configured_base_url = str(data.get("llm_base_url") or "")
        is_deepseek = data.get("llm_provider") != "openai_compatible"
        if configured_base_url:
            is_deepseek = is_deepseek_endpoint(configured_base_url)
        if legacy_key:
            field = "deepseek_api_key" if is_deepseek else "custom_api_key"
            data.setdefault(field, legacy_key)
        data["history_path"] = str(self.history_path)
        if data.get("mode_id") in {"concise", "professional"}:
            data["mode_id"] = "coding_agent"
        self._write_payload(data)

    def load(self) -> Settings:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_data()

        settings = Settings()
        settings.history_path = self.history_path
        settings.model_cache_dir = self.root_dir / "models"

        if not self.path.exists():
            self.save(settings)
            data: dict[str, Any] = {}
        else:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"Invalid local configuration file: {self.path}") from exc

        # Environment variables are useful for packaged deployments and keep
        # provider credentials out of source files.
        for env_name, field in (("ARK_API_KEY", "ark_api_key"), ("ARK_BASE_URL", "llm_base_url"),
                                ("ARK_MODEL", "llm_model"), ("ASR_API_KEY", "asr_api_key"),
                                ("ASR_WS_URL", "asr_ws_url"), ("ASR_RESOURCE_ID", "asr_resource_id")):
            if os.environ.get(env_name) and not data.get(field):
                data[field] = os.environ[env_name]
        if os.environ.get("ARK_API_KEY") and "llm_provider" not in data:
            data["llm_provider"] = "doubao"
            data.setdefault("llm_base_url", "https://ark.cn-beijing.volces.com/api/v3")
            data.setdefault("llm_model", "doubao-seed-2-0-mini-260428")
        if os.environ.get("ASR_API_KEY") and "stt_provider" not in data:
            data["stt_provider"] = "doubao-asr"

        # Consolidate legacy built-in provider choices into the single DeepSeek default.
        # Non-DeepSeek endpoints remain available through the custom compatible interface.
        configured_base_url = str(data.get("llm_base_url") or "")
        if data.get("llm_provider") == "deepseek" or is_deepseek_endpoint(configured_base_url):
            data["llm_provider"] = "deepseek"
            data["llm_base_url"] = DEEPSEEK_BASE_URL
            if data.get("llm_model") not in DEEPSEEK_MODELS:
                data["llm_model"] = "deepseek-v4-flash"
            data["llm_thinking_enabled"] = bool(data.get("llm_thinking_enabled", False))
        elif data.get("llm_provider") in {"anthropic", "local_openai_compatible"}:
            data["llm_provider"] = "openai_compatible"
            data["llm_thinking_enabled"] = False

        for key, value in data.items():
            if key == "llm_api_key":
                continue
            if hasattr(settings, key):
                if key in {"history_path", "model_cache_dir"} and value:
                    value = Path(value)
                if key == "skills" and value:
                    value = [Skill(**item) for item in value if isinstance(item, dict)]
                if key == "rewrite_skills" and isinstance(value, list):
                    value = upgrade_default_skills(value)
                setattr(settings, key, value)

        settings.app_name = "Aura"
        # History is application data and always stays inside this project/install root.
        old_history_path = settings.history_path
        if old_history_path and old_history_path != self.history_path:
            self._copy_history(old_history_path)
        settings.history_path = self.history_path
        if settings.mode_id in {"concise", "professional"}:
            settings.mode_id = "coding_agent"
        if getattr(sys, "frozen", False):
            settings.model_cache_dir = self.root_dir / "models"
        elif settings.model_cache_dir is None or settings.model_cache_dir.name == "huggingface":
            settings.model_cache_dir = self.root_dir / "models"
        if settings.stt_provider not in SUPPORTED_STT_PROVIDERS:
            settings.stt_provider = "sensevoice-small"
        if settings.ui_theme not in SUPPORTED_UI_THEMES:
            settings.ui_theme = "morning"
        if settings.ui_language not in SUPPORTED_UI_LANGUAGES:
            settings.ui_language = "zh-CN"

        legacy_key = str(data.get("llm_api_key") or "").strip()
        if legacy_key:
            if settings.llm_provider == "deepseek" and not settings.deepseek_api_key:
                settings.deepseek_api_key = legacy_key
            elif settings.llm_provider != "deepseek" and not settings.custom_api_key:
                settings.custom_api_key = legacy_key
        if "llm_api_key" in data:
            self.save(settings)
        return settings

    def _write_payload(self, payload: dict[str, Any]) -> None:
        payload.pop("llm_api_key", None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
        try:
            self.path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            # Some Windows/network filesystems do not expose POSIX-style modes.
            pass

    def save(self, settings: Settings) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        settings.history_path = self.history_path
        payload: dict[str, Any] = asdict(settings)
        if payload.get("history_path"):
            payload["history_path"] = str(payload["history_path"])
        if payload.get("model_cache_dir"):
            payload["model_cache_dir"] = str(payload["model_cache_dir"])
        self._write_payload(payload)
