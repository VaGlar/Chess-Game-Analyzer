"""Local configuration for Chess Game Analyzer."""
import os

DB_PATH = os.environ.get("CHESS_ANALYZER_DB", os.path.join("data", "chess_analyzer.db"))
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "stockfish")

# Engine analysis effort. Depth is a good local-speed/accuracy tradeoff for
# a personal tool; raise it if you don't mind analysis taking longer.
ENGINE_DEPTH = int(os.environ.get("CHESS_ANALYZER_DEPTH", "12"))

# Centipawn-loss thresholds used to classify a move.
INACCURACY_CP = 50
MISTAKE_CP = 100
BLUNDER_CP = 300

# A clock reading at or below this many seconds counts as "time pressure".
TIME_PRESSURE_SECONDS = 30

CHESS_COM_USER_AGENT = "ChessGameAnalyzer/1.0 (personal use; contact: local-user)"
