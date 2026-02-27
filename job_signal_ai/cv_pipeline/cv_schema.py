"""Pydantic schema for CV profile (skills, experience, domain) used by query and ranking pipelines."""

from typing import List

from pydantic import BaseModel, Field


class CVProfileSchema(BaseModel):
    """Validated CV profile from LLM extraction: skills, experience_years, domain."""

    skills: List[str] = Field(default_factory=list, description="List of skills from the CV")
    experience_years: str = Field(default="", description="Years of experience (e.g. '5', '2-3')")
    domain: str = Field(default="", description="Domain or industry focus (e.g. Software, Data, ML)")
