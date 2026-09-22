"""Streamlit dashboard for Chess Game Analyzer.

Run with: streamlit run dashboard.py
"""
import time

import pandas as pd
import plotly.express as px
import streamlit as st

from chess_analyzer.analysis import analyze_pending_games
from chess_analyzer.config import DB_PATH, ENGINE_DEPTH, STOCKFISH_PATH
from chess_analyzer.db import init_db
from chess_analyzer.fetch import fetch_games
from chess_analyzer.modules.accuracy import accuracy_trend, per_game_accuracy
from chess_analyzer.modules.blunders import (
    blunder_rate_by_phase,
    blunder_rate_by_time_pressure,
    top_worst_games,
)
from chess_analyzer.modules.openings import opening_stats
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

with st.sidebar.expander("Run Stockfish analysis"):
    stockfish_path = st.text_input("Stockfish binary path", value=STOCKFISH_PATH)
    depth = st.number_input("Search depth", min_value=4, max_value=30, value=ENGINE_DEPTH)
    pending_count = conn.execute(
        "SELECT COUNT(*) FROM games WHERE username = ? AND analyzed = 0", (username,)
    ).fetchone()[0] if username else 0
    if pending_count:
        st.caption(f"{pending_count} games pending analysis.")

    if st.button("Analyze pending games", disabled=pending_count == 0):
        progress_bar = st.progress(0.0)
        status = st.empty()
        start_time = time.monotonic()

        def _on_progress(done: int, total: int) -> None:
            progress_bar.progress(done / total)
            elapsed = time.monotonic() - start_time
            rate = elapsed / done if done else 0
            eta_s = int(rate * (total - done))
            status.text(f"{done}/{total} games analyzed — ETA ~{eta_s // 60}m {eta_s % 60}s")

        try:
            n = analyze_pending_games(conn=conn, stockfish_path=stockfish_path, depth=depth,
                                       progress_callback=_on_progress)
            status.empty()
            st.success(f"Analyzed {n} games.")
        except FileNotFoundError:
            st.error(f"Could not find Stockfish at '{stockfish_path}'.")

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

(
    tab_blunders, tab_accuracy, tab_worst_moves,
    tab_win_loss, tab_openings, tab_time,
) = st.tabs([
    "Blunder analysis", "Accuracy score", "Worst moves",
    "Win/Loss patterns", "Openings", "Time management",
])

with tab_blunders:
    st.subheader("Blunder rate by game phase")
    phase_df = blunder_rate_by_phase(conn, username)
    if phase_df.empty:
        st.info("No move data yet.")
    else:
        fig = px.bar(phase_df, x="phase", y="blunder_rate", text="blunder_rate",
                     labels={"phase": "Phase", "blunder_rate": "Blunder rate (%)"})
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(phase_df, use_container_width=True, hide_index=True)

    st.subheader("Blunder rate vs. time pressure")
    tp_df = blunder_rate_by_time_pressure(conn, username)
    if tp_df.empty:
        st.info("No clock data found in analyzed games (chess.com PGNs must include %clk).")
    else:
        fig = px.bar(tp_df, x="time_pressure", y="blunder_rate", text="blunder_rate",
                     labels={"time_pressure": "", "blunder_rate": "Blunder rate (%)"})
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top 5 worst games (by total centipawn loss)")
    worst_df = top_worst_games(conn, username, n=5)
    if worst_df.empty:
        st.info("No games analyzed yet.")
    else:
        st.dataframe(
            worst_df[["played_at", "opponent_username", "result", "total_cp_loss", "blunders", "url"]],
            use_container_width=True, hide_index=True,
        )

with tab_accuracy:
    st.subheader("Accuracy per game")
    acc_df = per_game_accuracy(conn, username)
    if acc_df.empty:
        st.info("No move data yet.")
    else:
        trend_df = accuracy_trend(acc_df)
        fig = px.line(trend_df, x="played_at", y=["accuracy", "accuracy_rolling"],
                       labels={"played_at": "Date", "value": "Accuracy (%)", "variable": ""})
        st.plotly_chart(fig, use_container_width=True)

        avg_acc = round(acc_df["accuracy"].mean(), 1)
        st.metric("Average accuracy", f"{avg_acc}%")
        st.dataframe(
            acc_df[["played_at", "opponent_username", "result", "time_class", "acpl", "accuracy", "url"]],
            use_container_width=True, hide_index=True,
        )

with tab_worst_moves:
    st.subheader("Your worst individual moves")
    st.caption("Concrete, reviewable mistakes — click through to the game and jump to the move number.")
    worst_moves_df = worst_moves(conn, username, n=25)
    if worst_moves_df.empty:
        st.info("No move data yet.")
    else:
        st.dataframe(
            worst_moves_df[["played_at", "opponent_username", "result", "move_number", "color",
                             "san", "cp_loss", "phase", "clock_seconds", "url"]],
            use_container_width=True, hide_index=True,
        )

with tab_win_loss:
    st.subheader("Win rate by color")
    color_df = win_rate_by_color(conn, username)
    if color_df.empty:
        st.info("No games yet.")
    else:
        fig = px.bar(color_df, x="color", y="win_rate", text="win_rate",
                     labels={"color": "Color", "win_rate": "Win rate (%)"})
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(color_df, use_container_width=True, hide_index=True)

    st.subheader("Win rate by time control")
    tc_df = win_rate_by_time_class(conn, username)
    if tc_df.empty:
        st.info("No games yet.")
    else:
        fig = px.bar(tc_df, x="time_class", y="win_rate", text="win_rate",
                     labels={"time_class": "Time control", "win_rate": "Win rate (%)"})
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(tc_df, use_container_width=True, hide_index=True)

    st.subheader("Win rate by opponent strength")
    strength_df = win_rate_by_opponent_strength(conn, username)
    if strength_df.empty:
        st.info("No rated games yet.")
    else:
        fig = px.bar(strength_df, x="bucket", y="win_rate", text="win_rate",
                     labels={"bucket": "Opponent vs. your rating", "win_rate": "Win rate (%)"})
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(strength_df, use_container_width=True, hide_index=True)

with tab_openings:
    st.subheader("Opening repertoire")
    openings_df = opening_stats(conn, username, min_games=2)
    if openings_df.empty:
        st.info("No openings played at least twice yet.")
    else:
        top_openings = openings_df.head(15)
        fig = px.bar(top_openings, x="opening_name", y="win_rate", text="win_rate",
                     hover_data=["games"],
                     labels={"opening_name": "Opening", "win_rate": "Win rate (%)"})
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        fig.update_xaxes(tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(openings_df, use_container_width=True, hide_index=True)

with tab_time:
    st.subheader("Average time spent per move, by game phase")
    time_df = time_by_phase(conn, username)
    if time_df.empty:
        st.info("No clock data in analyzed games with a live (non-daily) time control.")
    else:
        fig = px.bar(time_df, x="phase", y="avg_seconds_per_move", text="avg_seconds_per_move",
                     labels={"phase": "Phase", "avg_seconds_per_move": "Avg seconds/move"})
        fig.update_traces(texttemplate="%{text}s", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(time_df, use_container_width=True, hide_index=True)
