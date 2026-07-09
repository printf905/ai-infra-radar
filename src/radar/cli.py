from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

from radar.collectors.arxiv_collector import collect_arxiv
from radar.collectors.github_collector import collect_github
from radar.config import AppConfig, load_config
from radar.db import connect, init_db, upsert_papers, upsert_repos
from radar.digest import write_digest
from radar.matching import match_database
from radar.scoring import score_database
from radar.tagging import tag_database

app = typer.Typer(help="AI Infra Radar CLI")
ConfigPath = Annotated[Path, typer.Option("--config", "-c")]


def _load(config: Path) -> tuple[AppConfig, object]:
    cfg = load_config(config)
    conn = connect(cfg.database_path)
    init_db(conn)
    return cfg, conn


@app.command("init-db")
def init_db_command(config: ConfigPath = Path("config.yaml")) -> None:
    cfg, conn = _load(config)
    conn.close()
    typer.echo(f"Initialized database at {cfg.database_path}")


@app.command("ingest-arxiv")
def ingest_arxiv(config: ConfigPath = Path("config.yaml")) -> None:
    cfg, conn = _load(config)
    if not cfg.arxiv.enabled:
        typer.echo("arXiv collector disabled")
        return
    count = upsert_papers(conn, collect_arxiv(cfg.arxiv))
    conn.close()
    typer.echo(f"Upserted {count} arXiv papers")


@app.command("ingest-github")
def ingest_github(config: ConfigPath = Path("config.yaml")) -> None:
    cfg, conn = _load(config)
    if not cfg.github.enabled:
        typer.echo("GitHub collector disabled")
        return
    count = upsert_repos(conn, collect_github(cfg.github))
    conn.close()
    typer.echo(f"Upserted {count} GitHub repositories")


@app.command("tag")
def tag(config: ConfigPath = Path("config.yaml")) -> None:
    cfg, conn = _load(config)
    count = tag_database(conn, cfg.tagging)
    conn.close()
    typer.echo(f"Tagged {count} records")


@app.command("match")
def match(config: ConfigPath = Path("config.yaml")) -> None:
    _, conn = _load(config)
    count = match_database(conn)
    conn.close()
    typer.echo(f"Upserted {count} paper/repo matches")


@app.command("score")
def score(config: ConfigPath = Path("config.yaml")) -> None:
    cfg, conn = _load(config)
    count = score_database(conn, cfg.scoring)
    conn.close()
    typer.echo(f"Computed {count} trend scores")


@app.command("digest")
def digest(config: ConfigPath = Path("config.yaml")) -> None:
    cfg, conn = _load(config)
    path = write_digest(conn, cfg.reports_dir)
    conn.close()
    typer.echo(f"Wrote {path}")


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


if __name__ == "__main__":
    main()
