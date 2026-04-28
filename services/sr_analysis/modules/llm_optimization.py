from __future__ import annotations

from analysis_service.gemini_client import GeminiClient
from analysis_service.models import (
    ExtractionResult,
    LlmDimension,
    LlmOptimizationGeminiResponse,
    LlmOptimizationResult,
    PageType,
)
from analysis_service.modules.prompt_builder import build_prompt

_DETERMINISTIC_WEIGHT = 0.40
_GEMINI_WEIGHT = 0.60

_MODULE_INSTRUCTIONS = """Evaluate the target page's readiness for AI Overview (Google AI Overviews / LLM citations).

You will receive pre-computed deterministic signals from the page. Focus your evaluation on the QUALITATIVE dimensions that cannot be measured programmatically:

1. **direct_answers**: Does the content provide concise, quotable answers to likely user questions? Score 0-100.
2. **entity_clarity**: Are key entities (brands, products, concepts) clearly defined and disambiguated? Score 0-100.
3. **quotable_passages**: Are there self-contained sentences/paragraphs suitable for AI Overview citations? Score 0-100.

For each dimension, provide:
- score (0-100)
- evidence (what you observed)
- recommendation (what to improve, or null if score >= 80)
"""


def _compute_deterministic_signals(target: ExtractionResult) -> dict[str, float]:
    signals: dict[str, float] = {}

    if not target.faq.has_faq:
        signals["faq_format"] = 0.0
    elif target.faq.total_faq_items >= 3:
        signals["faq_format"] = 100.0
    else:
        signals["faq_format"] = min(100.0, round(target.faq.total_faq_items / 3 * 100, 1))

    jc = target.jsonld.jsonld_count
    if jc == 0:
        signals["structured_data"] = 0.0
    elif jc >= 3:
        signals["structured_data"] = 100.0
    else:
        signals["structured_data"] = round(jc / 3 * 100, 1)

    tl_count = target.tables.table_count + target.lists.ul_count + target.lists.ol_count
    if tl_count == 0:
        signals["table_list_summaries"] = 0.0
    elif tl_count >= 4:
        signals["table_list_summaries"] = 100.0
    else:
        signals["table_list_summaries"] = round(tl_count / 4 * 100, 1)

    all_headings = target.headings.h2_texts + target.headings.h3_texts
    total_h = len(all_headings)
    if total_h == 0:
        signals["heading_specificity"] = 0.0
    else:
        descriptive = sum(
            1 for h in all_headings
            if "?" in h or len(h.split()) > 5
        )
        signals["heading_specificity"] = min(100.0, round(descriptive / total_h * 100, 1))

    has_pub = target.freshness.published_date is not None
    has_mod = target.freshness.modified_date is not None
    if has_pub and has_mod:
        signals["freshness_signals"] = 100.0
    elif has_pub or has_mod:
        signals["freshness_signals"] = 50.0
    else:
        signals["freshness_signals"] = 0.0

    return signals


def _build_variable_data(
    target: ExtractionResult,
    keyword: str,
    page_type: PageType,
    deterministic_signals: dict[str, float],
) -> str:
    headings: list[str] = []
    for h1 in target.headings.h1_texts:
        headings.append(f"H1: {h1}")
    for h2 in target.headings.h2_texts:
        headings.append(f"H2: {h2}")
    headings_str = "\n".join(headings) if headings else "(no headings)"
    content = target.body_text.text[:5000]

    signals_str = "\n".join(
        f"  {k}: {v:.0f}/100" for k, v in deterministic_signals.items()
    )

    return (
        f"KEYWORD: {keyword}\n"
        f"PAGE TYPE: {page_type.value}\n\n"
        f"PRE-COMPUTED DETERMINISTIC SIGNALS:\n{signals_str}\n\n"
        f"TARGET PAGE:\n"
        f"- Headings:\n{headings_str}\n"
        f"- Content excerpt:\n{content}"
    )


def _compute_result(
    deterministic_signals: dict[str, float],
    gemini_response: LlmOptimizationGeminiResponse,
) -> LlmOptimizationResult:
    dimensions: list[LlmDimension] = []
    recommendations: list[str] = []

    for dim_name, dim_score in deterministic_signals.items():
        dimensions.append(LlmDimension(
            name=dim_name,
            score=dim_score,
            source="deterministic",
        ))

    for gd in gemini_response.dimensions:
        dimensions.append(LlmDimension(
            name=gd.name,
            score=gd.score,
            source="gemini",
            evidence=gd.evidence,
            recommendation=gd.recommendation,
        ))
        if gd.recommendation:
            recommendations.append(gd.recommendation)

    det_scores = list(deterministic_signals.values())
    gem_scores = [gd.score for gd in gemini_response.dimensions]

    det_avg = sum(det_scores) / len(det_scores) if det_scores else 0.0
    gem_avg = sum(gem_scores) / len(gem_scores) if gem_scores else 0.0

    if not gem_scores:
        final_score = round(det_avg)
    else:
        final_score = round(_DETERMINISTIC_WEIGHT * det_avg + _GEMINI_WEIGHT * gem_avg)

    return LlmOptimizationResult(
        score=float(final_score),
        dimensions=dimensions,
        deterministic_signals={k: v for k, v in deterministic_signals.items()},
        recommendations=recommendations,
    )


async def score_llm_optimization(
    target: ExtractionResult,
    keyword: str,
    page_type: PageType,
    gemini_client: GeminiClient,
) -> LlmOptimizationResult:
    deterministic_signals = _compute_deterministic_signals(target)

    variable_data = _build_variable_data(target, keyword, page_type, deterministic_signals)
    prompt = build_prompt(
        module_instructions=_MODULE_INSTRUCTIONS,
        variable_data=variable_data,
    )
    raw = await gemini_client.generate(prompt, LlmOptimizationGeminiResponse)
    return _compute_result(deterministic_signals, raw)
