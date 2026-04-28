"""Pydantic v2 models for the SERP pipeline.

All SERP data structures are typed Pydantic models with no raw dicts.
Difficulty score labels map 0-30 Easy, 31-60 Medium, 61-80 Hard, 81-100 Very Hard.
Config loading is cached at module level with graceful degradation on malformed JSON.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import logging
import os
import unicodedata
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Origin constants
# ---------------------------------------------------------------------------

ORIGIN_ORGANIC = "organic"
ORIGIN_ADS_TOP = "ads_top"
ORIGIN_ADS_BOTTOM = "ads_bottom"
ORIGIN_FEATURED_SNIPPET = "featured_snippet"
ORIGIN_PAA = "paa"
ORIGIN_SHOPPING = "shopping"
ORIGIN_TOP_STORIES = "top_stories"
ORIGIN_KNOWLEDGE_PANEL = "knowledge_panel"
ORIGIN_VIDEO = "video"
ORIGIN_IMAGE = "image"
ORIGIN_TARGET = "target"


# ---------------------------------------------------------------------------
# Config loading (cached, with graceful degradation)
# ---------------------------------------------------------------------------

_PACKAGE_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_operators_cache: list[dict[str, Any]] | None = None
_authority_domains_cache: dict[str, Any] | None = None


def load_operators(path: str | None = None) -> list[dict[str, Any]]:
    """Load operator brand domains from JSON. Results are cached after first load."""
    global _operators_cache
    if _operators_cache is not None and path is None:
        return _operators_cache

    file_path = path or os.environ.get(
        "SCRAPER_OPERATORS_PATH",
        str(_PACKAGE_DATA_DIR / "operators.json"),
    )
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            if path is None:
                _operators_cache = data
            return data
    except Exception as exc:
        logger.warning("Could not load operators from %s: %s", file_path, exc)
    return []


def load_authority_domains(path: str | None = None) -> dict[str, Any]:
    """Load high authority domain list from JSON. Results are cached after first load."""
    global _authority_domains_cache
    if _authority_domains_cache is not None and path is None:
        return _authority_domains_cache

    file_path = path or os.environ.get(
        "SCRAPER_AUTHORITY_DOMAINS_PATH",
        str(_PACKAGE_DATA_DIR / "high_authority_domains.json"),
    )
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            if path is None:
                _authority_domains_cache = data
            return data
    except Exception as exc:
        logger.warning("Could not load authority domains from %s: %s", file_path, exc)
    return {"domains": [], "tld_patterns": []}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

_DIFFICULTY_LABELS: list[tuple[float, str]] = [
    (30.0, "Easy"),
    (60.0, "Medium"),
    (80.0, "Hard"),
    (100.0, "Very Hard"),
]

_DIFFICULTY_COLORS: list[tuple[float, str]] = [
    (30.0, "#00A878"),
    (60.0, "#F5A623"),
    (80.0, "#FF9800"),
    (100.0, "#E74C3C"),
]


def get_difficulty_label(score: float) -> str:
    """Map a 0-100 score to a label: Easy (0-30), Medium (31-60), Hard (61-80), Very Hard (81-100)."""
    for threshold, label in _DIFFICULTY_LABELS:
        if score <= threshold:
            return label
    return "Very Hard"


def get_difficulty_color(score: float) -> str:
    """Map a 0-100 score to a hex color matching the existing score_calculator.py palette."""
    for threshold, color in _DIFFICULTY_COLORS:
        if score <= threshold:
            return color
    return "#E74C3C"


def normalize_keyword(keyword: str) -> str:
    """NFC normalize, collapse whitespace, lowercase."""
    normalized = unicodedata.normalize("NFC", keyword)
    collapsed = " ".join(normalized.split())
    return collapsed.lower()


def normalize_language(language: str) -> str:
    """Normalize BCP-47 language tag: 'pt-br' -> 'pt-BR', 'en' -> 'en'."""
    if "-" in language:
        parts = language.split("-", 1)
        return f"{parts[0].lower()}-{parts[1].upper()}"
    return language.lower()


def normalize_market(market: str) -> str:
    """Uppercase market code: 'us' -> 'US'."""
    return market.upper()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SerpFeatures(BaseModel):
    """19 boolean SERP feature flags."""

    model_config = ConfigDict(extra="forbid")

    has_organic_results: bool = False
    has_ads_top: bool = False
    has_ads_bottom: bool = False
    has_featured_snippet: bool = False
    has_ai_overview: bool = False
    has_knowledge_panel: bool = False
    has_local_pack: bool = False
    has_top_stories: bool = False
    has_images_results: bool = False
    has_videos_results: bool = False
    has_shopping_results: bool = False
    has_people_also_ask: bool = False
    has_related_searches: bool = False
    has_sitelinks: bool = False
    has_twitter_cards: bool = False
    has_discussions_forums: bool = False
    has_instant_answer: bool = False
    has_calculator: bool = False
    has_faq_rich_results: bool = False


class OrganicResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int | None = None
    url: str
    title: str = ""
    description: str = ""
    raw_json: dict[str, Any] | None = None


class PeopleAlsoAskItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int
    question: str
    snippet: str = ""
    title: str = ""
    link: str = ""
    displayed_link: str = ""
    date: str = ""
    raw_json: dict[str, Any] | None = None


class AdResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int | None = None
    url: str
    title: str = ""
    description: str = ""
    block_position: str = "top"
    raw_json: dict[str, Any] | None = None


class FeaturedSnippet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    title: str = ""
    snippet: str = ""
    raw_json: dict[str, Any] | None = None


class ShoppingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int | None = None
    url: str
    title: str = ""
    raw_json: dict[str, Any] | None = None


class TopStoryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int | None = None
    url: str
    title: str = ""
    raw_json: dict[str, Any] | None = None


class VideoResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int | None = None
    url: str
    title: str = ""
    raw_json: dict[str, Any] | None = None


class ImageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int | None = None
    url: str
    title: str = ""
    raw_json: dict[str, Any] | None = None


class KnowledgePanel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    title: str = ""
    raw_json: dict[str, Any] | None = None


class SerpUrl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    origin: str
    position: int | None = None
    title: str = ""


class SerpSnapshot(BaseModel):
    """Holds compressed HTML and screenshot data for a SERP page."""

    model_config = ConfigDict(extra="forbid")

    html_compressed: bytes | None = None
    html_sha256: str = ""
    html_bytes_len: int | None = None
    html_encoding: str = ""
    screenshot_png: bytes | None = None
    screenshot_width: int | None = None
    screenshot_height: int | None = None

    @field_serializer("html_compressed", "screenshot_png", when_used="json")
    def serialize_bytes(self, v: bytes | None) -> str | None:
        """Base64-encode bytes for JSON output (D-12)."""
        if v is None:
            return None
        return base64.b64encode(v).decode("ascii")

    def compress_html(self, html: str) -> None:
        """Gzip-compress HTML, store SHA-256 hash and byte length."""
        raw = html.encode("utf-8", "replace")
        gz = gzip.compress(raw, compresslevel=6)
        self.html_compressed = gz
        self.html_encoding = "gzip"
        self.html_bytes_len = len(gz)
        self.html_sha256 = hashlib.sha256(raw).hexdigest()

    def decompress_html(self) -> str:
        """Decompress gzip bytes back to UTF-8 string."""
        if not self.html_compressed:
            return ""
        return gzip.decompress(self.html_compressed).decode("utf-8", "replace")


class DifficultyScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_score: float = Field(ge=0, le=100)
    label: str
    component_breakdown: dict[str, float]


class CostMetadata(BaseModel):
    """Per-SERP-call cost and usage metadata."""

    model_config = ConfigDict(extra="forbid")

    serp_api_calls: int = 1
    serp_api_credits_used: float | None = None
    serp_api_total_time_taken: float | None = None
    fetch_duration_ms: float | None = None


class SerpResponse(BaseModel):
    """Top-level model returned by the SERP pipeline."""

    model_config = ConfigDict(extra="forbid")

    keyword: str
    keyword_norm: str
    market: str
    language: str
    features: SerpFeatures
    organic_results: list[OrganicResult]
    paa_items: list[PeopleAlsoAskItem]
    ads_top: list[AdResult]
    ads_bottom: list[AdResult]
    featured_snippet: FeaturedSnippet | None
    shopping_results: list[ShoppingResult]
    top_stories: list[TopStoryResult]
    knowledge_panel: KnowledgePanel | None
    videos: list[VideoResult]
    images: list[ImageResult]
    serp_urls: list[SerpUrl]
    snapshot: SerpSnapshot
    difficulty_score: DifficultyScore
    search_id: str = ""
    search_status: str = ""
    cost: CostMetadata | None = None
