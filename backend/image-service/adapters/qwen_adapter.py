"""
Qwen Vision Model Adapter - Ultra-fast API-based VLM via OpenRouter.
Uses Qwen/Qwen2.5-VL-72B-Instruct for vision-language tasks.
Much faster than local models since it's an API call.
"""

from __future__ import annotations

import logging
import base64
from pathlib import Path
from typing import Literal
from PIL import Image
import io

logger = logging.getLogger(__name__)


class QwenAdapter:
    """Vision-language adapter using Qwen via OpenRouter API."""

    def __init__(self, device: str | None = None) -> None:
        """
        Initialize Qwen adapter with OpenRouter API.
        
        Args:
            device: Ignored for API-based model (kept for interface compatibility)
        """
        from openai import OpenAI
        from config.settings import settings
        
        logger.info("Initializing Qwen VLM via OpenRouter API...")
        
        # Initialize OpenAI-compatible client for OpenRouter
        self.client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url
        )
        
        # Use Qwen 2.5 VL 72B - powerful vision-language model
        self.model = settings.qwen_model
        
        logger.info("✓ Qwen adapter ready (API-based, no local model loading)")
        logger.info("   Model: %s", self.model)

    def _image_to_base64(self, image_path: Path) -> str:
        """Convert image to base64 string for API."""
        with Image.open(image_path) as img:
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save to bytes
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=95)
            img_bytes = buffer.getvalue()
            
            # Encode to base64
            return base64.b64encode(img_bytes).decode('utf-8')

    def analyze_scene(self, image_path: Path) -> str:
        """
        Generate a scene description using Qwen vision model.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Scene description string
        """
        try:
            logger.debug("Qwen analyzing scene: %s", image_path.name)
            
            # Convert image to base64
            img_b64 = self._image_to_base64(image_path)
            
            # Call OpenRouter API with vision prompt
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Describe this social media image concisely. Focus on: people, emotions, setting, objects, activities. Keep under 100 words."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=256,
                temperature=0.3
            )
            
            description = response.choices[0].message.content.strip()
            logger.debug("✓ Scene description: %s", description[:80] + "...")
            return description
            
        except Exception as e:
            logger.error("Qwen scene analysis failed: %s", e)
            return f"Error analyzing scene: {str(e)}"

    def extract_text(self, image_path: Path) -> str:
        """
        Extract text from image using OCR capabilities.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Extracted text string
        """
        try:
            logger.debug("Qwen extracting text: %s", image_path.name)
            
            # Convert image to base64
            img_b64 = self._image_to_base64(image_path)
            
            # Call OpenRouter API with OCR prompt
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract ALL visible text from this image. Include captions, overlays, signs, and any readable text. Output only the extracted text, nothing else."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=256,
                temperature=0.1
            )
            
            text = response.choices[0].message.content.strip()
            logger.debug("✓ Extracted text length: %d chars", len(text))
            return text
            
        except Exception as e:
            logger.error("Qwen text extraction failed: %s", e)
            return ""

    def detect_emotion(self, image_path: Path) -> Literal["happy", "sad", "anxious", "neutral"]:
        """
        Detect primary emotion from image.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Primary emotion label
        """
        try:
            logger.debug("Qwen detecting emotion: %s", image_path.name)
            
            # Convert image to base64
            img_b64 = self._image_to_base64(image_path)
            
            # Call OpenRouter API with emotion detection prompt
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "What is the PRIMARY emotion conveyed in this image? Choose ONLY ONE: happy, sad, anxious, or neutral. Respond with just the single word emotion label."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=10,
                temperature=0.1
            )
            
            emotion = response.choices[0].message.content.strip().lower()
            
            # Validate and normalize
            if emotion in ["happy", "sad", "anxious", "neutral"]:
                logger.debug("✓ Detected emotion: %s", emotion)
                return emotion
            else:
                logger.warning("Unexpected emotion '%s', defaulting to neutral", emotion)
                return "neutral"
            
        except Exception as e:
            logger.error("Qwen emotion detection failed: %s", e)
            return "neutral"

    def describe_images(self, image_paths: list, prompt_text: str) -> str | None:
        """
        General-purpose vision-language method for compatibility with SmolVLM interface.
        
        Args:
            image_paths: List of image file paths (typically 1 image)
            prompt_text: Text prompt for the vision-language task
            
        Returns:
            Model response as string, or None on error
        """
        if not image_paths:
            logger.warning("describe_images called with empty image_paths")
            return None
            
        try:
            # Use first image (most cases only have 1 image)
            image_path = Path(image_paths[0])
            logger.debug("Qwen describe_images: %s with prompt: %s", image_path.name, prompt_text[:50])
            
            # Convert image to base64
            img_b64 = self._image_to_base64(image_path)
            
            # Call OpenRouter API with custom prompt
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt_text
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=512,  # Reduced from 1024 to save tokens
                temperature=0.2  # Lower for more focused responses
            )
            
            # Check for None content
            content = response.choices[0].message.content
            if content is None:
                logger.warning("Qwen API returned None content for image: %s", image_path.name)
                return None
                
            result = content.strip()
            logger.debug("✓ Qwen response: %s", result)
            return result
            
        except Exception as e:
            logger.error("Qwen describe_images failed: %s", e)
            return None
