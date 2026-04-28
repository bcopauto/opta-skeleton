"""Extract heading structure: h1-h6 counts, texts, hierarchy issues (EXTR-03)."""
from __future__ import annotations

from selectolax.parser import HTMLParser

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


def extract(tree: HTMLParser, url: str) -> dict:
    """Extract heading structure. Returns dict with counts, texts, hierarchy issues. Never raises."""
    try:
        headings: list[dict[str, str | int]] = []
        seen_levels: set[int] = set()
        hierarchy_issues: list[str] = []

        body = tree.body
        if not body:
            return _empty()

        for node in body.traverse():
            if node.tag in _HEADING_TAGS:
                level = int(node.tag[1])
                text = node.text()
                headings.append({"level": level, "text": text, "tag": node.tag})

                if level > 1 and (level - 1) not in seen_levels and not any(l < level for l in seen_levels):
                    hierarchy_issues.append(f"h{level} before h{level - 1}")
                seen_levels.add(level)

        h1_texts = [h["text"] for h in headings if h["tag"] == "h1"]
        h2_texts = [h["text"] for h in headings if h["tag"] == "h2"]

        counts = {}
        for tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            counts[f"{tag_name}_count"] = sum(1 for h in headings if h["tag"] == tag_name)

        empty_count = sum(1 for h in headings if not h["text"])
        heading_words = sum(len(str(h["text"]).split()) for h in headings)
        first_heading = headings[0]["tag"] if headings else None
        duplicate_h1 = counts["h1_count"] > 1

        return {
            **counts,
            "total_headings": len(headings),
            "h1_texts": h1_texts,
            "h2_texts": h2_texts,
            "first_heading_tag": first_heading,
            "duplicate_h1": duplicate_h1,
            "empty_headings": empty_count,
            "heading_word_count": heading_words,
            "hierarchy_issues": list(set(hierarchy_issues)),
        }
    except Exception:
        return _empty()


def _empty() -> dict:
    return {
        "h1_count": 0, "h2_count": 0, "h3_count": 0,
        "h4_count": 0, "h5_count": 0, "h6_count": 0,
        "total_headings": 0, "h1_texts": [], "h2_texts": [],
        "first_heading_tag": None, "duplicate_h1": False,
        "empty_headings": 0, "heading_word_count": 0,
        "hierarchy_issues": [],
    }
