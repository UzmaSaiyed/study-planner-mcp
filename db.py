import os
import sqlite3
from contextlib import closing
from typing import Any


def db_path() -> str:
    return os.getenv("PLANNER_DB", "planner.db")


def init_db() -> None:
    with closing(sqlite3.connect(db_path())) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Todo',
                due_on TEXT,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.commit()


def run_query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with closing(sqlite3.connect(db_path())) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def run_write(sql: str, params: tuple = ()) -> int:
    with closing(sqlite3.connect(db_path())) as conn:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid