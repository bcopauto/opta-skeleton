"""HTML Element Gap scoring module (DET-02).

Pure function: score_html_element_gap(target, competitors) -> HtmlElementGapResult.
Uses pre-extracted ExtractionResult fields directly — no HTML re-parsing (D-12).
"""
from __future__ import annotations

from analysis_service.models import (
    ElementBreakdown,
    ExtractionResult,
    HtmlElementGapResult,
)

# All 11 element types per D-09 (scoring doc §Module 4)
_ELEMENT_KEYS = [
    "tables",
    "ordered_lists",
    "unordered_lists",
    "faq",
    "images",
    "videos",
    "toc",
    "comparison_charts",
    "callout_boxes",
    "step_by_step",
    "pros_cons",
]


def _detect_elements(er: ExtractionResult) -> dict[str, bool]:
    """Detect presence of each element type from ExtractionResult fields (D-12)."""
    return {
        "tables": er.tables.table_count > 0,
        "ordered_lists": er.lists.ol_count > 0,
        "unordered_lists": er.lists.ul_count > 0,
        "faq": er.faq.has_faq,
        "images": er.images.total_images >= 3,  # images_3plus per scoring doc
        "videos": er.videos.video_count > 0,
        "toc": er.toc.has_toc,
        "comparison_charts": er.comparison_tables.has_comparison_table,
        "callout_boxes": er.callout_boxes.has_callouts,
        "step_by_step": er.step_by_step.has_steps,
        "pros_cons": er.callout_boxes.has_pros_cons,
    }


def score_html_element_gap(
    target: ExtractionResult,
    competitors: list[ExtractionResult],
) -> HtmlElementGapResult:
    """Compute HTML Element Gap Score (0-100).

    Score = elements_target_has / commonly_used_elements × 100
    Commonly used = present on 2+ competitors (or 1+ if only 1 competitor).
    Zero commonly-used elements → score=100 (nothing to improve).
    """
    n_competitors = len(competitors)
    threshold = 2 if n_competitors >= 2 else 1
    warning: str | None = None
    if n_competitors == 1:
        warning = "Limited competitor data — analysis may be less reliable."

    target_elements = _detect_elements(target)
    competitor_element_lists = [_detect_elements(c) for c in competitors]

    # Count how many competitors have each element
    competitor_counts: dict[str, int] = {
        key: sum(1 for ce in competitor_element_lists if ce[key])
        for key in _ELEMENT_KEYS
    }

    # Build ElementBreakdown per field
    breakdowns: dict[str, ElementBreakdown] = {}
    for key in _ELEMENT_KEYS:
        count = competitor_counts[key]
        pct = (count / n_competitors * 100.0) if n_competitors > 0 else 0.0
        breakdowns[key] = ElementBreakdown(
            target_present=target_elements[key],
            competitor_count=count,
            competitor_pct=round(pct, 1),
        )

    # Determine commonly-used elements
    commonly_used = [key for key in _ELEMENT_KEYS if competitor_counts[key] >= threshold]

    if not commonly_used:
        score: float = 100.0
    else:
        target_has_count = sum(1 for key in commonly_used if target_elements[key])
        score = round(target_has_count / len(commonly_used) * 100.0)

    return HtmlElementGapResult(
        score=score,
        tables=breakdowns["tables"],
        ordered_lists=breakdowns["ordered_lists"],
        unordered_lists=breakdowns["unordered_lists"],
        faq=breakdowns["faq"],
        images=breakdowns["images"],
        videos=breakdowns["videos"],
        toc=breakdowns["toc"],
        comparison_charts=breakdowns["comparison_charts"],
        callout_boxes=breakdowns["callout_boxes"],
        step_by_step=breakdowns["step_by_step"],
        pros_cons=breakdowns["pros_cons"],
        low_competitor_data_warning=warning,
    )
