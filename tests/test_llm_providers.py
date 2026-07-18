from aura.models import Settings
from aura.providers.llm import OpenAICompatibleClient
from aura.service import AuraService


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_custom_openai_compatible_allows_empty_key_and_normalizes_v1(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse({"choices": [{"message": {"content": "local result"}}]})

    monkeypatch.setattr("aura.providers.llm.openai_compatible.requests.post", fake_post)
    client = OpenAICompatibleClient(
        base_url="http://127.0.0.1:11434/v1",
        api_key="",
        model="custom-model",
        allow_anonymous=True,
    )

    result = client.chat([{"role": "user", "content": "hello"}])

    assert result == "local result"
    assert captured["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert "Authorization" not in captured["headers"]
    assert "thinking" not in captured["json"]


def test_deepseek_thinking_is_explicitly_disabled_by_default(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse({"choices": [{"message": {"content": "deepseek result"}}]})

    monkeypatch.setattr("aura.providers.llm.openai_compatible.requests.post", fake_post)
    client = OpenAICompatibleClient(
        base_url="https://api.deepseek.com",
        api_key="secret",
        model="deepseek-v4-flash",
        thinking_enabled=False,
    )

    client.chat([{"role": "user", "content": "hello"}])

    assert captured["json"]["model"] == "deepseek-v4-flash"
    assert captured["json"]["thinking"] == {"type": "disabled"}


def test_service_builds_anonymous_custom_provider():
    service = object.__new__(AuraService)
    service.settings = Settings(
        llm_provider="openai_compatible",
        llm_base_url="http://127.0.0.1:8000/v1",
        llm_model="custom-model",
        llm_api_key="",
    )

    client = service._build_llm()

    assert isinstance(client, OpenAICompatibleClient)
    assert client.is_configured is True


def test_service_uses_deepseek_v4_flash_without_thinking_by_default():
    service = object.__new__(AuraService)
    service.settings = Settings(llm_api_key="secret")

    client = service._build_llm()

    assert isinstance(client, OpenAICompatibleClient)
    assert client.model == "deepseek-v4-flash"
    assert client.thinking_enabled is False
