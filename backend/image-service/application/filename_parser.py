"""
filename_parser — pure domain utility for parsing image filenames.

Convention:  <ig_handle>__<YYYYMMDD>__<index>.(jpg|jpeg|png|webp)

Examples:
  johndoe__20240101__0.jpg   → ig_handle="johndoe", date=2024-01-01, index=0
  brand_co__20231215__3.png  → ig_handle="brand_co", date=2023-12-15, index=3

The function returns ``None`` on any parse failure so callers can decide
whether to skip or raise.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Optional

from domain.entities import ImageMetadata

# ---- Constants ---------------------------------------------------------

_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp"}
)

_FILENAME_RE = re.compile(
    r"^(?P<handle>.+?)__(?P<date>\d{8})__(?P<index>\d+)$",
    re.IGNORECASE,
)


# ---- Public API --------------------------------------------------------

def parse_image_filename(path: Path) -> Optional[ImageMetadata]:
    """Parse *path* stem and return ``ImageMetadata`` or ``None`` on failure.

    Args:
        path: Path to the image file (only the stem + suffix are examined).

    Returns:
        An :class:`~domain.entities.ImageMetadata` instance, or ``None``
        if the filename does not conform to the expected convention.
    """
    if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
        return None

    match = _FILENAME_RE.match(path.stem)
    if match is None:
        return None

    ig_handle = match.group("handle")
    raw_date = match.group("date")
    raw_index = match.group("index")

    try:
        post_date = date(
            int(raw_date[:4]),
            int(raw_date[4:6]),
            int(raw_date[6:8]),
        )
    except ValueError:
        return None

    try:
        image_index = int(raw_index)
    except ValueError:
        return None

    return ImageMetadata(
        ig_handle=ig_handle,
        post_date=post_date,
        image_index=image_index,
    )


def discover_images(folder: Path) -> list[Path]:
    """Recursively return all supported image files under *folder*.

    Returns an empty list if *folder* does not exist.
    """
    if not folder.exists():
        return []
    results: list[Path] = []
    for ext in _SUPPORTED_EXTENSIONS:
        results.extend(folder.rglob(f"*{ext}"))
        results.extend(folder.rglob(f"*{ext.upper()}"))
    return sorted(set(results))
