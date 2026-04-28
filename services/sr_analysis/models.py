"""Pydantic v2 models for the analysis service.

ExtractionResult and its sub-models are copied from scraper_service (D-01: independent service,
no cross-service imports). HeadingsData gains h3_texts and CalloutBoxesData gains has_pros_cons
(D-02: gap fills). SerpFeatures copied from scraper_service/serp/models.py (D-03).
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# ExtractionResult sub-models (copied from scraper_service/models.py — D-01)
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
    h3_texts: list[str] = []  # D-02: gap fill (not in scraper_service)
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
    has_pros_cons: bool = False  # D-02: gap fill (not in scraper_service)


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
    jsonld_blocks: list[dict[str, Any]] = []
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
    recipe_info: dict[str, Any] | None = None
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
    top_anchor_texts: list[dict[str, Any]] = []


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


class ExtractionResult(BaseModel):
    """Assembled result from all 20 extractors.

    Each sub-model corresponds to one extractor module. The errors dict
    records any extractor that returned an ``_error`` key.

    Copied from scraper_service/models.py (D-01). HeadingsData and
    CalloutBoxesData have additional gap-fill fields (D-02).
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
    errors: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# SERP feature flags (copied from scraper_service/serp/models.py — D-03)
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


# ---------------------------------------------------------------------------
# Analysis input models
# ---------------------------------------------------------------------------


class PageType(str, Enum):
    """8 BC page types (D-05)."""

    CODE_PAGE = "code_page"
    REGISTRATION_PAGE = "registration_page"
    COMPARATOR = "comparator"
    OPERATOR_REVIEW = "operator_review"
    APP_PAGE = "app_page"
    BETTING_CASINO_GUIDE = "betting_casino_guide"
    TIMELY_CONTENT = "timely_content"
    OTHER = "other"


class AnalysisRequest(BaseModel):
    """Input to POST /analyze (D-04)."""

    model_config = ConfigDict(extra="forbid")

    target: ExtractionResult = Field(default_factory=ExtractionResult)
    competitors: list[ExtractionResult] = Field(default_factory=list)
    keyword: str
    market: str
    page_type: PageType
    device: str = "desktop"
    serp_features: SerpFeatures | None = None


# ---------------------------------------------------------------------------
# Analysis output models — sub-score breakdowns (D-06 through D-12)
# ---------------------------------------------------------------------------


class ElementBreakdown(BaseModel):
    """Shared sub-score breakdown for HTML element matrix modules (D-07)."""

    model_config = ConfigDict(extra="forbid")
    target_present: bool = False
    competitor_count: int = 0
    competitor_pct: float = 0.0


class HtmlElementGapResult(BaseModel):
    """HTML element gap score with per-element breakdown (D-09, D-10)."""

    model_config = ConfigDict(extra="forbid")
    score: float | None = None
    tables: ElementBreakdown = Field(default_factory=ElementBreakdown)
    ordered_lists: ElementBreakdown = Field(default_factory=ElementBreakdown)
    unordered_lists: ElementBreakdown = Field(default_factory=ElementBreakdown)
    faq: ElementBreakdown = Field(default_factory=ElementBreakdown)
    images: ElementBreakdown = Field(default_factory=ElementBreakdown)
    videos: ElementBreakdown = Field(default_factory=ElementBreakdown)
    toc: ElementBreakdown = Field(default_factory=ElementBreakdown)
    comparison_charts: ElementBreakdown = Field(default_factory=ElementBreakdown)
    callout_boxes: ElementBreakdown = Field(default_factory=ElementBreakdown)
    step_by_step: ElementBreakdown = Field(default_factory=ElementBreakdown)
    pros_cons: ElementBreakdown = Field(default_factory=ElementBreakdown)
    low_competitor_data_warning: str | None = None  # Set when competitor count < 2 (D-11)


class H1MetaOptimizationResult(BaseModel):
    """7-check flat scoring result (D-09). Each check has a bool flag + int points field."""

    model_config = ConfigDict(extra="forbid")
    score: float | None = None
    # Check 1: keyword in title (20pts)
    keyword_in_title: bool = False
    keyword_in_title_pts: int = 0
    # Check 2: keyword in H1 (20pts)
    keyword_in_h1: bool = False
    keyword_in_h1_pts: int = 0
    # Check 3: keyword in meta description (15pts)
    keyword_in_meta_description: bool = False
    keyword_in_meta_description_pts: int = 0
    # Check 4: title length 50-60 chars (10pts)
    title_length_ok: bool = False
    title_length_pts: int = 0
    # Check 5: meta description length 120-160 chars (10pts)
    meta_length_ok: bool = False
    meta_length_pts: int = 0
    # Check 6: H1 differs from title (10pts)
    h1_differs_from_title: bool = False
    h1_differs_from_title_pts: int = 0
    # Check 7: keyword in first 100 words (15pts)
    keyword_in_first_100_words: bool = False
    keyword_in_first_100_words_pts: int = 0
    # Edge case tracking (D-15)
    multiple_h1_warning: str | None = None


class FeatureDetail(BaseModel):
    """Per-feature breakdown for SERP Feature Opportunity Score (D-08)."""

    model_config = ConfigDict(extra="forbid")
    name: str  # Display name e.g. "Featured Snippet"
    type: str  # Internal key e.g. "featured_snippet"
    assessable: bool  # Whether this feature can be captured by content pages
    capturable: bool | None = None  # None if not assessable; True/False if assessable
    reason: str | None = None  # Why capturable/not e.g. "FAQPage schema present"
    recommendation: str | None = None  # Action to take if not capturable


class SerpFeatureOpportunityResult(BaseModel):
    """SERP feature opportunity score (D-08)."""

    model_config = ConfigDict(extra="forbid")
    score: float | None = None
    capturable_features: int = 0
    assessable_features: int = 0
    feature_details: list[FeatureDetail] = Field(default_factory=list)


class SchemaMarkupResult(BaseModel):
    """Schema/markup gap score (D-11)."""

    model_config = ConfigDict(extra="forbid")
    score: float | None = None
    missing_types: list[str] = Field(default_factory=list)
    present_types: list[str] = Field(default_factory=list)
    relevant_types: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Gemini module result models (Phase 12 — AI-01 through AI-05)
# ---------------------------------------------------------------------------


class TopicToAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str
    competitor_coverage: str
    competitors_covering: int
    importance: str
    covered_by_target: bool = False
    suggested_heading: str | None = None
    content_summary: str | None = None


class TopicToTrim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: str
    reason: str
    recommendation: str


class InformationGapResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: float | None = None
    breakdown: str | None = None
    topics_to_add: list[TopicToAdd] = Field(default_factory=list)
    topics_to_trim: list[TopicToTrim] = Field(default_factory=list)
    total_important_topics: int = 0
    covered_important_topics: int = 0


class BestPracticeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str
    passed: bool = False
    evidence: str | None = None
    recommendation: str | None = None


class StructuralSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    heading: str
    rationale: str


class L2RuleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_name: str
    source: str
    rule_text: str
    priority: str
    status: str
    reason: str | None = None


class L2NotVerifiable(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_name: str
    reason: str


class ContentBestPracticesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    l1_score: float | None = None
    intent_summary: str | None = None
    best_practices: list[BestPracticeItem] = Field(default_factory=list)
    structural_suggestions: list[StructuralSuggestion] = Field(default_factory=list)
    l2_score: float | None = None
    rules_applied: list[L2RuleResult] = Field(default_factory=list)
    passed: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    not_verifiable: list[L2NotVerifiable] = Field(default_factory=list)


class GeneratedSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_type: str
    json_ld: str
    status: str
    validation_errors: list[str] = Field(default_factory=list)


class SchemaJsonLdResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generated_schemas: list[GeneratedSchema] = Field(default_factory=list)
    total_generated: int = 0
    valid_count: int = 0
    invalid_count: int = 0


class LlmDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    score: float
    source: str
    evidence: str | None = None
    recommendation: str | None = None


class LlmOptimizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: float | None = None
    dimensions: list[LlmDimension] = Field(default_factory=list)
    deterministic_signals: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Gemini response models (internal — used as response_schema for generate())
# ---------------------------------------------------------------------------


class GeminiTopic(BaseModel):
    model_config = ConfigDict(extra="ignore")
    topic: str
    competitor_coverage: str
    competitors_covering: int
    is_important: bool
    covered_by_target: bool
    suggested_heading: str | None = None
    content_summary: str | None = None


class GeminiBloat(BaseModel):
    model_config = ConfigDict(extra="ignore")
    section: str
    reason: str
    recommendation: str


class InformationGapGeminiResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    topics: list[GeminiTopic] = Field(default_factory=list)
    bloat: list[GeminiBloat] = Field(default_factory=list)


class GeminiBestPractice(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    name: str
    description: str
    pass_: bool = Field(alias="pass")
    evidence: str | None = None
    recommendation: str | None = None


class GeminiStructuralSuggestion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    heading: str
    rationale: str


class ContentBestPracticesL1GeminiResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    intent_summary: str
    best_practices: list[GeminiBestPractice] = Field(default_factory=list)
    structural_suggestions: list[GeminiStructuralSuggestion] = Field(default_factory=list)


class GeminiGeneratedSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_type: str
    json_ld: str


class SchemaJsonLdGeminiResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schemas: list[GeminiGeneratedSchema] = Field(default_factory=list)


class GeminiLlmDimension(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    score: float
    evidence: str | None = None
    recommendation: str | None = None


class LlmOptimizationGeminiResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    dimensions: list[GeminiLlmDimension] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Top-level result returned by POST /analyze. All module fields default to None (D-16).

    Field names are locked — consumed by django_app v3.0 API contract.
    Phases 10-12 populate each field with real results.
    """

    model_config = ConfigDict(extra="forbid")

    # Deterministic modules (Phase 10)
    html_element_gap: HtmlElementGapResult | None = None
    h1_meta_optimization: H1MetaOptimizationResult | None = None
    serp_feature_opportunity: SerpFeatureOpportunityResult | None = None
    schema_markup: SchemaMarkupResult | None = None

    # Gemini modules (Phase 12)
    information_gap: InformationGapResult | None = None
    content_best_practices: ContentBestPracticesResult | None = None
    schema_json_ld: SchemaJsonLdResult | None = None
    llm_optimization: LlmOptimizationResult | None = None

    # Composite (Phase 10)
    overall_score: float | None = None
    priority_modules: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Async job models (Phase 13 — ANLYS-04)
# ---------------------------------------------------------------------------


class AnalysisJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisJobState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: AnalysisJobStatus = AnalysisJobStatus.PENDING
    completed_modules: list[str] = Field(default_factory=list)
    result: AnalysisResult | None = None
    error: str | None = None
    created_at: str = ""
    completed_at: str | None = None
