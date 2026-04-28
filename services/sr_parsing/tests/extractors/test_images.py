"""Tests for images extractor (EXTR-14 + EXTR-15)."""
from __future__ import annotations

from selectolax.parser import HTMLParser

from scraper_service.extractors.images import extract


class TestImagesFromFullPage:
    """Tests using the full_page_html fixture from conftest.py."""

    def test_total_images(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["total_images"] == 4

    def test_image_list_count(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert len(result["image_list"]) == 4

    def test_seo_chart_image(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        chart_img = [img for img in result["image_list"] if "seo-chart" in img["src"]]
        assert len(chart_img) == 1
        assert chart_img[0]["alt"] == "SEO Performance Chart"
        assert chart_img[0]["in_main_content"] is True

    def test_missing_alt_images(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        # selectolax returns None for both missing alt and alt=""
        # logo.png (alt="") and data:gif (no alt) both count as missing_alt
        assert result["missing_alt"] == 2

    def test_data_src_fallback(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        lazy_imgs = [img for img in result["image_list"] if "lazy-image" in img["src"]]
        assert len(lazy_imgs) == 1
        assert lazy_imgs[0]["alt"] == "Lazy loaded image"

    def test_lazy_loaded_count(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["lazy_loaded"] == 1

    def test_alt_coverage(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        # 4 images: seo-chart (descriptive), logo.png (None from selectolax),
        # lazy-image (descriptive), data:gif (None from selectolax)
        # selectolax returns None for both missing alt and alt=""
        assert result["descriptive_alt"] == 2  # seo-chart + lazy-image
        assert result["missing_alt"] == 2       # logo.png + data:gif
        assert result["total_images"] == 4
        expected_pct = round(2 / 4 * 100, 1)
        assert result["alt_coverage_pct"] == expected_pct

    def test_in_main_content(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        # All images in full_page_html are inside <main>
        assert result["in_main_content"] == 4

    def test_extension_breakdown(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        # seo-chart.jpg, logo.png, lazy-image.webp, data:gif (skipped - data URI)
        assert result["ext_jpg"] == 1
        assert result["ext_png"] == 1
        assert result["ext_webp"] == 1


class TestImagesNoImages:
    """Tests with minimal HTML that has no images."""

    def test_no_images(self, minimal_tree: HTMLParser) -> None:
        result = extract(minimal_tree, "https://example.com")
        assert result["total_images"] == 0
        assert result["image_list"] == []
        assert result["alt_coverage_pct"] == 100.0  # no images = perfect coverage

    def test_all_zero_stats(self, minimal_tree: HTMLParser) -> None:
        result = extract(minimal_tree, "https://example.com")
        assert result["missing_alt"] == 0
        assert result["empty_alt"] == 0
        assert result["descriptive_alt"] == 0
        assert result["lazy_loaded"] == 0
        assert result["has_srcset"] == 0
        assert result["ext_jpg"] == 0


class TestImagesOutsideMain:
    """Tests for images outside <main> tag."""

    def test_images_outside_main_not_in_main(self) -> None:
        html = '''<html><body>
            <div>
                <img src="https://example.com/outside.jpg" alt="Outside main">
            </div>
            <main></main>
        </body></html>'''
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["in_main_content"] == 0
        assert result["image_list"][0]["in_main_content"] is False

    def test_images_inside_main(self) -> None:
        html = '''<html><body>
            <main>
                <img src="https://example.com/inside.jpg" alt="Inside main">
            </main>
        </body></html>'''
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["in_main_content"] == 1
        assert result["image_list"][0]["in_main_content"] is True

    def test_mixed_main_and_outside(self) -> None:
        html = '''<html><body>
            <header>
                <img src="https://example.com/header.png" alt="Logo">
            </header>
            <main>
                <img src="https://example.com/content.jpg" alt="Content">
            </main>
            <footer>
                <img src="https://example.com/footer.png" alt="Footer">
            </footer>
        </body></html>'''
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["total_images"] == 3
        assert result["in_main_content"] == 1


class TestImagesMalformed:
    """Tests for error handling with malformed content."""

    def test_never_raises_on_malformed_html(self) -> None:
        tree = HTMLParser("<html><<>>><<<")
        result = extract(tree, "https://example.com")
        assert isinstance(result, dict)
        assert result["total_images"] >= 0

    def test_never_raises_on_empty_body(self) -> None:
        tree = HTMLParser("<html><body></body></html>")
        result = extract(tree, "https://example.com")
        assert result["total_images"] == 0
        assert result["alt_coverage_pct"] == 100.0


class TestImagesSrcset:
    """Tests for srcset attribute detection."""

    def test_srcset_detected(self) -> None:
        html = '''<html><body>
            <img src="https://example.com/photo.jpg"
                 srcset="photo-320.jpg 320w, photo-640.jpg 640w"
                 alt="Responsive image">
        </body></html>'''
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_srcset"] == 1


class TestImagesMissingAlt:
    """Tests for alt attribute classification."""

    def test_missing_vs_descriptive_alt(self) -> None:
        html = '''<html><body>
            <img src="https://example.com/no-alt.jpg">
            <img src="https://example.com/empty-alt.jpg" alt="">
            <img src="https://example.com/descriptive.jpg" alt="A description">
        </body></html>'''
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        # selectolax returns None for both missing alt and alt=""
        assert result["missing_alt"] == 2      # no alt attr + alt=""
        assert result["empty_alt"] == 0         # selectolax can't distinguish alt=""
        assert result["descriptive_alt"] == 1   # non-empty alt
        assert result["alt_coverage_pct"] == round(1 / 3 * 100, 1)
