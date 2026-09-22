from chess_analyzer.modules.openings import _opening_family, opening_family_stats, opening_stats


def test_opening_family_truncates_to_two_words():
    assert _opening_family("Italian Game Giuoco Piano") == "Italian Game"
    assert _opening_family("Sicilian Defense Najdorf Variation") == "Sicilian Defense"


def test_opening_family_keeps_short_names_whole():
    assert _opening_family("Ruy Lopez") == "Ruy Lopez"
    assert _opening_family("B20") == "B20"


def test_opening_stats_filters_by_min_games(conn, make_game):
    make_game(opening_name="Italian Game Giuoco Piano", opening_eco="C50", result="win")
    make_game(opening_name="Caro-Kann Defense", opening_eco="B10", result="loss")

    assert opening_stats(conn, "tester", min_games=2).empty
    df = opening_stats(conn, "tester", min_games=1)
    assert len(df) == 2
    assert set(df["family"]) == {"Italian Game", "Caro-Kann Defense"}


def test_opening_family_stats_aggregates_variations(conn, make_game):
    make_game(opening_name="Italian Game Giuoco Piano", opening_eco="C50", result="win")
    make_game(opening_name="Italian Game Two Knights Defense", opening_eco="C55", result="loss")
    make_game(opening_name="Caro-Kann Defense", opening_eco="B10", result="win")

    fam = opening_family_stats(conn, "tester", min_games=2)
    assert len(fam) == 1
    row = fam.iloc[0]
    assert row["family"] == "Italian Game"
    assert row["games"] == 2
    assert row["wins"] == 1
    assert row["losses"] == 1
    assert row["win_rate"] == 50.0


def test_openings_ignore_null_opening_name(conn, make_game):
    make_game(opening_name=None)
    assert opening_stats(conn, "tester", min_games=1).empty


def test_empty_db_returns_empty_frames(conn):
    assert opening_stats(conn, "nobody").empty
    assert opening_family_stats(conn, "nobody").empty
