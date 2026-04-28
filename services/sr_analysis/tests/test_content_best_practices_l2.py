from __future__ import annotations

import pytest

from analysis_service.models import ExtractionResult, PageType
from analysis_service.modules.content_best_practices_l2 import (
    _NOT_VERIFIABLE_EXTERNAL,
    _NOT_VERIFIABLE_HTML,
    _PAGE_TYPE_YAML_KEY,
    _VERIFIABLE_CHECKS,
    score_content_best_practices_l2,
)


# --- Page type mapping ---


def test_page_type_mapping_comparator() -> None:
    assert _PAGE_TYPE_YAML_KEY["comparator"] == "comparator_page"


def test_page_type_mapping_operator_review() -> None:
    assert _PAGE_TYPE_YAML_KEY["operator_review"] == "review_page"


def test_page_type_mapping_betting_casino_guide() -> None:
    assert _PAGE_TYPE_YAML_KEY["betting_casino_guide"] == "guide"


def test_page_type_mapping_code_page_identity() -> None:
    assert _PAGE_TYPE_YAML_KEY["code_page"] == "code_page"


def test_page_type_mapping_other_empty() -> None:
    assert _PAGE_TYPE_YAML_KEY["other"] == ""


# --- Registry sizes ---


def test_verifiable_checks_count() -> None:
    assert len(_VERIFIABLE_CHECKS) >= 18


def test_not_verifiable_html_count() -> None:
    assert len(_NOT_VERIFIABLE_HTML) >= 20


def test_not_verifiable_external_count() -> None:
    assert len(_NOT_VERIFIABLE_EXTERNAL) >= 9


# --- Individual verifiable checks ---


def test_has_toc_true() -> None:
    er = ExtractionResult()
    er.toc.has_toc = True
    ok, _ = _VERIFIABLE_CHECKS["has_toc"](er)
    assert ok is True


def test_has_toc_false() -> None:
    er = ExtractionResult()
    ok, _ = _VERIFIABLE_CHECKS["has_toc"](er)
    assert ok is False


def test_has_faq_section_true() -> None:
    er = ExtractionResult()
    er.faq.has_faq = True
    ok, _ = _VERIFIABLE_CHECKS["has_faq_section"](er)
    assert ok is True


def test_has_breadcrumb_navigation_true() -> None:
    er = ExtractionResult()
    er.jsonld.has_breadcrumb = True
    ok, _ = _VERIFIABLE_CHECKS["has_breadcrumb_navigation"](er)
    assert ok is True


def test_has_real_author_true() -> None:
    er = ExtractionResult()
    er.eeat.author_name = "John Doe"
    ok, _ = _VERIFIABLE_CHECKS["has_real_author"](er)
    assert ok is True


def test_has_real_author_none() -> None:
    er = ExtractionResult()
    ok, _ = _VERIFIABLE_CHECKS["has_real_author"](er)
    assert ok is False


def test_schema_faqpage_true() -> None:
    er = ExtractionResult()
    er.jsonld.has_faq = True
    ok, _ = _VERIFIABLE_CHECKS["schema_faqpage"](er)
    assert ok is True


def test_has_minimum_two_tables_true() -> None:
    er = ExtractionResult()
    er.tables.table_count = 3
    ok, _ = _VERIFIABLE_CHECKS["has_minimum_two_tables"](er)
    assert ok is True


def test_has_minimum_two_tables_false() -> None:
    er = ExtractionResult()
    er.tables.table_count = 1
    ok, _ = _VERIFIABLE_CHECKS["has_minimum_two_tables"](er)
    assert ok is False


def test_has_hreflang_tags_true() -> None:
    er = ExtractionResult()
    er.meta.hreflang_count = 3
    ok, _ = _VERIFIABLE_CHECKS["has_hreflang_tags"](er)
    assert ok is True


def test_has_visible_dates_true() -> None:
    er = ExtractionResult()
    er.freshness.published_date = "2024-01-01"
    ok, _ = _VERIFIABLE_CHECKS["has_visible_dates"](er)
    assert ok is True


def test_has_minimum_one_internal_link_true() -> None:
    er = ExtractionResult()
    er.links.internal_links = 5
    ok, _ = _VERIFIABLE_CHECKS["has_minimum_one_internal_link"](er)
    assert ok is True


# --- Not-verifiable classification ---


def test_cta_above_fold_in_html_set() -> None:
    assert "cta_above_fold" in _NOT_VERIFIABLE_HTML


def test_content_recently_updated_in_external_set() -> None:
    assert "content_recently_updated" in _NOT_VERIFIABLE_EXTERNAL


# --- Full score function ---


@pytest.fixture
def _minimal_bc_config():
    from analysis_service.bc_config import BcBestPracticesConfig
    return BcBestPracticesConfig(
        version="1.0",
        page_type_priority={},
        universal_rules={},
        page_types={},
    )


def test_score_l2_empty_extraction_minimal_config(_minimal_bc_config) -> None:
    er = ExtractionResult()
    result = score_content_best_practices_l2(er, PageType.OTHER, _minimal_bc_config)
    assert result.l2_score is not None
    assert isinstance(result.l2_score, float)


def test_score_l2_other_page_type_only_universal(_minimal_bc_config) -> None:
    result = score_content_best_practices_l2(ExtractionResult(), PageType.OTHER, _minimal_bc_config)
    assert result.l2_score == 100.0


def test_score_l2_verifiable_pass_in_passed_list() -> None:
    from analysis_service.bc_config import BcBestPracticesConfig, BcRule
    bc = BcBestPracticesConfig(
        version="1.0", page_type_priority={},
        universal_rules={"linking": [BcRule(check="has_minimum_one_internal_link", priority="high")]},
        page_types={},
    )
    er = ExtractionResult()
    er.links.internal_links = 5
    result = score_content_best_practices_l2(er, PageType.OTHER, bc)
    assert "has_minimum_one_internal_link" in result.passed


def test_score_l2_verifiable_fail_in_failed_list() -> None:
    from analysis_service.bc_config import BcBestPracticesConfig, BcRule
    bc = BcBestPracticesConfig(
        version="1.0", page_type_priority={},
        universal_rules={"linking": [BcRule(check="has_minimum_one_internal_link", priority="high")]},
        page_types={},
    )
    er = ExtractionResult()
    result = score_content_best_practices_l2(er, PageType.OTHER, bc)
    assert "has_minimum_one_internal_link" in result.failed


def test_score_l2_not_verifiable_in_not_verifiable_list() -> None:
    from analysis_service.bc_config import BcBestPracticesConfig, BcRule
    bc = BcBestPracticesConfig(
        version="1.0", page_type_priority={},
        universal_rules={"cta": [BcRule(check="cta_above_fold", priority="critical")]},
        page_types={},
    )
    result = score_content_best_practices_l2(ExtractionResult(), PageType.OTHER, bc)
    nv_names = [nv.check_name for nv in result.not_verifiable]
    assert "cta_above_fold" in nv_names
    nv = next(nv for nv in result.not_verifiable if nv.check_name == "cta_above_fold")
    assert "HTML" in nv.reason


def test_score_l2_not_verifiable_excluded_from_denominator() -> None:
    from analysis_service.bc_config import BcBestPracticesConfig, BcRule
    bc = BcBestPracticesConfig(
        version="1.0", page_type_priority={},
        universal_rules={
            "linking": [BcRule(check="has_minimum_one_internal_link", priority="high")],
            "cta": [BcRule(check="cta_above_fold", priority="critical")],
        },
        page_types={},
    )
    er = ExtractionResult()
    er.links.internal_links = 5
    result = score_content_best_practices_l2(er, PageType.OTHER, bc)
    assert result.l2_score == 100.0
    assert len(result.passed) == 1
    assert len(result.not_verifiable) == 1


def test_score_l2_formula() -> None:
    from analysis_service.bc_config import BcBestPracticesConfig, BcRule
    bc = BcBestPracticesConfig(
        version="1.0", page_type_priority={},
        universal_rules={
            "a": [BcRule(check="has_minimum_one_internal_link", priority="high")],
            "b": [BcRule(check="has_toc", priority="medium")],
        },
        page_types={},
    )
    er = ExtractionResult()
    er.links.internal_links = 5
    result = score_content_best_practices_l2(er, PageType.OTHER, bc)
    assert result.l2_score == 50.0


def test_score_l2_all_not_verifiable_score_100() -> None:
    from analysis_service.bc_config import BcBestPracticesConfig, BcRule
    bc = BcBestPracticesConfig(
        version="1.0", page_type_priority={},
        universal_rules={
            "cta": [
                BcRule(check="cta_above_fold", priority="critical"),
                BcRule(check="content_recently_updated", priority="medium"),
            ],
        },
        page_types={},
    )
    result = score_content_best_practices_l2(ExtractionResult(), PageType.OTHER, bc)
    assert result.l2_score == 100.0


def test_score_l2_rules_applied_covers_all() -> None:
    from analysis_service.bc_config import BcBestPracticesConfig, BcRule
    bc = BcBestPracticesConfig(
        version="1.0", page_type_priority={},
        universal_rules={
            "a": [BcRule(check="has_toc", priority="high")],
            "b": [BcRule(check="cta_above_fold", priority="critical")],
        },
        page_types={},
    )
    result = score_content_best_practices_l2(ExtractionResult(), PageType.OTHER, bc)
    assert len(result.rules_applied) == 2


def test_score_l2_has_toc_pass() -> None:
    from analysis_service.bc_config import BcBestPracticesConfig, BcRule
    bc = BcBestPracticesConfig(
        version="1.0", page_type_priority={},
        universal_rules={"nav": [BcRule(check="has_toc", priority="high")]},
        page_types={},
    )
    er = ExtractionResult()
    er.toc.has_toc = True
    result = score_content_best_practices_l2(er, PageType.OTHER, bc)
    assert "has_toc" in result.passed


def test_score_l2_has_toc_fail() -> None:
    from analysis_service.bc_config import BcBestPracticesConfig, BcRule
    bc = BcBestPracticesConfig(
        version="1.0", page_type_priority={},
        universal_rules={"nav": [BcRule(check="has_toc", priority="high")]},
        page_types={},
    )
    result = score_content_best_practices_l2(ExtractionResult(), PageType.OTHER, bc)
    assert "has_toc" in result.failed


def test_score_l2_with_real_bc_yaml() -> None:
    from analysis_service.bc_config import load_bc_config
    bc = load_bc_config("config/bc_best_practices.yaml")
    er = ExtractionResult()
    er.toc.has_toc = True
    er.links.internal_links = 10
    result = score_content_best_practices_l2(er, PageType.CODE_PAGE, bc)
    assert result.l2_score is not None
    assert len(result.rules_applied) > 0
    assert len(result.passed) + len(result.failed) + len(result.not_verifiable) > 0
