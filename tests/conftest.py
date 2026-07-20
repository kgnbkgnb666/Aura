import pytest


@pytest.fixture(autouse=True)
def isolate_aura_api_key_environment(monkeypatch):
    """Prove API key environment variables do not affect local-config tests."""
    monkeypatch.delenv("AURA_LLM_API_KEY", raising=False)
    monkeypatch.delenv("AURA_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("AURA_CUSTOM_API_KEY", raising=False)
