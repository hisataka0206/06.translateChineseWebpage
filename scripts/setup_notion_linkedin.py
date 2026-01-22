
import os
import sys
import yaml
import logging

# Add project root to path
sys.path.append(os.getcwd())

from src.notion.client import NotionClient
from dotenv import load_dotenv

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)

def run_setup():
    logger.info("Setting up Notion database for Social Publishing...")
    load_dotenv()
    config = load_config()
    
    # Setup Notion Client
    notion_api_key = os.getenv("NOTION_TOKEN") or config["notion"]["token"]
    if not notion_api_key:
        logger.error("NOTION_TOKEN is missing!")
        return
        
    notion = NotionClient(api_key=notion_api_key)
    
    # Destination DB ID
    dest_id = config["notion"]["destination_parent_id"]
    if "?" in dest_id: dest_id = dest_id.split("?")[0]
    
    logger.info(f"Target Database: {dest_id}")
    
    properties_to_add = {
        "LinkedIn post": {
            "select": {
                "options": [
                    {"name": "Go", "color": "green"},
                    {"name": "Done", "color": "blue"}
                ]
            }
        },
        "LinkedIn comment": {
            "rich_text": {}
        }
    }
    
    try:
        notion.update_database_schema(dest_id, properties_to_add)
        logger.info("Successfully added 'LinkedIn post' and 'LinkedIn comment' properties!")
    except Exception as e:
        logger.error(f"Failed to update database schema: {e}")

if __name__ == "__main__":
    run_setup()
