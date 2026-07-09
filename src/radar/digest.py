from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def write_digest(conn: sqlite3.Connection, reports_dir: Path | str) -> Path:
    out_dir = Path(reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"digest-{datetime.now(UTC).date().isoformat()}.md"

    scores = conn.execute(
        "SELECT tag, score, paper_count, repo_count, match_count, star_count FROM trend_scores "
        "ORDER BY score DESC LIMIT 20"
    ).fetchall()
    papers = conn.execute(
        "SELECT title, url, published_at FROM papers ORDER BY published_at DESC LIMIT 10"
    ).fetchall()
    repos = conn.execute(
        "SELECT full_name, url, stars, language FROM repos ORDER BY stars DESC LIMIT 10"
    ).fetchall()

    lines = [
        f"# AI Infra Radar Digest - {datetime.now(UTC).date().isoformat()}",
        "",
        "## Top Trends",
        "",
    ]
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

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
