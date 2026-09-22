"""Streamlit dashboard for Chess Game Analyzer.

Run with: streamlit run dashboard.py
"""
import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from chess_analyzer.background import reconcile_stale_status, start_background_analysis
from chess_analyzer.config import DB_PATH, ENGINE_DEPTH, STOCKFISH_PATH
from chess_analyzer.db import get_analysis_status, init_db, request_cancel
from chess_analyzer.fetch import fetch_games
from chess_analyzer.modules.accuracy import accuracy_trend, per_game_accuracy
from chess_analyzer.modules.blunders import (
    blunder_rate_by_phase,
    blunder_rate_by_time_pressure,
    top_worst_games,
)
from chess_analyzer.modules.game_detail import game_moves, game_summary, games_for_selector
from chess_analyzer.modules.openings import opening_family_stats, opening_stats
from chess_analyzer.modules.rating import rating_progression
from chess_analyzer.modules.time_management import time_by_phase
from chess_analyzer.modules.win_loss import (
    win_rate_by_color,
    win_rate_by_opponent_strength,
    win_rate_by_time_class,
)
from chess_analyzer.modules.worst_moves import worst_moves

st.set_page_config(page_title="Chess Game Analyzer", layout="wide")

conn = init_db(DB_PATH)

st.sidebar.title("Chess Game Analyzer")
username = st.sidebar.text_input("chess.com username", value=st.session_state.get("username", ""))

with st.sidebar.expander("Fetch new games"):
    col1, col2 = st.columns(2)
    year = col1.number_input("Year (optional, 0 = all)", min_value=0, max_value=2100, value=0, step=1)
    month = col2.number_input("Month (optional)", min_value=0, max_value=12, value=0, step=1)
    if st.button("Fetch from chess.com", disabled=not username):
        with st.spinner("Fetching games..."):
            n = fetch_games(username, year or None, month or None, conn=conn)
        st.success(f"Inserted {n} new games.")

with st.sidebar.expander("Run Stockfish analysis", expanded=True):
    stockfish_path = st.text_input("Stockfish binary path", value=STOCKFISH_PATH)
    depth = st.number_input("Search depth", min_value=4, max_value=30, value=ENGINE_DEPTH)

    if reconcile_stale_status(conn):
        st.rerun()
    status_row = get_analysis_status(conn)

    if status_row["running"]:
        st_autorefresh(interval=3000, key="analysis_autorefresh")
        done, total = status_row["done"], status_row["total"]
        st.progress(done / total if total else 0.0)
        if status_row["started_at"] and done:
            started = datetime.datetime.fromisoformat(status_row["started_at"])
            elapsed = (datetime.datetime.utcnow() - started).total_seconds()
            eta_s = int(elapsed / done * (total - done))
            st.caption(f"{done}/{total} games analyzed — ETA ~{eta_s // 60}m {eta_s % 60}s")
        else:
            st.caption(f"{done}/{total} games analyzed — starting...")
        if st.button("Stop analysis"):
            request_cancel(conn)
            st.info("Stopping after the current game finishes...")
    else:
        if status_row["error"]:
            st.error(f"Last analysis run failed: {status_row['error']}")

        pending_count = conn.execute(
            "SELECT COUNT(*) FROM games WHERE username = ? AND analyzed = 0", (username,)
        ).fetchone()[0] if username else 0
        if pending_count:
            st.caption(f"{pending_count} games pending analysis.")

        if st.button("Analyze pending games", disabled=pending_count == 0):
            if start_background_analysis(stockfish_path=stockfish_path, depth=depth):
                st.rerun()
            else:
                st.warning("Could not start (already running, or nothing pending).")

if not username:
    st.info("Enter your chess.com username in the sidebar to get started.")
    st.stop()

game_count = conn.execute("SELECT COUNT(*) FROM games WHERE username = ?", (username,)).fetchone()[0]
analyzed_count = conn.execute(
    "SELECT COUNT(*) FROM games WHERE username = ? AND analyzed = 1", (username,)
).fetchone()[0]
st.caption(f"{game_count} games stored, {analyzed_count} analyzed for **{username}**.")

if game_count == 0:
    st.warning("No games stored yet. Fetch games from the sidebar.")
    st.stop()

SECTIONS = [
    "Rating", "Blunder analysis", "Accuracy score", "Worst moves",
    "Win/Loss patterns", "Openings", "Time management", "Game detail",
]
st.session_state.setdefault("active_section", SECTIONS[0])
st.session_state.setdefault("jump_game_id", None)
st.session_state.setdefault("jump_ply", None)

# A widget-bound session_state key (like "active_section" below) can't be
# reassigned after its widget has rendered in the same script run. So a
# jump only *requests* a section via this separate key; the request is
# applied here, before the radio widget is created, on the rerun it triggers.
if st.session_state.get("pending_section"):
    st.session_state["active_section"] = st.session_state.pop("pending_section")


def jump_to_game(game_id: int, ply: int | None = None) -> None:
    """Used by "→" buttons elsewhere to open a specific game (and
    optionally highlight one move) in the Game detail section.
    """
    st.session_state["jump_game_id"] = game_id
    st.session_state["jump_ply"] = ply
    st.session_state["pending_section"] = "Game detail"
    st.rerun()


active_section = st.radio("Section", SECTIONS, horizontal=True, key="active_section",
                           label_visibility="collapsed")

if active_section == "Rating":
    st.subheader("Rating over time")
    rating_df = rating_progression(conn, username)
    if rating_df.empty:
        st.info("No rated games yet.")
    else:
        fig = px.line(rating_df, x="played_at", y="my_rating", color="time_class",
                       markers=True, labels={"played_at": "Date", "my_rating": "Rating",
                                              "time_class": "Time control"})
        st.plotly_chart(fig, width="stretch")

        latest = rating_df.sort_values("played_at").groupby("time_class").tail(1)
        cols = st.columns(len(latest)) if len(latest) else [st]
        for col, (_, row) in zip(cols, latest.iterrows()):
            col.metric(f"Current {row['time_class']}", int(row["my_rating"]))

elif active_section == "Blunder analysis":
    st.subheader("Blunder rate by game phase")
    phase_df = blunder_rate_by_phase(conn, username)
    if phase_df.empty:
        st.info("No move data yet.")
    else:
        fig = px.bar(phase_df, x="phase", y="blunder_rate", text="blunder_rate",
                     labels={"phase": "Phase", "blunder_rate": "Blunder rate (%)"})
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(phase_df, width="stretch", hide_index=True)

    st.subheader("Blunder rate vs. time pressure")
    tp_df = blunder_rate_by_time_pressure(conn, username)
    if tp_df.empty:
        st.info("No clock data found in analyzed games (chess.com PGNs must include %clk).")
    else:
        fig = px.bar(tp_df, x="time_pressure", y="blunder_rate", text="blunder_rate",
                     labels={"time_pressure": "", "blunder_rate": "Blunder rate (%)"})
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig, width="stretch")

    st.subheader("Top 5 worst games (by total centipawn loss)")
    worst_df = top_worst_games(conn, username, n=5)
    if worst_df.empty:
        st.info("No games analyzed yet.")
    else:
        header = st.columns([1.2, 1.5, 0.8, 1, 0.8, 0.6])
        for col, title in zip(header, ["Date", "Opponent", "Result", "CP lost", "Blunders", ""]):
            col.markdown(f"**{title}**")
        for _, row in worst_df.iterrows():
            c = st.columns([1.2, 1.5, 0.8, 1, 0.8, 0.6])
            c[0].write(row["played_at"])
            c[1].write(row["opponent_username"])
            c[2].write(row["result"])
            c[3].write(int(row["total_cp_loss"]))
            c[4].write(int(row["blunders"]))
            if c[5].button("→", key=f"jump_worstgame_{row['game_id']}"):
                jump_to_game(int(row["game_id"]))

elif active_section == "Accuracy score":
    st.subheader("Accuracy per game")
    acc_df = per_game_accuracy(conn, username)
    if acc_df.empty:
        st.info("No move data yet.")
    else:
        trend_df = accuracy_trend(acc_df)
        fig = px.line(trend_df, x="played_at", y=["accuracy", "accuracy_rolling"],
                       labels={"played_at": "Date", "value": "Accuracy (%)", "variable": ""})
        st.plotly_chart(fig, width="stretch")

        avg_acc = round(acc_df["accuracy"].mean(), 1)
        st.metric("Average accuracy", f"{avg_acc}%")

        header = st.columns([1.2, 1.5, 0.8, 0.9, 0.8, 0.8, 0.6])
        for col, title in zip(header, ["Date", "Opponent", "Result", "Time class", "ACPL", "Accuracy", ""]):
            col.markdown(f"**{title}**")
        for _, row in acc_df.iterrows():
            c = st.columns([1.2, 1.5, 0.8, 0.9, 0.8, 0.8, 0.6])
            c[0].write(row["played_at"].date() if pd.notna(row["played_at"]) else "?")
            c[1].write(row["opponent_username"])
            c[2].write(row["result"])
            c[3].write(row["time_class"])
            c[4].write(row["acpl"])
            c[5].write(f"{row['accuracy']}%")
            if c[6].button("→", key=f"jump_acc_{row['game_id']}"):
                jump_to_game(int(row["game_id"]))

elif active_section == "Worst moves":
    st.subheader("Your worst individual moves")
    st.caption("Concrete, reviewable mistakes — hit → to open the game at that exact move.")
    worst_moves_df = worst_moves(conn, username, n=25)
    if worst_moves_df.empty:
        st.info("No move data yet.")
    else:
        widths = [1.2, 1.4, 0.8, 0.9, 0.7, 0.8, 0.8, 1, 0.9, 0.6]
        header = st.columns(widths)
        for col, title in zip(header, ["Date", "Opponent", "Result", "Move #", "Color", "Move",
                                        "CP lost", "Phase", "Clock", ""]):
            col.markdown(f"**{title}**")
        for _, row in worst_moves_df.iterrows():
            c = st.columns(widths)
            c[0].write(row["played_at"])
            c[1].write(row["opponent_username"])
            c[2].write(row["result"])
            c[3].write(int(row["move_number"]))
            c[4].write(row["color"])
            c[5].write(row["san"])
            c[6].write(int(row["cp_loss"]))
            c[7].write(row["phase"])
            c[8].write(row["clock_seconds"])
            if c[9].button("→", key=f"jump_wmove_{row['game_id']}_{row['ply']}"):
                jump_to_game(int(row["game_id"]), int(row["ply"]))

elif active_section == "Win/Loss patterns":
    st.subheader("Win rate by color")
    color_df = win_rate_by_color(conn, username)
    if color_df.empty:
        st.info("No games yet.")
    else:
        fig = px.bar(color_df, x="color", y="win_rate", text="win_rate",
                     labels={"color": "Color", "win_rate": "Win rate (%)"})
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(color_df, width="stretch", hide_index=True)

    st.subheader("Win rate by time control")
    tc_df = win_rate_by_time_class(conn, username)
    if tc_df.empty:
        st.info("No games yet.")
    else:
        fig = px.bar(tc_df, x="time_class", y="win_rate", text="win_rate",
                     labels={"time_class": "Time control", "win_rate": "Win rate (%)"})
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(tc_df, width="stretch", hide_index=True)

    st.subheader("Win rate by opponent strength")
    strength_df = win_rate_by_opponent_strength(conn, username)
    if strength_df.empty:
        st.info("No rated games yet.")
    else:
        fig = px.bar(strength_df, x="bucket", y="win_rate", text="win_rate",
                     labels={"bucket": "Opponent vs. your rating", "win_rate": "Win rate (%)"})
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(strength_df, width="stretch", hide_index=True)

elif active_section == "Openings":
    st.subheader("Opening repertoire, by family")
    family_df = opening_family_stats(conn, username, min_games=2)
    variations_df = opening_stats(conn, username, min_games=1)
    if family_df.empty:
        st.info("No openings played at least twice yet.")
    else:
        top_families = family_df.head(15)
        fig = px.bar(top_families, x="family", y="win_rate", text="win_rate",
                     hover_data=["games"],
                     labels={"family": "Opening family", "win_rate": "Win rate (%)"})
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        fig.update_xaxes(tickangle=-30)
        st.plotly_chart(fig, width="stretch")

        for _, fam_row in family_df.iterrows():
            variations = variations_df[variations_df["family"] == fam_row["family"]]
            with st.expander(
                f"{fam_row['family']} — {fam_row['games']} games, {fam_row['win_rate']}% win rate"
            ):
                st.dataframe(
                    variations[["opening_name", "opening_eco", "games", "wins", "draws",
                                "losses", "win_rate"]],
                    width="stretch", hide_index=True,
                )

elif active_section == "Time management":
    st.subheader("Average time spent per move, by game phase")
    time_df = time_by_phase(conn, username)
    if time_df.empty:
        st.info("No clock data in analyzed games with a live (non-daily) time control.")
    else:
        fig = px.bar(time_df, x="phase", y="avg_seconds_per_move", text="avg_seconds_per_move",
                     labels={"phase": "Phase", "avg_seconds_per_move": "Avg seconds/move"})
        fig.update_traces(texttemplate="%{text}s", textposition="outside")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(time_df, width="stretch", hide_index=True)

elif active_section == "Game detail":
    st.subheader("Per-game review")
    st.caption("The eval curve and full move list for one game, so you can see exactly where it turned.")
    games_df = games_for_selector(conn, username)
    if games_df.empty:
        st.info("No analyzed games yet.")
    else:
        def _label(row):
            date = row["played_at"] or "?"
            return f"{date} vs {row['opponent_username']} ({row['result']}, {row['color']}, {row['time_class']})"

        labels = games_df.apply(_label, axis=1)
        jump_game_id = st.session_state.get("jump_game_id")
        default_index = 0
        if jump_game_id is not None:
            matches = games_df.index[games_df["id"] == jump_game_id]
            if len(matches):
                default_index = int(matches[0])

        choice = st.selectbox("Pick a game", options=labels.index, index=default_index,
                               format_func=lambda i: labels[i])
        game_id = int(games_df.loc[choice, "id"])
        jump_ply = st.session_state.get("jump_ply") if game_id == jump_game_id else None

        summary = game_summary(conn, game_id)
        cols = st.columns(4)
        cols[0].metric("Result", summary.get("result", "?"))
        cols[1].metric("Color", summary.get("color", "?"))
        cols[2].metric("Opponent", f"{summary.get('opponent_username', '?')} ({summary.get('opponent_rating', '?')})")
        cols[3].metric("Opening", summary.get("opening_name") or "?")
        if summary.get("url"):
            st.markdown(f"[Open on chess.com]({summary['url']})")

        moves_df = game_moves(conn, game_id)
        if moves_df.empty:
            st.info("No move data for this game.")
        else:
            if jump_ply is not None:
                jumped = moves_df[moves_df["ply"] == jump_ply]
                if not jumped.empty:
                    m = jumped.iloc[0]
                    st.info(f"Jumped to move {m['move_number']} ({m['color']}): "
                            f"**{m['san']}** — {m['cp_loss']} cp lost")

            fig = px.line(moves_df, x="ply", y="eval_white_pov", markers=True,
                          labels={"ply": "Ply", "eval_white_pov": "Eval (White POV, cp)"})
            fig.add_hline(y=0, line_dash="dot", line_color="gray")
            blunder_rows = moves_df[moves_df["classification"] == "blunder"]
            if not blunder_rows.empty:
                fig.add_scatter(x=blunder_rows["ply"], y=blunder_rows["eval_white_pov"], mode="markers",
                                marker=dict(color="red", size=12, symbol="x"), name="Blunder")
            if jump_ply is not None:
                fig.add_vline(x=jump_ply, line_dash="dash", line_color="blue")
            st.plotly_chart(fig, width="stretch")

            display_cols = ["ply", "move_number", "color", "san", "flag", "cp_loss",
                             "classification", "phase", "clock_seconds"]
            styler = moves_df[display_cols].style
            if jump_ply is not None:
                styler = styler.apply(
                    lambda r: ["background-color: #fff3b0" if r["ply"] == jump_ply else ""
                               for _ in r], axis=1,
                )
            st.dataframe(styler, width="stretch", hide_index=True)
