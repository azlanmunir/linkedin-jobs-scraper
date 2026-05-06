# LinkedIn Jobs Market Intelligence Pipeline

This project turns the original August 2025 LinkedIn jobs notebook into a reproducible market-intelligence pipeline for tech job demand analysis.

The original notebook proved the concept: collect recent LinkedIn job cards, compare cities, classify roles, and test whether AI/ML demand matched the hype. The rebuild makes that work durable: config-driven collection, raw snapshots, DuckDB storage, typed parsing, deterministic classification, data-quality checks, and generated research reports.

## What This Produces

- A resumable DuckDB database of search runs, queries, listing snapshots, detail pages, classifications, and QA issues.
- Raw HTML snapshots with content hashes so parser behavior is auditable.
- Classified market tables for role family, seniority, track, and workplace mode.
- A deduplicated `canonical_jobs.parquet` export where each LinkedIn job ID appears once, while
  raw listing snapshots still preserve every discovery path for auditability.
- Markdown and HTML reports with weighted vs raw estimates, confidence intervals, charts, and methodology notes.

Generated data, snapshots, and reports are intentionally ignored by Git.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install ".[dev]"
playwright install chromium
```

Run the test suite:

```bash
pytest
```

Run a tiny smoke collection:

```bash
linkedin-jobs run --config configs/smoke.yaml
```

Run the intended market collection:

```bash
linkedin-jobs collect --config configs/market_us_tech.yaml
linkedin-jobs enrich --run-id <run_id>
linkedin-jobs classify --run-id <run_id>
linkedin-jobs validate --run-id <run_id>
linkedin-jobs report --run-id <run_id>
```

Useful paths:

- Database: `data/db/jobs.duckdb`
- Raw snapshots: `data/raw/<run_id>/`
- Reports: `reports/<run_id>/`
- Historical notebook: `notebooks/archive/LinkedIn_job_scraping.ipynb`

## Methodology

The default config defines a target population of recent US tech postings in SF Bay Area, Seattle, New York, Austin, and Boston. Searches are stratified by city, role-family keywords, and experience filters. The pipeline preserves all discovery paths for each job so a single canonical job can be deduplicated while still retaining which queries found it.

The report includes raw and weighted estimates. Raw counts describe the deduplicated canonical
corpus; weighted estimates adjust for the configured city/query sampling frame. Confidence
intervals use bootstrap resampling over deduplicated jobs. Discovery overlap is reported
separately so repeated appearances across queries do not inflate role, city, seniority, or AI/ML
shares.

## Current Architecture

- `src/linkedin_jobs/collector.py`: Playwright collection and detail enrichment.
- `src/linkedin_jobs/parser.py`: HTML parsing for search cards and detail pages.
- `src/linkedin_jobs/storage.py`: DuckDB schema, persistence, and dedup helpers.
- `src/linkedin_jobs/classifier.py`: deterministic title/workplace classification with expanded
  buckets for SWE, AI/ML, data, infrastructure, QA, research, technical go-to-market, and
  non-tech leakage.
- `src/linkedin_jobs/quality.py`: QA checks and issue persistence.
- `src/linkedin_jobs/report.py`: Markdown/HTML report generation and SVG charts.
- `src/linkedin_jobs/cli.py`: Typer CLI.

## Historical Context

The notebook scraped two datasets in August 2025:

- Scraper 1: roughly 8,000 jobs across SF Bay Area, NYC, Austin, and Seattle using fixed title searches.
- Scraper 2: roughly 8,316 jobs with Google Drive checkpoints and stratified city targets.

The rebuild keeps the useful intent but fixes the major quality issues: notebook-only execution, fragile selectors, hard-coded Colab paths, incomplete schemas, weak sampling metadata, brittle category rules, and no automated QA.
