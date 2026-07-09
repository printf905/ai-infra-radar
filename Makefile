.PHONY: install pipeline dashboard digest test lint demo-data demo-dashboard

DB ?= data/radar.db
DEMO_DB ?= data/sample/sample.db

install:
	python -m pip install -e ".[dev]"

pipeline:
	python -m radar.cli ingest-arxiv --config config.example.yaml --db $(DB)
	python -m radar.cli ingest-github --config config.example.yaml --db $(DB)
	python -m radar.cli tag-papers --config config.example.yaml --db $(DB)
	python -m radar.cli score --config config.example.yaml --db $(DB)
	python -m radar.cli match-repos --db $(DB)
	python -m radar.cli digest --config config.example.yaml --db $(DB) --date today

dashboard:
	streamlit run app/streamlit_app.py

digest:
	python -m radar.cli digest --config config.example.yaml --db $(DB) --date today

test:
	python -m pytest

lint:
	ruff check .

demo-data:
	python -m radar.cli load-sample --db $(DEMO_DB)

demo-dashboard:
	RADAR_DB_PATH=$(DEMO_DB) streamlit run app/streamlit_app.py
