from __future__ import annotations

from .models import Session, new_id


class SessionManager:
    def __init__(self, default_mode_id: str) -> None:
        self.current = self.new_session(default_mode_id)

    def new_session(self, mode_id: str | None = None) -> Session:
        self.current = Session(id=new_id(), mode_id=mode_id or "professional")
        return self.current

    def set_mode(self, mode_id: str) -> None:
        self.current.mode_id = mode_id

    def previous_transcripts(self) -> list[str]:
        return [turn.raw_transcript for turn in self.current.turns]

    def previous_compiled_text(self) -> str:
        return self.current.latest_compiled_text
