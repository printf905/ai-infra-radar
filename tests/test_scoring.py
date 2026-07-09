from radar.config import ScoringConfig
from radar.db import (
    connect,
    init_db,
    replace_paper_tags,
    upsert_matches,
    upsert_papers,
    upsert_repos,
)
from radar.models import Match, Paper, Repo
from radar.scoring import compute_scores


def test_compute_scores_combines_counts_stars_and_matches() -> None:
    conn = connect(":memory:")
    init_db(conn)
    upsert_papers(
        conn,
        [
            Paper(
                arxiv_id="2401.1",
                title="Inference Systems",
                url="https://arxiv.org/abs/2401.1",
            )
        ],
    )
    upsert_repos(
        conn,
        [
            Repo(
                github_id=100,
                full_name="example/inference",
                url="https://github.com/example/inference",
                stars=20,
            )
        ],
    )

    paper_id = conn.execute("SELECT id FROM papers").fetchone()["id"]
    repo_id = conn.execute("SELECT id FROM repos").fetchone()["id"]
    replace_paper_tags(conn, paper_id, ["inference"])
    upsert_matches(conn, [Match(paper_id=paper_id, repo_id=repo_id, score=0.5, reason="test")])

    scores = compute_scores(
        conn,
        ScoringConfig(paper_weight=1.0, repo_weight=2.0, star_weight=0.1, match_weight=3.0),
    )

    assert len(scores) == 1
    assert scores[0].tag == "inference"
    assert scores[0].score == 8.0
    assert scores[0].paper_count == 1
    assert scores[0].repo_count == 1
    assert scores[0].match_count == 1
    assert scores[0].star_count == 20
