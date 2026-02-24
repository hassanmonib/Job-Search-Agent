"""SerpAPI (Google Search) service for job signal discovery."""

from typing import Any, Optional

import httpx
from config import HTTP_TIMEOUT_SECONDS, SERPAPI_KEY
from schemas.raw_job import RawJobSignal
from utils.logger import get_logger

logger = get_logger(__name__)

SERPAPI_BASE = "https://serpapi.com/search"


def _is_job_like(url: str, title: str, snippet: str) -> bool:
    """Filter out obvious non-job pages (login, feed, generic)."""
    url_lower = url.lower()
    title_lower = (title or "").lower()
    snippet_lower = (snippet or "").lower()
    # Exclude login, auth, feed-only pages
    if "/login" in url_lower or "/auth" in url_lower or "/feed" in url_lower:
        return False
    # LinkedIn posts and jobs paths are ok
    if "linkedin.com" in url_lower:
        if "/posts/" in url_lower or "/jobs/" in url_lower or "/jobs/view" in url_lower:
            return True
        if "/pulse/" in url_lower or "/company/" in url_lower:
            return True  # recruiter posts sometimes under company
    if "indeed.com" in url_lower and ("/job/" in url_lower or "/jobs" in url_lower or "/viewjob" in url_lower):
        return True
    if "glassdoor.com" in url_lower and ("/job/" in url_lower or "/job-" in url_lower or "/Job" in url_lower):
        return True
    # If we have job-like keywords in title/snippet, allow
    job_keywords = ("job", "hiring", "position", "recruit", "engineer", "developer", "role", "vacancy")
    text = f"{title_lower} {snippet_lower}"
    return any(kw in text for kw in job_keywords)


def _parse_organic_result(
    item: dict[str, Any],
    source_key: str,
    searched_location: str = "",
) -> Optional[RawJobSignal]:
    """Build RawJobSignal from SerpAPI organic result."""
    link = item.get("link") or item.get("url")
    if not link:
        return None
    title = item.get("title") or ""
    snippet = item.get("snippet") or item.get("description") or ""
    if not _is_job_like(link, title, snippet):
        return None
    return RawJobSignal(
        source=source_key,
        url=link,
        title_snippet=title[:500] if title else "",
        description_snippet=snippet[:1000] if snippet else "",
        searched_location=searched_location,
    )


async def search_serp(
    query: str,
    api_key: str,
    num: int = 10,
    source_key: str = "unknown",
    searched_location: str = "",
) -> list[RawJobSignal]:
    """
    Run a single SerpAPI Google search and return raw job signals from organic results.
    """
    if not api_key:
        logger.error("SERPAPI_KEY is not set")
        return []

    params: dict[str, Any] = {
        "q": query,
        "api_key": api_key,
        "num": min(100, max(10, num)),
        "engine": "google",
    }

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(SERPAPI_BASE, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        logger.error("SerpAPI HTTP error: %s %s", e.response.status_code, e.response.text)
        return []
    except Exception as e:
        logger.exception("SerpAPI request failed: %s", e)
        return []

    organic = data.get("organic_results") or []
    signals = []
    for item in organic:
        sig = _parse_organic_result(item, source_key, searched_location)
        if sig:
            signals.append(sig)
    logger.info("SerpAPI query '%s' returned %s raw signals", query[:50], len(signals))
    return signals


def build_search_queries(
    job_title: str,
    locations: list[str],
    selected_sources: list[str],
) -> list[tuple[str, str, str]]:
    """
    Build (source_key, location, query) for each location × source combination.
    Uses config.AVAILABLE_SOURCES. Combined locations (e.g. Islamabad/Rawalpindi)
    expand to one query per city; results are tagged with the combined location.
    """
    from config import AVAILABLE_SOURCES, LOCATION_QUERY_EXPANSION

    qt = (job_title or "").strip() or "job"
    result = []
    for loc in locations:
        loc = (loc or "").strip()
        # Use expansion so "Islamabad/Rawalpindi" runs separate queries for each city
        query_locations = LOCATION_QUERY_EXPANSION.get(loc, [loc])
        for key in selected_sources:
            if key not in AVAILABLE_SOURCES:
                continue
            pattern = AVAILABLE_SOURCES[key]["query_pattern"]
            for query_loc in query_locations:
                query = pattern.format(job_title=qt, location=query_loc)
                result.append((key, loc, query))
    return result
