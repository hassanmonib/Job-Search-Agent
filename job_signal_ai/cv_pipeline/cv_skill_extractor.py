"""CV skill extraction via LLM; returns validated Pydantic schema (skills, experience_years, domain)."""

import asyncio
from typing import Optional

from openai import AsyncOpenAI

from config import OPENAI_API_KEY, MODEL_NAME
from cv_pipeline.cv_schema import CVProfileSchema
from utils.logger import get_logger

logger = get_logger(__name__)

CV_SKILL_EXTRACTION_PROMPT = """You are an AI CV/resume parsing system.
Extract structured data from the CV content below.
Return only valid JSON matching this schema (no markdown, no code block):
{
  "skills": ["string"],
  "experience_years": "string",
  "domain": "string"
}
- skills: list of professional skills (languages, frameworks, methodologies, tools).
- experience_years: total or relevant years of experience as a string (e.g. "5", "2-3").
- domain: primary domain or industry focus (e.g. "Software Engineering", "Data Science").
If a field cannot be determined, use empty string or empty array."""


async def _extract_skills_async(client: AsyncOpenAI, cv_text: str) -> Optional[CVProfileSchema]:
    """Call LLM to extract skills, experience_years, domain from CV text."""
    import json
    import re

    if not cv_text or len(cv_text.strip()) < 50:
        logger.warning("CV text too short for extraction")
        return None
    content = cv_text[:12000].strip()
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": CV_SKILL_EXTRACTION_PROMPT},
                {"role": "user", "content": f"CV content:\n\n{content}"},
            ],
            temperature=0.1,
        )
        choice = response.choices[0] if response.choices else None
        if not choice or not choice.message or not choice.message.content:
            return None
        raw = choice.message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        return CVProfileSchema(
            skills=data.get("skills") or [],
            experience_years=data.get("experience_years") or "",
            domain=data.get("domain") or "",
        )
    except Exception as e:
        logger.exception("CV skill extraction failed: %s", e)
        return None


def extract_skills_from_text(cv_text: str) -> Optional[CVProfileSchema]:
    """
    Extract skills, experience_years, and domain from CV text using LLM.
    Returns validated CVProfileSchema or None. Safe to call from sync context.
    """
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not set; cannot run CV skill extraction")
        return None
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        return loop.run_until_complete(_extract_skills_async(client, cv_text))
    finally:
        loop.close()
