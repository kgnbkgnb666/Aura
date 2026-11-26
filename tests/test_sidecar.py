import json
import os
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from aura.config import SettingsStore
from aura.models import RecordingResult
from aura.providers.llm import OpenAICompatibleClient
from aura.providers.llm.base import UnsupportedLLMCapabilityError
from aura.recorder import AudioRecorder
from aura.sidecar import (
    API_KEY_MASK,
    MAX_REQUEST_BODY_BYTES,
    AuraSidecar,
    _setup_logging,
    _process_is_alive,
    build_handler,
    json_response,
    settings_payload,
)


def local_app(tmp_path):
    return AuraSidecar(
        preload_stt=False,
        settings_store=SettingsStore(tmp_path / "config.local.json"),
    )


def test_parent_process_liveness_detection():
    assert _process_is_alive(os.getpid()) is True
    assert _process_is_alive(0) is False


def test_microphone_check_only_transcribes_on_request(tmp_path, monkeypatch):
    app = local_app(tmp_path)
    audio = tmp_path / "mic.wav"
    calls = []
    monkeypatch.setattr("aura.sidecar.time.sleep", lambda _: None)
    monkeypatch.setattr(AudioRecorder, "start", lambda recorder: recorder.volume_callback(300))

    def stop(recorder, **kwargs):
        audio.write_bytes(b"fixture")
        return RecordingResult(audio, 1, 300, 900)

    def transcribe(path, **kwargs):
        assert path.read_bytes() == b"fixture"
        calls.append(path)
        return "测试成功"

    monkeypatch.setattr(AudioRecorder, "stop", stop)
    monkeypatch.setattr(app.service, "transcribe", transcribe)
    assert app.test_microphone({"keep_audio": False})["transcript"] is None
    assert not calls and not audio.exists()
    assert app.test_microphone({"keep_audio": False, "transcribe": True})["transcript"] == "测试成功"
    assert calls == [audio] and not audio.exists()


def test_mic_meter_stops_without_recording_audio(tmp_path, monkeypatch):
    app = local_app(tmp_path)
    cancelled = []

    def start(recorder):
        assert recorder.meter_only
        recorder.volume_callback(300)

    monkeypatch.setattr(AudioRecorder, "start", start)
    monkeypatch.setattr(AudioRecorder, "cancel", lambda recorder: cancelled.append(recorder))
    assert app.start_microphone_test() == {"testing": True}
    assert app.runtime_status()["mic_test_volume"] == 300
    assert app.runtime_status()["volume"] == 0
    assert app.stop_microphone_test() == {"testing": False}
    assert len(cancelled) == 1
    assert app.runtime_status()["mic_test_volume"] == 0


def test_sidecar_logging_is_rotating_persistent_and_not_duplicated(tmp_path, monkeypatch):
    monkeypatch.setattr("aura.sidecar._log_dir", lambda: tmp_path)
    logger = _setup_logging()
    logger = _setup_logging()
    handlers = [
        handler for handler in logger.handlers
        if getattr(handler, "_aura_sidecar_file", False)
    ]
    assert len(handlers) == 1
    assert handlers[0].backupCount == 7
    logger.info("persistent-test-message")
    handlers[0].flush()
    assert "persistent-test-message" in (tmp_path / "aura-sidecar.log").read_text("utf-8")
    logger.removeHandler(handlers[0])
    handlers[0].close()


def test_rule_based_fallback_skips_structured_llm_features(tmp_path):
    app = local_app(tmp_path)
    assert app.service.supports_structured_analysis is False
    assert app.assess_clarity({"transcript": "some request"}) == {"clarity": None}
    assert app.generate_questions({"transcript": "some request"}) == {"questions": []}
    with pytest.raises(UnsupportedLLMCapabilityError):
        app.service.assess_clarity("some request")


def test_json_response_serializes_paths_and_dataclasses(tmp_path):
    app = local_app(tmp_path)
    body = json_response(app.state()).decode("utf-8")
    assert '"settings"' in body
    assert '"modes"' in body
    assert '"current_session"' in body


def test_sidecar_state_has_frontend_contract(tmp_path):
    app = local_app(tmp_path)
    state = app.state()
    assert state["settings"]["app_name"] == "Aura"
    assert isinstance(state["modes"], list)
    assert state["settings"]["mode_id"] == "coding_agent"
    assert state["current_mode"]["id"] == "coding_agent"
    assert state["current_session"]["mode_id"] == "coding_agent"
    assert state["runtime"]["recording"] is False
    assert state["runtime"]["latest_job_id"] == ""
    assert state["runtime"]["log_count"] >= 1
    assert "llm_provider" in state["service"]
    assert state["service"]["stt_provider"] == "deepseek-asr"
    assert state["service"]["transcriber_status"] == "ready"
    assert state["service"]["transcriber_progress"] == 100


def test_sidecar_job_contract(tmp_path):
    app = local_app(tmp_path)
    result = RecordingResult(
        wav_path=tmp_path / "test.wav",
        duration_seconds=1.0,
        average_volume=100.0,
        max_volume=500,
    )
    job = app._create_job(result)
    app._update_job(job["id"], transcript="hello", phase="compiling")
    app._append_job_chunk(job["id"], "compiled")
    payload = app.job_status(job["id"])
    assert payload["job"]["transcript"] == "hello"
    assert payload["job"]["compiled"] == "compiled"
    assert payload["job"]["phase"] == "compiling"


def test_voice_edit_recovers_final_text_across_restart(tmp_path, monkeypatch):
    app = local_app(tmp_path)
    monkeypatch.setattr(app.service, "transcribe", lambda *a, **kw: "改成周四")
    def compose(spoken, selected):
        assert (spoken, selected) == ("改成周四", "周三开会")
        return "周四开会"

    monkeypatch.setattr(app.service, "compose_dictation", compose)
    result = RecordingResult(tmp_path / "demo.wav", 1.0, 100.0, 500)
    job = app._create_job(result)
    app._process_recording_job(job["id"], result.wav_path, dictation=True, selected="周三开会")
    assert app.job_status(job["id"])["job"]["compiled"] == "周四开会"
    entry, = local_app(tmp_path).history_entries({})["entries"]
    assert entry["compiled_text"] == "周四开会"


def test_settings_dictionary_persists_and_reaches_text_model(tmp_path, monkeypatch):
    app = local_app(tmp_path)
    app.save_general_settings({"vocabulary": [" WebView2 ", "WebView2"]})
    restored = local_app(tmp_path)
    assert restored.state()["settings"]["vocabulary"] == ["WebView2"]
    llm = restored.service.compiler.llm
    monkeypatch.setattr(llm, "name", "test")
    def chat(messages):
        assert "WebView2" in messages[0]["content"]
        return "WebView2"
    monkeypatch.setattr(llm, "chat", chat)
    assert restored.service.compose_dictation("web view two") == "WebView2"


def test_history_search_delete_and_disabled_save(tmp_path, monkeypatch):
    app = local_app(tmp_path)
    monkeypatch.setattr(app.service, "transcribe", lambda *args, **kwargs: "原话")
    monkeypatch.setattr(app.service, "compose_dictation", lambda *args: "整理结果")
    def record():
        wav = tmp_path / "test.wav"
        job = app._create_job(RecordingResult(wav, 1, 100, 100))
        app._process_recording_job(job["id"], wav, True)
    record()
    row, = app.history_entries({"query": "结果"})["entries"]
    assert row["raw_transcript"] == "原话"
    app.delete_entry({"id": row["id"]})
    app.save_general_settings({"save_history": False})
    record()
    app.save_general_settings({"save_history": True})
    record()
    rows = app.history_entries({"query": "原话"})["entries"]
    assert len(rows) == 1 and rows[0]["id"] != row["id"]
    app.clear_history()
    assert app.history_entries({})["entries"] == []


def test_unconfigured_model_keeps_dictation_and_declines_edit(tmp_path):
    service = local_app(tmp_path).service
    assert service.compose_dictation("周四开会") == "周四开会"
    with pytest.raises(RuntimeError, match="配置文字模型"):
        service.compose_dictation("改成周四", "周三开会")


def test_sidecar_logs_contract(tmp_path):
    app = local_app(tmp_path)
    app.logs.warning("test", "careful", "details")
    payload = app.recent_logs()
    assert payload["logs"][0]["level"] == "warning"
    assert payload["logs"][0]["source"] == "test"
    assert payload["logs"][0]["details"] == "details"
    cleared = app.clear_logs()
    assert len(cleared["logs"]) == 1
    assert cleared["logs"][0]["message"] == "Logs cleared"


def test_sidecar_save_modes_preserves_current_mode(tmp_path):
    app = local_app(tmp_path)
    app.service.modes.modes_dir = tmp_path / "modes"
    modes = app.state()["modes"]
    modes.append(
        {
            "id": "reviewer",
            "name": "审查模式",
            "target": "code_review",
            "description": "Review code",
            "system_prompt": "Review the transcript as a code review request.",
            "output_hint": "review",
            "source": "custom",
            "enabled": True,
            "icon": "sparkles",
            "base_mode_id": "",
        }
    )
    payload = app.save_modes({"modes": modes})
    state = payload["state"]
    assert [mode["id"] for mode in state["modes"]] == [
        "coding_agent",
        "decision_partner",
        "creative_studio",
        "reviewer",
    ]
    assert state["settings"]["mode_id"] == "coding_agent"
    assert state["current_session"]["mode_id"] == "coding_agent"
    assert (tmp_path / "modes" / "custom" / "001-reviewer.yaml").exists()


def test_sidecar_rejects_empty_mode_list(tmp_path):
    app = local_app(tmp_path)

    try:
        app.save_modes({"modes": []})
    except ValueError as exc:
        assert "At least one" in str(exc)
    else:
        raise AssertionError("empty mode list should be rejected")


def test_http_api_requires_token_and_limits_request_body(tmp_path):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        build_handler(local_app(tmp_path), auth_token="test-token"),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        try:
            urlopen(f"{base_url}/api/health", timeout=2)
        except HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("unauthenticated request should be rejected")

        request = Request(
            f"{base_url}/api/health",
            headers={"X-Aura-Token": "test-token", "Origin": "https://evil.example"},
        )
        with urlopen(request, timeout=2) as response:
            assert json.load(response)["api_version"] == 6
            assert response.headers.get("Access-Control-Allow-Origin") is None

        oversized = Request(
            f"{base_url}/api/compile",
            method="POST",
            headers={
                "X-Aura-Token": "test-token",
                "Content-Type": "application/json",
                "Content-Length": str(MAX_REQUEST_BODY_BYTES + 1),
            },
            data=b"{}",
        )
        try:
            urlopen(oversized, timeout=2)
        except HTTPError as exc:
            assert exc.code == 413
        else:
            raise AssertionError("oversized request should be rejected")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_sidecar_load_session_restores_turn_context(tmp_path):
    app = local_app(tmp_path)
    app.service.current_session.add_turn(
        raw_transcript="first request",
        compiled_text="compiled first request",
        stt_provider="test-stt",
        llm_provider="test-llm",
    )
    app.service.current_session.add_turn(
        raw_transcript="second request",
        compiled_text="compiled second request",
        stt_provider="test-stt",
        llm_provider="test-llm",
    )
    session_id = app.service.current_session.id
    app.service.history.save_session(app.service.current_session)
    recent = app.service.history.recent_sessions()
    assert recent[0]["last_transcript"] == "second request"
    assert recent[0]["last_compiled"] == "compiled second request"
    assert recent[0]["turn_count"] == 2
    app.new_session({"mode_id": app.service.settings.mode_id})

    payload = app.load_session({"session_id": session_id})

    assert payload["transcript"] == "second request"
    assert payload["compiled"] == "compiled second request"
    assert payload["state"]["current_session"]["id"] == session_id
    assert app.service.sessions.previous_transcripts() == ["first request", "second request"]
    assert app.service.sessions.previous_compiled_text() == "compiled second request"


def test_merge_output_is_session_scoped_and_defaults_to_enabled(tmp_path):
    app = local_app(tmp_path)

    disabled = app.set_merge_output({"merge_output": False})
    assert disabled["state"]["current_session"]["merge_output"] is False

    app.service.current_session.add_turn(
        raw_transcript="first session",
        compiled_text="first result",
        stt_provider="test-stt",
        llm_provider="test-llm",
    )
    first_session_id = app.service.current_session.id
    app.service.history.save_session(app.service.current_session)

    new_session = app.new_session({"mode_id": app.service.settings.mode_id})
    assert new_session["state"]["current_session"]["merge_output"] is True
    assert new_session["state"]["current_session"]["turn_count"] == 0

    restored = app.load_session({"session_id": first_session_id})
    assert restored["state"]["current_session"]["merge_output"] is False
    assert restored["state"]["current_session"]["turn_count"] == 1


def test_session_switch_is_blocked_while_processing_job_is_active(tmp_path):
    app = local_app(tmp_path)
    app._create_job(
        RecordingResult(
            wav_path=tmp_path / "active.wav",
            duration_seconds=1.0,
            average_volume=100.0,
            max_volume=500,
        )
    )

    try:
        app.new_session({"mode_id": app.service.settings.mode_id})
    except RuntimeError as exc:
        assert "仍在处理中" in str(exc)
    else:
        raise AssertionError("active processing must prevent session switching")


def test_recompile_overwrites_latest_turn_without_adding_memory(tmp_path):
    app = local_app(tmp_path)
    session = app.service.current_session
    original = session.add_turn(
        raw_transcript="old transcript",
        compiled_text="old compiled text",
        stt_provider="test-stt",
        llm_provider="test-llm",
    )

    app.update_latest_turn({"transcript": "edited transcript", "compiled": "edited compiled text"})
    payload = app.compile_text({"transcript": "edited transcript"})

    assert len(session.turns) == 1
    assert session.turns[0].id == original.id
    assert session.turns[0].raw_transcript == "edited transcript"
    assert session.turns[0].compiled_text == payload["compiled"]
    assert payload["state"]["current_session"]["turn_count"] == 1


def test_manual_compiled_edit_overwrites_history_memory(tmp_path):
    app = local_app(tmp_path)
    session = app.service.current_session
    original = session.add_turn(
        raw_transcript="original transcript",
        compiled_text="original compiled text",
        stt_provider="test-stt",
        llm_provider="test-llm",
    )
    app.service.history.save_session(session)

    payload = app.update_latest_turn(
        {"transcript": "original transcript", "compiled": "manually edited result"}
    )

    assert len(session.turns) == 1
    assert session.turns[0].id == original.id
    assert session.turns[0].compiled_text == "manually edited result"
    assert app.service.history.recent_sessions()[0]["last_compiled"] == "manually edited result"
    assert payload["state"]["current_session"]["turn_count"] == 1


def test_delete_history_removes_one_session_and_replaces_current(tmp_path):
    app = local_app(tmp_path)
    session = app.service.current_session
    session.add_turn(
        raw_transcript="session to delete",
        compiled_text="compiled",
        stt_provider="test-stt",
        llm_provider="test-llm",
    )
    app.service.history.save_session(session)
    deleted_session_id = session.id

    payload = app.delete_history({"session_id": deleted_session_id})

    assert payload["deleted"] is True
    assert payload["deleted_current"] is True
    assert payload["state"]["current_session"]["id"] != deleted_session_id
    assert payload["state"]["history"] == []


def test_sidecar_save_skills_updates_settings(tmp_path):
    app = local_app(tmp_path)

    payload = app.save_skills(
        {
            "skill_scan_dir": str(tmp_path / "skills"),
            "skills": [
                {
                    "id": "doc",
                    "name": "doc",
                    "description": "Edit docx documents",
                    "example": "Use when the user asks for a Word document.",
                    "category": "Document",
                    "enabled": True,
                    "source_path": "",
                }
            ],
        }
    )

    assert payload["state"]["skills"][0]["name"] == "doc"
    assert payload["state"]["skills"][0]["enabled"] is True
    assert app.service.settings.skill_scan_dir.endswith("skills")


def test_scanning_new_skill_directory_replaces_previous_scanned_results(tmp_path):
    app = local_app(tmp_path)
    app.save_skills(
        {
            "skill_scan_dir": "",
            "skills": [
                {
                    "id": "manual",
                    "name": "manual",
                    "description": "Manually maintained Skill",
                    "category": "Custom",
                    "enabled": True,
                    "source_path": "",
                }
            ],
        }
    )
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    empty_dir = tmp_path / "empty"
    (first_dir / "one").mkdir(parents=True)
    (second_dir / "two").mkdir(parents=True)
    empty_dir.mkdir()
    (first_dir / "one" / "SKILL.md").write_text(
        "# First Skill\nDescription: Imported from the first directory.",
        encoding="utf-8",
    )
    (second_dir / "two" / "SKILL.md").write_text(
        "# Second Skill\nDescription: Imported from the second directory.",
        encoding="utf-8",
    )

    first = app.scan_skills({"directory": str(first_dir)})
    second = app.scan_skills({"directory": str(second_dir)})
    empty = app.scan_skills({"directory": str(empty_dir)})

    assert {skill["name"] for skill in first["state"]["skills"]} == {"manual", "First Skill"}
    assert {skill["name"] for skill in second["state"]["skills"]} == {"manual", "Second Skill"}
    assert {skill["name"] for skill in empty["state"]["skills"]} == {"manual"}
    assert empty["state"]["settings"]["skill_scan_dir"] == str(empty_dir)


def test_sidecar_saves_keyless_custom_llm_configuration(tmp_path):
    app = local_app(tmp_path)

    payload = app.save_llm_settings(
        {
            "llm_provider": "openai_compatible",
            "llm_base_url": "http://127.0.0.1:11434/v1",
            "llm_model": "llama3.3",
            "custom_api_key": "",
            "llm_temperature": 0.2,
            "llm_timeout_seconds": 60,
        }
    )

    assert payload["state"]["settings"]["llm_provider"] == "openai_compatible"
    assert payload["state"]["settings"]["custom_api_key"] == ""
    assert isinstance(app.service.compiler.llm, OpenAICompatibleClient)
    assert app.service.compiler.llm.is_configured is True


def test_sidecar_normalizes_legacy_deepseek_endpoint_and_keeps_pro_model(tmp_path):
    app = local_app(tmp_path)

    payload = app.save_llm_settings(
        {
            "llm_provider": "openai_compatible",
            "llm_base_url": "https://api.deepseek.com/v1/",
            "llm_model": "deepseek-v4-pro",
            "deepseek_api_key": "secret",
            "llm_thinking_enabled": False,
        }
    )
    settings = payload["state"]["settings"]

    assert settings["llm_provider"] == "deepseek"
    assert settings["llm_base_url"] == "https://api.deepseek.com"
    assert settings["llm_model"] == "deepseek-v4-pro"
    assert settings["llm_thinking_enabled"] is False


def test_state_masks_configured_api_keys():
    from aura.models import Settings

    payload = settings_payload(
        Settings(deepseek_api_key="deepseek-secret", custom_api_key="custom-secret"),
    )

    assert payload["deepseek_api_key"] == API_KEY_MASK
    assert payload["custom_api_key"] == API_KEY_MASK
    assert payload["deepseek_api_key_source"] == "config"


def test_saving_llm_settings_keeps_masked_config_key(tmp_path):
    app = local_app(tmp_path)
    app.service.settings.deepseek_api_key = "existing-secret"
    app.settings_store.save(app.service.settings)

    payload = app.save_llm_settings(
        {
            "llm_provider": "deepseek",
            "llm_base_url": "https://api.deepseek.com",
            "llm_model": "deepseek-v4-pro",
            "deepseek_api_key": API_KEY_MASK,
            "llm_thinking_enabled": False,
        }
    )

    assert app.service.settings.deepseek_api_key == "existing-secret"
    saved = json.loads(app.settings_store.path.read_text(encoding="utf-8"))
    assert saved["deepseek_api_key"] == "existing-secret"
    assert payload["state"]["settings"]["deepseek_api_key"] == API_KEY_MASK


def test_saving_llm_settings_persists_to_local_config(tmp_path):
    app = local_app(tmp_path)

    payload = app.save_llm_settings(
        {
            "llm_provider": "deepseek",
            "llm_base_url": "https://api.deepseek.com",
            "llm_model": "deepseek-v4-flash",
            "deepseek_api_key": "new-secret",
        }
    )

    saved = json.loads(app.settings_store.path.read_text(encoding="utf-8"))
    assert saved["deepseek_api_key"] == "new-secret"
    assert saved["custom_api_key"] == ""
    assert payload["state"]["settings"]["deepseek_api_key_source"] == "config"


def test_environment_variable_does_not_override_saved_config(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_DEEPSEEK_API_KEY", "environment-secret")
    app = local_app(tmp_path)

    payload = app.save_llm_settings(
        {
            "llm_provider": "deepseek",
            "llm_base_url": "https://api.deepseek.com",
            "llm_model": "deepseek-v4-flash",
            "deepseek_api_key": "attempted-replacement",
        }
    )

    assert app.service.settings.deepseek_api_key == "attempted-replacement"
    saved = json.loads(app.settings_store.path.read_text(encoding="utf-8"))
    assert saved["deepseek_api_key"] == "attempted-replacement"
    assert payload["state"]["settings"]["deepseek_api_key_source"] == "config"


def test_sidecar_switches_to_whisper_large_v3(tmp_path, monkeypatch):
    app = local_app(tmp_path)
    monkeypatch.setattr(app.service, "warm_up_transcriber_background", lambda on_status=None, on_fallback=None: None)

    payload = app.save_speech_settings({"stt_provider": "whisper-large-v3"})

    assert app.service.transcriber.name == "whisper-large-v3"
    assert payload["state"]["settings"]["stt_provider"] == "whisper-large-v3"


def test_switching_stt_while_previous_model_loads_starts_new_warmup(tmp_path, monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    new_started = threading.Event()

    class FakeTranscriber:
        def __init__(self, name, started=None):
            self.name = name
            self.is_ready = False
            self.status = "not_loaded"
            self.progress = 0
            self.last_error = ""
            self._started = started

        def load_model(self, status_callback=None):
            if self._started:
                self._started.set()
            if self.name == "old":
                release.wait(timeout=2)
            self.is_ready = True

    app = local_app(tmp_path)
    old = FakeTranscriber("old", entered)
    new = FakeTranscriber("new", new_started)
    app.service.transcriber = old
    app.service.warm_up_transcriber_background()
    assert entered.wait(timeout=2)

    monkeypatch.setattr(app.service, "_build_transcriber", lambda: new)
    app.save_speech_settings({"stt_provider": "whisper-large-v3"})

    assert new_started.wait(timeout=2)
    release.set()


def test_general_theme_and_language_settings_are_saved(tmp_path):
    app = local_app(tmp_path)

    payload = app.save_general_settings({"ui_theme": "night", "ui_language": "ja"})

    assert payload["state"]["settings"]["ui_theme"] == "night"
    assert payload["state"]["settings"]["ui_language"] == "ja"
