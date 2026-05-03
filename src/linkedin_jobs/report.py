"""Report generation for market-intelligence runs."""

from __future__ import annotations

import html
import random
from collections import Counter
from pathlib import Path
from statistics import quantiles
from typing import Any

from .models import QualityIssue
from .storage import JobStore


def generate_report(store: JobStore, *, run_id: str, report_root: Path) -> dict[str, Path]:
    report_dir = report_root / run_id
    charts_dir = report_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    jobs = fetch_classified_jobs(store, run_id)
    issues = fetch_quality_issues(store, run_id)
    role_counts = Counter(job["role_family"] for job in jobs)
    seniority_counts = Counter(job["seniority"] for job in jobs)
    weighted_role = weighted_counts(jobs, "role_family")
    weighted_seniority = weighted_counts(jobs, "seniority")
    city_role = cross_tab(jobs, "city_name", "role_family")

    role_chart = charts_dir / "role_family.svg"
    seniority_chart = charts_dir / "seniority.svg"
    write_bar_svg(role_chart, role_counts, "Role Family")
    write_bar_svg(seniority_chart, seniority_counts, "Seniority")

    markdown = render_markdown(
        run_id=run_id,
        jobs=jobs,
        issues=issues,
        role_counts=role_counts,
        seniority_counts=seniority_counts,
        weighted_role=weighted_role,
        weighted_seniority=weighted_seniority,
        city_role=city_role,
    )
    md_path = report_dir / "market_report.md"
    md_path.write_text(markdown, encoding="utf-8")
    html_path = report_dir / "market_report.html"
    html_path.write_text(render_html(markdown, [role_chart, seniority_chart]), encoding="utf-8")
    return {
        "markdown": md_path,
        "html": html_path,
        "role_chart": role_chart,
        "seniority_chart": seniority_chart,
    }


def fetch_classified_jobs(store: JobStore, run_id: str) -> list[dict[str, Any]]:
    result = store.conn.execute(
        """
        WITH deduped AS (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY job_id
                       ORDER BY parser_confidence DESC, scraped_at DESC
                   ) AS rn
            FROM listing_snapshots
            WHERE run_id = ?
        )
        SELECT d.job_id, d.title, d.company, d.location, q.city_name, q.target_weight,
               c.role_family, c.seniority, c.track, c.workplace, c.confidence
        FROM deduped d
        LEFT JOIN search_queries q USING (query_id)
        LEFT JOIN classifications c ON c.run_id = d.run_id AND c.job_id = d.job_id
        WHERE d.rn = 1
        """,
        [run_id],
    )
    columns = [col[0] for col in result.description]
    return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]


def fetch_quality_issues(store: JobStore, run_id: str) -> list[QualityIssue]:
    rows = store.conn.execute(
        """
        SELECT run_id, scope, severity, code, message, details_json, created_at
        FROM quality_issues
        WHERE run_id = ?
        ORDER BY severity DESC, code
        """,
        [run_id],
    ).fetchall()
    issues = []
    for row in rows:
        issues.append(
            QualityIssue(
                run_id=row[0],
                scope=row[1],
                severity=row[2],
                code=row[3],
                message=row[4],
                details={},
                created_at=row[6],
            )
        )
    return issues


def render_markdown(
    *,
    run_id: str,
    jobs: list[dict[str, Any]],
    issues: list[QualityIssue],
    role_counts: Counter[str],
    seniority_counts: Counter[str],
    weighted_role: dict[str, float],
    weighted_seniority: dict[str, float],
    city_role: dict[str, Counter[str]],
) -> str:
    total = len(jobs)
    ai_share = share_with_ci([job["role_family"] for job in jobs], "AI/ML")
    junior_share = share_with_ci([job["seniority"] for job in jobs], "Entry")
    lines = [
        f"# LinkedIn Jobs Market Report: `{run_id}`",
        "",
        "## Executive Summary",
        "",
        f"- Deduplicated jobs analyzed: {total:,}",
        f"- AI/ML share: {format_ci(ai_share)}",
        f"- Entry-level share: {format_ci(junior_share)}",
        f"- QA issues: {len(issues)}",
        "",
        "## Role Family Distribution",
        "",
        table_from_counter(role_counts, total),
        "",
        "## Weighted Role Family Estimate",
        "",
        table_from_weighted(weighted_role),
        "",
        "## Seniority Distribution",
        "",
        table_from_counter(seniority_counts, total),
        "",
        "## Weighted Seniority Estimate",
        "",
        table_from_weighted(weighted_seniority),
        "",
        "## City x Role Family",
        "",
        table_from_crosstab(city_role),
        "",
        "## Quality Notes",
        "",
    ]
    if issues:
        for issue in issues:
            lines.append(f"- **{issue.severity.upper()} {issue.code}**: {issue.message}")
    else:
        lines.append("- No automated QA issues found.")
    lines.extend(
        [
            "",
            "## Methodology",
            "",
            "The corpus is deduplicated by LinkedIn job ID while preserving every query path "
            "that discovered each job. Raw counts describe the collected corpus. Weighted "
            "estimates use inverse query target weights, normalized to share. Confidence "
            "intervals use bootstrap resampling over deduplicated jobs.",
        ]
    )
    return "\n".join(lines) + "\n"


def table_from_counter(counter: Counter[str], total: int) -> str:
    lines = ["| Segment | Jobs | Share |", "|---|---:|---:|"]
    for key, count in counter.most_common():
        lines.append(f"| {key or 'Unknown'} | {count:,} | {count / total:.1%} |")
    return "\n".join(lines)


def table_from_weighted(weighted: dict[str, float]) -> str:
    total = sum(weighted.values()) or 1.0
    lines = ["| Segment | Weighted Share |", "|---|---:|"]
    for key, value in sorted(weighted.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"| {key or 'Unknown'} | {value / total:.1%} |")
    return "\n".join(lines)


def table_from_crosstab(crosstab: dict[str, Counter[str]]) -> str:
    role_keys = sorted({key for counts in crosstab.values() for key in counts})
    lines = ["| City | " + " | ".join(role_keys) + " |", "|---" + "|---:" * len(role_keys) + "|"]
    for city, counts in sorted(crosstab.items()):
        values = [str(counts.get(role, 0)) for role in role_keys]
        lines.append(f"| {city} | " + " | ".join(values) + " |")
    return "\n".join(lines)


def cross_tab(jobs: list[dict[str, Any]], row_key: str, col_key: str) -> dict[str, Counter[str]]:
    table: dict[str, Counter[str]] = {}
    for job in jobs:
        row = job.get(row_key) or "Unknown"
        col = job.get(col_key) or "Unknown"
        table.setdefault(row, Counter())[col] += 1
    return table


def weighted_counts(jobs: list[dict[str, Any]], key: str) -> dict[str, float]:
    counts: dict[str, float] = {}
    for job in jobs:
        segment = str(job.get(key) or "Unknown")
        target_weight = float(job.get("target_weight") or 1.0)
        weight = 1.0 / max(target_weight, 1e-9)
        counts[segment] = counts.get(segment, 0.0) + weight
    return counts


def share_with_ci(
    values: list[str],
    target: str,
    *,
    samples: int = 500,
) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    rng = random.Random(42)
    observed = sum(value == target for value in values) / len(values)
    boot = []
    for _ in range(samples):
        draw = [values[rng.randrange(len(values))] for _ in values]
        boot.append(sum(value == target for value in draw) / len(draw))
    lower, upper = quantiles(boot, n=40)[0], quantiles(boot, n=40)[-1]
    return observed, lower, upper


def format_ci(ci: tuple[float, float, float]) -> str:
    observed, lower, upper = ci
    return f"{observed:.1%} ({lower:.1%}-{upper:.1%} bootstrap CI)"


def write_bar_svg(path: Path, counter: Counter[str], title: str) -> None:
    width = 900
    row_height = 28
    rows = counter.most_common(15)
    height = 80 + row_height * max(len(rows), 1)
    max_count = max(counter.values(), default=1)
    parts = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}'>",
        "<style>text{font-family:Arial,sans-serif;font-size:13px}.title{font-size:20px;font-weight:700}</style>",
        f"<text x='20' y='32' class='title'>{html.escape(title)}</text>",
    ]
    for index, (label, count) in enumerate(rows):
        y = 60 + index * row_height
        bar_width = int((count / max_count) * 520)
        parts.append(f"<text x='20' y='{y + 16}'>{html.escape(label)}</text>")
        parts.append(f"<rect x='230' y='{y}' width='{bar_width}' height='18' fill='#2563eb'/>")
        parts.append(f"<text x='{240 + bar_width}' y='{y + 15}'>{count}</text>")
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def render_html(markdown: str, chart_paths: list[Path]) -> str:
    chart_html = "\n".join(
        path.read_text(encoding="utf-8") for path in chart_paths if path.exists()
    )
    escaped = html.escape(markdown)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>LinkedIn Jobs Market Report</title>
  <style>
    body {{
      font-family: Inter, Arial, sans-serif;
      margin: 40px;
      line-height: 1.5;
      color: #111827;
    }}
    pre {{ white-space: pre-wrap; background: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; }}
    svg {{ display: block; margin: 28px 0; max-width: 100%; }}
  </style>
</head>
<body>
  {chart_html}
  <pre>{escaped}</pre>
</body>
</html>
"""
