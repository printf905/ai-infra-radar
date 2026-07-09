import sqlite3
from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from radar.cli import app
from radar.db import (
    connect,
    fetch_all,
    get_table_columns,
    init_db,
    insert_paper_tags,
    insert_repo_snapshot,
    upsert_paper,
    upsert_repo,
)
from radar.models import Paper, Repo, RepoSnapshot

runner = CliRunner()


def test_init_db_creates_all_tables() -> None:
    conn = connect(":memory:")
    init_db(conn)

    tables = {
        row["name"]
        for row in fetch_all(
            conn,
            "SELECT name FROM sqlite_master WHERE type = 'table'",
        )
    }

    assert {
        "papers",
        "repos",
        "repo_snapshots",
        "paper_tags",
        "paper_repo_matches",
        "daily_scores",
        "digests",
    }.issubset(tables)


def test_upsert_paper_is_idempotent() -> None:
    conn = connect(":memory:")
    init_db(conn)
    paper = Paper(
        arxiv_id="2401.00001",
        title="Fast Inference",
        url="https://arxiv.org/abs/2401.00001",
    )

    first_id = upsert_paper(conn, paper)
    second_id = upsert_paper(
        conn,
        paper.model_copy(update={"title": "Faster Inference"}),
    )
    papers = fetch_all(conn, "SELECT id, title FROM papers")

    assert first_id == second_id
    assert len(papers) == 1
    assert papers[0]["title"] == "Faster Inference"


def test_upsert_repo_updates_stars() -> None:
    conn = connect(":memory:")
    init_db(conn)
    repo = Repo(
        github_id=1,
        full_name="example/fast-inference",
        url="https://github.com/example/fast",
        stars=3,
    )

    first_id = upsert_repo(conn, repo)
    second_id = upsert_repo(conn, repo.model_copy(update={"stars": 10}))
    repos = fetch_all(conn, "SELECT id, stars FROM repos")

    assert first_id == second_id
    assert len(repos) == 1
    assert repos[0]["stars"] == 10


def test_insert_tags_does_not_duplicate() -> None:
    conn = connect(":memory:")
    init_db(conn)
    paper_id = upsert_paper(
        conn,
        Paper(
            arxiv_id="2401.00002",
            title="Serving Systems",
            url="https://arxiv.org/abs/2401.00002",
        ),
    )

    assert insert_paper_tags(conn, paper_id, ["inference", "inference", "serving"]) == 2
    assert insert_paper_tags(conn, paper_id, ["inference"]) == 0

    tags = fetch_all(conn, "SELECT tag FROM paper_tags WHERE paper_id = ?", (paper_id,))

    assert [row["tag"] for row in tags] == ["inference", "serving"]


def test_insert_repo_snapshot_is_idempotent_for_same_date() -> None:
    conn = connect(":memory:")
    init_db(conn)
    repo_id = upsert_repo(
        conn,
        Repo(
            github_id=100,
            full_name="example/inference",
            url="https://github.com/example/inference",
            stars=20,
        ),
    )
    snapshot = RepoSnapshot(
        repo_id=repo_id,
        captured_at=date(2026, 7, 9),
        stars=20,
        forks=2,
    )

    first_id = insert_repo_snapshot(conn, snapshot)
    second_id = insert_repo_snapshot(conn, snapshot.model_copy(update={"stars": 21}))
    snapshots = fetch_all(conn, "SELECT id, stars FROM repo_snapshots")

    assert first_id == second_id
    assert len(snapshots) == 1
    assert snapshots[0]["stars"] == 21


def test_init_db_migrates_old_paper_tags_table() -> None:
    conn = connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE papers (
            id INTEGER PRIMARY KEY,
            arxiv_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            abstract TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL
        );
        CREATE TABLE paper_tags (
            id INTEGER PRIMARY KEY,
            paper_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            UNIQUE (paper_id, tag)
        );
        """
    )

    init_db(conn)
    columns = get_table_columns(conn, "paper_tags")

    assert "confidence" in columns
    assert "source" in columns


def test_tag_papers_cli_works_after_paper_tags_migration(tmp_path: Path) -> None:
    db_path = tmp_path / "old.sqlite"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
topics:
  llm_inference:
    weight: 1.0
    keywords:
      - speculative decoding
""",
        encoding="utf-8",
    )
    old_conn = sqlite3.connect(db_path)
    old_conn.executescript(
        """
        CREATE TABLE papers (
            id INTEGER PRIMARY KEY,
            arxiv_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            abstract TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL
        );
        CREATE TABLE paper_tags (
            id INTEGER PRIMARY KEY,
            paper_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            UNIQUE (paper_id, tag)
        );
        INSERT INTO papers (arxiv_id, title, abstract, url)
        VALUES (
            '2401.1',
            'Speculative Decoding for Fast Inference',
            'A systems paper.',
            'https://arxiv.org/abs/2401.1'
        );
        """
    )
    old_conn.close()

    result = runner.invoke(
        app,
        ["tag-papers", "--config", str(config_path), "--db", str(db_path)],
    )

    assert result.exit_code == 0

    conn = connect(db_path)
    columns = get_table_columns(conn, "paper_tags")
    rows = fetch_all(conn, "SELECT tag, confidence, source FROM paper_tags")

    assert "confidence" in columns
    assert "source" in columns
    assert rows[0]["tag"] == "llm_inference"
    assert rows[0]["confidence"] == 0.95
    assert rows[0]["source"] == "rules"
