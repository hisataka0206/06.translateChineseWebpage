
import os
import sys
import logging
import yaml
import json
# Add project root to path
sys.path.append(os.getcwd())

from src.notion.client import NotionClient
from src.publisher.notion_publisher import NotionPublisher

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)

def inspect_blocks():
    config = load_config()
    notion_api_key = config["notion"]["token"]
    
    # The failing page ID
    page_id = "2edcd557-2261-8187-b6fc-d1fb47270887"
    
    client = NotionClient(api_key=notion_api_key)
    
    # We need a dummy publisher to access _sanitize_blocks_for_copy
    # Pass None for translators as we won't use them
    publisher = NotionPublisher(client, None, None)
    
    logger.info(f"Fetching blocks for page {page_id}...")
    blocks = client.get_page_blocks(page_id)
    
    logger.info(f"Total blocks: {len(blocks)}")
    
    # Inspect block 5 (and surrounding)
    target_indices = [4, 5, 6]
    
    for idx in target_indices:
        if idx < len(blocks):
            block = blocks[idx]
            print(f"\n--- Block {idx} Raw ---")
            print(json.dumps(block, indent=2, ensure_ascii=False))
            
            # Test sanitization
            sanitized_list = publisher._sanitize_blocks_for_copy([block])
            if sanitized_list:
                print(f"--- Block {idx} Sanitized ---")
                print(json.dumps(sanitized_list[0], indent=2, ensure_ascii=False))
            else:
                print(f"--- Block {idx} Sanitized Result: REMOVED ---")

if __name__ == "__main__":
    inspect_blocks()
