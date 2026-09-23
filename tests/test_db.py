import sqlite3
import time

import pytest

from chess_analyzer.db import (
    finish_analysis_status,
    get_analysis_status,
    init_db,
    is_cancel_requested,
    request_cancel,
    start_analysis_status,
    update_analysis_progress,
)


def test_init_db_creates_singleton_analysis_status_row(conn):
    row = get_analysis_status(conn)
    assert row["running"] == 0
    assert row["done"] == 0
    assert row["total"] == 0
    assert row["error"] is None


def test_analysis_status_lifecycle(conn):
    start_analysis_status(conn, total=10)
    row = get_analysis_status(conn)
    assert row["running"] == 1
    assert row["total"] == 10
    assert row["done"] == 0
    assert row["cancel_requested"] == 0
    assert row["started_at"] is not None

    update_analysis_progress(conn, 4)
    assert get_analysis_status(conn)["done"] == 4

    finish_analysis_status(conn, error=None)
    row = get_analysis_status(conn)
    assert row["running"] == 0
    assert row["error"] is None


def test_finish_analysis_status_records_error(conn):
    start_analysis_status(conn, total=5)
    finish_analysis_status(conn, error="boom")
    row = get_analysis_status(conn)
    assert row["running"] == 0
    assert row["error"] == "boom"


def test_cancel_request_roundtrip(conn):
    start_analysis_status(conn, total=5)
    assert is_cancel_requested(conn) is False
    request_cancel(conn)
    assert is_cancel_requested(conn) is True
    # starting a fresh run clears any leftover cancel flag
    start_analysis_status(conn, total=3)
    assert is_cancel_requested(conn) is False


def test_start_analysis_status_resets_ema(conn):
    start_analysis_status(conn, total=5)
    update_analysis_progress(conn, 1)
    assert get_analysis_status(conn)["ema_seconds"] is not None

    start_analysis_status(conn, total=3)  # a fresh run must not carry over the old rate
    assert get_analysis_status(conn)["ema_seconds"] is None


def test_ema_converges_toward_recent_rate_not_stuck_on_early_average(conn):
    """Regression: the old since-the-start-average ETA kept climbing forever
    once a run slowed down partway through, because a fast early patch never
    washed out of a cumulative average. The EMA should instead track
    whatever the *last few* games actually took.
    """
    start_analysis_status(conn, total=10)

    time.sleep(0.3)
    update_analysis_progress(conn, 1)  # fast game: ~0.3s
    time.sleep(0.3)
    update_analysis_progress(conn, 2)  # fast game: ~0.3s
    fast_ema = get_analysis_status(conn)["ema_seconds"]
    assert fast_ema == pytest.approx(0.3, abs=0.15)

    for done in (3, 4, 5, 6):
        time.sleep(1.0)
        update_analysis_progress(conn, done)  # now much slower: ~1.0s each

    slow_ema = get_analysis_status(conn)["ema_seconds"]
    assert slow_ema > fast_ema
    assert slow_ema == pytest.approx(1.0, abs=0.3)


def test_migration_adds_columns_to_pre_existing_db_without_losing_data(tmp_path):
    """The analysis_status table shipped before last_progress_at/ema_seconds
    existed. init_db() must migrate an already-deployed DB in place rather
    than assuming CREATE TABLE IF NOT EXISTS is enough (it isn't — that
    statement is a no-op once the table already exists).
    """
    db_path = str(tmp_path / "old.db")
    raw = sqlite3.connect(db_path)
    raw.execute("""
        CREATE TABLE analysis_status (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            running INTEGER NOT NULL DEFAULT 0,
            done INTEGER NOT NULL DEFAULT 0,
            total INTEGER NOT NULL DEFAULT 0,
            started_at TEXT,
            cancel_requested INTEGER NOT NULL DEFAULT 0,
            error TEXT
        )
    """)
    raw.execute("INSERT INTO analysis_status (id, running, done, total) VALUES (1, 1, 3, 10)")
    raw.commit()
    raw.close()

    migrated = init_db(db_path)
    row = get_analysis_status(migrated)
    assert row["done"] == 3  # pre-existing data preserved
    assert row["running"] == 1
    assert row["ema_seconds"] is None  # new column present, defaulted
    migrated.close()


def test_migration_adds_best_move_uci_to_pre_existing_moves_table(tmp_path):
    """moves shipped before best_move_uci existed (added for the board
    view's "what should I have played" arrow). Same in-place migration
    requirement as analysis_status above.
    """
    db_path = str(tmp_path / "old_moves.db")
    raw = sqlite3.connect(db_path)
    raw.execute("""
        CREATE TABLE moves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
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
        )
    """)
    raw.execute("""
        INSERT INTO moves (game_id, ply, move_number, color, san, uci, phase)
        VALUES (1, 1, 1, 'white', 'e4', 'e2e4', 'opening')
    """)
    raw.commit()
    raw.close()

    migrated = init_db(db_path)
    row = migrated.execute("SELECT san, best_move_uci FROM moves WHERE id = 1").fetchone()
    assert row["san"] == "e4"  # pre-existing data preserved
    assert row["best_move_uci"] is None  # new column present, defaulted
    migrated.close()
