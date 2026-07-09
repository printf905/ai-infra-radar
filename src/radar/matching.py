from __future__ import annotations

import logging
import os
import re
import sqlite3
from collections.abc import Callable

import httpx

from radar.db import upsert_matches
from radar.models import Match

logger = logging.getLogger(__name__)

ReadmeFetcher = Callable[[str], str]


def match_database(
    conn: sqlite3.Connection,
    fetch_readme: bool = False,
    readme_fetcher: ReadmeFetcher | None = None,
) -> int:
    papers = conn.execute("SELECT id, arxiv_id, title, abstract FROM papers").fetchall()
    repos = conn.execute("SELECT id, full_name, description FROM repos").fetchall()
    readme_cache: dict[int, str] = {}
    matches: list[Match] = []

    for paper in papers:
        paper_tags = _paper_tags(conn, int(paper["id"]))
        paper_terms = _terms(f"{paper['title']} {paper['abstract']} {' '.join(paper_tags)}")
        for repo in repos:
            local_text = f"{repo['full_name']} {repo['description']}"
            readme_text = ""
            if fetch_readme and _is_candidate(paper_terms, local_text):
                readme_text = readme_cache.setdefault(
                    int(repo["id"]),
                    _fetch_repo_readme(str(repo["full_name"]), readme_fetcher),
                )
            match = match_paper_to_repo(
                paper_id=int(paper["id"]),
                repo_id=int(repo["id"]),
                arxiv_id=str(paper["arxiv_id"]),
                title=str(paper["title"]),
                abstract=str(paper["abstract"]),
                tags=paper_tags,
                repo_name=str(repo["full_name"]),
                repo_description=str(repo["description"] or ""),
                repo_readme=readme_text,
            )
            if match:
                matches.append(match)

    return upsert_matches(conn, matches)


def match_paper_to_repo(
    paper_id: int,
    repo_id: int,
    arxiv_id: str,
    title: str,
    abstract: str,
    tags: list[str],
    repo_name: str,
    repo_description: str,
    repo_readme: str = "",
) -> Match | None:
    repo_text = _normalize_text(f"{repo_name} {repo_description} {repo_readme}")
    repo_name_text = _normalize_text(repo_name)
    title_text = _normalize_text(title)

    clean_arxiv_id = _clean_arxiv_id(arxiv_id)
    if clean_arxiv_id and clean_arxiv_id in repo_text:
        return _match(paper_id, repo_id, "arxiv_id", 0.98, f"arXiv id {clean_arxiv_id}")

    if len(title_text) >= 12 and title_text in repo_text:
        return _match(paper_id, repo_id, "title_phrase", 0.9, "exact title phrase")

    acronym = method_acronym(title)
    if acronym and (
        _contains_token(repo_name_text, acronym.lower())
        or _contains_token(repo_text, acronym.lower())
    ):
        return _match(paper_id, repo_id, "acronym", 0.78, f"title acronym {acronym}")

    overlap = _topic_overlap(title, abstract, tags, repo_text)
    if overlap:
        confidence = min(0.45 + 0.08 * len(overlap), 0.72)
        return _match(
            paper_id,
            repo_id,
            "topic_overlap",
            round(confidence, 4),
            f"topic/keyword overlap: {', '.join(overlap[:8])}",
        )

    return None


def method_acronym(title: str) -> str | None:
    parenthetical = re.search(r"\(([A-Z][A-Z0-9-]{1,10})\)", title)
    if parenthetical:
        return parenthetical.group(1).replace("-", "")

    words = [
        word
        for word in re.findall(r"[A-Za-z][A-Za-z0-9-]*", title)
        if word.lower() not in _STOPWORDS
    ]
    if len(words) < 2:
        return None
    acronym = "".join(word[0] for word in words).upper()
    if 2 <= len(acronym) <= 8:
        return acronym
    return None


def fetch_github_readme(full_name: str) -> str:
    headers = {
        "Accept": "application/vnd.github.raw",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = httpx.get(
        f"https://api.github.com/repos/{full_name}/readme",
        headers=headers,
        timeout=20.0,
    )
    if response.status_code == 404:
        return ""
    if response.status_code in {403, 429}:
        logger.warning(
            "Skipping README for %s: GitHub API returned HTTP %s",
            full_name,
            response.status_code,
        )
        return ""
    response.raise_for_status()
    return response.text


def _match(
    paper_id: int,
    repo_id: int,
    match_type: str,
    confidence: float,
    reason: str,
) -> Match:
    return Match(
        paper_id=paper_id,
        repo_id=repo_id,
        score=confidence,
        reason=reason,
        match_type=match_type,
        confidence=confidence,
    )


def _paper_tags(conn: sqlite3.Connection, paper_id: int) -> list[str]:
    return [
        str(row["tag"])
        for row in conn.execute(
            "SELECT tag FROM paper_tags WHERE paper_id = ? ORDER BY tag",
            (paper_id,),
        )
    ]


def _fetch_repo_readme(full_name: str, readme_fetcher: ReadmeFetcher | None) -> str:
    try:
        return readme_fetcher(full_name) if readme_fetcher else fetch_github_readme(full_name)
    except httpx.HTTPError as exc:
        logger.warning("Skipping README for %s: %s", full_name, exc)
        return ""


def _is_candidate(paper_terms: set[str], repo_text: str) -> bool:
    return bool(paper_terms & _terms(repo_text))


def _topic_overlap(title: str, abstract: str, tags: list[str], repo_text: str) -> list[str]:
    paper_terms = _terms(f"{title} {abstract}")
    tag_terms = set()
    for tag in tags:
        tag_terms.update(_terms(tag.replace("_", " ")))
    overlap = (paper_terms | tag_terms) & _terms(repo_text)
    return sorted(overlap)


def _clean_arxiv_id(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id.lower())


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().replace("_", " ").replace("-", " ").split())


def _contains_token(text: str, token: str) -> bool:
    return re.search(rf"\b{re.escape(token)}\b", text) is not None


def _terms(text: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z0-9][a-z0-9-]{2,}", text.lower().replace("_", " "))
        if term not in _STOPWORDS
    }


_STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "into",
    "model",
    "paper",
    "the",
    "this",
    "using",
    "with",
}
