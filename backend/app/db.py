from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DB_ENV_VAR = "PM_DB_PATH"
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "pm.db"

DEFAULT_BOARD: dict[str, Any] = {
    "columns": [
        {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-1", "card-2"]},
        {"id": "col-discovery", "title": "Discovery", "cardIds": ["card-3"]},
        {
            "id": "col-progress",
            "title": "In Progress",
            "cardIds": ["card-4", "card-5"],
        },
        {"id": "col-review", "title": "Review", "cardIds": ["card-6"]},
        {"id": "col-done", "title": "Done", "cardIds": ["card-7", "card-8"]},
    ],
    "cards": {
        "card-1": {
            "id": "card-1",
            "title": "Align roadmap themes",
            "details": "Draft quarterly themes with impact statements and metrics.",
        },
        "card-2": {
            "id": "card-2",
            "title": "Gather customer signals",
            "details": "Review support tags, sales notes, and churn feedback.",
        },
        "card-3": {
            "id": "card-3",
            "title": "Prototype analytics view",
            "details": "Sketch initial dashboard layout and key drill-downs.",
        },
        "card-4": {
            "id": "card-4",
            "title": "Refine status language",
            "details": "Standardize column labels and tone across the board.",
        },
        "card-5": {
            "id": "card-5",
            "title": "Design card layout",
            "details": "Add hierarchy and spacing for scanning dense lists.",
        },
        "card-6": {
            "id": "card-6",
            "title": "QA micro-interactions",
            "details": "Verify hover, focus, and loading states.",
        },
        "card-7": {
            "id": "card-7",
            "title": "Ship marketing page",
            "details": "Final copy approved and asset pack delivered.",
        },
        "card-8": {
            "id": "card-8",
            "title": "Close onboarding sprint",
            "details": "Document release notes and share internally.",
        },
    },
}


def get_db_path() -> Path:
    raw = os.getenv(DB_ENV_VAR)
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_DB_PATH


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Path | None = None) -> Path:
    path = db_path or get_db_path()
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS boards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                board_key TEXT NOT NULL DEFAULT 'default',
                title TEXT NOT NULL DEFAULT 'My Project',
                board_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, board_key),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_boards_user_id ON boards(user_id);
            """
        )
        conn.commit()
    return path


def _get_or_create_user(conn: sqlite3.Connection, username: str) -> int:
    row = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row:
        return int(row[0])

    cursor = conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, ""),
    )
    return int(cursor.lastrowid)


def _get_or_create_default_board(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT board_json FROM boards WHERE user_id = ? AND board_key = 'default'",
        (user_id,),
    ).fetchone()
    if row:
        return json.loads(row[0])

    payload = json.dumps(DEFAULT_BOARD)
    conn.execute(
        """
        INSERT INTO boards (user_id, board_key, title, board_json)
        VALUES (?, 'default', 'My Project', ?)
        """,
        (user_id, payload),
    )
    return DEFAULT_BOARD


def get_board_for_user(username: str) -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        user_id = _get_or_create_user(conn, username)
        board = _get_or_create_default_board(conn, user_id)
        conn.commit()
        return board


def update_board_for_user(username: str, board: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        user_id = _get_or_create_user(conn, username)
        _get_or_create_default_board(conn, user_id)

        conn.execute(
            """
            UPDATE boards
            SET board_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND board_key = 'default'
            """,
            (json.dumps(board), user_id),
        )
        conn.commit()
        return board


def delete_board_for_user(username: str) -> bool:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not row:
            return False

        user_id = int(row[0])
        cursor = conn.execute(
            "DELETE FROM boards WHERE user_id = ? AND board_key = 'default'",
            (user_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
