"""Shared fixtures for extractor tests."""
import pytest
from selectolax.parser import HTMLParser


@pytest.fixture
def minimal_html() -> str:
    """Bare minimum HTML with no content."""
    return "<html><head></head><body></body></html>"


@pytest.fixture
def minimal_tree(minimal_html: str) -> HTMLParser:
    return HTMLParser(minimal_html)


@pytest.fixture
def full_page_html() -> str:
    """Full page with title, meta, headings, body text, tables, lists, images, links."""
    return '''<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
    <meta charset="UTF-8">
    <title>Best SEO Tools 2025 - Complete Guide</title>
    <meta name="description" content="Comprehensive guide to SEO tools for 2025">
    <meta name="keywords" content="seo, tools, 2025">
    <meta name="author" content="Jane Doe">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#ffffff">
    <meta property="og:title" content="Best SEO Tools 2025">
    <meta property="og:description" content="Comprehensive guide to SEO tools">
    <meta property="og:image" content="https://example.com/og.jpg">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://example.com/seo-tools">
    <meta property="og:site_name" content="Example Site">
    <meta property="og:locale" content="en_US">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Best SEO Tools 2025">
    <meta name="twitter:description" content="Comprehensive guide">
    <meta name="twitter:image" content="https://example.com/twitter.jpg">
    <meta name="twitter:site" content="@example">
    <meta name="twitter:creator" content="@janedoe">
    <link rel="canonical" href="https://example.com/seo-tools">
    <meta name="robots" content="index, follow, max-snippet:200, max-image-preview:large">
    <meta name="googlebot" content="index, follow">
    <link rel="alternate" hreflang="en" href="https://example.com/seo-tools">
    <link rel="alternate" hreflang="de" href="https://example.com/de/seo-tools">
    <link rel="alternate" hreflang="x-default" href="https://example.com/seo-tools">
    <link rel="next" href="https://example.com/seo-tools?page=2">
    <link rel="icon" href="/favicon.ico">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "Best SEO Tools 2025",
        "author": {"@type": "Person", "name": "Jane Doe"},
        "datePublished": "2025-01-15"
    }
    </script>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": "What is SEO?", "acceptedAnswer": {"@type": "Answer", "text": "Search Engine Optimization"}},
            {"@type": "Question", "name": "How to start?", "acceptedAnswer": {"@type": "Answer", "text": "Begin with keyword research"}}
        ]
    }
    </script>
</head>
<body>
    <header>
        <nav><a href="/">Home</a> | <a href="/about">About</a></nav>
    </header>
    <main>
        <h1>Best SEO Tools 2025</h1>
        <p>This guide covers the top SEO tools available in 2025. With over 500 words of content, this page provides comprehensive information about search engine optimization tools.</p>
        <p>The landscape of SEO has changed dramatically. Modern tools now include AI-powered features, real-time analysis, and comprehensive reporting capabilities that were not available just a few years ago.</p>

        <h2>Table of Contents</h2>
        <ul>
            <li><a href="#keyword-tools">Keyword Research Tools</a></li>
            <li><a href="#technical-seo">Technical SEO Tools</a></li>
            <li><a href="#comparison">Tool Comparison</a></li>
        </ul>

        <h2 id="keyword-tools">Keyword Research Tools</h2>
        <p>Keyword research is the foundation of any SEO strategy. The right tools help you identify high-value keywords with reasonable competition levels.</p>

        <h3>Ahrefs Keywords Explorer</h3>
        <p>Ahrefs provides one of the most comprehensive keyword databases available, with data on over 8 billion keywords across multiple search engines.</p>

        <h3>SEMrush Keyword Magic</h3>
        <p>SEMrush offers a powerful keyword research tool that generates thousands of keyword ideas from a single seed keyword.</p>

        <h2 id="technical-seo">Technical SEO Tools</h2>
        <p>Technical SEO tools help identify and fix crawl errors, page speed issues, and other technical problems that can hurt your search rankings.</p>

        <!-- FAQ via details/summary -->
        <details>
            <summary>What is the best free SEO tool?</summary>
            <p>Google Search Console is widely considered the best free SEO tool available.</p>
        </details>
        <details>
            <summary>How long does SEO take?</summary>
            <p>SEO typically takes 3-6 months to show meaningful results.</p>
        </details>

        <h2 id="comparison">Tool Comparison</h2>
        <table>
            <thead>
                <tr><th>Feature</th><th>Ahrefs</th><th>SEMrush</th><th>Moz</th></tr>
            </thead>
            <tbody>
                <tr><td>Keyword Research</td><td>Yes</td><td>Yes</td><td>Yes</td></tr>
                <tr><td>Backlink Analysis</td><td>Yes</td><td>Yes</td><td>Yes</td></tr>
                <tr><td>Site Audit</td><td>Yes</td><td>Yes</td><td>No</td></tr>
            </tbody>
        </table>

        <h2>Steps to Get Started</h2>
        <ol>
            <li>Sign up for a free trial of your chosen tool</li>
            <li>Run a site audit to identify issues</li>
            <li>Research keywords for your content strategy</li>
        </ol>

        <div class="callout notice">Important: Always track your results over time.</div>
        <div class="alert alert-warning">Warning: Avoid black-hat SEO techniques.</div>

        <img src="https://example.com/seo-chart.jpg" alt="SEO Performance Chart" width="800" height="400">
        <img src="https://example.com/logo.png" alt="">
        <img data-src="https://example.com/lazy-image.webp" alt="Lazy loaded image" loading="lazy">
        <img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7">

        <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" title="SEO Tutorial"></iframe>
        <video src="https://example.com/intro.mp4" controls></video>

        <a href="https://ahrefs.com" rel="nofollow">Ahrefs</a>
        <a href="/internal-page">Internal Page</a>
        <a href="https://example.com/external">External Link</a>
        <a href="mailto:test@example.com">Email</a>
        <a href="#">Skip</a>
    </main>
    <aside>
        <h3>Related Articles</h3>
        <ul><li><a href="/link-building">Link Building Guide</a></li></ul>
    </aside>
    <footer>
        <p>Copyright 2025</p>
        <a href="/privacy">Privacy Policy</a>
    </footer>
</body>
</html>'''


@pytest.fixture
def full_page_tree(full_page_html: str) -> HTMLParser:
    return HTMLParser(full_page_html)
