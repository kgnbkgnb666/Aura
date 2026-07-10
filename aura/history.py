from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .models import Session, Turn


def _dt(value: datetime) -> str:
    return value.isoformat()


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


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
                select
                    sessions.id,
                    sessions.title,
                    sessions.mode_id,
                    sessions.created_at,
                    sessions.updated_at,
                    coalesce(latest.raw_transcript, ''),
                    coalesce(latest.compiled_text, ''),
                    coalesce(counts.turn_count, 0)
                from sessions
                left join turns latest on latest.id = (
                    select id
                    from turns
                    where session_id = sessions.id
                    order by turn_index desc
                    limit 1
                )
                left join (
                    select session_id, count(*) as turn_count
                    from turns
                    group by session_id
                ) counts on counts.session_id = sessions.id
                order by sessions.updated_at desc
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
                "last_transcript": row[5],
                "last_compiled": row[6],
                "turn_count": row[7],
            }
            for row in rows
        ]

    def load_session(self, session_id: str) -> Session:
        with self._connect() as conn:
            row = conn.execute(
                """
                select id, title, mode_id, created_at, updated_at
                from sessions
                where id = ?
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("Session not found.")
            turns = conn.execute(
                """
                select id, session_id, turn_index, raw_transcript, compiled_text,
                    mode_id, stt_provider, llm_provider, created_at
                from turns
                where session_id = ?
                order by turn_index asc
                """,
                (session_id,),
            ).fetchall()

        session = Session(
            id=row[0],
            title=row[1],
            mode_id=row[2],
            created_at=_parse_dt(row[3]),
            updated_at=_parse_dt(row[4]),
        )
        session.turns = [
            Turn(
                id=turn[0],
                session_id=turn[1],
                turn_index=turn[2],
                raw_transcript=turn[3],
                compiled_text=turn[4],
                mode_id=turn[5],
                stt_provider=turn[6],
                llm_provider=turn[7],
                created_at=_parse_dt(turn[8]),
            )
            for turn in turns
        ]
        return session

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("delete from turns")
            conn.execute("delete from sessions")
