"""Deterministic scoring modules for the analysis service.

Each module exports a single pure function that takes an ExtractionResult
(and competitors list where applicable) and returns a typed result model.
No side effects, no network calls.
"""
from __future__ import annotations
