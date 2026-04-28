"""Extract visible body text using readability heuristics (EXTR-04)."""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser

_STRIP_TAGS = ["script", "style", "noscript", "head", "nav", "footer", "header"]
_WORDS_PER_MINUTE = 200


def extract(tree: HTMLParser, url: str) -> dict:
    """Extract visible body text. Strips nav, footer, scripts, styles. Never raises."""
    try:
        # Clone tree to avoid mutating the original
        tree2 = HTMLParser(tree.html)
        tree2.strip_tags(_STRIP_TAGS)
        body = tree2.body
        if not body:
            return _empty()

        visible = body.text()
        if not visible:
            return _empty()

        words = visible.split()
        word_count = len(words)
        char_count = len(visible)

        # Sentence count (approximate)
        sentences = re.split(r"[.!?]+", visible)
        sentence_count = sum(1 for s in sentences if s.strip())

        # Paragraph count from original tree (not stripped)
        paragraphs = tree.css("p")
        para_count = len(paragraphs)

        # Text/HTML ratio
        html_bytes = len(tree.html.encode("utf-8"))
        text_bytes = len(visible.encode("utf-8"))
        text_html_ratio = round(text_bytes / html_bytes, 4) if html_bytes else 0

        # Reading time
        reading_time_s = round((word_count / _WORDS_PER_MINUTE) * 60) if word_count else 0

        # Language from <html lang>
        html_tag = tree.css_first("html")
        lang = (html_tag.attributes.get("lang") or "").strip() if html_tag else ""

        return {
            "word_count": word_count,
            "char_count": char_count,
            "sentence_count": sentence_count,
            "paragraph_count": para_count,
            "text_html_ratio": text_html_ratio,
            "reading_time_s": reading_time_s,
            "lang": lang or None,
            "text": visible.strip(),
        }
    except Exception:
        return _empty()


def _empty() -> dict:
    return {
        "word_count": 0, "char_count": 0, "sentence_count": 0,
        "paragraph_count": 0, "text_html_ratio": 0, "reading_time_s": 0,
        "lang": None, "text": "",
    }
