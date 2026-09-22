"""Blunder analysis module: rate by phase, by time pressure, worst games."""
import sqlite3

import pandas as pd


def _moves_df(conn: sqlite3.Connection, username: str) -> pd.DataFrame:
    query = """
        SELECT m.*, g.username, g.color AS my_color,
               g.opponent_username, g.played_at, g.url, g.time_class, g.result
        FROM moves m
        JOIN games g ON g.id = m.game_id
        WHERE g.username = ? AND m.color = g.color
    """
    return pd.read_sql_query(query, conn, params=(username,))


def blunder_rate_by_phase(conn: sqlite3.Connection, username: str) -> pd.DataFrame:
    """Blunder rate (%) per game phase for the player's own moves."""
    df = _moves_df(conn, username)
    if df.empty:
        return pd.DataFrame(columns=["phase", "moves", "blunders", "blunder_rate"])
    grouped = df.groupby("phase").agg(
        moves=("id", "count"),
        blunders=("classification", lambda s: (s == "blunder").sum()),
    ).reset_index()
    grouped["blunder_rate"] = (grouped["blunders"] / grouped["moves"] * 100).round(2)
    order = {"opening": 0, "middlegame": 1, "endgame": 2}
    grouped["_order"] = grouped["phase"].map(order)
    return grouped.sort_values("_order").drop(columns="_order").reset_index(drop=True)


def blunder_rate_by_time_pressure(conn: sqlite3.Connection, username: str) -> pd.DataFrame:
    """Blunder rate (%) with vs. without time pressure (low clock)."""
    df = _moves_df(conn, username)
    df = df[df["clock_seconds"].notna()]
    if df.empty:
        return pd.DataFrame(columns=["time_pressure", "moves", "blunders", "blunder_rate"])
    grouped = df.groupby("time_pressure").agg(
        moves=("id", "count"),
        blunders=("classification", lambda s: (s == "blunder").sum()),
    ).reset_index()
    grouped["blunder_rate"] = (grouped["blunders"] / grouped["moves"] * 100).round(2)
    grouped["time_pressure"] = grouped["time_pressure"].map({0: "normal", 1: "time pressure"})
    return grouped


def top_worst_games(conn: sqlite3.Connection, username: str, n: int = 5) -> pd.DataFrame:
    """The n games with the highest total centipawn loss on the player's own moves."""
    df = _moves_df(conn, username)
    if df.empty:
        return pd.DataFrame(columns=["game_id", "played_at", "opponent_username", "result",
                                      "url", "total_cp_loss", "blunders"])
    grouped = df.groupby(
        ["game_id", "played_at", "opponent_username", "result", "url"]
    ).agg(
        total_cp_loss=("cp_loss", "sum"),
        blunders=("classification", lambda s: (s == "blunder").sum()),
    ).reset_index()
    return grouped.sort_values("total_cp_loss", ascending=False).head(n).reset_index(drop=True)
