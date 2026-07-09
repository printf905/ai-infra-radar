from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from radar.db import insert_digest
from radar.models import DigestRecord


def write_digest(conn: sqlite3.Connection, reports_dir: Path | str) -> Path:
    out_dir = Path(reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).date()
    path = out_dir / f"digest-{today.isoformat()}.md"

    scores = conn.execute(
        """
        SELECT tag, score, paper_count, repo_count, match_count, star_count
        FROM daily_scores
        WHERE score_date = ?
        ORDER BY score DESC
        LIMIT 20
        """,
        (today.isoformat(),),
    ).fetchall()
    papers = conn.execute(
        "SELECT title, url, published_at FROM papers ORDER BY published_at DESC LIMIT 10"
    ).fetchall()
    repos = conn.execute(
        "SELECT full_name, url, stars, language FROM repos ORDER BY stars DESC LIMIT 10"
    ).fetchall()

    lines = [f"# AI Infra Radar Digest - {today.isoformat()}", "", "## Top Trends", ""]
    if scores:
        for row in scores:
            lines.append(
                f"- **{row['tag']}**: score {row['score']} "
                f"({row['paper_count']} papers, {row['repo_count']} repos, "
                f"{row['match_count']} matches, {row['star_count']} stars)"
            )
    else:
        lines.append("- No scores computed yet.")

    lines.extend(["", "## Recent Papers", ""])
    lines.extend(f"- [{row['title']}]({row['url']})" for row in papers)
    if not papers:
        lines.append("- No papers ingested yet.")

    lines.extend(["", "## Notable Repositories", ""])
    lines.extend(
        f"- [{row['full_name']}]({row['url']}) - {row['stars']} stars"
        for row in repos
    )
    if not repos:
        lines.append("- No repositories ingested yet.")

    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    insert_digest(
        conn,
        DigestRecord(
            digest_date=date.today(),
            path=str(path),
            title=f"AI Infra Radar Digest - {today.isoformat()}",
            content=content,
        ),
    )
    return path
