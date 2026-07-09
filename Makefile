.PHONY: install test lint format init-db ingest-arxiv ingest-github tag score digest dashboard

CONFIG ?= config.yaml

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest

lint:
	ruff check .

format:
	ruff format .

init-db:
	python -m radar init-db --config $(CONFIG)

ingest-arxiv:
	python -m radar ingest-arxiv --config $(CONFIG)

ingest-github:
	python -m radar ingest-github --config $(CONFIG)

tag:
	python -m radar tag --config $(CONFIG)

score:
	python -m radar score --config $(CONFIG)

digest:
	python -m radar digest --config $(CONFIG)

dashboard:
	python -m radar dashboard --config $(CONFIG)
