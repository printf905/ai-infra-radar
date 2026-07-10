from radar.db import connect, fetch_all, init_db, insert_paper_tags, upsert_paper, upsert_repo
from radar.matching import match_database, match_paper_to_repo
from radar.models import Paper, Repo


def test_topic_overlap_alone_does_not_create_strong_match() -> None:
    match = match_paper_to_repo(
        paper_id=1,
        repo_id=2,
        arxiv_id="2607.00000",
        title="A Survey of Sorting Algorithms",
        abstract="Retrieval augmented generation background.",
        tags=["rag"],
        repo_name="sample/rag-toolkit",
        repo_description="RAG retriever knowledge base utilities.",
    )

    assert match is None


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
    assert match.confidence == 0.95


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
    assert match.confidence == 0.9


def test_acronym_alone_without_keyword_overlap_does_not_match() -> None:
    match = match_paper_to_repo(
        paper_id=1,
        repo_id=2,
        arxiv_id="2607.00003",
        title="Fast Attention Sparse Transformer",
        abstract="",
        tags=[],
        repo_name="sample/fast-runtime",
        repo_description="Reference implementation.",
    )

    assert match is None


def test_acronym_with_title_keyword_overlap_matches() -> None:
    match = match_paper_to_repo(
        paper_id=1,
        repo_id=2,
        arxiv_id="2607.00004",
        title="Fast Attention Sparse Transformer",
        abstract="",
        tags=[],
        repo_name="sample/fast-attention",
        repo_description="Reference implementation.",
    )

    assert match is not None
    assert match.match_type == "acronym"
    assert match.confidence == 0.75
    assert "FAST" in match.reason


def test_no_match() -> None:
    match = match_paper_to_repo(
        paper_id=1,
        repo_id=2,
        arxiv_id="2607.00005",
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
            arxiv_id="2607.00006",
            title="Retrieval Augmented Generation Runtime",
            abstract="",
            url="https://arxiv.org/abs/2607.00006",
        ),
    )
    repo_id = upsert_repo(
        conn,
        Repo(
            github_id=123,
            full_name="sample/rag-runtime",
            description="Implementation for arXiv 2607.00006.",
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
    assert rows[0]["confidence"] == 0.95


def test_match_database_caps_matches_per_paper_at_three() -> None:
    conn = connect(":memory:")
    init_db(conn)
    paper_id = upsert_paper(
        conn,
        Paper(
            arxiv_id="2607.00007",
            title="Sparse Retrieval Cache Runtime",
            abstract="Runtime for sparse retrieval cache systems.",
            url="https://arxiv.org/abs/2607.00007",
        ),
    )
    insert_paper_tags(conn, paper_id, {"rag": 0.75})
    for index, description in enumerate(
        [
            "Implementation for arXiv 2607.00007.",
            "Unofficial Sparse Retrieval Cache Runtime implementation.",
            "Sparse retrieval cache tooling.",
            "Retrieval cache runtime examples.",
            "Sparse cache runtime experiments.",
        ],
        start=1,
    ):
        upsert_repo(
            conn,
            Repo(
                github_id=9000 + index,
                full_name=f"sample/repo-{index}",
                description=description,
                url=f"https://github.com/sample/repo-{index}",
            ),
        )

    assert match_database(conn) == 3
    rows = fetch_all(
        conn,
        """
        SELECT match_type, confidence
        FROM paper_repo_matches
        WHERE paper_id = ?
        ORDER BY confidence DESC
        """,
        (paper_id,),
    )

    assert len(rows) == 3
    assert [row["match_type"] for row in rows] == [
        "arxiv_id",
        "title_phrase",
        "title_similarity",
    ]
