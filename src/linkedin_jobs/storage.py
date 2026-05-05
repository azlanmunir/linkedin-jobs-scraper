"""DuckDB persistence layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from .models import Classification, JobDetail, QualityIssue, RawListing, SearchQuery, utc_now


class JobStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(path))
        self.init_schema()

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_runs (
                run_id VARCHAR PRIMARY KEY,
                config_hash VARCHAR NOT NULL,
                code_version VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                target_population VARCHAR NOT NULL,
                config_json VARCHAR NOT NULL,
                started_at TIMESTAMP NOT NULL,
                ended_at TIMESTAMP
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_queries (
                query_id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                city_key VARCHAR NOT NULL,
                city_name VARCHAR NOT NULL,
                location VARCHAR NOT NULL,
                keyword VARCHAR NOT NULL,
                role_family_key VARCHAR NOT NULL,
                experience_key VARCHAR NOT NULL,
                experience_param VARCHAR NOT NULL,
                time_window_days INTEGER NOT NULL,
                target_weight DOUBLE NOT NULL,
                url VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'pending',
                result_count INTEGER,
                pages_collected INTEGER DEFAULT 0,
                last_error VARCHAR
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listing_snapshots (
                snapshot_id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                query_id VARCHAR NOT NULL,
                job_id VARCHAR NOT NULL,
                url VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                company VARCHAR,
                location VARCHAR,
                posted_text VARCHAR,
                posted_at TIMESTAMP,
                page INTEGER NOT NULL,
                rank INTEGER NOT NULL,
                raw_snapshot_path VARCHAR,
                content_sha256 VARCHAR,
                parser_confidence DOUBLE NOT NULL,
                scraped_at TIMESTAMP NOT NULL,
                extraction_status VARCHAR NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_details (
                run_id VARCHAR NOT NULL,
                job_id VARCHAR NOT NULL,
                url VARCHAR NOT NULL,
                description VARCHAR,
                workplace_type VARCHAR NOT NULL,
                employment_type VARCHAR,
                salary_min DOUBLE,
                salary_max DOUBLE,
                salary_currency VARCHAR,
                applicants_signal VARCHAR,
                criteria_json VARCHAR NOT NULL,
                skills_json VARCHAR NOT NULL,
                raw_snapshot_path VARCHAR,
                content_sha256 VARCHAR,
                parser_confidence DOUBLE NOT NULL,
                scraped_at TIMESTAMP NOT NULL,
                extraction_status VARCHAR NOT NULL,
                PRIMARY KEY (run_id, job_id)
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS companies (
                company_key VARCHAR PRIMARY KEY,
                canonical_name VARCHAR NOT NULL,
                first_seen_at TIMESTAMP NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS locations (
                location_key VARCHAR PRIMARY KEY,
                canonical_name VARCHAR NOT NULL,
                first_seen_at TIMESTAMP NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS classifications (
                run_id VARCHAR NOT NULL,
                job_id VARCHAR NOT NULL,
                role_family VARCHAR NOT NULL,
                seniority VARCHAR NOT NULL,
                track VARCHAR NOT NULL,
                workplace VARCHAR NOT NULL,
                confidence DOUBLE NOT NULL,
                reasons_json VARCHAR NOT NULL,
                classified_at TIMESTAMP NOT NULL,
                PRIMARY KEY (run_id, job_id)
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quality_issues (
                issue_id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                scope VARCHAR NOT NULL,
                severity VARCHAR NOT NULL,
                code VARCHAR NOT NULL,
                message VARCHAR NOT NULL,
                details_json VARCHAR NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
            """
        )

    def create_run(
        self,
        *,
        run_id: str,
        config_hash: str,
        code_version: str,
        target_population: str,
        config_json: str,
    ) -> None:
        self.conn.execute("DELETE FROM search_runs WHERE run_id = ?", [run_id])
        self.conn.execute(
            """
            INSERT INTO search_runs
            VALUES (?, ?, ?, 'running', ?, ?, ?, NULL)
            """,
            [run_id, config_hash, code_version, target_population, config_json, utc_now()],
        )

    def ensure_run(
        self,
        *,
        run_id: str,
        config_hash: str,
        code_version: str,
        target_population: str,
        config_json: str,
    ) -> bool:
        existing = self.conn.execute(
            "SELECT config_hash FROM search_runs WHERE run_id = ?",
            [run_id],
        ).fetchone()
        if not existing:
            self.create_run(
                run_id=run_id,
                config_hash=config_hash,
                code_version=code_version,
                target_population=target_population,
                config_json=config_json,
            )
            return False
        if existing[0] != config_hash:
            raise ValueError(
                f"Run {run_id!r} already exists with a different config hash; "
                "use a new run id for a changed config."
            )
        self.conn.execute(
            "UPDATE search_runs SET status = 'running', ended_at = NULL WHERE run_id = ?",
            [run_id],
        )
        return True

    def finish_run(self, run_id: str, status: str = "complete") -> None:
        self.conn.execute(
            "UPDATE search_runs SET status = ?, ended_at = ? WHERE run_id = ?",
            [status, utc_now(), run_id],
        )

    def upsert_query(self, query: SearchQuery) -> None:
        existing = self.conn.execute(
            "SELECT 1 FROM search_queries WHERE query_id = ?",
            [query.query_id],
        ).fetchone()
        if existing:
            self.conn.execute(
                """
                UPDATE search_queries
                SET run_id = ?,
                    city_key = ?,
                    city_name = ?,
                    location = ?,
                    keyword = ?,
                    role_family_key = ?,
                    experience_key = ?,
                    experience_param = ?,
                    time_window_days = ?,
                    target_weight = ?,
                    url = ?
                WHERE query_id = ?
                """,
                [
                    query.run_id,
                    query.city_key,
                    query.city_name,
                    query.location,
                    query.keyword,
                    query.role_family_key,
                    query.experience_key,
                    query.experience_param,
                    query.time_window_days,
                    query.target_weight,
                    query.url,
                    query.query_id,
                ],
            )
            return
        self.conn.execute(
            """
            INSERT INTO search_queries (
                query_id, run_id, city_key, city_name, location, keyword, role_family_key,
                experience_key, experience_param, time_window_days, target_weight, url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                query.query_id,
                query.run_id,
                query.city_key,
                query.city_name,
                query.location,
                query.keyword,
                query.role_family_key,
                query.experience_key,
                query.experience_param,
                query.time_window_days,
                query.target_weight,
                query.url,
            ],
        )

    def mark_query_status(
        self,
        query_id: str,
        *,
        status: str,
        result_count: int | None = None,
        pages_collected: int | None = None,
        last_error: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE search_queries
            SET status = ?,
                result_count = COALESCE(?, result_count),
                pages_collected = COALESCE(?, pages_collected),
                last_error = ?
            WHERE query_id = ?
            """,
            [status, result_count, pages_collected, last_error, query_id],
        )

    def query_statuses(self, run_id: str) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT query_id, status FROM search_queries WHERE run_id = ?",
            [run_id],
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    def upsert_listing(self, listing: RawListing) -> None:
        snapshot_id = f"{listing.query_id}:{listing.page}:{listing.rank}:{listing.job_id}"
        self.conn.execute("DELETE FROM listing_snapshots WHERE snapshot_id = ?", [snapshot_id])
        self.conn.execute(
            """
            INSERT INTO listing_snapshots
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                snapshot_id,
                listing.run_id,
                listing.query_id,
                listing.job_id,
                listing.url,
                listing.title,
                listing.company,
                listing.location,
                listing.posted_text,
                listing.posted_at,
                listing.page,
                listing.rank,
                str(listing.raw_snapshot_path) if listing.raw_snapshot_path else None,
                listing.content_sha256,
                listing.parser_confidence,
                listing.scraped_at,
                listing.extraction_status,
            ],
        )
        if listing.company:
            self.upsert_dimension("companies", "company_key", listing.company)
        if listing.location:
            self.upsert_dimension("locations", "location_key", listing.location)

    def upsert_dimension(self, table: str, key_column: str, value: str) -> None:
        key = normalize_key(value)
        existing = self.conn.execute(
            f"SELECT 1 FROM {table} WHERE {key_column} = ?",
            [key],
        ).fetchone()
        if existing:
            return
        self.conn.execute(
            f"INSERT INTO {table} VALUES (?, ?, ?)",
            [key, value.strip(), utc_now()],
        )

    def upsert_detail(self, detail: JobDetail) -> None:
        self.conn.execute(
            "DELETE FROM job_details WHERE run_id = ? AND job_id = ?",
            [detail.run_id, detail.job_id],
        )
        self.conn.execute(
            """
            INSERT INTO job_details
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                detail.run_id,
                detail.job_id,
                detail.url,
                detail.description,
                detail.workplace_type,
                detail.employment_type,
                detail.salary_min,
                detail.salary_max,
                detail.salary_currency,
                detail.applicants_signal,
                json.dumps(detail.criteria, sort_keys=True),
                json.dumps(detail.skills, sort_keys=True),
                str(detail.raw_snapshot_path) if detail.raw_snapshot_path else None,
                detail.content_sha256,
                detail.parser_confidence,
                detail.scraped_at,
                detail.extraction_status,
            ],
        )

    def upsert_classification(self, classification: Classification) -> None:
        self.conn.execute(
            "DELETE FROM classifications WHERE run_id = ? AND job_id = ?",
            [classification.run_id, classification.job_id],
        )
        self.conn.execute(
            """
            INSERT INTO classifications
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                classification.run_id,
                classification.job_id,
                classification.role_family,
                classification.seniority,
                classification.track,
                classification.workplace,
                classification.confidence,
                json.dumps(classification.reasons),
                classification.classified_at,
            ],
        )

    def replace_quality_issues(self, run_id: str, issues: list[QualityIssue]) -> None:
        self.conn.execute("DELETE FROM quality_issues WHERE run_id = ?", [run_id])
        for index, issue in enumerate(issues, start=1):
            self.conn.execute(
                """
                INSERT INTO quality_issues
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    f"{run_id}:{index:04d}:{issue.code}",
                    issue.run_id,
                    issue.scope,
                    issue.severity,
                    issue.code,
                    issue.message,
                    json.dumps(issue.details, sort_keys=True),
                    issue.created_at,
                ],
            )

    def unique_jobs(self, run_id: str) -> list[dict[str, Any]]:
        result = self.conn.execute(
            """
            WITH ranked AS (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY job_id
                           ORDER BY parser_confidence DESC, scraped_at DESC, page ASC, rank ASC
                       ) AS rn
                FROM listing_snapshots
                WHERE run_id = ?
            )
            SELECT r.*, q.city_name, q.city_key, q.target_weight, q.keyword, q.experience_key
            FROM ranked r
            LEFT JOIN search_queries q USING (query_id)
            WHERE rn = 1
            ORDER BY job_id
            """,
            [run_id],
        )
        columns = [col[0] for col in result.description]
        return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]

    def listing_discovery_paths(self, run_id: str) -> list[dict[str, Any]]:
        result = self.conn.execute(
            """
            SELECT job_id,
                   COUNT(*) AS discovery_count,
                   STRING_AGG(DISTINCT query_id, ',') AS query_ids
            FROM listing_snapshots
            WHERE run_id = ?
            GROUP BY job_id
            ORDER BY discovery_count DESC, job_id
            """,
            [run_id],
        )
        columns = [col[0] for col in result.description]
        return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]

    def pending_detail_jobs(self, run_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        sql = """
            SELECT u.job_id, u.url
            FROM (
                SELECT job_id, ANY_VALUE(url) AS url
                FROM listing_snapshots
                WHERE run_id = ?
                GROUP BY job_id
            ) u
            LEFT JOIN job_details d ON d.run_id = ? AND d.job_id = u.job_id
            WHERE d.job_id IS NULL
            ORDER BY u.job_id
        """
        params: list[Any] = [run_id, run_id]
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [{"job_id": row[0], "url": row[1]} for row in rows]

    def export_parquet(self, run_id: str, output_dir: Path) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        tables = [
            "search_runs",
            "search_queries",
            "listing_snapshots",
            "job_details",
            "companies",
            "locations",
            "classifications",
            "quality_issues",
        ]
        paths: list[Path] = []
        for table in tables:
            path = output_dir / f"{table}.parquet"
            output_path = sql_literal(str(path))
            if table == "companies" or table == "locations":
                sql = f"COPY (SELECT * FROM {table}) TO {output_path} (FORMAT PARQUET)"
                params = []
            else:
                sql = (
                    f"COPY (SELECT * FROM {table} WHERE run_id = ?) "
                    f"TO {output_path} (FORMAT PARQUET)"
                )
                params = [run_id]
            self.conn.execute(sql, params)
            paths.append(path)
        canonical_path = output_dir / "canonical_jobs.parquet"
        canonical_output = sql_literal(str(canonical_path))
        self.conn.execute(
            f"""
            COPY (
                WITH ranked AS (
                    SELECT *,
                           ROW_NUMBER() OVER (
                               PARTITION BY job_id
                               ORDER BY parser_confidence DESC, scraped_at DESC, page ASC, rank ASC
                           ) AS rn
                    FROM listing_snapshots
                    WHERE run_id = ?
                ),
                discovery AS (
                    SELECT l.job_id,
                           COUNT(*) AS discovery_paths,
                           COUNT(DISTINCT l.query_id) AS discovery_queries,
                           STRING_AGG(DISTINCT q.keyword, ', ' ORDER BY q.keyword)
                               AS discovered_keywords,
                           STRING_AGG(DISTINCT q.city_name, ', ' ORDER BY q.city_name)
                               AS discovered_cities
                    FROM listing_snapshots l
                    LEFT JOIN search_queries q ON q.query_id = l.query_id
                    WHERE l.run_id = ?
                    GROUP BY l.job_id
                )
                SELECT r.run_id,
                       r.job_id,
                       r.url,
                       r.title,
                       r.company,
                       r.location,
                       r.posted_text,
                       r.posted_at,
                       q.city_name AS canonical_city_name,
                       q.city_key AS canonical_city_key,
                       q.keyword AS canonical_keyword,
                       q.experience_key AS canonical_experience_key,
                       q.target_weight AS canonical_target_weight,
                       d.description,
                       d.workplace_type,
                       d.employment_type,
                       d.salary_min,
                       d.salary_max,
                       d.salary_currency,
                       d.applicants_signal,
                       c.role_family,
                       c.seniority,
                       c.track,
                       c.workplace AS classified_workplace,
                       c.confidence AS classification_confidence,
                       discovery.discovery_paths,
                       discovery.discovery_queries,
                       discovery.discovered_keywords,
                       discovery.discovered_cities
                FROM ranked r
                LEFT JOIN search_queries q ON q.query_id = r.query_id
                LEFT JOIN job_details d ON d.run_id = r.run_id AND d.job_id = r.job_id
                LEFT JOIN classifications c ON c.run_id = r.run_id AND c.job_id = r.job_id
                LEFT JOIN discovery ON discovery.job_id = r.job_id
                WHERE r.rn = 1
                ORDER BY r.job_id
            ) TO {canonical_output} (FORMAT PARQUET)
            """,
            [run_id, run_id],
        )
        paths.append(canonical_path)
        return paths


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def normalize_key(value: str) -> str:
    return " ".join(value.strip().lower().split())
