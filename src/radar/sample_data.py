from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime

from radar.db import (
    init_db,
    insert_daily_score,
    insert_paper_tags,
    insert_repo_snapshot,
    upsert_matches,
    upsert_paper,
    upsert_repo,
)
from radar.models import DailyScore, Match, Paper, Repo, RepoSnapshot

SAMPLE_DATE = date(2026, 7, 9)


@dataclass(frozen=True)
class SampleLoadResult:
    papers: int
    repos: int
    tags: int
    scores: int
    snapshots: int
    matches: int


def load_sample_data(conn: sqlite3.Connection) -> SampleLoadResult:
    init_db(conn)
    paper_ids = _load_papers(conn)
    repo_ids = _load_repos(conn)
    tags = _load_tags(conn, paper_ids)
    scores = _load_scores(conn, paper_ids)
    snapshots = _load_snapshots(conn, repo_ids)
    matches = _load_matches(conn, paper_ids, repo_ids)
    return SampleLoadResult(
        papers=len(paper_ids),
        repos=len(repo_ids),
        tags=tags,
        scores=scores,
        snapshots=snapshots,
        matches=matches,
    )


def _load_papers(conn: sqlite3.Connection) -> dict[str, int]:
    papers = [
        Paper(
            arxiv_id="2607.00001",
            title="Speculative Decoding for Low-Latency LLM Serving",
            abstract=(
                "Speculative decoding improves inference throughput for large "
                "language model serving. The method reduces latency while "
                "preserving output quality in production workloads."
            ),
            authors=["Mira Chen", "Noah Patel"],
            primary_category="cs.LG",
            categories=["cs.LG", "cs.DC"],
            published_at=datetime(2026, 7, 8, tzinfo=UTC),
            updated_at=datetime(2026, 7, 8, tzinfo=UTC),
            url="https://arxiv.org/abs/2607.00001",
            pdf_url="https://arxiv.org/pdf/2607.00001",
        ),
        Paper(
            arxiv_id="2607.00002",
            title="Long Context Retrieval with KV Cache Reuse",
            abstract=(
                "Long-context systems can combine retrieval cache and KV cache "
                "reuse to reduce repeated attention costs. We evaluate the "
                "approach on document question answering workloads."
            ),
            authors=["Ava Singh", "Leo Martinez"],
            primary_category="cs.CL",
            categories=["cs.CL", "cs.LG"],
            published_at=datetime(2026, 7, 6, tzinfo=UTC),
            updated_at=datetime(2026, 7, 6, tzinfo=UTC),
            url="https://arxiv.org/abs/2607.00002",
            pdf_url="https://arxiv.org/pdf/2607.00002",
        ),
        Paper(
            arxiv_id="2607.00003",
            title="Tool Use Benchmarks for Multi-Agent Code Agents",
            abstract=(
                "Agent systems increasingly rely on tool use, planning, and "
                "browser interaction. We introduce a benchmark for multi-agent "
                "code agent coordination."
            ),
            authors=["Sam Rivera", "Iris Wong"],
            primary_category="cs.AI",
            categories=["cs.AI", "cs.SE"],
            published_at=datetime(2026, 7, 3, tzinfo=UTC),
            updated_at=datetime(2026, 7, 3, tzinfo=UTC),
            url="https://arxiv.org/abs/2607.00003",
            pdf_url="https://arxiv.org/pdf/2607.00003",
        ),
    ]
    return {paper.arxiv_id: upsert_paper(conn, paper) for paper in papers}


def _load_repos(conn: sqlite3.Connection) -> dict[str, int]:
    repos = [
        Repo(
            github_id=900001,
            full_name="sample/vllm-serving-lab",
            description="Sample high-throughput LLM serving runtime.",
            url="https://github.com/sample/vllm-serving-lab",
            stars=1840,
            forks=210,
            open_issues=18,
            language="Python",
            created_at=datetime(2025, 11, 10, tzinfo=UTC),
            updated_at=datetime(2026, 7, 8, tzinfo=UTC),
            pushed_at=datetime(2026, 7, 8, tzinfo=UTC),
        ),
        Repo(
            github_id=900002,
            full_name="sample/rag-cache-kit",
            description="Sample retrieval cache utilities for RAG systems.",
            url="https://github.com/sample/rag-cache-kit",
            stars=730,
            forks=86,
            open_issues=9,
            language="Python",
            created_at=datetime(2026, 1, 14, tzinfo=UTC),
            updated_at=datetime(2026, 7, 7, tzinfo=UTC),
            pushed_at=datetime(2026, 7, 7, tzinfo=UTC),
        ),
        Repo(
            github_id=900003,
            full_name="sample/agent-browser-runtime",
            description="Sample runtime for browser agent workflows.",
            url="https://github.com/sample/agent-browser-runtime",
            stars=520,
            forks=61,
            open_issues=12,
            language="TypeScript",
            created_at=datetime(2026, 2, 2, tzinfo=UTC),
            updated_at=datetime(2026, 7, 5, tzinfo=UTC),
            pushed_at=datetime(2026, 7, 5, tzinfo=UTC),
        ),
    ]
    return {repo.full_name: upsert_repo(conn, repo) for repo in repos}


def _load_tags(conn: sqlite3.Connection, paper_ids: dict[str, int]) -> int:
    insert_paper_tags(
        conn,
        paper_ids["2607.00001"],
        {"inference_optimization": 0.95, "model_compression": 0.75},
    )
    insert_paper_tags(
        conn,
        paper_ids["2607.00002"],
        {"long_context": 0.95, "rag": 0.75},
    )
    insert_paper_tags(
        conn,
        paper_ids["2607.00003"],
        {"agents": 0.95},
    )
    placeholders = ",".join("?" for _ in paper_ids)
    row = conn.execute(
        f"SELECT COUNT(*) AS count FROM paper_tags WHERE paper_id IN ({placeholders})",
        tuple(paper_ids.values()),
    ).fetchone()
    return int(row["count"] or 0)


def _load_scores(conn: sqlite3.Connection, paper_ids: dict[str, int]) -> int:
    scores = [
        DailyScore(
            score_date=SAMPLE_DATE,
            paper_id=paper_ids["2607.00001"],
            score=0.6825,
            components_json=json.dumps(
                {
                    "topic_relevance": 1.0,
                    "recency": 1.0,
                    "github_momentum": 0.0,
                    "implementation_confidence": 0.0,
                    "anomaly_score": 0.0,
                },
                sort_keys=True,
            ),
        ),
        DailyScore(
            score_date=SAMPLE_DATE,
            paper_id=paper_ids["2607.00002"],
            score=0.595,
            components_json=json.dumps(
                {
                    "topic_relevance": 1.0,
                    "recency": 0.7,
                    "github_momentum": 0.0,
                    "implementation_confidence": 0.0,
                    "anomaly_score": 0.0,
                },
                sort_keys=True,
            ),
        ),
        DailyScore(
            score_date=SAMPLE_DATE,
            paper_id=paper_ids["2607.00003"],
            score=0.5075,
            components_json=json.dumps(
                {
                    "topic_relevance": 1.0,
                    "recency": 0.4,
                    "github_momentum": 0.0,
                    "implementation_confidence": 0.0,
                    "anomaly_score": 0.0,
                },
                sort_keys=True,
            ),
        ),
    ]
    for score in scores:
        insert_daily_score(conn, score)
    return len(scores)


def _load_snapshots(conn: sqlite3.Connection, repo_ids: dict[str, int]) -> int:
    snapshots = [
        RepoSnapshot(
            repo_id=repo_ids["sample/vllm-serving-lab"],
            captured_at=SAMPLE_DATE,
            stars=1840,
            forks=210,
            open_issues=18,
            pushed_at=datetime(2026, 7, 8, tzinfo=UTC),
        ),
        RepoSnapshot(
            repo_id=repo_ids["sample/rag-cache-kit"],
            captured_at=SAMPLE_DATE,
            stars=730,
            forks=86,
            open_issues=9,
            pushed_at=datetime(2026, 7, 7, tzinfo=UTC),
        ),
        RepoSnapshot(
            repo_id=repo_ids["sample/agent-browser-runtime"],
            captured_at=SAMPLE_DATE,
            stars=520,
            forks=61,
            open_issues=12,
            pushed_at=datetime(2026, 7, 5, tzinfo=UTC),
        ),
    ]
    for snapshot in snapshots:
        insert_repo_snapshot(conn, snapshot)
    return len(snapshots)


def _load_matches(
    conn: sqlite3.Connection,
    paper_ids: dict[str, int],
    repo_ids: dict[str, int],
) -> int:
    matches = [
        Match(
            paper_id=paper_ids["2607.00001"],
            repo_id=repo_ids["sample/vllm-serving-lab"],
            score=0.82,
            reason="sample match: serving and speculative decoding",
        ),
        Match(
            paper_id=paper_ids["2607.00002"],
            repo_id=repo_ids["sample/rag-cache-kit"],
            score=0.76,
            reason="sample match: retrieval cache and long context",
        ),
        Match(
            paper_id=paper_ids["2607.00003"],
            repo_id=repo_ids["sample/agent-browser-runtime"],
            score=0.72,
            reason="sample match: browser agent workflow",
        ),
    ]
    return upsert_matches(conn, matches)
