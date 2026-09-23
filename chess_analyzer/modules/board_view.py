"""Interactive chessboard rendering for the Game detail view.

Walks the stored PGN to whatever ply the user is looking at and renders an
SVG board — the same source of truth (the PGN) the rest of the analysis
pipeline uses, so it can never drift from the move list shown alongside it.
"""
import io

import chess
import chess.pgn
import chess.svg


def total_plies(pgn_text: str) -> int:
    """Number of half-moves in the game (0 for an unparsable/empty PGN)."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return 0
    return sum(1 for _ in game.mainline())


def board_svg_at_ply(
    pgn_text: str,
    ply: int,
    best_move_uci: str = None,
    size: int = 400,
) -> str:
    """SVG of the position after `ply` half-moves (ply=0 is the start).

    If best_move_uci is given, draws a green arrow for it — the engine's
    recommended alternative to whatever was actually played at that ply.
    The arrow is drawn on squares only (UCI encodes absolute squares), so
    it stays meaningful even though the board has already moved on.
    """
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return chess.svg.board(size=size)

    board = game.board()
    lastmove = None
    for i, node in enumerate(game.mainline(), start=1):
        if i > ply:
            break
        lastmove = node.move
        board.push(node.move)

    arrows = []
    if best_move_uci:
        try:
            best_move = chess.Move.from_uci(best_move_uci)
            arrows.append(chess.svg.Arrow(best_move.from_square, best_move.to_square, color="green"))
        except ValueError:
            pass

    check_square = board.king(board.turn) if board.is_check() else None
    return chess.svg.board(board=board, lastmove=lastmove, arrows=arrows, check=check_square, size=size)
