"""Win/loss pattern module: by color, time control, and opponent strength."""
import sqlite3

import pandas as pd


def _games_df(conn: sqlite3.Connection, username: str) -> pd.DataFrame:
    query = """
        SELECT id, played_at, color, result, time_class, my_rating, opponent_rating
        FROM games WHERE username = ?
    """
    return pd.read_sql_query(query, conn, params=(username,))


def _win_rate_table(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[group_col, "games", "wins", "draws", "losses", "win_rate"])
    grouped = df.groupby(group_col).agg(
        games=("id", "count"),
        wins=("result", lambda s: (s == "win").sum()),
        draws=("result", lambda s: (s == "draw").sum()),
        losses=("result", lambda s: (s == "loss").sum()),
    ).reset_index()
    grouped["win_rate"] = (grouped["wins"] / grouped["games"] * 100).round(1)
    return grouped.sort_values("games", ascending=False).reset_index(drop=True)


def win_rate_by_color(conn: sqlite3.Connection, username: str) -> pd.DataFrame:
    return _win_rate_table(_games_df(conn, username), "color")


def win_rate_by_time_class(conn: sqlite3.Connection, username: str) -> pd.DataFrame:
    return _win_rate_table(_games_df(conn, username), "time_class")


_RATING_BUCKETS = [
    (-10_000, -150, "much weaker (-150+)"),
    (-150, -50, "weaker (-150 to -50)"),
    (-50, 50, "similar (-50 to +50)"),
    (50, 150, "stronger (+50 to +150)"),
    (150, 10_000, "much stronger (+150+)"),
]


def _rating_bucket(diff: float) -> str:
    for lo, hi, label in _RATING_BUCKETS:
        if lo <= diff < hi:
            return label
    return "unknown"


def win_rate_by_opponent_strength(conn: sqlite3.Connection, username: str) -> pd.DataFrame:
    """Win rate bucketed by opponent rating relative to the player's own
    rating at the time of the game (positive diff = opponent was stronger).
    """
    df = _games_df(conn, username)
    df = df[df["my_rating"].notna() & df["opponent_rating"].notna()].copy()
    if df.empty:
        return pd.DataFrame(columns=["bucket", "games", "wins", "draws", "losses", "win_rate"])
    df["rating_diff"] = df["opponent_rating"] - df["my_rating"]
    df["bucket"] = df["rating_diff"].apply(_rating_bucket)
    order = [label for _, _, label in _RATING_BUCKETS]
    result = _win_rate_table(df, "bucket")
    result["_order"] = result["bucket"].apply(lambda b: order.index(b) if b in order else len(order))
    return result.sort_values("_order").drop(columns="_order").reset_index(drop=True)
