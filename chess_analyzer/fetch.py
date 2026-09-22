"""Fetch game history from the chess.com public API into SQLite."""
import re
import sqlite3
import time
from typing import Iterable, Optional

import requests

from chess_analyzer.config import CHESS_COM_USER_AGENT
from chess_analyzer.db import get_connection, init_db

ARCHIVES_URL = "https://api.chess.com/pub/player/{username}/games/archives"
HEADERS = {"User-Agent": CHESS_COM_USER_AGENT}

_PGN_HEADER_RE = re.compile(r'\[(\w+)\s+"(.*)"\]')


def _pgn_headers(pgn: str) -> dict:
    return {m.group(1): m.group(2) for m in _PGN_HEADER_RE.finditer(pgn)}


def _get(url: str) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def list_archives(username: str) -> list:
    data = _get(ARCHIVES_URL.format(username=username))
    return data.get("archives", [])


def _month_filter(archives: Iterable[str], year: Optional[int], month: Optional[int]) -> list:
    if year is None:
        return list(archives)
    suffix = f"/{year:04d}/{month:02d}" if month else f"/{year:04d}/"
    return [a for a in archives if suffix in a]


def fetch_games(
    username: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
    conn: Optional[sqlite3.Connection] = None,
    delay: float = 0.2,
) -> int:
    """Fetch games for `username` and store new ones in the DB.

    Returns the number of newly inserted games. Existing games (by chess.com
    uuid) are skipped, so this is safe to re-run incrementally.
    """
    own_conn = conn is None
    conn = conn or init_db()
    inserted = 0
    try:
        archives = _month_filter(list_archives(username), year, month)
        for archive_url in archives:
            payload = _get(archive_url)
            for game in payload.get("games", []):
                if inserted_row(conn, username, game):
                    inserted += 1
            time.sleep(delay)
        conn.commit()
    finally:
        if own_conn:
            conn.close()
    return inserted


def inserted_row(conn: sqlite3.Connection, username: str, game: dict) -> bool:
    uuid = game.get("uuid")
    pgn = game.get("pgn", "")
    if not uuid or not pgn:
        return False

    white = game.get("white", {})
    black = game.get("black", {})
    is_white = white.get("username", "").lower() == username.lower()
    mine, opp = (white, black) if is_white else (black, white)
    color = "white" if is_white else "black"

    result_map = {"win": "win", "checkmated": "loss", "timeout": "loss", "resigned": "loss",
                  "agreed": "draw", "repetition": "draw", "stalemate": "draw",
                  "insufficient": "draw", "50move": "draw", "abandoned": "loss",
                  "timevsinsufficient": "draw"}
    result = result_map.get(mine.get("result", ""), mine.get("result", ""))

    headers = _pgn_headers(pgn)

    try:
        conn.execute(
            """
            INSERT INTO games (
                uuid, username, played_at, time_control, time_class, color,
                result, my_rating, opponent_rating, opponent_username,
                opening_eco, opening_name, pgn, url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid,
                username,
                headers.get("UTCDate") or headers.get("Date"),
                game.get("time_control"),
                game.get("time_class"),
                color,
                result,
                mine.get("rating"),
                opp.get("rating"),
                opp.get("username"),
                headers.get("ECO"),
                headers.get("ECOUrl") or headers.get("Opening"),
                pgn,
                game.get("url"),
            ),
        )
        return True
    except sqlite3.IntegrityError:
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch chess.com games into SQLite")
    parser.add_argument("username")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--month", type=int, default=None)
    args = parser.parse_args()

    n = fetch_games(args.username, args.year, args.month)
    print(f"Inserted {n} new games for {args.username}")
