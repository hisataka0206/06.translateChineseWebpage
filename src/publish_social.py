
import os
import sys
import yaml
import logging
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.notion.client import NotionClient
from src.publisher.x_publisher import XPublisher
from src.publisher.linkedin_publisher import LinkedInPublisher
from src.notion.parser import NotionBlockParser

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)

def run_social_publish():
    logger.info("Starting Social Auto-Publisher (DB Driven)...")
    load_dotenv()
    config = load_config()
    
    # Setup Notion Client
    notion_api_key = os.getenv("NOTION_TOKEN") or config["notion"]["token"]
    notion = NotionClient(api_key=notion_api_key)
    
    # Initialize Publishers
    x_publisher = XPublisher(config)
    linkedin_publisher = LinkedInPublisher(config)
    
    # Destination DB ID
    dest_id = config["notion"]["destination_parent_id"]
    if "?" in dest_id: dest_id = dest_id.split("?")[0]
    
    logger.info(f"Scanning DB: {dest_id}...")
    
    # Filter: (X post starts with 'Go') OR (LinkedIn post starts with 'Go')
    # Notion API strict filter logic is a bit complex for OR with selects.
    # We can fetch pages where X post is Go OR LinkedIn post is Go.
    # Or just fetch all active pages? No, that's too many.
    # Simple approach: Fetch separately or use compound filter (OR).
    
    filter_criteria = {
        "or": [
            {
                "property": "X post",
                "select": {
                    "equals": "Go"
                }
            },
            {
                "property": "LinkedIn post",
                "select": {
                    "equals": "Go"
                }
            }
        ]
    }
    
    try:
        pages = notion.query_database(dest_id, filter_criteria)
    except Exception as e:
        logger.error(f"Failed to query database: {e}")
        return

    if not pages:
        logger.info("No pages found with 'Go' status for X or LinkedIn.")
        return
        
    logger.info(f"Found {len(pages)} pages to process.")
    
    parser = NotionBlockParser()
    
    for page in pages:
        page_id = page["id"]
        title = parser.get_page_title(page)
        logger.info(f"Processing: {title} ({page_id})")
        
        # 0. Common Data Preparation
        page_url = page.get("public_url")
        if not page_url:
            page_url = page.get("url") or f"https://notion.so/{page_id.replace('-', '')}"
            logger.info(f"Page not published (public_url is null). Using internal URL: {page_url}")
        else:
            logger.info(f"Using Public URL: {page_url}")
        
        props_to_update = {}
        
        # --- X Publishing ---
        x_status = page.get("properties", {}).get("X post", {}).get("select")
        if x_status and x_status.get("name") == "Go":
            logger.info(">>> Processing X Post...")
            try:
                # Get/Gen Comment
                existing_comment = ""
                x_comment_prop = page.get("properties", {}).get("X comment", {})
                if x_comment_prop.get("rich_text"):
                    existing_comment = x_comment_prop["rich_text"][0]["plain_text"]
                
                post_text = existing_comment
                if not post_text:
                    post_text = x_publisher.generate_post_text(title, title)
                    # Queue update to save generated text
                    props_to_update["X comment"] = {"rich_text": [{"text": {"content": post_text}}]}
                
                if x_publisher.post(title, page_url, override_text=post_text):
                    props_to_update["X post"] = {"select": {"name": "Done"}}
                    logger.info("X Post Successful.")
                else:
                    logger.error("X Post Failed.")
            except Exception as e:
                logger.error(f"Error processing X post: {e}")

        # --- LinkedIn Publishing ---
        li_status = page.get("properties", {}).get("LinkedIn post", {}).get("select")
        if li_status and li_status.get("name") == "Go":
            logger.info(">>> Processing LinkedIn Post...")
            try:
                # Get/Gen Comment
                existing_comment = ""
                li_comment_prop = page.get("properties", {}).get("LinkedIn comment", {})
                if li_comment_prop.get("rich_text"):
                    existing_comment = li_comment_prop["rich_text"][0]["plain_text"]
                
                post_text = existing_comment
                if not post_text:
                    post_text = linkedin_publisher.generate_post_text(title, title)
                    # Queue update to save generated text
                    props_to_update["LinkedIn comment"] = {"rich_text": [{"text": {"content": post_text}}]}
                
                if linkedin_publisher.post(title, page_url, override_text=post_text):
                    props_to_update["LinkedIn post"] = {"select": {"name": "Done"}}
                    logger.info("LinkedIn Post Successful.")
                else:
                    logger.error("LinkedIn Post Failed.")
            except Exception as e:
                logger.error(f"Error processing LinkedIn post: {e}")

        # --- Update Notion ---
        if props_to_update:
            try:
                notion.update_page_properties(page_id, props_to_update)
                logger.info("Updated Notion properties.")
            except Exception as e:
                logger.error(f"Failed to update Notion: {e}")

    logger.info("Social publishing cycle completed.")

if __name__ == "__main__":
    run_social_publish()
