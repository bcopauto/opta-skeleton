"""Extract images with alt text statistics (EXTR-14 + EXTR-15)."""
from __future__ import annotations

from urllib.parse import urlparse

from selectolax.parser import HTMLParser

_IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif", ".bmp", ".ico"}


def _get_ext(src: str) -> str:
    """Extract file extension from URL path."""
    try:
        path = urlparse(src).path.lower()
        for ext in _IMG_EXTENSIONS:
            if path.endswith(ext):
                return ext
    except Exception:
        pass
    return ""


def extract(tree: HTMLParser, url: str) -> dict:
    """Extract image data and compute alt text statistics. Never raises."""
    try:
        # Check for <main> to determine "in main content"
        main_node = tree.css_first("main")

        imgs = tree.css("img")
        image_list: list[dict[str, str | bool]] = []

        total = len(imgs)
        missing_alt = 0
        empty_alt = 0
        descriptive_alt = 0
        lazy_loaded = 0
        has_srcset = 0
        ext_counts: dict[str, int] = {}

        for img in imgs:
            src = (img.attributes.get("src") or img.attributes.get("data-src") or "").strip()
            alt = img.attributes.get("alt")
            loading = (img.attributes.get("loading") or "").lower()

            # Determine if in main content
            in_main = False
            if main_node:
                # Walk up parent chain to check if inside <main>
                parent = img.parent
                while parent:
                    if parent.tag == "main":
                        in_main = True
                        break
                    parent = parent.parent
            else:
                in_main = True  # No main tag, assume all are in content

            image_list.append({
                "src": src,
                "alt": alt or "",
                "in_main_content": in_main,
            })

            # Alt text analysis
            if alt is None:
                missing_alt += 1
            elif alt.strip() == "":
                empty_alt += 1
            else:
                descriptive_alt += 1

            # Lazy loading
            if loading == "lazy":
                lazy_loaded += 1

            # Srcset
            if img.attributes.get("srcset"):
                has_srcset += 1

            # Extension breakdown (skip data URIs)
            if not src.startswith("data:"):
                ext = _get_ext(src)
                if ext:
                    ext_counts[ext] = ext_counts.get(ext, 0) + 1

        # Inline SVG
        inline_svg = len(tree.css("svg"))

        # Figure/figcaption/picture
        figure_count = len(tree.css("figure"))
        figcaption_count = len(tree.css("figcaption"))
        picture_count = len(tree.css("picture"))

        # Images in main content stats
        in_main_count = sum(1 for img in image_list if img["in_main_content"])

        return {
            # EXTR-14: Image list
            "image_list": image_list,

            # EXTR-15: Statistics
            "total_images": total,
            "missing_alt": missing_alt,
            "empty_alt": empty_alt,
            "descriptive_alt": descriptive_alt,
            "alt_coverage_pct": round(descriptive_alt / total * 100, 1) if total else 100.0,
            "in_main_content": in_main_count,

            # Additional stats from existing extractor
            "lazy_loaded": lazy_loaded,
            "has_srcset": has_srcset,
            "inline_svg": inline_svg,
            "figure_count": figure_count,
            "figcaption_count": figcaption_count,
            "picture_count": picture_count,

            # Extension breakdown
            "ext_jpg": ext_counts.get(".jpg", 0) + ext_counts.get(".jpeg", 0),
            "ext_png": ext_counts.get(".png", 0),
            "ext_webp": ext_counts.get(".webp", 0),
            "ext_gif": ext_counts.get(".gif", 0),
            "ext_svg": ext_counts.get(".svg", 0),
            "ext_avif": ext_counts.get(".avif", 0),
        }
    except Exception:
        return _empty()


def _empty() -> dict:
    return {
        "image_list": [], "total_images": 0,
        "missing_alt": 0, "empty_alt": 0, "descriptive_alt": 0,
        "alt_coverage_pct": 100.0, "in_main_content": 0,
        "lazy_loaded": 0, "has_srcset": 0,
        "inline_svg": 0, "figure_count": 0, "figcaption_count": 0,
        "picture_count": 0,
        "ext_jpg": 0, "ext_png": 0, "ext_webp": 0,
        "ext_gif": 0, "ext_svg": 0, "ext_avif": 0,
    }
