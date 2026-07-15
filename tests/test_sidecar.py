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
    assert state["service"]["transcriber_status"] == "not_loaded"
    assert state["service"]["transcriber_progress"] == 0


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


def test_recompile_overwrites_latest_turn_without_adding_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = AuraSidecar(preload_stt=False)
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


def test_manual_compiled_edit_overwrites_history_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = AuraSidecar(preload_stt=False)
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


def test_delete_history_removes_one_session_and_replaces_current(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = AuraSidecar(preload_stt=False)
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


def test_sidecar_save_skills_updates_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = AuraSidecar(preload_stt=False)

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
