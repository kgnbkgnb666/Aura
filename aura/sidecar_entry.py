"""Entry point for PyInstaller-bundled Aura sidecar."""
from __future__ import annotations

import argparse
import sys

from aura.sidecar import serve


def main() -> int:
    parser = argparse.ArgumentParser(prog="aura-sidecar")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--parent-pid", type=int)
    args = parser.parse_args()
    serve(host=args.host, port=args.port, parent_pid=args.parent_pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
