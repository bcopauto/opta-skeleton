"""Detect FAQ patterns: FAQPage schema, details/summary, Q/A classes, headings ending in ? (EXTR-07)."""
from __future__ import annotations

import json

from selectolax.parser import HTMLParser


def extract(tree: HTMLParser, url: str) -> dict:
    """Detect FAQ patterns. Checks schema, details/summary, class names, heading questions. Never raises."""
    try:
        # Pattern 1: FAQPage JSON-LD schema
        faq_schema_count = 0
        faq_schema_questions: list[str] = []
        for script in tree.css('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.text())
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if (item.get("@type") or "").lower() == "faqpage":
                        faq_schema_count += 1
                        for entity in (item.get("mainEntity") or []):
                            name = entity.get("name") or ""
                            if name:
                                faq_schema_questions.append(name)
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        # Pattern 2: <details>/<summary> elements
        details_elements = tree.css("details")
        details_questions: list[str] = []
        for details in details_elements:
            summary = details.css_first("summary")
            if summary:
                text = summary.text().strip()
                if text:
                    details_questions.append(text)

        # Pattern 3: Common Q/A class names
        qa_selectors = [
            '[class*="faq"]', '[class*="question"]', '[class*="accordion"]',
            '[class*="q-and-a"]', '[class*="qna"]',
        ]
        class_questions: list[str] = []
        for selector in qa_selectors:
            for el in tree.css(selector):
                text = el.text().strip()
                if text and len(text) < 300:
                    class_questions.append(text)

        # Pattern 4: Headings ending in ?
        heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
        question_headings: list[str] = []
        body = tree.body
        if body:
            for node in body.traverse():
                if node.tag in heading_tags:
                    text = node.text().strip()
                    if text.endswith("?"):
                        question_headings.append(text)

        has_faq = bool(faq_schema_questions or details_questions or class_questions or question_headings)

        return {
            "has_faq": has_faq,
            "faq_schema_count": faq_schema_count,
            "faq_schema_questions": faq_schema_questions,
            "details_count": len(details_elements),
            "details_questions": details_questions,
            "class_based_questions": class_questions[:20],
            "question_headings": question_headings,
            "total_faq_items": (
                len(faq_schema_questions)
                + len(details_questions)
                + min(len(class_questions), 20)
                + len(question_headings)
            ),
        }
    except Exception:
        return _empty()


def _empty() -> dict:
    return {
        "has_faq": False, "faq_schema_count": 0,
        "faq_schema_questions": [], "details_count": 0,
        "details_questions": [], "class_based_questions": [],
        "question_headings": [], "total_faq_items": 0,
    }
