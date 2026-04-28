"""Content freshness extractor: consolidates date signals from multiple sources.

Sources checked (priority order):
  1. JSON-LD datePublished / dateModified
  2. OG meta article:published_time / article:modified_time
  3. <time datetime=""> elements
  4. URL date patterns (e.g. /2024/01/)
  5. Visible date strings near top of article
  6. HTTP Last-Modified header
"""
from __future__ import annotations

import json
import re
from typing import Any

from selectolax.parser import HTMLParser

WANTS_HEADERS = True

# Regex for dates in URLs like /2024/ or /2024/01/ or /2024-01-15/
_URL_DATE_RE = re.compile(r"/(\d{4})(?:[/-](\d{2}))?(?:[/-](\d{2}))?/")

# Regex for visible date patterns (ISO, US, European formats)
_VISIBLE_DATE_PATTERNS: list[re.Pattern[str]] = [
    # ISO: 2024-01-15 or 2024/01/15
    re.compile(r"\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2})\b"),
    # Written: January 15, 2024 / Jan 15, 2024
    re.compile(
        r"\b(\w+\s+\d{1,2},?\s+20\d{2})\b"
    ),
    # European: 15 January 2024
    re.compile(
        r"\b(\d{1,2}\s+\w+\s+20\d{2})\b"
    ),
]

_PUBLISHED_KEYS = {"datepublished", "datecreated", "uploaddate"}
_MODIFIED_KEYS = {"datemodified", "lastupdated"}


def _empty() -> dict[str, Any]:
    return {
        "published_date": None,
        "modified_date": None,
        "date_sources": [],
        "date_source_count": 0,
    }


def _extract_jsonld_dates(data: Any, dates: list[dict[str, str]]) -> None:
    """Recursively extract date fields from JSON-LD data."""
    if isinstance(data, list):
        for item in data:
            _extract_jsonld_dates(item, dates)
        return
    if not isinstance(data, dict):
        return
    for key, val in data.items():
        key_lower = key.lower()
        if key_lower in _PUBLISHED_KEYS and isinstance(val, str) and val.strip():
            dates.append({"source": "jsonld_published", "value": val.strip()})
        elif key_lower in _MODIFIED_KEYS and isinstance(val, str) and val.strip():
            dates.append({"source": "jsonld_modified", "value": val.strip()})
    # Recurse into nested objects (e.g. @graph)
    if "@graph" in data:
        _extract_jsonld_dates(data["@graph"], dates)


def _extract_url_date(url: str) -> str | None:
    """Extract date from URL path patterns like /2024/01/15/."""
    m = _URL_DATE_RE.search(url)
    if not m:
        return None
    year = m.group(1)
    month = m.group(2)
    day = m.group(3)
    if month and day:
        return f"{year}-{month}-{day}"
    if month:
        return f"{year}-{month}"
    return year


def _extract_visible_date(tree: HTMLParser) -> str | None:
    """Extract date from visible text near the top of the article body."""
    # Try article/main containers first, fallback to body
    for selector in ("article", "main", "[role='main']", "body"):
        node = tree.css_first(selector)
        if node:
            text = node.text(separator=" ")[:800]
            for pattern in _VISIBLE_DATE_PATTERNS:
                m = pattern.search(text)
                if m:
                    return m.group(1)
    return None


def _resolve_best(
    dates: list[dict[str, str]], kind: str,
) -> str | None:
    """Pick the best date for 'published' or 'modified' from collected sources.

    Priority: jsonld > og_meta > time_element > url_pattern > visible_text > http_header
    """
    if kind == "published":
        priority = [
            "jsonld_published", "og_published_time", "time_element",
            "url_pattern", "visible_text",
        ]
    else:
        priority = [
            "jsonld_modified", "og_modified_time", "http_last_modified",
        ]
    for source_name in priority:
        for d in dates:
            if d["source"] == source_name:
                return d["value"]
    return None


def extract(
    tree: HTMLParser,
    url: str,
    response_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Extract content freshness signals. Never raises."""
    try:
        dates: list[dict[str, str]] = []

        # Source 1: JSON-LD datePublished / dateModified
        for script in tree.css('script[type="application/ld+json"]'):
            try:
                raw = script.text()
                if raw:
                    data = json.loads(raw)
                    _extract_jsonld_dates(data, dates)
            except (json.JSONDecodeError, TypeError):
                pass

        # Source 2: OG meta article:published_time / article:modified_time
        for tag in tree.css("meta[property]"):
            prop = (tag.attributes.get("property") or "").lower()
            content = (tag.attributes.get("content") or "").strip()
            if prop == "article:published_time" and content:
                dates.append({"source": "og_published_time", "value": content})
            elif prop == "article:modified_time" and content:
                dates.append({"source": "og_modified_time", "value": content})

        # Source 3: <time datetime=""> elements
        for time_el in tree.css("time[datetime]"):
            dt_val = (time_el.attributes.get("datetime") or "").strip()
            if dt_val:
                dates.append({"source": "time_element", "value": dt_val})

        # Source 4: URL date patterns
        url_date = _extract_url_date(url)
        if url_date:
            dates.append({"source": "url_pattern", "value": url_date})

        # Source 5: Visible date strings near top of article
        visible_date = _extract_visible_date(tree)
        if visible_date:
            dates.append({"source": "visible_text", "value": visible_date})

        # Source 6: HTTP Last-Modified header
        if response_headers:
            last_mod = response_headers.get("last-modified")
            if last_mod:
                dates.append({"source": "http_last_modified", "value": last_mod})

        published = _resolve_best(dates, "published")
        modified = _resolve_best(dates, "modified")

        return {
            "published_date": published,
            "modified_date": modified,
            "date_sources": dates,
            "date_source_count": len(dates),
        }
    except Exception:
        return _empty()
