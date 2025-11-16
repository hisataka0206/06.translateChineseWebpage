"""
Text Translator using OpenAI ChatGPT API
Translates Chinese text to Japanese
"""

import os
from openai import OpenAI
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TextTranslator:
    """Translator for Chinese to Japanese text"""

    def __init__(self, prompt_template: Optional[str] = None):
        """
        Initialize translator with OpenAI API

        Args:
            prompt_template: Custom prompt template for translation
        """
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        self.default_prompt = (
            "あなたは中国語から日本語への翻訳専門家です。"
            "以下の中国語テキストを自然な日本語に翻訳してください。"
            "専門用語は正確に、文脈を考慮して翻訳してください。\n\n"
            "中国語テキスト:\n{text}"
        )

        self.prompt_template = prompt_template or self.default_prompt

    def translate(self, chinese_text: str) -> str:
        """
        Translate Chinese text to Japanese

        Args:
            chinese_text: Text in Chinese

        Returns:
            Translated text in Japanese
        """
        if not chinese_text or not chinese_text.strip():
            return ""

        logger.info(f"Translating text: {chinese_text[:50]}...")

        prompt = self.prompt_template.format(text=chinese_text)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "あなたは優秀な翻訳者です。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )

            translated_text = response.choices[0].message.content.strip()
            logger.info(f"Translation complete: {translated_text[:50]}...")

            return translated_text

        except Exception as e:
            logger.error(f"Translation error: {e}")
            raise

    def translate_batch(self, texts: list[str]) -> list[str]:
        """
        Translate multiple texts

        Args:
            texts: List of Chinese texts

        Returns:
            List of translated Japanese texts
        """
        return [self.translate(text) for text in texts]
