"""Shared helper functions used across modules."""

import re
import hashlib
from datetime import datetime, timedelta
from typing import Optional


def clean_text(text: Optional[str]) -> str:
    """Remove excess whitespace, HTML entities, and normalize text."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)  # Strip HTML tags
    text = re.sub(r"&\w+;", " ", text)  # Strip HTML entities
    text = re.sub(r"\s+", " ", text).strip()
    return text


def generate_job_hash(title: str, company: str, url: str) -> str:
    """Generate a deterministic hash for a job posting."""
    raw = f"{title.lower().strip()}|{company.lower().strip()}|{url.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_relative_date(text: str) -> Optional[datetime]:
    """Convert relative date strings like '3 days ago' into datetime objects."""
    text = text.lower().strip()
    now = datetime.utcnow()

    patterns = {
        r"(\d+)\s*minute": lambda m: now - timedelta(minutes=int(m)),
        r"(\d+)\s*hour": lambda m: now - timedelta(hours=int(m)),
        r"(\d+)\s*day": lambda m: now - timedelta(days=int(m)),
        r"(\d+)\s*week": lambda m: now - timedelta(weeks=int(m)),
        r"(\d+)\s*month": lambda m: now - timedelta(days=int(m) * 30),
        r"just\s*now|just\s*posted": lambda _: now,
        r"today": lambda _: now,
        r"yesterday": lambda _: now - timedelta(days=1),
    }

    for pattern, resolver in patterns.items():
        match = re.search(pattern, text)
        if match:
            try:
                return resolver(int(match.group(1)) if match.lastindex else None)
            except (ValueError, TypeError):
                return resolver(None)

    return None


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text to a maximum length, adding ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rsplit(" ", 1)[0] + "..."
