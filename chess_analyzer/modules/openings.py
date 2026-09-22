"""Opening repertoire module: frequency and win rate per opening."""
import sqlite3

import pandas as pd


def _opening_family(opening_name: str) -> str:
    """Collapse a full opening name to its parent family, e.g.
    'Italian Game Giuoco Piano' -> 'Italian Game', 'Ruy Lopez' -> 'Ruy Lopez'.
    Heuristic (first two words) since chess.com names aren't structured;
    good enough for grouping, not authoritative ECO taxonomy.
    """
    words = opening_name.split()
    return " ".join(words[:2]) if len(words) > 2 else opening_name


def opening_stats(conn: sqlite3.Connection, username: str, min_games: int = 2) -> pd.DataFrame:
    """Win rate per opening (specific variation), most-played first.

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
        return pd.DataFrame(columns=["opening_name", "opening_eco", "family", "games",
                                      "wins", "draws", "losses", "win_rate"])
    grouped = df.groupby(["opening_name", "opening_eco"]).agg(
        games=("id", "count"),
        wins=("result", lambda s: (s == "win").sum()),
        draws=("result", lambda s: (s == "draw").sum()),
        losses=("result", lambda s: (s == "loss").sum()),
    ).reset_index()
    grouped["win_rate"] = (grouped["wins"] / grouped["games"] * 100).round(1)
    grouped["family"] = grouped["opening_name"].apply(_opening_family)
    grouped = grouped[grouped["games"] >= min_games]
    return grouped.sort_values("games", ascending=False).reset_index(drop=True)


def opening_family_stats(conn: sqlite3.Connection, username: str, min_games: int = 2) -> pd.DataFrame:
    """Win rate per opening family (e.g. all Italian Game variations
    combined), most-played first.
    """
    variations = opening_stats(conn, username, min_games=1)
    if variations.empty:
        return pd.DataFrame(columns=["family", "games", "wins", "draws", "losses", "win_rate"])
    grouped = variations.groupby("family").agg(
        games=("games", "sum"),
        wins=("wins", "sum"),
        draws=("draws", "sum"),
        losses=("losses", "sum"),
    ).reset_index()
    grouped["win_rate"] = (grouped["wins"] / grouped["games"] * 100).round(1)
    grouped = grouped[grouped["games"] >= min_games]
    return grouped.sort_values("games", ascending=False).reset_index(drop=True)
