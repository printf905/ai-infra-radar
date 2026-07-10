import json
from datetime import UTC, date, datetime

from radar.config import AppConfig, TopicConfig
from radar.db import (
    connect,
    fetch_all,
    init_db,
    insert_repo_snapshot,
    replace_paper_tags,
    upsert_matches,
    upsert_paper,
    upsert_repo,
)
from radar.models import Match, Paper, Repo, RepoSnapshot
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
    assert components["repo_match_confidence"] == 0.0
    assert components["repo_momentum"] == 0.0


def test_matched_repo_increases_score() -> None:
    conn = connect(":memory:")
    init_db(conn)
    config = AppConfig(topics={"rag": TopicConfig(weight=1.0)})
    unmatched_id = _paper(conn, "2401.5", "RAG Runtime", datetime(2026, 7, 9, tzinfo=UTC))
    matched_id = _paper(conn, "2401.6", "RAG Runtime with Repo", datetime(2026, 7, 9, tzinfo=UTC))
    repo_id = upsert_repo(
        conn,
        Repo(
            github_id=200,
            full_name="example/rag-runtime",
            url="https://github.com/example/rag-runtime",
        ),
    )
    replace_paper_tags(conn, unmatched_id, {"rag": 0.75})
    replace_paper_tags(conn, matched_id, {"rag": 0.75})
    upsert_matches(
        conn,
        [
            Match(
                paper_id=matched_id,
                repo_id=repo_id,
                score=0.8,
                reason="test",
                match_type="title_phrase",
                confidence=0.8,
            )
        ],
    )

    scores = score_papers(conn, config, today=date(2026, 7, 9))
    by_paper_id = {score.paper_id: score.score for score in scores}

    assert by_paper_id[matched_id] > by_paper_id[unmatched_id]


def test_high_repo_momentum_increases_score() -> None:
    conn = connect(":memory:")
    init_db(conn)
    config = AppConfig(topics={"agents": TopicConfig(weight=1.0)})
    low_id = _paper(conn, "2401.7", "Agent Runtime", datetime(2026, 7, 9, tzinfo=UTC))
    high_id = _paper(
        conn,
        "2401.8",
        "Agent Runtime with Momentum",
        datetime(2026, 7, 9, tzinfo=UTC),
    )
    low_repo_id = upsert_repo(
        conn,
        Repo(github_id=201, full_name="example/agent-low", url="https://github.com/example/low"),
    )
    high_repo_id = upsert_repo(
        conn,
        Repo(github_id=202, full_name="example/agent-high", url="https://github.com/example/high"),
    )
    replace_paper_tags(conn, low_id, {"agents": 0.75})
    replace_paper_tags(conn, high_id, {"agents": 0.75})
    upsert_matches(
        conn,
        [
            Match(
                paper_id=low_id,
                repo_id=low_repo_id,
                score=0.8,
                reason="test",
                match_type="title_similarity",
                confidence=0.8,
            ),
            Match(
                paper_id=high_id,
                repo_id=high_repo_id,
                score=0.8,
                reason="test",
                match_type="title_similarity",
                confidence=0.8,
            ),
        ],
    )
    insert_repo_snapshot(
        conn,
        RepoSnapshot(repo_id=low_repo_id, captured_at=date(2026, 7, 1), stars=100),
    )
    insert_repo_snapshot(
        conn,
        RepoSnapshot(repo_id=low_repo_id, captured_at=date(2026, 7, 9), stars=105),
    )
    insert_repo_snapshot(
        conn,
        RepoSnapshot(repo_id=high_repo_id, captured_at=date(2026, 7, 1), stars=100),
    )
    insert_repo_snapshot(
        conn,
        RepoSnapshot(repo_id=high_repo_id, captured_at=date(2026, 7, 9), stars=260),
    )

    scores = score_papers(conn, config, today=date(2026, 7, 9))
    by_paper_id = {score.paper_id: score.score for score in scores}

    assert by_paper_id[high_id] > by_paper_id[low_id]


def test_score_with_match_and_momentum_stays_between_zero_and_one() -> None:
    conn = connect(":memory:")
    init_db(conn)
    config = AppConfig(topics={"inference_optimization": TopicConfig(weight=2.0)})
    paper_id = _paper(conn, "2401.9", "Inference Runtime", datetime(2026, 7, 9, tzinfo=UTC))
    repo_id = upsert_repo(
        conn,
        Repo(github_id=203, full_name="example/inference", url="https://github.com/example/inference"),
    )
    replace_paper_tags(conn, paper_id, {"inference_optimization": 0.95})
    upsert_matches(
        conn,
        [
            Match(
                paper_id=paper_id,
                repo_id=repo_id,
                score=0.99,
                reason="test",
                match_type="arxiv_id",
                confidence=0.99,
            )
        ],
    )
    insert_repo_snapshot(
        conn,
        RepoSnapshot(repo_id=repo_id, captured_at=date(2026, 7, 1), stars=10),
    )
    insert_repo_snapshot(
        conn,
        RepoSnapshot(repo_id=repo_id, captured_at=date(2026, 7, 9), stars=500),
    )

    score = score_papers(conn, config, today=date(2026, 7, 9))[0].score

    assert 0.0 <= score <= 1.0


def test_scoring_ignores_weak_topic_overlap() -> None:
    conn = connect(":memory:")
    init_db(conn)
    config = AppConfig(topics={"rag": TopicConfig(weight=1.0)})
    paper_id = _paper(conn, "2401.10", "RAG Runtime", datetime(2026, 7, 9, tzinfo=UTC))
    repo_id = upsert_repo(
        conn,
        Repo(github_id=204, full_name="example/rag", url="https://github.com/example/rag"),
    )
    replace_paper_tags(conn, paper_id, {"rag": 0.75})
    upsert_matches(
        conn,
        [
            Match(
                paper_id=paper_id,
                repo_id=repo_id,
                score=0.25,
                reason="weak topic overlap",
                match_type="topic_overlap",
                confidence=0.25,
            )
        ],
    )

    score_papers(conn, config, today=date(2026, 7, 9))
    row = fetch_all(
        conn,
        "SELECT components_json FROM daily_scores WHERE paper_id = ?",
        (paper_id,),
    )[0]
    components = json.loads(row["components_json"])

    assert components["repo_match_confidence"] == 0.0
    assert components["repo_momentum"] == 0.0


def _paper(conn, arxiv_id: str, title: str, published_at: datetime) -> int:
    return upsert_paper(
        conn,
        Paper(
            arxiv_id=arxiv_id,
            title=title,
            published_at=published_at,
            url=f"https://arxiv.org/abs/{arxiv_id}",
        ),
    )
