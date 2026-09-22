from chess_analyzer.modules.worst_moves import worst_moves


def test_worst_moves_only_own_color_and_only_blunders(conn, make_game, make_move):
    g1 = make_game(username="tester", color="white")
    make_move(g1, ply=1, color="white", san="Qh5", cp_loss=400, classification="blunder")
    make_move(g1, ply=2, color="black", san="??", cp_loss=900, classification="blunder")  # opponent's
    make_move(g1, ply=3, color="white", san="Nf3", cp_loss=60, classification="inaccuracy")  # not a blunder

    df = worst_moves(conn, "tester", n=10)
    assert len(df) == 1
    assert df.iloc[0]["san"] == "Qh5"
    assert df.iloc[0]["cp_loss"] == 400


def test_worst_moves_sorted_descending_and_limited(conn, make_game, make_move):
    g1 = make_game(username="tester", color="white")
    for i, loss in enumerate([300, 900, 450]):
        make_move(g1, ply=i + 1, color="white", cp_loss=loss, classification="blunder")

    df = worst_moves(conn, "tester", n=2)
    assert len(df) == 2
    assert list(df["cp_loss"]) == [900, 450]


def test_worst_moves_empty_when_no_blunders(conn, make_game, make_move):
    g1 = make_game(username="tester", color="white")
    make_move(g1, ply=1, color="white", cp_loss=10, classification="ok")
    assert worst_moves(conn, "tester").empty
