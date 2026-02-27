"""Search Agent: uses query strategy to build queries, calls SerpAPI, returns deduplicated raw job signals."""

import asyncio
from typing import List

from schemas.raw_job import RawJobSignal
from services.serp_service import search_serp
from utils.helpers import deduplicate_raw_signals
from utils.logger import get_logger
from config import SERPAPI_KEY, MAX_RESULTS_MAX

from agents.query_strategies import BaseQueryStrategy

logger = get_logger(__name__)


async def run_search_agent(
    strategy: BaseQueryStrategy,
    max_results: int = 25,
) -> List[RawJobSignal]:
    """
    Run the Search Agent: build queries from strategy, call SerpAPI for each,
    merge results, deduplicate by URL, return at most max_results.
    Each RawJobSignal has searched_location set to the location that was queried.
    """
    if not SERPAPI_KEY:
        logger.error("SERPAPI_KEY is not set; cannot run search")
        return []

    queries = strategy.build_queries()
    if not queries:
        logger.warning("Strategy returned no queries; nothing to search")
        return []

    per_query = max(5, (max_results + len(queries) - 1) // len(queries))
    per_query = min(per_query, 30)

    all_signals: List[RawJobSignal] = []
    for source_key, location, query in queries:
        try:
            raw = await search_serp(
                query,
                SERPAPI_KEY,
                num=per_query,
                source_key=source_key,
                searched_location=location,
            )
            all_signals.extend(raw)
        except Exception as e:
            logger.exception("Search failed for query '%s': %s", query[:50], e)

    deduped = deduplicate_raw_signals(all_signals)
    result = deduped[: min(max_results, MAX_RESULTS_MAX)]
    logger.info(
        "Search Agent finished: queries=%s total=%s deduped=%s returned=%s",
        len(queries),
        len(all_signals),
        len(deduped),
        len(result),
    )
    return result
