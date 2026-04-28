"""Schema/Markup scoring module (DET-04).

Pure function: score_schema_markup(target, competitors, page_type) -> SchemaMarkupResult.
Relevant schema set = union(competitor schemas, page-type recommended).
Uses ExtractionResult.jsonld.all_schema_types — no HTML re-parsing (D-17).
"""
from __future__ import annotations

from analysis_service.models import (
    ExtractionResult,
    PageType,
    SchemaMarkupResult,
)

# Hardcoded recommended schemas per page type (D-16)
# Key = PageType.value string
_RECOMMENDED: dict[str, set[str]] = {
    "code_page": {
        "FAQPage", "Article", "NewsArticle", "BreadcrumbList", "WebPage", "HowTo", "ItemList",
    },
    "registration_page": {
        "FAQPage", "Article", "BreadcrumbList", "HowTo", "WebPage",
    },
    "comparator": {
        "FAQPage", "Article", "BreadcrumbList", "ItemList", "Table",
    },
    "operator_review": {
        "Review", "FAQPage", "Article", "BreadcrumbList", "Organization",
    },
    "app_page": {
        "FAQPage", "Article", "BreadcrumbList", "SoftwareApplication",
    },
    "betting_casino_guide": {
        "Article", "FAQPage", "HowTo", "BreadcrumbList",
    },
    "timely_content": {
        "NewsArticle", "BreadcrumbList", "Event", "SportsEvent",
    },
    "other": {
        "Article", "BreadcrumbList", "WebPage",
    },
}


def _normalize_type(schema_type: str) -> str:
    """Normalize schema type to short form.

    "https://schema.org/Article" → "Article"
    "http://schema.org/Article"  → "Article"
    "Article"                    → "Article"
    Handles trailing slashes: "https://schema.org/Article/" → "Article"
    """
    return schema_type.rstrip("/").split("/")[-1]


def _extract_schemas(er: ExtractionResult) -> set[str]:
    """Extract and normalize all schema types from an ExtractionResult."""
    return {_normalize_type(t) for t in er.jsonld.all_schema_types}


def score_schema_markup(
    target: ExtractionResult,
    competitors: list[ExtractionResult],
    page_type: PageType,
) -> SchemaMarkupResult:
    """Compute Schema/Markup Score (0-100).

    Score = |target_schemas ∩ relevant| / |relevant| × 100
    Relevant = union(competitor schemas, page-type recommended schemas).
    """
    target_schemas = _extract_schemas(target)

    competitor_schemas: set[str] = set()
    for comp in competitors:
        competitor_schemas.update(_extract_schemas(comp))

    recommended = _RECOMMENDED.get(page_type.value, set())
    relevant_schemas = competitor_schemas | recommended

    present_relevant = target_schemas & relevant_schemas

    if len(relevant_schemas) == 0:
        score: float = 100.0
    else:
        score = round(len(present_relevant) / len(relevant_schemas) * 100.0)

    return SchemaMarkupResult(
        score=score,
        missing_types=sorted(relevant_schemas - target_schemas),
        present_types=sorted(present_relevant),
        relevant_types=sorted(relevant_schemas),
    )
