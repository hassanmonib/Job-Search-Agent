"""Extract raw text from uploaded CV files (PDF, DOCX). In-memory only."""

import re
import unicodedata
from io import BytesIO
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


def _normalize_unicode(text: str) -> str:
    """Normalize unicode (NFC) and replace problematic chars."""
    if not text:
        return ""
    return unicodedata.normalize("NFC", text)


def _clean_cv_text(text: str, max_chars: int = 50000) -> str:
    """Remove excessive whitespace and normalize unicode for CV content."""
    if not text or not text.strip():
        return ""
    t = _normalize_unicode(text)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n\s*\n", "\n\n", t)
    t = t.strip()
    if len(t) > max_chars:
        t = t[:max_chars] + "\n\n[Content truncated.]"
    return t


def _extract_pdf(bytes_io: BytesIO) -> Optional[str]:
    """Extract text from PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed; install with: pip install pdfplumber")
        return None
    try:
        with pdfplumber.open(bytes_io) as pdf:
            parts = []
            for page in pdf.pages:
                ptext = page.extract_text()
                if ptext:
                    parts.append(ptext)
            return "\n\n".join(parts) if parts else None
    except Exception as e:
        logger.exception("PDF extraction failed: %s", e)
        return None


def _extract_docx(bytes_io: BytesIO) -> Optional[str]:
    """Extract text from DOCX using python-docx."""
    try:
        from docx import Document
    except ImportError:
        logger.warning("python-docx not installed; install with: pip install python-docx")
        return None
    try:
        doc = Document(bytes_io)
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(parts) if parts else None
    except Exception as e:
        logger.exception("DOCX extraction failed: %s", e)
        return None


def extract_text_from_file(file_bytes: bytes, filename: str) -> Optional[str]:
    """
    Extract and clean text from an uploaded CV file (PDF or DOCX).
    File is read from bytes in memory; no disk write.
    Returns cleaned text or None if unsupported type or extraction fails.
    """
    name_lower = (filename or "").lower().strip()
    if not name_lower.endswith(".pdf") and not name_lower.endswith(".docx"):
        logger.warning("Unsupported file type: %s", filename)
        return None

    bio = BytesIO(file_bytes)
    raw: Optional[str] = None
    if name_lower.endswith(".pdf"):
        raw = _extract_pdf(bio)
    else:
        raw = _extract_docx(bio)

    if not raw or not raw.strip():
        return None
    return _clean_cv_text(raw)
