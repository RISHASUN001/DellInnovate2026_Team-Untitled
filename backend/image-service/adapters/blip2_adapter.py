"""
BLIP-2 Adapter - Faster VLM alternative optimized for Apple Silicon.
Uses Salesforce/blip2-opt-2.7b for faster inference on MPS.
"""

from __future__ import annotations

import logging
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)


class BLIP2Adapter:
    """Vision-language adapter using BLIP-2 (optimized for Apple Silicon)."""

    def __init__(self, device: str | None = None) -> None:
        import torch
        from transformers import Blip2Processor, Blip2ForConditionalGeneration
        from config.device_utils import get_device

        self._torch = torch
        self.device = get_device(prefer=device)
        
        logger.info("Loading BLIP-2 model 'Salesforce/blip2-opt-2.7b' on %s…", self.device)
        
        # Use smaller BLIP-2 model for speed
        model_name = "Salesforce/blip2-opt-2.7b"
        self.processor = Blip2Processor.from_pretrained(model_name)
        
        # Use float16 on MPS/CUDA for speed
        dtype = torch.float16 if self.device in ["mps", "cuda"] else torch.float32
        
        self.model = Blip2ForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=dtype,
        ).to(self.device)
        
        logger.info("BLIP-2 model ready (optimized for %s).", self.device)

    def describe_images(self, image_paths: list, prompt_text: str) -> str | None:
        """
        Run BLIP-2 on image(s) with a text prompt.
        
        Note: BLIP-2 works best with single images. Multi-image support is limited.
        """
        try:
            # Load first image (BLIP-2 is optimized for single image)
            image_path = image_paths[0] if image_paths else None
            if not image_path:
                return None
            
            image = Image.open(image_path).convert("RGB")
            
            # BLIP-2 inference with prompt
            inputs = self.processor(
                images=image,
                text=prompt_text,
                return_tensors="pt"
            ).to(self.device)
            
            # Generate with optimized settings for speed
            generated_ids = self.model.generate(
                **inputs,
                max_length=100,      # Shorter responses (faster)
                num_beams=3,         # Fewer beams (faster than 5)
                early_stopping=True,
                do_sample=False,
            )
            
            # Decode output
            generated_text = self.processor.batch_decode(
                generated_ids,
                skip_special_tokens=True
            )[0].strip()
            
            return generated_text
            
        except Exception as e:
            logger.error("BLIP-2 inference error: %s", e)
            return None
