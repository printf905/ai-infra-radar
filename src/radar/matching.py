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
STRONG_MATCH_TYPES = {"arxiv_id", "title_phrase", "acronym", "title_similarity"}


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
        paper_id = int(paper["id"])
        paper_tags = _paper_tags(conn, paper_id)
        paper_terms = _terms(f"{paper['title']} {paper['abstract']} {' '.join(paper_tags)}")
        paper_matches: dict[int, Match] = {}

        for repo in repos:
            repo_id = int(repo["id"])
            local_text = f"{repo['full_name']} {repo['description']}"
            readme_text = ""
            if fetch_readme and _is_candidate(paper_terms, local_text):
                readme_text = readme_cache.setdefault(
                    repo_id,
                    _fetch_repo_readme(str(repo["full_name"]), readme_fetcher),
                )
            match = match_paper_to_repo(
                paper_id=paper_id,
                repo_id=repo_id,
                arxiv_id=str(paper["arxiv_id"]),
                title=str(paper["title"]),
                abstract=str(paper["abstract"]),
                tags=paper_tags,
                repo_name=str(repo["full_name"]),
                repo_description=str(repo["description"] or ""),
                repo_readme=readme_text,
            )
            if not match:
                continue
            existing = paper_matches.get(repo_id)
            if existing is None or float(match.confidence or 0.0) > float(
                existing.confidence or 0.0
            ):
                paper_matches[repo_id] = match

        matches.extend(
            sorted(
                paper_matches.values(),
                key=lambda item: float(item.confidence or 0.0),
                reverse=True,
            )[:3]
        )

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
    del abstract, tags
    repo_text = f"{repo_name} {repo_description} {repo_readme}"
    repo_text_lower = repo_text.lower()
    repo_tokens = _terms(repo_text)
    repo_text_normalized = _normalize_text(repo_text)
    title_tokens = _terms(title)

    clean_arxiv_id = _clean_arxiv_id(arxiv_id)
    if clean_arxiv_id and clean_arxiv_id in repo_text_lower:
        return _match(paper_id, repo_id, "arxiv_id", 0.95, f"arXiv id {clean_arxiv_id}")

    title_phrase = _meaningful_title_phrase(title)
    if title_phrase and title_phrase in " ".join(_meaningful_tokens(repo_text)):
        return _match(paper_id, repo_id, "title_phrase", 0.9, "exact meaningful title phrase")

    acronym = method_acronym(title)
    acronym_token = acronym.lower() if acronym else ""
    title_keyword_overlap = sorted((title_tokens - {acronym_token}) & repo_tokens)
    if acronym and _contains_token(repo_text_normalized, acronym.lower()) and title_keyword_overlap:
        return _match(
            paper_id,
            repo_id,
            "acronym",
            0.75,
            f"title acronym {acronym}; title keyword overlap: {title_keyword_overlap[0]}",
        )

    similarity = title_similarity(title, repo_text)
    if similarity >= 0.35:
        confidence = round(min(0.70 + (similarity - 0.35) * 0.30, 0.85), 4)
        return _match(
            paper_id,
            repo_id,
            "title_similarity",
            confidence,
            f"title token similarity {similarity:.2f}",
        )

    return None


def method_acronym(title: str) -> str | None:
    parenthetical = re.search(r"\(([A-Z][A-Z0-9-]{2,10})\)", title)
    if parenthetical:
        return parenthetical.group(1).replace("-", "")

    words = _meaningful_tokens(title)
    if len(words) < 3:
        return None
    acronym = "".join(word[0] for word in words).upper()
    if 3 <= len(acronym) <= 8:
        return acronym
    return None


def title_similarity(title: str, repo_text: str) -> float:
    title_tokens = _terms(title)
    if not title_tokens:
        return 0.0
    repo_tokens = _terms(repo_text)
    if not repo_tokens:
        return 0.0
    return len(title_tokens & repo_tokens) / len(title_tokens)


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


def _clean_arxiv_id(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id.lower())


def _meaningful_title_phrase(title: str) -> str | None:
    tokens = _meaningful_tokens(title)
    if len(tokens) < 4:
        return None
    return " ".join(tokens)


def _normalize_text(text: str) -> str:
    return " ".join(_raw_tokens(text))


def _contains_token(text: str, token: str) -> bool:
    return re.search(rf"\b{re.escape(token)}\b", text) is not None


def _terms(text: str) -> set[str]:
    return set(_meaningful_tokens(text))


def _meaningful_tokens(text: str) -> list[str]:
    return [
        token
        for token in _raw_tokens(text)
        if len(token) >= 3 and token not in _STOPWORDS and token not in _GENERIC_AI_TERMS
    ]


def _raw_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


_STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "into",
    "of",
    "the",
    "this",
    "using",
    "with",
}

_GENERIC_AI_TERMS = {
    "agent",
    "agents",
    "ai",
    "efficient",
    "inference",
    "language",
    "learning",
    "llm",
    "model",
    "models",
    "neural",
    "paper",
    "training",
}
