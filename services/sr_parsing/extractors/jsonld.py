"""Extract JSON-LD blocks, Microdata, and RDFa structured data (EXTR-13)."""
from __future__ import annotations

import json

from selectolax.parser import HTMLParser

# Schema.org type sets for high-value detection
_ARTICLE_TYPES = {
    "article", "newsarticle", "blogposting", "technicalarticle",
    "scholarlyarticle", "report",
}
_LOCAL_TYPES = {
    "localbusiness", "restaurant", "store", "hotel",
    "medicalorganization", "dentist", "physician",
}


def _collect_types(obj: object, found: list[str]) -> None:
    """Recursively collect all @type values from a JSON-LD object or array."""
    if isinstance(obj, list):
        for item in obj:
            _collect_types(item, found)
    elif isinstance(obj, dict):
        raw = obj.get("@type")
        if isinstance(raw, list):
            found.extend(t.lower() for t in raw if isinstance(t, str))
        elif isinstance(raw, str):
            found.append(raw.lower())
        for val in obj.values():
            if isinstance(val, (dict, list)):
                _collect_types(val, found)


def _parse_jsonld(tree: HTMLParser) -> tuple[list[str], list[dict]]:
    """Extract JSON-LD types and raw blocks from script tags."""
    types: list[str] = []
    blocks: list[dict] = []

    for script in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.text())
            blocks.append(data)
            _collect_types(data, types)
        except (json.JSONDecodeError, TypeError):
            pass

    return types, blocks


def _microdata_types(html: str) -> list[str]:
    """Extract Microdata itemtype values using BS4 (fallback parser)."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        return [
            (t.get("itemtype") or "").split("/")[-1].lower()
            for t in soup.find_all(attrs={"itemscope": True})
            if t.get("itemtype")
        ]
    except Exception:
        return []


def _rdfa_types(html: str) -> list[str]:
    """Extract RDFa typeof values using BS4 (fallback parser)."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        return [
            (t.get("typeof") or "").lower()
            for t in soup.find_all(attrs={"typeof": True})
            if t.get("typeof")
        ]
    except Exception:
        return []


def _extract_detail(blocks: list[dict], schema_type: str) -> dict | None:
    """Extract a specific schema type detail from JSON-LD blocks."""
    for block in blocks:
        items = block if isinstance(block, list) else [block]
        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = (item.get("@type") or "").lower()
            if item_type == schema_type:
                return item
    return None


def extract(tree: HTMLParser, url: str) -> dict:
    """Extract all structured data: JSON-LD, Microdata, RDFa. Never raises."""
    try:
        # JSON-LD
        jsonld_types, blocks = _parse_jsonld(tree)

        # Microdata and RDFa (use BS4 fallback)
        html_raw = tree.html
        microdata_types = _microdata_types(html_raw)
        rdfa_types = _rdfa_types(html_raw)

        all_types = set(jsonld_types + microdata_types + rdfa_types)

        def has(*names: str) -> bool:
            return bool(all_types & set(names))

        # Breadcrumb items
        breadcrumb_items: int | None = None
        breadcrumb_data = _extract_detail(blocks, "breadcrumblist")
        if breadcrumb_data:
            elem = breadcrumb_data.get("itemListElement") or []
            breadcrumb_items = len(elem)

        # FAQ count
        faq_count: int | None = None
        faq_data = _extract_detail(blocks, "faqpage")
        if faq_data:
            faq_count = len(faq_data.get("mainEntity") or [])

        # HowTo steps
        howto_steps: int | None = None
        howto_data = _extract_detail(blocks, "howto")
        if howto_data:
            howto_steps = len(howto_data.get("step") or [])

        # Recipe info
        recipe_info = None
        recipe_data = _extract_detail(blocks, "recipe")
        if recipe_data:
            recipe_info = {
                "name": recipe_data.get("name"),
                "cook_time": recipe_data.get("cookTime"),
                "recipe_yield": recipe_data.get("recipeYield"),
            }

        return {
            "jsonld_present": len(jsonld_types) > 0,
            "jsonld_count": len(blocks),
            "jsonld_types": sorted(set(jsonld_types)),
            "jsonld_blocks": blocks,
            "microdata_present": bool(microdata_types),
            "microdata_types": sorted(set(microdata_types)),
            "rdfa_present": bool(rdfa_types),
            "rdfa_types": sorted(set(rdfa_types)),
            "all_schema_types": sorted(all_types),

            # High-value schema flags
            "has_breadcrumb": has("breadcrumblist"),
            "breadcrumb_items": breadcrumb_items,
            "has_faq": has("faqpage"),
            "faq_count": faq_count,
            "has_howto": has("howto"),
            "howto_steps": howto_steps,
            "has_article": bool(all_types & _ARTICLE_TYPES),
            "has_product": has("product"),
            "has_review": has("review"),
            "has_aggregate_rating": has("aggregaterating"),
            "has_organization": has("organization"),
            "has_local_business": bool(all_types & _LOCAL_TYPES),
            "has_event": has("event"),
            "has_recipe": has("recipe"),
            "recipe_info": recipe_info,
            "has_video_object": has("videoobject"),
            "has_person": has("person"),
            "has_website": has("website"),
            "has_sitelinks_searchbox": has("searchaction"),
            "has_speakable": has("speakable"),
            "has_course": has("course"),
            "has_job_posting": has("jobposting"),
            "has_software_app": has("softwareapplication", "mobileapplication"),
            "has_medical": has("medicalcondition", "medicalwebpage", "drug"),
        }
    except Exception:
        return _empty()


def _empty() -> dict:
    return {
        "jsonld_present": False, "jsonld_count": 0,
        "jsonld_types": [], "jsonld_blocks": [],
        "microdata_present": False, "microdata_types": [],
        "rdfa_present": False, "rdfa_types": [],
        "all_schema_types": [],
        "has_breadcrumb": False, "breadcrumb_items": None,
        "has_faq": False, "faq_count": None,
        "has_howto": False, "howto_steps": None,
        "has_article": False, "has_product": False,
        "has_review": False, "has_aggregate_rating": False,
        "has_organization": False, "has_local_business": False,
        "has_event": False, "has_recipe": False,
        "recipe_info": None,
        "has_video_object": False, "has_person": False,
        "has_website": False, "has_sitelinks_searchbox": False,
        "has_speakable": False, "has_course": False,
        "has_job_posting": False, "has_software_app": False,
        "has_medical": False,
    }
