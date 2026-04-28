"""Extraction runner: parses HTML once, runs all 18 extractors, returns ExtractionResult."""
from __future__ import annotations

import logging

from selectolax.parser import HTMLParser

from scraper_service.extractors import (
    body_text,
    callout_boxes,
    comparison_tables,
    eeat,
    faq,
    freshness,
    headings,
    images,
    jsonld,
    links,
    lists,
    meta,
    meta_desc,
    pagination,
    step_by_step,
    tables,
    technical,
    title,
    toc,
    videos,
)
from scraper_service.models import ExtractionResult

logger = logging.getLogger(__name__)

EXTRACTOR_NAMES: list[str] = [
    "title",
    "meta_desc",
    "headings",
    "body_text",
    "tables",
    "lists",
    "faq",
    "videos",
    "toc",
    "comparison_tables",
    "callout_boxes",
    "step_by_step",
    "jsonld",
    "images",
    "links",
    "technical",
    "pagination",
    "meta",
    "freshness",
    "eeat",
]

_EXTRACTORS = [
    ("title", title.extract),
    ("meta_desc", meta_desc.extract),
    ("headings", headings.extract),
    ("body_text", body_text.extract),
    ("tables", tables.extract),
    ("lists", lists.extract),
    ("faq", faq.extract),
    ("videos", videos.extract),
    ("toc", toc.extract),
    ("comparison_tables", comparison_tables.extract),
    ("callout_boxes", callout_boxes.extract),
    ("step_by_step", step_by_step.extract),
    ("jsonld", jsonld.extract),
    ("images", images.extract),
    ("links", links.extract),
    ("technical", technical.extract),
    ("pagination", pagination.extract),
    ("meta", meta.extract),
    ("freshness", freshness.extract),
    ("eeat", eeat.extract),
]


def extract_page(
    html: str,
    url: str,
    response_headers: dict[str, str] | None = None,
) -> ExtractionResult:
    """Parse HTML once with selectolax, run all extractors, return ExtractionResult.

    Per D-02: HTML is parsed once with selectolax. Extractors needing BS4 create their own.
    Per D-10: Extractor failures are isolated -- partial results returned with _error key.
    Per D-11: Warning-level log on each extractor failure.

    Extractors that declare a module-level ``WANTS_HEADERS = True`` receive
    *response_headers* as an extra keyword argument.
    """
    import sys

    tree = HTMLParser(html)
    results: dict[str, dict] = {}

    for name, extract_fn in _EXTRACTORS:
        try:
            mod = sys.modules.get(extract_fn.__module__)
            if response_headers and mod and getattr(mod, "WANTS_HEADERS", False):
                results[name] = extract_fn(tree, url, response_headers=response_headers)
            else:
                results[name] = extract_fn(tree, url)
        except Exception as exc:
            logger.warning("extractor %s failed for %s: %s", name, url, exc)
            results[name] = {"_error": str(exc)}

    return ExtractionResult.from_extraction_results(results)
