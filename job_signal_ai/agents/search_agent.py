"""Search Agent: builds queries, calls SerpAPI, returns deduplicated raw job signals."""

import asyncio
from typing import List, Optional

from schemas.raw_job import RawJobSignal
from services.serp_service import build_search_queries, search_serp
from utils.helpers import deduplicate_raw_signals
from utils.logger import get_logger
from config import SERPAPI_KEY, MAX_RESULTS_MAX

logger = get_logger(__name__)


async def run_search_agent(
    job_title: str,
    location: str,
    max_results: int = 25,
    selected_sources: Optional[List[str]] = None,
) -> List[RawJobSignal]:
    """
    Run the Search Agent: build queries only for selected sources, call SerpAPI,
    collect and deduplicate raw job signals. Returns at most max_results (cap 25).
    RawJobSignal.source is set to standardized key (linkedin_post, linkedin_job, indeed).
    """
    if not SERPAPI_KEY:
        logger.error("SERPAPI_KEY is not set; cannot run search")
        return []

    from config import AVAILABLE_SOURCES

    if not selected_sources:
        selected_sources = list(AVAILABLE_SOURCES.keys())
    # Only query selected sources that exist in config
    selected_sources = [s for s in selected_sources if s in AVAILABLE_SOURCES]
    if not selected_sources:
        logger.warning("No valid selected_sources; nothing to search")
        return []

    queries = build_search_queries(job_title, location, selected_sources)
    per_query = max(5, (max_results + len(queries) - 1) // len(queries))
    per_query = min(per_query, 30)

    all_signals: List[RawJobSignal] = []
    for query, source_key in queries:
        try:
            raw = await search_serp(query, SERPAPI_KEY, num=per_query, source_key=source_key)
            all_signals.extend(raw)
        except Exception as e:
            logger.exception("Search failed for query '%s': %s", query[:50], e)

    # Deduplicate by URL
    deduped = deduplicate_raw_signals(all_signals)
    # Cap at max_results
    result = deduped[: min(max_results, MAX_RESULTS_MAX)]
    logger.info(
        "Search Agent finished: job_title=%s location=%s total=%s deduped=%s returned=%s",
        job_title,
        location,
        len(all_signals),
        len(deduped),
        len(result),
    )
    return result
