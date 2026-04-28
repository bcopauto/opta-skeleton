from __future__ import annotations

from analysis_service.gemini_client import GeminiClient
from analysis_service.models import (
    ExtractionResult,
    InformationGapGeminiResponse,
    InformationGapResult,
    PageType,
    TopicToAdd,
    TopicToTrim,
)
from analysis_service.modules.prompt_builder import build_prompt

_MAX_WORDS_PER_PAGE = 3000

_MODULE_INSTRUCTIONS = """Compare the target page against competitor pages for the given keyword and page type.

1. List ALL distinct topics/subtopics covered across competitors.
2. For each topic, note how many competitors cover it.
3. For each topic, check if the target page covers it.
4. Identify sections on the target page that NO competitor covers (potential bloat).
5. All recommendations in ENGLISH regardless of content language.
6. Mark topics as "is_important" if covered by 2+ competitors (or 1+ if only a single competitor).
7. For topics to add, provide a suggested_heading (H2/H3 text) and content_summary (1-2 sentences).
"""


def _truncate_text(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " [truncated]"


def _format_page_data(er: ExtractionResult, label: str) -> str:
    headings: list[str] = []
    for h1 in er.headings.h1_texts:
        headings.append(f"H1: {h1}")
    for h2 in er.headings.h2_texts:
        headings.append(f"H2: {h2}")
    for h3 in er.headings.h3_texts:
        headings.append(f"H3: {h3}")
    headings_str = "\n".join(headings) if headings else "(no headings)"
    content = _truncate_text(er.body_text.text, _MAX_WORDS_PER_PAGE)
    return f"{label}:\n- Headings:\n{headings_str}\n- Content:\n{content}"


def _build_variable_data(
    target: ExtractionResult,
    competitors: list[ExtractionResult],
    keyword: str,
    page_type: PageType,
) -> str:
    parts = [f"KEYWORD: {keyword}", f"PAGE TYPE: {page_type.value}", ""]
    parts.append(_format_page_data(target, "TARGET PAGE"))
    for i, comp in enumerate(competitors, 1):
        parts.append("")
        parts.append(_format_page_data(comp, f"COMPETITOR {i}"))
    return "\n".join(parts)


def _compute_result(
    gemini_response: InformationGapGeminiResponse,
    num_competitors: int,
) -> InformationGapResult:
    topics = gemini_response.topics
    threshold = 1 if num_competitors <= 1 else 2
    important = [t for t in topics if t.competitors_covering >= threshold]
    covered = [t for t in important if t.covered_by_target]

    if len(important) == 0:
        score = 100.0
    else:
        score = float(round(len(covered) / len(important) * 100))

    topics_to_add_raw = [t for t in important if not t.covered_by_target]
    topics_to_add_raw.sort(key=lambda t: t.competitors_covering, reverse=True)
    topics_to_add = [
        TopicToAdd(
            topic=t.topic,
            competitor_coverage=t.competitor_coverage,
            competitors_covering=t.competitors_covering,
            importance="High" if t.competitors_covering >= threshold + 1 else "Medium",
            covered_by_target=False,
            suggested_heading=t.suggested_heading,
            content_summary=t.content_summary,
        )
        for t in topics_to_add_raw
    ]

    topics_to_trim = [
        TopicToTrim(section=b.section, reason=b.reason, recommendation=b.recommendation)
        for b in gemini_response.bloat
    ]

    breakdown = f"{len(covered)} of {len(important)} important topics covered"

    return InformationGapResult(
        score=score,
        breakdown=breakdown,
        topics_to_add=topics_to_add,
        topics_to_trim=topics_to_trim,
        total_important_topics=len(important),
        covered_important_topics=len(covered),
    )


async def score_information_gap(
    target: ExtractionResult,
    competitors: list[ExtractionResult],
    keyword: str,
    page_type: PageType,
    gemini_client: GeminiClient,
) -> InformationGapResult:
    variable_data = _build_variable_data(target, competitors, keyword, page_type)
    prompt = build_prompt(
        module_instructions=_MODULE_INSTRUCTIONS,
        variable_data=variable_data,
    )
    raw = await gemini_client.generate(prompt, InformationGapGeminiResponse)
    return _compute_result(raw, len(competitors))
