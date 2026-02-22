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


def _parse_organic_result(item: dict[str, Any], source_key: str) -> Optional[RawJobSignal]:
    """Build RawJobSignal from SerpAPI organic result. source_key is standardized (e.g. linkedin_post)."""
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
    )


async def search_serp(
    query: str,
    api_key: str,
    num: int = 10,
    source_key: str = "unknown",
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
        sig = _parse_organic_result(item, source_key)
        if sig:
            signals.append(sig)
    logger.info("SerpAPI query '%s' returned %s raw signals", query[:50], len(signals))
    return signals


def build_search_queries(
    job_title: str,
    location: str,
    selected_sources: list[str],
) -> list[tuple[str, str]]:
    """
    Build (query, source_key) list only for selected sources.
    Uses config.AVAILABLE_SOURCES for query patterns. Extensible for future sources.
    """
    from config import AVAILABLE_SOURCES

    qt = (job_title or "").strip() or "job"
    loc = (location or "").strip()
    result = []
    for key in selected_sources:
        if key not in AVAILABLE_SOURCES:
            continue
        pattern = AVAILABLE_SOURCES[key]["query_pattern"]
        query = pattern.format(job_title=qt, location=loc)
        result.append((query, key))
    return result
