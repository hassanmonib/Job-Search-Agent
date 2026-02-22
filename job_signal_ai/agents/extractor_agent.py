"""Extractor Agent: fetch page, clean text, LLM extraction, return structured jobs."""

import asyncio
import json
import re
from typing import List, Optional

from openai import AsyncOpenAI
from pydantic import ValidationError

from config import OPENAI_API_KEY, MODEL_NAME, EXTRACTOR_CONCURRENCY
from schemas.raw_job import RawJobSignal
from schemas.structured_job import StructuredJob
from services.page_fetcher import fetch_pages_concurrent
from services.text_cleaner import extract_main_content
from utils.date_parser import normalize_posted_date
from utils.helpers import deduplicate_structured_jobs, extract_emails
from utils.logger import get_logger

logger = get_logger(__name__)

# Standardized source keys (LLM may return display names; map to keys)
SOURCE_NORMALIZE = {
    "linkedin posts": "linkedin_post",
    "linkedin jobs": "linkedin_job",
    "indeed": "indeed",
    "glassdoor": "glassdoor",
}


def _normalize_source(source: str) -> str:
    """Map display names to standardized source keys."""
    key = (source or "").strip().lower()
    return SOURCE_NORMALIZE.get(key, key.replace(" ", "_") if key else "unknown")

EXTRACTION_SYSTEM_PROMPT = """You are an AI job information extraction system.
Extract structured job data from the content below.
If the content is not an active hiring post (e.g. repost-only, meme, unrelated, or clearly not a job), set is_valid_job to false.
Return only valid JSON matching this schema (no markdown, no code block):
{
  "title": "string or null",
  "company": "string or null",
  "location": "string or null",
  "employment_type": "string or null",
  "experience_required": "string or null",
  "skills": ["string"],
  "salary": "string or null",
  "contact_email": "string or null",
  "description_summary": "string or null",
  "source": "string (will be normalized)",
  "source_url": "string (use the URL provided)",
  "is_valid_job": true or false
}
Extract any visible posting date or relative time (e.g. \"2 days ago\", \"Posted 1 week ago\") if present in the content.
Support unstructured recruiter posts, incomplete descriptions, and extract any mentioned skills and experience.
If you find an email in the content, put it in contact_email; otherwise null."""


def _merge_email_into_job(job: StructuredJob, page_text: str) -> StructuredJob:
    """If LLM didn't extract email, try regex on page text."""
    if job.contact_email:
        return job
    emails = extract_emails(page_text)
    if emails:
        return job.model_copy(update={"contact_email": emails[0]})
    return job


def _parse_llm_json(text: str) -> Optional[dict]:
    """Parse JSON from LLM response, stripping markdown code blocks if present."""
    raw = text.strip()
    # Remove optional markdown code block
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def _extract_one(
    client: AsyncOpenAI,
    raw: RawJobSignal,
    page_content: Optional[str],
) -> Optional[StructuredJob]:
    """Fetch (if needed), clean, call LLM, validate and return one StructuredJob."""
    source = raw.source
    source_url = raw.url
    if page_content:
        content_for_llm = extract_main_content(page_content)
        if len(content_for_llm) < 50:
            content_for_llm = f"Title/snippet: {raw.title_snippet}\n\nSnippet: {raw.description_snippet}\n\nPage content too short or inaccessible."
    else:
        content_for_llm = f"Title/snippet: {raw.title_snippet}\n\nSnippet: {raw.description_snippet}\n\n(Page could not be fetched; use snippets only.)"

    user_content = f"Source: {source}\nSource URL: {source_url}\n\nContent:\n{content_for_llm[:8000]}"

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
        )
        choice = response.choices[0] if response.choices else None
        if not choice or not choice.message or not choice.message.content:
            return None
        parsed = _parse_llm_json(choice.message.content)
        if not parsed:
            return None
        # Ensure required fields; normalize source to standard keys
        parsed.setdefault("source_url", source_url)
        parsed.setdefault("is_valid_job", True)
        parsed["source"] = _normalize_source(parsed.get("source") or source)
        # Searched location from raw signal (multi-location search)
        parsed["searched_location"] = getattr(raw, "searched_location", "") or None
        # Extract posting date from page content (do not use LLM date fields)
        posted_date, posted_days_ago = normalize_posted_date(content_for_llm)
        parsed.pop("posted_date", None)
        parsed.pop("posted_days_ago", None)
        parsed["posted_date"] = posted_date
        parsed["posted_days_ago"] = posted_days_ago
        job = StructuredJob(**parsed)
        job = _merge_email_into_job(job, content_for_llm)
        return job
    except ValidationError as e:
        logger.warning("LLM output validation failed for %s: %s", source_url, e)
        return None
    except Exception as e:
        logger.exception("Extraction failed for %s: %s", source_url, e)
        return None


async def run_extractor_agent(
    raw_signals: List[RawJobSignal],
) -> List[StructuredJob]:
    """
    Run the Extractor Agent: fetch pages (async), clean text, run LLM extraction,
    validate schema, deduplicate. Returns list of StructuredJob.
    """
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not set; cannot run extractor")
        return []

    urls = [r.url for r in raw_signals]
    pages = await fetch_pages_concurrent(urls, max_concurrent=EXTRACTOR_CONCURRENCY)
    # Map RawJobSignal by url for ordered processing
    by_url = {r.url: r for r in raw_signals}

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    sem = asyncio.Semaphore(EXTRACTOR_CONCURRENCY)

    async def task(signal: RawJobSignal) -> Optional[StructuredJob]:
        async with sem:
            content = pages.get(signal.url)
            return await _extract_one(client, signal, content)

    results = await asyncio.gather(*[task(s) for s in raw_signals])
    jobs = [j for j in results if j is not None]
    jobs = deduplicate_structured_jobs(jobs)
    logger.info("Extractor Agent finished: signals=%s structured=%s", len(raw_signals), len(jobs))
    return jobs
