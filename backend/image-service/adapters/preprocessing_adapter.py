"""
PillowPreprocessingAdapter — concrete implementation of PreprocessingPort.

Applies EXIF auto-orientation, RGB conversion, optional downscaling,
and basic denoise + contrast normalisation (CLAHE via OpenCV) before
passing the image on to the OCR or emotion pipelines.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageOps

from config.settings import settings
from ports.preprocessing_port import PreprocessingPort

logger = logging.getLogger(__name__)


def _exif_orient_rgb(path: Path) -> Image.Image:
    """Open an image, apply EXIF orientation, and convert to RGB."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)   # honour EXIF rotation tags
    img = img.convert("RGB")
    return img


def _get_cv2():
    """Lazy cv2 import."""
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    return cv2, np


def _maybe_resize(img: Image.Image, max_side: int) -> Image.Image:
    """Downscale proportionally if either dimension exceeds *max_side*."""
    if max_side <= 0:
        return img
    w, h = img.size
    if max(w, h) <= max_side:
        return img
    if w >= h:
        new_w, new_h = max_side, int(h * max_side / w)
    else:
        new_w, new_h = int(w * max_side / h), max_side
    return img.resize((new_w, new_h), Image.LANCZOS)


def _denoise_and_normalise(img: Image.Image) -> Image.Image:
    """Apply fastNlMeansDenoisingColored + CLAHE on LAB lightness + unsharp mask."""
    cv2, np = _get_cv2()
    arr = np.array(img)

    # Light fastNlMeans denoise
    arr = cv2.fastNlMeansDenoisingColored(arr, None, h=10, hColor=10,
                                          templateWindowSize=7, searchWindowSize=21)

    # CLAHE on L channel of LAB for contrast enhancement
    lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    lab = cv2.merge([l_channel, a_channel, b_channel])
    arr = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    # Unsharp mask — sharpens edges which greatly helps EasyOCR on blurry text
    blurred = cv2.GaussianBlur(arr, (0, 0), sigmaX=1.5)
    arr = cv2.addWeighted(arr, 1.6, blurred, -0.6, 0)

    return Image.fromarray(arr)


class PillowPreprocessingAdapter(PreprocessingPort):
    """Image preprocessing using Pillow + OpenCV."""

    def load_for_ocr(self, path: Path) -> Image.Image:
        """Full preprocessing pipeline for OCR."""
        img = _exif_orient_rgb(path)
        img = _maybe_resize(img, settings.max_image_side_px)
        img = _denoise_and_normalise(img)
        return img

    def load_for_emotion(self, path: Path) -> Image.Image:
        """Minimal preprocessing for emotion detection.

        Only EXIF orient + RGB conversion — the HuggingFace feature extractor
        handles everything the model needs (resize, normalise, etc.).
        """
        return _exif_orient_rgb(path)
