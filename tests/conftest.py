import pytest


@pytest.fixture(autouse=True)
def isolate_aura_api_key_environment(monkeypatch):
    """Keep developer credentials out of tests unless a test opts in explicitly."""
    monkeypatch.delenv("AURA_LLM_API_KEY", raising=False)
