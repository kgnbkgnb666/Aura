from __future__ import annotations

import importlib
import logging
import os
import sys
import threading
import traceback
from pathlib import Path
from typing import Callable


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
        log = logging.getLogger("aura")
        if self._model is not None:
            self._status = "ready"
            self._progress = 100
            if status_callback:
                status_callback("SenseVoice-Small 模型已就绪")
            return

        with self._lock:
            if self._model is not None:
                self._status = "ready"
                self._progress = 100
                if status_callback:
                    status_callback("SenseVoice-Small 模型已就绪")
                return

            self._status = "loading"
            self._progress = 5
            self._last_error = ""
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            modelscope_cache = self.cache_dir / "modelscope"
            modelscope_cache.mkdir(parents=True, exist_ok=True)
            self._progress = 15
            log.info("STT cache_dir=%s  modelscope_cache=%s  frozen=%s  exe=%s",
                     self.cache_dir, modelscope_cache,
                     getattr(sys, "frozen", False),
                     getattr(sys, "executable", "N/A"))
            os.environ["MODELSCOPE_CACHE"] = str(modelscope_cache)
            os.environ["MODELSCOPE_MODULES_CACHE"] = str(modelscope_cache / "modules")
            os.environ.setdefault("MODELSCOPE_OFFLINE", "0")
            if status_callback:
                status_callback(
                    "正在加载 SenseVoice-Small，首次需要下载模型，请稍等\n"
                    f"模型缓存目录: {modelscope_cache}"
                )

            try:
                self._progress = 25
                from funasr import AutoModel
                log.info("FunASR AutoModel imported successfully")
            except ImportError as exc:
                self._status = "error"
                self._progress = 0
                self._last_error = "FunASR is not installed."
                log.error("FunASR import failed: %s", traceback.format_exc())
                raise RuntimeError(
                    "SenseVoice-Small requires FunASR. Run: pip install funasr modelscope torch"
                ) from exc

            # ------------------------------------------------------------------
            # PyInstaller workaround #1: funasr's @tables.register decorator
            # calls inspect.getsourcelines() to record source-location metadata
            # (register.py:78).  PyInstaller does not bundle source code, so
            # getsourcelines() raises OSError.  The actual class registration
            # (register.py:70) happens *before* getsourcelines(), so we only
            # lose debug metadata.  Monkey-patch getsourcelines to return a
            # dummy value so decorators can complete without crashing.
            # ------------------------------------------------------------------
            import inspect as _inspect
            _orig_getsourcelines = _inspect.getsourcelines

            def _pyinstaller_safe_getsourcelines(obj):
                try:
                    return _orig_getsourcelines(obj)
                except OSError:
                    return (["# <pyinstaller: source not available>"], 0)

            _inspect.getsourcelines = _pyinstaller_safe_getsourcelines

            # ------------------------------------------------------------------
            # PyInstaller workaround #2: funasr's __init__.py discovers and
            # imports submodules via pkgutil.walk_packages, which triggers
            # @tables.register decorators.  PyInstaller's virtual filesystem
            # does not support walk_packages, so registries stay empty.
            # Explicitly import the submodules that SenseVoiceSmall and its
            # VAD model (fsmn-vad) need so AutoModel can resolve them.
            # ------------------------------------------------------------------
            try:
                registration_modules = (
                    "funasr.tokenizer.sentencepiece_tokenizer",
                    "funasr.frontends.wav_frontend",
                    "funasr.models.sense_voice.model",
                    "funasr.models.fsmn_vad_streaming.model",
                    "funasr.models.fsmn_vad_streaming.encoder",
                    "funasr.models.specaug.specaug",
                    "funasr.models.normalize.global_mvn",
                    "funasr.models.normalize.utterance_mvn",
                )
                for module_name in registration_modules:
                    importlib.import_module(module_name)

                log.info("FunASR registrations imported successfully")
            except ImportError as exc:
                log.warning("Some FunASR registrations could not be imported: %s", exc)

            try:
                self._progress = 40
                model_root = modelscope_cache / "models"
                sensevoice_cached = any(
                    model_root.glob("*SenseVoiceSmall*/snapshots/*/model.pt")
                )
                vad_cached = any(
                    model_root.glob("*fsmn*vad*/snapshots/*/model.pt")
                )
                models_cached = sensevoice_cached and vad_cached
                self._status = "loading" if models_cached else "downloading"
                if status_callback:
                    status_callback(
                        "检测到本地模型缓存，正在从磁盘加载"
                        if models_cached
                        else "本地模型尚未完整安装，已开始自动下载；首次启动可能需要几分钟"
                    )
                # Always pass model *names* (not local snapshot paths) to
                # AutoModel.  When a local path is passed, FunASR's build_model
                # skips the hub-download path and the tokenizer/frontend
                # registries are never populated, leading to:
                #   TypeError: 'NoneType' object is not callable
                # at tokenizer_class(**tokenizer_conf).
                # The MODELSCOPE_CACHE env var (set above) ensures FunASR finds
                # pre-downloaded models without re-downloading.
                log.info("Calling AutoModel(model=%s, vad_model=%s, device=%s)...",
                         self.model_name, self.vad_model, self.device)
                self._model = AutoModel(
                    model=self.model_name,
                    vad_model=self.vad_model,
                    disable_update=True,
                    device=self.device,
                )
                log.info("AutoModel created successfully: %s", type(self._model))
                self._progress = 90
                self._status = "loading"
                if status_callback:
                    status_callback("模型文件已准备完成，正在初始化语音识别引擎")
            except Exception as exc:
                self._status = "error"
                self._progress = 0
                self._last_error = str(exc)
                log.error("AutoModel creation failed: %s\nTRACEBACK:\n%s",
                          exc, traceback.format_exc())
                raise

            self._status = "ready"
            self._progress = 100
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
