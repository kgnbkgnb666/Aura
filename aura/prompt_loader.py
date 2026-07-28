from __future__ import annotations

import json
import logging
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


def prompt_config_dir() -> Path:
    override = os.environ.get("AURA_PROMPT_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "prompt_templates"
    return Path(__file__).resolve().parent.parent / "prompt_templates"


@lru_cache(maxsize=8)
def load_prompt_config(filename: str) -> dict[str, Any]:
    path = prompt_config_dir() / filename
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging.getLogger("aura").warning("Unable to load prompt config %s: %s", path, exc)
        return {}
    if not isinstance(payload, dict):
        logging.getLogger("aura").warning("Prompt config must be a JSON object: %s", path)
        return {}
    return payload
