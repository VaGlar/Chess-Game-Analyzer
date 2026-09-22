"""blunder_rate_by_phase/_time_pressure/top_worst_games, seeded directly.

top_worst_games regression: an earlier version's SQL selected m.* (which
already has game_id) alongside g.id AS game_id, producing two identically
named columns and crashing pandas' groupby with "not 1-dimensional".
"""
import pytest

from chess_analyzer.modules.blunders import (
    blunder_rate_by_phase,
    blunder_rate_by_time_pressure,
    top_worst_games,
)


def _seed_two_games_with_moves(make_game, make_move):
    g1 = make_game(username="tester", color="white", opponent_username="opp1")
    make_move(g1, ply=1, color="white", san="e4", cp_loss=0, classification="ok", phase="opening")
    make_move(g1, ply=3, color="white", san="Qh5", cp_loss=350, classification="blunder", phase="opening",
              clock_seconds=10, time_pressure=1)
    make_move(g1, ply=5, color="white", san="Nf3", cp_loss=60, classification="inaccuracy", phase="middlegame",
              clock_seconds=90, time_pressure=0)

    g2 = make_game(username="tester", color="black", opponent_username="opp2")
    make_move(g2, ply=2, color="black", san="e5", cp_loss=0, classification="ok", phase="opening",
              clock_seconds=100, time_pressure=0)
    make_move(g2, ply=8, color="black", san="Qxf6", cp_loss=900, classification="blunder", phase="endgame",
              clock_seconds=5, time_pressure=1)
    return g1, g2


def test_top_worst_games_no_duplicate_column_crash_and_sorted(conn, make_game, make_move):
    _seed_two_games_with_moves(make_game, make_move)
    df = top_worst_games(conn, "tester", n=5)
    assert len(df) == 2
    # game 2 (350 no wait: g1 total=0+350+60=410, g2 total=0+900=900) -> g2 first
    assert df.iloc[0]["total_cp_loss"] == 900
    assert df.iloc[0]["blunders"] == 1
    assert df.iloc[1]["total_cp_loss"] == 410


def test_blunder_rate_by_phase_aggregates_own_moves_only(conn, make_game, make_move):
    _seed_two_games_with_moves(make_game, make_move)
    df = blunder_rate_by_phase(conn, "tester")
    phases = dict(zip(df["phase"], df["blunder_rate"]))
    # opening: g1 ply1 (ok) + g1 ply3 (blunder) + g2 ply2 (ok) = 1/3
    assert phases["opening"] == pytest.approx(33.33, abs=0.01)
    assert phases["endgame"] == 100.0


def test_blunder_rate_ignores_opponent_moves(conn, make_game, make_move):
    g1 = make_game(username="tester", color="white")
    make_move(g1, ply=1, color="white", san="e4", cp_loss=0, classification="ok", phase="opening")
    # opponent's own huge blunder shouldn't count towards *my* blunder rate
    make_move(g1, ply=2, color="black", san="??", cp_loss=999, classification="blunder", phase="opening")
    df = blunder_rate_by_phase(conn, "tester")
    assert df.iloc[0]["blunders"] == 0
    assert df.iloc[0]["moves"] == 1


def test_blunder_rate_by_time_pressure_splits_correctly(conn, make_game, make_move):
    _seed_two_games_with_moves(make_game, make_move)
    df = blunder_rate_by_time_pressure(conn, "tester")
    rows = {r["time_pressure"]: r for _, r in df.iterrows()}
    assert rows["time pressure"]["blunders"] == 2
    assert rows["normal"]["blunders"] == 0


def test_empty_db_returns_empty_frames(conn):
    assert top_worst_games(conn, "nobody").empty
    assert blunder_rate_by_phase(conn, "nobody").empty
    assert blunder_rate_by_time_pressure(conn, "nobody").empty
