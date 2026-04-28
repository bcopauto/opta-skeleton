"""H1 + Meta Optimization scoring module (DET-03).

Pure function: score_h1_meta_optimization(target, keyword) -> H1MetaOptimizationResult.
7-check scoring with close-variant keyword matching (D-13).
Uses ExtractionResult fields — no HTML re-parsing.
"""
from __future__ import annotations

import re
import unicodedata

from analysis_service.models import ExtractionResult, H1MetaOptimizationResult


def normalize_text(text: str) -> str:
    """Normalize text for close-variant keyword matching (D-13).

    1. Lowercase
    2. Strip Unicode accent marks (NFD decomposition, drop Mn category)
    3. Collapse whitespace
    """
    text = text.lower()
    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text


def keyword_matches(keyword: str, text: str) -> bool:
    """Return True if keyword (or close variant) appears as substring in text."""
    return normalize_text(keyword) in normalize_text(text)


def score_h1_meta_optimization(
    target: ExtractionResult,
    keyword: str,
) -> H1MetaOptimizationResult:
    """Compute H1 + Meta Optimization Score (0-100).

    Runs 7 deterministic checks. Maximum score = 20+20+15+10+10+10+15 = 100.
    """
    title_text: str = target.title.title or ""
    h1_texts: list[str] = target.headings.h1_texts
    h1_count: int = target.headings.h1_count
    h1_text: str = h1_texts[0] if h1_texts else ""
    meta_desc: str = target.meta.meta_description or ""
    first_100_words: str = " ".join(target.body_text.text.split()[:100])

    # Multiple H1 warning (D-15)
    multiple_h1_warning: str | None = None
    if h1_count > 1:
        multiple_h1_warning = (
            f"Multiple H1 tags detected ({h1_count} found) — "
            "best practice is exactly one H1."
        )

    # Check 1: Keyword in title (20 pts)
    c1 = keyword_matches(keyword, title_text) if title_text else False
    c1_pts = 20 if c1 else 0

    # Check 2: Keyword in H1 (20 pts)
    c2 = keyword_matches(keyword, h1_text) if h1_text else False
    c2_pts = 20 if c2 else 0

    # Check 3: Keyword in meta description (15 pts)
    c3 = keyword_matches(keyword, meta_desc) if meta_desc else False
    c3_pts = 15 if c3 else 0

    # Check 4: Title length 50-60 chars inclusive (10 pts)
    title_len = len(title_text)
    c4 = 50 <= title_len <= 60 if title_text else False
    c4_pts = 10 if c4 else 0

    # Check 5: Meta description length 120-160 chars inclusive (10 pts)
    meta_len = len(meta_desc)
    c5 = 120 <= meta_len <= 160 if meta_desc else False
    c5_pts = 10 if c5 else 0

    # Check 6: H1 differs from title (10 pts)
    c6 = (
        bool(h1_text and title_text)
        and normalize_text(h1_text) != normalize_text(title_text)
    )
    c6_pts = 10 if c6 else 0

    # Check 7: Keyword in first 100 words (15 pts)
    c7 = keyword_matches(keyword, first_100_words) if first_100_words else False
    c7_pts = 15 if c7 else 0

    score = float(c1_pts + c2_pts + c3_pts + c4_pts + c5_pts + c6_pts + c7_pts)

    return H1MetaOptimizationResult(
        score=score,
        keyword_in_title=c1,
        keyword_in_title_pts=c1_pts,
        keyword_in_h1=c2,
        keyword_in_h1_pts=c2_pts,
        keyword_in_meta_description=c3,
        keyword_in_meta_description_pts=c3_pts,
        title_length_ok=c4,
        title_length_pts=c4_pts,
        meta_length_ok=c5,
        meta_length_pts=c5_pts,
        h1_differs_from_title=c6,
        h1_differs_from_title_pts=c6_pts,
        keyword_in_first_100_words=c7,
        keyword_in_first_100_words_pts=c7_pts,
        multiple_h1_warning=multiple_h1_warning,
    )
