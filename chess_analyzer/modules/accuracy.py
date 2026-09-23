"""Accuracy score module: per-game accuracy and its trend over time."""
import math
import sqlite3

import pandas as pd


def _win_percent(cp: float) -> float:
    """Centipawn eval (from the mover's own POV) -> win probability %,
    using the logistic model Lichess's accuracy calculation is built on.
    Centipawns aren't linear in practical winning chances -- losing 50cp
    at a roughly equal position matters far more than losing 50cp when
    already up a rook -- so accuracy has to be derived from this, not from
    raw cp loss directly.
    """
    return 50 + 50 * (2 / (1 + math.exp(-0.00368 * cp)) - 1)


def _move_accuracy(win_percent_before: float, win_percent_after: float) -> float:
    """Per-move accuracy: the Lichess exponential-decay curve applied to how
    much this move's win% dropped (0% drop -> 100%, decaying towards 0% as
    the drop grows).
    """
    win_drop = max(0.0, win_percent_before - win_percent_after)
    value = 103.1668 * math.exp(-0.04354 * win_drop) - 3.1668
    return min(100.0, max(0.0, value))


def per_game_accuracy(conn: sqlite3.Connection, username: str) -> pd.DataFrame:
    """Accuracy score per game, based on the player's own moves.

    Each move's accuracy comes from its own win%-drop (see _move_accuracy),
    and the game's accuracy is the average of its moves' accuracy -- not
    the decay formula applied once to the game's mean centipawn loss, which
    is a different (and much harsher, order-of-magnitude-wrong) quantity.
    """
    query = """
        SELECT g.id AS game_id, g.played_at, g.opponent_username, g.result,
               g.time_class, g.url, m.cp_loss, m.eval_cp_before, m.eval_cp_after
        FROM games g
        JOIN moves m ON m.game_id = g.id
        WHERE g.username = ? AND m.color = g.color
    """
    df = pd.read_sql_query(query, conn, params=(username,))
    if df.empty:
        return pd.DataFrame(columns=["game_id", "played_at", "opponent_username", "result",
                                      "time_class", "url", "acpl", "accuracy"])
    df["move_accuracy"] = [
        _move_accuracy(_win_percent(before), _win_percent(after))
        for before, after in zip(df["eval_cp_before"], df["eval_cp_after"])
    ]
    grouped = df.groupby(
        ["game_id", "played_at", "opponent_username", "result", "time_class", "url"]
    ).agg(acpl=("cp_loss", "mean"), accuracy=("move_accuracy", "mean")).reset_index()
    grouped["accuracy"] = grouped["accuracy"].round(2)
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
