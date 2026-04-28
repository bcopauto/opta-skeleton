"""Extract page title from <title> tag (EXTR-01)."""
from __future__ import annotations

from selectolax.parser import HTMLParser


def extract(tree: HTMLParser, url: str) -> dict:
    """Extract page title. Returns dict with title text and length. Never raises."""
    try:
        title_tag = tree.css_first("title")
        title_text = title_tag.text() if title_tag else None
        return {
            "title": title_text,
            "title_length": len(title_text) if title_text else 0,
        }
    except Exception:
        return {"title": None, "title_length": 0}
