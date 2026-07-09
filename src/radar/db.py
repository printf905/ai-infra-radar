from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any

from radar.models import (
    DailyScore,
    DigestRecord,
    Match,
    Paper,
    Repo,
    RepoSnapshot,
    TrendScore,
)


def connect(database_path: Path | str) -> sqlite3.Connection:
    raw_path = str(database_path)
    if raw_path != ":memory:":
        Path(raw_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(raw_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    schema = files("radar").joinpath("schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()


def upsert_paper(conn: sqlite3.Connection, paper: Paper) -> int:
    conn.execute(
        """
        INSERT INTO papers
            (
                arxiv_id,
                title,
                abstract,
                authors,
                primary_category,
                categories,
                published_at,
                updated_at,
                url,
                pdf_url
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(arxiv_id) DO UPDATE SET
            title = excluded.title,
            abstract = excluded.abstract,
            authors = excluded.authors,
            primary_category = excluded.primary_category,
            categories = excluded.categories,
            published_at = excluded.published_at,
            updated_at = excluded.updated_at,
            url = excluded.url,
            pdf_url = excluded.pdf_url,
            ingested_at = CURRENT_TIMESTAMP
        """,
        (
            paper.arxiv_id,
            paper.title,
            paper.abstract,
            json.dumps(paper.authors),
            paper.primary_category,
            json.dumps(paper.categories),
            _iso(paper.published_at),
            _iso(paper.updated_at),
            str(paper.url),
            str(paper.pdf_url) if paper.pdf_url else None,
        ),
    )
    conn.commit()
    return _required_id(conn, "SELECT id FROM papers WHERE arxiv_id = ?", (paper.arxiv_id,))


def upsert_papers(conn: sqlite3.Connection, papers: Iterable[Paper]) -> int:
    rows = list(papers)
    for paper in rows:
        upsert_paper(conn, paper)
    return len(rows)


def upsert_repo(conn: sqlite3.Connection, repo: Repo) -> int:
    conn.execute(
        """
        INSERT INTO repos
            (
                github_id,
                full_name,
                description,
                url,
                stars,
                forks,
                open_issues,
                language,
                created_at,
                updated_at,
                pushed_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(github_id) DO UPDATE SET
            full_name = excluded.full_name,
            description = excluded.description,
            url = excluded.url,
            stars = excluded.stars,
            forks = excluded.forks,
            open_issues = excluded.open_issues,
            language = excluded.language,
            created_at = excluded.created_at,
            updated_at = excluded.updated_at,
            pushed_at = excluded.pushed_at,
            ingested_at = CURRENT_TIMESTAMP
        """,
        (
            repo.github_id,
            repo.full_name,
            repo.description,
            str(repo.url),
            repo.stars,
            repo.forks,
            repo.open_issues,
            repo.language,
            _iso(repo.created_at),
            _iso(repo.updated_at),
            _iso(repo.pushed_at),
        ),
    )
    conn.commit()
    return _required_id(conn, "SELECT id FROM repos WHERE github_id = ?", (repo.github_id,))


def upsert_repos(conn: sqlite3.Connection, repos: Iterable[Repo]) -> int:
    rows = list(repos)
    for repo in rows:
        upsert_repo(conn, repo)
    return len(rows)


def insert_repo_snapshot(conn: sqlite3.Connection, snapshot: RepoSnapshot) -> int:
    conn.execute(
        """
        INSERT INTO repo_snapshots
            (repo_id, captured_at, stars, forks, open_issues, pushed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(repo_id, captured_at) DO UPDATE SET
            stars = excluded.stars,
            forks = excluded.forks,
            open_issues = excluded.open_issues,
            pushed_at = excluded.pushed_at
        """,
        (
            snapshot.repo_id,
            snapshot.captured_at.isoformat(),
            snapshot.stars,
            snapshot.forks,
            snapshot.open_issues,
            _iso(snapshot.pushed_at),
        ),
    )
    conn.commit()
    return _required_id(
        conn,
        "SELECT id FROM repo_snapshots WHERE repo_id = ? AND captured_at = ?",
        (snapshot.repo_id, snapshot.captured_at.isoformat()),
    )


def insert_paper_tags(
    conn: sqlite3.Connection,
    paper_id: int,
    tags: Iterable[str],
    source: str = "rules",
) -> int:
    inserted = 0
    for tag in sorted({tag.strip() for tag in tags if tag.strip()}):
        cursor = conn.execute(
            """
            INSERT INTO paper_tags (paper_id, tag, source)
            VALUES (?, ?, ?)
            ON CONFLICT(paper_id, tag, source) DO NOTHING
            """,
            (paper_id, tag, source),
        )
        inserted += max(cursor.rowcount, 0)
    conn.commit()
    return inserted


def replace_paper_tags(
    conn: sqlite3.Connection,
    paper_id: int,
    tags: Iterable[str],
    source: str = "rules",
) -> int:
    conn.execute("DELETE FROM paper_tags WHERE paper_id = ? AND source = ?", (paper_id, source))
    return insert_paper_tags(conn, paper_id, tags, source)


def insert_daily_score(conn: sqlite3.Connection, score: DailyScore) -> int:
    conn.execute(
        """
        INSERT INTO daily_scores
            (score_date, tag, score, paper_count, repo_count, match_count, star_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(score_date, tag) DO UPDATE SET
            score = excluded.score,
            paper_count = excluded.paper_count,
            repo_count = excluded.repo_count,
            match_count = excluded.match_count,
            star_count = excluded.star_count
        """,
        (
            score.score_date.isoformat(),
            score.tag,
            score.score,
            score.paper_count,
            score.repo_count,
            score.match_count,
            score.star_count,
        ),
    )
    conn.commit()
    return _required_id(
        conn,
        "SELECT id FROM daily_scores WHERE score_date = ? AND tag = ?",
        (score.score_date.isoformat(), score.tag),
    )


def insert_digest(conn: sqlite3.Connection, digest: DigestRecord) -> int:
    conn.execute(
        """
        INSERT INTO digests (digest_date, path, title, content)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(digest_date, path) DO UPDATE SET
            title = excluded.title,
            content = excluded.content
        """,
        (digest.digest_date.isoformat(), digest.path, digest.title, digest.content),
    )
    conn.commit()
    return _required_id(
        conn,
        "SELECT id FROM digests WHERE digest_date = ? AND path = ?",
        (digest.digest_date.isoformat(), digest.path),
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
    today = date.today()
    rows = list(scores)
    conn.execute("DELETE FROM daily_scores WHERE score_date = ?", (today.isoformat(),))
    for score in rows:
        insert_daily_score(
            conn,
            DailyScore(
                score_date=today,
                tag=score.tag,
                score=score.score,
                paper_count=score.paper_count,
                repo_count=score.repo_count,
                match_count=score.match_count,
                star_count=score.star_count,
            ),
        )
    conn.commit()
    return len(rows)


def fetch_all(
    conn: sqlite3.Connection,
    query: str,
    params: tuple[Any, ...] = (),
) -> list[sqlite3.Row]:
    return list(conn.execute(query, params).fetchall())


def _required_id(conn: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> int:
    row = conn.execute(query, params).fetchone()
    if row is None:
        raise RuntimeError(f"Expected row not found for query: {query}")
    return int(row["id"])


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None
