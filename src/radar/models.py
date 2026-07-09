from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, HttpUrl


class Paper(BaseModel):
    arxiv_id: str
    title: str
    abstract: str = ""
    authors: list[str] = Field(default_factory=list)
    primary_category: str | None = None
    categories: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    updated_at: datetime | None = None
    url: HttpUrl | str
    pdf_url: HttpUrl | str | None = None


class Repo(BaseModel):
    github_id: int
    full_name: str
    description: str = ""
    url: HttpUrl | str
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    language: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    pushed_at: datetime | None = None


class RepoSnapshot(BaseModel):
    repo_id: int
    captured_at: date
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    pushed_at: datetime | None = None


class PaperTag(BaseModel):
    paper_id: int
    tag: str
    source: str = "rules"


class PaperRepoMatch(BaseModel):
    paper_id: int
    repo_id: int
    score: float
    reason: str


class Match(PaperRepoMatch):
    pass


class DailyScore(BaseModel):
    score_date: date
    tag: str
    score: float
    paper_count: int
    repo_count: int
    match_count: int
    star_count: int


class TrendScore(BaseModel):
    tag: str
    score: float
    paper_count: int
    repo_count: int
    match_count: int
    star_count: int


class DigestRecord(BaseModel):
    digest_date: date
    path: str
    title: str
    content: str = ""
