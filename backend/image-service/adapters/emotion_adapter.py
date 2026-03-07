"""
HuggingFaceEmotionAdapter — concrete implementation of EmotionPort.


# Model: vit-face-expression (stronger ViT-based classifier)

Pipeline:
  1. Face detection via OpenCV Haar cascade (lightweight, no extra deps).
     If a face is detected the bounding-box crop is extracted; otherwise the
     full image is passed through with face_detected_bool = False.
  2. The HuggingFace feature extractor + model run on the (possibly cropped)
     image.  The feature extractor handles all resizing / normalisation
     required by the ViT checkpoint so we do *not* manually resize here.

The model and feature extractor are warm-loaded once at construction time.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from config.settings import settings
from domain.entities import EmotionResult
from ports.emotion_port import EmotionPort

logger = logging.getLogger(__name__)

# Haar path is resolved lazily inside __init__ after cv2 is imported


class HuggingFaceEmotionAdapter(EmotionPort):
    """Facial emotion detection via dima806/facial_emotions_image_detection."""

    def __init__(self) -> None:
        # Lazy imports — deferred to avoid slow module-level torch/transformers scan
        import cv2 as _cv2  # noqa: PLC0415
        import numpy as _np  # noqa: PLC0415
        import torch as _torch  # noqa: PLC0415
        from transformers import (  # noqa: PLC0415
            AutoImageProcessor,
            AutoModelForImageClassification,
        )
        self._cv2 = _cv2
        self._np = _np
        self._torch = _torch


        # Use the model specified in settings (now dima806/facial_emotions_image_detection)
        model_name = settings.emotion_model
        logger.info("Loading emotion model '%s'…", model_name)

        self._model_name = model_name
        self._extractor = AutoImageProcessor.from_pretrained(model_name)
        self._model = AutoModelForImageClassification.from_pretrained(model_name)
        self._model.eval()

        # Move to device if possible
        self._device = settings.device
        try:
            self._model = self._model.to(self._device)
        except Exception:  # noqa: BLE001
            self._device = "cpu"
            self._model = self._model.to("cpu")
            logger.warning("Could not move emotion model to '%s', falling back to cpu.", settings.device)

        # OpenCV face detector
        haar_path = (
            Path(_cv2.__file__).parent / "data" / "haarcascade_frontalface_default.xml"
        )
        if haar_path.exists():
            self._face_detector = _cv2.CascadeClassifier(str(haar_path))
        else:
            logger.warning("Haar cascade not found at %s — face detection disabled.", haar_path)
            self._face_detector = None

        logger.info("Emotion model ready.")

    # ------------------------------------------------------------------

    # Detection passes: (scaleFactor, minNeighbors, minSize) — lenient → strict
    _HAAR_PASSES: list[tuple[float, int, tuple[int, int]]] = [
        (1.05, 3, (20, 20)),   # most lenient — catches small / tilted faces
        (1.08, 4, (25, 25)),   # balanced
        (1.10, 5, (30, 30)),   # original strict pass
    ]
    _FACE_PAD: float = 0.20   # 20 % bounding-box padding on each side

    def _detect_face_crop(self, image: Image.Image) -> tuple[bool, Image.Image]:
        """Return (face_found, crop_or_original).

        Multi-pass strategy: try progressively stricter Haar params and
        return the best (largest-area) face found in *any* pass.  This
        significantly increases recall on typical Instagram photos where
        the face may be small or partially lit.
        """
        if self._face_detector is None:
            return False, image

        bgr = self._cv2.cvtColor(self._np.array(image), self._cv2.COLOR_RGB2BGR)
        gray = self._cv2.cvtColor(bgr, self._cv2.COLOR_BGR2GRAY)
        # Equalise histogram once — improves detection under poor lighting
        gray = self._cv2.equalizeHist(gray)

        best_face: tuple[int, int, int, int] | None = None
        best_area = 0

        for scale, neighbors, min_size in self._HAAR_PASSES:
            try:
                faces = self._face_detector.detectMultiScale(
                    gray,
                    scaleFactor=scale,
                    minNeighbors=neighbors,
                    minSize=min_size,
                    flags=self._cv2.CASCADE_SCALE_IMAGE,
                )
            except Exception:  # noqa: BLE001
                continue
            if len(faces) > 0:
                candidate = max(faces, key=lambda r: r[2] * r[3])
                area = int(candidate[2]) * int(candidate[3])
                if area > best_area:
                    best_face = tuple(candidate)
                    best_area = area

        if best_face is None:
            return False, image

        x, y, w, h = best_face
        pad_x = int(w * self._FACE_PAD)
        pad_y = int(h * self._FACE_PAD)
        img_w, img_h = image.size
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(img_w, x + w + pad_x)
        y2 = min(img_h, y + h + pad_y)
        crop = image.crop((x1, y1, x2, y2))
        return True, crop

    # ------------------------------------------------------------------

    def detect(self, image: Image.Image) -> EmotionResult:
        try:
            face_found, crop = self._detect_face_crop(image)

            if face_found:
                logger.debug("Face detected — running emotion model on cropped region.")
            else:
                logger.debug(
                    "No face detected (image %dx%d) — running emotion model on full image.",
                    image.width, image.height,
                )

            inputs = self._extractor(images=crop, return_tensors="pt")
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            with self._torch.no_grad():
                outputs = self._model(**inputs)

            logits = outputs.logits
            probs = self._torch.softmax(logits, dim=-1)
            # Return the top-2 so callers can see how peaked the distribution is
            top_idx = int(self._torch.argmax(probs, dim=-1).item())
            top_prob = float(probs[0, top_idx].item())
            label = self._model.config.id2label.get(top_idx, str(top_idx))

            # Normalise label to lower-case consistent form
            label = label.lower().strip()

            return EmotionResult(
                face_detected_bool=face_found,
                emotion_label=label,
                emotion_score=round(top_prob, 6),
                model_name=self._model_name,
            )

        except Exception as exc:  # noqa: BLE001
            logger.warning("Emotion detection failed: %s", exc)
            return EmotionResult(
                face_detected_bool=False,
                emotion_label="",
                emotion_score=0.0,
                model_name=self._model_name,
            )
