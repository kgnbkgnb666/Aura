from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import sys
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


StatusCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class ModelArtifact:
    filename: str
    repository: str
    sha256: str
    start_progress: int
    end_progress: int


MODEL_ARTIFACTS = (
    ModelArtifact(
        filename="sensevoice-small-q8.gguf",
        repository="FunAudioLLM/SenseVoiceSmall-GGUF",
        sha256="4ae45c94422de949b387e2e0fb10d7e14e4c42c69db30c3444ecc7d4b844b7c5",
        start_progress=10,
        end_progress=88,
    ),
    ModelArtifact(
        filename="fsmn-vad.gguf",
        repository="FunAudioLLM/fsmn-vad-GGUF",
        sha256="1270f2559c495f4e7b6e739541151027d360761a3fda43fc147034f5719f5479",
        start_progress=88,
        end_progress=98,
    ),
)


def _runtime_filename() -> str:
    return "llama-funasr-sensevoice.exe" if os.name == "nt" else "llama-funasr-sensevoice"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_runtime_paths() -> list[Path]:
    """Return both packaged and development locations for the native executable."""
    filename = _runtime_filename()
    candidates: list[Path] = []
    configured = os.environ.get("AURA_SENSEVOICE_GGUF_BIN", "").strip()
    if configured:
        candidates.append(Path(configured))

    executable_dir = Path(sys.executable).resolve().parent
    candidates.extend(
        [
            # Windows/Linux Tauri bundles.
            executable_dir / "resources" / "sensevoice-gguf" / filename,
            executable_dir / "sensevoice-gguf" / filename,
            executable_dir / filename,
            # macOS .app/Contents/{MacOS,Resources} layout.
            executable_dir.parent / "Resources" / "sensevoice-gguf" / filename,
        ]
    )

    project_root = Path(__file__).resolve().parents[3]
    candidates.extend(
        [
            project_root / "src-tauri" / "resources" / "sensevoice-gguf" / filename,
            project_root / "sensevoice-gguf" / filename,
        ]
    )
    discovered = shutil.which(filename)
    if discovered:
        candidates.append(Path(discovered))
    return candidates


def resolve_runtime_binary() -> Path | None:
    for candidate in _candidate_runtime_paths():
        if candidate.is_file():
            return candidate.resolve()
    return None


class SenseVoiceGgufTranscriber:
    """SenseVoice Q8 inference through the official llama.cpp runtime."""

    name = "sensevoice-small"

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        binary_path: Path | str | None = None,
    ) -> None:
        root = Path(cache_dir) if cache_dir else Path.cwd() / "models"
        self.cache_dir = root / "sensevoice-gguf"
        self.binary_path = Path(binary_path).resolve() if binary_path else None
        self._lock = threading.Lock()
        self._status = "not_loaded"
        self._progress = 0
        self._last_error = ""
        self._ready = False

    @property
    def status(self) -> str:
        return self._status

    @property
    def progress(self) -> int:
        return self._progress

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def is_ready(self) -> bool:
        return self._ready

    def _artifact_url(self, artifact: ModelArtifact) -> str:
        endpoint = os.environ.get("AURA_HF_ENDPOINT", "https://huggingface.co").rstrip("/")
        return f"{endpoint}/{artifact.repository}/resolve/main/{artifact.filename}?download=true"

    @staticmethod
    def _report(callback: StatusCallback | None, message: str) -> None:
        if callback:
            callback(message)

    def _download_artifact(
        self,
        artifact: ModelArtifact,
        status_callback: StatusCallback | None,
    ) -> Path:
        target = self.cache_dir / artifact.filename
        if target.is_file() and _sha256(target) == artifact.sha256:
            self._progress = artifact.end_progress
            return target
        target.unlink(missing_ok=True)

        partial = target.with_suffix(f"{target.suffix}.part")
        if partial.is_file() and _sha256(partial) == artifact.sha256:
            os.replace(partial, target)
            self._progress = artifact.end_progress
            return target

        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": "Aura-STT/1.0"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(self._artifact_url(artifact), headers=headers)
        self._status = "downloading"
        self._report(status_callback, f"正在下载 {artifact.filename}")

        with urllib.request.urlopen(request, timeout=60) as response:
            append = offset > 0 and getattr(response, "status", None) == 206
            if not append:
                offset = 0
            remaining = int(response.headers.get("Content-Length") or 0)
            total = offset + remaining if remaining else 0
            downloaded = offset
            with partial.open("ab" if append else "wb") as handle:
                while chunk := response.read(1024 * 1024):
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        ratio = min(downloaded / total, 1.0)
                        span = artifact.end_progress - artifact.start_progress
                        self._progress = artifact.start_progress + int(span * ratio)

        if _sha256(partial) != artifact.sha256:
            partial.unlink(missing_ok=True)
            raise RuntimeError(f"Downloaded model checksum mismatch: {artifact.filename}")
        os.replace(partial, target)
        self._progress = artifact.end_progress
        return target

    def load_model(self, status_callback: StatusCallback | None = None) -> None:
        if self._ready:
            self._status = "ready"
            self._progress = 100
            return

        with self._lock:
            if self._ready:
                return
            self._status = "loading"
            self._progress = 5
            self._last_error = ""
            try:
                binary = self.binary_path or resolve_runtime_binary()
                if binary is None:
                    raise RuntimeError(
                        "SenseVoice GGUF runtime is missing for this platform. "
                        "Package it with scripts/sync-sensevoice-runtime.py or set "
                        "AURA_SENSEVOICE_GGUF_BIN."
                    )
                if os.name != "nt":
                    binary.chmod(binary.stat().st_mode | 0o111)
                self.binary_path = binary
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                for artifact in MODEL_ARTIFACTS:
                    self._download_artifact(artifact, status_callback)
                self._ready = True
                self._status = "ready"
                self._progress = 100
                self._report(status_callback, "SenseVoice-Small GGUF Q8 已就绪（CPU）")
            except Exception as exc:
                self._status = "error"
                self._progress = 0
                self._last_error = str(exc)
                logging.getLogger("aura").exception("SenseVoice GGUF preparation failed")
                raise

    def transcribe(self, audio_path: Path, status_callback: StatusCallback | None = None) -> str:
        self.load_model(status_callback=status_callback)
        self._report(status_callback, "正在使用 SenseVoice-Small GGUF Q8 识别语音")
        command = [
            str(self.binary_path),
            "-m",
            str(self.cache_dir / MODEL_ARTIFACTS[0].filename),
            "-a",
            str(audio_path),
            "--vad",
            str(self.cache_dir / MODEL_ARTIFACTS[1].filename),
        ]
        kwargs: dict[str, object] = {
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "check": False,
        }
        if os.name == "nt":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        result = subprocess.run(command, **kwargs)
        if result.returncode != 0:
            diagnostic = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"SenseVoice GGUF transcription failed: {diagnostic}")
        return result.stdout.strip()
