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

    UNWANTED_TEXTS = [
        "点击蓝字 关注我们",
        "关注公众号，点击公众号主页右上角“ · · · ”，设置星标，实时关注人形机器人新鲜的行业动态与知识！"
    ]

    @staticmethod
    def _format_uuid(uuid_str: str) -> str:
        """
        Format a UUID string to have hyphens (XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX)
        """
        if not uuid_str:
            return uuid_str
        
        # If already formatted with hyphens, return as is (simple check)
        if "-" in uuid_str and len(uuid_str) == 36:
            return uuid_str
            
        # If length is 32 (no hyphens), insert them
        if len(uuid_str) == 32:
            return f"{uuid_str[:8]}-{uuid_str[8:12]}-{uuid_str[12:16]}-{uuid_str[16:20]}-{uuid_str[20:]}"
            
        return uuid_str

    def _clean_text(self, text: str) -> str:
        """
        Remove unwanted phrases from text

        Args:
            text: Original text

        Returns:
            Cleaned text, or None if empty
        """
        if not text:
            return None

        for unwanted in self.UNWANTED_TEXTS:
            text = text.replace(unwanted, "")

        cleaned = text.strip()
        return cleaned if cleaned else None

    def translate_and_publish_page(
        self,
        source_page_id: str,
        destination_parent_id: str,
        processed_parent_id: str
    ) -> Dict[str, Any]:
        """
        Translate a Chinese Notion page, publish to Japanese parent, and move source to processed parent

        Args:
            source_page_id: Source Chinese page ID
            destination_parent_id: Destination parent page ID for Japanese version
            processed_parent_id: Destination parent ID for processed source pages

        Returns:
            Dict with result information
        """
        logger.info(f"Starting translation: {source_page_id}")

        # Get source page
        source_page = self.notion.get_page(source_page_id)

        # Skip check for "done" prefix as we are now moving pages
        # But we check for title generation

        # Get page blocks (content) first to help with title generation if needed
        source_blocks = self.notion.get_page_blocks(source_page_id)

        # Get page title
        original_title = self.parser.get_page_title(source_page)
        
        # If title is missing or Untitled, generate it from content
        if not original_title or original_title.strip() == "Untitled":
            logger.info("Title is missing or Untitled. Generating title from content...")
            # Extract first few text blocks for context
            content_snippet = ""
            for block in source_blocks[:10]:
                text = self.parser.extract_text_from_block(block)
                if text:
                    content_snippet += text + "\n"
            
            generated_title = self.text_translator.generate_title(content_snippet)
            translated_title = generated_title
            original_title = f"(Auto-Generated) {translated_title}" # Keep a note it was generated
        else:
            translated_title = self.text_translator.translate(original_title)

        final_title = f"{translated_title}"

        logger.info(f"Translating page: {original_title} -> {translated_title}")

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

        # Move source page to processed parent
        formatted_parent_id = self._format_uuid(processed_parent_id)
        
        logger.info(f"Moving source page {source_page_id} to processed folder {formatted_parent_id}")
        self.notion.move_page(
            page_id=source_page_id,
            target_parent_id=formatted_parent_id
        )
        
        # If title was auto-generated, fix the source title to be clean
        if "(Auto-Generated)" in original_title:
             clean_generated_title = original_title.replace("(Auto-Generated) ", "")
             self.notion.update_page_title(source_page_id, clean_generated_title)

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

        # Clean text first
        text = self._clean_text(text)

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
