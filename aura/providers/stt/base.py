from __future__ import annotations

from pathlib import Path
from typing import Protocol


class SpeechToTextProvider(Protocol):
    name: str

    def transcribe(self, audio_path: Path) -> str:
        raise NotImplementedError

