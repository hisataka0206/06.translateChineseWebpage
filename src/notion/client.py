"""
Notion API Client
Handles reading Chinese pages and creating Japanese pages
"""

from notion_client import Client
import logging

logger = logging.getLogger(__name__)


class NotionClient:
    """Client for interacting with Notion API"""

    def __init__(self, api_key: str):
        """
        Initialize Notion client

        Args:
            api_key: Notion API integration token
        """
        self.client = Client(auth=api_key)

    def get_page(self, page_id: str) -> dict:
        """
        Retrieve a Notion page by ID

        Args:
            page_id: Notion page ID

        Returns:
            Page object with properties and content
        """
        logger.info(f"Fetching page: {page_id}")
        return self.client.pages.retrieve(page_id=page_id)

    def get_page_blocks(self, page_id: str) -> list:
        """
        Retrieve all blocks (content) from a page

        Args:
            page_id: Notion page ID

        Returns:
            List of block objects
        """
        logger.info(f"Fetching blocks for page: {page_id}")
        blocks = []
        has_more = True
        start_cursor = None

        while has_more:
            response = self.client.blocks.children.list(
                block_id=page_id,
                start_cursor=start_cursor
            )
            blocks.extend(response["results"])
            has_more = response["has_more"]
            start_cursor = response.get("next_cursor")

        return blocks

    def is_already_translated(self, page: dict) -> bool:
        """
        Check if page is already translated (title starts with 'done')

        Args:
            page: Notion page object

        Returns:
            True if already translated, False otherwise
        """
        title_property = page.get("properties", {}).get("title", {})
        title_array = title_property.get("title", [])

        if not title_array:
            return False

        title_text = title_array[0].get("plain_text", "")
        return title_text.lower().startswith("done")

    def create_page(self, parent_id: str, title: str, children: list) -> dict:
        """
        Create a new Notion page with translated content

        Args:
            parent_id: Parent page/database ID
            title: Page title (should start with 'done')
            children: List of block objects for page content

        Returns:
            Created page object
        """
        logger.info(f"Creating page: {title}")
        return self.client.pages.create(
            parent={"page_id": parent_id},
            properties={
                "title": {
                    "title": [{"text": {"content": title}}]
                }
            },
            children=children
        )

    def update_page_title(self, page_id: str, new_title: str) -> dict:
        """
        Update page title to mark as translated

        Args:
            page_id: Notion page ID
            new_title: New title (should start with 'done')

        Returns:
            Updated page object
        """
        logger.info(f"Updating page title: {page_id} -> {new_title}")
        return self.client.pages.update(
            page_id=page_id,
            properties={
                "title": {
                    "title": [{"text": {"content": new_title}}]
                }
            }
        )

    def get_child_page_ids(self, page_id: str) -> list[str]:
        """
        Get all child page IDs from a parent page

        Args:
            page_id: Parent page ID

        Returns:
            List of child page IDs
        """
        logger.info(f"Getting child pages for: {page_id}")
        blocks = self.get_page_blocks(page_id)

        child_page_ids = []
        for block in blocks:
            if block.get("type") == "child_page":
                child_id = block.get("id")
                if child_id:
                    child_page_ids.append(child_id)

        logger.info(f"Found {len(child_page_ids)} child pages")
        return child_page_ids

    def append_block_children(self, block_id: str, children: list) -> dict:
        """
        Append blocks to a parent block (or page)

        Args:
            block_id: ID of the parent block or page
            children: List of blocks to append

        Returns:
            The API response dictionary
        """
        logger.info(f"Appending {len(children)} blocks to: {block_id}")
        return self.client.blocks.children.append(
            block_id=block_id,
            children=children
        )
