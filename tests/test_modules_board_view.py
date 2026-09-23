from chess_analyzer.modules.board_view import board_svg_at_ply, total_plies

_PGN = """[Event "Test"]
[White "tester"]
[Black "opp"]
[Result "0-1"]

1. e4 e5 2. Qh5 Nc6 3. Bc4 g6 4. Qf3 Nf6 5. Qxf6 Qxf6 0-1
"""


def test_total_plies_counts_half_moves():
    assert total_plies(_PGN) == 10


def test_total_plies_empty_for_unparsable_pgn():
    assert total_plies("") == 0


def test_board_svg_at_ply_zero_is_starting_position():
    svg = board_svg_at_ply(_PGN, 0)
    assert "<svg" in svg
    # White's queen still on d1, no pieces moved yet
    assert "d1" in svg


def test_board_svg_at_ply_reflects_moves_played():
    # after 1 ply (1. e4), a white pawn should have left e2 for e4
    svg_start = board_svg_at_ply(_PGN, 0)
    svg_after_e4 = board_svg_at_ply(_PGN, 1)
    assert svg_start != svg_after_e4


def test_board_svg_draws_arrow_for_best_move():
    without_arrow = board_svg_at_ply(_PGN, 9)
    with_arrow = board_svg_at_ply(_PGN, 9, best_move_uci="g1e2")
    assert with_arrow != without_arrow
    assert "marker-end" in with_arrow or "arrow" in with_arrow.lower()


def test_board_svg_ignores_invalid_best_move_uci():
    # must not raise even with garbage input
    svg = board_svg_at_ply(_PGN, 5, best_move_uci="not-a-move")
    assert "<svg" in svg


def test_board_svg_at_full_game_length_is_final_position():
    svg = board_svg_at_ply(_PGN, total_plies(_PGN))
    assert "<svg" in svg
