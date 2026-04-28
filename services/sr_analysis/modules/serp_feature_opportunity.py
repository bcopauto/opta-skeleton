"""SERP Feature Opportunity scoring module (DET-01).

Pure function: score_serp_feature_opportunity(target, serp_features) -> SerpFeatureOpportunityResult.
8 assessable features (D-04); AI Overview and 8 others excluded from denominator (D-05).
Capturability checks use ExtractionResult fields — no HTML re-parsing.
"""
from __future__ import annotations

from analysis_service.models import (
    ExtractionResult,
    FeatureDetail,
    SerpFeatureOpportunityResult,
    SerpFeatures,
)

# Assessable features: SerpFeatures field name → display name (D-04)
_ASSESSABLE: dict[str, str] = {
    "has_featured_snippet": "Featured Snippet",
    "has_people_also_ask": "People Also Ask",
    "has_knowledge_panel": "Knowledge Panel",
    "has_videos_results": "Video Carousel",
    "has_images_results": "Image Pack",
    "has_top_stories": "Top Stories",
    "has_faq_rich_results": "FAQ Rich Results",
    "has_sitelinks": "Sitelinks",
}

# Non-assessable: excluded from denominator (D-05)
_NONASSESSABLE: dict[str, str] = {
    "has_ai_overview": "AI Overview",
    "has_local_pack": "Local Pack",
    "has_shopping_results": "Shopping Results",
    "has_twitter_cards": "Twitter/X Cards",
    "has_related_searches": "Related Searches",
    "has_discussions_forums": "Discussions & Forums",
    "has_instant_answer": "Instant Answer",
    "has_calculator": "Calculator",
    "has_ads_top": "Ads (Top)",
    "has_ads_bottom": "Ads (Bottom)",
    "has_organic_results": "Organic Results",
}


def _check_capturable(feature_flag: str, target: ExtractionResult) -> tuple[bool, str]:
    """Check if target page can capture this SERP feature.

    Returns (capturable: bool, reason: str).
    Uses ExtractionResult fields only — no HTML re-parsing.
    """
    question_headings = [
        h for h in target.headings.h2_texts + target.headings.h3_texts
        if "?" in h
    ]
    has_faq_or_questions = target.faq.has_faq or len(question_headings) > 0

    if feature_flag == "has_featured_snippet":
        capturable = target.body_text.word_count > 0
        reason = (
            "Page has extractable body content (can provide direct factual answer)"
            if capturable
            else "No body text detected — cannot provide a direct answer"
        )
        return capturable, reason

    if feature_flag == "has_people_also_ask":
        capturable = has_faq_or_questions
        reason = (
            "FAQPage schema present or question-format headings detected"
            if capturable
            else "No FAQPage schema and no question-format H2/H3 headings"
        )
        return capturable, reason

    if feature_flag == "has_faq_rich_results":
        capturable = has_faq_or_questions
        reason = (
            "FAQPage schema or question-format headings detected"
            if capturable
            else "Add FAQPage schema or question-format headings to qualify"
        )
        return capturable, reason

    if feature_flag == "has_images_results":
        capturable = target.images.total_images >= 3
        reason = (
            f"{target.images.total_images} images detected (3+ required)"
            if capturable
            else f"Only {target.images.total_images} image(s) detected — need 3+ with descriptive alt text"
        )
        return capturable, reason

    if feature_flag == "has_videos_results":
        capturable = target.videos.video_count > 0
        reason = (
            f"{target.videos.video_count} video embed(s) detected"
            if capturable
            else "No embedded video detected — add YouTube/Vimeo iframe or <video> element"
        )
        return capturable, reason

    if feature_flag == "has_top_stories":
        capturable = target.jsonld.has_article
        reason = (
            "Article/NewsArticle schema detected"
            if capturable
            else "Add NewsArticle schema with recent publication date to qualify"
        )
        return capturable, reason

    if feature_flag == "has_sitelinks":
        capturable = target.jsonld.has_breadcrumb
        reason = (
            "BreadcrumbList schema detected"
            if capturable
            else "Add BreadcrumbList schema and ensure clean URL path structure"
        )
        return capturable, reason

    if feature_flag == "has_knowledge_panel":
        capturable = target.jsonld.has_organization
        reason = (
            "Organization schema detected"
            if capturable
            else "Add Organization schema with name matching the target brand/entity"
        )
        return capturable, reason

    # Fallback (should not reach here for known assessable features)
    return False, "Assessment not available"


def score_serp_feature_opportunity(
    target: ExtractionResult,
    serp_features: SerpFeatures | None,
) -> SerpFeatureOpportunityResult:
    """Compute SERP Feature Opportunity Score (0-100).

    Score = capturable_features / assessable_features × 100.
    AI Overview excluded from denominator (D-05).
    Returns score=None if serp_features is None (D-07).
    """
    if serp_features is None:
        return SerpFeatureOpportunityResult(score=None)

    feature_details: list[FeatureDetail] = []
    assessable_count = 0
    capturable_count = 0

    for flag, display_name in {**_ASSESSABLE, **_NONASSESSABLE}.items():
        detected = getattr(serp_features, flag, False)
        if not detected:
            continue

        is_assessable = flag in _ASSESSABLE

        if is_assessable:
            assessable_count += 1
            capturable, reason = _check_capturable(flag, target)
            if capturable:
                capturable_count += 1
            recommendation = (
                None
                if capturable
                else f"Improve page to capture {display_name}"
            )
            feature_details.append(
                FeatureDetail(
                    name=display_name,
                    type=flag.removeprefix("has_"),
                    assessable=True,
                    capturable=capturable,
                    reason=reason,
                    recommendation=recommendation,
                )
            )
        else:
            feature_details.append(
                FeatureDetail(
                    name=display_name,
                    type=flag.removeprefix("has_"),
                    assessable=False,
                    capturable=None,
                    reason=None,
                    recommendation="Not capturable by content pages",
                )
            )

    if assessable_count == 0:
        score: float = 100.0
    else:
        score = round(capturable_count / assessable_count * 100.0)

    return SerpFeatureOpportunityResult(
        score=score,
        capturable_features=capturable_count,
        assessable_features=assessable_count,
        feature_details=feature_details,
    )
