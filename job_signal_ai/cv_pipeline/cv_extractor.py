"""LLM-based extraction of structured CV profile from raw CV text."""

import asyncio
import json
import re
from typing import Optional

from openai import AsyncOpenAI
from pydantic import ValidationError

from config import OPENAI_API_KEY, MODEL_NAME
from schemas.cv_profile import CVProfile
from utils.logger import get_logger

logger = get_logger(__name__)

CV_EXTRACTION_SYSTEM_PROMPT = """You are an AI CV/resume parsing system.
Extract structured data from the CV content below.
Return only valid JSON matching this schema (no markdown, no code block):
{
  "skills": ["string"],
  "experience_years": "string",
  "domain": "string",
  "tools": ["string"]
}
- skills: list of professional skills (languages, frameworks, methodologies, soft skills).
- experience_years: total or relevant years of experience as a string (e.g. "5", "2-3", "1+").
- domain: primary domain or industry focus (e.g. "Software Engineering", "Data Science", "ML").
- tools: tools, technologies, and software mentioned (IDEs, cloud, databases, etc.).
If a field cannot be determined, use empty string or empty array as appropriate."""


def _parse_llm_json(text: str) -> Optional[dict]:
    """Parse JSON from LLM response, stripping markdown code blocks if present."""
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def _extract_cv_profile_async(client: AsyncOpenAI, cv_text: str) -> Optional[CVProfile]:
    """Call LLM to extract structured CV profile from text."""
    if not cv_text or len(cv_text.strip()) < 50:
        logger.warning("CV text too short for extraction")
        return None
    content = cv_text[:12000].strip()
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": CV_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"CV content:\n\n{content}"},
            ],
            temperature=0.1,
        )
        choice = response.choices[0] if response.choices else None
        if not choice or not choice.message or not choice.message.content:
            return None
        parsed = _parse_llm_json(choice.message.content)
        if not parsed:
            return None
        return CVProfile(
            skills=parsed.get("skills") or [],
            experience_years=parsed.get("experience_years") or "",
            domain=parsed.get("domain") or "",
            tools=parsed.get("tools") or [],
        )
    except ValidationError as e:
        logger.warning("CV profile validation failed: %s", e)
        return None
    except Exception as e:
        logger.exception("CV extraction failed: %s", e)
        return None


def run_cv_pipeline(file_bytes: bytes, filename: str) -> Optional[CVProfile]:
    """
    Run the full CV pipeline: extract text from file, then LLM extraction.
    Uses asyncio to call the async LLM; safe to call from sync context (e.g. Streamlit).
    """
    from cv_pipeline.text_extractor import extract_text_from_file

    raw_text = extract_text_from_file(file_bytes, filename)
    if not raw_text:
        return None
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not set; cannot run CV extraction")
        return None
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        return loop.run_until_complete(_extract_cv_profile_async(client, raw_text))
    finally:
        loop.close()
