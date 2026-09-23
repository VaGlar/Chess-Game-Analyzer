"""Shared pytest fixtures: an in-memory DB plus helpers to seed games/moves
directly (bypassing Stockfish) so most tests run fast and deterministically.
"""
import pytest

from chess_analyzer.db import init_db

_GAME_DEFAULTS = {
    "uuid": None,  # set per-call if not given
    "username": "tester",
    "played_at": "2024.01.15",
    "time_control": "180",
    "time_class": "blitz",
    "color": "white",
    "result": "win",
    "result_reason": "win",
    "my_rating": 1200,
    "opponent_rating": 1200,
    "opponent_username": "opp",
    "opening_eco": "C50",
    "opening_name": "Italian Game",
    "pgn": "[Event \"Test\"]\n\n1. e4 e5 *",
    "url": "https://chess.com/game/x",
    "analyzed": 1,
}

_MOVE_DEFAULTS = {
    "ply": 1,
    "move_number": 1,
    "color": "white",
    "san": "e4",
    "uci": "e2e4",
    "eval_cp_before": 0,
    "eval_cp_after": 0,
    "cp_loss": 0,
    "is_best": 1,
    "classification": "ok",
    "phase": "opening",
    "clock_seconds": None,
    "time_pressure": 0,
}


@pytest.fixture
def conn():
    connection = init_db(":memory:")
    yield connection
    connection.close()


@pytest.fixture
def make_game(conn):
    counter = {"n": 0}

    def _make(**overrides):
        counter["n"] += 1
        row = dict(_GAME_DEFAULTS)
        row["uuid"] = f"game-{counter['n']}"
        row.update(overrides)
        cur = conn.execute(
            """
            INSERT INTO games (
                uuid, username, played_at, time_control, time_class, color,
                result, result_reason, my_rating, opponent_rating, opponent_username,
                opening_eco, opening_name, pgn, url, analyzed
            ) VALUES (:uuid, :username, :played_at, :time_control, :time_class,
                      :color, :result, :result_reason, :my_rating, :opponent_rating,
                      :opponent_username, :opening_eco, :opening_name, :pgn,
                      :url, :analyzed)
            """,
            row,
        )
        conn.commit()
        return cur.lastrowid

    return _make


@pytest.fixture
def make_move(conn):
    def _make(game_id, **overrides):
        row = dict(_MOVE_DEFAULTS)
        row["game_id"] = game_id
        row.update(overrides)
        conn.execute(
            """
            INSERT INTO moves (
                game_id, ply, move_number, color, san, uci, eval_cp_before,
                eval_cp_after, cp_loss, is_best, classification, phase,
                clock_seconds, time_pressure
            ) VALUES (:game_id, :ply, :move_number, :color, :san, :uci,
                      :eval_cp_before, :eval_cp_after, :cp_loss, :is_best,
                      :classification, :phase, :clock_seconds, :time_pressure)
            """,
            row,
        )
        conn.commit()

    return _make
