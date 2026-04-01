"""
Vision Module - Image Understanding with Google Gemini
=======================================================
Gemini 1.5 Flash vision capability use karta hai images analyze karne ke liye.
"""

import google.generativeai as genai
import io
from PIL import Image


class VisionModule:

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self.model_name = model_name

    async def analyze_image(self, image_bytes: bytes, content_type: str, prompt: str = None) -> str:
        if not prompt or prompt.strip() == "":
            prompt = """Please provide a comprehensive analysis of this image:

1. **Overall Description**: What is shown in this image?
2. **Objects & Elements**: List all visible objects, people, animals, or elements
3. **Text (OCR)**: Extract any visible text, signs, labels, or writing
4. **Colors & Style**: Dominant colors, visual style, and composition
5. **Context & Setting**: Environment, location, or context if identifiable
6. **Notable Details**: Any interesting, unusual, or important details

Be thorough and specific."""

        # Convert to PIL Image (handle RGBA etc.)
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode in ("RGBA", "P", "LA"):
            image = image.convert("RGB")

        model = genai.GenerativeModel(self.model_name)
        response = await model.generate_content_async([prompt, image])
        return response.text

    async def extract_text_ocr(self, image_bytes: bytes) -> str:
        return await self.analyze_image(
            image_bytes, "image/jpeg",
            "Extract ALL text visible in this image. Preserve formatting. If no text found, say 'No text found in image'."
        )

    async def detect_objects(self, image_bytes: bytes) -> str:
        return await self.analyze_image(
            image_bytes, "image/jpeg",
            "Detect and list all objects in this image with: name, location, size, attributes. Format as numbered list."
        )

    async def analyze_chart(self, image_bytes: bytes) -> str:
        return await self.analyze_image(
            image_bytes, "image/jpeg",
            "Analyze this chart/graph: chart type, labels, data summary, key insights, notable data points, conclusion."
        )
