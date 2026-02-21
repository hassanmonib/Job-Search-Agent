"""Async HTTP page fetcher for public job URLs."""

import asyncio
from typing import Optional

import httpx
from config import HTTP_MAX_RETRIES, HTTP_TIMEOUT_SECONDS
from utils.logger import get_logger

logger = get_logger(__name__)


async def fetch_page(url: str) -> Optional[str]:
    """
    Fetch public page content as text. No authentication; public content only.
    Retries on transient failures with timeout protection.
    """
    last_error: Optional[Exception] = None
    for attempt in range(HTTP_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=HTTP_TIMEOUT_SECONDS,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; JobSignalBot/1.0; +https://github.com/jobsignal)",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as e:
            last_error = e
            logger.warning("HTTP error %s for %s: %s", e.response.status_code, url, str(e))
            if e.response.status_code and 400 <= e.response.status_code < 500:
                break  # Don't retry client errors
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_error = e
            logger.warning("Request failed for %s (attempt %s): %s", url, attempt + 1, str(e))
        except Exception as e:
            last_error = e
            logger.exception("Unexpected error fetching %s", url)
            break
        await asyncio.sleep(1.0 * (attempt + 1))  # Backoff

    if last_error:
        logger.error("Failed to fetch %s after %s attempts: %s", url, HTTP_MAX_RETRIES, last_error)
    return None


async def fetch_pages_concurrent(
    urls: list[str], max_concurrent: int = 5
) -> dict[str, Optional[str]]:
    """Fetch multiple URLs with concurrency limit. Returns url -> content (or None)."""
    sem = asyncio.Semaphore(max_concurrent)

    async def fetch_with_sem(u: str) -> tuple[str, Optional[str]]:
        async with sem:
            content = await fetch_page(u)
            return (u, content)

    results = await asyncio.gather(*[fetch_with_sem(u) for u in urls])
    return dict(results)
