from __future__ import annotations

from datetime import UTC, datetime

from linkedin_jobs.models import SearchQuery
from linkedin_jobs.urls import build_search_url, extract_job_id, parse_posted_date


def test_build_search_url_encodes_query() -> None:
    query = SearchQuery(
        query_id="q1",
        run_id="r1",
        city_key="sf",
        city_name="SF Bay Area",
        location="San Francisco, CA",
        keyword="software engineer",
        role_family_key="swe",
        experience_key="mid",
        experience_param="f_E=4",
        time_window_days=7,
        target_weight=1.0,
        url="",
    )

    url = build_search_url(query, start=25)

    assert "keywords=software+engineer" in url
    assert "location=San+Francisco%2C+CA" in url
    assert "f_TPR=r604800" in url
    assert "f_E=4" in url
    assert "start=25" in url


def test_extract_job_id_handles_common_shapes() -> None:
    assert (
        extract_job_id("https://www.linkedin.com/jobs/view/staff-engineer-at-x-4211112222")
        == "4211112222"
    )
    assert (
        extract_job_id("https://www.linkedin.com/jobs/view/4222223333/?trackingId=abc")
        == "4222223333"
    )
    assert (
        extract_job_id("https://www.linkedin.com/jobs/search/?currentJobId=4333334444")
        == "4333334444"
    )


def test_parse_posted_date_handles_relative_and_reposted_text() -> None:
    now = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)

    assert parse_posted_date("1 day ago", now=now) == datetime(2026, 4, 30, 12, 0, tzinfo=UTC)
    assert parse_posted_date("Reposted 7 days ago", now=now) == datetime(
        2026, 4, 24, 12, 0, tzinfo=UTC
    )
    assert parse_posted_date("Just now", now=now) == now
    assert parse_posted_date("Promoted") is None
