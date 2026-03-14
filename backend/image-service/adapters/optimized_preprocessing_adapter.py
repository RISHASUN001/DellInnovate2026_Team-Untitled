"""
OptimizedPreprocessingAdapter — High-performance image preprocessing.

Optimization strategies:
1. Aggressive resizing (256x256 or configurable)
2. Format conversion to JPEG with quality reduction
3. Pixel abstraction/quantization
4. Smart caching
5. Batch-friendly transformations

This adapter is designed for speed over quality when processing large batches.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps, ImageFilter
import numpy as np

from config.settings import settings
from ports.preprocessing_port import PreprocessingPort

logger = logging.getLogger(__name__)


class OptimizedPreprocessingAdapter(PreprocessingPort):
    """Ultra-fast preprocessing with aggressive optimizations."""

    def __init__(
        self,
        target_size: int = 256,
        jpeg_quality: int = 85,
        enable_cache: bool = False,
        pixel_quantization: Optional[int] = None,
    ) -> None:
        """
        Args:
            target_size: Resize images to this size (default: 256x256)
            jpeg_quality: JPEG compression quality 1-100 (default: 85)
            enable_cache: Cache preprocessed images (default: False)
            pixel_quantization: Reduce color palette to N colors for abstraction (default: None)
        """
        self.target_size = target_size
        self.jpeg_quality = jpeg_quality
        self.enable_cache = enable_cache
        self.pixel_quantization = pixel_quantization
        self._cache: dict[str, Image.Image] = {}
        
        logger.info(
            "OptimizedPreprocessingAdapter initialized: size=%d, quality=%d, cache=%s, quantize=%s",
            target_size, jpeg_quality, enable_cache, pixel_quantization
        )

    def _get_cache_key(self, path: Path, mode: str) -> str:
        """Generate cache key from path and processing mode."""
        return f"{mode}:{hashlib.md5(str(path).encode()).hexdigest()}"

    def _fast_load_and_orient(self, path: Path) -> Image.Image:
        """Quickly load, orient, and convert to RGB."""
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)  # Honor EXIF rotation
        return img.convert("RGB")

    def _aggressive_resize(self, img: Image.Image, target: int) -> Image.Image:
        """Resize to square, preserving aspect ratio with padding or crop."""
        w, h = img.size
        
        # If already small enough, just resize
        if max(w, h) <= target:
            return img.resize((target, target), Image.Resampling.BILINEAR)
        
        # Calculate aspect-preserving resize
        if w > h:
            new_w = target
            new_h = int(h * target / w)
        else:
            new_h = target
            new_w = int(w * target / h)
        
        # Use BILINEAR (faster than LANCZOS)
        img = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
        
        # Pad to square if needed
        if new_w != target or new_h != target:
            padded = Image.new("RGB", (target, target), color=(255, 255, 255))
            offset = ((target - new_w) // 2, (target - new_h) // 2)
            padded.paste(img, offset)
            return padded
        
        return img

    def _quantize_pixels(self, img: Image.Image, colors: int) -> Image.Image:
        """Reduce image to N colors for abstract/posterized effect."""
        # Convert to palette mode with specified colors
        return img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGB")

    def _smart_sharpen(self, img: Image.Image) -> Image.Image:
        """Light sharpening to compensate for aggressive resize."""
        return img.filter(ImageFilter.SHARPEN)

    def _jpeg_compress(self, img: Image.Image) -> Image.Image:
        """Simulate JPEG compression to reduce memory footprint."""
        import io
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=self.jpeg_quality, optimize=True)
        buffer.seek(0)
        return Image.open(buffer)

    def load_for_ocr(self, path: Path) -> Image.Image:
        """Optimized preprocessing for OCR/VLM - prioritizes speed."""
        cache_key = self._get_cache_key(path, "ocr")
        
        # Check cache
        if self.enable_cache and cache_key in self._cache:
            logger.debug("Cache hit: %s", path.name)
            return self._cache[cache_key]
        
        # Fast pipeline
        img = self._fast_load_and_orient(path)
        img = self._aggressive_resize(img, self.target_size)
        
        # Optional pixel quantization for extreme speed
        if self.pixel_quantization:
            img = self._quantize_pixels(img, self.pixel_quantization)
        
        # Light sharpen to improve text readability
        img = self._smart_sharpen(img)
        
        # JPEG compress to reduce memory
        img = self._jpeg_compress(img)
        
        # Cache if enabled
        if self.enable_cache:
            self._cache[cache_key] = img
        
        return img

    def preprocess_and_save(self, path: Path) -> Path:
        """Preprocess image and save to disk for VLM inference. Returns path to preprocessed image."""
        from pathlib import Path as PathLib
        
        # Create preprocessed directory
        preprocessed_dir = PathLib("data/preprocessed")
        preprocessed_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate output path
        filename = path.stem
        preprocessed_path = preprocessed_dir / f"{filename}_proc.jpg"
        
        try:
            # Load and preprocess
            logger.info("🔄 Preprocessing: %s → %s", path.name, preprocessed_path.name)
            img = self.load_for_ocr(path)
            
            # Save preprocessed image
            img.save(
                preprocessed_path,
                format="JPEG",
                quality=self.jpeg_quality,
                optimize=True
            )
            
            logger.info("✅ Preprocessed image saved: %s (%dx%d, quality=%d)",
                       preprocessed_path.name, self.target_size, self.target_size, self.jpeg_quality)
            
            return preprocessed_path
            
        except Exception as e:
            logger.error("❌ Preprocessing failed for %s: %s", path.name, e)
            return path  # Return original if preprocessing fails

    def load_for_emotion(self, path: Path) -> Image.Image:
        """Optimized preprocessing for emotion - minimal processing."""
        cache_key = self._get_cache_key(path, "emotion")
        
        # Check cache
        if self.enable_cache and cache_key in self._cache:
            logger.debug("Cache hit: %s", path.name)
            return self._cache[cache_key]
        
        # Minimal pipeline - models handle their own preprocessing
        img = self._fast_load_and_orient(path)
        img = self._aggressive_resize(img, self.target_size)
        
        # Cache if enabled
        if self.enable_cache:
            self._cache[cache_key] = img
        
        return img

    def clear_cache(self) -> None:
        """Clear the preprocessing cache."""
        self._cache.clear()
        logger.info("Preprocessing cache cleared.")

    def get_cache_size(self) -> int:
        """Get number of cached images."""
        return len(self._cache)


class BatchOptimizedPreprocessingAdapter(PreprocessingPort):
    """Batch-aware preprocessing for maximum throughput."""

    def __init__(self, target_size: int = 256, jpeg_quality: int = 85) -> None:
        self.target_size = target_size
        self.jpeg_quality = jpeg_quality
        logger.info("BatchOptimizedPreprocessingAdapter initialized: size=%d", target_size)

    def load_for_ocr(self, path: Path) -> Image.Image:
        """Load and resize for OCR."""
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        
        # Simple resize - let batch processing handle optimization
        return img.resize((self.target_size, self.target_size), Image.Resampling.BILINEAR)

    def load_for_emotion(self, path: Path) -> Image.Image:
        """Load and resize for emotion detection."""
        return self.load_for_ocr(path)

    def batch_preprocess(self, paths: list[Path], mode: str = "ocr") -> list[Image.Image]:
        """Preprocess multiple images efficiently."""
        images = []
        for path in paths:
            try:
                if mode == "ocr":
                    images.append(self.load_for_ocr(path))
                else:
                    images.append(self.load_for_emotion(path))
            except Exception as exc:
                logger.warning("Failed to preprocess %s: %s", path.name, exc)
                # Create a blank placeholder
                images.append(Image.new("RGB", (self.target_size, self.target_size)))
        return images

    def batch_preprocess_to_tensors(self, paths: list[Path]) -> np.ndarray:
        """Preprocess images and convert to numpy array for batch inference."""
        images = self.batch_preprocess(paths)
        
        # Convert to numpy array
        arrays = [np.array(img) for img in images]
        return np.stack(arrays, axis=0)
