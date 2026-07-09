from radar.db import connect, fetch_all, init_db, upsert_papers, upsert_repos
from radar.models import Paper, Repo


def test_upserts_are_idempotent() -> None:
    conn = connect(":memory:")
    init_db(conn)

    paper = Paper(
        arxiv_id="2401.00001",
        title="Fast Inference",
        url="https://arxiv.org/abs/2401.00001",
    )
    repo = Repo(
        github_id=1,
        full_name="example/fast-inference",
        url="https://github.com/example/fast",
    )

    assert upsert_papers(conn, [paper]) == 1
    assert upsert_papers(conn, [paper.model_copy(update={"title": "Faster Inference"})]) == 1
    assert upsert_repos(conn, [repo]) == 1
    assert upsert_repos(conn, [repo.model_copy(update={"stars": 10})]) == 1

    papers = fetch_all(conn, "SELECT title FROM papers")
    repos = fetch_all(conn, "SELECT stars FROM repos")

    assert len(papers) == 1
    assert papers[0]["title"] == "Faster Inference"
    assert len(repos) == 1
    assert repos[0]["stars"] == 10
