"""Playwright collection and enrichment engine."""

from __future__ import annotations

import random
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from . import __version__
from .config import PipelineConfig
from .models import SearchQuery, utc_now
from .parser import parse_job_detail, parse_search_results, sha256_text
from .sampling import generate_queries
from .storage import JobStore
from .urls import build_search_url


def create_run_id(config: PipelineConfig) -> str:
    return f"{config.name}_{utc_now().strftime('%Y%m%d_%H%M%S')}"


def collect(config: PipelineConfig, *, run_id: str | None = None) -> str:
    run_id = run_id or create_run_id(config)
    store = JobStore(config.database_path)
    queries = generate_queries(config, run_id)
    resumed = store.ensure_run(
        run_id=run_id,
        config_hash=config.config_hash,
        code_version=__version__,
        target_population=config.target_population,
        config_json=config.to_canonical_json(),
    )
    for query in queries:
        store.upsert_query(query)
    statuses = store.query_statuses(run_id)
    pending_queries = [query for query in queries if statuses.get(query.query_id) != "complete"]
    print(
        f"[collect] run_id={run_id} resumed={resumed} "
        f"queries_total={len(queries)} queries_pending={len(pending_queries)}",
        flush=True,
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=config.headless)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        for index, query in enumerate(pending_queries, start=1):
            print(
                f"[collect] {index}/{len(pending_queries)} "
                f"{query.city_name} | {query.keyword} | {query.experience_key}",
                flush=True,
            )
            collect_query(store, config, query, page)
        browser.close()

    store.finish_run(run_id)
    store.close()
    return run_id


def collect_query(store: JobStore, config: PipelineConfig, query: SearchQuery, page: Page) -> None:
    total = 0
    pages_collected = 0
    store.mark_query_status(query.query_id, status="running", last_error=None)
    try:
        for page_number in range(1, config.max_pages_per_query + 1):
            start = (page_number - 1) * 25
            url = build_search_url(query, start=start)
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(2_000)
            html = page.content()
            snapshot_path = write_snapshot(
                config.raw_snapshot_dir,
                run_id=query.run_id,
                kind="search",
                identifier=f"{query.query_id}_p{page_number}",
                html=html,
            )
            listings = parse_search_results(
                html,
                run_id=query.run_id,
                query_id=query.query_id,
                page=page_number,
                snapshot_path=snapshot_path,
            )
            for listing in listings:
                store.upsert_listing(listing)
            total += len(listings)
            pages_collected = page_number
            print(
                f"[collect] query={query.query_id} page={page_number} "
                f"listings={len(listings)} total={total}",
                flush=True,
            )
            if not listings:
                break
            sleep_between_requests(config)
        store.mark_query_status(
            query.query_id,
            status="complete",
            result_count=total,
            pages_collected=pages_collected,
        )
    except Exception as exc:
        store.mark_query_status(query.query_id, status="failed", last_error=repr(exc))
        print(f"[collect] query={query.query_id} failed={exc!r}", flush=True)


def enrich(config: PipelineConfig, *, run_id: str, limit: int | None = None) -> int:
    store = JobStore(config.database_path)
    jobs = store.pending_detail_jobs(run_id, limit=limit)
    completed = 0
    print(f"[enrich] run_id={run_id} pending_details={len(jobs)}", flush=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=config.headless)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        for index, job in enumerate(jobs, start=1):
            try:
                page.goto(job["url"], wait_until="domcontentloaded", timeout=45_000)
                page.wait_for_timeout(2_000)
                html = page.content()
                snapshot_path = write_snapshot(
                    config.raw_snapshot_dir,
                    run_id=run_id,
                    kind="detail",
                    identifier=job["job_id"],
                    html=html,
                )
                detail = parse_job_detail(
                    html,
                    run_id=run_id,
                    job_id=job["job_id"],
                    url=job["url"],
                    snapshot_path=snapshot_path,
                )
                store.upsert_detail(detail)
                completed += 1
                if index == 1 or index % 25 == 0 or index == len(jobs):
                    print(
                        f"[enrich] {index}/{len(jobs)} completed={completed} "
                        f"job_id={job['job_id']}",
                        flush=True,
                    )
                sleep_between_requests(config)
            except Exception as exc:
                print(f"[enrich] job_id={job['job_id']} failed={exc!r}", flush=True)
                continue
        browser.close()
    store.close()
    return completed


def write_snapshot(
    root: Path,
    *,
    run_id: str,
    kind: str,
    identifier: str,
    html: str,
) -> Path:
    digest = sha256_text(html)
    output_dir = root / run_id / kind
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{identifier}_{digest[:12]}.html"
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(html, encoding="utf-8")
    tmp_path.replace(path)
    return path


def sleep_between_requests(config: PipelineConfig) -> None:
    delay = random.uniform(config.request_delay_seconds.min, config.request_delay_seconds.max)
    time.sleep(delay)
