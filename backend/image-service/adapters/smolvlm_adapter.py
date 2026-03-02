from __future__ import annotations

import logging
from PIL import Image

logger = logging.getLogger(__name__)



class SmolVLMAdapter:
    """
    Vision-language adapter for HuggingFaceTB/SmolVLM-Instruct.
    Loads model on GPU if available, otherwise CPU.
    All heavy imports (torch, transformers) are deferred to __init__ for fast startup.
    Uses AutoModelForImageTextToText (transformers >=5.x).
    """


    def __init__(self, device: str | None = None) -> None:
        # Lazy imports — deferred to avoid slow transformers module scan at startup
        import torch as _torch  # noqa: PLC0415
        from transformers import AutoProcessor, AutoModelForImageTextToText  # noqa: PLC0415
        from transformers.image_utils import load_image as _load_image  # noqa: PLC0415

        self._torch = _torch
        self._load_image = _load_image

        # Prefer GPU if available
        if device:
            self.device = device
        else:
            self.device = "cuda" if _torch.cuda.is_available() else "cpu"
        logger.info("Loading SmolVLM model 'HuggingFaceTB/SmolVLM-Instruct' on %s…", self.device)

        self.processor = AutoProcessor.from_pretrained("HuggingFaceTB/SmolVLM-Instruct")
        self.model = AutoModelForImageTextToText.from_pretrained(
            "HuggingFaceTB/SmolVLM-Instruct",
            dtype=_torch.bfloat16 if self.device == "cuda" else _torch.float32,
            attn_implementation="eager",   # 👈 FORCE disable flash attention
        ).to(self.device)
        logger.info("SmolVLM model ready.")


    def describe_images(self, image_paths: list, prompt_text: str) -> str | None:
        """Run SmolVLM on a list of image paths with a text prompt."""
        images = [self._load_image(p) for p in image_paths]
        messages = [
            {
                "role": "user",
                "content": [
                    *[{"type": "image"} for _ in images],
                    {"type": "text", "text": prompt_text},
                ],
            },
        ]
        prompt = self.processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = self.processor(text=prompt, images=images, return_tensors="pt").to(self.device)
        generated_ids = self.model.generate(**inputs, max_new_tokens=500)
        generated_texts = self.processor.batch_decode(generated_ids, skip_special_tokens=True)
        return generated_texts[0] if generated_texts else None
