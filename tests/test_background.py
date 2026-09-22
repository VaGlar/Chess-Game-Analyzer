"""Regression tests for the stuck-analysis-flag bug: a process crash used to
leave analysis_status.running=1 forever, permanently blocking both the
"Stop" button and any new "Analyze pending games" click.
"""
import chess_analyzer.background as background
from chess_analyzer.db import get_analysis_status, start_analysis_status


def test_is_running_here_false_with_no_thread():
    background._current_thread = None
    assert background.is_running_here() is False


def test_reconcile_clears_stale_running_flag(conn):
    start_analysis_status(conn, total=10)
    background._current_thread = None  # simulate a fresh process, no live thread

    cleared = background.reconcile_stale_status(conn)

    assert cleared is True
    row = get_analysis_status(conn)
    assert row["running"] == 0
    assert "restarted" in row["error"]


def test_reconcile_leaves_genuinely_running_status_alone(conn):
    start_analysis_status(conn, total=10)

    class _FakeAliveThread:
        def is_alive(self):
            return True

    background._current_thread = _FakeAliveThread()
    try:
        cleared = background.reconcile_stale_status(conn)
        assert cleared is False
        assert get_analysis_status(conn)["running"] == 1
    finally:
        background._current_thread = None


def test_start_background_analysis_returns_false_when_nothing_pending(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(background, "DB_PATH", db_path)
    from chess_analyzer.db import init_db as real_init_db
    real_init_db(db_path).close()  # just create the schema, no pending games

    started = background.start_background_analysis(stockfish_path="/usr/games/stockfish")
    assert started is False


def test_start_background_analysis_self_heals_stale_flag_then_starts(tmp_path, monkeypatch):
    # A real file-backed DB (not :memory:) so start_background_analysis's own
    # short-lived connection and the background thread's separate connection
    # both see the same data, exactly like in production — using a single
    # shared in-memory connection for both would make the first one's
    # conn.close() break the second (that's what a `:memory:` monkeypatch
    # here used to do).
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(background, "DB_PATH", db_path)

    from chess_analyzer.db import init_db as real_init_db, start_analysis_status as real_start
    from chess_analyzer.fetch import inserted_row

    setup_conn = real_init_db(db_path)
    inserted_row(setup_conn, "tester", {
        "uuid": "bg1", "pgn": "[Event \"Test\"]\n\n1. e4 e5 *",
        "white": {"username": "tester", "rating": 1200, "result": "win"},
        "black": {"username": "opp", "rating": 1200, "result": "checkmated"},
        "time_control": "180", "time_class": "blitz", "url": "https://chess.com/game/1",
    })
    setup_conn.commit()
    real_start(setup_conn, total=1)  # simulate a stuck flag left by a dead process
    setup_conn.close()

    background._current_thread = None
    started = background.start_background_analysis(stockfish_path="/usr/games/stockfish", depth=4)
    assert started is True
    background._current_thread.join(timeout=30)

    final_conn = real_init_db(db_path)
    assert get_analysis_status(final_conn)["running"] == 0
    assert final_conn.execute("SELECT analyzed FROM games WHERE uuid='bg1'").fetchone()[0] == 1
    final_conn.close()
