from __future__ import annotations

import logging
import threading
import traceback
from pathlib import Path
from typing import Callable


StatusCallback = Callable[[str], None]


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

                has_cuda = ctranslate2.get_cuda_device_count() > 0
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
        segments, _ = self._model.transcribe(
            str(audio_path),
            beam_size=5,
            vad_filter=True,
            language=None,
        )
        return "".join(segment.text for segment in segments).strip()
