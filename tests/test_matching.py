from radar.db import connect, fetch_all, init_db, upsert_paper, upsert_repo
from radar.matching import match_database, match_paper_to_repo
from radar.models import Paper, Repo


def test_arxiv_id_match() -> None:
    match = match_paper_to_repo(
        paper_id=1,
        repo_id=2,
        arxiv_id="2607.00001",
        title="Speculative Decoding for Low-Latency LLM Serving",
        abstract="",
        tags=[],
        repo_name="sample/serving",
        repo_description="Implementation of arXiv 2607.00001.",
    )

    assert match is not None
    assert match.match_type == "arxiv_id"
    assert match.confidence == 0.98


def test_title_phrase_match() -> None:
    title = "Speculative Decoding for Low-Latency LLM Serving"
    match = match_paper_to_repo(
        paper_id=1,
        repo_id=2,
        arxiv_id="2607.00002",
        title=title,
        abstract="",
        tags=[],
        repo_name="sample/serving",
        repo_description=f"Unofficial implementation of {title}.",
    )

    assert match is not None
    assert match.match_type == "title_phrase"


def test_acronym_match() -> None:
    match = match_paper_to_repo(
        paper_id=1,
        repo_id=2,
        arxiv_id="2607.00003",
        title="Fast Attention for Sparse Transformers",
        abstract="",
        tags=[],
        repo_name="sample/fast-attention",
        repo_description="Reference implementation.",
    )

    assert match is not None
    assert match.match_type == "acronym"
    assert "FAST" in match.reason


def test_no_match() -> None:
    match = match_paper_to_repo(
        paper_id=1,
        repo_id=2,
        arxiv_id="2607.00004",
        title="A Survey of Sorting Algorithms",
        abstract="",
        tags=[],
        repo_name="sample/llm-serving",
        repo_description="Inference server for language models.",
    )

    assert match is None


def test_match_database_stores_match_type_and_confidence() -> None:
    conn = connect(":memory:")
    init_db(conn)
    paper_id = upsert_paper(
        conn,
        Paper(
            arxiv_id="2607.00005",
            title="Retrieval Augmented Generation Runtime",
            abstract="",
            url="https://arxiv.org/abs/2607.00005",
        ),
    )
    repo_id = upsert_repo(
        conn,
        Repo(
            github_id=123,
            full_name="sample/rag-runtime",
            description="Implementation for arXiv 2607.00005.",
            url="https://github.com/sample/rag-runtime",
        ),
    )

    assert match_database(conn) == 1
    rows = fetch_all(
        conn,
        "SELECT paper_id, repo_id, match_type, confidence FROM paper_repo_matches",
    )

    assert rows[0]["paper_id"] == paper_id
    assert rows[0]["repo_id"] == repo_id
    assert rows[0]["match_type"] == "arxiv_id"
    assert rows[0]["confidence"] == 0.98
