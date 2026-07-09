from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime

from radar.config import AppConfig
from radar.db import insert_daily_score
from radar.models import DailyScore


def score_papers(
    conn: sqlite3.Connection,
    config: AppConfig,
    today: date | None = None,
) -> list[DailyScore]:
    score_date = today or date.today()
    scores: list[DailyScore] = []
    for paper in conn.execute("SELECT id, published_at FROM papers").fetchall():
        components = score_components(
            published_at=_parse_datetime(paper["published_at"]),
            tag_confidences=_paper_tag_confidences(conn, int(paper["id"])),
            topic_weights=config.topic_weights,
            today=score_date,
        )
        score = final_score(components)
        daily_score = DailyScore(
            score_date=score_date,
            paper_id=int(paper["id"]),
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
    today: date | None = None,
) -> dict[str, float]:
    topic_relevance = 0.0
    for tag, confidence in tag_confidences.items():
        topic_relevance = max(topic_relevance, confidence * topic_weights.get(tag, 1.0))
    return {
        "topic_relevance": round(min(topic_relevance, 1.0), 4),
        "recency": recency_score(published_at, today=today),
        "github_momentum": 0.0,
        "implementation_confidence": 0.0,
        "anomaly_score": 0.0,
    }


def final_score(components: dict[str, float]) -> float:
    score = (
        0.35 * components["topic_relevance"]
        + 0.25 * components["recency"]
        + 0.20 * components["github_momentum"]
        + 0.10 * components["implementation_confidence"]
        + 0.10 * components["anomaly_score"]
    )
    return round(min(max(score, 0.0), 1.0), 4)


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


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
