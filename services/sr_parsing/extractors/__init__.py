"""Extraction pipeline: 20 pure-function extractor modules and the extract_page runner."""
from scraper_service.extractors.runner import EXTRACTOR_NAMES, extract_page

__all__ = ["EXTRACTOR_NAMES", "extract_page"]
