from chess_analyzer.modules.win_loss import (
    _rating_bucket,
    win_rate_by_color,
    win_rate_by_opponent_strength,
    win_rate_by_time_class,
)


def test_rating_bucket_boundaries():
    assert _rating_bucket(-200) == "much weaker (-150+)"
    assert _rating_bucket(-150) == "weaker (-150 to -50)"
    assert _rating_bucket(-50) == "similar (-50 to +50)"
    assert _rating_bucket(0) == "similar (-50 to +50)"
    assert _rating_bucket(49.9) == "similar (-50 to +50)"
    assert _rating_bucket(50) == "stronger (+50 to +150)"
    assert _rating_bucket(150) == "much stronger (+150+)"


def test_win_rate_by_color(conn, make_game):
    make_game(color="white", result="win")
    make_game(color="white", result="loss")
    make_game(color="black", result="win")

    df = win_rate_by_color(conn, "tester")
    rows = {r["color"]: r for _, r in df.iterrows()}
    assert rows["white"]["games"] == 2
    assert rows["white"]["win_rate"] == 50.0
    assert rows["black"]["win_rate"] == 100.0


def test_win_rate_by_time_class(conn, make_game):
    make_game(time_class="blitz", result="win")
    make_game(time_class="blitz", result="win")
    make_game(time_class="rapid", result="loss")

    df = win_rate_by_time_class(conn, "tester")
    rows = {r["time_class"]: r for _, r in df.iterrows()}
    assert rows["blitz"]["win_rate"] == 100.0
    assert rows["rapid"]["win_rate"] == 0.0


def test_win_rate_by_opponent_strength_buckets(conn, make_game):
    make_game(my_rating=1200, opponent_rating=1000, result="win")   # much weaker opp
    make_game(my_rating=1200, opponent_rating=1350, result="loss")  # much stronger opp

    df = win_rate_by_opponent_strength(conn, "tester")
    buckets = dict(zip(df["bucket"], df["win_rate"]))
    assert buckets["much weaker (-150+)"] == 100.0
    assert buckets["much stronger (+150+)"] == 0.0


def test_win_rate_ignores_games_without_ratings(conn, make_game):
    make_game(my_rating=None, opponent_rating=None)
    assert win_rate_by_opponent_strength(conn, "tester").empty


def test_win_rate_all_games_regardless_of_analyzed_flag(conn, make_game):
    make_game(analyzed=0, color="white", result="win")
    df = win_rate_by_color(conn, "tester")
    assert not df.empty


def test_empty_db_returns_empty_frames(conn):
    assert win_rate_by_color(conn, "nobody").empty
    assert win_rate_by_time_class(conn, "nobody").empty
    assert win_rate_by_opponent_strength(conn, "nobody").empty
