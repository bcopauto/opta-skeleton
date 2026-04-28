"""Overall Score and Priority List module (DET-05, DET-07).

Pure function: score_overall(result) -> (overall_score, priority_modules).
Weighted composite of 5 contributing modules with null propagation (D-20).
Priority list sorted ascending by score (lowest = highest priority, D-22).
"""
from __future__ import annotations

from analysis_service.models import AnalysisResult

# Module weights (D-19). Must sum to 1.00.
_WEIGHTS: dict[str, float] = {
    "information_gap": 0.30,
    "h1_meta_optimization": 0.20,
    "serp_feature_opportunity": 0.20,
    "html_element_gap": 0.15,
    "schema_markup": 0.15,
}


def _get_score(result: AnalysisResult, module: str) -> float | None:
    """Extract .score from a named module result on AnalysisResult.

    Returns None if the module result is None or its score is None.
    """
    module_result = getattr(result, module, None)
    if module_result is None:
        return None
    return getattr(module_result, "score", None)


def score_overall(
    result: AnalysisResult,
) -> tuple[float | None, list[str]]:
    """Compute Overall Score and Priority List.

    Returns:
        (overall_score, priority_modules) tuple.
        overall_score = None if any weighted module score is None (D-20).
        priority_modules = module names with non-null scores, sorted ascending by score (D-22).
            Ties broken alphabetically by module name.
    """
    module_scores: dict[str, float | None] = {
        module: _get_score(result, module)
        for module in _WEIGHTS
    }

    # Priority list: only non-null scores, ascending
    non_null = [
        (name, score)
        for name, score in module_scores.items()
        if score is not None
    ]
    non_null_sorted = sorted(non_null, key=lambda x: (x[1], x[0]))
    priority_modules = [name for name, _ in non_null_sorted]

    # Null propagation: any weighted module null → overall null (D-20)
    if any(score is None for score in module_scores.values()):
        return None, priority_modules

    weighted_sum = sum(
        module_scores[module] * weight  # type: ignore[operator]
        for module, weight in _WEIGHTS.items()
    )
    overall = float(round(weighted_sum))

    return overall, priority_modules
