# AI Infra Radar

Track which AI research ideas are turning into real code.

AI Infra Radar is a local-first open-source data product for monitoring AI infrastructure research trends. The first version tracks arXiv papers and GitHub repositories, stores them in SQLite, tags infrastructure themes, matches papers to repos, scores momentum, and generates Markdown digests plus a Streamlit dashboard.

## Architecture

```text
config.yaml
  -> collectors
  -> SQLite
  -> tagging
  -> paper/repo matching
  -> scoring
  -> Markdown digest
  -> Streamlit dashboard
```

The project intentionally starts simple:

- Public APIs only: arXiv Atom feeds and GitHub Search API.
- No paid LLM API requirement.
- No fragile HTML scraping.
- Local SQLite database with idempotent upserts.
- Small typed Python modules that can be tested without network access.

## Quick Start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp config.example.yaml config.yaml
python -m radar init-db
```

## Example Commands

```bash
python -m radar ingest-arxiv --config config.yaml
python -m radar ingest-github --config config.yaml
python -m radar tag --config config.yaml
python -m radar match --config config.yaml
python -m radar score --config config.yaml
python -m radar digest --config config.yaml --date today
python -m radar dashboard --config config.yaml
streamlit run app/streamlit_app.py
```

Equivalent Make targets are available:

```bash
make init-db
make ingest-arxiv
make ingest-github
make tag
make score
make digest
make dashboard
```

## Roadmap

- v0.1: arXiv and GitHub collectors, SQLite schema, rule-based tagging, simple matching, scoring, digest, dashboard.
- v0.2: richer trend queries, better deduplication, saved search presets, expanded tests.
- v0.3: Hugging Face dataset/model integration.
- Later: hosted-friendly deployment docs, richer evaluation of paper-to-code adoption, optional embeddings.

## Open-Source Positioning

AI Infra Radar is designed as a transparent local-first tool for researchers, engineers, investors, and open-source maintainers who want to understand which AI infrastructure ideas are gaining implementation traction. It should remain useful without proprietary APIs, hidden datasets, or secret prompts.
