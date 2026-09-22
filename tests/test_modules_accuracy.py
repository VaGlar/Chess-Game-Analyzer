from chess_analyzer.modules.accuracy import _acpl_to_accuracy, accuracy_trend, per_game_accuracy


def test_acpl_to_accuracy_zero_loss_is_100_percent():
    assert _acpl_to_accuracy(0) == 100.0


def test_acpl_to_accuracy_decreases_with_loss():
    low = _acpl_to_accuracy(20)
    high = _acpl_to_accuracy(200)
    assert low > high


def test_acpl_to_accuracy_clipped_to_0_100():
    assert 0.0 <= _acpl_to_accuracy(10000) <= 100.0
    assert _acpl_to_accuracy(10000) >= 0.0


def test_per_game_accuracy_uses_own_moves_only(conn, make_game, make_move):
    g1 = make_game(username="tester", color="white", opponent_username="opp")
    make_move(g1, ply=1, color="white", cp_loss=0)
    make_move(g1, ply=2, color="black", cp_loss=500)  # opponent's blunder, must be ignored
    make_move(g1, ply=3, color="white", cp_loss=40)

    df = per_game_accuracy(conn, "tester")
    assert len(df) == 1
    assert df.iloc[0]["acpl"] == 20.0  # mean of [0, 40], not the opponent's 500


def test_accuracy_trend_adds_rolling_column(conn, make_game, make_move):
    for i in range(3):
        g = make_game(username="tester", played_at=f"2024.01.{10 + i:02d}")
        make_move(g, ply=1, color="white", cp_loss=i * 10)
    df = per_game_accuracy(conn, "tester")
    trend = accuracy_trend(df, window=2)
    assert "accuracy_rolling" in trend.columns
    assert len(trend) == 3


def test_empty_db_returns_empty_frame(conn):
    assert per_game_accuracy(conn, "nobody").empty
