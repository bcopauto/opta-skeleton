"""Technical signals: scripts, styles, resource hints, trackers, AMP."""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser

# Pre-compiled patterns for tracker detection
_GTM_RE = re.compile(r"googletagmanager\.com", re.I)
_GA_RE = re.compile(r"google-analytics\.com|googletagmanager\.com/gtag|gtag\(", re.I)
_FB_PIXEL = re.compile(r"connect\.facebook\.net|fbq\(", re.I)
_HOTJAR = re.compile(r"hotjar\.com|hjid", re.I)
_INTERCOM = re.compile(r"intercom", re.I)
_HUBSPOT = re.compile(r"hs-scripts\.com|hubspot", re.I)
_SEGMENT = re.compile(r"segment\.com|analytics\.js", re.I)

_CONSENT_RE = re.compile(
    r"cookiebot|onetrust|cookieconsent|gdpr|cookie.consent|cc-banner|"
    r"cookiepolicy|cookie-law|cookie-notice|usercentrics|quantcast",
    re.I,
)


def extract(tree: HTMLParser, url: str) -> dict:
    """Extract scripts, styles, trackers, and technical signals. Never raises."""
    try:
        # Viewport / mobile
        viewport_tag = tree.css_first('meta[name="viewport"]')
        viewport_content = (viewport_tag.attributes.get("content") or "").strip() if viewport_tag else None

        # AMP detection
        html_tag = tree.css_first("html")
        is_amp = False
        if html_tag:
            attrs = html_tag.attributes
            is_amp = "amp" in attrs or "\u26a1" in attrs

        amphtml_link = tree.css_first('link[rel="amphtml"]') is not None

        # Charset
        charset_tag = tree.css_first("meta[charset]")
        charset = (charset_tag.attributes.get("charset") or "").strip() if charset_tag else None

        # HTTPS
        is_https = url.startswith("https://") if url else None

        # Favicons / touch icons
        has_favicon = (
            tree.css_first('link[rel="icon"]') is not None
            or tree.css_first('link[rel="shortcut icon"]') is not None
        )
        has_apple_touch_icon = tree.css_first('link[rel="apple-touch-icon"]') is not None

        # Web manifest / PWA
        has_web_manifest = tree.css_first('link[rel="manifest"]') is not None

        # Feeds
        has_rss = tree.css_first('link[type="application/rss+xml"]') is not None
        has_atom = tree.css_first('link[type="application/atom+xml"]') is not None

        # Resource hints -- iterate link tags and check rel string
        dns_prefetch = 0
        preload = 0
        prefetch = 0
        preconnect = 0
        for link in tree.css("link[rel]"):
            rel = (link.attributes.get("rel") or "").lower()
            if "dns-prefetch" in rel:
                dns_prefetch += 1
            if "preload" in rel:
                preload += 1
            if "prefetch" in rel:
                prefetch += 1
            if "preconnect" in rel:
                preconnect += 1

        # Scripts
        all_scripts = tree.css("script")
        total_scripts = len(all_scripts)
        async_scripts = sum(1 for s in all_scripts if "async" in s.attributes)
        defer_scripts = sum(1 for s in all_scripts if "defer" in s.attributes)
        inline_scripts = sum(
            1 for s in all_scripts
            if not s.attributes.get("src") and (s.text() or "").strip()
        )
        external_scripts = sum(1 for s in all_scripts if s.attributes.get("src"))

        # Render-blocking: external scripts in <head> without async/defer
        head = tree.head
        blocking_scripts = 0
        if head:
            for s in head.css("script"):
                if s.attributes.get("src") and "async" not in s.attributes and "defer" not in s.attributes:
                    blocking_scripts += 1

        # Module scripts
        module_scripts = sum(
            1 for s in all_scripts
            if (s.attributes.get("type") or "").lower() == "module"
        )

        # Styles
        total_styles = len(tree.css("style"))

        # External stylesheets: links where rel contains "stylesheet"
        external_css = 0
        for link in tree.css("link[rel]"):
            if "stylesheet" in (link.attributes.get("rel") or "").lower():
                external_css += 1

        # Inline style attributes -- check elements that have style attr
        inline_style_attrs = len(tree.css("[style]"))

        # Noscript
        noscript_count = len(tree.css("noscript"))

        # Tracker detection via script content/src
        script_parts: list[str] = []
        for s in all_scripts:
            src = s.attributes.get("src") or ""
            script_parts.append(src)
            script_parts.append(s.text() or "")
        script_text = " ".join(script_parts)

        has_gtm = bool(_GTM_RE.search(script_text))
        has_ga = bool(_GA_RE.search(script_text))
        has_fb = bool(_FB_PIXEL.search(script_text))
        has_hotjar = bool(_HOTJAR.search(script_text))
        has_intercom = bool(_INTERCOM.search(script_text))
        has_hubspot = bool(_HUBSPOT.search(script_text))
        has_segment = bool(_SEGMENT.search(script_text))

        # Consent / GDPR -- search full HTML
        full_html = tree.html or ""
        has_consent = bool(_CONSENT_RE.search(full_html))

        # Dublin Core meta tags
        has_dublin_core = False
        for m in tree.css("meta[name]"):
            name = m.attributes.get("name") or ""
            if re.match(r"^dc\.", name, re.I):
                has_dublin_core = True
                break

        # Service worker detection
        has_service_worker = bool(
            re.search(r"serviceWorker\.register|navigator\.serviceWorker", script_text)
        )

        return {
            # Mobile
            "has_viewport": viewport_tag is not None,
            "viewport_content": viewport_content,

            # AMP
            "is_amp": is_amp,
            "has_amphtml_link": amphtml_link,

            # Security / protocol
            "is_https": is_https,
            "charset": charset,

            # Discovery
            "has_favicon": has_favicon,
            "has_apple_touch_icon": has_apple_touch_icon,
            "has_web_manifest": has_web_manifest,
            "has_rss_feed": has_rss,
            "has_atom_feed": has_atom,

            # Resource hints
            "dns_prefetch_count": dns_prefetch,
            "preload_count": preload,
            "prefetch_count": prefetch,
            "preconnect_count": preconnect,

            # Scripts
            "total_scripts": total_scripts,
            "async_scripts": async_scripts,
            "defer_scripts": defer_scripts,
            "inline_scripts": inline_scripts,
            "external_scripts": external_scripts,
            "blocking_scripts": blocking_scripts,
            "module_scripts": module_scripts,

            # Styles
            "total_style_tags": total_styles,
            "external_stylesheets": external_css,
            "inline_style_attrs": inline_style_attrs,

            "noscript_count": noscript_count,

            # Trackers
            "has_gtm": has_gtm,
            "has_google_analytics": has_ga,
            "has_facebook_pixel": has_fb,
            "has_hotjar": has_hotjar,
            "has_intercom": has_intercom,
            "has_hubspot": has_hubspot,
            "has_segment": has_segment,

            # Privacy
            "has_cookie_consent": has_consent,

            # Misc
            "has_dublin_core": has_dublin_core,
            "has_service_worker": has_service_worker,
        }
    except Exception:
        return {
            "has_viewport": False, "viewport_content": None,
            "is_amp": False, "has_amphtml_link": False,
            "is_https": None, "charset": None,
            "has_favicon": False, "has_apple_touch_icon": False,
            "has_web_manifest": False, "has_rss_feed": False, "has_atom_feed": False,
            "dns_prefetch_count": 0, "preload_count": 0,
            "prefetch_count": 0, "preconnect_count": 0,
            "total_scripts": 0, "async_scripts": 0, "defer_scripts": 0,
            "inline_scripts": 0, "external_scripts": 0,
            "blocking_scripts": 0, "module_scripts": 0,
            "total_style_tags": 0, "external_stylesheets": 0,
            "inline_style_attrs": 0, "noscript_count": 0,
            "has_gtm": False, "has_google_analytics": False,
            "has_facebook_pixel": False, "has_hotjar": False,
            "has_intercom": False, "has_hubspot": False,
            "has_segment": False, "has_cookie_consent": False,
            "has_dublin_core": False, "has_service_worker": False,
        }
