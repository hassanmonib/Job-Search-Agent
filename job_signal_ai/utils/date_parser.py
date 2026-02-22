"""Parse job posting dates from page text (relative and absolute)."""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

# Type alias: (posted_date or None, posted_days_ago or None)
DateResult = Tuple[Optional[datetime], Optional[int]]


def normalize_posted_date(raw_text: str) -> DateResult:
    """
    Attempt to extract posting date from raw text.
    Handles: "2 days ago", "1 week ago", "Posted 3h ago", "Jan 12, 2025", "12 January 2025".
    Returns (posted_date, posted_days_ago). If cannot determine, returns (None, None).
    """
    if not raw_text or not raw_text.strip():
        return (None, None)

    text = raw_text.strip().lower()
    now = datetime.now(timezone.utc)

    # ---- Relative: X hours ago ----
    m = re.search(r"(?:posted\s+)?(\d+)\s*h(?:our)?s?\s+ago", text, re.IGNORECASE)
    if m:
        hours = int(m.group(1))
        posted = now - timedelta(hours=hours)
        days = max(0, (now - posted).days) if (now - posted).days >= 0 else 0
        return (posted, days)

    m = re.search(r"(?:posted\s+)?(\d+)\s*h\s+ago", text, re.IGNORECASE)
    if m:
        hours = int(m.group(1))
        posted = now - timedelta(hours=hours)
        days = max(0, (now - posted).days)
        return (posted, days)

    # ---- Relative: X days ago ----
    m = re.search(r"(?:posted\s+)?(\d+)\s*days?\s+ago", text, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        posted = now - timedelta(days=days)
        return (posted, days)

    # ---- Relative: X weeks ago ----
    m = re.search(r"(?:posted\s+)?(\d+)\s*weeks?\s+ago", text, re.IGNORECASE)
    if m:
        weeks = int(m.group(1))
        days = weeks * 7
        posted = now - timedelta(days=days)
        return (posted, days)

    # ---- Relative: 1 month ago / X months ago ----
    m = re.search(r"(?:posted\s+)?(\d+)\s*months?\s+ago", text, re.IGNORECASE)
    if m:
        months = int(m.group(1))
        # Approximate: 30 days per month
        days = months * 30
        posted = now - timedelta(days=days)
        return (posted, days)

    # ---- Absolute: Jan 12, 2025 or January 12, 2025 ----
    months_abbr = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    months_full = r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
    # 12 Jan 2025 or Jan 12, 2025
    m = re.search(
        rf"(?:posted\s+)?(\d{{1,2}})\s+({months_abbr}|{months_full})\.?\s*,?\s*(\d{{4}})",
        text,
        re.IGNORECASE,
    )
    if m:
        day, mon_str, year = int(m.group(1)), m.group(2), int(m.group(3))
        try:
            posted = datetime(year, _month_num(mon_str), day, tzinfo=timezone.utc)
            if posted <= now:
                delta = (now - posted).days
                return (posted, delta)
        except (ValueError, KeyError):
            pass

    m = re.search(
        rf"(?:posted\s+)?({months_abbr}|{months_full})\.?\s+(\d{{1,2}})\s*,?\s*(\d{{4}})",
        text,
        re.IGNORECASE,
    )
    if m:
        mon_str, day, year = m.group(1), int(m.group(2)), int(m.group(3))
        try:
            posted = datetime(year, _month_num(mon_str), day, tzinfo=timezone.utc)
            if posted <= now:
                delta = (now - posted).days
                return (posted, delta)
        except (ValueError, KeyError):
            pass

    # ---- ISO-style or 2025-01-12 ----
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            posted = datetime(y, mo, d, tzinfo=timezone.utc)
            if posted <= now:
                delta = (now - posted).days
                return (posted, delta)
        except ValueError:
            pass

    return (None, None)


def _month_num(mon_str: str) -> int:
    s = mon_str.lower()[:3]
    months = [
        "jan", "feb", "mar", "apr", "may", "jun",
        "jul", "aug", "sep", "oct", "nov", "dec",
    ]
    for i, m in enumerate(months, 1):
        if s == m or mon_str.lower().startswith(m):
            return i
    raise KeyError(mon_str)
