from __future__ import annotations

import argparse

import pandas as pd
import streamlit as st

from radar.config import load_config
from radar.db import connect, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    conn = connect(cfg.database_path)
    init_db(conn)

    st.set_page_config(page_title="AI Infra Radar", layout="wide")
    st.title("AI Infra Radar")

    scores = pd.read_sql_query(
        "SELECT * FROM daily_scores ORDER BY score_date DESC, score DESC",
        conn,
    )
    papers = pd.read_sql_query(
        "SELECT title, published_at, url FROM papers ORDER BY published_at DESC LIMIT 50", conn
    )
    repos = pd.read_sql_query(
        "SELECT full_name, stars, language, url FROM repos ORDER BY stars DESC LIMIT 50", conn
    )

    st.subheader("Trend Scores")
    st.dataframe(scores, use_container_width=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Recent Papers")
        st.dataframe(papers, use_container_width=True)
    with right:
        st.subheader("Notable Repositories")
        st.dataframe(repos, use_container_width=True)

    conn.close()


if __name__ == "__main__":
    main()
