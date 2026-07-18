import json

from aura.config import SettingsStore


def test_new_local_config_defaults_to_professional_and_ignores_api_key_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "must-not-be-imported")
    store = SettingsStore(tmp_path / "config.local.json")

    settings = store.load()

    assert settings.mode_id == "professional"
    assert settings.llm_api_key == ""
    assert settings.llm_provider == "deepseek"
    assert settings.llm_model == "deepseek-v4-flash"
    assert settings.llm_thinking_enabled is False
    assert settings.history_path == tmp_path / ".aura-local" / "history.sqlite"
    assert store.path.exists()


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
    store = SettingsStore(project_dir / "config.local.json", legacy_dir=legacy_dir)

    settings = store.load()

    assert settings.mode_id == "coding_agent"
    assert settings.llm_api_key == "legacy-key"
    assert settings.history_path == project_dir / ".aura-local" / "history.sqlite"
    assert settings.history_path.read_bytes() == b"legacy-history"
    assert (legacy_dir / "config.json").exists()


def test_clear_all_data_only_removes_project_local_runtime_files(tmp_path):
    store = SettingsStore(tmp_path / "config.local.json")
    settings = store.load()
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

    settings = SettingsStore(config_path).load()

    assert settings.llm_provider == "deepseek"
    assert settings.llm_base_url == "https://api.deepseek.com"
    assert settings.llm_model == "deepseek-v4-flash"
