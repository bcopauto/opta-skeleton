"""Lightweight content sufficiency check for raw HTML (FETCH-05).

Determines whether static HTML from httpx has enough content to skip
Playwright rendering. Uses regex on raw HTML strings -- no DOM parsing.
"""
from __future__ import annotations

import re

_JS_REQUIRED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"enable\s+javascript", re.IGNORECASE),
    re.compile(r"javascript\s+is\s+required", re.IGNORECASE),
    re.compile(r"javascript\s+is\s+disabled", re.IGNORECASE),
    re.compile(r"requires\s+javascript", re.IGNORECASE),
]

_SPA_ROOT_IDS: list[str] = ["root", "app", "__next", "__nuxt"]


def is_content_sufficient(html: str, min_body_chars: int = 500) -> bool:
    """Return True if the HTML has enough visible content to skip rendering.

    Checks for JS-required messages, empty SPA root divs, and body text length.
    """
    if not html:
        return False

    html_lower = html.lower()

    # Check 1: JS-required messages in noscript tags and visible text
    noscript_matches = re.findall(
        r"<noscript>(.*?)</noscript>", html, re.IGNORECASE | re.DOTALL
    )
    combined = html_lower + " " + " ".join(m.lower() for m in noscript_matches)
    for pattern in _JS_REQUIRED_PATTERNS:
        if pattern.search(combined):
            return False

    # Check 2: Strip script/style tags, then strip all HTML tags to get visible text
    stripped = re.sub(
        r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL
    )
    stripped = re.sub(
        r"<style[^>]*>.*?</style>", "", stripped, flags=re.IGNORECASE | re.DOTALL
    )
    stripped = re.sub(r"<[^>]+>", "", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()

    if len(stripped) < min_body_chars:
        return False

    return True
