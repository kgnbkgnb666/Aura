from __future__ import annotations

import json
import re
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from .config import LOCAL_DATA_DIR_NAME, project_root
from .models import Mode


LEGACY_MODE_IDS = {"concise": "coding_agent", "professional": "coding_agent"}
MODE_STATE_VERSION = 1
MODE_STATE_FILE = "state.json"
CUSTOM_MODE_ICON = "sparkles"
LEGACY_STANDARD_DESCRIPTION = (
    "面向所有人的全能模式：忠实澄清意图，自动适配任务复杂度，"
    "输出可执行、可验证的高质量提示词。"
)


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_").lower()
    return slug or "mode"


def _default_official_modes_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "modes" / "official"
    return Path(__file__).resolve().parent.parent / "modes" / "official"


def _local_modes_dir() -> Path:
    return project_root() / LOCAL_DATA_DIR_NAME / "modes"


def _same_definition(left: Mode, right: Mode) -> bool:
    return all(
        str(getattr(left, field)).strip() == str(getattr(right, field)).strip()
        for field in (
            "name",
            "target",
            "description",
            "system_prompt",
            "output_hint",
        )
    )


def _is_legacy_standard(mode: Mode) -> bool:
    return (
        mode.id == "coding_agent"
        and mode.name == "标准模式"
        and mode.target == "universal_agent"
        and mode.description == LEGACY_STANDARD_DESCRIPTION
        and mode.output_hint == "clear_actionable_prompt"
    )


def _unique_id(base: str, used: set[str]) -> str:
    candidate = _safe_slug(base)
    suffix = 2
    while candidate in used:
        candidate = f"{_safe_slug(base)}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


class ModeRegistry:
    def __init__(
        self,
        official_modes_dir: Path | None = None,
        local_modes_dir: Path | None = None,
    ) -> None:
        explicit_official_dir = official_modes_dir is not None
        resolved_official_dir = official_modes_dir or _default_official_modes_dir()
        if (resolved_official_dir / "official").is_dir():
            resolved_official_dir = resolved_official_dir / "official"
        self.official_modes_dir = resolved_official_dir
        self.local_modes_dir = (
            local_modes_dir
            or (
                resolved_official_dir.parent / ".local-modes-disabled"
                if explicit_official_dir
                else _local_modes_dir()
            )
        )
        self.custom_modes_dir = self.local_modes_dir / "custom"
        self.state_path = self.local_modes_dir / MODE_STATE_FILE
        self._modes: dict[str, Mode] = {}

    @property
    def builtin_modes_dir(self) -> Path:
        return self.official_modes_dir

    @builtin_modes_dir.setter
    def builtin_modes_dir(self, value: Path) -> None:
        self.official_modes_dir = value / "official" if (value / "official").is_dir() else value

    @property
    def modes_dir(self) -> Path:
        return self.local_modes_dir

    @modes_dir.setter
    def modes_dir(self, value: Path) -> None:
        self.local_modes_dir = value
        self.custom_modes_dir = value / "custom"
        self.state_path = value / MODE_STATE_FILE

    def load(self) -> "ModeRegistry":
        self._migrate_legacy_layout()
        official_modes = self._read_modes(self.official_modes_dir, source="official")
        custom_modes = self._read_modes(self.custom_modes_dir, source="custom")

        modes = list(official_modes)
        used = {mode.id for mode in official_modes}
        for mode in custom_modes:
            if mode.id in used:
                continue
            used.add(mode.id)
            modes.append(mode)

        state = self._load_state()
        enabled_map = state.get("enabled") if isinstance(state.get("enabled"), dict) else {}
        for mode in modes:
            mode.enabled = bool(enabled_map.get(mode.id, True))

        order = state.get("order") if isinstance(state.get("order"), list) else []
        by_id = {mode.id: mode for mode in modes}
        ordered = [by_id[mode_id] for mode_id in order if mode_id in by_id]
        ordered.extend(mode for mode in modes if mode.id not in {item.id for item in ordered})

        if ordered and not any(mode.enabled for mode in ordered):
            ordered[0].enabled = True
            self._write_state(ordered)

        self._modes = {mode.id: mode for mode in ordered}
        return self

    def _read_modes(self, directory: Path, source: str) -> list[Mode]:
        if not directory.exists():
            return []
        modes: list[Mode] = []
        for path in sorted(directory.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not data.get("id"):
                continue
            modes.append(
                Mode(
                    id=str(data["id"]),
                    name=str(data.get("name", data["id"])),
                    target=str(data.get("target", data["id"])),
                    description=str(data.get("description", "")),
                    system_prompt=str(data.get("system_prompt", "")),
                    output_hint=str(data.get("output_hint", "")),
                    source=source,
                    enabled=True,
                    icon=(
                        str(data.get("icon") or CUSTOM_MODE_ICON)
                        if source == "official"
                        else CUSTOM_MODE_ICON
                    ),
                    base_mode_id=str(data.get("base_mode_id") or ""),
                )
            )
        return modes

    def _load_state(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_state(self, modes: list[Mode]) -> None:
        self.local_modes_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": MODE_STATE_VERSION,
            "order": [mode.id for mode in modes],
            "enabled": {mode.id: mode.enabled for mode in modes},
        }
        self.state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_custom_modes(self, modes: list[Mode]) -> None:
        self.custom_modes_dir.mkdir(parents=True, exist_ok=True)
        for path in self.custom_modes_dir.glob("*.yaml"):
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
            if mode.base_mode_id:
                payload["base_mode_id"] = mode.base_mode_id
            filename = f"{index:03d}-{_safe_slug(mode.id)}.yaml"
            (self.custom_modes_dir / filename).write_text(
                yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

    def _migrate_legacy_layout(self) -> None:
        legacy_paths = sorted(self.local_modes_dir.glob("*.yaml"))
        if not legacy_paths:
            return

        official_modes = self._read_modes(self.official_modes_dir, source="official")
        official_by_id = {mode.id: mode for mode in official_modes}
        legacy_modes = self._read_modes(self.local_modes_dir, source="custom")
        custom_modes: list[Mode] = []
        used = set(official_by_id)
        enabled = {mode.id: True for mode in official_modes}
        order = [mode.id for mode in official_modes]

        for mode in legacy_modes:
            official = official_by_id.get(mode.id)
            if official and _is_legacy_standard(mode):
                continue
            if official and _same_definition(mode, official):
                continue
            if official:
                original_id = mode.id
                mode.id = _unique_id(f"{original_id}_custom", used)
                mode.base_mode_id = original_id
                enabled[original_id] = False
            else:
                mode.id = _unique_id(mode.id, used)
            mode.source = "custom"
            mode.icon = CUSTOM_MODE_ICON
            custom_modes.append(mode)
            enabled[mode.id] = True
            order.append(mode.id)

        self._write_custom_modes(custom_modes)
        all_modes = official_modes + custom_modes
        for mode in all_modes:
            mode.enabled = enabled.get(mode.id, True)
        ordered_by_id = {mode.id: mode for mode in all_modes}
        self._write_state([ordered_by_id[mode_id] for mode_id in order if mode_id in ordered_by_id])

        for path in legacy_paths:
            path.unlink()
        (self.local_modes_dir / ".builtin-version").unlink(missing_ok=True)

    def get(self, mode_id: str) -> Mode:
        if not self._modes:
            self.load()
        mode_id = LEGACY_MODE_IDS.get(mode_id, mode_id)
        mode = self._modes.get(mode_id)
        if mode and mode.enabled:
            return mode
        enabled_modes = self.all(enabled_only=True)
        if enabled_modes:
            return enabled_modes[0]
        raise RuntimeError(
            f"No enabled modes found in {self.official_modes_dir} or {self.custom_modes_dir}"
        )

    def resolve_id(self, mode_id: str) -> str:
        return self.get(mode_id).id

    def all(self, enabled_only: bool = False) -> list[Mode]:
        if not self._modes:
            self.load()
        modes = list(self._modes.values())
        return [mode for mode in modes if mode.enabled] if enabled_only else modes

    def save_all(self, modes: list[Mode]) -> "ModeRegistry":
        if not modes:
            raise ValueError("At least one mode is required.")

        official_modes = self._read_modes(self.official_modes_dir, source="official")
        official_by_id = {mode.id: mode for mode in official_modes}
        previous_state = self._load_state()
        previous_enabled = (
            previous_state.get("enabled")
            if isinstance(previous_state.get("enabled"), dict)
            else {}
        )
        reserved_custom_ids = {
            _safe_slug(mode.id or mode.name)
            for mode in modes
            if mode.source == "custom"
        }
        used = set(official_by_id) | reserved_custom_ids
        seen: set[str] = set()
        custom_modes: list[Mode] = []
        enabled = {
            mode.id: bool(previous_enabled.get(mode.id, True))
            for mode in official_modes
        }
        order: list[str] = []

        for mode in modes:
            mode_id = _safe_slug(mode.id or mode.name)
            if mode_id in seen:
                raise ValueError(f"Duplicate mode id: {mode_id}")
            seen.add(mode_id)
            official = official_by_id.get(mode_id)

            if mode.source == "official" and official:
                if _same_definition(mode, official):
                    enabled[official.id] = mode.enabled
                    order.append(official.id)
                    continue

                private_id = _unique_id(f"{official.id}_custom", used)
                private_mode = replace(
                    mode,
                    id=private_id,
                    source="custom",
                    icon=CUSTOM_MODE_ICON,
                    base_mode_id=official.id,
                )
                custom_modes.append(private_mode)
                enabled[official.id] = False
                enabled[private_id] = private_mode.enabled
                order.extend([official.id, private_id])
                continue

            if mode_id in official_by_id:
                mode_id = _unique_id(f"{mode_id}_custom", used)
            custom_mode = replace(
                mode,
                id=mode_id,
                source="custom",
                icon=CUSTOM_MODE_ICON,
            )
            custom_modes.append(custom_mode)
            enabled[custom_mode.id] = custom_mode.enabled
            order.append(custom_mode.id)

        for official in official_modes:
            if official.id not in order:
                order.append(official.id)

        all_by_id = {mode.id: mode for mode in official_modes + custom_modes}
        ordered_modes = [all_by_id[mode_id] for mode_id in order if mode_id in all_by_id]
        for mode in ordered_modes:
            mode.enabled = enabled.get(mode.id, True)
        if not any(mode.enabled for mode in ordered_modes):
            raise ValueError("At least one mode must be enabled.")

        self._write_custom_modes(custom_modes)
        self._write_state(ordered_modes)
        return self.load()
