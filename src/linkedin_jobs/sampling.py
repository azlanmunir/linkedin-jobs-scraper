"""Search-query generation for stratified collection."""

from __future__ import annotations

import hashlib
from itertools import product

from .config import PipelineConfig
from .models import SearchQuery
from .urls import build_search_url


def stable_query_id(parts: list[str]) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return "q_" + digest


def generate_queries(config: PipelineConfig, run_id: str) -> list[SearchQuery]:
    queries: list[SearchQuery] = []
    for location, role_family, experience in product(
        config.locations, config.role_families, config.experience_levels
    ):
        role_weight = 1.0 / len(config.role_families)
        for linkedin_location, keyword in product(
            location.linkedin_locations,
            role_family.keywords,
        ):
            target_weight = (
                location.weight
                * experience.weight
                * role_weight
                / (len(location.linkedin_locations) * len(role_family.keywords))
            )
            query_id = stable_query_id(
                [
                    run_id,
                    location.key,
                    linkedin_location,
                    role_family.key,
                    keyword,
                    experience.key,
                ]
            )
            query = SearchQuery(
                query_id=query_id,
                run_id=run_id,
                city_key=location.key,
                city_name=location.name,
                location=linkedin_location,
                keyword=keyword,
                role_family_key=role_family.key,
                experience_key=experience.key,
                experience_param=experience.linkedin_param,
                time_window_days=config.time_window_days,
                target_weight=target_weight,
                url="",
            )
            queries.append(query.model_copy(update={"url": build_search_url(query)}))
    return queries
