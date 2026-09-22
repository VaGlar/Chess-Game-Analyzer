# Chess-Game-Analyzer

Chess Game Analyzer — fetches your chess.com game history and analyzes it
move-by-move with Stockfish, surfacing patterns in blunders, accuracy,
openings, time management, and win/loss trends. Local-first, containerized,
built with Python and Streamlit.

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

## Run it

Requires only Docker — no Python, pip, or Stockfish install on your machine.
The image bundles Python, all dependencies, and the Stockfish binary.

```bash
docker compose up --build
```

Then open http://localhost:8501. Use the sidebar to fetch your chess.com
games and run Stockfish analysis; both tabs (blunders, accuracy) update from
there.

Data is stored in a named Docker volume (`chess_data`), so it survives
container restarts and rebuilds. To reset it: `docker compose down -v`.

### CLI, without the dashboard

The same image can run the fetch/analyze CLI directly:

```bash
docker compose run --rm dashboard python cli.py fetch <chess.com-username> [--year 2024] [--month 3]
docker compose run --rm dashboard python cli.py analyze [--depth 12]
```

## Config

Environment variables (all optional, already set correctly inside the
container by the Dockerfile):

- `CHESS_ANALYZER_DB` — path to the SQLite database (default
  `/app/data/chess_analyzer.db` in the container)
- `STOCKFISH_PATH` — path to the Stockfish binary (default
  `/usr/games/stockfish` in the container)
- `CHESS_ANALYZER_DEPTH` — Stockfish search depth per position (default `12`)
