from chess_analyzer.modules.game_detail import game_moves, game_summary, games_for_selector


def test_game_moves_white_pov_sign_flip(conn, make_game, make_move):
    g1 = make_game()
    # White's move: eval_cp_after is already White's own perspective -> unchanged
    make_move(g1, ply=1, color="white", eval_cp_after=50)
    # Black's move: eval_cp_after is Black's perspective -> flips sign for White POV
    make_move(g1, ply=2, color="black", eval_cp_after=-30)

    df = game_moves(conn, g1)
    row_white = df[df["ply"] == 1].iloc[0]
    row_black = df[df["ply"] == 2].iloc[0]
    assert row_white["eval_white_pov"] == 50
    assert row_black["eval_white_pov"] == 30


def test_game_moves_flag_emoji_by_classification(conn, make_game, make_move):
    g1 = make_game()
    make_move(g1, ply=1, classification="blunder")
    make_move(g1, ply=2, classification="ok")

    df = game_moves(conn, g1)
    flags = dict(zip(df["ply"], df["flag"]))
    assert flags[1] == "🔴"
    assert flags[2] == ""


def test_games_for_selector_only_analyzed_most_recent_first(conn, make_game):
    make_game(played_at="2024.01.10", analyzed=1)
    make_game(played_at="2024.01.20", analyzed=1)
    make_game(played_at="2024.01.15", analyzed=0)  # not analyzed, excluded

    df = games_for_selector(conn, "tester")
    assert len(df) == 2
    assert list(df["played_at"]) == ["2024.01.20", "2024.01.10"]


def test_game_summary_returns_dict(conn, make_game):
    gid = make_game(opponent_username="rival")
    summary = game_summary(conn, gid)
    assert summary["opponent_username"] == "rival"


def test_game_summary_missing_id_returns_empty_dict(conn):
    assert game_summary(conn, 99999) == {}


def test_game_moves_empty_for_unknown_game(conn):
    assert game_moves(conn, 99999).empty
