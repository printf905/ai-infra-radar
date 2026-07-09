from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

import feedparser
import httpx

from radar.config import ArxivConfig
from radar.models import Paper

ARXIV_API_URL = "https://export.arxiv.org/api/query"


def collect_arxiv(config: ArxivConfig) -> list[Paper]:
    papers: dict[str, Paper] = {}
    for query in config.queries:
        params = urlencode(
            {
                "search_query": query,
                "start": 0,
                "max_results": config.max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
        )
        response = httpx.get(f"{ARXIV_API_URL}?{params}", timeout=30.0)
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        for entry in feed.entries:
            paper = _entry_to_paper(entry)
            papers[paper.arxiv_id] = paper
    return list(papers.values())


def _entry_to_paper(entry: object) -> Paper:
    entry_id = str(getattr(entry, "id", ""))
    arxiv_id = entry_id.rsplit("/", maxsplit=1)[-1]
    authors = [
        author.name
        for author in getattr(entry, "authors", [])
        if getattr(author, "name", None)
    ]
    return Paper(
        arxiv_id=arxiv_id,
        title=_clean_text(str(getattr(entry, "title", ""))),
        abstract=_clean_text(str(getattr(entry, "summary", ""))),
        authors=authors,
        published_at=_parse_datetime(getattr(entry, "published", None)),
        updated_at=_parse_datetime(getattr(entry, "updated", None)),
        url=entry_id,
    )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def _clean_text(value: str) -> str:
    return " ".join(value.split())
