"""Pydantic validation models for bc_best_practices.yaml.

All models use extra="ignore" — intentional exception to project-wide extra="forbid".
The BC team can add new YAML keys without requiring a Python code change.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError


class BcPageTypePriority(BaseModel):
    model_config = ConfigDict(extra="ignore")
    priority: int
    intent: str
    conversion: str
    traffic: str


class BcRule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rule: str | None = None
    check: str
    priority: str
    detail: str | None = None
    applies_to: list[str] | None = None
    criterion: str | None = None


class BcMandatoryElement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    element: str
    check: str
    priority: str
    detail: str | None = None


class BcMandatorySection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    section: str
    heading_level: str
    check: str
    priority: str
    detail: str | None = None


class BcChecklistItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    check_item: str | None = None
    check: str
    priority: str
    detail: str | None = None
    rule: str | None = None


class BcPageTypeConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str | None = None
    mandatory_elements: list[BcMandatoryElement] | None = None
    mandatory_sections: list[BcMandatorySection] | None = None
    cta_rules: list[BcRule] | None = None
    serp_checklist: list[BcChecklistItem] | None = None
    special_rules: list[BcRule] | None = None
    important_notes: list[str] | None = None
    above_fold: list[BcMandatoryElement] | None = None
    below_fold: list[BcMandatoryElement] | None = None
    desktop_above_fold: list[BcRule] | None = None
    mobile_above_fold: list[BcRule] | None = None
    content_structure: list[BcRule] | None = None
    monetization_rules: list[BcRule] | None = None
    bc_patterns: list[BcRule] | None = None
    why_it_matters: list[str] | None = None
    featured_tip_above_fold: list[BcMandatoryElement] | None = None
    event_tip_page: list[BcMandatoryElement] | None = None
    tips_hub_page: list[BcMandatoryElement] | None = None
    important_rules: list[BcRule] | None = None
    homepage_rules: list[BcRule] | None = None
    overview_rules: list[BcRule] | None = None


class BcSchemaRequirementItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_: str | None = None
    check: str
    priority: str

    def __init__(self, **data: Any) -> None:
        if "schema" in data:
            data["schema_"] = data.pop("schema")
        super().__init__(**data)


class BcSchemaRequirement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    required: list[BcSchemaRequirementItem]


class BcProvenOptimization(BaseModel):
    model_config = ConfigDict(extra="ignore")
    optimization: str
    check: str | None = None
    applies_to: list[str] | None = None


class BcBenchmarkResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    test: str
    result: str
    applies_to: list[str] | None = None


class BcConversionOptimization(BaseModel):
    model_config = ConfigDict(extra="ignore")
    core_criteria: list[BcRule] | None = None
    proven_optimizations: list[BcProvenOptimization] | None = None
    benchmark_results: list[BcBenchmarkResult] | None = None


class BcFeaturedSnippets(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rules: list[BcRule]


class BcGoogleUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    update: str
    check: str
    priority: str
    detail: str | None = None


class BcProgrammaticCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    check: str
    priority: str | None = None
    detail: str | None = None
    rule: str | None = None


class BcOpenQuestion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    question: str
    status: str | None = None
    detail: str | None = None


class BcBestPracticesConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    version: str
    page_type_priority: dict[str, BcPageTypePriority]
    universal_rules: dict[str, list[BcRule]]
    page_types: dict[str, BcPageTypeConfig]
    schema_requirements: dict[str, BcSchemaRequirement] | None = None
    conversion_optimization: BcConversionOptimization | None = None
    featured_snippets: BcFeaturedSnippets | None = None
    google_updates_awareness: list[BcGoogleUpdate] | None = None
    serp_analysis_checklist: dict[str, list[BcChecklistItem]] | None = None
    programmatic_checks: dict[str, list[BcProgrammaticCheck]] | None = None
    open_questions: list[BcOpenQuestion] | None = None


def load_bc_config(path: str) -> BcBestPracticesConfig:
    """Load and validate bc_best_practices.yaml.

    Raises RuntimeError if the file is missing, unreadable, or fails Pydantic validation.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise RuntimeError(f"bc_best_practices.yaml not found: {config_path.resolve()}")

    try:
        with config_path.open() as f:
            raw = yaml.safe_load(f)
    except Exception as exc:
        raise RuntimeError(f"Failed to read {config_path.resolve()}: {exc}") from exc

    if raw is None:
        raise RuntimeError(f"bc_best_practices.yaml is empty: {config_path.resolve()}")

    try:
        return BcBestPracticesConfig.model_validate(raw)
    except ValidationError as exc:
        raise RuntimeError(
            f"bc_best_practices.yaml validation failed ({config_path.resolve()}):\n{exc}"
        ) from exc
