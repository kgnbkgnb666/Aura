from __future__ import annotations

import ctypes
import logging
import os
import threading
import traceback
from pathlib import Path
from typing import Callable


StatusCallback = Callable[[str], None]


def _cuda_runtime_available() -> bool:
    """Check the CUDA libraries required by CTranslate2 before selecting the GPU."""
    libraries = (
        ("cublas64_12.dll", "cudnn_ops64_9.dll")
        if os.name == "nt"
        else ("libcublas.so.12", "libcudnn.so.9")
    )
    loader = ctypes.WinDLL if os.name == "nt" else ctypes.CDLL
    try:
        for library in libraries:
            loader(library)
    except OSError:
        return False
    return True


def _is_cuda_library_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in ("cublas", "cudnn", "cuda runtime", "cuda driver")
    )


# HuggingFace 镜像站（国内用户优先使用镜像加速下载）
_HF_MIRRORS = [
    "https://hf-mirror.com",
    "https://huggingface.co",
]

def _configure_hf_endpoint() -> str:
    """Pick an accessible HuggingFace endpoint and disable Xet when on a mirror.

    huggingface.co is often blocked in China, so we default to hf-mirror.com.
    Mirror backends don't support the Xet CAS protocol, so we also set
    HF_HUB_DISABLE_XET=1 to force plain HTTP downloads.
    """
    if os.environ.get("HF_ENDPOINT"):
        return os.environ["HF_ENDPOINT"]

    if os.environ.get("HF_NO_MIRROR", "").strip() in ("1", "true", "yes"):
        return "https://huggingface.co"

    mirror = os.environ.get("HF_MIRROR", "https://hf-mirror.com")
    os.environ["HF_ENDPOINT"] = mirror

    # Mirror backends don't support Xet — disable it
    if not os.environ.get("HF_HUB_DISABLE_XET"):
        os.environ["HF_HUB_DISABLE_XET"] = "1"

    return mirror


class WhisperLargeV3Transcriber:
    name = "whisper-large-v3"

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        root = Path(cache_dir) if cache_dir else Path.cwd() / "models"
        self.cache_dir = root / "huggingface"
        self._model = None
        self._lock = threading.Lock()
        self._status = "not_loaded"
        self._progress = 0
        self._last_error = ""
        self._device = "cpu"

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
        return self._model is not None

    def load_model(self, status_callback: StatusCallback | None = None) -> None:
        if self._model is not None:
            self._status = "ready"
            self._progress = 100
            return

        with self._lock:
            if self._model is not None:
                return
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._status = "loading"
            self._progress = 10
            self._last_error = ""
            try:
                from faster_whisper import WhisperModel
                import ctranslate2

                # Use mirror for HuggingFace downloads (hf.co blocked in China)
                endpoint = _configure_hf_endpoint()
                logging.getLogger("aura").info(
                    "Whisper HF endpoint: %s", endpoint
                )

                has_cuda = ctranslate2.get_cuda_device_count() > 0 and _cuda_runtime_available()
                device = "cuda" if has_cuda else "cpu"
                compute_type = "float16" if has_cuda else "int8"
                cached = any(
                    self.cache_dir.glob(
                        "models--Systran--faster-whisper-large-v3/snapshots/*/model.bin"
                    )
                )
                self._status = "loading" if cached else "downloading"
                self._progress = 35 if cached else 15
                if status_callback:
                    status_callback(
                        "检测到本地 Whisper Large V3，正在加载"
                        if cached
                        else "正在下载 Whisper Large V3（约 3 GB），请保持网络连接"
                    )
                self._model = WhisperModel(
                    "large-v3",
                    device=device,
                    compute_type=compute_type,
                    download_root=str(self.cache_dir),
                )
                self._device = device
                self._status = "ready"
                self._progress = 100
                if status_callback:
                    status_callback(f"Whisper Large V3 已就绪（{device}）")
            except ImportError as exc:
                self._status = "error"
                self._progress = 0
                self._last_error = "faster-whisper is not installed"
                raise RuntimeError(
                    "Whisper Large V3 requires faster-whisper. Run: pip install faster-whisper"
                ) from exc
            except Exception as exc:
                self._status = "error"
                self._progress = 0
                self._last_error = str(exc)
                logging.getLogger("aura").error(
                    "Whisper Large V3 loading failed: %s\n%s", exc, traceback.format_exc()
                )
                raise

    def transcribe(self, audio_path: Path, status_callback: StatusCallback | None = None) -> str:
        self.load_model(status_callback=status_callback)
        if status_callback:
            status_callback("正在使用 Whisper Large V3 识别语音")
        try:
            segments, _ = self._model.transcribe(
                str(audio_path),
                beam_size=5,
                vad_filter=True,
                language=None,
            )
        except Exception as exc:
            if self._device != "cuda" or not _is_cuda_library_error(exc):
                raise
            logging.getLogger("aura").warning(
                "CUDA runtime is incomplete; retrying Whisper Large V3 on CPU: %s", exc
            )
            if status_callback:
                status_callback("CUDA 运行库不完整，已自动切换到 CPU 模式")
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                "large-v3",
                device="cpu",
                compute_type="int8",
                download_root=str(self.cache_dir),
            )
            self._device = "cpu"
            segments, _ = self._model.transcribe(
                str(audio_path),
                beam_size=5,
                vad_filter=True,
                language=None,
            )
        return "".join(segment.text for segment in segments).strip()
