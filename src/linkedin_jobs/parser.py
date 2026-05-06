"""HTML parsers for LinkedIn job search and detail pages."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from .models import JobDetail, RawListing, Workplace, utc_now
from .urls import canonical_job_url, extract_job_id, parse_posted_date

COMMON_SKILLS = [
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "node",
    "go",
    "rust",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "sql",
    "spark",
    "pytorch",
    "tensorflow",
    "llm",
    "machine learning",
]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_search_results(
    html: str,
    *,
    run_id: str,
    query_id: str,
    page: int,
    snapshot_path: Path | None = None,
    scraped_at: datetime | None = None,
) -> list[RawListing]:
    scraped_at = scraped_at or utc_now()
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.base-search-card.job-search-card")
    if not cards:
        cards = soup.select("li.jobs-search-results__list-item, div.job-card-container")

    listings: list[RawListing] = []
    for rank, card in enumerate(cards, start=1):
        parsed = parse_listing_card(
            card,
            run_id=run_id,
            query_id=query_id,
            page=page,
            rank=rank,
            snapshot_path=snapshot_path,
            content_sha256=sha256_text(html),
            scraped_at=scraped_at,
        )
        if parsed:
            listings.append(parsed)
    return listings


def parse_listing_card(
    card: Tag,
    *,
    run_id: str,
    query_id: str,
    page: int,
    rank: int,
    snapshot_path: Path | None,
    content_sha256: str,
    scraped_at: datetime,
) -> RawListing | None:
    link = card.select_one("a.base-card__full-link[href*='/jobs/view/'], a[href*='/jobs/view/']")
    if not link:
        return None
    href = str(link.get("href") or "")
    job_id = extract_job_id(href)
    if not job_id:
        return None

    title = first_text(
        card,
        [
            ".base-search-card__title",
            ".job-search-card__title",
            "h3",
            "a.base-card__full-link",
        ],
    )
    if not title:
        title = clean_text(link.get_text(" "))
    if not title or looks_like_ui_text(title):
        return None

    company = first_text(
        card,
        [".base-search-card__subtitle", "h4", ".job-card-container__company-name"],
    )
    location = first_text(
        card,
        [".job-search-card__location", ".job-card-container__metadata-item"],
    )
    posted_text = first_text(card, [".job-search-card__listdate", "time"])
    posted_at = parse_posted_date(posted_text, now=scraped_at)

    confidence = 0.35
    confidence += 0.2 if title else 0
    confidence += 0.15 if company else 0
    confidence += 0.15 if location else 0
    confidence += 0.1 if posted_text else 0
    confidence += 0.05 if href else 0

    return RawListing(
        run_id=run_id,
        query_id=query_id,
        job_id=job_id,
        url=canonical_job_url(job_id),
        title=title,
        company=company,
        location=location,
        posted_text=posted_text,
        posted_at=posted_at,
        page=page,
        rank=rank,
        raw_snapshot_path=snapshot_path,
        content_sha256=content_sha256,
        parser_confidence=min(confidence, 1.0),
        scraped_at=scraped_at,
    )


def parse_job_detail(
    html: str,
    *,
    run_id: str,
    job_id: str,
    url: str,
    snapshot_path: Path | None = None,
    scraped_at: datetime | None = None,
) -> JobDetail:
    scraped_at = scraped_at or utc_now()
    soup = BeautifulSoup(html, "html.parser")
    description = first_text(
        soup,
        [
            ".show-more-less-html__markup",
            ".description__text",
            ".jobs-description-content__text",
            "section.description",
        ],
    )
    criteria = parse_criteria(soup)
    workplace = infer_workplace(" ".join([description or "", *criteria.values()]))
    salary_min, salary_max, currency = parse_salary(description or "")
    skills = extract_skills(description or "")
    applicants = first_text(
        soup,
        [".num-applicants__caption", ".jobs-unified-top-card__applicant-count"],
    )
    employment_type = criteria.get("Employment type") or criteria.get("Job type")

    confidence = 0.25
    confidence += 0.25 if description else 0
    confidence += 0.2 if criteria else 0
    confidence += 0.1 if workplace != "Unknown" else 0
    confidence += 0.1 if employment_type else 0
    confidence += 0.1 if skills else 0

    return JobDetail(
        run_id=run_id,
        job_id=job_id,
        url=url,
        description=description,
        workplace_type=workplace,
        employment_type=employment_type,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=currency,
        applicants_signal=applicants,
        criteria=criteria,
        skills=skills,
        raw_snapshot_path=snapshot_path,
        content_sha256=sha256_text(html),
        parser_confidence=min(confidence, 1.0),
        scraped_at=scraped_at,
    )


def parse_criteria(soup: BeautifulSoup) -> dict[str, str]:
    criteria: dict[str, str] = {}
    for item in soup.select(".description__job-criteria-item, li.description__job-criteria-item"):
        key = first_text(item, [".description__job-criteria-subheader", "h3"])
        value = first_text(item, [".description__job-criteria-text", "span"])
        if key and value:
            criteria[key] = value
    return criteria


def parse_salary(text: str) -> tuple[float | None, float | None, str | None]:
    cleaned = text.replace(",", "")
    match = re.search(
        r"\$?\s*(\d{2,3}(?:\.\d+)?)\s*(k|000)?\s*(?:-|to|–)\s*\$?\s*(\d{2,3}(?:\.\d+)?)\s*(k|000)?",
        cleaned,
        re.IGNORECASE,
    )
    if not match:
        return None, None, None
    low = float(match.group(1))
    high = float(match.group(3))
    if match.group(2) or low < 1000:
        low *= 1000
    if match.group(4) or high < 1000:
        high *= 1000
    return low, high, "USD"


def extract_skills(text: str) -> list[str]:
    lowered = text.lower()
    return sorted(
        {skill for skill in COMMON_SKILLS if re.search(rf"\b{re.escape(skill)}\b", lowered)}
    )


def infer_workplace(text: str) -> Workplace:
    lowered = text.lower()
    if "hybrid" in lowered:
        return "Hybrid"
    if "remote" in lowered or "work from home" in lowered:
        return "Remote"
    if "on-site" in lowered or "onsite" in lowered or "in office" in lowered:
        return "On-site"
    return "Unknown"


def first_text(root: Tag | BeautifulSoup, selectors: list[str]) -> str | None:
    for selector in selectors:
        element = root.select_one(selector)
        if element:
            text = clean_text(element.get_text(" "))
            if text:
                return text
    return None


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def looks_like_ui_text(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in ["sign in", "join now", "promoted", "see more"])
