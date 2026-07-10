from __future__ import annotations

from typing import Iterable, Protocol


class LLMProvider(Protocol):
    name: str

    def stream_chat(self, messages: list[dict[str, str]]) -> Iterable[str]:
        raise NotImplementedError

    def chat(self, messages: list[dict[str, str]]) -> str:
        return "".join(self.stream_chat(messages))

