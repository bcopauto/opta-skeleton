"""URL validation, normalization, and deduplication functions.

Per D-12: lowercase scheme+host, strip trailing slash, sort query params,
strip fragments, remove default ports (:80/:443).
Per D-13: exact match after normalization.
Per D-14: reject invalid upfront (no scheme, spaces, unparseable).
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def is_valid_url(url: str) -> bool:
    """Check if URL has http/https scheme and valid netloc. No DNS checks.

    Args:
        url: URL string to validate.

    Returns:
        True if URL has http/https scheme and valid netloc, False otherwise.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if not parsed.netloc:
            return False
        if " " in url:
            return False
        return True
    except Exception:
        return False


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication.

    Per D-12: lowercase scheme+host, strip trailing slash, sort query params,
    strip fragments, remove default ports (:80/:443).

    Args:
        url: URL string to normalize.

    Returns:
        Normalized URL string.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove default ports
    if parsed.port == 80 and scheme == "http":
        netloc = parsed.hostname.lower() if parsed.hostname else netloc
    elif parsed.port == 443 and scheme == "https":
        netloc = parsed.hostname.lower() if parsed.hostname else netloc

    # Strip trailing slash from path, but keep "/" if there's a query string
    # Per D-12: strip trailing slash from all paths
    if parsed.path == "/":
        # Keep "/" if there's a query string, otherwise strip it
        path = "/" if parsed.query else ""
    else:
        path = parsed.path.rstrip("/")

    # Sort query params for stable comparison
    params = sorted(parse_qsl(parsed.query))
    query = urlencode(params)
    # Drop fragment
    return urlunparse((scheme, netloc, path, parsed.params, query, ""))


def deduplicate_urls(urls: list[str]) -> list[str]:
    """Return deduplicated list preserving first-seen order.

    Per D-13: exact match after normalization.

    Args:
        urls: List of URL strings to deduplicate.

    Returns:
        Deduplicated list with first-seen order preserved.
    """
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        normalized = normalize_url(url)
        if normalized not in seen:
            seen.add(normalized)
            result.append(url)
    return result
