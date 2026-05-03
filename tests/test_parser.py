from __future__ import annotations

from pathlib import Path

from linkedin_jobs.parser import parse_job_detail, parse_search_results

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_search_results_fixture() -> None:
    html = (FIXTURES / "search_results.html").read_text(encoding="utf-8")

    listings = parse_search_results(html, run_id="r1", query_id="q1", page=1)

    assert len(listings) == 3
    assert listings[0].job_id == "4211112222"
    assert listings[0].title == "Staff Software Engineer, Infrastructure"
    assert listings[0].company == "Notion"
    assert listings[1].job_id == "4222223333"
    assert listings[2].title == "Product Manager, Growth"
    assert all(listing.parser_confidence >= 0.8 for listing in listings)


def test_parse_detail_fixture() -> None:
    html = (FIXTURES / "detail_page.html").read_text(encoding="utf-8")

    detail = parse_job_detail(
        html,
        run_id="r1",
        job_id="4211112222",
        url="https://www.linkedin.com/jobs/view/4211112222/",
    )

    assert detail.workplace_type == "Hybrid"
    assert detail.employment_type == "Full-time"
    assert detail.salary_min == 180000
    assert detail.salary_max == 240000
    assert set(detail.skills) >= {"python", "aws", "kubernetes", "machine learning"}
    assert detail.parser_confidence >= 0.8
