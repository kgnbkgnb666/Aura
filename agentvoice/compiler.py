from __future__ import annotations

from collections.abc import Iterable

from .models import CompileRequest
from .providers.llm import LLMProvider, RuleBasedCompiler


class PromptCompiler:
    def __init__(self, llm: LLMProvider | None = None) -> None:
        self.llm = llm or RuleBasedCompiler()

    def stream_compile(self, request: CompileRequest) -> Iterable[str]:
        yield from self.llm.stream_chat(request.as_messages())

    def compile(self, request: CompileRequest) -> str:
        return "".join(self.stream_compile(request)).strip()

