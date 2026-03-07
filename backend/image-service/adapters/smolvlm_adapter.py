from __future__ import annotations

import logging
from PIL import Image

logger = logging.getLogger(__name__)


def _clean_generated_text(text: str | None) -> str:
    """Normalize generated VLM text to the assistant answer only."""
    if not text:
        return ""

    cleaned = text.strip()
    prefixes = ("assistant:", "assistant", "answer:", "response:")
    lower = cleaned.lower()
    for prefix in prefixes:
        if lower.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            lower = cleaned.lower()

    return cleaned


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

        # Resolve device from explicit input or auto-detect, with safe fallback.
        requested_device = (device or "").strip().lower()
        if requested_device == "cuda":
            if _torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
                logger.warning("Requested device 'cuda' is not available. Falling back to cpu.")
        elif requested_device == "mps":
            if hasattr(_torch.backends, "mps") and _torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
                logger.warning("Requested device 'mps' is not available. Falling back to cpu.")
        elif requested_device == "cpu":
            self.device = "cpu"
        else:
            self.device = "cuda" if _torch.cuda.is_available() else "cpu"
        logger.info("Loading SmolVLM model 'HuggingFaceTB/SmolVLM-Instruct' on %s…", self.device)

        self.processor = AutoProcessor.from_pretrained("HuggingFaceTB/SmolVLM-Instruct")
        self.model = AutoModelForImageTextToText.from_pretrained(
            "HuggingFaceTB/SmolVLM-Instruct",
            torch_dtype=_torch.bfloat16 if self.device == "cuda" else _torch.float32,
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

        generated_ids = self.model.generate(
            **inputs,
            max_new_tokens=192,
            do_sample=False,
        )

        input_token_len = int(inputs["input_ids"].shape[-1]) if "input_ids" in inputs else 0
        continuation_ids = generated_ids[:, input_token_len:] if input_token_len > 0 else generated_ids
        generated_texts = self.processor.batch_decode(continuation_ids, skip_special_tokens=True)

        if not generated_texts:
            return None
        return _clean_generated_text(generated_texts[0])
