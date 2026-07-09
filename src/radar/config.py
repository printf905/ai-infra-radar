from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ArxivConfig(BaseModel):
    enabled: bool = True
    queries: list[str] = Field(default_factory=list)
    max_results: int = 25


class GitHubConfig(BaseModel):
    enabled: bool = True
    queries: list[str] = Field(default_factory=list)
    max_results: int = 25
    token_env: str = "GITHUB_TOKEN"


class TaggingConfig(BaseModel):
    keywords: dict[str, list[str]] = Field(default_factory=dict)


class ScoringConfig(BaseModel):
    paper_weight: float = 1.0
    repo_weight: float = 1.0
    star_weight: float = 0.05
    match_weight: float = 2.0


class AppConfig(BaseModel):
    database_path: Path = Path("data/radar.sqlite")
    reports_dir: Path = Path("reports")
    arxiv: ArxivConfig = Field(default_factory=ArxivConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    tagging: TaggingConfig = Field(default_factory=TaggingConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)


def load_config(path: Path | str = "config.yaml") -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        fallback = Path("config.example.yaml")
        if fallback.exists():
            config_path = fallback
        else:
            return AppConfig()

    with config_path.open("r", encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle) or {}
    return AppConfig.model_validate(raw)
