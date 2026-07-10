from aura.models import RecordingResult
from aura.sidecar import AuraSidecar, json_response


def test_json_response_serializes_paths_and_dataclasses(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = AuraSidecar(preload_stt=False)
    body = json_response(app.state()).decode("utf-8")
    assert '"settings"' in body
    assert '"modes"' in body
    assert '"current_session"' in body


def test_sidecar_state_has_frontend_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = AuraSidecar(preload_stt=False)
    state = app.state()
    assert state["settings"]["app_name"] == "Aura"
    assert isinstance(state["modes"], list)
    assert state["runtime"]["recording"] is False
    assert state["runtime"]["latest_job_id"] == ""
    assert state["runtime"]["log_count"] >= 1
    assert "llm_provider" in state["service"]


def test_sidecar_job_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = AuraSidecar(preload_stt=False)
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


def test_sidecar_logs_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = AuraSidecar(preload_stt=False)
    app.logs.warning("test", "careful", "details")
    payload = app.recent_logs()
    assert payload["logs"][0]["level"] == "warning"
    assert payload["logs"][0]["source"] == "test"
    assert payload["logs"][0]["details"] == "details"
    cleared = app.clear_logs()
    assert len(cleared["logs"]) == 1
    assert cleared["logs"][0]["message"] == "Logs cleared"


def test_sidecar_save_modes_sets_first_mode_as_default(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = AuraSidecar(preload_stt=False)
    app.service.modes.modes_dir = tmp_path / "modes"
    payload = app.save_modes(
        {
            "modes": [
                {
                    "id": "reviewer",
                    "name": "Reviewer",
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


def test_sidecar_load_session_restores_turn_context(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = AuraSidecar(preload_stt=False)
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
