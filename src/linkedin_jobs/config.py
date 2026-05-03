"""Typed configuration for market-intelligence runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class DelayConfig(BaseModel):
    min: float = 1.0
    max: float = 3.0

    @model_validator(mode="after")
    def validate_bounds(self) -> DelayConfig:
        if self.min < 0 or self.max < self.min:
            raise ValueError("request_delay_seconds must satisfy 0 <= min <= max")
        return self


class LocationConfig(BaseModel):
    key: str
    name: str
    linkedin_locations: list[str] = Field(min_length=1)
    weight: float = Field(gt=0)


class RoleFamilyConfig(BaseModel):
    key: str
    name: str
    keywords: list[str] = Field(min_length=1)


class ExperienceLevelConfig(BaseModel):
    key: str
    linkedin_param: str
    weight: float = Field(gt=0)


class PipelineConfig(BaseModel):
    name: str
    description: str = ""
    database_path: Path = Path("data/db/jobs.duckdb")
    raw_snapshot_dir: Path = Path("data/raw")
    report_dir: Path = Path("reports")
    target_population: str
    time_window_days: int = Field(default=7, ge=1, le=30)
    max_pages_per_query: int = Field(default=3, ge=1, le=40)
    detail_enrichment: bool = True
    headless: bool = True
    request_delay_seconds: DelayConfig = Field(default_factory=DelayConfig)
    locations: list[LocationConfig] = Field(min_length=1)
    role_families: list[RoleFamilyConfig] = Field(min_length=1)
    experience_levels: list[ExperienceLevelConfig] = Field(min_length=1)

    @field_validator("database_path", "raw_snapshot_dir", "report_dir", mode="before")
    @classmethod
    def expand_paths(cls, value: Any) -> Path:
        return Path(value)

    @model_validator(mode="after")
    def validate_weights(self) -> PipelineConfig:
        total_location_weight = sum(location.weight for location in self.locations)
        total_experience_weight = sum(level.weight for level in self.experience_levels)
        if abs(total_location_weight - 1.0) > 0.01:
            raise ValueError(f"location weights must sum to 1.0; got {total_location_weight:.3f}")
        if abs(total_experience_weight - 1.0) > 0.01:
            raise ValueError(
                f"experience weights must sum to 1.0; got {total_experience_weight:.3f}"
            )
        return self

    def to_canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    @property
    def config_hash(self) -> str:
        return hashlib.sha256(self.to_canonical_json().encode("utf-8")).hexdigest()


def load_config(path: Path) -> PipelineConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected mapping config in {path}")
    return PipelineConfig.model_validate(payload)
