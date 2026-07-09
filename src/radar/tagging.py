from __future__ import annotations

import re
import sqlite3

from radar.config import TaggingConfig
from radar.db import replace_paper_tags


def tags_for_text(text: str, keywords: dict[str, list[str]]) -> list[str]:
    normalized = text.lower()
    matches: list[str] = []
    for tag, terms in keywords.items():
        if any(_contains_term(normalized, term.lower()) for term in terms):
            matches.append(tag)
    return sorted(matches)


def tag_database(conn: sqlite3.Connection, config: TaggingConfig) -> int:
    count = 0
    for row in conn.execute("SELECT id, title, abstract FROM papers"):
        text = f"{row['title']} {row['abstract']}"
        replace_paper_tags(conn, int(row["id"]), tags_for_text(text, config.keywords))
        count += 1
    conn.commit()
    return count


def _contains_term(text: str, term: str) -> bool:
    if " " in term:
        return term in text
    return re.search(rf"\b{re.escape(term)}\b", text) is not None
