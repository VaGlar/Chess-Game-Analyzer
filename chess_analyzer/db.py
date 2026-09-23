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
    best_move_uci TEXT,
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
    error TEXT,
    last_progress_at TEXT,
    ema_seconds REAL
);
"""

# CREATE TABLE IF NOT EXISTS won't add columns to an already-deployed DB, so
# columns added after the initial release are migrated in by hand here.
_COLUMN_MIGRATIONS = {
    "analysis_status": [
        ("last_progress_at", "TEXT"),
        ("ema_seconds", "REAL"),
    ],
    "moves": [
        ("best_move_uci", "TEXT"),
    ],
}


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
    for table, migrations in _COLUMN_MIGRATIONS.items():
        existing_columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column, sql_type in migrations:
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")
    conn.commit()
    return conn


def get_analysis_status(conn: sqlite3.Connection) -> sqlite3.Row:
    return conn.execute("SELECT * FROM analysis_status WHERE id = 1").fetchone()


_EMA_ALPHA = 0.3  # weight on the most recently finished game vs. history


def start_analysis_status(conn: sqlite3.Connection, total: int) -> None:
    now = datetime.datetime.utcnow().isoformat()
    conn.execute(
        """
        UPDATE analysis_status
        SET running = 1, done = 0, total = ?, started_at = ?, cancel_requested = 0,
            error = NULL, last_progress_at = ?, ema_seconds = NULL
        WHERE id = 1
        """,
        (total, now, now),
    )
    conn.commit()


def update_analysis_progress(conn: sqlite3.Connection, done: int) -> None:
    """Record progress and update a smoothed (EMA) seconds-per-game estimate
    from the time since the previous update — i.e. how long the game that
    just finished actually took — rather than a since-the-start average.
    A since-start average is dragged around by however the very first games
    happened to go and never really settles; the EMA tracks the recent,
    current rate instead, so it converges to steady state instead of
    climbing indefinitely while an early fast/slow patch washes out.
    """
    now = datetime.datetime.utcnow()
    row = conn.execute(
        "SELECT last_progress_at, ema_seconds FROM analysis_status WHERE id = 1"
    ).fetchone()
    ema = row["ema_seconds"]
    if row["last_progress_at"]:
        last_at = datetime.datetime.fromisoformat(row["last_progress_at"])
        latest_game_seconds = (now - last_at).total_seconds()
        ema = latest_game_seconds if ema is None else (
            _EMA_ALPHA * latest_game_seconds + (1 - _EMA_ALPHA) * ema
        )
    conn.execute(
        "UPDATE analysis_status SET done = ?, last_progress_at = ?, ema_seconds = ? WHERE id = 1",
        (done, now.isoformat(), ema),
    )
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
