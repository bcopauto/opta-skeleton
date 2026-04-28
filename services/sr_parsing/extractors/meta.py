"""Full meta tag extraction: OG, Twitter Card, hreflang, canonical, robots, charset."""
from __future__ import annotations

import re
from urllib.parse import urlparse, urljoin

from selectolax.parser import HTMLParser


def _meta_by_name(tree: HTMLParser, name: str) -> str | None:
    """Get meta tag content by name attribute. Case-insensitive matching."""
    for tag in tree.css("meta[name]"):
        if (tag.attributes.get("name") or "").lower() == name.lower():
            content = (tag.attributes.get("content") or "").strip()
            return content if content else None
    return None


def _meta_by_property(tree: HTMLParser, prop: str) -> str | None:
    """Get meta tag content by property attribute."""
    for tag in tree.css("meta[property]"):
        if (tag.attributes.get("property") or "").lower() == prop.lower():
            content = (tag.attributes.get("content") or "").strip()
            return content if content else None
    return None


def _meta_by_http_equiv(tree: HTMLParser, http_equiv: str) -> str | None:
    """Get meta tag content by http-equiv attribute. Case-insensitive."""
    for tag in tree.css("meta[http-equiv]"):
        if (tag.attributes.get("http-equiv") or "").lower() == http_equiv.lower():
            content = (tag.attributes.get("content") or "").strip()
            return content if content else None
    return None


def _parse_robots(content: str) -> dict:
    """Parse robots meta content into individual directives."""
    parts = [p.strip().lower() for p in (content or "").split(",")]
    max_snippet = None
    max_image = None
    for p in parts:
        m = re.match(r"max-snippet:(-?\d+)", p)
        if m:
            max_snippet = int(m.group(1))
        m = re.match(r"max-image-preview:(\S+)", p)
        if m:
            max_image = m.group(1)
    return {
        "noindex": "noindex" in parts,
        "nofollow": "nofollow" in parts,
        "noarchive": "noarchive" in parts,
        "nosnippet": "nosnippet" in parts,
        "noimageindex": "noimageindex" in parts,
        "max_snippet": max_snippet,
        "max_image_preview": max_image,
    }


def extract(tree: HTMLParser, url: str) -> dict:
    """Extract 40+ meta tag fields including OG, Twitter, hreflang, canonical, robots. Never raises."""
    try:
        # Title
        title_tag = tree.css_first("title")
        title_text = title_tag.text() if title_tag else None
        title_len = len(title_text) if title_text else 0

        # Description
        desc_tag = tree.css_first('meta[name="description"]')
        desc = (desc_tag.attributes.get("content") or "").strip() if desc_tag else None
        desc = desc if desc else None
        desc_len = len(desc) if desc else 0

        # Keywords
        kw_tag = tree.css_first('meta[name="keywords"]')
        keywords = (kw_tag.attributes.get("content") or "").strip() if kw_tag else None
        keywords = keywords if keywords else None

        # Canonical
        canonical_tag = tree.css_first('link[rel="canonical"]')
        canonical_url = (canonical_tag.attributes.get("href") or "").strip() if canonical_tag else None
        if canonical_url:
            canonical_url = urljoin(url, canonical_url)
        canonical_is_self: bool | None = None
        if canonical_url and url:
            try:
                canonical_is_self = urlparse(canonical_url).path == urlparse(url).path
            except Exception:
                pass

        # Robots
        robots_content = _meta_by_name(tree, "robots") or ""
        robots = _parse_robots(robots_content)

        # Googlebot-specific
        googlebot_content = _meta_by_name(tree, "googlebot") or ""
        googlebot = _parse_robots(googlebot_content)

        # Meta refresh
        refresh_content = _meta_by_http_equiv(tree, "refresh")
        refresh_delay: int | None = None
        refresh_present = refresh_content is not None
        if refresh_content:
            m = re.match(r"(\d+)", refresh_content)
            if m:
                refresh_delay = int(m.group(1))

        # Open Graph tags
        og_tags: dict[str, str] = {}
        for tag in tree.css('meta[property^="og:"]'):
            prop = (tag.attributes.get("property") or "").lower().replace("og:", "")
            content = (tag.attributes.get("content") or "").strip()
            if prop and content:
                og_tags[prop] = content

        # Article OG tags
        article_tags: dict[str, str] = {}
        for tag in tree.css('meta[property^="article:"]'):
            prop = (tag.attributes.get("property") or "").lower().replace("article:", "")
            content = (tag.attributes.get("content") or "").strip()
            if prop and content:
                article_tags[prop] = content

        # Twitter Card tags
        tw_tags: dict[str, str] = {}
        for tag in tree.css("meta[name]"):
            name = (tag.attributes.get("name") or "").lower()
            if name.startswith("twitter:"):
                prop = name.replace("twitter:", "")
                content = (tag.attributes.get("content") or "").strip()
                if prop and content:
                    tw_tags[prop] = content

        # Hreflang
        hreflang_tags = tree.css("link[hreflang]")
        hreflang_langs = [t.attributes.get("hreflang", "").lower() for t in hreflang_tags]
        x_default = "x-default" in hreflang_langs

        # Misc head meta
        author = _meta_by_name(tree, "author")
        viewport = _meta_by_name(tree, "viewport")
        theme_color = _meta_by_name(tree, "theme-color")
        rating = _meta_by_name(tree, "rating")

        # Charset from <meta charset> or http-equiv content-type
        charset_tag = tree.css_first("meta[charset]")
        charset: str | None = None
        if charset_tag:
            charset = (charset_tag.attributes.get("charset") or "").strip() or None
        else:
            ct = _meta_by_http_equiv(tree, "content-type") or ""
            m = re.search(r"charset=([\w-]+)", ct, re.I)
            if m:
                charset = m.group(1)

        # x-ua-compatible
        x_ua = _meta_by_http_equiv(tree, "x-ua-compatible")

        return {
            # Title
            "title": title_text,
            "title_length": title_len,
            "title_pixel_width_est": round(title_len * 7.0),

            # Description
            "meta_description": desc,
            "meta_description_length": desc_len,

            # Keywords
            "meta_keywords": keywords,

            # Canonical
            "canonical_url": canonical_url,
            "canonical_is_self": canonical_is_self,

            # Robots
            "robots_noindex": robots["noindex"],
            "robots_nofollow": robots["nofollow"],
            "robots_noarchive": robots["noarchive"],
            "robots_nosnippet": robots["nosnippet"],
            "robots_noimageindex": robots["noimageindex"],
            "robots_max_snippet": robots["max_snippet"],
            "robots_max_image_preview": robots["max_image_preview"],
            "googlebot_noindex": googlebot["noindex"],
            "googlebot_nofollow": googlebot["nofollow"],

            # Refresh
            "meta_refresh": refresh_present,
            "meta_refresh_delay_s": refresh_delay,

            # Open Graph
            "og_title": og_tags.get("title"),
            "og_description": og_tags.get("description"),
            "og_image": og_tags.get("image"),
            "og_type": og_tags.get("type"),
            "og_url": og_tags.get("url"),
            "og_site_name": og_tags.get("site_name"),
            "og_locale": og_tags.get("locale"),
            "og_present": bool(og_tags),

            # Article OG
            "article_published_time": article_tags.get("published_time"),
            "article_modified_time": article_tags.get("modified_time"),
            "article_section": article_tags.get("section"),
            "article_tag": article_tags.get("tag"),

            # Twitter Card
            "twitter_card": tw_tags.get("card"),
            "twitter_title": tw_tags.get("title"),
            "twitter_description": tw_tags.get("description"),
            "twitter_image": tw_tags.get("image"),
            "twitter_site": tw_tags.get("site"),
            "twitter_creator": tw_tags.get("creator"),
            "twitter_present": bool(tw_tags),

            # Hreflang
            "hreflang_count": len(hreflang_tags),
            "hreflang_langs": hreflang_langs,
            "hreflang_x_default": x_default,

            # Misc
            "meta_author": author,
            "meta_viewport": viewport,
            "meta_charset": charset,
            "meta_theme_color": theme_color,
            "meta_rating": rating,
            "x_ua_compatible": x_ua,
        }
    except Exception:
        return {
            "title": None, "title_length": 0, "title_pixel_width_est": 0,
            "meta_description": None, "meta_description_length": 0,
            "meta_keywords": None,
            "canonical_url": None, "canonical_is_self": None,
            "robots_noindex": False, "robots_nofollow": False,
            "robots_noarchive": False, "robots_nosnippet": False,
            "robots_noimageindex": False, "robots_max_snippet": None,
            "robots_max_image_preview": None,
            "googlebot_noindex": False, "googlebot_nofollow": False,
            "meta_refresh": False, "meta_refresh_delay_s": None,
            "og_title": None, "og_description": None, "og_image": None,
            "og_type": None, "og_url": None, "og_site_name": None,
            "og_locale": None, "og_present": False,
            "article_published_time": None, "article_modified_time": None,
            "article_section": None, "article_tag": None,
            "twitter_card": None, "twitter_title": None,
            "twitter_description": None, "twitter_image": None,
            "twitter_site": None, "twitter_creator": None,
            "twitter_present": False,
            "hreflang_count": 0, "hreflang_langs": [],
            "hreflang_x_default": False,
            "meta_author": None, "meta_viewport": None,
            "meta_charset": None, "meta_theme_color": None,
            "meta_rating": None, "x_ua_compatible": None,
        }
