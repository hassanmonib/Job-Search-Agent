"""Helper utilities for the Job Signal AI system."""

import re
from typing import List

from schemas.raw_job import RawJobSignal
from schemas.structured_job import StructuredJob


def extract_emails(text: str) -> List[str]:
    """Extract email addresses from text using regex."""
    if not text:
        return []
    pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    return list(dict.fromkeys(re.findall(pattern, text)))


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication (strip trailing slashes, fragments)."""
    if not url:
        return ""
    url = url.strip().rstrip("/")
    if "#" in url:
        url = url.split("#")[0]
    if "?" in url:
        base, query = url.split("?", 1)
        # Keep only meaningful query params for job URLs (optional: strip UTM etc.)
        url = base
    return url


def deduplicate_raw_signals(signals: List[RawJobSignal]) -> List[RawJobSignal]:
    """Remove duplicate raw job signals by normalized URL."""
    seen: set[str] = set()
    result: List[RawJobSignal] = []
    for s in signals:
        key = normalize_url(s.url)
        if key and key not in seen:
            seen.add(key)
            result.append(s)
    return result


def deduplicate_structured_jobs(jobs: List[StructuredJob]) -> List[StructuredJob]:
    """Remove duplicate jobs by (title, company, source_url) similarity."""
    seen: set[tuple[str, str, str]] = set()
    result: List[StructuredJob] = []
    for j in jobs:
        title = (j.title or "").strip().lower()
        company = (j.company or "").strip().lower()
        url = normalize_url(j.source_url)
        key = (title[:50], company[:50], url)
        if key not in seen:
            seen.add(key)
            result.append(j)
    return result
