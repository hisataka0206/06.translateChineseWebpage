"""
Toggle Block Formatter
Creates collapsible toggle blocks in Notion for translation tables
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ToggleFormatter:
    """Formatter for creating toggle blocks in Notion"""

    @staticmethod
    def create_toggle_block(title: str, content_blocks: List[Dict[Any, Any]]) -> Dict[Any, Any]:
        """
        Create a Notion toggle block with nested content

        Args:
            title: Toggle block title/header
            content_blocks: List of blocks to nest inside the toggle

        Returns:
            Notion toggle block object
        """
        return {
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": title}
                    }
                ],
                "children": content_blocks
            }
        }

    @staticmethod
    def create_table_block(headers: List[str], rows: List[List[str]]) -> Dict[Any, Any]:
        """
        Create a Notion table block

        Args:
            headers: List of column headers
            rows: List of row data (each row is a list of cell values)

        Returns:
            Notion table block object
        """
        table_width = len(headers)

        # Create header row
        table_rows = [
            {
                "cells": [
                    [{"type": "text", "text": {"content": header}}]
                    for header in headers
                ]
            }
        ]

        # Add data rows
        for row in rows:
            table_rows.append({
                "cells": [
                    [{"type": "text", "text": {"content": str(cell)}}]
                    for cell in row
                ]
            })

        return {
            "object": "block",
            "type": "table",
            "table": {
                "table_width": table_width,
                "has_column_header": True,
                "has_row_header": False,
                "children": table_rows
            }
        }

    @staticmethod
    def create_image_translation_toggle(image_url: str, translations: List[tuple]) -> Dict[Any, Any]:
        """
        Create a toggle block containing image and translation table

        Args:
            image_url: URL of the image
            translations: List of (chinese, japanese) translation pairs

        Returns:
            Notion toggle block with image and translation table
        """
        # Create content blocks
        content_blocks = []

        # Add image block
        content_blocks.append({
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": image_url}
            }
        })

        # Add translation as formatted text instead of table (tables don't work nested in toggles)
        if translations:
            # Create a bulleted list for each translation pair
            for chinese, japanese in translations:
                content_blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": f"🇨🇳 {chinese}"},
                                "annotations": {"bold": True}
                            },
                            {
                                "type": "text",
                                "text": {"content": " → "}
                            },
                            {
                                "type": "text",
                                "text": {"content": f"🇯🇵 {japanese}"}
                            }
                        ]
                    }
                })
        else:
            # Add note if no text in image
            content_blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": "画像内にテキストはありません。"}
                        }
                    ]
                }
            })

        # Create toggle wrapping everything
        toggle = ToggleFormatter.create_toggle_block(
            title="画像の翻訳 (クリックして展開)",
            content_blocks=content_blocks
        )

        return toggle

    @staticmethod
    def create_text_block(text: str) -> Dict[Any, Any]:
        """
        Create a simple paragraph block

        Args:
            text: Text content

        Returns:
            Notion paragraph block
        """
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": text}
                    }
                ]
            }
        }
