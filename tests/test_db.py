from chess_analyzer.db import (
    finish_analysis_status,
    get_analysis_status,
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
