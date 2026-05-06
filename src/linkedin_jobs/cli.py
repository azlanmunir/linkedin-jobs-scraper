"""Command-line interface for the jobs market-intelligence pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from .classifier import ClassificationInput, classify_title
from .collector import collect as collect_live
from .collector import enrich as enrich_live
from .config import load_config
from .parser import parse_job_detail, parse_search_results
from .quality import validate_run as validate_run_quality
from .quality import write_qa_report
from .report import generate_report
from .sampling import generate_queries
from .storage import JobStore
from .urls import canonical_job_url

app = typer.Typer(help="LinkedIn jobs market-intelligence pipeline.")

ConfigOption = Annotated[Path, typer.Option("--config", "-c")]
RunIdOption = Annotated[str, typer.Option("--run-id")]
OptionalRunIdOption = Annotated[str | None, typer.Option("--run-id")]
LimitOption = Annotated[int | None, typer.Option("--limit")]
EnrichDetailsOption = Annotated[bool | None, typer.Option("--enrich-details/--no-enrich-details")]
SearchHtmlOption = Annotated[Path, typer.Option("--search-html")]
DetailHtmlOption = Annotated[Path | None, typer.Option("--detail-html")]


@app.command()
def collect(
    config: ConfigOption = Path("configs/market_us_tech.yaml"),
    run_id: OptionalRunIdOption = None,
) -> None:
    """Collect search-result listing snapshots into DuckDB."""
    loaded = load_config(config)
    created_run_id = collect_live(loaded, run_id=run_id)
    typer.echo(created_run_id)


@app.command()
def enrich(
    run_id: RunIdOption,
    config: ConfigOption = Path("configs/market_us_tech.yaml"),
    limit: LimitOption = None,
) -> None:
    """Enrich collected jobs by visiting detail pages."""
    loaded = load_config(config)
    count = enrich_live(loaded, run_id=run_id, limit=limit)
    typer.echo(json.dumps({"run_id": run_id, "details_completed": count}, indent=2))


@app.command(name="classify")
def classify_command(
    run_id: RunIdOption,
    config: ConfigOption = Path("configs/market_us_tech.yaml"),
) -> None:
    """Classify deduplicated jobs by role family, seniority, track, and workplace."""
    loaded = load_config(config)
    store = JobStore(loaded.database_path)
    count = classify_run(store, run_id)
    store.close()
    typer.echo(json.dumps({"run_id": run_id, "classified": count}, indent=2))


@app.command(name="validate")
def validate_command(
    run_id: RunIdOption,
    config: ConfigOption = Path("configs/market_us_tech.yaml"),
) -> None:
    """Run data-quality checks and write the QA report."""
    loaded = load_config(config)
    store = JobStore(loaded.database_path)
    issues = validate_run_quality(store, loaded, run_id)
    qa_path = loaded.report_dir / run_id / "qa_report.md"
    write_qa_report(qa_path, issues)
    store.close()
    typer.echo(
        json.dumps(
            {"run_id": run_id, "issues": len(issues), "qa_report": str(qa_path)},
            indent=2,
        )
    )


@app.command(name="report")
def report_command(
    run_id: RunIdOption,
    config: ConfigOption = Path("configs/market_us_tech.yaml"),
) -> None:
    """Generate Markdown/HTML market report and charts."""
    loaded = load_config(config)
    store = JobStore(loaded.database_path)
    paths = generate_report(store, run_id=run_id, report_root=loaded.report_dir)
    export_dir = Path("data/processed") / run_id
    parquet_paths = store.export_parquet(run_id, export_dir)
    store.close()
    payload: dict[str, object] = {key: str(value) for key, value in paths.items()}
    payload["parquet_exports"] = [str(path) for path in parquet_paths]
    typer.echo(json.dumps(payload, indent=2))


@app.command(name="status")
def status_command(
    run_id: RunIdOption,
    config: ConfigOption = Path("configs/market_us_tech.yaml"),
) -> None:
    """Print run progress from DuckDB."""
    loaded = load_config(config)
    store = JobStore(loaded.database_path)
    query_rows = store.conn.execute(
        """
        SELECT status, COUNT(*)
        FROM search_queries
        WHERE run_id = ?
        GROUP BY status
        ORDER BY status
        """,
        [run_id],
    ).fetchall()
    failed_queries = store.conn.execute(
        """
        SELECT city_name, keyword, experience_key, last_error
        FROM search_queries
        WHERE run_id = ? AND status = 'failed'
        ORDER BY city_name, keyword, experience_key
        LIMIT 10
        """,
        [run_id],
    ).fetchall()
    counts = {
        "listing_snapshots": scalar_count(store, "listing_snapshots", run_id),
        "job_details": scalar_count(store, "job_details", run_id),
        "classifications": scalar_count(store, "classifications", run_id),
        "quality_issues": scalar_count(store, "quality_issues", run_id),
    }
    unique_jobs_row = store.conn.execute(
        "SELECT COUNT(DISTINCT job_id) FROM listing_snapshots WHERE run_id = ?",
        [run_id],
    ).fetchone()
    unique_jobs = int(unique_jobs_row[0]) if unique_jobs_row else 0
    pending_details_row = store.conn.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT DISTINCT job_id
            FROM listing_snapshots
            WHERE run_id = ?
        ) jobs
        LEFT JOIN job_details d ON d.run_id = ? AND d.job_id = jobs.job_id
        WHERE d.job_id IS NULL
        """,
        [run_id, run_id],
    ).fetchone()
    pending_details = int(pending_details_row[0]) if pending_details_row else 0
    store.close()
    typer.echo(
        json.dumps(
            {
                "run_id": run_id,
                "queries": {row[0]: row[1] for row in query_rows},
                "unique_jobs": unique_jobs,
                "pending_details": pending_details,
                **counts,
                "failed_query_samples": [
                    {
                        "city": row[0],
                        "keyword": row[1],
                        "experience": row[2],
                        "error": row[3],
                    }
                    for row in failed_queries
                ],
            },
            indent=2,
        )
    )


@app.command()
def run(
    config: ConfigOption = Path("configs/market_us_tech.yaml"),
    run_id: OptionalRunIdOption = None,
    enrich_details: EnrichDetailsOption = None,
) -> None:
    """Collect, enrich, classify, validate, and report in one command."""
    loaded = load_config(config)
    created_run_id = collect_live(loaded, run_id=run_id)
    if enrich_details if enrich_details is not None else loaded.detail_enrichment:
        enrich_live(loaded, run_id=created_run_id)
    store = JobStore(loaded.database_path)
    classify_run(store, created_run_id)
    issues = validate_run_quality(store, loaded, created_run_id)
    qa_path = loaded.report_dir / created_run_id / "qa_report.md"
    write_qa_report(qa_path, issues)
    paths = generate_report(store, run_id=created_run_id, report_root=loaded.report_dir)
    store.export_parquet(created_run_id, Path("data/processed") / created_run_id)
    store.close()
    payload = {
        "run_id": created_run_id,
        "qa_report": str(qa_path),
        **{key: str(value) for key, value in paths.items()},
    }
    typer.echo(json.dumps(payload, indent=2))


@app.command("load-fixture")
def load_fixture(
    search_html: SearchHtmlOption,
    config: ConfigOption = Path("configs/market_us_tech.yaml"),
    run_id: RunIdOption = "fixture_run",
    detail_html: DetailHtmlOption = None,
) -> None:
    """Load local HTML fixtures through the same parsers and storage layer."""
    loaded = load_config(config)
    store = JobStore(loaded.database_path)
    queries = generate_queries(loaded, run_id)
    first_query = queries[0]
    store.create_run(
        run_id=run_id,
        config_hash=loaded.config_hash,
        code_version="fixture",
        target_population=loaded.target_population,
        config_json=loaded.to_canonical_json(),
    )
    store.upsert_query(first_query)
    listings = parse_search_results(
        search_html.read_text(encoding="utf-8"),
        run_id=run_id,
        query_id=first_query.query_id,
        page=1,
        snapshot_path=search_html,
    )
    for listing in listings:
        store.upsert_listing(listing)
    store.mark_query_status(
        first_query.query_id,
        status="complete",
        result_count=len(listings),
        pages_collected=1,
    )
    if detail_html:
        for listing in listings:
            detail = parse_job_detail(
                detail_html.read_text(encoding="utf-8"),
                run_id=run_id,
                job_id=listing.job_id,
                url=canonical_job_url(listing.job_id),
                snapshot_path=detail_html,
            )
            store.upsert_detail(detail)
    classify_run(store, run_id)
    issues = validate_run_quality(store, loaded, run_id)
    store.replace_quality_issues(run_id, issues)
    store.finish_run(run_id)
    store.close()
    typer.echo(
        json.dumps(
            {"run_id": run_id, "listings": len(listings), "issues": len(issues)},
            indent=2,
        )
    )


def classify_run(store: JobStore, run_id: str) -> int:
    jobs = store.unique_jobs(run_id)
    detail_rows = store.conn.execute(
        """
        SELECT job_id, description, workplace_type
        FROM job_details
        WHERE run_id = ?
        """,
        [run_id],
    ).fetchall()
    details = {row[0]: {"description": row[1], "workplace": row[2]} for row in detail_rows}
    for job in jobs:
        detail = details.get(job["job_id"], {})
        classification = classify_title(
            ClassificationInput(
                run_id=run_id,
                job_id=job["job_id"],
                title=job["title"],
                description=detail.get("description"),
                workplace_hint=detail.get("workplace"),
            )
        )
        store.upsert_classification(classification)
    return len(jobs)


def scalar_count(store: JobStore, table: str, run_id: str) -> int:
    row = store.conn.execute(f"SELECT COUNT(*) FROM {table} WHERE run_id = ?", [run_id]).fetchone()
    return int(row[0]) if row else 0


if __name__ == "__main__":
    app()
