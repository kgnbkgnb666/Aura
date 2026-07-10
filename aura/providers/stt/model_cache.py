from __future__ import annotations

import os
from pathlib import Path


def _unique_existing_dirs(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        resolved = path.expanduser()
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        result.append(resolved)
    return result


def _modelscope_roots(cache_dir: Path | None) -> list[Path]:
    candidates: list[Path] = []
    if cache_dir is not None:
        candidates.extend([cache_dir / "modelscope", cache_dir])
    if os.environ.get("MODELSCOPE_CACHE"):
        candidates.append(Path(os.environ["MODELSCOPE_CACHE"]))
    candidates.append(Path.home() / ".cache" / "modelscope")
    return _unique_existing_dirs(candidates)


def _modelscope_snapshot(root: Path, repo_id: str, revision: str) -> Path:
    repo_key = repo_id.replace("/", "--")
    return root / "models" / repo_key / "snapshots" / revision


def resolve_modelscope_snapshot(
    cache_dir: Path | None,
    repo_id: str,
    revision: str = "master",
) -> Path | None:
    for root in _modelscope_roots(cache_dir):
        snapshot = _modelscope_snapshot(root, repo_id, revision)
        if (snapshot / "configuration.json").exists():
            return snapshot
    return None


def resolve_modelscope_model(
    cache_dir: Path | None,
    model_id: str,
    revision: str = "master",
) -> str:
    snapshot = resolve_modelscope_snapshot(cache_dir, model_id, revision)
    return str(snapshot) if snapshot else model_id


def resolve_modelscope_alias(cache_dir: Path | None, alias: str, revision: str = "master") -> str:
    alias_map = {
        "fsmn-vad": ("iic/speech_fsmn_vad_zh-cn-16k-common-pytorch", "master"),
    }
    repo_id, default_revision = alias_map.get(alias, (alias, revision))
    snapshot = resolve_modelscope_snapshot(cache_dir, repo_id, default_revision)
    return str(snapshot) if snapshot else alias
