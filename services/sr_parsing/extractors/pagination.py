"""Pagination signals: rel next/prev, page number patterns in URL, nav detection."""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser

_PAGE_IN_URL_RE = re.compile(
    r"[?&/](page|p|pg|paged|pagenum|start|offset)[=/](\d+)",
    re.I,
)

_PAGINATION_CLASS_RE = re.compile(
    r"paginat|pager\b|page-nav|wp-pagenavi",
    re.I,
)

_INFINITE_SCROLL_RE = re.compile(
    r"infinite.?scroll|load.?more|fetch.*next",
    re.I,
)


def extract(tree: HTMLParser, url: str) -> dict:
    """Detect rel next/prev, page number patterns, pagination nav. Never raises."""
    try:
        # rel="next" / rel="prev" -- use CSS selectors for exact match
        next_link = tree.css_first('link[rel="next"]')
        prev_link = tree.css_first('link[rel="prev"]')

        next_url = (next_link.attributes.get("href") or "").strip() if next_link else None
        prev_url = (prev_link.attributes.get("href") or "").strip() if prev_link else None

        # Page number in the current URL
        page_in_url = bool(_PAGE_IN_URL_RE.search(url)) if url else False

        # Pagination nav element -- check nav/div/ul for pagination class patterns
        pagination_nav = False
        for tag in tree.css("nav, div, ul"):
            classes = tag.attributes.get("class") or ""
            tag_id = tag.attributes.get("id") or ""
            aria_label = tag.attributes.get("aria-label") or ""
            combined = f"{classes} {tag_id} {aria_label}"
            if _PAGINATION_CLASS_RE.search(combined):
                pagination_nav = True
                break

        # Infinite scroll signal -- search full HTML
        full_html = tree.html or ""
        has_infinite_scroll = bool(_INFINITE_SCROLL_RE.search(full_html))

        return {
            "has_rel_next": next_link is not None,
            "rel_next_url": next_url,
            "has_rel_prev": prev_link is not None,
            "rel_prev_url": prev_url,
            "page_number_in_url": page_in_url,
            "has_pagination_nav": pagination_nav,
            "has_infinite_scroll": has_infinite_scroll,
        }
    except Exception:
        return {
            "has_rel_next": False, "rel_next_url": None,
            "has_rel_prev": False, "rel_prev_url": None,
            "page_number_in_url": False,
            "has_pagination_nav": False,
            "has_infinite_scroll": False,
        }
