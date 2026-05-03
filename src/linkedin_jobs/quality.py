"""Data-quality checks and QA report rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import PipelineConfig
from .models import QualityIssue
from .storage import JobStore


def validate_run(store: JobStore, config: PipelineConfig, run_id: str) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    add_required_field_checks(store, run_id, issues)
    add_duplicate_checks(store, run_id, issues)
    add_query_balance_checks(store, config, run_id, issues)
    add_classification_checks(store, run_id, issues)
    add_date_window_checks(store, config, run_id, issues)
    store.replace_quality_issues(run_id, issues)
    return issues


def add_required_field_checks(store: JobStore, run_id: str, issues: list[QualityIssue]) -> None:
    total = scalar(
        store,
        "SELECT COUNT(*) FROM listing_snapshots WHERE run_id = ?",
        [run_id],
    )
    if total == 0:
        issues.append(
            QualityIssue(
                run_id=run_id,
                scope="listing_snapshots",
                severity="error",
                code="no_listings",
                message="No listing snapshots collected.",
            )
        )
        return
    for field in ["title", "company", "location", "url"]:
        missing = scalar(
            store,
            f"""
            SELECT COUNT(*)
            FROM listing_snapshots
            WHERE run_id = ? AND ({field} IS NULL OR TRIM({field}) = '')
            """,
            [run_id],
        )
        rate = missing / total
        if rate > 0.05:
            issues.append(
                QualityIssue(
                    run_id=run_id,
                    scope="listing_snapshots",
                    severity="warning",
                    code=f"high_null_{field}",
                    message=f"{field} missing rate is {rate:.1%}.",
                    details={"missing": missing, "total": total},
                )
            )


def add_duplicate_checks(store: JobStore, run_id: str, issues: list[QualityIssue]) -> None:
    raw_count = scalar(store, "SELECT COUNT(*) FROM listing_snapshots WHERE run_id = ?", [run_id])
    unique_count = scalar(
        store,
        "SELECT COUNT(DISTINCT job_id) FROM listing_snapshots WHERE run_id = ?",
        [run_id],
    )
    if raw_count and unique_count / raw_count < 0.55:
        issues.append(
            QualityIssue(
                run_id=run_id,
                scope="listing_snapshots",
                severity="warning",
                code="high_duplicate_rate",
                message="More than 45% of collected snapshots are duplicate job IDs.",
                details={"raw": raw_count, "unique": unique_count},
            )
        )


def add_query_balance_checks(
    store: JobStore,
    config: PipelineConfig,
    run_id: str,
    issues: list[QualityIssue],
) -> None:
    rows = store.conn.execute(
        """
        SELECT q.city_key, COUNT(DISTINCT l.job_id) AS jobs
        FROM search_queries q
        LEFT JOIN listing_snapshots l USING (query_id)
        WHERE q.run_id = ?
        GROUP BY q.city_key
        """,
        [run_id],
    ).fetchall()
    city_counts = {row[0]: int(row[1]) for row in rows}
    for location in config.locations:
        if city_counts.get(location.key, 0) < 25 and config.name != "smoke":
            issues.append(
                QualityIssue(
                    run_id=run_id,
                    scope="search_queries",
                    severity="warning",
                    code="low_city_sample",
                    message=f"{location.name} has fewer than 25 unique jobs.",
                    details={"city_key": location.key, "jobs": city_counts.get(location.key, 0)},
                )
            )

    zero_queries = scalar(
        store,
        """
        SELECT COUNT(*)
        FROM search_queries
        WHERE run_id = ? AND COALESCE(result_count, 0) = 0
        """,
        [run_id],
    )
    query_count = scalar(store, "SELECT COUNT(*) FROM search_queries WHERE run_id = ?", [run_id])
    if query_count and zero_queries / query_count > 0.25:
        issues.append(
            QualityIssue(
                run_id=run_id,
                scope="search_queries",
                severity="warning",
                code="many_zero_result_queries",
                message="More than 25% of queries returned zero parsed jobs.",
                details={"zero_queries": zero_queries, "query_count": query_count},
            )
        )


def add_classification_checks(store: JobStore, run_id: str, issues: list[QualityIssue]) -> None:
    total = scalar(store, "SELECT COUNT(*) FROM classifications WHERE run_id = ?", [run_id])
    if total == 0:
        issues.append(
            QualityIssue(
                run_id=run_id,
                scope="classifications",
                severity="warning",
                code="no_classifications",
                message="No classifications have been generated.",
            )
        )
        return
    rows = store.conn.execute(
        """
        SELECT role_family, COUNT(*) AS count
        FROM classifications
        WHERE run_id = ?
        GROUP BY role_family
        """,
        [run_id],
    ).fetchall()
    counts = {row[0]: int(row[1]) for row in rows}
    if counts.get("Executive", 0) / total > 0.12:
        issues.append(
            QualityIssue(
                run_id=run_id,
                scope="classifications",
                severity="warning",
                code="executive_share_spike",
                message="Executive share is above 12%; inspect title rules and query bias.",
                details={"executive": counts.get("Executive", 0), "total": total},
            )
        )
    if counts.get("Product", 0) + counts.get("Program", 0) == 0:
        issues.append(
            QualityIssue(
                run_id=run_id,
                scope="classifications",
                severity="warning",
                code="missing_product_program",
                message="No Product or Program jobs classified; likely query or classifier issue.",
            )
        )
    if counts.get("Other", 0) / total > 0.20:
        issues.append(
            QualityIssue(
                run_id=run_id,
                scope="classifications",
                severity="warning",
                code="high_other_share",
                message="Other role share is above 20%; taxonomy may be underfitting.",
                details={"other": counts.get("Other", 0), "total": total},
            )
        )


def add_date_window_checks(
    store: JobStore,
    config: PipelineConfig,
    run_id: str,
    issues: list[QualityIssue],
) -> None:
    violations = scalar(
        store,
        """
        SELECT COUNT(*)
        FROM listing_snapshots
        WHERE run_id = ?
          AND posted_at IS NOT NULL
          AND posted_at < scraped_at - (? * INTERVAL 1 DAY)
        """,
        [run_id, config.time_window_days + 1],
    )
    if violations:
        issues.append(
            QualityIssue(
                run_id=run_id,
                scope="listing_snapshots",
                severity="warning",
                code="date_window_violations",
                message="Some parsed posting dates fall outside the configured time window.",
                details={"violations": violations},
            )
        )


def write_qa_report(path: Path, issues: list[QualityIssue]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# QA Report", "", f"Issues: {len(issues)}", ""]
    for issue in issues:
        lines.append(
            f"- **{issue.severity.upper()} {issue.code}** ({issue.scope}): {issue.message}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def scalar(store: JobStore, sql: str, params: list[Any]) -> int:
    row = store.conn.execute(sql, params).fetchone()
    value = row[0] if row else 0
    return int(value or 0)
