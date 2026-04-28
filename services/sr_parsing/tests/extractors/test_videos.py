"""Tests for videos extractor (EXTR-08)."""
from selectolax.parser import HTMLParser

from scraper_service.extractors import videos


class TestVideosWithFullPage:
    """Tests using the full_page_html fixture which has a YouTube iframe and video tag."""

    def test_video_count(self, full_page_tree: HTMLParser) -> None:
        result = videos.extract(full_page_tree, "https://example.com")
        # 1 YouTube iframe + 1 <video> tag
        assert result["video_count"] == 2

    def test_youtube_iframe(self, full_page_tree: HTMLParser) -> None:
        result = videos.extract(full_page_tree, "https://example.com")
        yt = [v for v in result["videos"] if v["type"] == "youtube"]
        assert len(yt) == 1
        assert "youtube.com/embed/" in yt[0]["src"]
        assert yt[0]["title"] == "SEO Tutorial"

    def test_video_tag(self, full_page_tree: HTMLParser) -> None:
        result = videos.extract(full_page_tree, "https://example.com")
        tag = [v for v in result["videos"] if v["type"] == "video_tag"]
        assert len(tag) == 1
        assert tag[0]["src"] == "https://example.com/intro.mp4"


class TestVideosVimeo:
    """Tests for Vimeo iframe detection."""

    def test_vimeo_detected(self) -> None:
        html = '<html><body><iframe src="https://player.vimeo.com/video/123"></iframe></body></html>'
        tree = HTMLParser(html)
        result = videos.extract(tree, "https://example.com")
        assert result["video_count"] == 1
        assert result["videos"][0]["type"] == "vimeo"
        assert "vimeo.com" in result["videos"][0]["src"]


class TestVideosOgVideo:
    """Tests for og:video meta detection."""

    def test_og_video_detected(self) -> None:
        html = '<html><head><meta property="og:video" content="https://example.com/vid.mp4"></head><body></body></html>'
        tree = HTMLParser(html)
        result = videos.extract(tree, "https://example.com")
        assert result["video_count"] == 1
        assert result["videos"][0]["type"] == "og_video"
        assert result["videos"][0]["src"] == "https://example.com/vid.mp4"


class TestVideosNoVideos:
    """Tests with minimal HTML that has no videos."""

    def test_no_videos(self, minimal_tree: HTMLParser) -> None:
        result = videos.extract(minimal_tree, "https://example.com")
        assert result["video_count"] == 0
        assert result["videos"] == []


class TestVideosNeverRaises:
    """Extractor must never raise, even on malformed input."""

    def test_malformed_html(self) -> None:
        tree = HTMLParser("<html><<<<>>>></html>")
        result = videos.extract(tree, "https://example.com")
        assert isinstance(result, dict)
        assert "video_count" in result
        assert result["video_count"] == 0

    def test_iframe_no_src(self) -> None:
        html = '<html><body><iframe></iframe></body></html>'
        tree = HTMLParser(html)
        result = videos.extract(tree, "https://example.com")
        assert result["video_count"] == 0
