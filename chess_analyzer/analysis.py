"""Move-by-move Stockfish analysis pipeline.

Feeds every module: for each unanalyzed game in the DB, walk the PGN,
evaluate each position with Stockfish, and store per-move centipawn loss,
classification (blunder/mistake/inaccuracy/ok), game phase and clock time.
"""
import io
import re
import sqlite3
from typing import Callable, Optional

import chess
import chess.engine
import chess.pgn

from chess_analyzer.config import (
    BLUNDER_CP,
    ENGINE_DEPTH,
    ENGINE_HASH_MB,
    ENGINE_RESTART_EVERY_N_GAMES,
    ENGINE_THREADS,
    INACCURACY_CP,
    MISTAKE_CP,
    STOCKFISH_PATH,
    TIME_PRESSURE_SECONDS,
)
from chess_analyzer.db import get_connection, init_db

MATE_SCORE = 100_000
_CLOCK_RE = re.compile(r"\[%clk\s+(\d+):(\d+):(\d+(?:\.\d+)?)\]")


def _clock_seconds(comment: str) -> Optional[int]:
    m = _CLOCK_RE.search(comment or "")
    if not m:
        return None
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(float(s))


def _phase(board: chess.Board, fullmove_number: int) -> str:
    if fullmove_number <= 10:
        return "opening"
    non_pawn_material = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        non_pawn_material += len(board.pieces(piece_type, chess.WHITE))
        non_pawn_material += len(board.pieces(piece_type, chess.BLACK))
    if non_pawn_material <= 6:
        return "endgame"
    return "middlegame"


def _classify(cp_loss: int) -> str:
    if cp_loss >= BLUNDER_CP:
        return "blunder"
    if cp_loss >= MISTAKE_CP:
        return "mistake"
    if cp_loss >= INACCURACY_CP:
        return "inaccuracy"
    return "ok"


def _score_cp(score: chess.engine.PovScore, color: chess.Color) -> int:
    return score.pov(color).score(mate_score=MATE_SCORE)


def analyze_game(engine: chess.engine.SimpleEngine, pgn_text: str, depth: int = ENGINE_DEPTH) -> list:
    """Return a list of per-move dicts for a single PGN game."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return []

    board = game.board()
    limit = chess.engine.Limit(depth=depth)
    rows = []
    ply = 0

    info_before = engine.analyse(board, limit)
    for node in game.mainline():
        move = node.move
        mover = board.turn
        fullmove_number = board.fullmove_number
        score_before = _score_cp(info_before["score"], mover)
        best_move = info_before.get("pv", [None])[0]

        san = board.san(move)
        uci = move.uci()
        board.push(move)
        ply += 1

        info_after = engine.analyse(board, limit)
        score_after = _score_cp(info_after["score"], mover)

        cp_loss = max(0, score_before - score_after)
        is_best = best_move is not None and best_move == move
        classification = "ok" if is_best else _classify(cp_loss)

        clock = _clock_seconds(node.comment)

        rows.append({
            "ply": ply,
            "move_number": fullmove_number,
            "color": "white" if mover == chess.WHITE else "black",
            "san": san,
            "uci": uci,
            "eval_cp_before": score_before,
            "eval_cp_after": score_after,
            "cp_loss": cp_loss,
            "is_best": int(is_best),
            "classification": classification,
            "phase": _phase(board, fullmove_number),
            "clock_seconds": clock,
            "time_pressure": int(clock is not None and clock <= TIME_PRESSURE_SECONDS),
        })

        info_before = info_after

    return rows


def _spawn_engine(stockfish_path: str, threads: int, hash_mb: int) -> chess.engine.SimpleEngine:
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    engine.configure({"Threads": threads, "Hash": hash_mb})
    return engine


def _safe_quit(engine: chess.engine.SimpleEngine) -> None:
    """Best-effort engine shutdown. If the process/event loop already died
    (OOM kill, crash, resource starvation — anything), quit() itself can
    raise; that must never take down the whole analysis run, since we're
    discarding this engine either way.
    """
    try:
        engine.quit()
    except Exception:
        pass


def analyze_pending_games(
    conn: Optional[sqlite3.Connection] = None,
    stockfish_path: str = STOCKFISH_PATH,
    depth: int = ENGINE_DEPTH,
    limit_games: Optional[int] = None,
    threads: int = ENGINE_THREADS,
    hash_mb: int = ENGINE_HASH_MB,
    restart_every: int = ENGINE_RESTART_EVERY_N_GAMES,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> int:
    """Analyze every game with analyzed=0. Returns the number of games analyzed.

    If given, progress_callback(games_done, games_total) is called after
    each game is committed, so a caller (e.g. the dashboard) can show live
    progress through a long run. If given, should_cancel() is checked before
    each game; returning True stops the run cleanly (already-committed
    games are kept, nothing partial is written).

    The Stockfish process is restarted every `restart_every` games (0/None
    disables this) — a single long-lived process can slow down over a long
    run, and a periodic fresh one is cheap insurance against that. It's
    invisible to the caller: progress just keeps climbing across the swap.
    """
    own_conn = conn is None
    conn = conn or init_db()
    count = 0
    try:
        query = "SELECT id, pgn FROM games WHERE analyzed = 0"
        if limit_games:
            query += f" LIMIT {int(limit_games)}"
        games = conn.execute(query).fetchall()
        if not games:
            return 0
        total = len(games)

        engine = _spawn_engine(stockfish_path, threads, hash_mb)
        games_on_current_engine = 0
        try:
            for row in games:
                if should_cancel and should_cancel():
                    break
                if restart_every and games_on_current_engine >= restart_every:
                    _safe_quit(engine)
                    engine = _spawn_engine(stockfish_path, threads, hash_mb)
                    games_on_current_engine = 0

                move_rows = analyze_game(engine, row["pgn"], depth=depth)
                for mr in move_rows:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO moves (
                            game_id, ply, move_number, color, san, uci,
                            eval_cp_before, eval_cp_after, cp_loss, is_best,
                            classification, phase, clock_seconds, time_pressure
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row["id"], mr["ply"], mr["move_number"], mr["color"],
                            mr["san"], mr["uci"], mr["eval_cp_before"], mr["eval_cp_after"],
                            mr["cp_loss"], mr["is_best"], mr["classification"], mr["phase"],
                            mr["clock_seconds"], mr["time_pressure"],
                        ),
                    )
                conn.execute("UPDATE games SET analyzed = 1 WHERE id = ?", (row["id"],))
                conn.commit()
                count += 1
                games_on_current_engine += 1
                if progress_callback:
                    progress_callback(count, total)
        finally:
            _safe_quit(engine)
    finally:
        if own_conn:
            conn.close()
    return count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze pending games with Stockfish")
    parser.add_argument("--stockfish-path", default=STOCKFISH_PATH)
    parser.add_argument("--depth", type=int, default=ENGINE_DEPTH)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    n = analyze_pending_games(stockfish_path=args.stockfish_path, depth=args.depth, limit_games=args.limit)
    print(f"Analyzed {n} games")
