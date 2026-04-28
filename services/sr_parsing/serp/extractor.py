"""Pure extraction functions for SERP data from SerpAPI JSON responses.

All functions are stateless: no file I/O, no network calls, no side effects.
They handle SerpAPI's inconsistent key naming defensively (e.g., "ads" vs
"top_ads", "answer_box" vs "featured_snippet") and never raise on malformed
input -- returning empty lists, None, or zero-values instead.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from scraper_service.serp.models import (
    AdResult,
    FeaturedSnippet,
    ImageResult,
    KnowledgePanel,
    OrganicResult,
    PeopleAlsoAskItem,
    SerpFeatures,
    SerpUrl,
    ShoppingResult,
    TopStoryResult,
    VideoResult,
    ORIGIN_ADS_BOTTOM,
    ORIGIN_ADS_TOP,
    ORIGIN_FEATURED_SNIPPET,
    ORIGIN_IMAGE,
    ORIGIN_KNOWLEDGE_PANEL,
    ORIGIN_ORGANIC,
    ORIGIN_PAA,
    ORIGIN_SHOPPING,
    ORIGIN_TARGET,
    ORIGIN_TOP_STORIES,
    ORIGIN_VIDEO,
)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _is_valid_url(url: str | None) -> bool:
    """Check that a URL has http/https scheme and non-empty netloc."""
    if not url or not isinstance(url, str):
        return False
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def _get_link(item: dict[str, Any], *keys: str) -> str:
    """Try multiple keys to extract a URL string from an item dict."""
    for key in keys:
        val = item.get(key)
        if isinstance(val, str) and val:
            return val
    return ""


# ---------------------------------------------------------------------------
# extract_features  (19 boolean flags)
# ---------------------------------------------------------------------------


def _is_instant_answer(data: dict[str, Any]) -> bool:
    """True if answer_box is a direct answer (no attribution link)."""
    ab = data.get("answer_box")
    if not ab or not isinstance(ab, dict):
        return False
    # Calculator and other typed boxes are not instant answers
    if ab.get("type") in ("calculator", "currency_converter", "translation"):
        return False
    # Instant answer = answer_box without a source link
    return not bool(_get_link(ab, "link", "url", "displayed_link"))


def _is_calculator(data: dict[str, Any]) -> bool:
    """True if answer_box is a calculator widget."""
    ab = data.get("answer_box")
    return bool(ab and isinstance(ab, dict) and ab.get("type") == "calculator")


def _has_faq_rich_results(data: dict[str, Any]) -> bool:
    """True if any organic result has FAQ rich snippet extensions."""
    for r in data.get("organic_results") or []:
        if not isinstance(r, dict):
            continue
        rich = r.get("rich_snippet") or {}
        for section in ("bottom", "top"):
            block = rich.get(section) or {}
            if "questions" in block:
                return True
            detected = block.get("detected_extensions") or {}
            if isinstance(detected, dict) and "faq" in detected:
                return True
    return False


def extract_features(data: dict[str, Any]) -> SerpFeatures:
    """Extract 19 boolean SERP feature flags from a SerpAPI JSON response.

    Handles inconsistent SerpAPI key naming:
      - ads vs top_ads
      - answer_box vs featured_snippet
      - ai_overview vs generative_knowledge_graph
      - video_results vs inline_videos
      - related_questions vs people_also_ask
    """
    return SerpFeatures(
        has_organic_results=bool(data.get("organic_results")),
        has_ads_top=bool(data.get("ads") or data.get("top_ads")),
        has_ads_bottom=bool(data.get("bottom_ads")),
        has_featured_snippet=bool(data.get("answer_box") or data.get("featured_snippet")),
        has_ai_overview=bool(data.get("ai_overview") or data.get("generative_knowledge_graph")),
        has_knowledge_panel=bool(data.get("knowledge_graph")),
        has_local_pack=bool(data.get("local_results") or data.get("local_map")),
        has_top_stories=bool(data.get("top_stories")),
        has_images_results=bool(data.get("images_results")),
        has_videos_results=bool(data.get("video_results") or data.get("inline_videos")),
        has_shopping_results=bool(data.get("shopping_results")),
        has_people_also_ask=bool(data.get("related_questions") or data.get("people_also_ask")),
        has_related_searches=bool(data.get("related_searches")),
        has_sitelinks=any(
            "sitelinks" in r for r in (data.get("organic_results") or [])
        ),
        has_twitter_cards=bool(data.get("twitter_results")),
        has_discussions_forums=bool(data.get("discussions_and_forums")),
        has_instant_answer=_is_instant_answer(data),
        has_calculator=_is_calculator(data),
        has_faq_rich_results=_has_faq_rich_results(data),
    )


# ---------------------------------------------------------------------------
# extract_organic_results
# ---------------------------------------------------------------------------


def extract_organic_results(data: dict[str, Any]) -> list[OrganicResult]:
    """Extract organic results from SerpAPI response.

    Tries "link" then "url" key for the URL. Skips items with no URL.
    """
    results: list[OrganicResult] = []
    for item in data.get("organic_results") or []:
        url = _get_link(item, "link", "url")
        if not url:
            continue
        results.append(
            OrganicResult(
                position=item.get("position"),
                url=url,
                title=item.get("title", ""),
                description=item.get("snippet", ""),
                raw_json=item,
            )
        )
    return results


# ---------------------------------------------------------------------------
# extract_paa_items
# ---------------------------------------------------------------------------


def extract_paa_items(data: dict[str, Any]) -> list[PeopleAlsoAskItem]:
    """Extract People Also Ask items from 'related_questions' or 'people_also_ask'."""
    raw = data.get("related_questions") or data.get("people_also_ask") or []
    items: list[PeopleAlsoAskItem] = []
    for i, item in enumerate(raw, start=1):
        question = (item.get("question") or "").strip()
        if not question:
            continue
        items.append(
            PeopleAlsoAskItem(
                position=i,
                question=question,
                snippet=item.get("snippet") or "",
                title=item.get("title") or "",
                link=item.get("link") or "",
                displayed_link=item.get("displayed_link") or "",
                date=item.get("date") or "",
                raw_json=item,
            )
        )
    return items


# ---------------------------------------------------------------------------
# extract_ads
# ---------------------------------------------------------------------------


def extract_ads(data: dict[str, Any]) -> tuple[list[AdResult], list[AdResult]]:
    """Extract ads, returning (top_ads, bottom_ads).

    Handles "ads"/"top_ads" key with block_position field, and "bottom_ads" key.
    """
    top: list[AdResult] = []
    bottom: list[AdResult] = []

    # From "ads" or "top_ads" -- split by block_position
    for item in data.get("ads") or data.get("top_ads") or []:
        url = _get_link(item, "link", "url")
        if not url:
            continue
        block = (item.get("block_position") or "top").lower()
        ad = AdResult(
            position=item.get("position"),
            url=url,
            title=item.get("title", ""),
            description=item.get("snippet", ""),
            block_position=block,
            raw_json=item,
        )
        if block == "bottom":
            bottom.append(ad)
        else:
            top.append(ad)

    # From "bottom_ads" key
    for item in data.get("bottom_ads") or []:
        url = _get_link(item, "link", "url")
        if not url:
            continue
        bottom.append(
            AdResult(
                position=item.get("position"),
                url=url,
                title=item.get("title", ""),
                description=item.get("snippet", ""),
                block_position="bottom",
                raw_json=item,
            )
        )

    return top, bottom


# ---------------------------------------------------------------------------
# extract_featured_snippet
# ---------------------------------------------------------------------------


def extract_featured_snippet(data: dict[str, Any]) -> FeaturedSnippet | None:
    """Extract featured snippet from 'answer_box' or 'featured_snippet' key."""
    for key in ("answer_box", "featured_snippet"):
        raw = data.get(key)
        if raw:
            url = _get_link(raw, "link", "url")
            return FeaturedSnippet(
                url=url,
                title=raw.get("title", ""),
                snippet=raw.get("snippet", ""),
                raw_json=raw,
            )
    return None


# ---------------------------------------------------------------------------
# extract_shopping
# ---------------------------------------------------------------------------


def extract_shopping(data: dict[str, Any]) -> list[ShoppingResult]:
    """Extract shopping results. Tries 'link', 'url', 'product_link' for URL."""
    results: list[ShoppingResult] = []
    for i, item in enumerate(data.get("shopping_results") or [], start=1):
        url = _get_link(item, "link", "url", "product_link")
        if not url:
            continue
        results.append(
            ShoppingResult(
                position=item.get("position", i),
                url=url,
                title=item.get("title", ""),
                raw_json=item,
            )
        )
    return results


# ---------------------------------------------------------------------------
# extract_top_stories
# ---------------------------------------------------------------------------


def extract_top_stories(data: dict[str, Any]) -> list[TopStoryResult]:
    """Extract top stories from 'top_stories' key."""
    results: list[TopStoryResult] = []
    for i, item in enumerate(data.get("top_stories") or [], start=1):
        url = _get_link(item, "link", "url")
        if not url:
            continue
        results.append(
            TopStoryResult(
                position=item.get("position", i),
                url=url,
                title=item.get("title", ""),
                raw_json=item,
            )
        )
    return results


# ---------------------------------------------------------------------------
# extract_knowledge_panel
# ---------------------------------------------------------------------------


def extract_knowledge_panel(data: dict[str, Any]) -> KnowledgePanel | None:
    """Extract knowledge panel from 'knowledge_graph' key."""
    kg = data.get("knowledge_graph")
    if not kg:
        return None
    src = kg.get("source") or {}
    url = src.get("link") or kg.get("website") or kg.get("url") or ""
    return KnowledgePanel(
        url=url,
        title=kg.get("title", ""),
        raw_json=kg,
    )


# ---------------------------------------------------------------------------
# extract_videos
# ---------------------------------------------------------------------------


def extract_videos(data: dict[str, Any]) -> list[VideoResult]:
    """Extract videos from 'inline_videos' or 'video_results' key."""
    raw = data.get("inline_videos") or data.get("video_results") or []
    results: list[VideoResult] = []
    for i, item in enumerate(raw, start=1):
        url = _get_link(item, "link", "url")
        if not url:
            continue
        results.append(
            VideoResult(
                position=item.get("position", i),
                url=url,
                title=item.get("title", ""),
                raw_json=item,
            )
        )
    return results


# ---------------------------------------------------------------------------
# extract_images
# ---------------------------------------------------------------------------


def extract_images(data: dict[str, Any]) -> list[ImageResult]:
    """Extract images from 'images_results' key. Tries 'link' then 'original'."""
    results: list[ImageResult] = []
    for i, item in enumerate(data.get("images_results") or [], start=1):
        url = _get_link(item, "link", "original")
        if not url:
            continue
        results.append(
            ImageResult(
                position=item.get("position", i),
                url=url,
                title=item.get("title", ""),
                raw_json=item,
            )
        )
    return results


# ---------------------------------------------------------------------------
# extract_serp_urls
# ---------------------------------------------------------------------------


def extract_serp_urls(
    data: dict[str, Any],
    target_url: str = "",
) -> list[SerpUrl]:
    """Extract deduplicated URLs from all SERP origin types.

    Deduplication is by (url, origin) tuple -- the same URL can appear
    under multiple origins, but the same url+origin pair only appears once.
    Invalid URLs (non-http/https, empty netloc) are skipped.

    If target_url is provided, it is prepended as origin='target'.
    """
    items: list[SerpUrl] = []
    seen: set[tuple[str, str]] = set()

    def add(url: str, origin: str, position: int | None, title: str = "") -> None:
        if not _is_valid_url(url):
            return
        key = (url, origin)
        if key in seen:
            return
        seen.add(key)
        items.append(SerpUrl(url=url, origin=origin, position=position, title=title))

    # Organic
    for r in data.get("organic_results") or []:
        url = _get_link(r, "link", "url")
        add(url, ORIGIN_ORGANIC, r.get("position"), r.get("title", ""))

    # Ads (top + bottom)
    for r in data.get("ads") or data.get("top_ads") or []:
        url = _get_link(r, "link", "url")
        block = (r.get("block_position") or "top").lower()
        origin = ORIGIN_ADS_BOTTOM if block == "bottom" else ORIGIN_ADS_TOP
        add(url, origin, r.get("position"), r.get("title", ""))

    for r in data.get("bottom_ads") or []:
        url = _get_link(r, "link", "url")
        add(url, ORIGIN_ADS_BOTTOM, r.get("position"), r.get("title", ""))

    # Featured snippet / answer box
    for key in ("answer_box", "featured_snippet"):
        fs = data.get(key)
        if fs:
            url = _get_link(fs, "link", "url")
            add(url, ORIGIN_FEATURED_SNIPPET, None, fs.get("title", ""))

    # People Also Ask
    for i, r in enumerate(
        data.get("related_questions") or data.get("people_also_ask") or [], start=1
    ):
        url = _get_link(r, "link", "url")
        title = r.get("title") or r.get("question", "")
        add(url, ORIGIN_PAA, i, title)

    # Shopping
    for i, r in enumerate(data.get("shopping_results") or [], start=1):
        url = _get_link(r, "link", "url", "product_link")
        add(url, ORIGIN_SHOPPING, i, r.get("title", ""))

    # Top stories
    for i, r in enumerate(data.get("top_stories") or [], start=1):
        url = _get_link(r, "link", "url")
        add(url, ORIGIN_TOP_STORIES, i, r.get("title", ""))

    # Knowledge panel
    kg = data.get("knowledge_graph")
    if kg:
        src = kg.get("source") or {}
        url = src.get("link") or kg.get("website") or kg.get("url") or ""
        add(url, ORIGIN_KNOWLEDGE_PANEL, None, kg.get("title", ""))

    # Videos
    for i, r in enumerate(
        data.get("inline_videos") or data.get("video_results") or [], start=1
    ):
        url = _get_link(r, "link", "url")
        add(url, ORIGIN_VIDEO, i, r.get("title", ""))

    # Images
    for i, r in enumerate(data.get("images_results") or [], start=1):
        url = _get_link(r, "link", "original")
        add(url, ORIGIN_IMAGE, i, r.get("title", ""))

    # Target URL injection
    if target_url:
        return inject_target_url(items, target_url)

    return items


# ---------------------------------------------------------------------------
# inject_target_url
# ---------------------------------------------------------------------------


def inject_target_url(urls: list[SerpUrl], target_url: str) -> list[SerpUrl]:
    """Prepend a SerpUrl with origin='target' to the URL list."""
    target = SerpUrl(url=target_url, origin=ORIGIN_TARGET, position=None, title="")
    return [target, *urls]
