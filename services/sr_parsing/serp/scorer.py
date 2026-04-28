"""Difficulty scoring algorithm for SERP keyword analysis.

Computes a 0-100 score from 5 additive components:
  1. AI Overview         (+30)
  2. Featured Snippet    (+10)
  3. Feature Saturation  (+2 per unique feature, max +20)
  4. Brand Dominance     (+5 per operator in top 5, max +20; +20 instant if branded keyword in top 3)
  5. Major Site Competition (+4 per authority domain in top 5, max +20)

The final score is capped at 100. All config loading uses the cached
loaders from models.py. No side effects beyond config file reads.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from scraper_service.serp.models import (
    OrganicResult,
    SerpFeatures,
    DifficultyScore,
    get_difficulty_label,
    load_operators,
    load_authority_domains,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _get_domain(url: str | None) -> str:
    """Extract domain from URL, strip www., lowercase.

    Returns empty string on failure.
    """
    if not url:
        return ""
    try:
        netloc = urlparse(url).netloc
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc.lower()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

_SATURATION_FIELDS: tuple[str, ...] = (
    "has_ads_top",
    "has_ads_bottom",
    "has_featured_snippet",
    "has_ai_overview",
    "has_knowledge_panel",
    "has_top_stories",
    "has_people_also_ask",
    "has_twitter_cards",
    "has_discussions_forums",
    "has_instant_answer",
    "has_calculator",
    "has_faq_rich_results",
)


# ---------------------------------------------------------------------------
# calculate_difficulty_score
# ---------------------------------------------------------------------------


def calculate_difficulty_score(
    features: SerpFeatures,
    organic_results: list[OrganicResult],
    keyword: str,
) -> DifficultyScore:
    """Compute a 0-100 difficulty score from SERP features and organic results.

    Returns a DifficultyScore with total_score, label, and component_breakdown.
    Never raises -- returns zero-score on any unexpected input.
    """
    breakdown: dict[str, float] = {}

    # Component 1: AI Overview (+30)
    ai_overview_pts = 30.0 if features.has_ai_overview else 0.0
    breakdown["ai_overview"] = ai_overview_pts

    # Component 2: Featured Snippet (+10)
    featured_snippet_pts = 10.0 if features.has_featured_snippet else 0.0
    breakdown["featured_snippet"] = featured_snippet_pts

    # Component 3: Feature Saturation (+2 per unique feature, max +20)
    saturation_count = sum(
        1 for field in _SATURATION_FIELDS if getattr(features, field, False)
    )
    saturation_pts = min(saturation_count * 2.0, 20.0)
    breakdown["feature_saturation"] = saturation_pts

    # Component 4: Brand Dominance (max +20)
    brand_pts = _compute_brand_dominance(organic_results, keyword)
    breakdown["brand_dominance"] = brand_pts

    # Component 5: Major Site Competition (+4 per, max +20)
    authority_pts = _compute_major_site_competition(organic_results)
    breakdown["major_site_competition"] = authority_pts

    # Sum and cap
    total = min(
        ai_overview_pts
        + featured_snippet_pts
        + saturation_pts
        + brand_pts
        + authority_pts,
        100.0,
    )

    return DifficultyScore(
        total_score=total,
        label=get_difficulty_label(total),
        component_breakdown=breakdown,
    )


# ---------------------------------------------------------------------------
# Component 4: Brand Dominance
# ---------------------------------------------------------------------------


def _compute_brand_dominance(
    organic_results: list[OrganicResult],
    keyword: str,
) -> float:
    """Score brand dominance based on operator domains in organic results.

    Branded keyword: if the keyword matches an operator name or alias,
    check if that operator's domain appears in the top 3 results -> +20.
    Generic keyword: count unique operator names in top 5 -> +5 each, max +20.
    """
    operators = load_operators()
    if not operators:
        return 0.0

    keyword_lower = keyword.lower()

    # Build flat list of all operator names + aliases for matching
    all_names: list[str] = []
    for op in operators:
        all_names.append(op["name"].lower())
        all_names.extend(a.lower() for a in op.get("aliases", []))

    is_branded = any(name in keyword_lower for name in all_names)

    if is_branded:
        # Find the matched operator
        matched_operator: dict[str, Any] | None = None
        for op in operators:
            names = [op["name"].lower()] + [a.lower() for a in op.get("aliases", [])]
            if any(n in keyword_lower for n in names):
                matched_operator = op
                break

        if matched_operator:
            brand_domains = [d.lower() for d in matched_operator["domains"]]
            top_3 = organic_results[:3]
            for res in top_3:
                domain = _get_domain(res.url)
                if any(bd in domain for bd in brand_domains):
                    return 20.0

        # Branded keyword but brand not in top 3
        return 0.0
    else:
        # Generic keyword: count unique operator names in top 5
        top_5 = organic_results[:5]
        found_operators: set[str] = set()
        for res in top_5:
            domain = _get_domain(res.url)
            for op in operators:
                for d in op["domains"]:
                    if d.lower() in domain:
                        found_operators.add(op["name"])
        return min(len(found_operators) * 5.0, 20.0)


# ---------------------------------------------------------------------------
# Component 5: Major Site Competition
# ---------------------------------------------------------------------------


def _compute_major_site_competition(
    organic_results: list[OrganicResult],
) -> float:
    """Score major site competition from authority domains + TLD patterns."""
    config = load_authority_domains()
    if not config:
        return 0.0

    high_auth_domains = [d.lower() for d in config.get("domains", [])]
    tld_patterns = [t.lower() for t in config.get("tld_patterns", [])]

    top_5 = organic_results[:5]
    count = 0
    for res in top_5:
        domain = _get_domain(res.url)
        # Exact domain match (contains check)
        if any(ha in domain for ha in high_auth_domains):
            count += 1
            continue
        # TLD pattern match
        if any(domain.endswith(tld) for tld in tld_patterns):
            count += 1

    return min(count * 4.0, 20.0)
