"""SQLite schema and connection helpers."""
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
"""


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
