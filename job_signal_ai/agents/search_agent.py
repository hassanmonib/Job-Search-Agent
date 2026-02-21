"""Search Agent: builds queries, calls SerpAPI, returns deduplicated raw job signals."""

import asyncio
from typing import List

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
) -> List[RawJobSignal]:
    """
    Run the Search Agent: build queries, call SerpAPI for each pattern,
    collect and deduplicate raw job signals. Returns at most max_results (cap 25).
    """
    if not SERPAPI_KEY:
        logger.error("SERPAPI_KEY is not set; cannot run search")
        return []

    queries = build_search_queries(job_title, location)
    # Distribute max_results across queries (e.g. 3 queries -> ~8-9 each)
    per_query = max(5, (max_results + len(queries) - 1) // len(queries))
    per_query = min(per_query, 30)  # SerpAPI typical max per request

    all_signals: List[RawJobSignal] = []
    for query, source_label in queries:
        try:
            # SerpAPI returns generic "Google" – we override source from our label
            raw = await search_serp(query, SERPAPI_KEY, num=per_query)
            for s in raw:
                all_signals.append(
                    RawJobSignal(
                        source=source_label,
                        url=s.url,
                        title_snippet=s.title_snippet,
                        description_snippet=s.description_snippet,
                    )
                )
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
