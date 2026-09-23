from chess_analyzer.modules.accuracy import _move_accuracy, _win_percent, accuracy_trend, per_game_accuracy


def test_win_percent_is_50_at_equal_eval():
    assert _win_percent(0) == 50.0


def test_win_percent_increases_with_eval():
    assert _win_percent(200) > _win_percent(0) > _win_percent(-200)


def test_move_accuracy_no_drop_is_100_percent():
    assert _move_accuracy(55.0, 55.0) == 100.0


def test_move_accuracy_decreases_with_win_percent_drop():
    small_drop = _move_accuracy(55.0, 50.0)
    big_drop = _move_accuracy(55.0, 10.0)
    assert small_drop > big_drop


def test_move_accuracy_clipped_to_0_100():
    value = _move_accuracy(90.0, 0.0)
    assert 0.0 <= value <= 100.0


def test_move_accuracy_ignores_a_win_percent_gain():
    # the opponent blundering shouldn't inflate *my* move's accuracy
    assert _move_accuracy(50.0, 90.0) == 100.0


def test_per_game_accuracy_uses_own_moves_only(conn, make_game, make_move):
    g1 = make_game(username="tester", color="white", opponent_username="opp")
    make_move(g1, ply=1, color="white", eval_cp_before=20, eval_cp_after=20, cp_loss=0)
    make_move(g1, ply=2, color="black", eval_cp_before=20, eval_cp_after=-480, cp_loss=500)  # opponent's blunder, must be ignored
    make_move(g1, ply=3, color="white", eval_cp_before=-480, eval_cp_after=-520, cp_loss=40)

    df = per_game_accuracy(conn, "tester")
    assert len(df) == 1
    assert df.iloc[0]["acpl"] == 20.0  # mean of [0, 40], not the opponent's 500


def test_per_game_accuracy_lands_in_realistic_range_for_small_cp_loss(conn, make_game, make_move):
    """Regression: feeding raw ACPL straight into the Lichess decay formula
    produced absurd single-digit accuracy for completely ordinary blitz
    play. A game with only small, realistic per-move win%-drops should
    score in the normal 70-100% band, not near 0%.
    """
    g1 = make_game(username="tester", color="white")
    # small, realistic evals close to equal -- nowhere near a blunder
    make_move(g1, ply=1, color="white", eval_cp_before=10, eval_cp_after=5, cp_loss=5)
    make_move(g1, ply=3, color="white", eval_cp_before=8, eval_cp_after=-2, cp_loss=10)
    make_move(g1, ply=5, color="white", eval_cp_before=0, eval_cp_after=-15, cp_loss=15)

    df = per_game_accuracy(conn, "tester")
    assert df.iloc[0]["accuracy"] >= 70.0


def test_per_game_accuracy_clamped_mate_scores_dont_blow_up_acpl(conn, make_game, make_move):
    """Regression: an unclamped mate score used to produce ACPL values in
    the tens of thousands from a single mate-in-N move. Values already
    clamped to +-1000 (MATE_SCORE) must keep ACPL/accuracy sane.
    """
    g1 = make_game(username="tester", color="white")
    make_move(g1, ply=1, color="white", eval_cp_before=1000, eval_cp_after=1000, cp_loss=0)

    df = per_game_accuracy(conn, "tester")
    assert df.iloc[0]["acpl"] < 100


def test_accuracy_trend_adds_rolling_column(conn, make_game, make_move):
    for i in range(3):
        g = make_game(username="tester", played_at=f"2024.01.{10 + i:02d}")
        make_move(g, ply=1, color="white", eval_cp_before=0, eval_cp_after=-i * 10, cp_loss=i * 10)
    df = per_game_accuracy(conn, "tester")
    trend = accuracy_trend(df, window=2)
    assert "accuracy_rolling" in trend.columns
    assert len(trend) == 3


def test_empty_db_returns_empty_frame(conn):
    assert per_game_accuracy(conn, "nobody").empty
