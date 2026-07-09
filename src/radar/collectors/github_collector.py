from __future__ import annotations

import os
from datetime import datetime

import httpx

from radar.config import GitHubConfig
from radar.models import Repo

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"


def collect_github(config: GitHubConfig) -> list[Repo]:
    repos: dict[int, Repo] = {}
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv(config.token_env)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with httpx.Client(timeout=30.0, headers=headers) as client:
        for query in config.queries:
            response = client.get(
                GITHUB_SEARCH_URL,
                params={
                    "q": query,
                    "sort": "updated",
                    "order": "desc",
                    "per_page": config.max_results,
                },
            )
            response.raise_for_status()
            for item in response.json().get("items", []):
                repo = _item_to_repo(item)
                repos[repo.github_id] = repo
    return list(repos.values())


def _item_to_repo(item: dict[str, object]) -> Repo:
    return Repo(
        github_id=int(item["id"]),
        full_name=str(item["full_name"]),
        description=str(item.get("description") or ""),
        url=str(item["html_url"]),
        stars=int(item.get("stargazers_count") or 0),
        forks=int(item.get("forks_count") or 0),
        language=item.get("language") if isinstance(item.get("language"), str) else None,
        pushed_at=_parse_github_datetime(item.get("pushed_at")),
    )


def _parse_github_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
