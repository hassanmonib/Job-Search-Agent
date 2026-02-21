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
