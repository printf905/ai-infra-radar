from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from radar.db import insert_digest
from radar.models import DigestRecord


def write_digest(
    conn: sqlite3.Connection,
    reports_dir: Path | str,
    digest_date: date | None = None,
) -> Path:
    report_date = digest_date or datetime.now(UTC).date()
    out_dir = Path(reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report_date.isoformat()}.md"

    lines = [
        f"# AI Infra Radar Digest - {report_date.isoformat()}",
        "",
        "## Top Papers",
        "",
    ]
    lines.extend(_top_paper_lines(conn, report_date))
    lines.extend(["", "## Fast-Moving Repositories", ""])
    lines.extend(_repository_lines(conn))
    lines.extend(["", "## Topic Trends", ""])
    lines.extend(_topic_trend_lines(conn, report_date))
    lines.extend(["", "## Anomalies", "", "Placeholder for v0.1."])

    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    insert_digest(
        conn,
        DigestRecord(
            digest_date=report_date,
            path=str(path),
            title=f"AI Infra Radar Digest - {report_date.isoformat()}",
            content=content,
        ),
    )
    return path


def _top_paper_lines(conn: sqlite3.Connection, report_date: date) -> list[str]:
    rows = conn.execute(
        """
        SELECT
            p.id,
            p.title,
            p.abstract,
            p.authors,
            p.published_at,
            p.url,
            ds.score
        FROM daily_scores ds
        JOIN papers p ON p.id = ds.paper_id
        WHERE ds.score_date = ?
        ORDER BY ds.score DESC
        LIMIT 10
        """,
        (report_date.isoformat(),),
    ).fetchall()
    if not rows:
        return ["No scored papers yet."]

    lines: list[str] = []
    for row in rows:
        tags = _paper_tags(conn, int(row["id"]))
        matched_repo = _matched_repo(conn, int(row["id"]))
        lines.extend(
            [
                f"### {row['title']}",
                "",
                f"- Authors: {_authors(row['authors'])}",
                f"- Published: {_published_date(row['published_at'])}",
                f"- Tags: {', '.join(tags) if tags else 'No tags yet'}",
                f"- Score: {row['score']}",
                f"- Summary: {_abstract_summary(row['abstract'])}",
                f"- arXiv: {row['url']}",
                f"- Matched GitHub repo: {matched_repo}",
                "",
            ]
        )
    return lines


def _repository_lines(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT full_name, stars, forks, pushed_at, url
        FROM repos
        ORDER BY pushed_at DESC, stars DESC
        LIMIT 10
        """
    ).fetchall()
    if not rows:
        return ["No repositories ingested yet."]
    return [
        "- "
        f"{row['full_name']} | stars: {row['stars']} | forks: {row['forks']} | "
        f"pushed_at: {row['pushed_at'] or 'unknown'} | {row['url']}"
        for row in rows
    ]


def _topic_trend_lines(conn: sqlite3.Connection, report_date: date) -> list[str]:
    start_date = report_date - timedelta(days=6)
    rows = conn.execute(
        """
        SELECT pt.tag, COUNT(DISTINCT p.id) AS paper_count
        FROM paper_tags pt
        JOIN papers p ON p.id = pt.paper_id
        WHERE p.published_at IS NOT NULL
          AND date(p.published_at) BETWEEN date(?) AND date(?)
        GROUP BY pt.tag
        ORDER BY paper_count DESC, pt.tag
        """,
        (start_date.isoformat(), report_date.isoformat()),
    ).fetchall()
    if not rows:
        return ["No tagged papers published in the last 7 days."]
    return [f"- {row['tag']}: {row['paper_count']} papers" for row in rows]


def _paper_tags(conn: sqlite3.Connection, paper_id: int) -> list[str]:
    return [
        str(row["tag"])
        for row in conn.execute(
            "SELECT tag FROM paper_tags WHERE paper_id = ? ORDER BY tag",
            (paper_id,),
        )
    ]


def _matched_repo(conn: sqlite3.Connection, paper_id: int) -> str:
    row = conn.execute(
        """
        SELECT r.full_name, r.url
        FROM paper_repo_matches m
        JOIN repos r ON r.id = m.repo_id
        WHERE m.paper_id = ?
        ORDER BY m.score DESC
        LIMIT 1
        """,
        (paper_id,),
    ).fetchone()
    if row is None:
        return "No matched repo yet"
    return f"{row['full_name']} ({row['url']})"


def _authors(raw_authors: object) -> str:
    if not isinstance(raw_authors, str) or not raw_authors:
        return "Unknown"
    try:
        authors = json.loads(raw_authors)
    except json.JSONDecodeError:
        return raw_authors
    if not authors:
        return "Unknown"
    return ", ".join(str(author) for author in authors)


def _published_date(raw_published_at: object) -> str:
    if not isinstance(raw_published_at, str) or not raw_published_at:
        return "Unknown"
    return raw_published_at[:10]


def _abstract_summary(raw_abstract: object) -> str:
    if not isinstance(raw_abstract, str) or not raw_abstract.strip():
        return "No abstract available."
    sentences = re.split(r"(?<=[.!?])\s+", " ".join(raw_abstract.split()))
    return " ".join(sentences[:2])
