from __future__ import annotations

import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Callable

import numpy as np

from .models import DeviceInfo, RecordingResult


VolumeCallback = Callable[[float], None]


class AudioRecorder:
    format_name = "paInt16"
    channels = 1
    rate = 16000
    chunk = 1024

    def __init__(
        self,
        input_device_index: int | None = None,
        volume_callback: VolumeCallback | None = None,
    ) -> None:
        self.input_device_index = input_device_index
        self.volume_callback = volume_callback
        self._frames: list[bytes] = []
        self._recording = False
        self._audio = None
        self._stream = None
        self._thread: threading.Thread | None = None

    @staticmethod
    def _pyaudio():
        try:
            import pyaudio
        except ImportError as exc:
            raise RuntimeError("PyAudio is not installed. Run: pip install pyaudio") from exc
        return pyaudio

    @classmethod
    def list_input_devices(cls) -> list[DeviceInfo]:
        pyaudio = cls._pyaudio()
        audio = pyaudio.PyAudio()
        try:
            default_index = None
            try:
                default_index = int(audio.get_default_input_device_info()["index"])
            except Exception:
                default_index = None
            devices: list[DeviceInfo] = []
            for index in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(index)
                if int(info.get("maxInputChannels", 0)) <= 0:
                    continue
                devices.append(
                    DeviceInfo(
                        index=index,
                        name=str(info.get("name", f"Device {index}")),
                        max_input_channels=int(info.get("maxInputChannels", 0)),
                        default_sample_rate=int(info.get("defaultSampleRate", cls.rate)),
                        is_default_input=index == default_index,
                    )
                )
            return devices
        finally:
            audio.terminate()

    def start(self) -> None:
        if self._recording:
            return
        pyaudio = self._pyaudio()
        self._frames = []
        self._recording = True
        self._audio = pyaudio.PyAudio()
        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.rate,
            input=True,
            input_device_index=self.input_device_index,
            frames_per_buffer=self.chunk,
        )
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        while self._recording:
            data = self._stream.read(self.chunk, exception_on_overflow=False)
            self._frames.append(data)
            if self.volume_callback:
                audio_data = np.frombuffer(data, dtype=np.int16)
                self.volume_callback(float(np.abs(audio_data).mean()))

    def stop(self, min_duration_seconds: float = 0.4, min_average_volume: float = 40) -> RecordingResult:
        if not self._recording:
            raise RuntimeError("Recorder is not recording.")
        self._recording = False
        if self._thread:
            self._thread.join(timeout=1.5)

        sample_width = None
        try:
            pyaudio = self._pyaudio()
            sample_width = self._audio.get_sample_size(pyaudio.paInt16)
        finally:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
            if self._audio:
                self._audio.terminate()
            self._stream = None
            self._audio = None

        if not self._frames:
            raise RuntimeError("No audio was recorded.")

        raw_audio = b"".join(self._frames)
        samples = np.frombuffer(raw_audio, dtype=np.int16)
        average_volume = float(np.abs(samples).mean())
        max_volume = int(np.abs(samples).max())
        duration = len(self._frames) * self.chunk / self.rate
        if duration < min_duration_seconds:
            raise RuntimeError(f"Recording is too short: {duration:.2f}s")
        if average_volume < min_average_volume:
            raise RuntimeError(f"Recording volume is too low: {average_volume:.0f}")

        wav_path = Path(tempfile.gettempdir()) / f"aura-{time.time_ns()}.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(sample_width or 2)
            wf.setframerate(self.rate)
            wf.writeframes(raw_audio)

        self._frames = []
        return RecordingResult(
            wav_path=wav_path,
            duration_seconds=duration,
            average_volume=average_volume,
            max_volume=max_volume,
        )
