"""Extract structured data from framework-embedded JSON in HTML (FETCH-06, FETCH-07).

Parses __NEXT_DATA__, __NUXT__, and __APOLLO_STATE__ script tags to extract
page content without launching a browser. Each framework has its own extraction
and reconstruction logic.
"""
from __future__ import annotations

import json
import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def extract_xhr_content(html: str) -> str | None:
    """Try to extract meaningful content from embedded framework data.

    Tries Next.js, Nuxt.js, and Apollo in order. Returns the first
    successful reconstruction, or None if no framework data is found.
    """
    # Next.js: <script id="__NEXT_DATA__" type="application/json">{...}</script>
    next_data = _extract_script_json(html, "__NEXT_DATA__")
    if next_data is not None:
        content = _reconstruct_from_next_data(next_data)
        if content is not None:
            return content

    # Nuxt.js: window.__NUXT__ = {...};
    nuxt_data = _extract_assignment_json(html, "__NUXT__")
    if nuxt_data is not None:
        content = _reconstruct_from_nuxt_data(nuxt_data)
        if content is not None:
            return content

    # Apollo/GraphQL: window.__APOLLO_STATE__ = {...};
    apollo_data = _extract_assignment_json(html, "__APOLLO_STATE__")
    if apollo_data is not None:
        content = _reconstruct_from_apollo(apollo_data)
        if content is not None:
            return content

    return None


def _extract_script_json(html: str, script_id: str) -> dict[str, Any] | None:
    """Extract JSON from a <script id="..." type="application/json"> tag."""
    pattern = rf'<script\s+id="{re.escape(script_id)}"[^>]*type="application/json"[^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    try:
        result: dict[str, Any] = json.loads(match.group(1))
        return result
    except json.JSONDecodeError:
        logger.warning("xhr_sniffer.script_json_parse_failed", script_id=script_id)
        return None


def _extract_assignment_json(html: str, var_name: str) -> dict[str, Any] | None:
    """Extract JSON from a window.__VAR__ = {...}; assignment in a script tag."""
    pattern = rf'{re.escape(var_name)}\s*=\s*(\{{.*?\}})\s*;?\s*</script>'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return None
    try:
        result: dict[str, Any] = json.loads(match.group(1))
        return result
    except json.JSONDecodeError:
        logger.warning("xhr_sniffer.assignment_json_parse_failed", var_name=var_name)
        return None


def _reconstruct_from_next_data(data: dict[str, Any]) -> str | None:
    """Reconstruct HTML from Next.js __NEXT_DATA__ structure.

    Navigates data.props.pageProps and looks for common content keys.
    Falls back to wrapping the full pageProps as JSON in HTML.
    """
    page_props = data.get("props", {}).get("pageProps", {})
    if not page_props:
        return None

    # Try common content keys in priority order
    for key in ("content", "body", "html", "description"):
        value = page_props.get(key)
        if isinstance(value, str) and len(value) > 100:
            return value

    # Wrap full pageProps as JSON for the extraction pipeline
    dumped = json.dumps(page_props, ensure_ascii=False)
    return f"<html><body><pre>{dumped}</pre></body></html>"


def _reconstruct_from_nuxt_data(data: dict[str, Any]) -> str | None:
    """Reconstruct HTML from Nuxt.js __NUXT__ data.

    Tries common content keys, falls back to JSON dump.
    """
    # Nuxt may nest under "data" or be flat
    content_source = data.get("data", data)

    # Try common content keys on dicts
    if isinstance(content_source, dict):
        for key in ("content", "body", "html", "description", "pageContent"):
            value = content_source.get(key)
            if isinstance(value, str) and len(value) > 100:
                return value

    # Wrap as JSON if there's content worth extracting
    if content_source:
        dumped = json.dumps(content_source, ensure_ascii=False)
        if len(dumped) > 100:
            return f"<html><body><pre>{dumped}</pre></body></html>"

    return None


def _reconstruct_from_apollo(data: dict[str, Any]) -> str | None:
    """Reconstruct HTML from Apollo __APOLLO_STATE__ data.

    Apollo state is a flat dict of entities keyed like "Article:123".
    Collects all string values > 50 chars and wraps them as JSON.
    """
    if not data:
        return None

    # Collect substantial string values from all entities
    collected: list[dict[str, str]] = []
    for _key, entity in data.items():
        if not isinstance(entity, dict):
            continue
        for field_name, field_value in entity.items():
            if isinstance(field_value, str) and len(field_value) > 50:
                collected.append({"field": field_name, "value": field_value})

    if not collected:
        return None

    total_len = sum(len(item["value"]) for item in collected)
    if total_len < 100:
        return None

    dumped = json.dumps(collected, ensure_ascii=False)
    return f"<html><body><pre>{dumped}</pre></body></html>"
