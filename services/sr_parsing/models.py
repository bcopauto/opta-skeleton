"""Pydantic v2 models for the scraper service."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class RenderMethod(str, Enum):
    HTTPX = "httpx"
    XHR = "xhr"
    PLAYWRIGHT = "playwright"
    FAILED = "failed"


class ErrorType(str, Enum):
    TIMEOUT = "timeout"
    NETWORK = "network"
    HTTP_4XX = "http_4xx"
    HTTP_5XX = "http_5xx"
    ROBOTS_DENIED = "robots_denied"
    CIRCUIT_BREAKER = "circuit_breaker"
    INVALID_URL = "invalid_url"
    PLAYWRIGHT_CRASH = "playwright_crash"


class PageData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    final_url: str
    status_code: int | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    render_method: RenderMethod = RenderMethod.HTTPX
    error: str | None = None
    error_type: ErrorType | None = None
    html: str | None = None
    xhr_responses: list[dict[str, Any]] | None = None
    response_headers: dict[str, str] | None = None
    fetch_duration_ms: float | None = None


class SinkType(str, Enum):
    DATABASE = "database"
    CSV = "csv"
    JSON = "json"
    DEBUG_DUMP = "debug_dump"


class SinkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: SinkType
    config: dict[str, str] = {}


class ScrapeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    urls: list[str] = Field(..., min_length=1)
    sinks: list[SinkConfig] = []
    respect_robots: bool = False
    render_method: RenderMethod | None = None


# ---------------------------------------------------------------------------
# Extraction sub-models (one per extractor module)
# ---------------------------------------------------------------------------


class TitleData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    title_length: int = 0


class MetaDescData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meta_description: str | None = None
    meta_description_length: int = 0


class HeadingsData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    h1_count: int = 0
    h2_count: int = 0
    h3_count: int = 0
    h4_count: int = 0
    h5_count: int = 0
    h6_count: int = 0
    total_headings: int = 0
    h1_texts: list[str] = []
    h2_texts: list[str] = []
    first_heading_tag: str | None = None
    duplicate_h1: bool = False
    empty_headings: int = 0
    heading_word_count: int = 0
    hierarchy_issues: list[str] = []


class BodyTextData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    word_count: int = 0
    char_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0
    text_html_ratio: float = 0.0
    reading_time_s: int = 0
    lang: str | None = None
    text: str = ""


class TablesData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_count: int = 0
    tables: list[list[dict[str, str]]] = []


class ListsData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unordered_lists: list[list[str]] = []
    ordered_lists: list[list[str]] = []
    ul_count: int = 0
    ol_count: int = 0
    total_items: int = 0


class FaqData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    has_faq: bool = False
    faq_schema_count: int = 0
    faq_schema_questions: list[str] = []
    details_count: int = 0
    details_questions: list[str] = []
    class_based_questions: list[str] = []
    question_headings: list[str] = []
    total_faq_items: int = 0


class VideoItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    src: str = ""
    type: str = ""
    title: str = ""


class VideosData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    video_count: int = 0
    videos: list[VideoItem] = []


class TocLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = ""
    href: str = ""
    target_id: str = ""


class TocData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    has_toc: bool = False
    toc_link_count: int = 0
    toc_links: list[TocLink] = []


class ComparisonTableData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    headers: list[str] = []
    row_count: int = 0
    rows: list[dict[str, str]] = []


class ComparisonTablesData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    has_comparison_table: bool = False
    comparison_table_count: int = 0
    comparison_tables: list[ComparisonTableData] = []


class CalloutItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = ""
    classes: str = ""
    role: str = ""
    tag: str = ""


class CalloutBoxesData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    has_callouts: bool = False
    callout_count: int = 0
    callouts: list[CalloutItem] = []


class StepGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    heading: str = ""
    steps: list[str] = []


class StepByStepData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    has_steps: bool = False
    schema_step_count: int = 0
    schema_steps: list[str] = []
    html_step_groups: int = 0
    html_steps: list[StepGroup] = []
    total_step_count: int = 0


class JsonldData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jsonld_present: bool = False
    jsonld_count: int = 0
    jsonld_types: list[str] = []
    jsonld_blocks: list[dict] = []
    microdata_present: bool = False
    microdata_types: list[str] = []
    rdfa_present: bool = False
    rdfa_types: list[str] = []
    all_schema_types: list[str] = []
    has_breadcrumb: bool = False
    breadcrumb_items: int | None = None
    has_faq: bool = False
    faq_count: int | None = None
    has_howto: bool = False
    howto_steps: int | None = None
    has_article: bool = False
    has_product: bool = False
    has_review: bool = False
    has_aggregate_rating: bool = False
    has_organization: bool = False
    has_local_business: bool = False
    has_event: bool = False
    has_recipe: bool = False
    recipe_info: dict | None = None
    has_video_object: bool = False
    has_person: bool = False
    has_website: bool = False
    has_sitelinks_searchbox: bool = False
    has_speakable: bool = False
    has_course: bool = False
    has_job_posting: bool = False
    has_software_app: bool = False
    has_medical: bool = False


class ImageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    src: str = ""
    alt: str = ""
    in_main_content: bool = False


class ImagesData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_list: list[ImageItem] = []
    total_images: int = 0
    missing_alt: int = 0
    empty_alt: int = 0
    descriptive_alt: int = 0
    alt_coverage_pct: float = 100.0
    in_main_content: int = 0
    lazy_loaded: int = 0
    has_srcset: int = 0
    inline_svg: int = 0
    figure_count: int = 0
    figcaption_count: int = 0
    picture_count: int = 0
    ext_jpg: int = 0
    ext_png: int = 0
    ext_webp: int = 0
    ext_gif: int = 0
    ext_svg: int = 0
    ext_avif: int = 0


class LinksData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_links: int = 0
    internal_links: int = 0
    external_links: int = 0
    nofollow_links: int = 0
    sponsored_links: int = 0
    ugc_links: int = 0
    noreferrer_links: int = 0
    noopener_links: int = 0
    blank_target_links: int = 0
    http_external_links: int = 0
    empty_anchor_links: int = 0
    image_only_anchor_links: int = 0
    generic_anchor_links: int = 0
    unique_external_domains: int = 0
    top_external_domains: list[str] = []
    top_anchor_texts: list[dict] = []


class TechnicalData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    has_viewport: bool = False
    viewport_content: str | None = None
    is_amp: bool = False
    has_amphtml_link: bool = False
    is_https: bool | None = None
    charset: str | None = None
    has_favicon: bool = False
    has_apple_touch_icon: bool = False
    has_web_manifest: bool = False
    has_rss_feed: bool = False
    has_atom_feed: bool = False
    dns_prefetch_count: int = 0
    preload_count: int = 0
    prefetch_count: int = 0
    preconnect_count: int = 0
    total_scripts: int = 0
    async_scripts: int = 0
    defer_scripts: int = 0
    inline_scripts: int = 0
    external_scripts: int = 0
    blocking_scripts: int = 0
    module_scripts: int = 0
    total_style_tags: int = 0
    external_stylesheets: int = 0
    inline_style_attrs: int = 0
    noscript_count: int = 0
    has_gtm: bool = False
    has_google_analytics: bool = False
    has_facebook_pixel: bool = False
    has_hotjar: bool = False
    has_intercom: bool = False
    has_hubspot: bool = False
    has_segment: bool = False
    has_cookie_consent: bool = False
    has_dublin_core: bool = False
    has_service_worker: bool = False


class PaginationData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    has_rel_next: bool = False
    rel_next_url: str | None = None
    has_rel_prev: bool = False
    rel_prev_url: str | None = None
    page_number_in_url: bool = False
    has_pagination_nav: bool = False
    has_infinite_scroll: bool = False


class MetaData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    title_length: int = 0
    title_pixel_width_est: float = 0.0
    meta_description: str | None = None
    meta_description_length: int = 0
    meta_keywords: str | None = None
    canonical_url: str | None = None
    canonical_is_self: bool | None = None
    robots_noindex: bool = False
    robots_nofollow: bool = False
    robots_noarchive: bool = False
    robots_nosnippet: bool = False
    robots_noimageindex: bool = False
    robots_max_snippet: int | None = None
    robots_max_image_preview: str | None = None
    googlebot_noindex: bool = False
    googlebot_nofollow: bool = False
    meta_refresh: bool = False
    meta_refresh_delay_s: int | None = None
    og_title: str | None = None
    og_description: str | None = None
    og_image: str | None = None
    og_type: str | None = None
    og_url: str | None = None
    og_site_name: str | None = None
    og_locale: str | None = None
    og_present: bool = False
    article_published_time: str | None = None
    article_modified_time: str | None = None
    article_section: str | None = None
    article_tag: str | None = None
    twitter_card: str | None = None
    twitter_title: str | None = None
    twitter_description: str | None = None
    twitter_image: str | None = None
    twitter_site: str | None = None
    twitter_creator: str | None = None
    twitter_present: bool = False
    hreflang_count: int = 0
    hreflang_langs: list[str] = []
    hreflang_x_default: bool = False
    meta_author: str | None = None
    meta_viewport: str | None = None
    meta_charset: str | None = None
    meta_theme_color: str | None = None
    meta_rating: str | None = None
    x_ua_compatible: str | None = None


# ---------------------------------------------------------------------------
# E-E-A-T sub-model
# ---------------------------------------------------------------------------


class EeatData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    author_name: str | None = None
    author_byline_found: bool = False
    reviewed_by: str | None = None
    reviewed_by_found: bool = False
    author_bio_found: bool = False
    author_bio_text: str | None = None
    contact_page_linked: bool = False
    email_visible: bool = False
    about_page_linked: bool = False
    citation_count: int = 0
    authoritative_citations: int = 0
    expertise_signals: list[str] = []
    trust_signals_count: int = 0


# ---------------------------------------------------------------------------
# Freshness sub-model
# ---------------------------------------------------------------------------


class DateSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = ""
    value: str = ""


class FreshnessData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    published_date: str | None = None
    modified_date: str | None = None
    date_sources: list[DateSource] = []
    date_source_count: int = 0


# ---------------------------------------------------------------------------
# Top-level extraction result
# ---------------------------------------------------------------------------


class ExtractionResult(BaseModel):
    """Assembled result from all 20 extractors.

    Each sub-model corresponds to one extractor module. The errors dict
    records any extractor that returned an ``_error`` key.
    """

    model_config = ConfigDict(extra="forbid")

    title: TitleData = Field(default_factory=TitleData)
    meta_desc: MetaDescData = Field(default_factory=MetaDescData)
    headings: HeadingsData = Field(default_factory=HeadingsData)
    body_text: BodyTextData = Field(default_factory=BodyTextData)
    tables: TablesData = Field(default_factory=TablesData)
    lists: ListsData = Field(default_factory=ListsData)
    faq: FaqData = Field(default_factory=FaqData)
    videos: VideosData = Field(default_factory=VideosData)
    toc: TocData = Field(default_factory=TocData)
    comparison_tables: ComparisonTablesData = Field(default_factory=ComparisonTablesData)
    callout_boxes: CalloutBoxesData = Field(default_factory=CalloutBoxesData)
    step_by_step: StepByStepData = Field(default_factory=StepByStepData)
    jsonld: JsonldData = Field(default_factory=JsonldData)
    images: ImagesData = Field(default_factory=ImagesData)
    links: LinksData = Field(default_factory=LinksData)
    technical: TechnicalData = Field(default_factory=TechnicalData)
    pagination: PaginationData = Field(default_factory=PaginationData)
    meta: MetaData = Field(default_factory=MetaData)
    freshness: FreshnessData = Field(default_factory=FreshnessData)
    eeat: EeatData = Field(default_factory=EeatData)
    errors: dict[str, str] = {}

    @classmethod
    def from_extraction_results(cls, results: dict[str, dict]) -> ExtractionResult:
        """Assemble ExtractionResult from extractor output dicts.

        Each key in *results* maps to a sub-model name. Extractor failures
        (dicts with an ``_error`` key) are recorded in the errors field and
        the sub-model gets default values.
        """
        errors: dict[str, str] = {}
        kwargs: dict = {}

        for name, data in results.items():
            if not isinstance(data, dict):
                continue
            if "_error" in data:
                errors[name] = data["_error"]
                kwargs[name] = {}
            else:
                kwargs[name] = data

        kwargs["errors"] = errors
        return cls(**kwargs)


# ---------------------------------------------------------------------------
# Sink wrapper model
# ---------------------------------------------------------------------------


class ScrapedPage(BaseModel):
    """Wrapper combining fetch-level and extraction-level data for sinks.

    Every sink receives this single object and picks the fields it needs.
    Carries raw HTML, XHR responses, fetch metadata, screenshot bytes
    (when available), and full extraction results.
    """

    model_config = ConfigDict(extra="forbid")

    page_data: PageData
    extraction_result: ExtractionResult
    screenshot_bytes: bytes | None = None

    @field_serializer("screenshot_bytes", when_used="json")
    def serialize_bytes(self, v: bytes | None) -> str | None:
        """Base64-encode bytes for JSON output (D-12)."""
        if v is None:
            return None
        return base64.b64encode(v).decode("ascii")


# ---------------------------------------------------------------------------
# API request/response models
# ---------------------------------------------------------------------------


class SerpRequest(BaseModel):
    """Request body for POST /serp endpoint."""

    model_config = ConfigDict(extra="forbid")
    keyword: str
    market: str
    language: str
    num: int = 10
    target_url: str = ""
    sinks: list[SinkConfig] = []


class JobStatus(str, Enum):
    """Async job lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobState(BaseModel):
    """In-memory state for async scraping jobs."""

    model_config = ConfigDict(extra="forbid")
    job_id: str
    status: JobStatus = JobStatus.PENDING
    results: list[ScrapedPage] | None = None
    error: str | None = None


class ErrorResponse(BaseModel):
    """Structured error response body."""

    model_config = ConfigDict(extra="forbid")
    detail: str
    error_code: str
