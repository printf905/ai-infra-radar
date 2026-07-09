from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class Paper(BaseModel):
    arxiv_id: str
    title: str
    abstract: str = ""
    authors: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    updated_at: datetime | None = None
    url: HttpUrl | str


class Repo(BaseModel):
    github_id: int
    full_name: str
    description: str = ""
    url: HttpUrl | str
    stars: int = 0
    forks: int = 0
    language: str | None = None
    pushed_at: datetime | None = None


class Match(BaseModel):
    paper_id: int
    repo_id: int
    score: float
    reason: str


class TrendScore(BaseModel):
    tag: str
    score: float
    paper_count: int
    repo_count: int
    match_count: int
    star_count: int
