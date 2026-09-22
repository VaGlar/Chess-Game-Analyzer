from chess_analyzer.fetch import (
    _clean_opening_name,
    _month_filter,
    _pgn_headers,
    backfill_opening_names,
    inserted_row,
)


def _sample_game(uuid="g1", white_username="tester", black_username="opp",
                  white_result="win", black_result="checkmated", eco_url=None):
    eco_line = f'[ECOUrl "{eco_url}"]\n' if eco_url else ""
    pgn = (
        f'[Event "Live Chess"]\n[White "{white_username}"]\n[Black "{black_username}"]\n'
        f'[Result "1-0"]\n[UTCDate "2024.01.15"]\n[TimeControl "180"]\n[ECO "C50"]\n{eco_line}'
        f"\n1. e4 e5 1-0\n"
    )
    return {
        "uuid": uuid,
        "pgn": pgn,
        "white": {"username": white_username, "rating": 1200, "result": white_result},
        "black": {"username": black_username, "rating": 1250, "result": black_result},
        "time_control": "180",
        "time_class": "blitz",
        "url": f"https://chess.com/game/{uuid}",
    }


def test_clean_opening_name_from_ecourl():
    headers = {"ECOUrl": "https://www.chess.com/openings/Italian-Game-Giuoco-Piano"}
    assert _clean_opening_name(headers) == "Italian Game Giuoco Piano"


def test_clean_opening_name_falls_back_to_opening_header():
    headers = {"Opening": "Sicilian Defense"}
    assert _clean_opening_name(headers) == "Sicilian Defense"


def test_clean_opening_name_falls_back_to_eco_code():
    headers = {"ECO": "B20"}
    assert _clean_opening_name(headers) == "B20"


def test_clean_opening_name_none_when_nothing_present():
    assert _clean_opening_name({}) is None


def test_inserted_row_stores_correct_color_for_white_player(conn):
    ok = inserted_row(conn, "tester", _sample_game())
    conn.commit()
    assert ok is True
    row = conn.execute("SELECT color, result, opponent_username FROM games WHERE uuid = 'g1'").fetchone()
    assert row["color"] == "white"
    assert row["result"] == "win"
    assert row["opponent_username"] == "opp"


def test_inserted_row_stores_correct_color_for_black_player(conn):
    # "tester" plays black this time
    game = _sample_game(uuid="g2", white_username="opp2", black_username="tester",
                         white_result="win", black_result="resigned")
    ok = inserted_row(conn, "tester", game)
    conn.commit()
    assert ok is True
    row = conn.execute("SELECT color, result FROM games WHERE uuid = 'g2'").fetchone()
    assert row["color"] == "black"
    assert row["result"] == "loss"


def test_inserted_row_is_idempotent_on_duplicate_uuid(conn):
    game = _sample_game()
    assert inserted_row(conn, "tester", game) is True
    conn.commit()
    assert inserted_row(conn, "tester", game) is False
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert count == 1


def test_inserted_row_rejects_missing_uuid_or_pgn(conn):
    assert inserted_row(conn, "tester", {"pgn": "x"}) is False
    assert inserted_row(conn, "tester", {"uuid": "x"}) is False


def test_month_filter_matches_year_and_month():
    archives = [
        "https://api.chess.com/pub/player/x/games/2023/12",
        "https://api.chess.com/pub/player/x/games/2024/01",
        "https://api.chess.com/pub/player/x/games/2024/02",
    ]
    assert _month_filter(archives, None, None) == archives
    assert _month_filter(archives, 2024, None) == archives[1:]
    assert _month_filter(archives, 2024, 1) == [archives[1]]


def test_backfill_opening_names_recomputes_from_stored_pgn(conn):
    game = _sample_game(eco_url="https://www.chess.com/openings/Kings-Pawn-Opening")
    inserted_row(conn, "tester", game)
    conn.commit()
    # simulate an old row that stored the raw ECOUrl before the cleanup fix
    conn.execute("UPDATE games SET opening_name = ? WHERE uuid = 'g1'",
                 ("https://www.chess.com/openings/Kings-Pawn-Opening",))
    conn.commit()

    updated = backfill_opening_names(conn)
    assert updated == 1
    name = conn.execute("SELECT opening_name FROM games WHERE uuid = 'g1'").fetchone()[0]
    assert name == "Kings Pawn Opening"


def test_pgn_headers_parses_quoted_values():
    pgn = '[White "tester"]\n[Black "opp"]\n[Result "1-0"]\n\n1. e4 e5 1-0\n'
    headers = _pgn_headers(pgn)
    assert headers == {"White": "tester", "Black": "opp", "Result": "1-0"}
