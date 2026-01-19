"""
Image Text Extractor and Translator
Extracts Chinese text from images and creates translation tables
"""

import logging
from typing import Dict, List
from openai import OpenAI
import os
import requests
import base64
from PIL import Image
import io

logger = logging.getLogger(__name__)


class ImageTextTranslator:
    """Extract and translate text from images"""

    def __init__(self, api_key: str = None):
        """Initialize image translator with OpenAI API"""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)

    def _download_and_encode_image(self, image_url: str) -> str:
        """
        Download image, convert to JPEG, and encode to base64

        Args:
            image_url: URL of the image

        Returns:
            Base64 encoded JPEG image string with data URI prefix
        """
        try:
            # Download image
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()

            logger.info(f"Downloaded image: {len(response.content)} bytes")

            # Open image with PIL
            img = Image.open(io.BytesIO(response.content))
            logger.info(f"Image format: {img.format}, Size: {img.size}, Mode: {img.mode}")

            # Convert to RGB if necessary (handles RGBA, P, etc.)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Resize if too large (max 2048 on longest side for better processing)
            max_size = 2048
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.LANCZOS)
                logger.info(f"Resized to: {img.size}")

            # Convert to JPEG
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=85)
            jpeg_data = output.getvalue()

            logger.info(f"Converted to JPEG: {len(jpeg_data)} bytes")

            # Encode to base64
            base64_image = base64.b64encode(jpeg_data).decode('utf-8')

            return f"data:image/jpeg;base64,{base64_image}"
        except Exception as e:
            logger.error(f"Error downloading/converting image: {e}")
            raise

    def extract_and_translate_image_text(self, image_url: str) -> Dict[str, List[tuple]]:
        """
        Extract Chinese text from image and translate to Japanese
        Uses a two-step approach: 1) Extract text, 2) Translate

        Args:
            image_url: URL of the image containing Chinese text

        Returns:
            Dict with 'translations' as list of (chinese, japanese) tuples
        """
        logger.info(f"Processing image: {image_url}")

        try:
            # Download and encode image to base64
            logger.info("Downloading and encoding image...")
            base64_image = self._download_and_encode_image(image_url)

            # Step 1: Extract Chinese text from image
            logger.info("Step 1: Extracting Chinese text from image...")
            response1 = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Please list all the Chinese text labels and phrases you can see "
                                    "in this technical diagram. Just list them, one per line, "
                                    "without translation or explanation."
                                )
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": base64_image,
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.1
            )

            chinese_text = response1.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if chinese_text.startswith("```"):
                lines = chinese_text.split("\n")
                chinese_text = "\n".join([l for l in lines if not l.startswith("```") and not l.startswith("Sure,")])

            logger.info(f"Extracted text preview: {chinese_text[:200]}...")

            if not chinese_text or len(chinese_text) < 5:
                logger.info("No text found in image")
                return {"translations": []}

            # Step 2: Translate the extracted text
            logger.info("Step 2: Translating Chinese text to Japanese...")
            response2 = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Please translate each of the following Chinese phrases to Japanese. "
                            f"Format: Chinese|Japanese (one per line)\n\n{chinese_text}"
                        )
                    }
                ],
                max_tokens=3000,
                temperature=0.1
            )

            translation_text = response2.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if translation_text.startswith("```"):
                lines = translation_text.split("\n")
                translation_text = "\n".join([l for l in lines if not l.startswith("```") and not l.startswith("Sure,")])

            logger.info(f"Translation preview: {translation_text[:200]}...")

            # Parse response into list of (chinese, japanese) tuples
            translations = []
            for line in translation_text.split("\n"):
                line = line.strip()
                if "|" in line:
                    parts = line.split("|", 1)
                    if len(parts) == 2:
                        chinese = parts[0].strip()
                        japanese = parts[1].strip()
                        if chinese and japanese:
                            translations.append((chinese, japanese))

            logger.info(f"Extracted {len(translations)} text pairs from image")
            return {"translations": translations}

        except Exception as e:
            logger.error(f"Image processing error: {e}")
            return {"translations": [], "error": str(e)}

    def create_translation_table(self, translations: List[tuple]) -> str:
        """
        Create a formatted translation table in markdown

        Args:
            translations: List of (chinese, japanese) tuples

        Returns:
            Markdown table string
        """
        if not translations:
            return "画像内にテキストはありません。"

        table = "| 中国語 | 日本語 |\n"
        table += "|--------|--------|\n"

        for chinese, japanese in translations:
            table += f"| {chinese} | {japanese} |\n"

        return table
