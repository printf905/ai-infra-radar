from __future__ import annotations

import sqlite3


def search(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[sqlite3.Row]:
    pattern = f"%{query}%"
    return list(
        conn.execute(
            """
            SELECT 'paper' AS item_type, title AS name, abstract AS description, url
            FROM papers
            WHERE title LIKE ? OR abstract LIKE ?
            UNION ALL
            SELECT 'repo' AS item_type, full_name AS name, description, url
            FROM repos
            WHERE full_name LIKE ? OR description LIKE ?
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, limit),
        ).fetchall()
    )
