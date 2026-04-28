"""Tests for ExtractionResult model and its 18 sub-models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from scraper_service.models import (
    BodyTextData,
    CalloutBoxesData,
    CalloutItem,
    ComparisonTableData,
    ComparisonTablesData,
    ExtractionResult,
    FaqData,
    HeadingsData,
    ImageItem,
    ImagesData,
    JsonldData,
    LinksData,
    ListsData,
    MetaData,
    MetaDescData,
    PaginationData,
    StepByStepData,
    StepGroup,
    TablesData,
    TechnicalData,
    TitleData,
    TocData,
    TocLink,
    VideoItem,
    VideosData,
)

# The 18 sub-model field names on ExtractionResult.
SUB_MODEL_NAMES = [
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


def test_extraction_result_all_defaults():
    """ExtractionResult() creates with all defaults (empty sub-models, no errors)."""
    result = ExtractionResult()
    assert result.errors == {}
    for name in SUB_MODEL_NAMES:
        sub = getattr(result, name)
        assert sub is not None, f"sub-model {name} is None"


def test_extraction_result_from_single_extractor():
    """from_extraction_results with one extractor dict populates that sub-model."""
    result = ExtractionResult.from_extraction_results({
        "title": {"title": "Test Page", "title_length": 9},
    })
    assert result.title.title == "Test Page"
    assert result.title.title_length == 9
    # Other sub-models should have defaults
    assert result.headings.h1_count == 0
    assert result.errors == {}


def test_extraction_result_from_error_dict():
    """from_extraction_results records _error keys and uses defaults for that sub-model."""
    result = ExtractionResult.from_extraction_results({
        "title": {"_error": "boom"},
    })
    assert result.errors == {"title": "boom"}
    # Title sub-model should have defaults
    assert result.title.title is None
    assert result.title.title_length == 0


def test_extraction_result_mixed_success_and_error():
    """from_extraction_results handles a mix of successful and failed extractors."""
    result = ExtractionResult.from_extraction_results({
        "title": {"title": "OK", "title_length": 2},
        "headings": {"_error": "parse failed"},
        "links": {"total_links": 5, "internal_links": 3, "external_links": 2},
    })
    assert result.title.title == "OK"
    assert result.headings.h1_count == 0  # defaults
    assert result.links.total_links == 5
    assert result.errors == {"headings": "parse failed"}


def test_extraction_result_rejects_extra_fields():
    """ExtractionResult rejects unknown top-level fields (extra='forbid')."""
    with pytest.raises(ValidationError) as exc_info:
        ExtractionResult(unknown_field="value")
    assert "extra_forbidden" in str(exc_info.value)


def test_extraction_result_json_schema():
    """model_json_schema() produces a valid JSON schema with all sub-models."""
    schema = ExtractionResult.model_json_schema()
    assert "properties" in schema
    for name in SUB_MODEL_NAMES:
        assert name in schema["properties"], f"{name} missing from schema"


def test_all_18_sub_models_accessible():
    """All 20 sub-model names are accessible as attributes on ExtractionResult."""
    result = ExtractionResult()
    assert len(SUB_MODEL_NAMES) == 20
    for name in SUB_MODEL_NAMES:
        assert hasattr(result, name), f"ExtractionResult has no attribute {name}"


def test_sub_model_rejects_extra_fields():
    """Each sub-model rejects unknown fields (extra='forbid')."""
    with pytest.raises(ValidationError):
        TitleData(unknown="value")
    with pytest.raises(ValidationError):
        HeadingsData(unknown="value")
    with pytest.raises(ValidationError):
        MetaData(unknown="value")


def test_from_extraction_results_ignores_non_dict():
    """from_extraction_results skips non-dict values gracefully."""
    result = ExtractionResult.from_extraction_results({
        "title": "not a dict",
        "headings": {"h1_count": 1},
    })
    # title should keep defaults (non-dict ignored)
    assert result.title.title is None
    assert result.headings.h1_count == 1


def test_nested_sub_models():
    """Sub-models with nested structures (lists of sub-models) work correctly."""
    result = ExtractionResult.from_extraction_results({
        "videos": {
            "video_count": 2,
            "videos": [
                {"src": "https://example.com/v1.mp4", "type": "video_tag", "title": "Vid 1"},
                {"src": "https://youtube.com/embed/abc", "type": "youtube", "title": "Vid 2"},
            ],
        },
    })
    assert result.videos.video_count == 2
    assert len(result.videos.videos) == 2
    assert result.videos.videos[0].src == "https://example.com/v1.mp4"
    assert result.videos.videos[1].type == "youtube"


def test_images_data_nested():
    """ImagesData with nested ImageItem list validates correctly."""
    result = ExtractionResult.from_extraction_results({
        "images": {
            "total_images": 1,
            "image_list": [
                {"src": "https://example.com/img.jpg", "alt": "A photo", "in_main_content": True},
            ],
        },
    })
    assert result.images.total_images == 1
    assert len(result.images.image_list) == 1
    assert result.images.image_list[0].alt == "A photo"
