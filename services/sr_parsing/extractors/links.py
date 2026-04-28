"""Link analysis: internal/external, rel attributes, anchor text quality."""
from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse, urljoin

from selectolax.parser import HTMLParser

_GENERIC_ANCHORS = {
    "click here", "here", "read more", "more", "learn more", "this",
    "this page", "this post", "this article", "link", "continue",
    "continue reading", "go", "visit", "see more", "view more",
    "find out more", "more info", "more information",
}


def extract(tree: HTMLParser, url: str) -> dict:
    """Analyze internal/external links, rel attributes, anchor text quality. Never raises."""
    try:
        base_domain = urlparse(url).netloc.replace("www.", "") if url else ""

        all_anchors = tree.css("a[href]")

        total = 0
        internal = 0
        external = 0
        nofollow = 0
        sponsored = 0
        ugc = 0
        noreferrer = 0
        noopener = 0
        blank_target = 0
        http_links = 0
        empty_anchor = 0
        image_only = 0
        generic_anchor = 0
        external_domains: list[str] = []
        anchor_texts: list[str] = []

        for a in all_anchors:
            href = (a.attributes.get("href") or "").strip()
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue

            total += 1

            # selectolax returns rel as a string like "nofollow sponsored"
            rel_str = a.attributes.get("rel") or ""
            rel_values = set(rel_str.lower().split())

            if "nofollow" in rel_values:
                nofollow += 1
            if "sponsored" in rel_values:
                sponsored += 1
            if "ugc" in rel_values:
                ugc += 1
            if "noreferrer" in rel_values:
                noreferrer += 1
            if "noopener" in rel_values:
                noopener += 1

            if (a.attributes.get("target") or "").lower() == "_blank":
                blank_target += 1

            abs_href = urljoin(url, href)
            try:
                parsed = urlparse(abs_href)
                if not parsed.netloc or parsed.netloc.replace("www.", "") == base_domain:
                    internal += 1
                else:
                    external += 1
                    if parsed.scheme == "http":
                        http_links += 1
                    domain = parsed.netloc
                    if domain:
                        external_domains.append(domain)
            except Exception:
                internal += 1

            # Anchor text quality
            text = a.text().strip()
            has_img = bool(a.css_first("img"))

            if not text and not has_img:
                empty_anchor += 1
            elif not text and has_img:
                image_only += 1
            else:
                if text.lower() in _GENERIC_ANCHORS:
                    generic_anchor += 1
                if text:
                    anchor_texts.append(text.lower())

        counter = Counter(anchor_texts)
        top_anchors = [{"text": t, "count": c} for t, c in counter.most_common(15)]

        domain_counter = Counter(external_domains)
        unique_ext_domains = len(domain_counter)
        top_ext_domains = list(domain_counter.keys())[:10]

        return {
            "total_links": total,
            "internal_links": internal,
            "external_links": external,
            "nofollow_links": nofollow,
            "sponsored_links": sponsored,
            "ugc_links": ugc,
            "noreferrer_links": noreferrer,
            "noopener_links": noopener,
            "blank_target_links": blank_target,
            "http_external_links": http_links,
            "empty_anchor_links": empty_anchor,
            "image_only_anchor_links": image_only,
            "generic_anchor_links": generic_anchor,
            "unique_external_domains": unique_ext_domains,
            "top_external_domains": top_ext_domains,
            "top_anchor_texts": top_anchors,
        }
    except Exception:
        return {
            "total_links": 0, "internal_links": 0, "external_links": 0,
            "nofollow_links": 0, "sponsored_links": 0, "ugc_links": 0,
            "noreferrer_links": 0, "noopener_links": 0, "blank_target_links": 0,
            "http_external_links": 0, "empty_anchor_links": 0,
            "image_only_anchor_links": 0, "generic_anchor_links": 0,
            "unique_external_domains": 0, "top_external_domains": [],
            "top_anchor_texts": [],
        }
