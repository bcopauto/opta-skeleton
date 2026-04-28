"""Tests for structlog logging configuration and correlation IDs."""

from __future__ import annotations

import json
import uuid
from io import StringIO

import structlog

from scraper_service.logging import bind_correlation_id, configure_logging, get_logger


def test_configure_logging_sets_json_renderer() -> None:
    """Call configure_logging(), get a logger, capture output, verify it is valid JSON with keys "timestamp", "level", "event"."""
    configure_logging()

    # Capture stdout where PrintLoggerFactory writes
    log = get_logger()
    output = StringIO()
    import sys
    old_stdout = sys.stdout
    sys.stdout = output

    try:
        log.info("test_message")
        sys.stdout.flush()
    finally:
        sys.stdout = old_stdout

    # Parse the JSON output
    log_line = output.getvalue().strip()
    log_entry = json.loads(log_line)

    assert "timestamp" in log_entry
    assert "level" in log_entry or "log_level" in log_entry
    assert "event" in log_entry
    assert log_entry["event"] == "test_message"


def test_bind_correlation_id_generates_uuid() -> None:
    """Call bind_correlation_id() with no args, then log a message, verify "correlation_id" key exists in JSON output and value is a valid UUID."""
    configure_logging()

    log = get_logger()
    output = StringIO()
    import sys
    old_stdout = sys.stdout
    sys.stdout = output

    try:
        cid = bind_correlation_id()
        log.info("test_message")
        sys.stdout.flush()
    finally:
        sys.stdout = old_stdout

    log_line = output.getvalue().strip()
    log_entry = json.loads(log_line)

    assert "correlation_id" in log_entry
    # Verify it's a valid UUID
    uuid.UUID(log_entry["correlation_id"])
    assert log_entry["correlation_id"] == cid


def test_bind_correlation_id_uses_provided_id() -> None:
    """Call bind_correlation_id("test-job-123"), log a message, verify correlation_id == "test-job-123"."""
    configure_logging()

    log = get_logger()
    output = StringIO()
    import sys
    old_stdout = sys.stdout
    sys.stdout = output

    try:
        cid = bind_correlation_id("test-job-123")
        log.info("test_message")
        sys.stdout.flush()
    finally:
        sys.stdout = old_stdout

    log_line = output.getvalue().strip()
    log_entry = json.loads(log_line)

    assert log_entry["correlation_id"] == "test-job-123"
    assert cid == "test-job-123"


def test_correlation_id_per_context() -> None:
    """Bind correlation_id "aaa", capture log. Bind "bbb", capture log. Verify each has its own ID."""
    configure_logging()

    log = get_logger()
    output = StringIO()
    import sys
    old_stdout = sys.stdout
    sys.stdout = output

    try:
        bind_correlation_id("aaa")
        log.info("first_message")
        bind_correlation_id("bbb")
        log.info("second_message")
        sys.stdout.flush()
    finally:
        sys.stdout = old_stdout

    log_lines = output.getvalue().strip().split("\n")
    assert len(log_lines) == 2

    log_entry1 = json.loads(log_lines[0])
    log_entry2 = json.loads(log_lines[1])

    assert log_entry1["correlation_id"] == "aaa"
    assert log_entry2["correlation_id"] == "bbb"


def test_log_output_has_required_fields() -> None:
    """Log info("fetch_started", url="https://example.com", duration_ms=150, status_code=200). Verify JSON output has timestamp (ISO format), level ("info"), event ("fetch_started"), url, duration_ms, status_code."""
    configure_logging()

    log = get_logger()
    output = StringIO()
    import sys
    old_stdout = sys.stdout
    sys.stdout = output

    try:
        log.info("fetch_started", url="https://example.com", duration_ms=150, status_code=200)
        sys.stdout.flush()
    finally:
        sys.stdout = old_stdout

    log_line = output.getvalue().strip()
    log_entry = json.loads(log_line)

    assert "timestamp" in log_entry
    # Verify ISO format timestamp (contains 'T' and colons)
    assert "T" in log_entry["timestamp"]
    assert ":" in log_entry["timestamp"]
    assert log_entry.get("level") == "info" or log_entry.get("log_level") == "info"
    assert log_entry["event"] == "fetch_started"
    assert log_entry["url"] == "https://example.com"
    assert log_entry["duration_ms"] == 150
    assert log_entry["status_code"] == 200


def test_clear_contextvars_on_bind() -> None:
    """Bind "first-id", bind "second-id", verify correlation_id is "second-id" (no leak from first)."""
    configure_logging()

    log = get_logger()
    output = StringIO()
    import sys
    old_stdout = sys.stdout
    sys.stdout = output

    try:
        bind_correlation_id("first-id")
        log.info("first_message")
        bind_correlation_id("second-id")
        log.info("second_message")
        sys.stdout.flush()
    finally:
        sys.stdout = old_stdout

    log_lines = output.getvalue().strip().split("\n")
    assert len(log_lines) == 2

    log_entry1 = json.loads(log_lines[0])
    log_entry2 = json.loads(log_lines[1])

    assert log_entry1["correlation_id"] == "first-id"
    # After binding second-id, logs should only have second-id
    assert log_entry2["correlation_id"] == "second-id"
