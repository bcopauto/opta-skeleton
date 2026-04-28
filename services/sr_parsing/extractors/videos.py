"""Extract videos: <video> tags, YouTube/Vimeo iframes, og:video meta (EXTR-08)."""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser

_YOUTUBE_RE = re.compile(r"youtube\.com/embed/|youtu\.be/", re.I)
_VIMEO_RE = re.compile(r"vimeo\.com/", re.I)


def extract(tree: HTMLParser, url: str) -> dict:
    """Extract video sources as list of {src, type, title}. Never raises."""
    try:
        videos: list[dict[str, str]] = []

        # <video> tags
        for video in tree.css("video"):
            src = video.attributes.get("src") or ""
            if src:
                videos.append({
                    "src": src,
                    "type": "video_tag",
                    "title": (video.attributes.get("title") or "").strip(),
                })

        # YouTube/Vimeo iframes
        for iframe in tree.css("iframe"):
            src = (iframe.attributes.get("src") or "").strip()
            if not src:
                continue
            if _YOUTUBE_RE.search(src):
                videos.append({
                    "src": src,
                    "type": "youtube",
                    "title": (iframe.attributes.get("title") or "").strip(),
                })
            elif _VIMEO_RE.search(src):
                videos.append({
                    "src": src,
                    "type": "vimeo",
                    "title": (iframe.attributes.get("title") or "").strip(),
                })

        # og:video meta
        for meta in tree.css('meta[property^="og:video"]'):
            content = (meta.attributes.get("content") or "").strip()
            if content:
                videos.append({
                    "src": content,
                    "type": "og_video",
                    "title": "",
                })

        return {
            "video_count": len(videos),
            "videos": videos,
        }
    except Exception:
        return {"video_count": 0, "videos": []}
