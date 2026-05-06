from __future__ import annotations

import csv
from pathlib import Path

from linkedin_jobs.classifier import ClassificationInput, classify_title

GOLDEN = Path(__file__).parents[1] / "data" / "labels" / "golden_titles.csv"


def test_golden_titles_has_required_size() -> None:
    rows = list(csv.DictReader(GOLDEN.open(encoding="utf-8")))

    assert len(rows) >= 300


def test_golden_titles_match_classifier() -> None:
    rows = list(csv.DictReader(GOLDEN.open(encoding="utf-8")))
    mismatches = []
    for row in rows:
        result = classify_title(
            ClassificationInput(run_id="golden", job_id=row["title"], title=row["title"])
        )
        observed = (result.role_family, result.seniority, result.track)
        expected = (
            row["expected_role_family"],
            row["expected_seniority"],
            row["expected_track"],
        )
        if observed != expected:
            mismatches.append((row["title"], expected, observed))

    assert not mismatches[:20]
