from __future__ import annotations

from datetime import UTC, date, datetime

from radar.db import (
    connect,
    fetch_all,
    init_db,
    insert_daily_score,
    insert_paper_tags,
    upsert_matches,
    upsert_paper,
    upsert_repo,
)
from radar.digest import write_digest
from radar.models import DailyScore, Match, Paper, Repo


def test_digest_file_is_created(tmp_path) -> None:
    conn = connect(":memory:")
    init_db(conn)

    path = write_digest(conn, tmp_path, date(2026, 7, 9))

    assert path == tmp_path / "2026-07-09.md"
    assert path.exists()


def test_digest_contains_top_paper_title(tmp_path) -> None:
    conn = connect(":memory:")
    init_db(conn)
    paper_id = _insert_scored_paper(conn, title="Speculative Decoding in Production")

    insert_paper_tags(conn, paper_id, {"llm_inference": 0.95})
    path = write_digest(conn, tmp_path, date(2026, 7, 9))

    assert "Speculative Decoding in Production" in path.read_text(encoding="utf-8")


def test_empty_db_still_creates_valid_digest(tmp_path) -> None:
    conn = connect(":memory:")
    init_db(conn)

    path = write_digest(conn, tmp_path, date(2026, 7, 9))
    content = path.read_text(encoding="utf-8")
    digest_rows = fetch_all(conn, "SELECT digest_date, path FROM digests")

    assert "# AI Infra Radar Digest - 2026-07-09" in content
    assert "No scored papers yet." in content
    assert "No repositories ingested yet." in content
    assert "No tagged papers published in the last 7 days." in content
    assert len(digest_rows) == 1
    assert digest_rows[0]["digest_date"] == "2026-07-09"


def test_digest_uses_daily_scores_paper_id(tmp_path) -> None:
    conn = connect(":memory:")
    init_db(conn)
    unscored_id = upsert_paper(
        conn,
        Paper(
            arxiv_id="2401.00001",
            title="Unscored Paper",
            abstract="This paper should not appear.",
            published_at=datetime(2026, 7, 8, tzinfo=UTC),
            url="https://arxiv.org/abs/2401.00001",
        ),
    )
    scored_id = _insert_scored_paper(conn, title="Correct Scored Paper")

    assert scored_id != unscored_id

    path = write_digest(conn, tmp_path, date(2026, 7, 9))
    content = path.read_text(encoding="utf-8")

    assert "Correct Scored Paper" in content
    assert "Unscored Paper" not in content


def test_digest_includes_matched_repo_and_topic_trends(tmp_path) -> None:
    conn = connect(":memory:")
    init_db(conn)
    paper_id = _insert_scored_paper(conn, title="Agentic Inference Systems")
    insert_paper_tags(conn, paper_id, {"agents": 0.95, "llm_inference": 0.75})
    repo_id = upsert_repo(
        conn,
        Repo(
            github_id=42,
            full_name="example/agent-runtime",
            url="https://github.com/example/agent-runtime",
            stars=100,
            forks=10,
            pushed_at=datetime(2026, 7, 8, tzinfo=UTC),
        ),
    )
    upsert_matches(conn, [Match(paper_id=paper_id, repo_id=repo_id, score=0.8, reason="test")])

    path = write_digest(conn, tmp_path, date(2026, 7, 9))
    content = path.read_text(encoding="utf-8")

    assert "example/agent-runtime" in content
    assert "- agents: 1 papers" in content
    assert "- llm_inference: 1 papers" in content


def _insert_scored_paper(conn, title: str) -> int:
    paper_id = upsert_paper(
        conn,
        Paper(
            arxiv_id=f"2401.{abs(hash(title)) % 100000}",
            title=title,
            abstract="First sentence. Second sentence. Third sentence.",
            authors=["Alice Researcher", "Bob Engineer"],
            published_at=datetime(2026, 7, 8, tzinfo=UTC),
            url="https://arxiv.org/abs/2401.00002",
        ),
    )
    insert_daily_score(
        conn,
        DailyScore(
            score_date=date(2026, 7, 9),
            paper_id=paper_id,
            score=0.91,
            components_json='{"topic_relevance": 0.95}',
        ),
    )
    return paper_id
