"""Canonical pipeline records."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

RoleFamily = Literal[
    "SWE",
    "AI/ML",
    "Data Science",
    "Data Engineering",
    "Analytics/BI",
    "Data Operations/Annotation",
    "DevOps/SRE",
    "Infrastructure/Platform",
    "Security",
    "QA/Test",
    "Hardware/Embedded",
    "Robotics/Autonomy",
    "Research",
    "Product",
    "Program",
    "Design",
    "Management",
    "Executive",
    "Solutions/Sales Engineering",
    "Developer Relations",
    "IT/Support",
    "Customer Success/Implementation",
    "Business/Ops",
    "Admin/Operations",
    "Marketing/Growth",
    "People/Recruiting",
    "Education/Training",
    "Healthcare/Clinical",
    "Retail/Service",
    "Finance/Investment",
    "Facilities/Field Ops",
    "Other",
]
Seniority = Literal[
    "Intern",
    "Entry",
    "Mid",
    "Senior",
    "Staff+",
    "Manager",
    "Director+",
    "Executive",
]
Track = Literal["IC", "Manager", "Executive", "Non-technical"]
Workplace = Literal["Remote", "Hybrid", "On-site", "Unknown"]
Severity = Literal["info", "warning", "error"]


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


class SearchQuery(BaseModel):
    query_id: str
    run_id: str
    city_key: str
    city_name: str
    location: str
    keyword: str
    role_family_key: str
    experience_key: str
    experience_param: str
    time_window_days: int
    target_weight: float
    url: str


class RawListing(BaseModel):
    run_id: str
    query_id: str
    job_id: str
    url: str
    title: str
    company: str | None = None
    location: str | None = None
    posted_text: str | None = None
    posted_at: datetime | None = None
    page: int
    rank: int
    raw_snapshot_path: Path | None = None
    content_sha256: str | None = None
    parser_confidence: float = Field(ge=0, le=1)
    scraped_at: datetime = Field(default_factory=utc_now)
    extraction_status: str = "complete"

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title cannot be empty")
        return cleaned

    @field_validator("url")
    @classmethod
    def url_must_parse(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be absolute HTTP(S)")
        return value


class JobDetail(BaseModel):
    run_id: str
    job_id: str
    url: str
    description: str | None = None
    workplace_type: Workplace = "Unknown"
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    applicants_signal: str | None = None
    criteria: dict[str, str] = Field(default_factory=dict)
    skills: list[str] = Field(default_factory=list)
    raw_snapshot_path: Path | None = None
    content_sha256: str | None = None
    parser_confidence: float = Field(default=0, ge=0, le=1)
    scraped_at: datetime = Field(default_factory=utc_now)
    extraction_status: str = "complete"


class Classification(BaseModel):
    run_id: str
    job_id: str
    role_family: RoleFamily
    seniority: Seniority
    track: Track
    workplace: Workplace = "Unknown"
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
    classified_at: datetime = Field(default_factory=utc_now)


class QualityIssue(BaseModel):
    run_id: str
    scope: str
    severity: Severity
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
