from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from importlib.resources import files
from pathlib import Path
from typing import Any

from radar.models import Match, Paper, Repo, TrendScore


def connect(database_path: Path | str) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    schema = files("radar").joinpath("schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()


def upsert_papers(conn: sqlite3.Connection, papers: Iterable[Paper]) -> int:
    rows = list(papers)
    conn.executemany(
        """
        INSERT INTO papers (arxiv_id, title, abstract, authors, published_at, updated_at, url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(arxiv_id) DO UPDATE SET
            title = excluded.title,
            abstract = excluded.abstract,
            authors = excluded.authors,
            published_at = excluded.published_at,
            updated_at = excluded.updated_at,
            url = excluded.url,
            ingested_at = CURRENT_TIMESTAMP
        """,
        [
            (
                paper.arxiv_id,
                paper.title,
                paper.abstract,
                json.dumps(paper.authors),
                _iso(paper.published_at),
                _iso(paper.updated_at),
                str(paper.url),
            )
            for paper in rows
        ],
    )
    conn.commit()
    return len(rows)


def upsert_repos(conn: sqlite3.Connection, repos: Iterable[Repo]) -> int:
    rows = list(repos)
    conn.executemany(
        """
        INSERT INTO repos
            (github_id, full_name, description, url, stars, forks, language, pushed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(github_id) DO UPDATE SET
            full_name = excluded.full_name,
            description = excluded.description,
            url = excluded.url,
            stars = excluded.stars,
            forks = excluded.forks,
            language = excluded.language,
            pushed_at = excluded.pushed_at,
            ingested_at = CURRENT_TIMESTAMP
        """,
        [
            (
                repo.github_id,
                repo.full_name,
                repo.description,
                str(repo.url),
                repo.stars,
                repo.forks,
                repo.language,
                _iso(repo.pushed_at),
            )
            for repo in rows
        ],
    )
    conn.commit()
    return len(rows)


def upsert_tag(conn: sqlite3.Connection, name: str) -> int:
    conn.execute("INSERT INTO tags (name) VALUES (?) ON CONFLICT(name) DO NOTHING", (name,))
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise RuntimeError(f"Could not create tag: {name}")
    return int(row["id"])


def replace_item_tags(
    conn: sqlite3.Connection,
    item_type: str,
    item_id: int,
    tags: Iterable[str],
) -> None:
    conn.execute("DELETE FROM item_tags WHERE item_type = ? AND item_id = ?", (item_type, item_id))
    for tag in sorted(set(tags)):
        tag_id = upsert_tag(conn, tag)
        conn.execute(
            """
            INSERT INTO item_tags (item_type, item_id, tag_id)
            VALUES (?, ?, ?)
            ON CONFLICT(item_type, item_id, tag_id) DO NOTHING
            """,
            (item_type, item_id, tag_id),
        )


def upsert_matches(conn: sqlite3.Connection, matches: Iterable[Match]) -> int:
    rows = list(matches)
    conn.executemany(
        """
        INSERT INTO paper_repo_matches (paper_id, repo_id, score, reason)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(paper_id, repo_id) DO UPDATE SET
            score = excluded.score,
            reason = excluded.reason,
            updated_at = CURRENT_TIMESTAMP
        """,
        [(match.paper_id, match.repo_id, match.score, match.reason) for match in rows],
    )
    conn.commit()
    return len(rows)


def replace_scores(conn: sqlite3.Connection, scores: Iterable[TrendScore]) -> int:
    rows = list(scores)
    conn.execute("DELETE FROM trend_scores")
    conn.executemany(
        """
        INSERT INTO trend_scores
            (tag, score, paper_count, repo_count, match_count, star_count)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                score.tag,
                score.score,
                score.paper_count,
                score.repo_count,
                score.match_count,
                score.star_count,
            )
            for score in rows
        ],
    )
    conn.commit()
    return len(rows)


def fetch_all(
    conn: sqlite3.Connection,
    query: str,
    params: tuple[Any, ...] = (),
) -> list[sqlite3.Row]:
    return list(conn.execute(query, params).fetchall())


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None
