from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from radar.db import connect, init_db

DEFAULT_DB_PATH = "data/radar.db"
REPORTS_DIR = Path("reports")
SETUP_COMMANDS = [
    "python -m radar.cli ingest-arxiv --config config.example.yaml --db data/radar.db",
    "python -m radar.cli ingest-github --config config.example.yaml --db data/radar.db",
    "python -m radar.cli tag-papers --config config.example.yaml --db data/radar.db",
    "python -m radar.cli score --config config.example.yaml --db data/radar.db",
    "python -m radar.cli digest --config config.example.yaml --db data/radar.db --date today",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.getenv("RADAR_DB_PATH", DEFAULT_DB_PATH))
    args, _ = parser.parse_known_args()
    return args


def main() -> None:
    args = parse_args()
    st.set_page_config(page_title="AI Infra Radar", layout="wide")
    st.title("AI Infra Radar")

    with st.sidebar:
        db_path = st.text_input("DB path", value=args.db)
        page = st.selectbox(
            "Page",
            ["Overview", "Papers", "Repositories", "Daily Digest"],
        )
        topic_filter = st.selectbox("Topic tag", _topic_options(db_path))
        keyword = st.text_input("Keyword search")
        author = st.text_input("Author search")
        min_score = st.slider("Min score", 0.0, 1.0, 0.0, 0.01)

    db_file = Path(db_path)
    if not db_file.is_file():
        _render_setup(db_path)
        return

    try:
        conn = connect(db_path)
        init_db(conn)
        conn.close()
    except sqlite3.Error as exc:
        st.error(f"Could not open SQLite database: {exc}")
        _render_setup(db_path)
        return

    papers = _filter_papers(load_papers(db_path), topic_filter, keyword, author, min_score)
    repos = load_repositories(db_path)

    if page == "Overview":
        _render_overview(db_path, papers, repos)
    elif page == "Papers":
        _render_papers(papers)
    elif page == "Repositories":
        _render_repositories(repos)
    else:
        _render_daily_digest()


@st.cache_data(show_spinner=False)
def load_kpis(db_path: str) -> dict[str, int]:
    with sqlite3.connect(db_path) as conn:
        return {
            "papers": _single_int(conn, "SELECT COUNT(*) FROM papers"),
            "repos": _single_int(conn, "SELECT COUNT(*) FROM repos"),
            "tagged": _single_int(conn, "SELECT COUNT(DISTINCT paper_id) FROM paper_tags"),
            "scored": _single_int(conn, "SELECT COUNT(DISTINCT paper_id) FROM daily_scores"),
        }


@st.cache_data(show_spinner=False)
def load_papers(db_path: str) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(
            """
            SELECT
                p.id,
                p.title,
                p.abstract,
                p.authors,
                p.published_at,
                p.url,
                COALESCE(tags.tags, '') AS tags,
                COALESCE(scores.score, 0) AS score,
                COALESCE(scores.components_json, '') AS components_json
            FROM papers p
            LEFT JOIN (
                SELECT paper_id, GROUP_CONCAT(tag, ', ') AS tags
                FROM paper_tags
                GROUP BY paper_id
            ) tags ON tags.paper_id = p.id
            LEFT JOIN (
                SELECT ds.paper_id, ds.score, ds.components_json
                FROM daily_scores ds
                JOIN (
                    SELECT paper_id, MAX(score_date) AS score_date
                    FROM daily_scores
                    GROUP BY paper_id
                ) latest
                  ON latest.paper_id = ds.paper_id
                 AND latest.score_date = ds.score_date
            ) scores ON scores.paper_id = p.id
            ORDER BY score DESC, published_at DESC
            """,
            conn,
        )
    if df.empty:
        return df
    df["authors"] = df["authors"].apply(_format_authors)
    df["score"] = df["score"].fillna(0.0).astype(float)
    df["score_components"] = df["components_json"].apply(_format_components)
    return df


@st.cache_data(show_spinner=False)
def load_repositories(db_path: str) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT
                full_name,
                description,
                language,
                stars,
                forks,
                open_issues,
                pushed_at,
                url AS html_url
            FROM repos
            ORDER BY stars DESC, pushed_at DESC
            """,
            conn,
        )


@st.cache_data(show_spinner=False)
def load_topic_distribution(db_path: str) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT tag, COUNT(DISTINCT paper_id) AS papers
            FROM paper_tags
            GROUP BY tag
            ORDER BY papers DESC, tag
            """,
            conn,
        )


@st.cache_data(show_spinner=False)
def load_papers_by_date(db_path: str) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT date(published_at) AS published_date, COUNT(*) AS papers
            FROM papers
            WHERE published_at IS NOT NULL
            GROUP BY date(published_at)
            ORDER BY published_date
            """,
            conn,
        )


def _render_setup(db_path: str) -> None:
    st.info(f"Database not found: `{db_path}`")
    st.write("Run these commands to create and populate a local database:")
    st.code("\n".join(SETUP_COMMANDS), language="bash")


def _render_overview(db_path: str, papers: pd.DataFrame, repos: pd.DataFrame) -> None:
    st.info(
        "v0.1 note: metadata comes from public APIs; topic tags and scores are "
        "heuristic and rule-based. Scores are intended for exploration, not "
        "definitive paper ranking."
    )
    kpis = load_kpis(db_path)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Papers collected", kpis["papers"])
    col2.metric("Repos tracked", kpis["repos"])
    col3.metric("Tagged papers", kpis["tagged"])
    col4.metric("Scored papers", kpis["scored"])

    left, right = st.columns(2)
    with left:
        st.subheader("Topic Distribution")
        topic_distribution = load_topic_distribution(db_path)
        if topic_distribution.empty:
            st.caption("No tags yet.")
        else:
            st.bar_chart(topic_distribution.set_index("tag"))
    with right:
        st.subheader("Collected Papers by Publication Date")
        st.caption("Reflects publication dates of currently collected papers.")
        papers_by_date = load_papers_by_date(db_path)
        if papers_by_date.empty:
            st.caption("No dated papers yet.")
        else:
            st.line_chart(papers_by_date.set_index("published_date"))

    st.subheader("Top Papers by Heuristic Score")
    _dataframe(
        papers[["title", "authors", "published_at", "tags", "score", "url"]].head(10),
        empty_message="No scored papers match the current filters.",
    )

    st.subheader("Fast-Moving Repositories")
    _dataframe(
        repos[
            [
                "full_name",
                "language",
                "stars",
                "forks",
                "open_issues",
                "pushed_at",
                "html_url",
            ]
        ].head(10),
        empty_message="No repositories ingested yet.",
    )


def _render_papers(papers: pd.DataFrame) -> None:
    st.subheader("Papers")
    columns = [
        "title",
        "authors",
        "published_at",
        "tags",
        "score",
        "score_components",
        "url",
    ]
    _dataframe(papers[columns], empty_message="No papers match the current filters.")


def _render_repositories(repos: pd.DataFrame) -> None:
    st.subheader("Repositories")
    _dataframe(repos, empty_message="No repositories ingested yet.")


def _render_daily_digest() -> None:
    st.subheader("Daily Digest")
    reports = sorted(REPORTS_DIR.glob("*.md"), reverse=True)
    if not reports:
        st.info("No digest report found.")
        st.code(
            "python -m radar.cli digest --config config.example.yaml "
            "--db data/radar.db --date today",
            language="bash",
        )
        return
    latest_report = reports[0]
    st.caption(str(latest_report))
    st.markdown(latest_report.read_text(encoding="utf-8"))


def _filter_papers(
    papers: pd.DataFrame,
    topic_filter: str,
    keyword: str,
    author: str,
    min_score: float,
) -> pd.DataFrame:
    if papers.empty:
        return papers
    filtered = papers[papers["score"] >= min_score].copy()
    if topic_filter != "All":
        filtered = filtered[
            filtered["tags"].apply(lambda value: topic_filter in _split_tags(value))
        ]
    if keyword:
        pattern = keyword.casefold()
        filtered = filtered[
            filtered["title"].str.casefold().str.contains(pattern, regex=False)
            | filtered["abstract"].str.casefold().str.contains(pattern, regex=False)
        ]
    if author:
        pattern = author.casefold()
        filtered = filtered[filtered["authors"].str.casefold().str.contains(pattern, regex=False)]
    return filtered.sort_values(["score", "published_at"], ascending=[False, False])


def _topic_options(db_path: str) -> list[str]:
    if not Path(db_path).exists():
        return ["All"]
    try:
        tags = load_topic_distribution(db_path)["tag"].tolist()
    except Exception:
        return ["All"]
    return ["All", *[str(tag) for tag in tags]]


def _dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.caption(empty_message)
        return
    st.dataframe(df, width="stretch", hide_index=True)


def _single_int(conn: sqlite3.Connection, query: str) -> int:
    row = conn.execute(query).fetchone()
    return int(row[0] or 0) if row else 0


def _format_authors(raw_authors: Any) -> str:
    if not isinstance(raw_authors, str) or not raw_authors:
        return ""
    try:
        authors = json.loads(raw_authors)
    except json.JSONDecodeError:
        return raw_authors
    return ", ".join(str(author) for author in authors)


def _format_components(raw_components: Any) -> str:
    if not isinstance(raw_components, str) or not raw_components:
        return ""
    try:
        components = json.loads(raw_components)
    except json.JSONDecodeError:
        return raw_components
    if not isinstance(components, dict):
        return ""
    return ", ".join(f"{key}: {value}" for key, value in components.items())


def _split_tags(value: str) -> list[str]:
    return [tag.strip() for tag in str(value).split(",") if tag.strip()]


if __name__ == "__main__":
    main()
