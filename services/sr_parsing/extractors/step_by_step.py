"""Detect step-by-step content: OL in How to/Steps sections + HowTo schema (EXTR-12)."""
from __future__ import annotations

import json
import re

from selectolax.parser import HTMLParser

_HOW_TO_HEADING_RE = re.compile(
    r"how\s+to|step|guide|tutorial|instruction|walkthrough|directions",
    re.I,
)


def extract(tree: HTMLParser, url: str) -> dict:
    """Detect step-by-step content. Checks for HowTo schema and OL in step-related sections. Never raises."""
    try:
        # Pattern 1: HowTo JSON-LD schema
        schema_steps: list[str] = []
        for script in tree.css('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.text())
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if (item.get("@type") or "").lower() == "howto":
                        for step in (item.get("step") or []):
                            text = step.get("text") or ""
                            if not text:
                                text = step.get("name") or ""
                            if text:
                                schema_steps.append(text)
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        # Pattern 2: Ordered lists preceded by headings with step-related keywords
        html_steps: list[dict] = []
        heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}

        body = tree.body
        if body:
            nodes = list(body.traverse())
            for i, node in enumerate(nodes):
                if node.tag in heading_tags:
                    heading_text = node.text().strip()
                    if not _HOW_TO_HEADING_RE.search(heading_text):
                        continue
                    # Look for the next OL within the next few nodes
                    for j in range(i + 1, min(i + 10, len(nodes))):
                        if nodes[j].tag == "ol":
                            items = [
                                (li.text() or "").strip()
                                for li in nodes[j].css("li")
                            ]
                            if items:
                                html_steps.append({
                                    "heading": heading_text,
                                    "steps": items,
                                })
                            break
                        # Stop if we hit another heading
                        if nodes[j].tag in heading_tags:
                            break

        has_steps = bool(schema_steps or html_steps)

        return {
            "has_steps": has_steps,
            "schema_step_count": len(schema_steps),
            "schema_steps": schema_steps,
            "html_step_groups": len(html_steps),
            "html_steps": html_steps,
            "total_step_count": len(schema_steps) + sum(len(g.get("steps", [])) for g in html_steps),
        }
    except Exception:
        return _empty()


def _empty() -> dict:
    return {
        "has_steps": False, "schema_step_count": 0,
        "schema_steps": [], "html_step_groups": 0,
        "html_steps": [], "total_step_count": 0,
    }
