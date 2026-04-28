from __future__ import annotations

import json

from analysis_service.gemini_client import GeminiClient
from analysis_service.models import (
    ExtractionResult,
    GeminiGeneratedSchema,
    GeneratedSchema,
    PageType,
    SchemaJsonLdGeminiResponse,
    SchemaJsonLdResult,
)
from analysis_service.modules.prompt_builder import build_prompt

_MAX_WORDS = 2000

_MODULE_INSTRUCTIONS = """Generate valid JSON-LD structured data for each missing schema type listed below.

For each missing type:
1. Create a complete JSON-LD block with "@context": "https://schema.org" and the correct "@type".
2. Populate fields with actual content from the target page data provided.
3. Follow schema.org specifications for required and recommended properties.
4. Return each schema as a separate object in the schemas array.
5. The json_ld field must be a valid JSON string (e.g. '{"@context":"https://schema.org","@type":"FAQPage"}').
"""


def _truncate_text(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " [truncated]"


def _build_variable_data(
    target: ExtractionResult,
    missing_types: list[str],
    keyword: str,
    page_type: PageType,
) -> str:
    headings: list[str] = []
    for h1 in target.headings.h1_texts:
        headings.append(f"H1: {h1}")
    for h2 in target.headings.h2_texts:
        headings.append(f"H2: {h2}")
    headings_str = "\n".join(headings) if headings else "(no headings)"
    content = _truncate_text(target.body_text.text, _MAX_WORDS)

    faq_questions = "\n".join(target.faq.faq_schema_questions) if target.faq.faq_schema_questions else "(none)"

    return (
        f"MISSING SCHEMA TYPES: {', '.join(missing_types)}\n"
        f"KEYWORD: {keyword}\n"
        f"PAGE TYPE: {page_type.value}\n\n"
        f"TARGET PAGE:\n"
        f"- Title: {target.title.title or '(none)'}\n"
        f"- Headings:\n{headings_str}\n"
        f"- FAQ Questions:\n{faq_questions}\n"
        f"- Content excerpt:\n{content}"
    )


def _validate_schema_block(
    json_ld_dict: dict,
    missing_types: list[str],
) -> tuple[str, list[str]]:
    errors: list[str] = []
    if "@context" not in json_ld_dict:
        errors.append("Missing @context field")
    if "@type" not in json_ld_dict:
        errors.append("Missing @type field")
    elif json_ld_dict["@type"] not in missing_types:
        errors.append(
            f"@type '{json_ld_dict['@type']}' not in missing types: {missing_types}"
        )
    status = "invalid" if errors else "valid"
    return status, errors


def _process_generated_schema(
    gemini_schema: GeminiGeneratedSchema,
    missing_types: list[str],
) -> GeneratedSchema:
    raw = gemini_schema.json_ld
    try:
        json_ld_dict = json.loads(raw) if isinstance(raw, str) else raw
        json_ld_str = json.dumps(json_ld_dict, indent=2)
    except (json.JSONDecodeError, TypeError):
        return GeneratedSchema(
            schema_type=gemini_schema.schema_type,
            json_ld=str(raw),
            status="invalid",
            validation_errors=["json_ld is not valid JSON"],
        )
    status, validation_errors = _validate_schema_block(json_ld_dict, missing_types)
    return GeneratedSchema(
        schema_type=gemini_schema.schema_type,
        json_ld=json_ld_str,
        status=status,
        validation_errors=validation_errors,
    )


async def score_schema_json_ld(
    target: ExtractionResult,
    missing_types: list[str],
    keyword: str,
    page_type: PageType,
    gemini_client: GeminiClient,
) -> SchemaJsonLdResult:
    if not missing_types:
        return SchemaJsonLdResult(
            generated_schemas=[],
            total_generated=0,
            valid_count=0,
            invalid_count=0,
        )

    variable_data = _build_variable_data(target, missing_types, keyword, page_type)
    prompt = build_prompt(
        module_instructions=_MODULE_INSTRUCTIONS,
        variable_data=variable_data,
    )
    raw = await gemini_client.generate(prompt, SchemaJsonLdGeminiResponse)

    generated = [
        _process_generated_schema(s, missing_types)
        for s in raw.schemas
    ]
    valid_count = sum(1 for g in generated if g.status == "valid")
    invalid_count = sum(1 for g in generated if g.status == "invalid")

    return SchemaJsonLdResult(
        generated_schemas=generated,
        total_generated=len(generated),
        valid_count=valid_count,
        invalid_count=invalid_count,
    )
