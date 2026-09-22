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

## Run it — zero local install

Open this repo as a **GitHub Codespace** (button on the repo page: `Code` →
`Codespaces` → `Create codespace on <branch>`). Nothing installs on your
machine at all — the Dockerfile and `docker-compose.yml` build and run in a
free cloud VM, and GitHub forwards the dashboard's port to a URL in your
browser automatically. Stop the codespace when you're done and resume it
later; the SQLite data survives as long as you don't delete the codespace.

## Run it locally instead (needs Docker)

If you'd rather run it on your own machine:

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

## Run it on Fly.io — permanent URL, auto-deployed from GitHub

`fly.toml` and `.github/workflows/fly-deploy.yml` are already set up: every
push to `main` builds the existing Dockerfile and deploys it to Fly, using a
`FLY_API_TOKEN` GitHub Actions secret. Nothing ever gets typed into a chat
or seen by anyone but you — GitHub's Actions runner reads the secret, Fly
never sees this repo directly.

Fly.io isn't free (needs a card on file), and the app gets a public URL
by default — anyone with the link can see your dashboard.

**One-time setup** (run this inside a GitHub Codespace on this repo, not on
your own machine — see above for how to open one):

```bash
curl -L https://fly.io/install.sh | sh
export FLYCTL_INSTALL="$HOME/.fly"
export PATH="$FLYCTL_INSTALL/bin:$PATH"

fly auth login                    # opens a browser login flow
fly launch --no-deploy            # reads fly.toml/Dockerfile; pick a unique app name if asked
fly volumes create chess_data --size 1 --region ams
fly tokens create deploy -x 999999h   # prints a token — copy it
```

Then, in the GitHub repo (not here): **Settings → Secrets and variables →
Actions → New repository secret**, name it `FLY_API_TOKEN`, paste the token
from the last command. From then on every push to `main` deploys
automatically (or trigger one manually from the Actions tab — the workflow
also has `workflow_dispatch`). The Codespace used for setup can be deleted
afterwards; it's not needed for ongoing deploys.

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Most tests seed an in-memory DB directly (fast, no Stockfish needed) and
cover the dashboard modules, fetch parsing, and the background-analysis
self-healing logic. A handful in `test_analysis_engine.py` run the real
Stockfish pipeline on tiny synthetic games — they auto-skip if Stockfish
isn't on PATH. `.github/workflows/tests.yml` runs the full suite on every
push/PR.

## Config

Environment variables (all optional, already set correctly inside the
container by the Dockerfile):

- `CHESS_ANALYZER_DB` — path to the SQLite database (default
  `/app/data/chess_analyzer.db` in the container)
- `STOCKFISH_PATH` — path to the Stockfish binary (default
  `/usr/games/stockfish` in the container)
- `CHESS_ANALYZER_DEPTH` — Stockfish search depth per position (default `12`)
