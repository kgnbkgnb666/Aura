from __future__ import annotations

import re
from pathlib import Path

import yaml

from .models import Mode


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_").lower()
    return slug or "mode"


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

    def save_all(self, modes: list[Mode]) -> "ModeRegistry":
        if not modes:
            raise ValueError("At least one mode is required.")

        seen: set[str] = set()
        for mode in modes:
            mode.id = _safe_slug(mode.id or mode.name)
            if mode.id in seen:
                raise ValueError(f"Duplicate mode id: {mode.id}")
            seen.add(mode.id)

        self.modes_dir.mkdir(parents=True, exist_ok=True)
        for path in self.modes_dir.glob("*.yaml"):
            path.unlink()

        for index, mode in enumerate(modes, start=1):
            payload = {
                "id": mode.id,
                "name": mode.name.strip() or mode.id,
                "target": mode.target.strip() or mode.id,
                "description": mode.description.strip(),
                "system_prompt": mode.system_prompt.strip(),
                "output_hint": mode.output_hint.strip(),
            }
            filename = f"{index:03d}-{_safe_slug(mode.id)}.yaml"
            (self.modes_dir / filename).write_text(
                yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

        self._modes = {mode.id: mode for mode in modes}
        return self
