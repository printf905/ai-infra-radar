from __future__ import annotations

import sqlite3

from radar.config import ScoringConfig
from radar.db import replace_scores
from radar.models import TrendScore


def compute_scores(conn: sqlite3.Connection, config: ScoringConfig) -> list[TrendScore]:
    rows = conn.execute(
        """
        SELECT
            t.name AS tag,
            SUM(CASE WHEN it.item_type = 'paper' THEN 1 ELSE 0 END) AS paper_count,
            SUM(CASE WHEN it.item_type = 'repo' THEN 1 ELSE 0 END) AS repo_count,
            COALESCE(SUM(CASE WHEN it.item_type = 'repo' THEN r.stars ELSE 0 END), 0) AS star_count
        FROM tags t
        JOIN item_tags it ON it.tag_id = t.id
        LEFT JOIN repos r ON it.item_type = 'repo' AND it.item_id = r.id
        GROUP BY t.name
        """
    ).fetchall()

    match_counts = {
        row["tag"]: int(row["match_count"])
        for row in conn.execute(
            """
            SELECT t.name AS tag, COUNT(DISTINCT m.id) AS match_count
            FROM tags t
            JOIN item_tags pit ON pit.tag_id = t.id AND pit.item_type = 'paper'
            JOIN paper_repo_matches m ON m.paper_id = pit.item_id
            JOIN item_tags rit
              ON rit.tag_id = t.id
             AND rit.item_type = 'repo'
             AND rit.item_id = m.repo_id
            GROUP BY t.name
            """
        )
    }

    scores: list[TrendScore] = []
    for row in rows:
        paper_count = int(row["paper_count"] or 0)
        repo_count = int(row["repo_count"] or 0)
        star_count = int(row["star_count"] or 0)
        match_count = match_counts.get(str(row["tag"]), 0)
        score = (
            paper_count * config.paper_weight
            + repo_count * config.repo_weight
            + star_count * config.star_weight
            + match_count * config.match_weight
        )
        scores.append(
            TrendScore(
                tag=str(row["tag"]),
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
