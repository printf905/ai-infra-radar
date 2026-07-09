from __future__ import annotations

import re
import sqlite3

from radar.db import upsert_matches
from radar.models import Match


def match_database(conn: sqlite3.Connection, threshold: float = 0.2) -> int:
    papers = conn.execute("SELECT id, title, abstract FROM papers").fetchall()
    repos = conn.execute("SELECT id, full_name, description FROM repos").fetchall()
    matches: list[Match] = []

    for paper in papers:
        paper_terms = _terms(f"{paper['title']} {paper['abstract']}")
        if not paper_terms:
            continue
        for repo in repos:
            repo_terms = _terms(f"{repo['full_name']} {repo['description']}")
            overlap = paper_terms & repo_terms
            score = len(overlap) / max(len(paper_terms), 1)
            if score >= threshold:
                matches.append(
                    Match(
                        paper_id=int(paper["id"]),
                        repo_id=int(repo["id"]),
                        score=round(score, 4),
                        reason=f"shared terms: {', '.join(sorted(overlap)[:8])}",
                    )
                )

    return upsert_matches(conn, matches)


def _terms(text: str) -> set[str]:
    stopwords = {
        "and",
        "are",
        "for",
        "from",
        "into",
        "the",
        "this",
        "with",
        "using",
    }
    return {
        term
        for term in re.findall(r"[a-z0-9][a-z0-9-]{2,}", text.lower())
        if term not in stopwords
    }
