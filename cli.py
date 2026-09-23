"""Command-line entrypoint: fetch chess.com games and run Stockfish analysis.

    python cli.py fetch USERNAME [--year 2024] [--month 3]
    python cli.py analyze [--stockfish-path /usr/bin/stockfish] [--depth 12]
"""
import argparse

from chess_analyzer.analysis import analyze_pending_games, backfill_mate_score_clamp
from chess_analyzer.config import DB_PATH, ENGINE_DEPTH, STOCKFISH_PATH
from chess_analyzer.db import init_db
from chess_analyzer.fetch import backfill_opening_names, backfill_result_reason, fetch_games


def main():
    parser = argparse.ArgumentParser(description="Chess Game Analyzer CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_p = sub.add_parser("fetch", help="Fetch games from chess.com into SQLite")
    fetch_p.add_argument("username")
    fetch_p.add_argument("--year", type=int, default=None)
    fetch_p.add_argument("--month", type=int, default=None)

    analyze_p = sub.add_parser("analyze", help="Run Stockfish analysis on pending games")
    analyze_p.add_argument("--stockfish-path", default=STOCKFISH_PATH)
    analyze_p.add_argument("--depth", type=int, default=ENGINE_DEPTH)
    analyze_p.add_argument("--limit", type=int, default=None)

    sub.add_parser("backfill-openings", help="Re-derive opening names from stored PGNs")
    sub.add_parser("backfill-mate-scores", help="Clamp unclamped mate scores in already-analyzed moves")
    sub.add_parser("backfill-termination", help="Recover result_reason from stored PGNs' Termination header")

    args = parser.parse_args()
    conn = init_db(DB_PATH)

    if args.command == "fetch":
        n = fetch_games(args.username, args.year, args.month, conn=conn)
        print(f"Inserted {n} new games for {args.username}")
    elif args.command == "analyze":
        n = analyze_pending_games(conn=conn, stockfish_path=args.stockfish_path,
                                   depth=args.depth, limit_games=args.limit)
        print(f"Analyzed {n} games")
    elif args.command == "backfill-openings":
        n = backfill_opening_names(conn)
        print(f"Updated opening_name for {n} games")
    elif args.command == "backfill-mate-scores":
        n = backfill_mate_score_clamp(conn)
        print(f"Re-clamped mate scores for {n} moves")
    elif args.command == "backfill-termination":
        n = backfill_result_reason(conn)
        print(f"Recovered result_reason for {n} games")

    conn.close()


if __name__ == "__main__":
    main()
