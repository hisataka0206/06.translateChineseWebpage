
import os
import sys
import yaml
import logging
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.notion.client import NotionClient
from src.publisher.x_publisher import XPublisher
from src.notion.parser import NotionBlockParser

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)

def main():
    logger.info("Starting X Auto-Publisher (DB Driven)...")
    load_dotenv()
    config = load_config()
    
    # Setup Clients
    notion_api_key = config["notion"]["token"]
    notion = NotionClient(api_key=notion_api_key)
    
    # Initialize X Publisher
    x_publisher = XPublisher(config)
    
    # Destination DB ID
    dest_id = config["notion"]["destination_parent_id"]
    if "?" in dest_id: dest_id = dest_id.split("?")[0]
    
    logger.info(f"Scanning DB: {dest_id} for 'Go' status...")
    
    # Query for "X post" == "Go"
    # Note: Select property values are case sensitive usually, assuming "Go" as per user instruction logic.
    # User didn't explicitly confirm "Go" but in USAGE.md user wrote "X post列がGoであれば".
    filter_criteria = {
        "property": "X post",
        "select": {
            "equals": "Go"
        }
    }
    
    try:
        pages = notion.query_database(dest_id, filter_criteria)
    except Exception as e:
        logger.error(f"Failed to query database: {e}")
        return

    if not pages:
        logger.info("No pages found with 'X post' = 'Go'.")
        return
        
    logger.info(f"Found {len(pages)} pages to process.")
    
    parser = NotionBlockParser()
    
    for page in pages:
        page_id = page["id"]
        title = parser.get_page_title(page)
        
        logger.info(f"Processing: {title} ({page_id})")
        
        # 1. Get Content for Post
        # Attempt to read "X comment" property first
        # property structure: {"type": "rich_text", "rich_text": [...]}
        existing_comment = ""
        x_comment_prop = page.get("properties", {}).get("X comment", {})
        if x_comment_prop.get("rich_text"):
            existing_comment = x_comment_prop["rich_text"][0]["plain_text"]
            
        # Try to get Public URL first (for published pages)
        # See refers.md: "The public page URL if the page has been published to the web. Otherwise, null."
        page_url = page.get("public_url")
        
        if not page_url:
            # Fallback to internal URL
            page_url = page.get("url") or f"https://notion.so/{page_id.replace('-', '')}"
            logger.info(f"Page not published (public_url is null). Using internal URL: {page_url}")
        else:
            logger.info(f"Using Public URL: {page_url}")
        
        try:
            # Determine text to post
            if existing_comment:
                logger.info("Using existing X comment text.")
                post_text = existing_comment
            else:
                logger.info("No existing X comment. Generating new text...")
                # Generate Post Text (Fallback)
                gen_title = title # Simple title usage
                post_text = x_publisher.generate_post_text(gen_title, gen_title)
                logger.info(f"Generated text: {post_text}")
            
            # 2. Post to X
            # 2. Post to X
            success = x_publisher.post(
                page_title=title,
                page_url=page_url,
                override_text=post_text
            )
            
            if success:
                # 3. Update DB            
                props_to_update = {
                    "X post": {"select": {"name": "Done"}}
                }
                
                # Only update comment if we generated it newly
                if not existing_comment:
                    props_to_update["X comment"] = {"rich_text": [{"text": {"content": post_text}}]}
                
                notion.update_page_properties(page_id, props_to_update)
                logger.info(f"Updated DB status to 'Done'.")
            else:
                logger.warning(f"Skipping DB update for {page_id} because posting failed.")
                 
        except Exception as e:
            logger.error(f"Failed to process {page_id}: {e}")

    logger.info("Done.")

if __name__ == "__main__":
    main()
