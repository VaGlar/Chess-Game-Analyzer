"""How games actually ended, cross-referenced with accuracy.

per_game_accuracy() answers "how well did I play"; this answers "what
actually decided the game" -- a loss with perfectly ordinary accuracy that
keeps showing up as "timeout" points at time management, not chess
understanding, and a flat accuracy average can hide that entirely.
"""
import sqlite3

import pandas as pd

from chess_analyzer.modules.accuracy import per_game_accuracy

# chess.com's own per-player "result" vocabulary, grouped into a handful of
# human-readable buckets for display.
_CATEGORY_BY_REASON = {
    "win": "won",
    "checkmated": "checkmate",
    "timeout": "timeout",
    "resigned": "resignation",
    "abandoned": "abandoned",
    "agreed": "draw (agreed)",
    "repetition": "draw (repetition)",
    "stalemate": "draw (stalemate)",
    "insufficient": "draw (insufficient material)",
    "50move": "draw (50-move rule)",
    "timevsinsufficient": "draw (time vs. insufficient material)",
}


def _category(result_reason: str) -> str:
    return _CATEGORY_BY_REASON.get(result_reason, "unknown")


def accuracy_by_termination(conn: sqlite3.Connection, username: str) -> pd.DataFrame:
    """Average accuracy grouped by (result, how the game ended).

    A win/loss average alone can't tell a game decided by a real blunder
    apart from one decided by the clock; this table can.
    """
    games = pd.read_sql_query(
        """
        SELECT id AS game_id, result, result_reason FROM games
        WHERE username = ? AND analyzed = 1
        """,
        conn, params=(username,),
    )
    empty = pd.DataFrame(columns=["result", "termination", "games", "avg_accuracy"])
    if games.empty:
        return empty
    games["termination"] = games["result_reason"].apply(_category)

    acc = per_game_accuracy(conn, username)[["game_id", "accuracy"]]
    merged = games.merge(acc, on="game_id", how="inner")
    if merged.empty:
        return empty

    grouped = merged.groupby(["result", "termination"]).agg(
        games=("game_id", "count"), avg_accuracy=("accuracy", "mean")
    ).reset_index()
    grouped["avg_accuracy"] = grouped["avg_accuracy"].round(2)
    return grouped.sort_values(["result", "games"], ascending=[True, False]).reset_index(drop=True)
