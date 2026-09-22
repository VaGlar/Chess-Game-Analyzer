"""Local configuration for Chess Game Analyzer."""
import os

DB_PATH = os.environ.get("CHESS_ANALYZER_DB", os.path.join("data", "chess_analyzer.db"))
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "stockfish")

# Engine analysis effort. Depth is a good local-speed/accuracy tradeoff for
# a personal tool; raise it if you don't mind analysis taking longer.
ENGINE_DEPTH = int(os.environ.get("CHESS_ANALYZER_DEPTH", "12"))

# Number of CPU threads Stockfish searches with. Defaults to all available
# cores (Stockfish itself defaults to 1, which wastes multi-core machines).
ENGINE_THREADS = int(os.environ.get("CHESS_ANALYZER_THREADS", str(os.cpu_count() or 1)))

# Hash table size in MB. Stockfish's own default (16) is small for
# multi-threaded search; a bit more room reduces repeated work.
ENGINE_HASH_MB = int(os.environ.get("CHESS_ANALYZER_HASH_MB", "128"))

# Restart the Stockfish process after this many games in a single analysis
# run. A single long-lived engine process can slow down over a long run
# (hash table fill/fragmentation); a periodic fresh process is cheap
# insurance against that, invisible in the UI since the run itself doesn't
# stop — just the underlying process gets swapped out between games.
ENGINE_RESTART_EVERY_N_GAMES = int(os.environ.get("CHESS_ANALYZER_RESTART_EVERY", "2"))

# Centipawn-loss thresholds used to classify a move.
INACCURACY_CP = 50
MISTAKE_CP = 100
BLUNDER_CP = 300

# A clock reading at or below this many seconds counts as "time pressure".
TIME_PRESSURE_SECONDS = 30

CHESS_COM_USER_AGENT = "ChessGameAnalyzer/1.0 (personal use; contact: local-user)"
