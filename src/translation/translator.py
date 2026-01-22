import os
from openai import OpenAI
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TextTranslator:
    """Translator for Chinese to Japanese text"""

    def __init__(self, api_key: Optional[str] = None, prompt_template: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize translator with OpenAI API

        Args:
            api_key: OpenAI API key (optional, falls back to env var if not provided)
            prompt_template: Custom prompt template for translation
            model: OpenAI model to use (default: gpt-4o)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = model

        self.default_prompt = (
            "あなたは中国語から日本語への翻訳専門家です。"
            "以下の中国語テキストを自然な日本語に翻訳してください。"
            "専門用語は正確に、文脈を考慮して翻訳してください。\n"
            "【重要】\n"
            "・URL、ファイルパス、コードブロック、数値のみの行は翻訳せず、そのまま出力してください。\n"
            "・「翻訳できません」「読み込めません」などの謝罪や説明は一切不要です。\n"
            "・翻訳対象ではないと判断した場合は、原文をそのまま出力してください。\n\n"
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

        # Check if text is a URL
        if re.match(r'^https?://', chinese_text.strip()):
            logger.info(f"Skipping translation for URL: {chinese_text[:50]}...")
            return chinese_text

        # Check if text is just numbers or simple alphanumeric (like checking IDs or file paths)
        # Matches strings like "123", "v1.0", "/path/to/file", "filename.ext"
        if re.match(r'^[\w\-\./]+$', chinese_text.strip()):
            logger.info(f"Skipping translation for alphanumeric/path: {chinese_text[:50]}...")
            return chinese_text

        logger.info(f"Translating text: {chinese_text[:50]}...")

        prompt = self.prompt_template.format(text=chinese_text)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
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

    def generate_title(self, content_snippet: str) -> str:
        """
        Generate a title from content snippet

        Args:
            content_snippet: First few lines/paragraphs of the content

        Returns:
            Generated title in Japanese
        """
        if not content_snippet or not content_snippet.strip():
            return "Untitled Page"

        prompt = (
            "あなたは編集者です。\n"
            "以下の記事の冒頭部分を読んで、内容を適切に表す30文字以内の日本語タイトルを作成してください。\n"
            "タイトルのみを出力し、カギカッコや説明は含めないでください。\n\n"
            "記事冒頭:\n"
            f"{content_snippet[:1000]}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "あなたは優秀な編集者です。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=100
            )

            title = response.choices[0].message.content.strip()
            # Remove quotes if present
            title = re.sub(r'^["「『]|["」』]$', '', title)
            logger.info(f"Generated title: {title}")
            return title

        except Exception as e:
            logger.error(f"Title generation error: {e}")
            return "タイトル自動生成エラー"
