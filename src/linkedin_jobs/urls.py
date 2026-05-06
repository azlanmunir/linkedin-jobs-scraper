"""URL building and date parsing helpers."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, quote_plus, urlparse

from .models import SearchQuery

LINKEDIN_JOBS_SEARCH_URL = "https://www.linkedin.com/jobs/search/"


def build_search_url(query: SearchQuery, *, start: int = 0) -> str:
    params = [
        f"keywords={quote_plus(query.keyword)}",
        f"location={quote_plus(query.location)}",
        f"f_TPR=r{query.time_window_days * 86_400}",
        query.experience_param,
        "sortBy=DD",
    ]
    if start:
        params.append(f"start={start}")
    return LINKEDIN_JOBS_SEARCH_URL + "?" + "&".join(params)


def extract_job_id(url: str) -> str | None:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key in ("currentJobId", "jobId"):
        if params.get(key):
            return params[key][0]

    match = re.search(r"/jobs/view/(?:.*?-)?(\d+)/?$", parsed.path)
    if match:
        return match.group(1)

    match = re.search(r"(?:^|[?&])currentJobId=(\d+)", url)
    return match.group(1) if match else None


def canonical_job_url(job_id: str) -> str:
    return f"https://www.linkedin.com/jobs/view/{job_id}/"


def parse_posted_date(text: str | None, *, now: datetime | None = None) -> datetime | None:
    if not text:
        return None
    now = now or datetime.now(UTC)
    lowered = text.lower().strip()
    lowered = lowered.replace("reposted", "").replace("posted", "").strip()
    if "just now" in lowered or "today" in lowered:
        return now
    match = re.search(r"(\d+)\s*(minute|hour|day|week|month)s?\s*ago", lowered)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "minute":
        delta = timedelta(minutes=amount)
    elif unit == "hour":
        delta = timedelta(hours=amount)
    elif unit == "day":
        delta = timedelta(days=amount)
    elif unit == "week":
        delta = timedelta(weeks=amount)
    else:
        delta = timedelta(days=30 * amount)
    return now - delta
