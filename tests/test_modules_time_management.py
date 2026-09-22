from chess_analyzer.modules.time_management import _parse_time_control, time_by_phase


def test_parse_time_control_base_only():
    assert _parse_time_control("180") == (180, 0)


def test_parse_time_control_base_plus_increment():
    assert _parse_time_control("600+5") == (600, 5)


def test_parse_time_control_daily_format_unsupported():
    assert _parse_time_control("1/259200") == (None, None)


def test_parse_time_control_empty():
    assert _parse_time_control(None) == (None, None)
    assert _parse_time_control("") == (None, None)


def test_time_by_phase_computes_seconds_spent(conn, make_game, make_move):
    g1 = make_game(username="tester", color="white", time_control="180")
    # first own move: prev clock is the base (180s); spent 180-170=10s
    make_move(g1, ply=1, color="white", phase="opening", clock_seconds=170)
    # second own move: prev clock is 170 (previous own move), spent 170-150=20s
    make_move(g1, ply=3, color="white", phase="opening", clock_seconds=150)

    df = time_by_phase(conn, "tester")
    row = df[df["phase"] == "opening"].iloc[0]
    assert row["moves"] == 2
    assert row["avg_seconds_per_move"] == 15.0  # mean(10, 20)


def test_time_by_phase_excludes_games_without_clock(conn, make_game, make_move):
    g1 = make_game(username="tester", color="white")
    make_move(g1, ply=1, color="white", clock_seconds=None)
    assert time_by_phase(conn, "tester").empty


def test_time_by_phase_excludes_daily_time_control(conn, make_game, make_move):
    g1 = make_game(username="tester", color="white", time_control="1/259200")
    make_move(g1, ply=1, color="white", clock_seconds=200000)
    assert time_by_phase(conn, "tester").empty
