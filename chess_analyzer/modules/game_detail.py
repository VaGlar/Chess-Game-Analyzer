"""Per-game drill-down: the eval curve and annotated move list for one game.

Aggregate modules tell you *that* you're blundering; this shows *where*,
in the context of the actual game, using the eval already computed by the
analysis pipeline for every move (not just the player's own).
"""
import sqlite3

import pandas as pd

_FLAG = {"blunder": "🔴", "mistake": "🟠", "inaccuracy": "🟡", "ok": ""}


def games_for_selector(conn: sqlite3.Connection, username: str) -> pd.DataFrame:
    """Analyzed games, most recent first, for a game-picker dropdown."""
    query = """
        SELECT id, played_at, opponent_username, result, color, time_class, url
        FROM games WHERE username = ? AND analyzed = 1
        ORDER BY played_at DESC, id DESC
    """
    return pd.read_sql_query(query, conn, params=(username,))


def game_summary(conn: sqlite3.Connection, game_id: int) -> dict:
    row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    return dict(row) if row else {}


def game_moves(conn: sqlite3.Connection, game_id: int) -> pd.DataFrame:
    """Every move of the game (both colors) with a White-POV eval so the
    curve reads the same way a normal eval graph does (positive = White
    better), plus a flag emoji for quick visual scanning.
    """
    query = """
        SELECT ply, move_number, color, san, uci, eval_cp_before, eval_cp_after,
               cp_loss, classification, phase, clock_seconds, best_move_uci
        FROM moves WHERE game_id = ? ORDER BY ply
    """
    df = pd.read_sql_query(query, conn, params=(game_id,))
    if df.empty:
        return df
    sign = df["color"].map({"white": 1, "black": -1})
    df["eval_white_pov"] = df["eval_cp_after"] * sign
    df["flag"] = df["classification"].map(_FLAG).fillna("")
    return df
