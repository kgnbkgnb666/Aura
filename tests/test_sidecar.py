import json
import os
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from aura.config import SettingsStore
from aura.models import RecordingResult
from aura.providers.llm import OpenAICompatibleClient
from aura.sidecar import (
    API_KEY_MASK,
    MAX_REQUEST_BODY_BYTES,
    AuraSidecar,
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
    assert state["settings"]["mode_id"] == "professional"
    assert state["current_mode"]["id"] == "professional"
    assert state["current_session"]["mode_id"] == "professional"
    assert state["runtime"]["recording"] is False
    assert state["runtime"]["latest_job_id"] == ""
    assert state["runtime"]["log_count"] >= 1
    assert "llm_provider" in state["service"]
    assert state["service"]["transcriber_status"] == "not_loaded"
    assert state["service"]["transcriber_progress"] == 0


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
    payload = app.save_modes(
        {
            "modes": [
                {
                    "id": "reviewer",
                    "name": "审查模式",
                    "target": "code_review",
                    "description": "Review code",
                    "system_prompt": "Review the transcript as a code review request.",
                    "output_hint": "review",
                },
                {
                    "id": "coding_agent",
                    "name": "coding_agent",
                    "target": "coding_agent",
                    "description": "Write implementation prompts",
                    "system_prompt": "Compile the transcript into a coding agent prompt.",
                    "output_hint": "prompt",
                },
            ]
        }
    )
    state = payload["state"]
    assert [mode["id"] for mode in state["modes"]] == ["reviewer", "coding_agent"]
    assert state["settings"]["mode_id"] == "reviewer"
    assert state["current_session"]["mode_id"] == "reviewer"
    assert (tmp_path / "modes" / "001-reviewer.yaml").exists()


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
            assert json.load(response)["api_version"] == 4
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


def test_sidecar_saves_keyless_custom_llm_configuration(tmp_path):
    app = local_app(tmp_path)

    payload = app.save_llm_settings(
        {
            "llm_provider": "openai_compatible",
            "llm_base_url": "http://127.0.0.1:11434/v1",
            "llm_model": "llama3.3",
            "llm_api_key": "",
            "llm_temperature": 0.2,
            "llm_timeout_seconds": 60,
        }
    )

    assert payload["state"]["settings"]["llm_provider"] == "openai_compatible"
    assert payload["state"]["settings"]["llm_api_key"] == ""
    assert isinstance(app.service.compiler.llm, OpenAICompatibleClient)
    assert app.service.compiler.llm.is_configured is True


def test_sidecar_normalizes_legacy_deepseek_endpoint_and_keeps_pro_model(tmp_path):
    app = local_app(tmp_path)

    payload = app.save_llm_settings(
        {
            "llm_provider": "openai_compatible",
            "llm_base_url": "https://api.deepseek.com/v1/",
            "llm_model": "deepseek-v4-pro",
            "llm_api_key": "secret",
            "llm_thinking_enabled": False,
        }
    )
    settings = payload["state"]["settings"]

    assert settings["llm_provider"] == "deepseek"
    assert settings["llm_base_url"] == "https://api.deepseek.com"
    assert settings["llm_model"] == "deepseek-v4-pro"
    assert settings["llm_thinking_enabled"] is False


def test_state_masks_configured_api_key():
    from aura.models import Settings

    payload = settings_payload(Settings(llm_api_key="secret-value"))

    assert payload["llm_api_key"] == API_KEY_MASK


def test_saving_masked_api_key_preserves_existing_secret(tmp_path):
    app = local_app(tmp_path)
    app.service.settings.llm_api_key = "existing-secret"

    payload = app.save_llm_settings(
        {
            "llm_provider": "deepseek",
            "llm_base_url": "https://api.deepseek.com",
            "llm_model": "deepseek-v4-pro",
            "llm_api_key": API_KEY_MASK,
            "llm_thinking_enabled": False,
        }
    )

    assert app.service.settings.llm_api_key == "existing-secret"
    assert payload["state"]["settings"]["llm_api_key"] == API_KEY_MASK
