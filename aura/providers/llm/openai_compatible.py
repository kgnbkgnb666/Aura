from __future__ import annotations

import json
from typing import Iterable

import requests


class OpenAICompatibleClient:
    name = "openai_compatible"
    supports_structured_output = True

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.2,
        timeout_seconds: int = 60,
        allow_anonymous: bool = False,
        thinking_enabled: bool | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        self.allow_anonymous = allow_anonymous
        self.thinking_enabled = thinking_enabled

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.model and (self.api_key or self.allow_anonymous))

    def _url(self) -> str:
        suffix = "/chat/completions" if self.base_url.endswith("/v1") else "/v1/chat/completions"
        return f"{self.base_url}{suffix}"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _payload(self, messages: list[dict[str, str]], stream: bool) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "stream": stream,
        }
        if self.thinking_enabled is not None:
            payload["thinking"] = {
                "type": "enabled" if self.thinking_enabled else "disabled"
            }
        return payload

    def stream_chat(self, messages: list[dict[str, str]]) -> Iterable[str]:
        if not self.is_configured:
            raise RuntimeError("LLM provider is not configured. Add an API Key in Aura's LLM settings.")

        response = requests.post(
            self._url(),
            headers=self._headers(),
            json=self._payload(messages, stream=True),
            timeout=self.timeout_seconds,
            stream=True,
        )
        response.raise_for_status()

        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            if not raw_line.startswith("data:"):
                continue
            data = raw_line.removeprefix("data:").strip()
            if data == "[DONE]":
                break
            payload = json.loads(data)
            delta = payload.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content")
            if content:
                yield content

    def chat(self, messages: list[dict[str, str]]) -> str:
        if not self.is_configured:
            raise RuntimeError("LLM provider is not configured. Add an API Key in Aura's LLM settings.")
        response = requests.post(
            self._url(),
            headers=self._headers(),
            json=self._payload(messages, stream=False),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload["choices"][0]["message"]["content"]).strip()

