from __future__ import annotations

import json
from typing import Iterable

import requests


class OpenAICompatibleClient:
    name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.2,
        timeout_seconds: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def stream_chat(self, messages: list[dict[str, str]]) -> Iterable[str]:
        if not self.is_configured:
            raise RuntimeError("LLM provider is not configured. Set DEEPSEEK_API_KEY or configure it.")

        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "stream": True,
            },
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
            raise RuntimeError("LLM provider is not configured. Set DEEPSEEK_API_KEY or configure it.")
        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "stream": False,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload["choices"][0]["message"]["content"]).strip()

