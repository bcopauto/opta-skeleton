"""Extract callout boxes: elements with class/role hints (EXTR-11)."""
from __future__ import annotations

from selectolax.parser import HTMLParser

_CALLOUT_SELECTORS = [
    '[class*="callout"]',
    '[class*="notice"]',
    '[class*="alert"]',
    '[class*="info"]',
    '[class*="tip"]',
    '[class*="warning"]',
    '[class*="highlight"]',
    '[class*="note"]',
    '[class*="important"]',
    '[class*="caution"]',
    '[role="alert"]',
    '[role="note"]',
    '[role="status"]',
]


def extract(tree: HTMLParser, url: str) -> dict:
    """Extract callout boxes by class/role patterns. Never raises."""
    try:
        callouts: list[dict[str, str]] = []
        seen_html: set[str] = set()

        for selector in _CALLOUT_SELECTORS:
            for el in tree.css(selector):
                # Avoid double-counting elements matched by multiple selectors
                el_html = el.html
                if el_html in seen_html:
                    continue
                seen_html.add(el_html)

                text = el.text().strip()
                classes = el.attributes.get("class") or ""
                role = el.attributes.get("role") or ""

                callouts.append({
                    "text": text[:500] if text else "",
                    "classes": classes,
                    "role": role,
                    "tag": el.tag,
                })

        return {
            "has_callouts": len(callouts) > 0,
            "callout_count": len(callouts),
            "callouts": callouts,
        }
    except Exception:
        return {"has_callouts": False, "callout_count": 0, "callouts": []}
