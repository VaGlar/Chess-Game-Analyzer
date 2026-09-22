"""SQLite schema and connection helpers."""
import datetime
import os
import sqlite3

from chess_analyzer.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    username TEXT NOT NULL,
    played_at TEXT,
    time_control TEXT,
    time_class TEXT,
    color TEXT,
    result TEXT,
    my_rating INTEGER,
    opponent_rating INTEGER,
    opponent_username TEXT,
    opening_eco TEXT,
    opening_name TEXT,
    pgn TEXT NOT NULL,
    url TEXT,
    analyzed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    ply INTEGER NOT NULL,
    move_number INTEGER NOT NULL,
    color TEXT NOT NULL,
    san TEXT NOT NULL,
    uci TEXT NOT NULL,
    eval_cp_before INTEGER,
    eval_cp_after INTEGER,
    cp_loss INTEGER,
    is_best INTEGER NOT NULL DEFAULT 0,
    classification TEXT NOT NULL DEFAULT 'ok',
    phase TEXT NOT NULL,
    clock_seconds INTEGER,
    time_pressure INTEGER NOT NULL DEFAULT 0,
    UNIQUE(game_id, ply)
);

CREATE INDEX IF NOT EXISTS idx_games_username ON games(username);
CREATE INDEX IF NOT EXISTS idx_moves_game_id ON moves(game_id);

-- Single-row table tracking a (possibly background) analysis run, so
-- progress survives page refreshes and is visible from any session.
CREATE TABLE IF NOT EXISTS analysis_status (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    running INTEGER NOT NULL DEFAULT 0,
    done INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    started_at TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
"""


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO analysis_status (id, running, done, total) VALUES (1, 0, 0, 0)"
    )
    conn.commit()
    return conn


def get_analysis_status(conn: sqlite3.Connection) -> sqlite3.Row:
    return conn.execute("SELECT * FROM analysis_status WHERE id = 1").fetchone()


def start_analysis_status(conn: sqlite3.Connection, total: int) -> None:
    conn.execute(
        """
        UPDATE analysis_status
        SET running = 1, done = 0, total = ?, started_at = ?, cancel_requested = 0, error = NULL
        WHERE id = 1
        """,
        (total, datetime.datetime.utcnow().isoformat()),
    )
    conn.commit()


def update_analysis_progress(conn: sqlite3.Connection, done: int) -> None:
    conn.execute("UPDATE analysis_status SET done = ? WHERE id = 1", (done,))
    conn.commit()


def finish_analysis_status(conn: sqlite3.Connection, error: str = None) -> None:
    conn.execute(
        "UPDATE analysis_status SET running = 0, cancel_requested = 0, error = ? WHERE id = 1",
        (error,),
    )
    conn.commit()


def request_cancel(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE analysis_status SET cancel_requested = 1 WHERE id = 1")
    conn.commit()


def is_cancel_requested(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT cancel_requested FROM analysis_status WHERE id = 1").fetchone()
    return bool(row and row["cancel_requested"])
