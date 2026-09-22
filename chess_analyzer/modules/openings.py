"""Opening repertoire module: frequency and win rate per opening."""
import sqlite3

import pandas as pd


def opening_stats(conn: sqlite3.Connection, username: str, min_games: int = 2) -> pd.DataFrame:
    """Win rate per opening, most-played first.

    Uses all fetched games (doesn't require Stockfish analysis) since it
    only needs the PGN headers and result. Openings played fewer than
    `min_games` times are dropped — a 1-game 100%/0% record isn't a pattern.
    """
    query = """
        SELECT id, opening_name, opening_eco, color, result
        FROM games WHERE username = ? AND opening_name IS NOT NULL
    """
    df = pd.read_sql_query(query, conn, params=(username,))
    if df.empty:
        return pd.DataFrame(columns=["opening_name", "opening_eco", "games", "wins",
                                      "draws", "losses", "win_rate"])
    grouped = df.groupby(["opening_name", "opening_eco"]).agg(
        games=("id", "count"),
        wins=("result", lambda s: (s == "win").sum()),
        draws=("result", lambda s: (s == "draw").sum()),
        losses=("result", lambda s: (s == "loss").sum()),
    ).reset_index()
    grouped["win_rate"] = (grouped["wins"] / grouped["games"] * 100).round(1)
    grouped = grouped[grouped["games"] >= min_games]
    return grouped.sort_values("games", ascending=False).reset_index(drop=True)
