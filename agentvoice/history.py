from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .models import Session, Turn


def _dt(value: datetime) -> str:
    return value.isoformat()


class HistoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists sessions(
                    id text primary key,
                    title text,
                    mode_id text,
                    created_at text,
                    updated_at text
                )
                """
            )
            conn.execute(
                """
                create table if not exists turns(
                    id text primary key,
                    session_id text,
                    turn_index integer,
                    raw_transcript text,
                    compiled_text text,
                    mode_id text,
                    stt_provider text,
                    llm_provider text,
                    created_at text
                )
                """
            )

    def save_session(self, session: Session) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into sessions(id, title, mode_id, created_at, updated_at)
                values(?, ?, ?, ?, ?)
                on conflict(id) do update set
                    title=excluded.title,
                    mode_id=excluded.mode_id,
                    updated_at=excluded.updated_at
                """,
                (
                    session.id,
                    session.title,
                    session.mode_id,
                    _dt(session.created_at),
                    _dt(session.updated_at),
                ),
            )
            for turn in session.turns:
                self.save_turn(turn, conn)

    def save_turn(self, turn: Turn, conn: sqlite3.Connection | None = None) -> None:
        owns_connection = conn is None
        conn = conn or self._connect()
        try:
            conn.execute(
                """
                insert into turns(
                    id, session_id, turn_index, raw_transcript, compiled_text,
                    mode_id, stt_provider, llm_provider, created_at
                )
                values(?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do nothing
                """,
                (
                    turn.id,
                    turn.session_id,
                    turn.turn_index,
                    turn.raw_transcript,
                    turn.compiled_text,
                    turn.mode_id,
                    turn.stt_provider,
                    turn.llm_provider,
                    _dt(turn.created_at),
                ),
            )
            if owns_connection:
                conn.commit()
        finally:
            if owns_connection:
                conn.close()

    def recent_sessions(self, limit: int = 50) -> list[dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select id, title, mode_id, created_at, updated_at
                from sessions
                order by updated_at desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "title": row[1],
                "mode_id": row[2],
                "created_at": row[3],
                "updated_at": row[4],
            }
            for row in rows
        ]

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("delete from turns")
            conn.execute("delete from sessions")

