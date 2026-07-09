from __future__ import annotations

import sqlite3

from radar.config import ScoringConfig
from radar.db import replace_scores
from radar.models import TrendScore


def compute_scores(conn: sqlite3.Connection, config: ScoringConfig) -> list[TrendScore]:
    tags = [
        str(row["tag"])
        for row in conn.execute("SELECT DISTINCT tag FROM paper_tags ORDER BY tag").fetchall()
    ]
    scores: list[TrendScore] = []

    for tag in tags:
        paper_count = _single_int(
            conn,
            "SELECT COUNT(DISTINCT paper_id) AS value FROM paper_tags WHERE tag = ?",
            (tag,),
        )
        match_count = _single_int(
            conn,
            """
            SELECT COUNT(DISTINCT m.id) AS value
            FROM paper_tags pt
            JOIN paper_repo_matches m ON m.paper_id = pt.paper_id
            WHERE pt.tag = ?
            """,
            (tag,),
        )
        repo_rows = conn.execute(
            """
            SELECT DISTINCT r.id, r.stars
            FROM paper_tags pt
            JOIN paper_repo_matches m ON m.paper_id = pt.paper_id
            JOIN repos r ON r.id = m.repo_id
            WHERE pt.tag = ?
            """,
            (tag,),
        ).fetchall()
        repo_count = len(repo_rows)
        star_count = sum(int(row["stars"] or 0) for row in repo_rows)
        score = (
            paper_count * config.paper_weight
            + repo_count * config.repo_weight
            + star_count * config.star_weight
            + match_count * config.match_weight
        )
        scores.append(
            TrendScore(
                tag=tag,
                score=round(score, 4),
                paper_count=paper_count,
                repo_count=repo_count,
                match_count=match_count,
                star_count=star_count,
            )
        )

    return sorted(scores, key=lambda item: item.score, reverse=True)


def score_database(conn: sqlite3.Connection, config: ScoringConfig) -> int:
    return replace_scores(conn, compute_scores(conn, config))


def _single_int(conn: sqlite3.Connection, query: str, params: tuple[object, ...]) -> int:
    row = conn.execute(query, params).fetchone()
    return int(row["value"] or 0) if row else 0
