from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

from .config import LOCAL_DATA_DIR_NAME, project_root
from .models import Mode


LEGACY_MODE_IDS = {"concise": "coding_agent", "professional": "coding_agent"}


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_").lower()
    return slug or "mode"


def _default_modes_dir() -> Path:
    if getattr(sys, "frozen", False):
        # PyInstaller bundle: modes/ next to the exe
        return Path(sys.executable).parent / "modes"
    return Path(__file__).resolve().parent.parent / "modes"


def _local_modes_dir() -> Path:
    return project_root() / LOCAL_DATA_DIR_NAME / "modes"


class ModeRegistry:
    def __init__(self, modes_dir: Path | None = None) -> None:
        self.builtin_modes_dir = modes_dir or _default_modes_dir()
        self.modes_dir = modes_dir or _local_modes_dir()
        self._modes: dict[str, Mode] = {}

    def load(self) -> "ModeRegistry":
        self._modes.clear()
        source_dir = self.modes_dir
        if not any(source_dir.glob("*.yaml")):
            source_dir = self.builtin_modes_dir
        if not source_dir.exists():
            return self
        for path in sorted(source_dir.glob("*.yaml")):
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
        mode_id = LEGACY_MODE_IDS.get(mode_id, mode_id)
        if mode_id in self._modes:
            return self._modes[mode_id]
        if self._modes:
            return next(iter(self._modes.values()))
        raise RuntimeError(
            f"No modes found in {self.modes_dir} or {self.builtin_modes_dir}"
        )

    def resolve_id(self, mode_id: str) -> str:
        """Resolve legacy or missing mode IDs to a currently available mode."""
        return self.get(mode_id).id

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
