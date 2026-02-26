"""Structured CV profile extracted from uploaded resume (PDF/DOCX)."""

from typing import List

from pydantic import BaseModel, Field


class CVProfile(BaseModel):
    """Structured CV data extracted and validated by the CV pipeline LLM."""

    skills: List[str] = Field(default_factory=list, description="List of skills mentioned in the CV")
    experience_years: str = Field(default="", description="Years of experience (e.g. '5', '2-3')")
    domain: str = Field(default="", description="Domain or industry focus (e.g. Software, Data, ML)")
    tools: List[str] = Field(default_factory=list, description="Tools and technologies used")
