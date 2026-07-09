from radar.db import connect, fetch_all
from radar.digest import write_digest
from radar.sample_data import SAMPLE_DATE, load_sample_data


def test_load_sample_data_populates_core_tables(tmp_path) -> None:
    db_path = tmp_path / "sample.db"
    conn = connect(db_path)

    result = load_sample_data(conn)

    assert result.papers == 3
    assert result.repos == 3
    assert result.tags == 5
    assert result.scores == 3
    assert result.snapshots == 3
    assert result.matches == 3
    assert fetch_all(conn, "SELECT COUNT(*) AS count FROM papers")[0]["count"] == 3
    assert fetch_all(conn, "SELECT COUNT(*) AS count FROM repos")[0]["count"] == 3
    assert fetch_all(conn, "SELECT COUNT(*) AS count FROM daily_scores")[0]["count"] == 3


def test_sample_data_supports_digest_generation(tmp_path) -> None:
    conn = connect(":memory:")
    load_sample_data(conn)

    path = write_digest(conn, tmp_path, SAMPLE_DATE)
    content = path.read_text(encoding="utf-8")

    assert path == tmp_path / "2026-07-09.md"
    assert "Speculative Decoding for Low-Latency LLM Serving" in content
    assert "sample/vllm-serving-lab" in content
    assert "# AI Infra Radar Digest - 2026-07-09" in content


def test_load_sample_data_is_idempotent() -> None:
    conn = connect(":memory:")

    load_sample_data(conn)
    second = load_sample_data(conn)

    assert second.papers == 3
    assert fetch_all(conn, "SELECT COUNT(*) AS count FROM papers")[0]["count"] == 3
    assert fetch_all(conn, "SELECT COUNT(*) AS count FROM repos")[0]["count"] == 3
    assert fetch_all(conn, "SELECT COUNT(*) AS count FROM repo_snapshots")[0]["count"] == 3
    assert fetch_all(conn, "SELECT COUNT(*) AS count FROM paper_repo_matches")[0]["count"] == 3
