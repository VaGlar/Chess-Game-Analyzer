"""Pure-logic tests for analysis.py helpers that don't need a real engine."""
import chess

from chess_analyzer.analysis import MATE_SCORE, _classify, _clock_seconds, _phase, backfill_mate_score_clamp
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


def test_backfill_mate_score_clamp_fixes_unclamped_old_rows(conn, make_game, make_move):
    """Regression: games analyzed before MATE_SCORE was lowered to 1000
    have eval_cp_before/after values around +-100000 from a mate score
    that was never clamped, which then poisons cp_loss/classification
    (and therefore ACPL/accuracy) for that move. The backfill must clamp
    those old rows and recompute cp_loss/classification from the clamped
    values.
    """
    g1 = make_game(username="tester")
    make_move(
        g1, ply=1, color="white",
        eval_cp_before=100_000, eval_cp_after=-100_000,
        cp_loss=200_000, is_best=0, classification="blunder",
    )
    make_move(g1, ply=2, color="white", eval_cp_before=20, eval_cp_after=10, cp_loss=10)

    updated = backfill_mate_score_clamp(conn)
    assert updated == 1  # only the out-of-range row is touched

    row = conn.execute("SELECT * FROM moves WHERE ply = 1").fetchone()
    assert row["eval_cp_before"] == MATE_SCORE
    assert row["eval_cp_after"] == -MATE_SCORE
    assert row["cp_loss"] == 2 * MATE_SCORE
    assert row["classification"] == "blunder"

    untouched = conn.execute("SELECT * FROM moves WHERE ply = 2").fetchone()
    assert untouched["eval_cp_before"] == 20
    assert untouched["cp_loss"] == 10


def test_backfill_mate_score_clamp_respects_is_best(conn, make_game, make_move):
    g1 = make_game(username="tester")
    make_move(
        g1, ply=1, color="white",
        eval_cp_before=100_000, eval_cp_after=100_000,
        cp_loss=0, is_best=1, classification="ok",
    )

    backfill_mate_score_clamp(conn)
    row = conn.execute("SELECT * FROM moves WHERE ply = 1").fetchone()
    assert row["classification"] == "ok"
    assert row["cp_loss"] == 0
