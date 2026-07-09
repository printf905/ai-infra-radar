# AGENTS.md

## Project Overview

AI Infra Radar tracks which AI infrastructure research ideas are turning into real code. It ingests arXiv papers and GitHub repositories, stores normalized records in SQLite, applies local rule-based tags, matches likely related papers and repos, computes simple momentum scores, and emits Markdown digests plus a Streamlit dashboard.

## Repo Layout

```text
src/radar/              Python package
src/radar/collectors/   arXiv and GitHub API collectors
app/                    Streamlit dashboard
tests/                  pytest tests for core logic
data/                   local SQLite databases and sample data
reports/                generated Markdown digests
docs/                   documentation assets
.github/workflows/      automation placeholders
```

## Install

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp config.example.yaml config.yaml
python -m radar init-db
```

## Tests and Lint

```bash
python -m pytest
ruff check .
ruff format .
```

## CLI

```bash
python -m radar init-db
python -m radar ingest-arxiv --config config.yaml
python -m radar ingest-github --config config.yaml
python -m radar tag --config config.yaml
python -m radar match --config config.yaml
python -m radar score --config config.yaml
python -m radar digest --config config.yaml
python -m radar dashboard --config config.yaml
```

## Engineering Conventions

- Keep v0.1 simple and local-first.
- Prefer deterministic code paths over external services.
- Use public APIs only; do not add HTML scraping.
- Keep ingestion idempotent with SQLite upserts.
- Add type hints to new public functions.
- Keep files small and focused.
- Do not hardcode personal paths.
- Do not commit secrets or real API keys.
- Add tests for core logic before expanding behavior.
- Preserve user changes in the working tree.

## Definition of Done

For each task:

- The requested behavior is implemented.
- Core logic has focused tests.
- `python -m pytest` passes, or failures are documented.
- `ruff check .` passes, or failures are documented.
- Public commands and config examples are updated when behavior changes.
- No secrets, generated databases, or unrelated local files are committed.
