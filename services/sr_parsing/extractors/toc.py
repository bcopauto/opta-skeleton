"""Detect table of contents: anchor links to in-page headings (EXTR-09)."""
from __future__ import annotations

from selectolax.parser import HTMLParser


def extract(tree: HTMLParser, url: str) -> dict:
    """Detect table of contents via anchor links to heading IDs. Never raises."""
    try:
        # Collect heading IDs from the page
        heading_ids: set[str] = set()
        heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
        body = tree.body
        if body:
            for node in body.traverse():
                if node.tag in heading_tags:
                    heading_id = node.attributes.get("id") or ""
                    if heading_id:
                        heading_ids.add(heading_id)

        # Find anchor links that point to heading IDs
        toc_links: list[dict[str, str]] = []
        for anchor in tree.css("a[href]"):
            href = (anchor.attributes.get("href") or "").strip()
            if not href.startswith("#") or len(href) < 2:
                continue
            target_id = href[1:]  # Strip the #
            if target_id in heading_ids:
                toc_links.append({
                    "text": anchor.text().strip(),
                    "href": href,
                    "target_id": target_id,
                })

        has_toc = len(toc_links) >= 2  # At least 2 links to headings suggests a TOC

        return {
            "has_toc": has_toc,
            "toc_link_count": len(toc_links),
            "toc_links": toc_links,
        }
    except Exception:
        return {"has_toc": False, "toc_link_count": 0, "toc_links": []}
