from chess_analyzer.modules.rating import rating_progression


def test_rating_progression_sorted_chronologically(conn, make_game):
    make_game(played_at="2024.01.20", my_rating=1250, time_class="blitz")
    make_game(played_at="2024.01.10", my_rating=1200, time_class="blitz")
    make_game(played_at="2024.01.15", my_rating=1220, time_class="blitz")

    df = rating_progression(conn, "tester")
    assert list(df["my_rating"]) == [1200, 1220, 1250]
    assert list(df["game_number"]) == [1, 2, 3]


def test_rating_progression_separate_series_per_time_class(conn, make_game):
    make_game(played_at="2024.01.10", my_rating=1200, time_class="blitz")
    make_game(played_at="2024.01.11", my_rating=1500, time_class="rapid")
    make_game(played_at="2024.01.12", my_rating=1210, time_class="blitz")

    df = rating_progression(conn, "tester")
    blitz_numbers = df[df["time_class"] == "blitz"]["game_number"].tolist()
    assert blitz_numbers == [1, 2]


def test_rating_progression_ignores_games_without_rating(conn, make_game):
    make_game(my_rating=None)
    assert rating_progression(conn, "tester").empty
