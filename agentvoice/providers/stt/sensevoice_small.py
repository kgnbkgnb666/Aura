from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable

from .model_cache import resolve_modelscope_alias, resolve_modelscope_model


StatusCallback = Callable[[str], None]


class SenseVoiceSmallTranscriber:
    name = "sensevoice-small"

    def __init__(
        self,
        model: str = "iic/SenseVoiceSmall",
        vad_model: str = "fsmn-vad",
        language: str = "auto",
        device: str = "cpu",
        cache_dir: Path | str | None = None,
    ) -> None:
        self.model_name = model
        self.vad_model = vad_model
        self.language = language
        self.device = device
        self.cache_dir = Path(cache_dir) if cache_dir else Path.cwd() / "models"
        self._model = None
        self._lock = threading.Lock()
        self._status = "not_loaded"
        self._last_error = ""

    @property
    def status(self) -> str:
        return self._status

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def load_model(self, status_callback: StatusCallback | None = None) -> None:
        if self._model is not None:
            self._status = "ready"
            if status_callback:
                status_callback("SenseVoice-Small 模型已就绪")
            return

        with self._lock:
            if self._model is not None:
                self._status = "ready"
                if status_callback:
                    status_callback("SenseVoice-Small 模型已就绪")
                return

            self._status = "loading"
            self._last_error = ""
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            modelscope_cache = self.cache_dir / "modelscope"
            modelscope_cache.mkdir(parents=True, exist_ok=True)
            os.environ["MODELSCOPE_CACHE"] = str(modelscope_cache)
            os.environ["MODELSCOPE_MODULES_CACHE"] = str(modelscope_cache / "modules")
            if status_callback:
                status_callback(
                    "正在加载 SenseVoice-Small，首次需要下载模型，请稍等\n"
                    f"模型缓存目录: {modelscope_cache}"
                )

            try:
                from funasr import AutoModel
            except ImportError as exc:
                self._status = "error"
                self._last_error = "FunASR is not installed."
                raise RuntimeError(
                    "SenseVoice-Small requires FunASR. Run: pip install funasr modelscope torch"
                ) from exc

            try:
                model_source = resolve_modelscope_model(
                    self.cache_dir,
                    self.model_name,
                    revision="master",
                )
                vad_source = resolve_modelscope_alias(self.cache_dir, self.vad_model)
                self._model = AutoModel(
                    model=model_source,
                    vad_model=vad_source,
                    disable_update=True,
                    device=self.device,
                )
            except Exception as exc:
                self._status = "error"
                self._last_error = str(exc)
                raise

            self._status = "ready"
            if status_callback:
                status_callback("SenseVoice-Small 模型已就绪")

    def transcribe(self, audio_path: Path, status_callback: StatusCallback | None = None) -> str:
        self.load_model(status_callback=status_callback)
        if status_callback:
            status_callback("正在使用 SenseVoice-Small 识别语音")
        result = self._model.generate(
            input=str(audio_path),
            language=self.language,
            use_itn=True,
            batch_size_s=60,
        )
        if not result:
            return ""
        text = str(result[0].get("text", "")).strip()
        try:
            from funasr.utils.postprocess_utils import rich_transcription_postprocess

            text = rich_transcription_postprocess(text)
        except Exception:
            pass
        return text.strip()
