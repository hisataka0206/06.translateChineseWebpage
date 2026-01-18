"""
Notion Publisher
Publishes translated content to new Notion pages
"""

import logging
from typing import List, Dict, Any
from src.notion.client import NotionClient
from src.translation.translator import TextTranslator
from src.translation.image_translator import ImageTextTranslator
from src.formatting.toggle_formatter import ToggleFormatter
from src.notion.parser import NotionBlockParser

logger = logging.getLogger(__name__)


class NotionPublisher:
    """Publisher for creating translated Notion pages"""

    def __init__(
        self,
        notion_client: NotionClient,
        text_translator: TextTranslator,
        image_translator: ImageTextTranslator
    ):
        """
        Initialize publisher

        Args:
            notion_client: Notion API client
            text_translator: Text translation service
            image_translator: Image text extraction and translation service
        """
        self.notion = notion_client
        self.text_translator = text_translator
        self.image_translator = image_translator
        self.parser = NotionBlockParser()
        self.formatter = ToggleFormatter()

    def translate_and_publish_page(
        self,
        source_page_id: str,
        destination_parent_id: str
    ) -> Dict[str, Any]:
        """
        Translate a Chinese Notion page and publish to Japanese parent

        Args:
            source_page_id: Source Chinese page ID
            destination_parent_id: Destination parent page ID for Japanese version

        Returns:
            Dict with result information
        """
        logger.info(f"Starting translation: {source_page_id}")

        # Get source page
        source_page = self.notion.get_page(source_page_id)

        # Check if already translated
        if self.notion.is_already_translated(source_page):
            logger.info(f"Page already translated (title starts with 'done'): {source_page_id}")
            return {
                "status": "skipped",
                "reason": "already_translated",
                "source_page_id": source_page_id
            }

        # Get page title and translate
        original_title = self.parser.get_page_title(source_page)
        translated_title = self.text_translator.translate(original_title)
        final_title = f"done {translated_title}"

        logger.info(f"Translating page: {original_title} -> {translated_title}")

        # Get page blocks (content)
        source_blocks = self.notion.get_page_blocks(source_page_id)

        # Process blocks and create translated version
        translated_blocks = self._process_blocks(source_blocks)

        # Slice blocks into chunks of 100 (Notion API limit)
        LIMIT = 100
        first_batch = translated_blocks[:LIMIT]
        remaining_batches = [translated_blocks[i:i + LIMIT] for i in range(LIMIT, len(translated_blocks), LIMIT)]

        # Create new Japanese page with first batch
        new_page = self.notion.create_page(
            parent_id=destination_parent_id,
            title=final_title,
            children=first_batch
        )

        new_page_id = new_page["id"]
        logger.info(f"Created initial page with {len(first_batch)} blocks. ID: {new_page_id}")

        # Append remaining batches
        if remaining_batches:
            logger.info(f"Appending {len(remaining_batches)} additional batches...")
            for i, batch in enumerate(remaining_batches, 1):
                try:
                    logger.info(f"Appending batch {i}/{len(remaining_batches)} ({len(batch)} blocks)")
                    self.notion.append_block_children(
                        block_id=new_page_id,
                        children=batch
                    )
                except Exception as e:
                    logger.error(f"Failed to append batch {i}: {e}")
                    # Continue attempting valid batches instead of full failure? 
                    # For now just log, but page creation succeeded so we return blocking error maybe
                    raise e

        # Update original page title with "done" prefix
        self.notion.update_page_title(
            page_id=source_page_id,
            new_title=f"done {original_title}"
        )

        logger.info(f"Translation complete. New page ID: {new_page['id']}")

        return {
            "status": "success",
            "source_page_id": source_page_id,
            "new_page_id": new_page["id"],
            "original_title": original_title,
            "translated_title": translated_title
        }

    def _process_blocks(self, blocks: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """
        Process and translate all blocks from source page

        Args:
            blocks: List of source blocks

        Returns:
            List of translated blocks
        """
        translated_blocks = []

        for block in blocks:
            block_type = block.get("type")

            if block_type == "image":
                # Process image with translation table in toggle
                image_block = self._process_image_block(block)
                translated_blocks.append(image_block)

            elif block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item"]:
                # Translate text blocks
                text_block = self._process_text_block(block, block_type)
                if text_block:
                    translated_blocks.append(text_block)

            elif block_type == "table":
                # Add placeholder for tables (cannot auto-translate complex structures)
                logger.info("Skipping table block (not supported for auto-translation)")
                translated_blocks.append(
                    self.formatter.create_text_block("📊 [テーブル: 自動翻訳未対応。元のページを参照してください]")
                )

            else:
                logger.warning(f"Unsupported block type: {block_type}")
                # Could add support for more block types here

        return translated_blocks

    def _process_image_block(self, block: Dict[Any, Any]) -> Dict[Any, Any]:
        """
        Process image block: extract text and create toggle with translation table

        Args:
            block: Image block from source page

        Returns:
            Toggle block with image and translation table
        """
        image_data = block.get("image", {})
        image_type = image_data.get("type")

        if image_type == "external":
            image_url = image_data.get("external", {}).get("url")
        elif image_type == "file":
            image_url = image_data.get("file", {}).get("url")
        else:
            image_url = None

        if not image_url:
            logger.warning("No image URL found")
            return self.formatter.create_text_block("画像URLが見つかりません")

        # Skip image text extraction and translation
        # result = self.image_translator.extract_and_translate_image_text(image_url)
        # translations = result.get("translations", [])

        # Simply return the image block without toggle or translation
        logger.info(f"Skipping image translation for: {image_url}")

        return {
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": image_url}
            }
        }

    def _process_text_block(
        self,
        block: Dict[Any, Any],
        block_type: str
    ) -> Dict[Any, Any]:
        """
        Process and translate text block

        Args:
            block: Text block from source page
            block_type: Type of block (paragraph, heading, etc.)

        Returns:
            Translated text block
        """
        # Extract text
        text = self.parser.extract_text_from_block(block)

        if not text or not text.strip():
            return None

        # Translate text
        translated_text = self.text_translator.translate(text)

        # Create appropriate block type
        if block_type == "paragraph":
            return self.formatter.create_text_block(translated_text)

        elif block_type.startswith("heading"):
            level = block_type.split("_")[1]
            return {
                "object": "block",
                "type": block_type,
                block_type: {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": translated_text}
                        }
                    ]
                }
            }

        elif block_type in ["bulleted_list_item", "numbered_list_item"]:
            return {
                "object": "block",
                "type": block_type,
                block_type: {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": translated_text}
                        }
                    ]
                }
            }

        # Default: return as paragraph
        return self.formatter.create_text_block(translated_text)
