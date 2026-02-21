"""Structured job schema after LLM extraction."""

from typing import List, Optional

from pydantic import BaseModel, Field


class StructuredJob(BaseModel):
    """Structured job data extracted and validated by the Extractor Agent."""

    title: Optional[str] = Field(default=None, description="Job title")
    company: Optional[str] = Field(default=None, description="Company or employer name")
    location: Optional[str] = Field(default=None, description="Job location")
    employment_type: Optional[str] = Field(default=None, description="Full-time, Part-time, Contract, etc.")
    experience_required: Optional[str] = Field(default=None, description="Experience level or years required")
    skills: List[str] = Field(default_factory=list, description="List of required or preferred skills")
    salary: Optional[str] = Field(default=None, description="Salary or compensation info if mentioned")
    contact_email: Optional[str] = Field(default=None, description="Contact email if present")
    description_summary: Optional[str] = Field(default=None, description="Brief summary of the job description")
    source: str = Field(..., description="Source name (e.g. LinkedIn, Indeed)")
    source_url: str = Field(..., description="Original URL of the job post")
    is_valid_job: bool = Field(..., description="True if this is an active hiring post, false for reposts/fake/irrelevant")
