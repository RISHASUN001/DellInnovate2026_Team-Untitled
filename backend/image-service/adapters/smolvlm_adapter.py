from transformers import AutoProcessor, AutoModelForVision2Seq
from transformers.image_utils import load_image
import torch
from PIL import Image

class SmolVLMAdapter:
    def __init__(self, device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = AutoProcessor.from_pretrained("HuggingFaceTB/SmolVLM-Instruct")
        self.model = AutoModelForVision2Seq.from_pretrained(
            "HuggingFaceTB/SmolVLM-Instruct",
            torch_dtype=torch.bfloat16,
            _attn_implementation="flash_attention_2" if self.device == "cuda" else "eager"
        ).to(self.device)

    def describe_images(self, image_paths, prompt_text):
        # Accepts a list of image file paths and a prompt string
        images = [load_image(p) for p in image_paths]
        messages = [
            {
                "role": "user",
                "content": [
                    *[{"type": "image"} for _ in images],
                    {"type": "text", "text": prompt_text}
                ]
            },
        ]
        prompt = self.processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = self.processor(text=prompt, images=images, return_tensors="pt").to(self.device)
        generated_ids = self.model.generate(**inputs, max_new_tokens=500)
        generated_texts = self.processor.batch_decode(generated_ids, skip_special_tokens=True)
        return generated_texts[0] if generated_texts else None
