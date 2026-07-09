from __future__ import annotations

from pathlib import Path

import yaml

from .models import Mode


class ModeRegistry:
    def __init__(self, modes_dir: Path | None = None) -> None:
        self.modes_dir = modes_dir or Path(__file__).resolve().parent.parent / "modes"
        self._modes: dict[str, Mode] = {}

    def load(self) -> "ModeRegistry":
        self._modes.clear()
        if not self.modes_dir.exists():
            return self
        for path in sorted(self.modes_dir.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            mode = Mode(
                id=str(data["id"]),
                name=str(data.get("name", data["id"])),
                target=str(data.get("target", data["id"])),
                description=str(data.get("description", "")),
                system_prompt=str(data.get("system_prompt", "")),
                output_hint=str(data.get("output_hint", "")),
            )
            self._modes[mode.id] = mode
        return self

    def get(self, mode_id: str) -> Mode:
        if not self._modes:
            self.load()
        if mode_id in self._modes:
            return self._modes[mode_id]
        if self._modes:
            return next(iter(self._modes.values()))
        raise RuntimeError(f"No modes found in {self.modes_dir}")

    def all(self) -> list[Mode]:
        if not self._modes:
            self.load()
        return list(self._modes.values())

