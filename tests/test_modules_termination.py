from chess_analyzer.modules.termination import accuracy_by_termination


def test_empty_db_returns_empty_frame(conn):
    assert accuracy_by_termination(conn, "nobody").empty


def test_groups_by_result_and_termination_category(conn, make_game, make_move):
    g1 = make_game(username="tester", result="loss", result_reason="timeout")
    make_move(g1, ply=1, color="white", eval_cp_before=0, eval_cp_after=0, cp_loss=0)

    g2 = make_game(username="tester", result="loss", result_reason="checkmated")
    make_move(g2, ply=1, color="white", eval_cp_before=0, eval_cp_after=-400, cp_loss=400)

    df = accuracy_by_termination(conn, "tester")
    assert set(df["termination"]) == {"timeout", "checkmate"}
    assert set(df["result"]) == {"loss"}
    assert (df["games"] == 1).all()


def test_unmapped_result_reason_falls_back_to_unknown(conn, make_game, make_move):
    g1 = make_game(username="tester", result="loss", result_reason=None)
    make_move(g1, ply=1, color="white", eval_cp_before=0, eval_cp_after=0, cp_loss=0)

    df = accuracy_by_termination(conn, "tester")
    assert df.iloc[0]["termination"] == "unknown"


def test_a_timeout_loss_with_high_accuracy_is_distinguishable_from_a_blundered_one(conn, make_game, make_move):
    """The whole point of this breakdown: a loss decided by the clock should
    show up with high accuracy, separate from a loss actually caused by bad
    moves -- a plain win/loss accuracy average can't tell these apart.
    """
    timeout_game = make_game(username="tester", result="loss", result_reason="timeout")
    make_move(timeout_game, ply=1, color="white", eval_cp_before=10, eval_cp_after=8, cp_loss=2)

    blundered_game = make_game(username="tester", result="loss", result_reason="checkmated")
    make_move(blundered_game, ply=1, color="white", eval_cp_before=100, eval_cp_after=-900, cp_loss=1000)

    df = accuracy_by_termination(conn, "tester")
    timeout_acc = df[df["termination"] == "timeout"].iloc[0]["avg_accuracy"]
    checkmate_acc = df[df["termination"] == "checkmate"].iloc[0]["avg_accuracy"]
    assert timeout_acc > checkmate_acc
