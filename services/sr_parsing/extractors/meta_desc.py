"""Extract meta description from <meta name='description'> (EXTR-02)."""
from __future__ import annotations

from selectolax.parser import HTMLParser


def extract(tree: HTMLParser, url: str) -> dict:
    """Extract meta description. Returns dict with description text and length. Never raises."""
    try:
        desc_tag = tree.css_first('meta[name="description"]')
        desc = (desc_tag.attributes.get("content") or "").strip() if desc_tag else None
        return {
            "meta_description": desc if desc else None,
            "meta_description_length": len(desc) if desc else 0,
        }
    except Exception:
        return {"meta_description": None, "meta_description_length": 0}
