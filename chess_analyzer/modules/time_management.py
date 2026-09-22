"""Time management module: clock consumption per game phase.

Derives time spent per move from consecutive clock readings (chess.com PGNs
embed `%clk` per move), rather than just flagging "time pressure" like the
blunder module does.
"""
import re
import sqlite3

import pandas as pd

_TIME_CONTROL_RE = re.compile(r"^(\d+)(?:\+(\d+))?$")


def _parse_time_control(time_control):
    """Return (base_seconds, increment) for a chess.com time_control string,
    or (None, None) for formats we don't handle (e.g. daily/correspondence
    "1/259200").
    """
    if not time_control:
        return None, None
    m = _TIME_CONTROL_RE.match(time_control)
    if not m:
        return None, None
    base = int(m.group(1))
    increment = int(m.group(2)) if m.group(2) else 0
    return base, increment


def time_by_phase(conn: sqlite3.Connection, username: str) -> pd.DataFrame:
    """Average and median seconds spent per move, by game phase.

    Only covers live time controls (bullet/blitz/rapid) with a clean
    base(+increment) format; daily/correspondence games are excluded since
    their clocks don't represent per-move thinking time the same way.
    """
    query = """
        SELECT g.id AS game_id, g.time_control, m.ply, m.color, m.phase, m.clock_seconds
        FROM moves m
        JOIN games g ON g.id = m.game_id
        WHERE g.username = ? AND m.color = g.color AND m.clock_seconds IS NOT NULL
    """
    df = pd.read_sql_query(query, conn, params=(username,))
    if df.empty:
        return pd.DataFrame(columns=["phase", "moves", "avg_seconds_per_move", "median_seconds_per_move"])

    parsed = df["time_control"].apply(_parse_time_control)
    df["base_seconds"] = parsed.apply(lambda t: t[0])
    df["increment"] = parsed.apply(lambda t: t[1])
    df = df[df["base_seconds"].notna()].copy()
    if df.empty:
        return pd.DataFrame(columns=["phase", "moves", "avg_seconds_per_move", "median_seconds_per_move"])

    df = df.sort_values(["game_id", "color", "ply"])
    prev_clock = df.groupby(["game_id", "color"])["clock_seconds"].shift(1)
    df["prev_clock"] = prev_clock.fillna(df["base_seconds"])
    df["time_spent"] = (df["prev_clock"] + df["increment"] - df["clock_seconds"]).clip(lower=0)

    grouped = df.groupby("phase").agg(
        moves=("time_spent", "count"),
        avg_seconds_per_move=("time_spent", "mean"),
        median_seconds_per_move=("time_spent", "median"),
    ).reset_index()
    grouped["avg_seconds_per_move"] = grouped["avg_seconds_per_move"].round(1)
    grouped["median_seconds_per_move"] = grouped["median_seconds_per_move"].round(1)

    order = {"opening": 0, "middlegame": 1, "endgame": 2}
    grouped["_order"] = grouped["phase"].map(order)
    return grouped.sort_values("_order").drop(columns="_order").reset_index(drop=True)
