from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from linkedin_jobs.cli import app
from linkedin_jobs.config import load_config
from linkedin_jobs.quality import validate_run
from linkedin_jobs.report import generate_report
from linkedin_jobs.storage import JobStore

FIXTURES = Path(__file__).parent / "fixtures"
RUN_ID = "fixture_run"


def write_test_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
name: fixture
description: Fixture test config
database_path: {tmp_path / "jobs.duckdb"}
raw_snapshot_dir: {tmp_path / "raw"}
report_dir: {tmp_path / "reports"}
target_population: Fixture jobs
time_window_days: 7
max_pages_per_query: 1
detail_enrichment: false
headless: true
request_delay_seconds:
  min: 0
  max: 0
locations:
  - key: sf_bay_area
    name: SF Bay Area
    linkedin_locations: ["San Francisco, CA"]
    weight: 1.0
role_families:
  - key: swe
    name: Software Engineering
    keywords: ["software engineer"]
experience_levels:
  - key: mid_senior
    linkedin_param: f_E=4
    weight: 1.0
""",
        encoding="utf-8",
    )
    return config_path


def test_fixture_e2e_load_classify_validate_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    config_path = write_test_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "load-fixture",
            "--config",
            str(config_path),
            "--run-id",
            RUN_ID,
            "--search-html",
            str(FIXTURES / "search_results.html"),
            "--detail-html",
            str(FIXTURES / "detail_page.html"),
        ],
    )

    assert result.exit_code == 0, result.output
    store = JobStore(tmp_path / "jobs.duckdb")
    unique_jobs = store.unique_jobs(RUN_ID)
    assert len(unique_jobs) == 3
    assert store.listing_discovery_paths(RUN_ID)[0]["discovery_count"] == 1

    config = load_config(config_path)
    issues = validate_run(store, config, RUN_ID)
    assert not [issue for issue in issues if issue.severity == "error"]

    paths = generate_report(store, run_id=RUN_ID, report_root=tmp_path / "reports")
    assert paths["markdown"].exists()
    assert paths["html"].exists()
    report_text = paths["markdown"].read_text(encoding="utf-8")
    assert "Weighted Role Family Estimate" in report_text
    assert "Technical Program Manager" not in report_text

    export_paths = store.export_parquet(RUN_ID, tmp_path / "processed" / RUN_ID)
    assert len(export_paths) == 9
    assert all(path.exists() for path in export_paths)
    assert (tmp_path / "processed" / RUN_ID / "canonical_jobs.parquet").exists()
    assert not (Path.cwd() / RUN_ID).exists()
    store.close()
