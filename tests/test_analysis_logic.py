"""Pure-logic tests for analysis.py helpers that don't need a real engine."""
import chess

from chess_analyzer.analysis import _classify, _clock_seconds, _phase
from chess_analyzer.config import BLUNDER_CP, INACCURACY_CP, MISTAKE_CP


def test_classify_thresholds():
    assert _classify(0) == "ok"
    assert _classify(INACCURACY_CP - 1) == "ok"
    assert _classify(INACCURACY_CP) == "inaccuracy"
    assert _classify(MISTAKE_CP - 1) == "inaccuracy"
    assert _classify(MISTAKE_CP) == "mistake"
    assert _classify(BLUNDER_CP - 1) == "mistake"
    assert _classify(BLUNDER_CP) == "blunder"
    assert _classify(BLUNDER_CP + 500) == "blunder"


def test_clock_seconds_parses_hms():
    assert _clock_seconds("[%clk 0:03:00]") == 180
    assert _clock_seconds("[%clk 1:00:00]") == 3600
    assert _clock_seconds("[%clk 0:00:07.5]") == 7


def test_clock_seconds_none_when_absent():
    assert _clock_seconds("") is None
    assert _clock_seconds("just a comment") is None


def test_phase_opening_by_move_number():
    board = chess.Board()
    assert _phase(board, fullmove_number=1) == "opening"
    assert _phase(board, fullmove_number=10) == "opening"


def test_phase_middlegame_full_material_after_move_10():
    board = chess.Board()  # full starting material, but "late" move number
    assert _phase(board, fullmove_number=11) == "middlegame"


def test_phase_endgame_when_low_material():
    board = chess.Board()
    board.clear_board()
    board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(chess.E8, chess.Piece(chess.KING, chess.BLACK))
    board.set_piece_at(chess.A1, chess.Piece(chess.ROOK, chess.WHITE))
    assert _phase(board, fullmove_number=25) == "endgame"
