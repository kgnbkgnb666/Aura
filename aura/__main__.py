from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compiler import PromptCompiler
from .config import SettingsStore
from .models import CompileRequest
from .modes import ModeRegistry
from .providers.llm import OpenAICompatibleClient, RuleBasedCompiler
from .service import AuraService


def build_compiler():
    settings = SettingsStore().load()
    if settings.llm_api_key:
        llm = OpenAICompatibleClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    else:
        llm = RuleBasedCompiler()
    return PromptCompiler(llm), settings


def cmd_compile(args: argparse.Namespace) -> int:
    modes = ModeRegistry().load()
    compiler, _settings = build_compiler()
    mode = modes.get(args.mode)
    request = CompileRequest(
        mode=mode,
        current_transcript=args.text,
        previous_compiled_text=args.previous or "",
    )
    for chunk in compiler.stream_compile(request):
        print(chunk, end="", flush=True)
    print()
    return 0


def cmd_transcribe(args: argparse.Namespace) -> int:
    text = AuraService().transcribe(Path(args.audio), on_status=print)
    print(text)
    return 0


def cmd_sidecar(args: argparse.Namespace) -> int:
    from .sidecar import serve

    serve(host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aura")
    sub = parser.add_subparsers(dest="command", required=True)

    compile_parser = sub.add_parser("compile", help="Compile a raw transcript into an agent prompt")
    compile_parser.add_argument("text")
    compile_parser.add_argument("--mode", default="codex")
    compile_parser.add_argument("--previous", default="")
    compile_parser.set_defaults(func=cmd_compile)

    transcribe_parser = sub.add_parser("transcribe", help="Transcribe a wav file with the configured STT provider")
    transcribe_parser.add_argument("audio")
    transcribe_parser.set_defaults(func=cmd_transcribe)

    sidecar_parser = sub.add_parser("sidecar", help="Launch the local HTTP sidecar")
    sidecar_parser.add_argument("--host", default="127.0.0.1")
    sidecar_parser.add_argument("--port", default=8765, type=int)
    sidecar_parser.set_defaults(func=cmd_sidecar)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
