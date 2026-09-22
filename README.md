# Chess-Game-Analyzer

Chess Game Analyzer — fetches your chess.com game history and analyzes it
move-by-move with Stockfish, surfacing patterns in blunders, accuracy,
openings, time management, and win/loss trends. Local-first, built with
Python and Streamlit.

## MVP scope (v1)

- **Fetch**: pulls your games from the chess.com public API into SQLite.
- **Analysis engine**: runs local Stockfish over every move of every game,
  storing centipawn loss, move classification, game phase, and clock time.
  This same pipeline feeds every dashboard module below.
- **Blunder analysis**: blunder rate by game phase, blunder rate in vs. out
  of time pressure, top 5 worst games by total centipawn loss.
- **Accuracy score**: per-game accuracy (from average centipawn loss) and
  its trend over time.

Opening repertoire, time management, and win/loss pattern modules read from
the same `games`/`moves` tables and can be added later without touching the
fetch or analysis code.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install Stockfish locally (e.g. `apt install stockfish`, `brew install
stockfish`, or download a binary) and note its path.

## Usage

Fetch and analyze via the CLI:

```bash
python cli.py fetch <chess.com-username> [--year 2024] [--month 3]
python cli.py analyze --stockfish-path /usr/games/stockfish [--depth 12]
```

Or launch the dashboard, which can also trigger fetch/analyze from the
sidebar:

```bash
streamlit run dashboard.py
```

Data is stored in `data/chess_analyzer.db` (SQLite, gitignored). Everything
runs locally — no auth, no cloud.

## Config

Environment variables (all optional):

- `CHESS_ANALYZER_DB` — path to the SQLite database (default
  `data/chess_analyzer.db`)
- `STOCKFISH_PATH` — path to the Stockfish binary (default `stockfish`, i.e.
  whatever's on `PATH`)
- `CHESS_ANALYZER_DEPTH` — Stockfish search depth per position (default `12`)
