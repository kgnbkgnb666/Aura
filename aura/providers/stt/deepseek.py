import io
import wave
from pathlib import Path

import requests

from ...models import Settings


class DeepSeekTranscriber:
    name = "deepseek-asr"
    status = "ready"
    progress = 100
    last_error = ""
    is_ready = True  # Cloud recognition needs no local model warmup.

    def __init__(self, settings: Settings):
        self.settings = settings

    def load_model(self, status_callback=None):
        if status_callback:
            status_callback("DeepSeek 语音识别已就绪")

    def transcribe(self, audio_path: Path, status_callback=None) -> str:
        key = self.settings.deepseek_api_key.strip()
        if not key:
            raise RuntimeError("请在后台的大模型设置中填写 DeepSeek 密钥")
        if status_callback:
            status_callback("DeepSeek 正在转写")
        parts = []
        with wave.open(str(audio_path), "rb") as source:
            channels, width, rate = source.getparams()[:3]
            frames_per_request = min(120 * rate, (8 * 1024**2 - 44) // (channels * width))
            while frames := source.readframes(frames_per_request):
                audio = io.BytesIO()
                with wave.open(audio, "wb") as chunk:
                    chunk.setparams((channels, width, rate, 0, "NONE", "not compressed"))
                    chunk.writeframes(frames)
                response = requests.post(
                    "https://api.deepseek.com/v1/tools/asr",
                    headers={"Authorization": f"Bearer {key}"},
                    files={"file": ("dictation.wav", audio.getvalue(), "audio/wav")},
                    timeout=(10, 120),
                    allow_redirects=False,
                )
                if response.status_code != 200:
                    raise RuntimeError(f"DeepSeek 语音识别失败（HTTP {response.status_code}）")
                transcript = response.json().get("text")
                if not isinstance(transcript, str):
                    raise RuntimeError("DeepSeek 未返回有效的识别结果")
                if transcript.strip():
                    parts.append(transcript.strip())
        return "\n".join(parts)
