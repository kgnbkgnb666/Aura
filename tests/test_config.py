import json

import aura.config as config_module
from aura.config import SettingsStore


def local_store(path, legacy_dir=None):
    return SettingsStore(path, legacy_dir=legacy_dir)


def test_new_local_config_defaults_to_standard_and_ignores_provider_api_key_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "must-not-be-imported")
    store = local_store(tmp_path / "config.local.json")

    settings = store.load()

    assert settings.mode_id == "coding_agent"
    assert settings.deepseek_api_key == ""
    assert settings.llm_provider == "deepseek"
    assert settings.llm_model == "deepseek-v4-flash"
    assert settings.llm_thinking_enabled is False
    assert settings.history_path == tmp_path / ".aura-local" / "history.sqlite"
    assert store.path.exists()


def test_frozen_app_uses_local_appdata_instead_of_install_directory(tmp_path, monkeypatch):
    install_dir = tmp_path / "Program Files" / "Aura"
    local_appdata = tmp_path / "LocalAppData"
    install_dir.mkdir(parents=True)
    monkeypatch.setattr(config_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_module.sys, "executable", str(install_dir / "aura-sidecar.exe"))
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))

    store = SettingsStore()
    settings = store.load()

    assert store.root_dir == local_appdata / "Aura"
    assert store.path == local_appdata / "Aura" / "config.local.json"
    assert settings.history_path == local_appdata / "Aura" / ".aura-local" / "history.sqlite"
    assert not (install_dir / "config.local.json").exists()


def test_legacy_aura_api_key_environment_variable_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_LLM_API_KEY", "environment-secret")
    store = local_store(tmp_path / "config.local.json")

    settings = store.load()
    store.save(settings)
    saved = json.loads(store.path.read_text(encoding="utf-8"))

    assert settings.deepseek_api_key == ""
    assert settings.custom_api_key == ""
    assert "llm_api_key" not in saved
    assert saved["deepseek_api_key"] == ""


def test_legacy_plaintext_key_is_migrated_even_when_old_environment_variable_exists(tmp_path, monkeypatch):
    config_path = tmp_path / "config.local.json"
    config_path.write_text(json.dumps({"llm_api_key": "configured-secret"}), encoding="utf-8")
    monkeypatch.setenv("AURA_LLM_API_KEY", "environment-secret")
    store = local_store(config_path)

    settings = store.load()
    store.save(settings)
    saved = json.loads(config_path.read_text(encoding="utf-8"))

    assert settings.deepseek_api_key == "configured-secret"
    assert "llm_api_key" not in saved
    assert saved["deepseek_api_key"] == "configured-secret"


def test_legacy_appdata_is_copied_and_concise_mode_is_mapped(tmp_path):
    legacy_dir = tmp_path / "legacy" / "Aura"
    legacy_dir.mkdir(parents=True)
    legacy_history = legacy_dir / "history.sqlite"
    legacy_history.write_bytes(b"legacy-history")
    (legacy_dir / "config.json").write_text(
        json.dumps(
            {
                "mode_id": "concise",
                "llm_api_key": "legacy-key",
                "history_path": str(legacy_history),
            }
        ),
        encoding="utf-8",
    )
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    store = local_store(project_dir / "config.local.json", legacy_dir=legacy_dir)

    settings = store.load()

    assert settings.mode_id == "coding_agent"
    assert settings.deepseek_api_key == "legacy-key"
    assert settings.history_path == project_dir / ".aura-local" / "history.sqlite"
    assert settings.history_path.read_bytes() == b"legacy-history"
    assert (legacy_dir / "config.json").exists()
    migrated = json.loads(store.path.read_text(encoding="utf-8"))
    assert "llm_api_key" not in migrated
    assert migrated["deepseek_api_key"] == "legacy-key"


def test_clear_all_data_only_removes_project_local_runtime_files(tmp_path):
    store = local_store(tmp_path / "config.local.json")
    settings = store.load()
    settings.deepseek_api_key = "deepseek-secret"
    settings.custom_api_key = "custom-secret"
    store.save(settings)
    settings.history_path.write_bytes(b"history")
    unrelated = tmp_path / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")

    assert store.clear_all_data() is True
    assert not store.path.exists()
    assert not store.data_dir.exists()
    assert unrelated.exists()


def test_legacy_deepseek_v1_configuration_is_recognized(tmp_path):
    config_path = tmp_path / "config.local.json"
    config_path.write_text(
        json.dumps(
            {
                "llm_provider": "openai_compatible",
                "llm_base_url": "https://api.deepseek.com/v1",
                "llm_model": "deepseek-chat",
                "llm_api_key": "secret",
            }
        ),
        encoding="utf-8",
    )

    store = local_store(config_path)
    settings = store.load()

    assert settings.llm_provider == "deepseek"
    assert settings.llm_base_url == "https://api.deepseek.com"
    assert settings.llm_model == "deepseek-v4-flash"
    assert settings.deepseek_api_key == "secret"
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["deepseek_api_key"] == "secret"


def test_legacy_professional_mode_is_mapped_to_unified_standard(tmp_path):
    config_path = tmp_path / "config.local.json"
    config_path.write_text(json.dumps({"mode_id": "professional"}), encoding="utf-8")

    settings = local_store(config_path).load()

    assert settings.mode_id == "coding_agent"


def test_stt_provider_and_theme_are_persisted(tmp_path):
    store = local_store(tmp_path / "config.local.json")
    settings = store.load()
    settings.stt_provider = "whisper-large-v3"
    settings.ui_theme = "night"
    settings.ui_language = "zh-TW"

    store.save(settings)
    restored = store.load()

    assert restored.stt_provider == "whisper-large-v3"
    assert restored.ui_theme == "night"
    assert restored.ui_language == "zh-TW"


def test_invalid_ui_language_falls_back_to_simplified_chinese(tmp_path):
    config_path = tmp_path / "config.local.json"
    config_path.write_text(json.dumps({"ui_language": "unsupported"}), encoding="utf-8")

    settings = local_store(config_path).load()

    assert settings.ui_language == "zh-CN"


def test_provider_specific_environment_variables_are_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_DEEPSEEK_API_KEY", "deepseek-environment")
    monkeypatch.setenv("AURA_CUSTOM_API_KEY", "custom-environment")
    store = local_store(tmp_path / "config.local.json")

    settings = store.load()

    assert settings.deepseek_api_key == ""
    assert settings.custom_api_key == ""
