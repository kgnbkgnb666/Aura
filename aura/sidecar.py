from __future__ import annotations

import argparse
import json
import threading
import time
from dataclasses import asdict, is_dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .compiler import PromptCompiler
from .config import SettingsStore
from .models import DeviceInfo, Mode, RecordingResult, Session, Settings
from .recorder import AudioRecorder
from .runtime import ProcessingJobStore, RuntimeLog
from .service import AuraService


JsonDict = dict[str, Any]


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    return str(value)


def json_response(payload: Any, status: int = 200) -> bytes:
    body = json.dumps(payload, ensure_ascii=False, default=_json_default).encode("utf-8")
    return body


def settings_payload(settings: Settings) -> JsonDict:
    data = asdict(settings)
    if data.get("history_path"):
        data["history_path"] = str(data["history_path"])
    if data.get("model_cache_dir"):
        data["model_cache_dir"] = str(data["model_cache_dir"])
    return data


def mode_payload(mode: Mode) -> JsonDict:
    return asdict(mode)


def session_payload(session: Session) -> JsonDict:
    return {
        "id": session.id,
        "mode_id": session.mode_id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "turn_count": len(session.turns),
    }


def session_detail_payload(session: Session) -> JsonDict:
    latest_turn = session.turns[-1] if session.turns else None
    return {
        "session": session_payload(session),
        "transcript": latest_turn.raw_transcript if latest_turn else "",
        "compiled": latest_turn.compiled_text if latest_turn else "",
    }


def device_payload(device: DeviceInfo) -> JsonDict:
    return asdict(device)


def recording_payload(result: RecordingResult) -> JsonDict:
    return {
        "wav_path": str(result.wav_path),
        "duration_seconds": result.duration_seconds,
        "average_volume": result.average_volume,
        "max_volume": result.max_volume,
    }


class AuraSidecar:
    def __init__(self, preload_stt: bool = False) -> None:
        self.settings_store = SettingsStore()
        self.service = AuraService(settings=self.settings_store.load())
        self.logs = RuntimeLog()
        self.jobs = ProcessingJobStore()
        self.recorder: AudioRecorder | None = None
        self.last_test_wav: Path | None = None
        self.latest_status = "准备就绪"
        self.latest_volume = 0.0
        self._lock = threading.RLock()
        self.logs.info("sidecar", "Aura sidecar started")
        if preload_stt:
            self.warm_up_stt()

    def state(self) -> JsonDict:
        with self._lock:
            return {
                "settings": settings_payload(self.service.settings),
                "modes": [mode_payload(mode) for mode in self.service.modes.all()],
                "current_mode": mode_payload(self.service.current_mode),
                "current_session": session_payload(self.service.current_session),
                "history": self.service.history.recent_sessions(),
                "service": {
                    "stt_provider": self.service.settings.stt_provider,
                    "llm_provider": self.service.compiler.llm.name,
                    "transcriber": self.service.transcriber.name,
                    "transcriber_ready": self.service.transcriber.is_ready,
                },
                "runtime": {
                    "status": self.latest_status,
                    "volume": self.latest_volume,
                    "recording": self.recorder is not None,
                    "latest_job_id": self.jobs.latest_job_id,
                    "log_count": len(self.logs.recent()),
                },
            }

    def set_status(self, message: str, level: str = "info", source: str = "runtime") -> None:
        with self._lock:
            self.latest_status = message
        self.logs.add(level, source, message)

    def set_volume(self, volume: float) -> None:
        with self._lock:
            self.latest_volume = volume
            self.latest_status = f"录音中 {volume:.0f}"

    def list_devices(self) -> JsonDict:
        devices = [device_payload(device) for device in AudioRecorder.list_input_devices()]
        self.logs.info("audio", f"Loaded {len(devices)} input devices")
        return {"devices": devices}

    def new_session(self, payload: JsonDict) -> JsonDict:
        with self._lock:
            session = self.service.new_session(payload.get("mode_id") or self.service.settings.mode_id)
            self.latest_status = "新会话"
            self.logs.info("session", f"New session: {session.id}")
            return {"session": session_payload(session), "state": self.state()}

    def load_session(self, payload: JsonDict) -> JsonDict:
        session_id = str(payload.get("session_id") or "")
        if not session_id:
            raise ValueError("session_id is required")
        with self._lock:
            session = self.service.load_session(session_id)
            self.settings_store.save(self.service.settings)
            self.latest_status = f"已切换历史: {session.title}"
            self.logs.info("session", f"Loaded session: {session.id}")
            return {**session_detail_payload(session), "state": self.state()}

    def set_mode(self, payload: JsonDict) -> JsonDict:
        mode_id = str(payload.get("mode_id") or "")
        if not mode_id:
            raise ValueError("mode_id is required")
        with self._lock:
            self.service.set_mode(mode_id)
            self.settings_store.save(self.service.settings)
            self.latest_status = f"模式: {self.service.current_mode.name}"
            self.logs.info("settings", f"Mode changed: {mode_id}")
            return {"state": self.state()}

    def save_modes(self, payload: JsonDict) -> JsonDict:
        raw_modes = payload.get("modes") or []
        modes: list[Mode] = []
        for item in raw_modes:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            system_prompt = str(item.get("system_prompt") or "").strip()
            if not name or not system_prompt:
                raise ValueError("Mode name and system prompt are required.")
            modes.append(
                Mode(
                    id=name,
                    name=name,
                    target=name,
                    description=str(item.get("description") or "").strip(),
                    system_prompt=system_prompt,
                    output_hint=name,
                )
            )
        with self._lock:
            self.service.modes.save_all(modes)
            default_mode = modes[0]
            self.service.settings.mode_id = default_mode.id
            self.service.sessions.set_mode(default_mode.id)
            self.settings_store.save(self.service.settings)
            self.latest_status = f"默认模式: {default_mode.name}"
            self.logs.info("settings", "Modes saved")
            return {"state": self.state()}

    def save_general_settings(self, payload: JsonDict) -> JsonDict:
        with self._lock:
            settings = self.service.settings
            settings.hotkey = str(payload.get("hotkey") or settings.hotkey)
            settings.push_to_talk_key = str(payload.get("push_to_talk_key") or settings.push_to_talk_key)
            settings.auto_copy = bool(payload.get("auto_copy", settings.auto_copy))
            settings.save_history = bool(payload.get("save_history", settings.save_history))
            self.settings_store.save(settings)
            self.latest_status = "设置已保存"
            self.logs.info("settings", "General settings saved")
            return {"state": self.state()}

    def save_speech_settings(self, payload: JsonDict) -> JsonDict:
        with self._lock:
            settings = self.service.settings
            previous_cache_dir = settings.model_cache_dir
            settings.input_device_index = payload.get("input_device_index")
            cache_dir = str(payload.get("model_cache_dir") or "").strip()
            if cache_dir:
                settings.model_cache_dir = Path(cache_dir)
            settings.stt_provider = "sensevoice-small"
            if settings.model_cache_dir != previous_cache_dir:
                self.service.transcriber = self.service._build_transcriber()
                self.service.warm_up_transcriber_background(on_status=self.set_status)
            self.settings_store.save(settings)
            self.latest_status = "语音设置已保存"
            self.logs.info("settings", "Speech settings saved")
            return {"state": self.state()}

    def save_llm_settings(self, payload: JsonDict) -> JsonDict:
        with self._lock:
            settings = self.service.settings
            settings.llm_provider = str(payload.get("llm_provider") or settings.llm_provider)
            settings.llm_base_url = str(payload.get("llm_base_url") or "").strip()
            settings.llm_model = str(payload.get("llm_model") or "").strip()
            settings.llm_api_key = str(payload.get("llm_api_key") or "")
            settings.llm_temperature = float(payload.get("llm_temperature", settings.llm_temperature))
            settings.llm_timeout_seconds = int(payload.get("llm_timeout_seconds", settings.llm_timeout_seconds))
            self.service.compiler = PromptCompiler(self.service._build_llm())
            self.settings_store.save(settings)
            self.latest_status = "LLM 设置已保存"
            self.logs.info("settings", "LLM settings saved")
            return {"state": self.state()}

    def warm_up_stt(self) -> JsonDict:
        self.set_status("正在预加载转录模型")
        self.logs.info("stt", "STT preload requested")
        self.service.warm_up_transcriber_background(on_status=self.set_status)
        return {"state": self.state()}

    def start_recording(self) -> JsonDict:
        with self._lock:
            if self.recorder is not None:
                return {"state": self.state()}
            self.latest_volume = 0.0
            self.latest_status = "正在录音"
            self.logs.info("audio", "Recording started")
            self.recorder = AudioRecorder(
                input_device_index=self.service.settings.input_device_index,
                volume_callback=self.set_volume,
            )
            self.recorder.start()
            return {"state": self.state()}

    def stop_recording(self) -> JsonDict:
        with self._lock:
            if self.recorder is None:
                raise RuntimeError("Recorder is not recording.")
            recorder = self.recorder
            self.recorder = None
            self.latest_status = "正在转录"
            self.logs.info("audio", "Recording stopped")

        result = recorder.stop()
        job = self._create_job(result)
        thread = threading.Thread(
            target=self._process_recording_job,
            args=(job["id"], result.wav_path),
            daemon=True,
        )
        thread.start()
        return {"job": job, "state": self.state()}

    def _create_job(self, result: RecordingResult) -> JsonDict:
        job = self.jobs.create(recording_payload(result))
        with self._lock:
            self.latest_status = "正在转录"
        self.logs.info("job", f"Job created: {job['id']}")
        return dict(job)

    def _update_job(self, job_id: str, **updates: Any) -> None:
        self.jobs.update(job_id, **updates)

    def _append_job_chunk(self, job_id: str, chunk: str) -> None:
        self.jobs.append_chunk(job_id, chunk)

    def job_status(self, job_id: str) -> JsonDict:
        return {"job": self.jobs.get(job_id), "state": self.state()}

    def _process_recording_job(self, job_id: str, wav_path: Path) -> None:
        try:
            transcript = self.service.transcribe(wav_path, on_status=self.set_status).strip()
            self._update_job(job_id, transcript=transcript, phase="compiling")
            self.logs.info("stt", "Transcript ready", transcript)
            self.set_status("正在整理")

            compiled = self.service.compile_transcript(
                transcript,
                on_chunk=lambda chunk: self._append_job_chunk(job_id, chunk),
            ).strip()
            self._update_job(job_id, compiled=compiled, phase="done", done=True)
            self.logs.info("llm", "Compile completed", compiled[:1200])
            with self._lock:
                self.latest_status = "已复制" if self.service.settings.auto_copy else "整理完成"
        except Exception as exc:
            message = str(exc)
            self._update_job(job_id, phase="error", done=True, error=message)
            self.logs.error("job", message)
            self.set_status(message)
        finally:
            if wav_path.exists():
                wav_path.unlink(missing_ok=True)

    def test_microphone(self, payload: JsonDict) -> JsonDict:
        duration = max(0.5, min(float(payload.get("duration_seconds", 3)), 10.0))
        recorder = AudioRecorder(
            input_device_index=self.service.settings.input_device_index,
            volume_callback=self.set_volume,
        )
        with self._lock:
            self.latest_volume = 0.0
        self.set_status("正在测试麦克风")
        self.logs.info("audio", "Microphone test started")
        wav_path: Path | None = None
        try:
            recorder.start()
            time.sleep(duration)
            result = recorder.stop(min_duration_seconds=0.1, min_average_volume=0)
            self.last_test_wav = result.wav_path
            wav_path = result.wav_path
            self.set_status("麦克风测试完成")
            self.logs.info("audio", "Microphone test completed", json.dumps(recording_payload(result), ensure_ascii=False))
            return {"recording": recording_payload(result), "state": self.state()}
        except Exception:
            self.logs.error("audio", "Microphone test failed")
            if wav_path and wav_path.exists():
                wav_path.unlink(missing_ok=True)
            raise

    def transcribe_test_audio(self) -> JsonDict:
        if not self.last_test_wav or not self.last_test_wav.exists():
            raise RuntimeError("请先完成一次麦克风测试。")
        self.set_status("正在转录测试音频")
        text = self.service.transcribe(self.last_test_wav, on_status=self.set_status).strip()
        self.set_status("测试转录完成")
        self.logs.info("stt", "Test transcription completed", text)
        return {"transcript": text, "state": self.state()}

    def clear_history(self) -> JsonDict:
        with self._lock:
            self.service.history.clear()
            self.latest_status = "历史已清空"
            self.logs.warning("history", "History cleared")
            return {"state": self.state()}

    def recent_logs(self) -> JsonDict:
        return {"logs": self.logs.recent(), "state": self.state()}

    def clear_logs(self) -> JsonDict:
        self.logs.clear()
        self.logs.info("logs", "Logs cleared")
        return {"logs": self.logs.recent(), "state": self.state()}


def build_handler(app: AuraSidecar) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "AuraSidecar/1.0"

        def _send(self, payload: Any, status: int = 200) -> None:
            body = json_response(payload, status=status)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def _payload(self) -> JsonDict:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length == 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw) if raw else {}

        def do_OPTIONS(self) -> None:
            self._send({})

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            try:
                if path == "/api/health":
                    self._send({"ok": True, "app": "Aura", "api_version": 2})
                elif path == "/api/state":
                    self._send(app.state())
                elif path == "/api/devices":
                    self._send(app.list_devices())
                elif path == "/api/status":
                    self._send(app.state()["runtime"])
                elif path == "/api/logs":
                    self._send(app.recent_logs())
                elif path.startswith("/api/jobs/"):
                    self._send(app.job_status(path.rsplit("/", 1)[-1]))
                else:
                    self._send({"error": f"Unknown endpoint: {path}"}, status=404)
            except Exception as exc:
                app.logs.error("http", str(exc), self.path)
                self._send({"error": str(exc)}, status=500)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                payload = self._payload()
                routes = {
                    "/api/session/new": app.new_session,
                    "/api/session/load": app.load_session,
                    "/api/mode": app.set_mode,
                    "/api/modes": app.save_modes,
                    "/api/settings/general": app.save_general_settings,
                    "/api/settings/speech": app.save_speech_settings,
                    "/api/settings/llm": app.save_llm_settings,
                    "/api/record/start": lambda _: app.start_recording(),
                    "/api/record/stop": lambda _: app.stop_recording(),
                    "/api/stt/warmup": lambda _: app.warm_up_stt(),
                    "/api/microphone/test": app.test_microphone,
                    "/api/transcribe/test": lambda _: app.transcribe_test_audio(),
                    "/api/history/clear": lambda _: app.clear_history(),
                    "/api/logs/clear": lambda _: app.clear_logs(),
                }
                handler = routes.get(path)
                if handler is None:
                    self._send({"error": f"Unknown endpoint: {path}"}, status=404)
                    return
                self._send(handler(payload))
            except Exception as exc:
                app.logs.error("http", str(exc), self.path)
                app.set_status(str(exc), level="error", source="http")
                self._send({"error": str(exc), "state": app.state()}, status=500)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    app = AuraSidecar()
    server = ThreadingHTTPServer((host, port), build_handler(app))
    print(
        json.dumps(
            {"status": "listening", "host": host, "port": server.server_port},
            ensure_ascii=False,
        ),
        flush=True,
    )
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description="Aura Python sidecar")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    serve(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
