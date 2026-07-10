from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime

from radar.config import AppConfig
from radar.db import insert_daily_score
from radar.matching import STRONG_MATCH_TYPES
from radar.models import DailyScore

_STRONG_TYPES = tuple(sorted(STRONG_MATCH_TYPES))
_STRONG_TYPE_PLACEHOLDERS = ",".join("?" for _ in _STRONG_TYPES)


def score_papers(
    conn: sqlite3.Connection,
    config: AppConfig,
    today: date | None = None,
) -> list[DailyScore]:
    score_date = today or date.today()
    scores: list[DailyScore] = []
    for paper in conn.execute("SELECT id, published_at FROM papers").fetchall():
        paper_id = int(paper["id"])
        components = score_components(
            published_at=_parse_datetime(paper["published_at"]),
            tag_confidences=_paper_tag_confidences(conn, paper_id),
            topic_weights=config.topic_weights,
            repo_match_confidence=_repo_match_confidence(conn, paper_id),
            repo_momentum=_repo_momentum(conn, paper_id),
            today=score_date,
        )
        score = final_score(components)
        daily_score = DailyScore(
            score_date=score_date,
            paper_id=paper_id,
            score=score,
            components_json=json.dumps(components, sort_keys=True),
        )
        insert_daily_score(conn, daily_score)
        scores.append(daily_score)
    return scores


def score_components(
    published_at: datetime | None,
    tag_confidences: dict[str, float],
    topic_weights: dict[str, float],
    repo_match_confidence: float = 0.0,
    repo_momentum: float = 0.0,
    today: date | None = None,
) -> dict[str, float]:
    topic_relevance = 0.0
    for tag, confidence in tag_confidences.items():
        topic_relevance = max(topic_relevance, confidence * topic_weights.get(tag, 1.0))
    return {
        "topic_relevance": round(_clip(topic_relevance), 4),
        "recency": recency_score(published_at, today=today),
        "repo_match_confidence": round(_clip(repo_match_confidence), 4),
        "repo_momentum": round(_clip(repo_momentum), 4),
        "anomaly_score": 0.0,
    }


def final_score(components: dict[str, float]) -> float:
    score = (
        0.35 * components["topic_relevance"]
        + 0.25 * components["recency"]
        + 0.25 * components["repo_match_confidence"]
        + 0.10 * components["repo_momentum"]
        + 0.05 * components["anomaly_score"]
    )
    return round(_clip(score), 4)


def recency_score(published_at: datetime | None, today: date | None = None) -> float:
    if published_at is None:
        return 0.1
    current_date = today or date.today()
    age_days = (current_date - published_at.date()).days
    if age_days <= 3:
        return 1.0
    if age_days <= 7:
        return 0.7
    if age_days <= 14:
        return 0.4
    return 0.1


def score_database(conn: sqlite3.Connection, config: AppConfig) -> int:
    return len(score_papers(conn, config))


def _paper_tag_confidences(conn: sqlite3.Connection, paper_id: int) -> dict[str, float]:
    return {
        str(row["tag"]): float(row["confidence"])
        for row in conn.execute(
            "SELECT tag, confidence FROM paper_tags WHERE paper_id = ?",
            (paper_id,),
        )
    }


def _repo_match_confidence(conn: sqlite3.Connection, paper_id: int) -> float:
    row = conn.execute(
        f"""
        SELECT MAX(CASE WHEN confidence > 0 THEN confidence ELSE score END) AS value
        FROM paper_repo_matches
        WHERE paper_id = ?
          AND match_type IN ({_STRONG_TYPE_PLACEHOLDERS})
          AND (CASE WHEN confidence > 0 THEN confidence ELSE score END) >= 0.70
        """,
        (paper_id, *_STRONG_TYPES),
    ).fetchone()
    return _clip(float(row["value"] or 0.0)) if row else 0.0


def _repo_momentum(conn: sqlite3.Connection, paper_id: int) -> float:
    rows = conn.execute(
        f"""
        SELECT rs.repo_id, rs.captured_at, rs.stars
        FROM paper_repo_matches m
        JOIN repo_snapshots rs ON rs.repo_id = m.repo_id
        WHERE m.paper_id = ?
          AND m.match_type IN ({_STRONG_TYPE_PLACEHOLDERS})
          AND (CASE WHEN m.confidence > 0 THEN m.confidence ELSE m.score END) >= 0.70
        ORDER BY rs.repo_id, rs.captured_at
        """,
        (paper_id, *_STRONG_TYPES),
    ).fetchall()
    snapshots: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        snapshots.setdefault(int(row["repo_id"]), []).append(row)

    momentum = 0.0
    for repo_rows in snapshots.values():
        if len(repo_rows) < 2:
            continue
        star_delta = int(repo_rows[-1]["stars"] or 0) - int(repo_rows[0]["stars"] or 0)
        momentum = max(momentum, star_delta / 100.0)
    return _clip(momentum)


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _clip(value: float) -> float:
    return min(max(value, 0.0), 1.0)
