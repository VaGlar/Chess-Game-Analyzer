"""Accuracy score module: per-game accuracy and its trend over time."""
import math
import sqlite3

import pandas as pd


def _win_percent(cp: float) -> float:
    """Centipawn eval (from the mover's own POV) -> win probability %,
    using the logistic model Lichess's accuracy calculation is built on.
    Centipawns aren't linear in practical winning chances -- losing 50cp
    at a roughly equal position matters far more than losing 50cp when
    already up a rook -- so accuracy has to be derived from this, not from
    raw cp loss directly.
    """
    return 50 + 50 * (2 / (1 + math.exp(-0.00368 * cp)) - 1)


def _move_accuracy(win_percent_before: float, win_percent_after: float) -> float:
    """Per-move accuracy: the Lichess exponential-decay curve applied to how
    much this move's win% dropped (0% drop -> 100%, decaying towards 0% as
    the drop grows).
    """
    win_drop = max(0.0, win_percent_before - win_percent_after)
    value = 103.1668 * math.exp(-0.04354 * win_drop) - 3.1668
    return min(100.0, max(0.0, value))


def _window_size(n_plies: int) -> int:
    """Half-width (in plies either side) of the local window used to judge
    how "sharp"/volatile a position was, mirroring Lichess's own sizing.
    """
    return max(2, min(8, 2 + n_plies // 10))


def _stdev(values: list) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _game_accuracy(win_percent_by_ply: dict, own_move_accuracy: list) -> float:
    """Combine per-move accuracy into one game score the way Lichess does:
    the average of a volatility-weighted mean and the harmonic mean.

    A plain average lets a handful of forced/theory 100% moves paper over
    real blunders elsewhere, and treats a blunder in an already-decided
    position (win% barely moves either way) the same as one that actually
    swings the game. Weighting each move by how volatile the position was
    around it, then also folding in the harmonic mean (which is dragged
    down hard by any low value), fixes both: a move played while the
    result was already settled gets a small weight, and a real blunder
    can't be diluted away by easy moves.
    """
    if not own_move_accuracy:
        return None
    plies_sorted = sorted(win_percent_by_ply)
    n = len(plies_sorted)
    window = _window_size(n)
    values_by_index = [win_percent_by_ply[p] for p in plies_sorted]
    index_of_ply = {p: i for i, p in enumerate(plies_sorted)}

    weights = []
    accuracies = []
    for ply, move_acc in own_move_accuracy:
        idx = index_of_ply[ply]
        lo = max(0, idx - window)
        hi = min(n, idx + window + 1)
        weight = min(12.0, max(0.5, _stdev(values_by_index[lo:hi])))
        weights.append(weight)
        accuracies.append(move_acc)

    weighted_mean = sum(a * w for a, w in zip(accuracies, weights)) / sum(weights)
    safe_accuracies = [max(a, 1.0) for a in accuracies]  # keep harmonic mean finite
    harmonic_mean = len(safe_accuracies) / sum(1.0 / a for a in safe_accuracies)
    return (weighted_mean + harmonic_mean) / 2


def per_game_accuracy(conn: sqlite3.Connection, username: str) -> pd.DataFrame:
    """Accuracy score per game, based on the player's own moves.

    Needs every move of the game (not just the player's own) to judge how
    volatile the position was at each point -- that context is what lets
    _game_accuracy weight moves properly instead of a flat average.
    """
    query = """
        SELECT g.id AS game_id, g.played_at, g.opponent_username, g.result,
               g.time_class, g.url, g.color AS player_color,
               m.ply, m.color AS mover_color, m.cp_loss,
               m.eval_cp_before, m.eval_cp_after
        FROM games g
        JOIN moves m ON m.game_id = g.id
        WHERE g.username = ?
        ORDER BY g.id, m.ply
    """
    df = pd.read_sql_query(query, conn, params=(username,))
    if df.empty:
        return pd.DataFrame(columns=["game_id", "played_at", "opponent_username", "result",
                                      "time_class", "url", "acpl", "accuracy"])

    # eval_cp_after is stored from the mover's own POV; re-express it from
    # the analyzed player's POV so the whole game's win% series is on one
    # consistent scale, regardless of whose move produced each value.
    same_side = df["mover_color"] == df["player_color"]
    df["eval_player_pov"] = df["eval_cp_after"].where(same_side, -df["eval_cp_after"])
    df["win_percent_player_pov"] = df["eval_player_pov"].apply(_win_percent)

    own = df[same_side].copy()
    own["move_accuracy"] = [
        _move_accuracy(_win_percent(before), _win_percent(after))
        for before, after in zip(own["eval_cp_before"], own["eval_cp_after"])
    ]

    rows = []
    for game_id, game_df in df.groupby("game_id"):
        win_percent_by_ply = dict(zip(game_df["ply"], game_df["win_percent_player_pov"]))
        own_game_df = own[own["game_id"] == game_id]
        if own_game_df.empty:
            continue
        own_move_accuracy = list(zip(own_game_df["ply"], own_game_df["move_accuracy"]))
        meta = game_df.iloc[0]
        rows.append({
            "game_id": game_id,
            "played_at": meta["played_at"],
            "opponent_username": meta["opponent_username"],
            "result": meta["result"],
            "time_class": meta["time_class"],
            "url": meta["url"],
            "acpl": round(own_game_df["cp_loss"].mean(), 1),
            "accuracy": round(_game_accuracy(win_percent_by_ply, own_move_accuracy), 2),
        })

    grouped = pd.DataFrame(rows)
    grouped["played_at"] = pd.to_datetime(grouped["played_at"], errors="coerce")
    return grouped.sort_values("played_at").reset_index(drop=True)


def accuracy_trend(df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """Add a rolling-average accuracy column to a per_game_accuracy() result."""
    if df.empty:
        out = df.copy()
        out["accuracy_rolling"] = pd.Series(dtype=float)
        return out
    out = df.sort_values("played_at").reset_index(drop=True).copy()
    out["accuracy_rolling"] = out["accuracy"].rolling(window=window, min_periods=1).mean().round(2)
    return out
