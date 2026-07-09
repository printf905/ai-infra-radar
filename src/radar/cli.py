from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from radar.collectors.arxiv_collector import ingest_arxiv as ingest_arxiv_feed
from radar.collectors.github_collector import ingest_github as ingest_github_feed
from radar.config import AppConfig, load_config
from radar.db import connect, init_db
from radar.digest import write_digest
from radar.matching import match_database
from radar.sample_data import load_sample_data
from radar.scoring import score_database
from radar.tagging import tag_database

app = typer.Typer(help="AI Infra Radar CLI")
ConfigPath = Annotated[Path, typer.Option("--config", "-c")]
DbPath = Annotated[Path | None, typer.Option("--db")]
DigestDate = Annotated[str, typer.Option("--date")]
SampleDbPath = Annotated[Path, typer.Option("--db")]


def _load(config: Path, db: Path | None = None) -> tuple[AppConfig, sqlite3.Connection]:
    cfg = load_config(config)
    conn = connect(db or cfg.database_path)
    init_db(conn)
    return cfg, conn


@app.command("init-db")
def init_db_command(config: ConfigPath = Path("config.yaml")) -> None:
    cfg, conn = _load(config)
    conn.close()
    typer.echo(f"Initialized database at {cfg.database_path}")


@app.command("ingest-arxiv")
def ingest_arxiv(config: ConfigPath = Path("config.yaml"), db: DbPath = None) -> None:
    cfg, conn = _load(config, db)
    if not cfg.arxiv.enabled:
        typer.echo("arXiv collector disabled")
        return
    result = ingest_arxiv_feed(conn, cfg)
    conn.close()
    typer.echo(f"Fetched {result.fetched} arXiv papers; upserted {result.upserted}")


@app.command("ingest-github")
def ingest_github(config: ConfigPath = Path("config.yaml"), db: DbPath = None) -> None:
    cfg, conn = _load(config, db)
    if not cfg.github.enabled:
        typer.echo("GitHub collector disabled")
        return
    result = ingest_github_feed(conn, cfg)
    conn.close()
    typer.echo(
        f"Fetched {result.fetched} GitHub repositories; "
        f"upserted {result.upserted}; snapshots {result.snapshots}"
    )


@app.command("tag")
def tag(config: ConfigPath = Path("config.yaml"), db: DbPath = None) -> None:
    cfg, conn = _load(config, db)
    count = tag_database(conn, cfg)
    conn.close()
    typer.echo(f"Tagged {count} papers")


@app.command("tag-papers")
def tag_papers(config: ConfigPath = Path("config.yaml"), db: DbPath = None) -> None:
    cfg, conn = _load(config, db)
    count = tag_database(conn, cfg)
    conn.close()
    typer.echo(f"Tagged {count} papers")


@app.command("match")
def match(config: ConfigPath = Path("config.yaml")) -> None:
    _, conn = _load(config)
    count = match_database(conn)
    conn.close()
    typer.echo(f"Upserted {count} paper/repo matches")


@app.command("score")
def score(config: ConfigPath = Path("config.yaml"), db: DbPath = None) -> None:
    cfg, conn = _load(config, db)
    count = score_database(conn, cfg)
    conn.close()
    typer.echo(f"Computed {count} paper scores")


@app.command("digest")
def digest(
    config: ConfigPath = Path("config.yaml"),
    db: DbPath = None,
    digest_date: DigestDate = "today",
) -> None:
    cfg, conn = _load(config, db)
    path = write_digest(conn, cfg.reports_dir, _parse_digest_date(digest_date))
    conn.close()
    typer.echo(f"Wrote {path}")


@app.command("load-sample")
def load_sample(db: SampleDbPath = Path("data/sample/sample.db")) -> None:
    conn = connect(db)
    result = load_sample_data(conn)
    conn.close()
    typer.echo(
        f"Loaded sample data into {db}: "
        f"{result.papers} papers, {result.repos} repos, "
        f"{result.tags} tags, {result.scores} scores, "
        f"{result.snapshots} snapshots, {result.matches} matches"
    )
    typer.echo(
        "Sample digest supported. Run: "
        f"python -m radar.cli digest --db {db} --date 2026-07-09"
    )


@app.command("dashboard")
def dashboard(config: ConfigPath = Path("config.yaml")) -> None:
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app/streamlit_app.py",
        "--",
        "--config",
        str(config),
    ]
    raise typer.Exit(subprocess.call(command))


def main() -> None:
    app()


def _parse_digest_date(value: str) -> date:
    if value == "today":
        return date.today()
    return date.fromisoformat(value)


if __name__ == "__main__":
    main()
