"""Run Stockfish analysis in a background thread.

Lets the dashboard kick off a long analysis run without blocking the
Streamlit script (and therefore the whole UI) for hours. Progress and
cancellation are coordinated through the analysis_status DB row rather than
in-memory state, so they're visible from any browser session/tab and
survive a page refresh.
"""
import threading

from chess_analyzer.analysis import analyze_pending_games
from chess_analyzer.config import DB_PATH, ENGINE_DEPTH, ENGINE_HASH_MB, ENGINE_THREADS, STOCKFISH_PATH
from chess_analyzer.db import (
    finish_analysis_status,
    get_analysis_status,
    init_db,
    is_cancel_requested,
    start_analysis_status,
    update_analysis_progress,
)

_lock = threading.Lock()
_current_thread: threading.Thread | None = None


def is_running_here() -> bool:
    """Whether a background analysis thread from *this* process is alive.

    A DB row can say running=1 even after the process that set it has died
    (e.g. OOM-killed) without ever reaching finish_analysis_status(). A
    threading.Thread can't survive a process restart, so a fresh process's
    _current_thread is always None — that's what lets this tell a
    genuinely live thread apart from a stale leftover flag.
    """
    return _current_thread is not None and _current_thread.is_alive()


def reconcile_stale_status(conn) -> bool:
    """Clear the DB's running flag if it's stale (no live thread for it in
    this process). Returns True if it cleared one.
    """
    if get_analysis_status(conn)["running"] and not is_running_here():
        finish_analysis_status(
            conn,
            error=(
                "Analysis stopped unexpectedly (the app process restarted, "
                "likely out of memory). Click Analyze to resume from where it left off."
            ),
        )
        return True
    return False


def _run(stockfish_path: str, depth: int, threads: int, hash_mb: int) -> None:
    conn = init_db(DB_PATH)
    try:
        def _progress(done, total):
            update_analysis_progress(conn, done)

        def _cancelled():
            return is_cancel_requested(conn)

        error = None
        try:
            analyze_pending_games(
                conn=conn, stockfish_path=stockfish_path, depth=depth,
                threads=threads, hash_mb=hash_mb,
                progress_callback=_progress, should_cancel=_cancelled,
            )
        except Exception as exc:  # surfaced in the UI rather than lost in the thread
            error = str(exc)
        finish_analysis_status(conn, error=error)
    finally:
        conn.close()


def start_background_analysis(
    stockfish_path: str = STOCKFISH_PATH,
    depth: int = ENGINE_DEPTH,
    threads: int = ENGINE_THREADS,
    hash_mb: int = ENGINE_HASH_MB,
) -> bool:
    """Start an analysis run in a background thread. Returns False if one is
    already running (check analysis_status for live progress instead).
    """
    global _current_thread
    with _lock:
        conn = init_db(DB_PATH)
        try:
            reconcile_stale_status(conn)
            if get_analysis_status(conn)["running"]:
                return False
            pending = conn.execute("SELECT COUNT(*) FROM games WHERE analyzed = 0").fetchone()[0]
            if pending == 0:
                return False
            start_analysis_status(conn, pending)
        finally:
            conn.close()

        thread = threading.Thread(
            target=_run, args=(stockfish_path, depth, threads, hash_mb), daemon=True,
        )
        _current_thread = thread
        thread.start()
        return True
