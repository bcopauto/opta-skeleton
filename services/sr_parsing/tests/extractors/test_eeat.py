"""Tests for the E-E-A-T signal extractor."""
from __future__ import annotations

import pytest
from selectolax.parser import HTMLParser

from scraper_service.extractors.eeat import extract


def _tree(html: str) -> HTMLParser:
    return HTMLParser(html)


URL = "https://example.com/article"


class TestAuthorByline:
    def test_author_by_class(self) -> None:
        html = '<html><body><span class="author">John Doe</span></body></html>'
        result = extract(_tree(html), URL)
        assert result["author_name"] == "John Doe"
        assert result["author_byline_found"] is True

    def test_author_by_id(self) -> None:
        html = '<html><body><div id="byline">Jane Smith</div></body></html>'
        result = extract(_tree(html), URL)
        assert result["author_name"] == "Jane Smith"
        assert result["author_byline_found"] is True

    def test_author_via_rel(self) -> None:
        html = '<html><body><a rel="author" href="/john">John Doe</a></body></html>'
        result = extract(_tree(html), URL)
        assert result["author_name"] == "John Doe"
        assert result["author_byline_found"] is True

    def test_author_via_meta(self) -> None:
        html = '<html><head><meta name="author" content="Jane Smith"></head><body></body></html>'
        result = extract(_tree(html), URL)
        assert result["author_name"] == "Jane Smith"
        assert result["author_byline_found"] is True

    def test_no_author(self) -> None:
        html = "<html><body><p>No author info here.</p></body></html>"
        result = extract(_tree(html), URL)
        assert result["author_name"] is None
        assert result["author_byline_found"] is False


class TestReviewedBy:
    def test_reviewed_by(self) -> None:
        html = '<html><body><article><p>Reviewed by Dr. Sarah Wilson</p></article></body></html>'
        result = extract(_tree(html), URL)
        assert result["reviewed_by_found"] is True
        assert "Sarah Wilson" in result["reviewed_by"]

    def test_fact_checked_by(self) -> None:
        html = '<html><body><article><p>Fact-checked by Mark Johnson, PhD</p></article></body></html>'
        result = extract(_tree(html), URL)
        assert result["reviewed_by_found"] is True
        assert "Mark Johnson" in result["reviewed_by"]

    def test_medically_reviewed(self) -> None:
        html = '<html><body><article><p>Medically reviewed by Dr. Alice Brown</p></article></body></html>'
        result = extract(_tree(html), URL)
        assert result["reviewed_by_found"] is True

    def test_no_reviewed_by(self) -> None:
        html = "<html><body><article><p>Just a normal article.</p></article></body></html>"
        result = extract(_tree(html), URL)
        assert result["reviewed_by_found"] is False
        assert result["reviewed_by"] is None


class TestAuthorBio:
    def test_author_bio_section(self) -> None:
        html = '<html><body><div class="author-bio">Expert in SEO with 10 years of experience in digital marketing.</div></body></html>'
        result = extract(_tree(html), URL)
        assert result["author_bio_found"] is True
        assert result["author_bio_text"] is not None
        assert "SEO" in result["author_bio_text"]

    def test_about_author_section(self) -> None:
        html = '<html><body><section class="about-author">John is a certified professional.</section></body></html>'
        result = extract(_tree(html), URL)
        assert result["author_bio_found"] is True

    def test_no_bio(self) -> None:
        html = "<html><body><p>Regular content.</p></body></html>"
        result = extract(_tree(html), URL)
        assert result["author_bio_found"] is False
        assert result["author_bio_text"] is None


class TestContactLinks:
    def test_contact_page_link(self) -> None:
        html = '<html><body><a href="/contact">Contact Us</a></body></html>'
        result = extract(_tree(html), URL)
        assert result["contact_page_linked"] is True

    def test_about_page_link(self) -> None:
        html = '<html><body><a href="/about-us">About</a></body></html>'
        result = extract(_tree(html), URL)
        assert result["about_page_linked"] is True

    def test_email_visible(self) -> None:
        html = '<html><body><a href="mailto:info@example.com">Email us</a></body></html>'
        result = extract(_tree(html), URL)
        assert result["email_visible"] is True

    def test_no_contact_info(self) -> None:
        html = "<html><body><p>No contact links.</p></body></html>"
        result = extract(_tree(html), URL)
        assert result["contact_page_linked"] is False
        assert result["about_page_linked"] is False
        assert result["email_visible"] is False


class TestCitations:
    def test_external_citations_in_article(self) -> None:
        html = """<html><body><article>
            <a href="https://harvard.edu/study">Source 1</a>
            <a href="https://cdc.gov/report">Source 2</a>
            <a href="https://example.org/ref">Source 3</a>
        </article></body></html>"""
        result = extract(_tree(html), URL)
        assert result["citation_count"] >= 3
        assert result["authoritative_citations"] >= 2  # .edu and .gov

    def test_no_citations(self) -> None:
        html = "<html><body><article><p>No links at all.</p></article></body></html>"
        result = extract(_tree(html), URL)
        assert result["citation_count"] == 0
        assert result["authoritative_citations"] == 0


class TestExpertiseSignals:
    def test_phd_credential(self) -> None:
        html = '<html><body><span class="author">Dr. Smith, PhD</span></body></html>'
        result = extract(_tree(html), URL)
        assert "PhD" in result["expertise_signals"]

    def test_md_credential(self) -> None:
        html = '<html><body><span class="author">Dr. Jones, MD</span></body></html>'
        result = extract(_tree(html), URL)
        assert any("MD" in s for s in result["expertise_signals"])

    def test_no_credentials(self) -> None:
        html = '<html><body><span class="author">John Doe</span></body></html>'
        result = extract(_tree(html), URL)
        assert result["expertise_signals"] == []


class TestTrustSignals:
    def test_multiple_trust_signals(self) -> None:
        html = """<html><body>
            <span class="author">Dr. Smith, PhD</span>
            <div class="author-bio">Expert in field for 20 years.</div>
            <a href="/contact">Contact</a>
            <a href="/about">About</a>
            <a href="mailto:info@example.com">Email</a>
        </body></html>"""
        result = extract(_tree(html), URL)
        assert result["trust_signals_count"] >= 4


class TestEdgeCases:
    def test_empty_page(self) -> None:
        result = extract(_tree("<html><body></body></html>"), URL)
        assert result["author_name"] is None
        assert result["author_byline_found"] is False
        assert result["reviewed_by_found"] is False
        assert result["trust_signals_count"] == 0

    def test_garbage_html_never_raises(self) -> None:
        result = extract(_tree("<<<garbage>>>"), URL)
        assert isinstance(result, dict)
        assert "author_name" in result
        assert "trust_signals_count" in result
