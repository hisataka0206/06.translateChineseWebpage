
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

def inspect_dest():
    config = load_config()
    notion_api_key = config["notion"]["token"]
    dest_id = config["notion"]["destination_parent_id"]
    if "?" in dest_id: dest_id = dest_id.split("?")[0]
    
    client = NotionClient(api_key=notion_api_key)
    
    print(f"Inspecting DB: {dest_id}")
    
    # query db
    try:
        results = client.client.databases.query(dest_id, page_size=1)
        pages = results.get("results", [])
        if not pages:
            print("No pages in DB.")
            return

        page = pages[0]
        print(f"Inspecting Page: {page['id']}")
        for name, prop in page.get("properties", {}).items():
            prop_type = prop["type"]
            val = prop.get(prop_type)
            print(f"- {name} ({prop_type}): {val}")
            
    except Exception as e:
        logger.error(f"Failed: {e}")

if __name__ == "__main__":
    inspect_dest()
