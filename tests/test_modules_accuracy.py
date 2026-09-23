from chess_analyzer.modules.accuracy import (
    _game_accuracy,
    _move_accuracy,
    _win_percent,
    accuracy_trend,
    per_game_accuracy,
)


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


def test_game_accuracy_harmonic_mean_punishes_a_single_blunder_more_than_plain_average():
    """Regression: a plain mean of per-move accuracy lets a handful of easy
    100% moves (opening theory, forced recaptures) dilute one real blunder
    into a still-high game score. Lichess folds in a harmonic mean
    specifically to stop that -- a single low value should pull the game
    score down noticeably below the plain average.
    """
    win_percent_by_ply = {1: 50.0, 2: 50.0, 3: 50.0, 4: 50.0, 5: 50.0}
    # four perfect moves, one disaster
    own_move_accuracy = [(1, 100.0), (2, 100.0), (3, 100.0), (4, 100.0), (5, 10.0)]

    plain_average = sum(a for _, a in own_move_accuracy) / len(own_move_accuracy)
    game_accuracy = _game_accuracy(win_percent_by_ply, own_move_accuracy)
    assert game_accuracy < plain_average


def test_game_accuracy_downweights_moves_in_an_already_decided_position():
    """A blunder played while the position around it was already settled
    (win% pinned near 0, barely moving either way) should count for less
    than the identical-sized blunder played in a sharp, still-swinging
    position -- that's the concrete mechanism behind losses often scoring
    misleadingly high on a flat average: most of a lost game's moves happen
    after the result is no longer in doubt.
    """
    edges = {1: 50.0, 2: 50.0, 8: 50.0, 9: 50.0}
    sharp_series = {**edges, 3: 20.0, 4: 70.0, 5: 15.0, 6: 80.0, 7: 25.0}
    decided_series = {**edges, 3: 3.0, 4: 2.0, 5: 2.0, 6: 3.0, 7: 2.0}

    own_move_accuracy = [(p, 95.0) for p in range(1, 10)]
    own_move_accuracy[4] = (5, 20.0)  # the blunder, at ply 5 in both scenarios

    sharp_accuracy = _game_accuracy(sharp_series, own_move_accuracy)
    decided_accuracy = _game_accuracy(decided_series, own_move_accuracy)
    assert decided_accuracy > sharp_accuracy


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
