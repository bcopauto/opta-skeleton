from __future__ import annotations

from analysis_service.gemini_client import GeminiClient
from analysis_service.models import (
    BestPracticeItem,
    ContentBestPracticesL1GeminiResponse,
    ContentBestPracticesResult,
    ExtractionResult,
    PageType,
    StructuralSuggestion,
)
from analysis_service.modules.prompt_builder import build_prompt

_MAX_WORDS = 3000

_MODULE_INSTRUCTIONS = """Analyze the target page for the given keyword and page type.

1. Analyze the search intent: what is the user trying to accomplish?
2. Based on the intent, generate a checklist of content best practices this page SHOULD follow.
3. For each best practice, check whether the target page currently meets it.
4. Suggest an optimal page structure (heading hierarchy, section order).
5. All output must be in ENGLISH regardless of content language.
"""


def _truncate_text(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " [truncated]"


def _build_variable_data(
    target: ExtractionResult,
    keyword: str,
    page_type: PageType,
    market: str,
) -> str:
    headings: list[str] = []
    for h1 in target.headings.h1_texts:
        headings.append(f"H1: {h1}")
    for h2 in target.headings.h2_texts:
        headings.append(f"H2: {h2}")
    for h3 in target.headings.h3_texts:
        headings.append(f"H3: {h3}")
    headings_str = "\n".join(headings) if headings else "(no headings)"
    content = _truncate_text(target.body_text.text, _MAX_WORDS)

    return (
        f"KEYWORD: {keyword}\n"
        f"PAGE TYPE: {page_type.value}\n"
        f"MARKET: {market}\n\n"
        f"TARGET PAGE:\n"
        f"- Headings:\n{headings_str}\n"
        f"- Content:\n{content}"
    )


def _compute_result(
    gemini_response: ContentBestPracticesL1GeminiResponse,
) -> ContentBestPracticesResult:
    practices = gemini_response.best_practices
    if len(practices) == 0:
        l1_score = 100.0
    else:
        passed_count = sum(1 for p in practices if p.pass_)
        l1_score = float(round(passed_count / len(practices) * 100))

    best_practice_items = [
        BestPracticeItem(
            name=p.name,
            description=p.description,
            passed=p.pass_,
            evidence=p.evidence,
            recommendation=p.recommendation,
        )
        for p in practices
    ]

    structural_suggestions = [
        StructuralSuggestion(heading=s.heading, rationale=s.rationale)
        for s in gemini_response.structural_suggestions
    ]

    return ContentBestPracticesResult(
        l1_score=l1_score,
        intent_summary=gemini_response.intent_summary,
        best_practices=best_practice_items,
        structural_suggestions=structural_suggestions,
    )


async def score_content_best_practices_l1(
    target: ExtractionResult,
    keyword: str,
    page_type: PageType,
    market: str,
    gemini_client: GeminiClient,
) -> ContentBestPracticesResult:
    variable_data = _build_variable_data(target, keyword, page_type, market)
    prompt = build_prompt(
        module_instructions=_MODULE_INSTRUCTIONS,
        variable_data=variable_data,
    )
    raw = await gemini_client.generate(prompt, ContentBestPracticesL1GeminiResponse)
    return _compute_result(raw)
