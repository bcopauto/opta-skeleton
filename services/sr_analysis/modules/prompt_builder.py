from __future__ import annotations

SYSTEM_PREFIX = (
    "You are an expert SEO content analyst. "
    "Analyze web pages for search engine optimization quality. "
    "All output must be in ENGLISH regardless of content language. "
    "Return ONLY valid JSON matching the requested schema. "
    "Do not include markdown formatting or code fences in your response."
)


def build_prompt(
    *,
    system_instructions: str = SYSTEM_PREFIX,
    bc_config_yaml: str | None = None,
    module_instructions: str,
    variable_data: str,
) -> str:
    parts = [system_instructions]
    if bc_config_yaml is not None:
        parts.append(f"\n\nBC BEST PRACTICES CONFIGURATION:\n{bc_config_yaml}")
    parts.append(f"\n\nTASK:\n{module_instructions}")
    parts.append(f"\n\nDATA:\n{variable_data}")
    return "".join(parts)
