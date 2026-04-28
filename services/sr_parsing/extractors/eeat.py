"""E-E-A-T signal extractor: author expertise, trust, and authority signals.

Extracts:
  - Author byline and bio sections
  - "Reviewed by" / "Fact-checked by" attributions
  - Contact and about page links
  - Citation counts (external links in article body)
  - Expertise credential signals
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from selectolax.parser import HTMLParser

# CSS class/id patterns that indicate author-related elements
_AUTHOR_PATTERNS = re.compile(
    r"author|byline|writer|contributor|posted-by|written-by",
    re.IGNORECASE,
)

_AUTHOR_BIO_PATTERNS = re.compile(
    r"author-bio|about-author|author-info|author-box|author-profile|author-card|bio-section",
    re.IGNORECASE,
)

# Visible text patterns for review/fact-check attributions
_REVIEWED_BY_RE = re.compile(
    r"(?:reviewed|fact[- ]?checked|medically reviewed|edited|verified)\s+by\s+([A-Z][a-zA-Z.\s'-]{2,40})",
    re.IGNORECASE,
)

# Expertise credential patterns
_CREDENTIAL_RE = re.compile(
    r"\b(Ph\.?D\.?|M\.?D\.?|R\.?N\.?|CPA|CFA|J\.?D\.?|MBA|certified|licensed|board[- ]certified)\b",
    re.IGNORECASE,
)

# Authoritative TLDs for citation counting
_AUTHORITATIVE_TLDS = frozenset({".gov", ".edu", ".ac.uk", ".org"})


def _empty() -> dict[str, Any]:
    return {
        "author_name": None,
        "author_byline_found": False,
        "reviewed_by": None,
        "reviewed_by_found": False,
        "author_bio_found": False,
        "author_bio_text": None,
        "contact_page_linked": False,
        "email_visible": False,
        "about_page_linked": False,
        "citation_count": 0,
        "authoritative_citations": 0,
        "expertise_signals": [],
        "trust_signals_count": 0,
    }


def _matches_pattern(node: Any, pattern: re.Pattern[str]) -> bool:
    """Check if a node's class or id attributes match the given regex."""
    cls = node.attributes.get("class") or ""
    node_id = node.attributes.get("id") or ""
    return bool(pattern.search(cls) or pattern.search(node_id))


def _extract_author(tree: HTMLParser) -> tuple[str | None, bool]:
    """Find author name from byline elements or meta tags."""
    # Try elements with author-related class/id
    for tag in ("span", "a", "div", "p", "address", "li"):
        for node in tree.css(tag):
            if _matches_pattern(node, _AUTHOR_PATTERNS):
                text = (node.text(separator=" ") or "").strip()
                # Filter out empty or very long text (likely not just a name)
                if 2 < len(text) < 100:
                    return text, True

    # Try rel="author" links
    for node in tree.css('a[rel="author"]'):
        text = (node.text(separator=" ") or "").strip()
        if 2 < len(text) < 100:
            return text, True

    # Fallback: meta author tag
    meta = tree.css_first('meta[name="author"]')
    if meta:
        content = (meta.attributes.get("content") or "").strip()
        if content:
            return content, True

    return None, False


def _extract_reviewed_by(tree: HTMLParser) -> tuple[str | None, bool]:
    """Find 'reviewed by' / 'fact-checked by' attributions in visible text."""
    # Check specific containers first (often in a dedicated section)
    for selector in ("article", "main", "[role='main']", "body"):
        node = tree.css_first(selector)
        if node:
            text = node.text(separator=" ")[:3000]
            m = _REVIEWED_BY_RE.search(text)
            if m:
                return m.group(1).strip(), True
    return None, False


def _extract_author_bio(tree: HTMLParser) -> tuple[bool, str | None]:
    """Find author bio section."""
    for tag in ("div", "section", "aside", "p"):
        for node in tree.css(tag):
            if _matches_pattern(node, _AUTHOR_BIO_PATTERNS):
                text = (node.text(separator=" ") or "").strip()
                if len(text) > 10:
                    return True, text[:500]
    return False, None


def _check_contact_links(tree: HTMLParser) -> tuple[bool, bool, bool]:
    """Check for contact page, about page, and visible email links."""
    contact_linked = False
    about_linked = False
    email_visible = False

    for a in tree.css("a[href]"):
        href = (a.attributes.get("href") or "").lower()
        if "/contact" in href:
            contact_linked = True
        if "/about" in href or "/about-us" in href:
            about_linked = True
        if href.startswith("mailto:"):
            email_visible = True

    return contact_linked, about_linked, email_visible


def _count_citations(tree: HTMLParser) -> tuple[int, int]:
    """Count external links in article body as citations.

    Returns (total_external_citations, authoritative_citations).
    """
    # Find the main content container
    container = None
    for selector in ("article", "main", "[role='main']"):
        container = tree.css_first(selector)
        if container:
            break
    if container is None:
        container = tree.css_first("body")
    if container is None:
        return 0, 0

    total = 0
    authoritative = 0
    seen_domains: set[str] = set()

    for a in container.css("a[href]"):
        href = a.attributes.get("href") or ""
        if not href.startswith("http"):
            continue
        try:
            parsed = urlparse(href)
            domain = parsed.netloc.lower()
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)
            total += 1
            # Check if domain uses an authoritative TLD
            if any(domain.endswith(tld) for tld in _AUTHORITATIVE_TLDS):
                authoritative += 1
        except Exception:
            continue

    return total, authoritative


def _find_expertise_signals(tree: HTMLParser, author_name: str | None) -> list[str]:
    """Look for credential patterns near author-related content."""
    signals: list[str] = []

    # Scan author-related elements and nearby text
    search_text = ""
    for tag in ("span", "div", "p", "a", "address"):
        for node in tree.css(tag):
            if _matches_pattern(node, _AUTHOR_PATTERNS) or _matches_pattern(node, _AUTHOR_BIO_PATTERNS):
                search_text += " " + (node.text(separator=" ") or "")

    # Also check the author name context if we found one
    if author_name:
        # Search for credentials near the author name in full body
        body = tree.css_first("body")
        if body:
            full_text = body.text(separator=" ")[:5000]
            idx = full_text.lower().find(author_name.lower())
            if idx >= 0:
                # Check 200 chars around the author name
                start = max(0, idx - 50)
                end = min(len(full_text), idx + len(author_name) + 200)
                search_text += " " + full_text[start:end]

    for m in _CREDENTIAL_RE.finditer(search_text):
        cred = m.group(1).strip()
        if cred not in signals:
            signals.append(cred)

    return signals


def extract(tree: HTMLParser, url: str) -> dict[str, Any]:
    """Extract E-E-A-T signals. Never raises."""
    try:
        author_name, author_byline_found = _extract_author(tree)
        reviewed_by, reviewed_by_found = _extract_reviewed_by(tree)
        author_bio_found, author_bio_text = _extract_author_bio(tree)
        contact_linked, about_linked, email_visible = _check_contact_links(tree)
        citation_count, authoritative_citations = _count_citations(tree)
        expertise_signals = _find_expertise_signals(tree, author_name)

        # Count total trust signals present
        trust_count = sum([
            author_byline_found,
            reviewed_by_found,
            author_bio_found,
            contact_linked,
            about_linked,
            email_visible,
            citation_count > 0,
            authoritative_citations > 0,
            len(expertise_signals) > 0,
        ])

        return {
            "author_name": author_name,
            "author_byline_found": author_byline_found,
            "reviewed_by": reviewed_by,
            "reviewed_by_found": reviewed_by_found,
            "author_bio_found": author_bio_found,
            "author_bio_text": author_bio_text,
            "contact_page_linked": contact_linked,
            "email_visible": email_visible,
            "about_page_linked": about_linked,
            "citation_count": citation_count,
            "authoritative_citations": authoritative_citations,
            "expertise_signals": expertise_signals,
            "trust_signals_count": trust_count,
        }
    except Exception:
        return _empty()
