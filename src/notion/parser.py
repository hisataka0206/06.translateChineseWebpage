"""
Notion Block Parser
Extracts text and images from Notion blocks
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class NotionBlockParser:
    """Parser for Notion block content"""

    @staticmethod
    def extract_text_from_block(block: Dict[Any, Any]) -> str:
        """
        Extract plain text from a Notion block

        Args:
            block: Notion block object

        Returns:
            Extracted text content
        """
        block_type = block.get("type")

        if not block_type:
            return ""

        block_content = block.get(block_type, {})
        rich_text = block_content.get("rich_text", [])

        text_parts = []
        for text_obj in rich_text:
            text_parts.append(text_obj.get("plain_text", ""))

        return "".join(text_parts)

    @staticmethod
    def extract_images_from_blocks(blocks: List[Dict[Any, Any]]) -> List[Dict[str, str]]:
        """
        Extract all image URLs from blocks

        Args:
            blocks: List of Notion block objects

        Returns:
            List of dicts with image info (url, type, etc.)
        """
        images = []

        for block in blocks:
            if block.get("type") == "image":
                image_data = block.get("image", {})
                image_type = image_data.get("type")

                if image_type == "external":
                    url = image_data.get("external", {}).get("url")
                elif image_type == "file":
                    url = image_data.get("file", {}).get("url")
                else:
                    url = None

                if url:
                    images.append({
                        "url": url,
                        "type": image_type,
                        "block_id": block.get("id")
                    })

        return images

    @staticmethod
    def get_page_title(page: Dict[Any, Any]) -> str:
        """
        Extract page title from page object

        Args:
            page: Notion page object

        Returns:
            Page title string
        """
        title_property = page.get("properties", {}).get("title", {})
        title_array = title_property.get("title", [])

        if not title_array:
            return "Untitled"

        return title_array[0].get("plain_text", "Untitled")
