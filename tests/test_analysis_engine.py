"""Tests that exercise the real Stockfish pipeline. Kept fast with tiny
games and a shallow depth; skipped automatically if Stockfish can't be
spawned (e.g. a machine with only the Python deps installed).
"""
import shutil

import chess.engine
import pytest

from chess_analyzer.analysis import analyze_game, analyze_pending_games
from chess_analyzer.db import init_db
from chess_analyzer.fetch import inserted_row

STOCKFISH_PATH = shutil.which("stockfish") or "/usr/games/stockfish"

# The classic Scholar's-mate-adjacent trap: White throws away the queen
# with Qxf6, a textbook blunder any search depth should catch.
_BLUNDER_PGN = """[Event "Test"]
[White "tester"]
[Black "opp"]
[Result "0-1"]

1. e4 {[%clk 0:03:00]} e5 {[%clk 0:03:00]} 2. Qh5 {[%clk 0:02:58]} Nc6 {[%clk 0:02:59]}
3. Bc4 {[%clk 0:02:55]} g6 {[%clk 0:02:58]} 4. Qf3 {[%clk 0:02:50]} Nf6 {[%clk 0:02:57]}
5. Qxf6 {[%clk 0:02:20]} Qxf6 {[%clk 0:00:20]} 0-1
"""


def _make_engine():
    try:
        return chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    except Exception:
        return None


@pytest.fixture(scope="module")
def engine():
    eng = _make_engine()
    if eng is None:
        pytest.skip("stockfish binary not available")
    yield eng
    eng.quit()


def _seed_blunder_game(conn, uuid="eng1"):
    game = {
        "uuid": uuid, "pgn": _BLUNDER_PGN,
        "white": {"username": "tester", "rating": 1200, "result": "resigned"},
        "black": {"username": "opp", "rating": 1250, "result": "win"},
        "time_control": "180", "time_class": "blitz", "url": "https://chess.com/game/1",
    }
    inserted_row(conn, "tester", game)


def test_analyze_game_flags_the_queen_blunder(engine):
    rows = analyze_game(engine, _BLUNDER_PGN, depth=8)
    assert len(rows) == 10  # 5 full moves = 10 plies

    qxf6 = next(r for r in rows if r["san"] == "Qxf6" and r["color"] == "white")
    assert qxf6["classification"] == "blunder"
    assert qxf6["cp_loss"] >= 300


def test_analyze_game_clock_and_phase_fields(engine):
    rows = analyze_game(engine, _BLUNDER_PGN, depth=8)
    first = rows[0]
    assert first["clock_seconds"] == 180
    assert first["phase"] == "opening"
    assert first["ply"] == 1
    assert first["move_number"] == 1


def test_analyze_game_empty_pgn_returns_no_rows(engine):
    assert analyze_game(engine, "", depth=6) == []


def test_analyze_pending_games_marks_analyzed_and_commits(engine):
    conn = init_db(":memory:")
    _seed_blunder_game(conn)
    conn.commit()

    n = analyze_pending_games(conn=conn, stockfish_path=STOCKFISH_PATH, depth=8)
    assert n == 1

    row = conn.execute("SELECT analyzed FROM games WHERE uuid = 'eng1'").fetchone()
    assert row["analyzed"] == 1
    move_count = conn.execute("SELECT COUNT(*) FROM moves").fetchone()[0]
    assert move_count == 10
    conn.close()


def test_analyze_pending_games_restarts_engine_without_losing_data(engine):
    """restart_every=1 forces a fresh Stockfish process before every single
    game (the extreme case) — results must come out identical to a normal
    run, since the swap is meant to be invisible to callers.
    """
    conn = init_db(":memory:")
    for i in range(3):
        _seed_blunder_game(conn, f"restart{i}")
    conn.commit()

    calls = []
    # threads=1 for deterministic search: multi-threaded Stockfish can give
    # slightly different evals run-to-run near a classification boundary
    # (this test hit exactly that in CI — a borderline move tipped into
    # "blunder" only under multi-threaded search), which isn't what this
    # test is meant to catch.
    n = analyze_pending_games(conn=conn, stockfish_path=STOCKFISH_PATH, depth=8, threads=1,
                               restart_every=1, progress_callback=lambda d, t: calls.append((d, t)))
    assert n == 3
    assert calls == [(1, 3), (2, 3), (3, 3)]
    assert conn.execute("SELECT COUNT(*) FROM moves").fetchone()[0] == 30
    for game_id in (1, 2, 3):
        blunders = conn.execute(
            "SELECT COUNT(*) FROM moves WHERE game_id = ? AND classification='blunder'", (game_id,)
        ).fetchone()[0]
        assert blunders >= 1  # each game's Qxf6 must still be caught
    conn.close()


def test_analyze_pending_games_progress_callback_fires_per_game(engine):
    conn = init_db(":memory:")
    _seed_blunder_game(conn, "prog0")
    _seed_blunder_game(conn, "prog1")
    conn.commit()

    calls = []
    analyze_pending_games(conn=conn, stockfish_path=STOCKFISH_PATH, depth=6,
                           progress_callback=lambda done, total: calls.append((done, total)))
    assert calls == [(1, 2), (2, 2)]
    conn.close()


def test_analyze_pending_games_should_cancel_stops_after_current_game(engine):
    conn = init_db(":memory:")
    for i in range(3):
        _seed_blunder_game(conn, f"cancel{i}")
    conn.commit()

    done_count = {"n": 0}

    def _progress(done, total):
        done_count["n"] = done

    def _cancel_after_one():
        return done_count["n"] >= 1

    n = analyze_pending_games(conn=conn, stockfish_path=STOCKFISH_PATH, depth=6,
                               progress_callback=_progress, should_cancel=_cancel_after_one)
    assert n == 1
    remaining_pending = conn.execute("SELECT COUNT(*) FROM games WHERE analyzed = 0").fetchone()[0]
    assert remaining_pending == 2
    conn.close()
