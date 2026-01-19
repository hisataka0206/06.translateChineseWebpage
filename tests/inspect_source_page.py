
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

def inspect_source():
    config = load_config()
    notion_api_key = config["notion"]["token"]
    source_parent_ids = config["notion"]["source_page_ids"]
    
    client = NotionClient(api_key=notion_api_key)
    
    if not source_parent_ids:
        print("No source parents configured.")
        return

    parent_id = source_parent_ids[0]
    if "?" in parent_id: parent_id = parent_id.split("?")[0]
    
    print(f"Inspecting children of parent: {parent_id}")
    
    # Get children
    try:
        children = client.get_child_page_ids(parent_id)
        if not children:
            print("No children found.")
            return
            
        # Inspect first child
        child_id = children[0]
        print(f"Inspecting Child Page: {child_id}")
        
        page = client.client.pages.retrieve(child_id)
        print("Page Properties:")
        for name, prop in page.get("properties", {}).items():
            prop_type = prop["type"]
            value = prop.get(prop_type)
            print(f"- {name} ({prop_type}): {value}")
            
    except Exception as e:
        logger.error(f"Failed: {e}")

if __name__ == "__main__":
    inspect_source()
