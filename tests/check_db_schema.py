
import os
import sys
import logging
import yaml
# Add project root to path
sys.path.append(os.getcwd())

from src.notion.client import NotionClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)

def check_schema():
    config = load_config()
    notion_api_key = config["notion"]["token"]
    destination_id = config["notion"]["destination_parent_id"]
    
    # Clean ID
    if "?" in destination_id:
        destination_id = destination_id.split("?")[0]
        
    client = NotionClient(api_key=notion_api_key)
    
    logger.info(f"Checking schema for DB: {destination_id}")
    try:
        db = client.client.databases.retrieve(destination_id)
        logger.info("Properties found:")
        for name, prop in db.get("properties", {}).items():
            logger.info(f"- Name: {name}, Type: {prop['type']}")
    except Exception as e:
        logger.error(f"Failed: {e}")

if __name__ == "__main__":
    check_schema()
