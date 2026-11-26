import json
import wave
from types import SimpleNamespace

import pytest

from aura.recorder import AudioRecorder
from aura.providers.stt.doubao import DoubaoTranscriber
from aura.voice_options import DEFAULT_KEYS, default_skills, import_skills, validate_keys, validate_skills
from aura.config import SettingsStore
from aura.sidecar import AuraSidecar


def test_skill_formats_and_limits():
    rules = default_skills()
    assert import_skills({"filename": "a.json", "content": json.dumps({"version": 1, "skills": rules})})["skills"] == rules
    md = "---\nname: Polish\ndescription: >\n  Make writing\n  sound natural.\n---\nKeep the facts.\n"
    assert import_skills({"filename": "SKILL.md", "content": md})["skills"][0]["intent"] == "Make writing sound natural."
    with pytest.raises(ValueError):
        validate_skills([rules[0], rules[0]])
    with pytest.raises(ValueError):
        validate_keys({**DEFAULT_KEYS, "translate": DEFAULT_KEYS["edit"]})


def test_voice_preferences_persist(tmp_path):
    store = SettingsStore(tmp_path / "config.local.json")
    app = AuraSidecar(settings_store=store)
    app.save_general_settings({"voice_shortcuts": {**DEFAULT_KEYS, "dictate": "F8"},
                               "translation_language": "ja", "preview_mode": "input",
                               "rewrite_skills": []})
    saved = store.load()
    assert (saved.voice_shortcuts["dictate"], saved.translation_language, saved.preview_mode, saved.rewrite_skills) == ("F8", "ja", "input", [])


def test_preview_is_recording_scoped_and_does_not_consume_final_audio(tmp_path, monkeypatch):
    app = AuraSidecar(settings_store=SettingsStore(tmp_path / "config.local.json"))
    recorder = AudioRecorder()
    recorder._frames = [b"\x01\x00" * recorder.chunk for _ in range(28)]
    app.recorder = recorder
    def read_clip(path):
        with wave.open(str(path)) as clip:
            assert clip.getnframes() == 28 * recorder.chunk
        return "字幕"
    monkeypatch.setattr(app.service, "transcribe", read_clip)
    assert app.preview_recording({"recording_id": "old"}) == {"text": ""}
    assert app.preview_recording({"recording_id": recorder.id}) == {"text": "字幕"}
    assert app.preview_recording({"recording_id": recorder.id}) == {"text": ""}
    assert len(recorder._frames) == 28


def test_only_matching_enabled_skill_reaches_rewrite(tmp_path, monkeypatch):
    app = AuraSidecar(settings_store=SettingsStore(tmp_path / "config.local.json"))
    s = app.service
    client = s.compiler.llm
    monkeypatch.setattr(client, "name", "test")
    s.settings.rewrite_skills[1]["enabled"] = False
    calls = []
    def chat(messages):
        calls.append(messages)
        return "完成"
    monkeypatch.setattr(client, "chat", chat)
    assert s.compose_dictation("像我自己说话", "待编辑") == "完成"
    assert len(calls) == 1
    assert s.settings.rewrite_skills[0]["instructions"] in calls[0][0]["content"]
    calls.clear()
    s.compose_dictation("普通听写")
    assert len(calls) == 1
    calls.clear()
    s.translate_dictation("明天见", "en")
    assert len(calls) == 1 and "英语" in calls[0][0]["content"]


def test_doubao_recording_uses_one_stream_for_preview_and_final(tmp_path, monkeypatch):
    app = AuraSidecar(settings_store=SettingsStore(tmp_path / "config.local.json"))
    app.service.settings.save_history = False
    provider = DoubaoTranscriber(app.service.settings)
    app.service.transcriber = provider
    events = []
    stream = SimpleNamespace(
        text="预览",
        feed=lambda audio: events.append(audio),
        finish=lambda: "完整结果",
        cancel=lambda: events.append("cancel"),
    )
    monkeypatch.setattr(provider, "open_stream", lambda: stream)
    monkeypatch.setattr(AudioRecorder, "start", lambda recorder: recorder.audio_callback(b"pcm"))
    monkeypatch.setattr(AudioRecorder, "cancel", lambda recorder: None)
    wav_path = tmp_path / "example.wav"
    monkeypatch.setattr(AudioRecorder, "stop", lambda *args, **kwargs: SimpleNamespace(
        wav_path=wav_path, duration_seconds=1, average_volume=10, max_volume=100,
    ))
    monkeypatch.setattr(app.service, "transcribe", lambda *args, **kwargs: pytest.fail("Unexpected second upload"))
    monkeypatch.setattr(app.service, "compose_dictation", lambda spoken, selected: spoken)
    started = app.start_recording()
    assert app.preview_recording(started) == {"text": "预览", "snapshot": True}
    import aura.sidecar
    monkeypatch.setattr(aura.sidecar.threading, "Thread", lambda *, target, args, daemon: SimpleNamespace(start=lambda: target(*args)))
    stopped = app.stop_recording(dictation=True)
    assert app.jobs.get(stopped["job"]["id"])["compiled"] == "完整结果"
    app.start_recording()
    app.cancel_recording()
    assert events == [b"pcm", b"pcm", "cancel"]
