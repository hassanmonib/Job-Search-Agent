"""CV parser: extract raw text from PDF and DOCX (in-memory)."""

from typing import Optional

from cv_pipeline.text_extractor import extract_text_from_file
from utils.logger import get_logger

logger = get_logger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract and clean text from a PDF file (in-memory).
    Returns empty string if extraction fails.
    """
    text = extract_text_from_file(file_bytes, "document.pdf")
    return text or ""


def extract_text_from_docx(file_bytes: bytes) -> str:
    """
    Extract and clean text from a DOCX file (in-memory).
    Returns empty string if extraction fails.
    """
    text = extract_text_from_file(file_bytes, "document.docx")
    return text or ""
