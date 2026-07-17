from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import threading
from typing import Any
from uuid import uuid4


JsonDict = dict[str, Any]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class LogEntry:
    id: str
    timestamp: str
    level: str
    source: str
    message: str
    details: str = ""

    def as_dict(self) -> JsonDict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "level": self.level,
            "source": self.source,
            "message": self.message,
            "details": self.details,
        }


class RuntimeLog:
    def __init__(self, limit: int = 300) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=limit)
        self._lock = threading.RLock()

    def add(self, level: str, source: str, message: str, details: str = "") -> LogEntry:
        entry = LogEntry(
            id=uuid4().hex,
            timestamp=utc_timestamp(),
            level=level,
            source=source,
            message=message,
            details=details,
        )
        with self._lock:
            self._entries.appendleft(entry)
        return entry

    def info(self, source: str, message: str, details: str = "") -> LogEntry:
        return self.add("info", source, message, details)

    def warning(self, source: str, message: str, details: str = "") -> LogEntry:
        return self.add("warning", source, message, details)

    def error(self, source: str, message: str, details: str = "") -> LogEntry:
        return self.add("error", source, message, details)

    def recent(self, limit: int = 120) -> list[JsonDict]:
        with self._lock:
            return [entry.as_dict() for entry in list(self._entries)[:limit]]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class ProcessingJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JsonDict] = {}
        self.latest_job_id = ""
        self._lock = threading.RLock()

    def create(self, recording: JsonDict) -> JsonDict:
        job = {
            "id": uuid4().hex,
            "phase": "transcribing",
            "done": False,
            "error": "",
            "transcript": "",
            "compiled": "",
            "recording": recording,
        }
        with self._lock:
            self._jobs[job["id"]] = job
            self.latest_job_id = job["id"]
        return dict(job)

    def update(self, job_id: str, **updates: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.update(updates)

    def append_chunk(self, job_id: str, chunk: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job["compiled"] = f"{job.get('compiled', '')}{chunk}"

    def get(self, job_id: str) -> JsonDict:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise RuntimeError("Job not found.")
            return dict(job)
