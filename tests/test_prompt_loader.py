import json

from aura.prompt_loader import load_prompt_config, prompt_config_dir


def test_prompt_loader_supports_an_external_configuration_directory(tmp_path, monkeypatch):
    payload = {"clarity_system_prompt": "custom clarity prompt"}
    (tmp_path / "structured_analysis.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    monkeypatch.setenv("AURA_PROMPT_DIR", str(tmp_path))
    load_prompt_config.cache_clear()

    assert prompt_config_dir() == tmp_path.resolve()
    assert load_prompt_config("structured_analysis.json") == payload

    load_prompt_config.cache_clear()


def test_bundled_prompt_configs_have_expected_sections():
    load_prompt_config.cache_clear()
    rule_based = load_prompt_config("rule_based.json")
    structured = load_prompt_config("structured_analysis.json")

    assert "zh-CN" in rule_based["templates"]
    assert "decision_partner" in rule_based["mode_guidance"]
    assert structured["clarity_system_prompt"]
    assert structured["supplement_system_prompt"]
