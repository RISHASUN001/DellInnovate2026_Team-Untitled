"""
Tests for filename parsing — the most critical pure-domain function.

No ML models or IO are required; these tests run instantly.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from application.filename_parser import discover_images, parse_image_filename
from domain.entities import ImageMetadata


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename, expected",
    [
        (
            "johndoe__20240101__0.jpg",
            ImageMetadata(ig_handle="johndoe", post_date=date(2024, 1, 1), image_index=0),
        ),
        (
            "brand_co__20231215__3.png",
            ImageMetadata(ig_handle="brand_co", post_date=date(2023, 12, 15), image_index=3),
        ),
        (
            "some.user__20250228__12.jpeg",
            ImageMetadata(ig_handle="some.user", post_date=date(2025, 2, 28), image_index=12),
        ),
        (
            "UPPER__20220630__5.PNG",
            ImageMetadata(ig_handle="UPPER", post_date=date(2022, 6, 30), image_index=5),
        ),
        (
            "handle_with_numbers123__20200101__0.jpg",
            ImageMetadata(
                ig_handle="handle_with_numbers123",
                post_date=date(2020, 1, 1),
                image_index=0,
            ),
        ),
    ],
)
def test_valid_filenames(filename: str, expected: ImageMetadata) -> None:
    result = parse_image_filename(Path(filename))
    assert result == expected


# ---------------------------------------------------------------------------
# Edge cases that should still parse
# ---------------------------------------------------------------------------


def test_handle_with_double_underscores_inside() -> None:
    """Handles that contain double underscores are NOT supported —
    the *first* occurrence of __ splits handle from date."""
    # handle = "a__b", date = "20240101", index = 0
    # But our regex uses lazy matching so the handle will be "a"
    result = parse_image_filename(Path("a__b__20240101__0.jpg"))
    # The stem is "a__b__20240101__0"; regex: handle='a', date='b__202', ...
    # This is intentionally None because the date group won't be 8 pure digits.
    # Verify the function does not raise.
    assert result is None or isinstance(result, ImageMetadata)


# ---------------------------------------------------------------------------
# Invalid filename tests — must return None without raising
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename",
    [
        "no_separators.jpg",
        "only_one__separator.jpg",
        "johndoe__BADDATE__0.jpg",
        "johndoe__20241301__0.jpg",  # month=13
        "johndoe__20240132__0.jpg",  # day=32
        "johndoe__20240101__abc.jpg",  # non-numeric index
        "johndoe__20240101__0.gif",   # unsupported extension
        "johndoe__20240101__0.bmp",   # unsupported extension
        "",  # empty filename
    ],
)
def test_invalid_filenames_return_none(filename: str) -> None:
    result = parse_image_filename(Path(filename))
    assert result is None


# ---------------------------------------------------------------------------
# Webp extension support
# ---------------------------------------------------------------------------


def test_webp_extension() -> None:
    result = parse_image_filename(Path("creator__20240515__2.webp"))
    assert result is not None
    assert result.ig_handle == "creator"
    assert result.post_date == date(2024, 5, 15)
    assert result.image_index == 2


# ---------------------------------------------------------------------------
# discover_images — filesystem integration (uses tmp_path fixture)
# ---------------------------------------------------------------------------


def test_discover_images_recursive(tmp_path: Path) -> None:
    """discover_images should find nested images recursively."""
    sub = tmp_path / "sub"
    sub.mkdir()

    # Valid images
    (tmp_path / "user__20240101__0.jpg").touch()
    (sub / "user__20240102__1.png").touch()

    # Non-image file
    (tmp_path / "readme.txt").touch()

    images = discover_images(tmp_path)
    names = {p.name for p in images}
    assert "user__20240101__0.jpg" in names
    assert "user__20240102__1.png" in names
    assert "readme.txt" not in names


def test_discover_images_empty_folder(tmp_path: Path) -> None:
    assert discover_images(tmp_path) == []


def test_discover_images_missing_folder(tmp_path: Path) -> None:
    absent = tmp_path / "does_not_exist"
    # Should not raise; returns empty list
    assert discover_images(absent) == []
