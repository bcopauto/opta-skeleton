from __future__ import annotations

import re
from typing import Callable

from analysis_service.bc_config import BcBestPracticesConfig, BcPageTypeConfig
from analysis_service.models import (
    ContentBestPracticesResult,
    ExtractionResult,
    L2NotVerifiable,
    L2RuleResult,
    PageType,
)

_PAGE_TYPE_YAML_KEY: dict[str, str] = {
    "code_page": "code_page",
    "registration_page": "registration_page",
    "comparator": "comparator_page",
    "operator_review": "review_page",
    "app_page": "app_page",
    "betting_casino_guide": "guide",
    "timely_content": "timely_content",
    "other": "",
}

_MONTH_YEAR_RE = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b.*\b\d{4}\b"
    r"|\b\d{4}\b.*\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.IGNORECASE,
)

_RG_KEYWORDS = ("responsible gambling", "18+", "gamble responsibly", "gamble aware", "gambleaware")
_TC_KEYWORDS = ("terms and conditions", "terms & conditions", "t&c")


def _check_has_hreflang_tags(er: ExtractionResult) -> tuple[bool, str]:
    ok = er.meta.hreflang_count > 0
    return ok, f"hreflang count: {er.meta.hreflang_count}"


def _check_has_real_author(er: ExtractionResult) -> tuple[bool, str]:
    ok = er.eeat.author_name is not None and len(er.eeat.author_name.strip()) > 0
    return ok, f"author: {er.eeat.author_name or '(none)'}"


def _check_has_visible_dates(er: ExtractionResult) -> tuple[bool, str]:
    ok = er.freshness.published_date is not None or er.freshness.modified_date is not None
    return ok, f"published={er.freshness.published_date}, modified={er.freshness.modified_date}"


def _check_has_breadcrumb_navigation(er: ExtractionResult) -> tuple[bool, str]:
    return er.jsonld.has_breadcrumb, "breadcrumb schema present" if er.jsonld.has_breadcrumb else "no breadcrumb"


def _check_no_betting_expert_mention(er: ExtractionResult) -> tuple[bool, str]:
    text = (er.body_text.text or "").lower()
    ok = "betting expert" not in text
    return ok, "no 'betting expert' mention" if ok else "'betting expert' found in body text"


def _check_has_recent_date(er: ExtractionResult) -> tuple[bool, str]:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=365)
    for raw in (er.freshness.modified_date, er.freshness.published_date):
        if raw is None:
            continue
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt >= cutoff:
                return True, f"recent date: {raw}"
        except (ValueError, TypeError):
            continue
    if er.freshness.published_date is None and er.freshness.modified_date is None:
        return False, "no date found"
    return False, "dates found but older than 1 year"


def _check_has_minimum_one_internal_link(er: ExtractionResult) -> tuple[bool, str]:
    ok = er.links.internal_links > 0
    return ok, f"internal links: {er.links.internal_links}"


def _check_has_responsible_gambling(er: ExtractionResult) -> tuple[bool, str]:
    text = (er.body_text.text or "").lower()
    found = any(kw in text for kw in _RG_KEYWORDS)
    return found, "RG keywords found" if found else "no responsible gambling keywords"


def _check_has_visible_terms_conditions(er: ExtractionResult) -> tuple[bool, str]:
    text = (er.body_text.text or "").lower()
    found = any(kw in text for kw in _TC_KEYWORDS)
    return found, "T&C keywords found" if found else "no terms and conditions keywords"


def _check_has_toc(er: ExtractionResult) -> tuple[bool, str]:
    return er.toc.has_toc, "TOC present" if er.toc.has_toc else "no TOC"


def _check_has_faq_section(er: ExtractionResult) -> tuple[bool, str]:
    return er.faq.has_faq, "FAQ present" if er.faq.has_faq else "no FAQ"


def _check_has_h1(er: ExtractionResult) -> tuple[bool, str]:
    ok = er.headings.h1_count >= 1
    return ok, f"h1 count: {er.headings.h1_count}"


def _check_has_minimum_two_tables(er: ExtractionResult) -> tuple[bool, str]:
    ok = er.tables.table_count >= 2
    return ok, f"table count: {er.tables.table_count}"


def _check_has_short_intro(er: ExtractionResult) -> tuple[bool, str]:
    ok = er.body_text.word_count > 0
    return ok, f"word count: {er.body_text.word_count}"


def _check_h1_contains_code_month_year(er: ExtractionResult) -> tuple[bool, str]:
    if not er.headings.h1_texts:
        return False, "no H1 text"
    h1 = er.headings.h1_texts[0]
    ok = bool(_MONTH_YEAR_RE.search(h1))
    return ok, f"H1: {h1[:60]}"


def _check_schema_faqpage(er: ExtractionResult) -> tuple[bool, str]:
    return er.jsonld.has_faq, "FAQPage schema present" if er.jsonld.has_faq else "no FAQPage schema"


def _check_schema_article(er: ExtractionResult) -> tuple[bool, str]:
    return er.jsonld.has_article, "Article schema present" if er.jsonld.has_article else "no Article schema"


def _check_schema_breadcrumb(er: ExtractionResult) -> tuple[bool, str]:
    return er.jsonld.has_breadcrumb, "BreadcrumbList present" if er.jsonld.has_breadcrumb else "no BreadcrumbList"


def _check_schema_howto(er: ExtractionResult) -> tuple[bool, str]:
    return er.jsonld.has_howto, "HowTo schema present" if er.jsonld.has_howto else "no HowTo schema"


def _check_schema_review(er: ExtractionResult) -> tuple[bool, str]:
    return er.jsonld.has_review, "Review schema present" if er.jsonld.has_review else "no Review schema"


def _check_schema_organization(er: ExtractionResult) -> tuple[bool, str]:
    return er.jsonld.has_organization, "Organization present" if er.jsonld.has_organization else "no Organization"


def _check_schema_software_application(er: ExtractionResult) -> tuple[bool, str]:
    return er.jsonld.has_software_app, "SoftwareApplication present" if er.jsonld.has_software_app else "no SoftwareApplication"


def _check_schema_newsarticle(er: ExtractionResult) -> tuple[bool, str]:
    ok = "NewsArticle" in er.jsonld.jsonld_types
    return ok, "NewsArticle present" if ok else "no NewsArticle"


def _check_schema_itemlist(er: ExtractionResult) -> tuple[bool, str]:
    ok = "ItemList" in er.jsonld.jsonld_types
    return ok, "ItemList present" if ok else "no ItemList"


def _check_schema_webpage(er: ExtractionResult) -> tuple[bool, str]:
    ok = er.jsonld.has_website or "WebPage" in er.jsonld.jsonld_types
    return ok, "WebPage/WebSite present" if ok else "no WebPage"


def _check_serp_faq_present(er: ExtractionResult) -> tuple[bool, str]:
    return er.faq.has_faq, "FAQ present" if er.faq.has_faq else "no FAQ"


def _check_serp_toc_present(er: ExtractionResult) -> tuple[bool, str]:
    return er.toc.has_toc, "TOC present" if er.toc.has_toc else "no TOC"


_VERIFIABLE_CHECKS: dict[str, Callable[[ExtractionResult], tuple[bool, str]]] = {
    "has_hreflang_tags": _check_has_hreflang_tags,
    "has_real_author": _check_has_real_author,
    "has_visible_dates": _check_has_visible_dates,
    "has_breadcrumb_navigation": _check_has_breadcrumb_navigation,
    "no_betting_expert_mention": _check_no_betting_expert_mention,
    "has_recent_date": _check_has_recent_date,
    "has_minimum_one_internal_link": _check_has_minimum_one_internal_link,
    "has_responsible_gambling": _check_has_responsible_gambling,
    "has_visible_terms_conditions": _check_has_visible_terms_conditions,
    "has_toc": _check_has_toc,
    "has_faq_section": _check_has_faq_section,
    "has_h1": _check_has_h1,
    "has_minimum_two_tables": _check_has_minimum_two_tables,
    "has_short_intro": _check_has_short_intro,
    "h1_contains_code_month_year": _check_h1_contains_code_month_year,
    "schema_faqpage": _check_schema_faqpage,
    "schema_article": _check_schema_article,
    "schema_breadcrumb": _check_schema_breadcrumb,
    "schema_howto": _check_schema_howto,
    "schema_review": _check_schema_review,
    "schema_organization": _check_schema_organization,
    "schema_software_application": _check_schema_software_application,
    "schema_newsarticle": _check_schema_newsarticle,
    "schema_itemlist": _check_schema_itemlist,
    "schema_webpage": _check_schema_webpage,
    "serp_faq_present": _check_serp_faq_present,
    "serp_toc_present": _check_serp_toc_present,
}

_NOT_VERIFIABLE_HTML: frozenset[str] = frozenset({
    "cta_above_fold", "cta_above_fold_register", "has_bold_key_info",
    "cta_uses_plural", "code_via_search_module", "code_selectable_on_click",
    "cta_hidden_format_distinct", "code_displayed_clean",
    "referral_code_in_title_with_verb", "has_code_image",
    "has_images_with_code_screenshot", "has_short_intro_with_code",
    "code_in_first_paragraph", "code_visible_in_serp_title",
    "meta_title_has_code_year_month", "fast_info_access",
    "direct_writing_style", "rich_semantic_vocabulary",
    "anchor_is_natural", "anchor_in_sentence_context",
    "prefer_body_links", "prefer_contextual_links", "link_context_relevance",
})

_NOT_VERIFIABLE_EXTERNAL: frozenset[str] = frozenset({
    "content_recently_updated", "site_has_about_page", "site_has_contact_page",
    "commercial_page_monthly_republish", "links_present_at_publish",
    "hreflang_cross_market_linked", "cocoon_interlinking_complete",
    "no_cocoon_cannibalization", "has_customer_service_info",
    "uses_auto_date_shortcodes",
})


def _collect_applicable_rules(
    bc_config: BcBestPracticesConfig,
    page_type: PageType,
) -> list[tuple[str, str, str, str]]:
    """Collect (check_name, source, rule_text, priority) from universal + page-type rules."""
    rules: list[tuple[str, str, str, str]] = []

    for category, rule_list in bc_config.universal_rules.items():
        for rule in rule_list:
            rules.append((rule.check, f"universal/{category}", rule.rule or rule.check, rule.priority))

    yaml_key = _PAGE_TYPE_YAML_KEY.get(page_type.value, "")
    page_config: BcPageTypeConfig | None = bc_config.page_types.get(yaml_key) if yaml_key else None

    if page_config:
        for field_name, field_value in page_config:
            if isinstance(field_value, list):
                for item in field_value:
                    if hasattr(item, "check"):
                        check_name = item.check
                        rule_text = getattr(item, "rule", None) or getattr(item, "element", None) or getattr(item, "section", None) or getattr(item, "check_item", None) or check_name
                        priority = getattr(item, "priority", "medium")
                        rules.append((check_name, f"{yaml_key}/{field_name}", rule_text, priority))

    return rules


def score_content_best_practices_l2(
    target: ExtractionResult,
    page_type: PageType,
    bc_config: BcBestPracticesConfig,
) -> ContentBestPracticesResult:
    applicable = _collect_applicable_rules(bc_config, page_type)

    seen: set[str] = set()
    rules_applied: list[L2RuleResult] = []
    passed_names: list[str] = []
    failed_names: list[str] = []
    not_verifiable_items: list[L2NotVerifiable] = []

    for check_name, source, rule_text, priority in applicable:
        if check_name in seen:
            continue
        seen.add(check_name)

        if check_name in _VERIFIABLE_CHECKS:
            ok, _evidence = _VERIFIABLE_CHECKS[check_name](target)
            status = "passed" if ok else "failed"
            rules_applied.append(L2RuleResult(
                check_name=check_name, source=source, rule_text=rule_text,
                priority=priority, status=status,
            ))
            if ok:
                passed_names.append(check_name)
            else:
                failed_names.append(check_name)
        elif check_name in _NOT_VERIFIABLE_HTML:
            reason = "Requires raw HTML analysis"
            rules_applied.append(L2RuleResult(
                check_name=check_name, source=source, rule_text=rule_text,
                priority=priority, status="not_verifiable", reason=reason,
            ))
            not_verifiable_items.append(L2NotVerifiable(check_name=check_name, reason=reason))
        elif check_name in _NOT_VERIFIABLE_EXTERNAL:
            reason = "Requires historical or external data"
            rules_applied.append(L2RuleResult(
                check_name=check_name, source=source, rule_text=rule_text,
                priority=priority, status="not_verifiable", reason=reason,
            ))
            not_verifiable_items.append(L2NotVerifiable(check_name=check_name, reason=reason))
        else:
            reason = "Check not implemented"
            rules_applied.append(L2RuleResult(
                check_name=check_name, source=source, rule_text=rule_text,
                priority=priority, status="not_verifiable", reason=reason,
            ))
            not_verifiable_items.append(L2NotVerifiable(check_name=check_name, reason=reason))

    passed_count = len(passed_names)
    failed_count = len(failed_names)
    denominator = passed_count + failed_count

    if denominator == 0:
        l2_score = 100.0
    else:
        l2_score = round(passed_count / denominator * 100, 1)

    return ContentBestPracticesResult(
        l2_score=l2_score,
        rules_applied=rules_applied,
        passed=passed_names,
        failed=failed_names,
        not_verifiable=not_verifiable_items,
    )
