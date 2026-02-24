"""Configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env: try package dir then project root
_base = Path(__file__).resolve().parent
for _env_path in (_base / ".env", _base.parent / ".env"):
    if load_dotenv(_env_path):
        break
load_dotenv()  # also allow process env

# API keys – never hardcode
SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o-mini")

# HTTP / fetch settings
HTTP_TIMEOUT_SECONDS: float = 30.0
HTTP_MAX_RETRIES: int = 3

# Search limits
MAX_RESULTS_DEFAULT: int = 25
MAX_RESULTS_MIN: int = 5
MAX_RESULTS_MAX: int = 30

# Concurrency
EXTRACTOR_CONCURRENCY: int = 5  # Max concurrent page fetches + LLM calls per batch

# Centralized job sources (extensible: add new entry for each source)
# All query logic is generated from this dict; do not hardcode elsewhere.
AVAILABLE_SOURCES: dict = {
    "linkedin_post": {
        "label": "LinkedIn Posts",
        "query_pattern": 'site:linkedin.com/posts "{job_title}" "{location}"',
    },
    "linkedin_job": {
        "label": "LinkedIn Jobs",
        "query_pattern": 'site:linkedin.com/jobs "{job_title}" "{location}"',
    },
    "indeed": {
        "label": "Indeed",
        "query_pattern": 'site:indeed.com "{job_title}" "{location}"',
    },
    "glassdoor": {
        "label": "Glassdoor",
        "query_pattern": 'site:glassdoor.com/Job "{job_title}" "{location}"',
    },
}

# Locations for multi-city search (extensible)
AVAILABLE_LOCATIONS: list = [
    "Lahore",
    "Karachi",
    "Islamabad/Rawalpindi",
    "Remote",
]

# Combined locations: one option runs queries for each city, results tagged with the combined label
LOCATION_QUERY_EXPANSION: dict = {
    "Islamabad/Rawalpindi": ["Islamabad", "Rawalpindi"],
}
