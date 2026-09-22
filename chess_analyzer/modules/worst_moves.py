"""Worst individual moves: the actual blunders, not just aggregate rates."""
import sqlite3

import pandas as pd


def worst_moves(conn: sqlite3.Connection, username: str, n: int = 20) -> pd.DataFrame:
    """The n single worst moves (by centipawn loss) the player made.

    Each row is a concrete, reviewable mistake: which game, which move
    number, what was played, and how much it cost.
    """
    query = """
        SELECT g.id AS game_id, g.played_at, g.opponent_username, g.result,
               g.url, m.ply, m.move_number, m.color, m.san, m.cp_loss,
               m.classification, m.phase, m.clock_seconds
        FROM moves m
        JOIN games g ON g.id = m.game_id
        WHERE g.username = ? AND m.color = g.color AND m.classification = 'blunder'
        ORDER BY m.cp_loss DESC
        LIMIT ?
    """
    return pd.read_sql_query(query, conn, params=(username, n))
