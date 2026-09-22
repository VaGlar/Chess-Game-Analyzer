"""Rating progression module: how your rating actually moved over time."""
import sqlite3

import pandas as pd


def rating_progression(conn: sqlite3.Connection, username: str) -> pd.DataFrame:
    """Rating after each game, in chronological order, one series per
    time_class (chess.com tracks separate ratings for bullet/blitz/rapid).
    """
    query = """
        SELECT id, played_at, my_rating, opponent_rating, result, time_class, color
        FROM games WHERE username = ? AND my_rating IS NOT NULL
    """
    df = pd.read_sql_query(query, conn, params=(username,))
    if df.empty:
        return df
    df["played_at"] = pd.to_datetime(df["played_at"], errors="coerce")
    df = df.sort_values(["played_at", "id"]).reset_index(drop=True)
    df["game_number"] = df.groupby("time_class").cumcount() + 1
    return df
