"""Accuracy score module: per-game accuracy and its trend over time."""
import math
import sqlite3

import pandas as pd


def _acpl_to_accuracy(acpl: float) -> float:
    """Approximate average-centipawn-loss -> accuracy% conversion.

    This mirrors the commonly used exponential-decay approximation (0 ACPL
    -> 100%, decaying towards 0 as ACPL grows), not a full win%-based model.
    """
    if acpl is None or math.isnan(acpl):
        return None
    value = 103.1668 * math.exp(-0.04354 * acpl) - 3.1668
    return round(min(100.0, max(0.0, value)), 2)


def per_game_accuracy(conn: sqlite3.Connection, username: str) -> pd.DataFrame:
    """Accuracy score per game, based on the player's own moves' avg cp loss."""
    query = """
        SELECT g.id AS game_id, g.played_at, g.opponent_username, g.result,
               g.time_class, g.url, m.cp_loss
        FROM games g
        JOIN moves m ON m.game_id = g.id
        WHERE g.username = ? AND m.color = g.color
    """
    df = pd.read_sql_query(query, conn, params=(username,))
    if df.empty:
        return pd.DataFrame(columns=["game_id", "played_at", "opponent_username", "result",
                                      "time_class", "url", "acpl", "accuracy"])
    grouped = df.groupby(
        ["game_id", "played_at", "opponent_username", "result", "time_class", "url"]
    ).agg(acpl=("cp_loss", "mean")).reset_index()
    grouped["accuracy"] = grouped["acpl"].apply(_acpl_to_accuracy)
    grouped["acpl"] = grouped["acpl"].round(1)
    grouped["played_at"] = pd.to_datetime(grouped["played_at"], errors="coerce")
    return grouped.sort_values("played_at").reset_index(drop=True)


def accuracy_trend(df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """Add a rolling-average accuracy column to a per_game_accuracy() result."""
    if df.empty:
        out = df.copy()
        out["accuracy_rolling"] = pd.Series(dtype=float)
        return out
    out = df.sort_values("played_at").reset_index(drop=True).copy()
    out["accuracy_rolling"] = out["accuracy"].rolling(window=window, min_periods=1).mean().round(2)
    return out
