"""
LLaVA Adapter - Another fast VLM alternative.
Uses llava-hf/llava-1.5-7b-hf for good balance of speed and accuracy.
"""

from __future__ import annotations

import logging
from PIL import Image

logger = logging.getLogger(__name__)


class LLaVAAdapter:
    """Vision-language adapter using LLaVA 1.5."""

    def __init__(self, device: str | None = None) -> None:
        import torch
        from transformers import LlavaNextProcessor, LlavaNextForConditionalGeneration
        from config.device_utils import get_device

        self._torch = torch
        self.device = get_device(prefer=device)
        
        logger.info("Loading LLaVA model 'llava-hf/llava-v1.6-mistral-7b-hf' on %s…", self.device)
        
        # Use LLaVA-Next (v1.6) for better performance
        model_name = "llava-hf/llava-v1.6-mistral-7b-hf"
        
        self.processor = LlavaNextProcessor.from_pretrained(model_name)
        
        # Use float16 on MPS/CUDA for speed
        dtype = torch.float16 if self.device in ["mps", "cuda"] else torch.float32
        
        self.model = LlavaNextForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
        ).to(self.device)
        
        logger.info("LLaVA model ready (optimized for %s).", self.device)

    def describe_images(self, image_paths: list, prompt_text: str) -> str | None:
        """Run LLaVA on image(s) with a text prompt."""
        try:
            # Load first image
            image_path = image_paths[0] if image_paths else None
            if not image_path:
                return None
            
            image = Image.open(image_path).convert("RGB")
            
            # Format prompt for LLaVA
            conversation = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image"},
                        {"type": "text", "text": prompt_text},
                    ],
                },
            ]
            
            prompt = self.processor.apply_chat_template(
                conversation,
                add_generation_prompt=True
            )
            
            # Process inputs
            inputs = self.processor(
                text=prompt,
                images=image,
                return_tensors="pt"
            ).to(self.device)
            
            # Generate with optimized settings
            generated_ids = self.model.generate(
                **inputs,
                max_new_tokens=150,
                do_sample=False,
                temperature=0.0,
            )
            
            # Decode and extract answer
            generated_text = self.processor.batch_decode(
                generated_ids,
                skip_special_tokens=True
            )[0].strip()
            
            # Extract assistant's response
            if "ASSISTANT:" in generated_text:
                generated_text = generated_text.split("ASSISTANT:")[-1].strip()
            
            return generated_text
            
        except Exception as e:
            logger.error("LLaVA inference error: %s", e)
            return None
