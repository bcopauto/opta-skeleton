"""Extract ordered and unordered lists, preserved separately (EXTR-06)."""
from __future__ import annotations

from selectolax.parser import HTMLParser


def extract(tree: HTMLParser, url: str) -> dict:
    """Extract ordered and unordered list items. Never raises."""
    try:
        unordered: list[list[str]] = []
        ordered: list[list[str]] = []

        for ul in tree.css("ul"):
            items = [(li.text() or "").strip() for li in ul.css("li")]
            if items:
                unordered.append(items)

        for ol in tree.css("ol"):
            items = [(li.text() or "").strip() for li in ol.css("li")]
            if items:
                ordered.append(items)

        return {
            "unordered_lists": unordered,
            "ordered_lists": ordered,
            "ul_count": len(unordered),
            "ol_count": len(ordered),
            "total_items": sum(len(lst) for lst in unordered + ordered),
        }
    except Exception:
        return {
            "unordered_lists": [],
            "ordered_lists": [],
            "ul_count": 0,
            "ol_count": 0,
            "total_items": 0,
        }
