"""Streamlit dashboard for Chess Game Analyzer.

Run with: streamlit run dashboard.py
"""
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

st.set_page_config(page_title="Chess Game Analyzer", layout="wide")

conn = init_db(DB_PATH)

st.sidebar.title("Chess Game Analyzer")
username = st.sidebar.text_input("chess.com username", value=st.session_state.get("username", ""))

with st.sidebar.expander("Fetch new games"):
    col1, col2 = st.columns(2)
    year = col1.number_input("Year (optional)", min_value=2007, max_value=2100, value=0, step=1)
    month = col2.number_input("Month (optional)", min_value=0, max_value=12, value=0, step=1)
    if st.button("Fetch from chess.com", disabled=not username):
        with st.spinner("Fetching games..."):
            n = fetch_games(username, year or None, month or None, conn=conn)
        st.success(f"Inserted {n} new games.")

with st.sidebar.expander("Run Stockfish analysis"):
    stockfish_path = st.text_input("Stockfish binary path", value=STOCKFISH_PATH)
    depth = st.number_input("Search depth", min_value=4, max_value=30, value=ENGINE_DEPTH)
    if st.button("Analyze pending games"):
        with st.spinner("Running Stockfish over unanalyzed games... this can take a while."):
            try:
                n = analyze_pending_games(conn=conn, stockfish_path=stockfish_path, depth=depth)
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

if analyzed_count == 0:
    st.warning("No analyzed games yet. Fetch games and run Stockfish analysis from the sidebar.")
    st.stop()

tab_blunders, tab_accuracy = st.tabs(["Blunder analysis", "Accuracy score"])

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
