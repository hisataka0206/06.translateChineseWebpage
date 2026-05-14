"""
Toggle Block Formatter
Creates collapsible toggle blocks in Notion for translation tables
"""

import logging
from typing import List, Dict, Any

from src.utils.notion_text import (
    SAFE_CHUNK_LIMIT,
    chunk_text,
    make_text_rich_text,
)

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
        # title が 2000 文字を超える可能性は実運用上ほぼ無いが、
        # 万一に備えて make_text_rich_text を通す (自動チャンク)。
        return {
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": make_text_rich_text(title or ""),
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

        # Notion の table cell も rich_text 配列なので、1 セグメント 2000 文字制限が
        # 適用される。長文セルは複数セグメントに分割しておく。
        def _cell(value: Any) -> List[Dict[str, Any]]:
            return make_text_rich_text(str(value) if value is not None else "")

        # Create header row
        table_rows = [
            {
                "cells": [_cell(header) for header in headers]
            }
        ]

        # Add data rows
        for row in rows:
            table_rows.append({
                "cells": [_cell(cell) for cell in row]
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
                # 中国語・日本語どちらも 2000 文字を超え得るので make_text_rich_text を通す。
                rich_text: List[Dict[str, Any]] = []
                rich_text.extend(
                    make_text_rich_text(f"🇨🇳 {chinese}", annotations={"bold": True})
                )
                rich_text.extend(make_text_rich_text(" → "))
                rich_text.extend(make_text_rich_text(f"🇯🇵 {japanese}"))
                content_blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": rich_text}
                })
        else:
            # Add note if no text in image
            content_blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": make_text_rich_text("画像内にテキストはありません。")
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
        Create a simple paragraph block.

        text が Notion の rich_text 1 セグメント上限 (2000 文字) を超える場合は
        同一 paragraph 内で複数セグメントに自動分割される
        (見た目は連続テキストのまま)。

        Args:
            text: Text content

        Returns:
            Notion paragraph block
        """
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": make_text_rich_text(text or "")
            }
        }
