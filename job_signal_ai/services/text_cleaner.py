"""Clean and normalize page text for LLM extraction."""

import re
from typing import Optional


def clean_page_text(html_text: str, max_chars: int = 12000) -> str:
    """
    Clean raw HTML/text into readable plain text for LLM consumption.
    Removes scripts, styles, excessive whitespace, and truncates if needed.
    """
    if not html_text or not html_text.strip():
        return ""

    text = html_text

    # Remove script and style blocks (content between tags)
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<noscript[^>]*>[\s\S]*?</noscript>", " ", text, flags=re.IGNORECASE)

    # Replace block elements with newlines to preserve structure
    for tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"):
        text = re.sub(rf"</{tag}\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(rf"<{tag}[^>]*>", "\n", text, flags=re.IGNORECASE)

    # Strip all remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Decode common entities
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')

    # Collapse whitespace and newlines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = text.strip()

    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[Content truncated for extraction.]"

    return text


def extract_main_content(html_text: str) -> str:
    """
    Optional: try to focus on main/content areas if present.
    Falls back to full clean if no clear main section.
    """
    # Simple heuristic: look for common main content selectors
    main_patterns = [
        r'<main[^>]*>([\s\S]*?)</main>',
        r'<article[^>]*>([\s\S]*?)</article>',
        r'class="[^"]*content[^"]*"[\s\S]*?>([\s\S]{100,})',
    ]
    for pattern in main_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE | re.DOTALL)
        if match:
            return clean_page_text(match.group(1))
    return clean_page_text(html_text)
