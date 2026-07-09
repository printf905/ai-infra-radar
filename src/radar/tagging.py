from __future__ import annotations

import re
import sqlite3

from radar.config import AppConfig, TaggingConfig
from radar.db import replace_paper_tags

TITLE_CONFIDENCE = 0.95
ABSTRACT_CONFIDENCE = 0.75


def tags_for_text(text: str, keywords: dict[str, list[str]]) -> list[str]:
    normalized = text.lower()
    matches: list[str] = []
    for tag, terms in keywords.items():
        if any(_contains_term(normalized, term.lower()) for term in terms):
            matches.append(tag)
    return sorted(matches)


def tags_for_paper(
    title: str,
    abstract: str,
    keywords: dict[str, list[str]],
) -> dict[str, float]:
    normalized_title = title.lower()
    normalized_abstract = abstract.lower()
    matches: dict[str, float] = {}
    for tag, terms in keywords.items():
        for term in terms:
            normalized_term = term.lower()
            if _contains_term(normalized_title, normalized_term):
                matches[tag] = max(matches.get(tag, 0.0), TITLE_CONFIDENCE)
            elif _contains_term(normalized_abstract, normalized_term):
                matches[tag] = max(matches.get(tag, 0.0), ABSTRACT_CONFIDENCE)
    return dict(sorted(matches.items()))


def tag_database(conn: sqlite3.Connection, config: AppConfig | TaggingConfig) -> int:
    keywords = config.topic_keywords if isinstance(config, AppConfig) else config.keywords
    count = 0
    for row in conn.execute("SELECT id, title, abstract FROM papers"):
        tags = tags_for_paper(str(row["title"]), str(row["abstract"]), keywords)
        replace_paper_tags(conn, int(row["id"]), tags)
        count += 1
    conn.commit()
    return count


def _contains_term(text: str, term: str) -> bool:
    if " " in term:
        return term in text
    return re.search(rf"\b{re.escape(term)}\b", text) is not None
