from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import aura.providers.stt.sensevoice_gguf as gguf
from aura.models import Settings
from aura.modes import ModeRegistry
from aura.providers.stt import SenseVoiceGgufTranscriber, SenseVoiceSmallTranscriber
from aura.service import AuraService


def _artifact(filename: str, content: bytes, start: int, end: int) -> gguf.ModelArtifact:
    return gguf.ModelArtifact(
        filename=filename,
        repository="test/repository",
        sha256=hashlib.sha256(content).hexdigest(),
        start_progress=start,
        end_progress=end,
    )


def test_load_uses_existing_verified_artifacts(tmp_path, monkeypatch):
    binary = tmp_path / gguf._runtime_filename()
    binary.write_bytes(b"runtime")
    cache = tmp_path / "cache" / "sensevoice-gguf"
    cache.mkdir(parents=True)
    model = b"model"
    vad = b"vad"
    artifacts = (_artifact("model.gguf", model, 10, 80), _artifact("vad.gguf", vad, 80, 98))
    monkeypatch.setattr(gguf, "MODEL_ARTIFACTS", artifacts)
    (cache / "model.gguf").write_bytes(model)
    (cache / "vad.gguf").write_bytes(vad)

    transcriber = gguf.SenseVoiceGgufTranscriber(cache_dir=tmp_path / "cache", binary_path=binary)
    transcriber.load_model()

    assert transcriber.is_ready
    assert transcriber.progress == 100
    assert transcriber.status == "ready"


def test_transcribe_invokes_native_runtime(tmp_path, monkeypatch):
    binary = tmp_path / gguf._runtime_filename()
    binary.write_bytes(b"runtime")
    cache = tmp_path / "cache" / "sensevoice-gguf"
    cache.mkdir(parents=True)
    model = b"model"
    vad = b"vad"
    artifacts = (_artifact("model.gguf", model, 10, 80), _artifact("vad.gguf", vad, 80, 98))
    monkeypatch.setattr(gguf, "MODEL_ARTIFACTS", artifacts)
    (cache / "model.gguf").write_bytes(model)
    (cache / "vad.gguf").write_bytes(vad)
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"wav")
    captured: list[list[str]] = []

    def fake_run(command, **kwargs):
        captured.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="hello world\n", stderr="")

    monkeypatch.setattr(gguf.subprocess, "run", fake_run)
    transcriber = gguf.SenseVoiceGgufTranscriber(cache_dir=tmp_path / "cache", binary_path=binary)

    assert transcriber.transcribe(audio) == "hello world"
    assert captured[0] == [
        str(binary.resolve()),
        "-m",
        str(cache / "model.gguf"),
        "-a",
        str(audio),
        "--vad",
        str(cache / "vad.gguf"),
    ]


def test_sensevoice_small_defaults_to_funasr_runtime(tmp_path):
    """The default 'sensevoice-small' provider currently uses the FunASR SenseVoiceSmallTranscriber.
    The GGUF native runtime is available as a separate opt-in provider."""
    settings = Settings(
        model_cache_dir=tmp_path,
        history_path=tmp_path / "history.sqlite",
        stt_provider="sensevoice-small",
    )
    service = AuraService(settings=settings, modes=ModeRegistry().load())

    assert isinstance(service.transcriber, SenseVoiceSmallTranscriber)


def test_legacy_funasr_provider_remains_available(tmp_path):
    settings = Settings(
        model_cache_dir=tmp_path,
        history_path=tmp_path / "history.sqlite",
        stt_provider="sensevoice-funasr",
    )
    service = AuraService(settings=settings, modes=ModeRegistry().load())

    assert isinstance(service.transcriber, SenseVoiceSmallTranscriber)
