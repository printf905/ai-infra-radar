import json
from datetime import UTC, date, datetime

from radar.config import AppConfig, TopicConfig
from radar.db import connect, fetch_all, init_db, replace_paper_tags, upsert_paper
from radar.models import Paper
from radar.scoring import score_papers


def test_fresh_relevant_paper_scores_higher_than_old_paper() -> None:
    conn = connect(":memory:")
    init_db(conn)
    config = AppConfig(topics={"inference_optimization": TopicConfig(weight=1.3)})
    fresh_id = upsert_paper(
        conn,
        Paper(
            arxiv_id="2401.1",
            title="Fresh Inference Paper",
            published_at=datetime(2026, 7, 8, tzinfo=UTC),
            url="https://arxiv.org/abs/2401.1",
        ),
    )
    old_id = upsert_paper(
        conn,
        Paper(
            arxiv_id="2401.2",
            title="Old Inference Paper",
            published_at=datetime(2026, 6, 1, tzinfo=UTC),
            url="https://arxiv.org/abs/2401.2",
        ),
    )
    replace_paper_tags(conn, fresh_id, {"inference_optimization": 0.95})
    replace_paper_tags(conn, old_id, {"inference_optimization": 0.95})

    scores = score_papers(conn, config, today=date(2026, 7, 9))
    by_paper_id = {score.paper_id: score.score for score in scores}

    assert by_paper_id[fresh_id] > by_paper_id[old_id]


def test_score_is_between_zero_and_one() -> None:
    conn = connect(":memory:")
    init_db(conn)
    config = AppConfig(topics={"inference_optimization": TopicConfig(weight=2.0)})
    paper_id = upsert_paper(
        conn,
        Paper(
            arxiv_id="2401.3",
            title="Relevant Paper",
            published_at=datetime(2026, 7, 9, tzinfo=UTC),
            url="https://arxiv.org/abs/2401.3",
        ),
    )
    replace_paper_tags(conn, paper_id, {"inference_optimization": 0.95})

    score = score_papers(conn, config, today=date(2026, 7, 9))[0].score

    assert 0.0 <= score <= 1.0


def test_scoring_writes_rows_into_daily_scores() -> None:
    conn = connect(":memory:")
    init_db(conn)
    config = AppConfig(topics={"agents": TopicConfig(weight=0.8)})
    paper_id = upsert_paper(
        conn,
        Paper(
            arxiv_id="2401.4",
            title="Agent Paper",
            published_at=datetime(2026, 7, 4, tzinfo=UTC),
            url="https://arxiv.org/abs/2401.4",
        ),
    )
    replace_paper_tags(conn, paper_id, {"agents": 0.75})

    score_papers(conn, config, today=date(2026, 7, 9))
    rows = fetch_all(conn, "SELECT paper_id, score, components_json FROM daily_scores")
    components = json.loads(rows[0]["components_json"])

    assert len(rows) == 1
    assert rows[0]["paper_id"] == paper_id
    assert rows[0]["score"] > 0
    assert components["topic_relevance"] == 0.6
    assert components["recency"] == 0.7
    assert components["github_momentum"] == 0.0
