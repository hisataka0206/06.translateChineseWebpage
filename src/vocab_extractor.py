import os
import json
import logging
import yaml
import pandas as pd
import time
from collections import deque
from typing import List, Dict, Any
from notion_client import Client
from google import genai
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VocabExtractor:
    def __init__(self, config_path: str = "config/config.yaml"):
        # Load Config
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
            
        load_dotenv()
        
        # Notion Setup
        self.notion_token = os.getenv("NOTION_TOKEN") or self.config["notion"]["token"]
        if not self.notion_token:
             raise ValueError("NOTION_TOKEN not found in environment or config.")
        self.notion = Client(auth=self.notion_token)
        self.target_parent_id = self.config["vocab_extraction"]["target_parent_id"]
        
        # Gemini Setup
        api_key = os.getenv("GOOGLE_API_KEY") or self.config.get("GOOGLE_API_KEY")
             
        if not api_key:
             # Fallback manual check for the specific indentation user might have used
             # based on previous file view, user put it at the end
             pass

        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in config.yaml or environment variables.")
            
        self.client = genai.Client(api_key=api_key)
        self.model_name = self.config["openai"].get("vocab_model", "gemini-1.5-flash")
        
        self.output_file = self.config["vocab_extraction"].get("output_file", "robot_vocab.xlsx")
        self.chinese_dictionary_id = self.config["notion"].get("chinese_dictionary_id")
        
        # Rate Limiting
        self.request_history = deque()
        self.rpm_limit = 15

    def get_child_pages(self, parent_id: str) -> List[Dict[str, Any]]:
        """Fetch all child pages from the parent ID (block or database)"""
        logger.info(f"Fetching child pages for: {parent_id}")
        results = []
        has_more = True
        start_cursor = None
        
        while has_more:
            try:
                # First try fetching as block children (page parent)
                response = self.notion.blocks.children.list(
                    block_id=parent_id,
                    start_cursor=start_cursor
                )
            except Exception:
                # Fallback to database query if parent is a database
                logger.info("Parent might be a database, trying query...")
                try:
                    response = self.notion.databases.query(
                        database_id=parent_id,
                        start_cursor=start_cursor
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch children: {e}")
                    return []

            results.extend(response["results"])
            has_more = response["has_more"]
            start_cursor = response["next_cursor"]
            
        # Filter:
        # 1. Database Query results are object='page'
        # 2. Block List results (Child Pages) are object='block' and type='child_page'
        pages = []
        for r in results:
            if r["object"] == "page":
                pages.append(r)
            elif r["object"] == "block" and r.get("type") == "child_page":
                # Convert child_page block to a minimal page object for consistency
                # The ID is the same
                pages.append({
                    "id": r["id"],
                    "url": f"https://notion.so/{r['id'].replace('-', '')}", # Construct approximated URL
                    "child_page": r["child_page"], # Contains title
                    "object": "page" # Treat as page downstream
                })
        
        logger.info(f"Found {len(pages)} pages.")
        return pages

    def get_page_text(self, page_id: str) -> str:
        """Fetch and concatenate text blocks from a page"""
        all_text = []
        has_more = True
        start_cursor = None
        
        while has_more:
            response = self.notion.blocks.children.list(
                block_id=page_id,
                start_cursor=start_cursor
            )
            
            for block in response["results"]:
                block_type = block["type"]
                text_content = ""
                
                if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item"]:
                    rich_text = block[block_type].get("rich_text", [])
                    if rich_text:
                        text_content = "".join([t["plain_text"] for t in rich_text])
                        
                if text_content:
                    all_text.append(text_content)
            
            has_more = response["has_more"]
            start_cursor = response["next_cursor"]
            
        return "\n".join(all_text)
    
    def _enforce_rate_limit(self):
        """Enforce 15 RPM using a sliding window"""
        now = time.time()
        
        # Remove old requests > 60s ago
        while self.request_history and self.request_history[0] < now - 60:
            self.request_history.popleft()
            
        # Check current Load
        if len(self.request_history) >= self.rpm_limit:
            # Must wait until the oldest request expires
            wait_time = (self.request_history[0] + 60) - now + 1 # +1s buffer
            if wait_time > 0:
                logger.info(f"Rate limit approaching ({len(self.request_history)}/{self.rpm_limit}). Waiting {wait_time:.2f}s...")
                time.sleep(wait_time)
                # After waiting, we can proceed. The oldest will expire by "now + wait_time".
                # To be precise, we recursively check (or just clear old again)
                now = time.time()
                while self.request_history and self.request_history[0] < now - 60:
                    self.request_history.popleft()

        # Record this request
        self.request_history.append(now)

    def extract_terms(self, text: str) -> List[Dict[str, str]]:
        """Extract Chinese robot terms using Gemini"""
        if not text:
            return []
            
        prompt = """
        You are a translation expert specializing in Robotics.
        Task: Extract Chinese technical terms related to robotics (humanoids, hardware, AI control) from the text.
        
        Rules:
        1. Exclude common verbs and pronouns.
        2. Return ONLY a JSON list.
        3. Format:
        [
          {
            "word": "Original Word (Simplified Chinese)",
            "pinyin": "Pinyin",
            "meaning_ja": "Japanese Translation",
            "context_cn": "Short context sentence from text"
          }
        ]
        """
        
        try:
            # Enforce Rate Limit before making the call
            self._enforce_rate_limit()
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt + "\n\nText:\n" + text]
            )
            
            # cleanup code blocks if present
            cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_text)
        except Exception as e:
            # Re-raise exception so the caller can handle 429 retries
            raise e

    def export_to_notion(self, df: pd.DataFrame):
        """Export aggregated terms to Notion Database"""
        if not self.chinese_dictionary_id:
            logger.error("No chinese_dictionary_id found in config. Cannot export to Notion.")
            return

        # Prepare ID - remove query params if present
        db_id = self.chinese_dictionary_id.split("?")[0]
        logger.info(f"Exporting {len(df)} terms to Notion DB: {db_id}")

        for index, row in df.iterrows():
            word = row['word']
            # Safeguard NaN
            pinyin = str(row['pinyin']) if pd.notna(row['pinyin']) else ""
            meaning = str(row['meaning_ja']) if pd.notna(row['meaning_ja']) else ""
            context = str(row['context_cn']) if pd.notna(row['context_cn']) else ""
            source_title = str(row['source_title']) if pd.notna(row['source_title']) else ""
            source_url = str(row['source_url']) if pd.notna(row['source_url']) else "" # Note: Simple string for now in Rich Text or URL
            frequency = int(row['frequency']) if pd.notna(row['frequency']) else 1
            
            try:
                # Construct Properties
                properties = {
                    "Word": {"title": [{"text": {"content": word}}]},
                    "PinYin": {"rich_text": [{"text": {"content": pinyin}}]},
                    "Meaning_ja": {"rich_text": [{"text": {"content": meaning}}]},
                    "ContextCn": {"rich_text": [{"text": {"content": context}}]},
                    "Source Title": {"rich_text": [{"text": {"content": source_title}}]},
                    "Frequency": {"number": frequency} 
                }
                
                # Source URL is not in the database schema, so we skip it.
                # If the user wants it, they need to add the property to Notion first.
                
                self.notion.pages.create(
                    parent={"database_id": db_id},
                    properties=properties
                )
                logger.info(f"  Saved: {word} ({meaning})")
                time.sleep(0.5) # Slight delay to be nice to Notion API

            except Exception as e:
                logger.error(f"Failed to save term '{word}': {e}")


    def run(self, limit: int = None):
        """Main execution flow"""
        pages = self.get_child_pages(self.target_parent_id)
        if limit:
            pages = pages[:limit]
            
        all_terms = []
        
        for i, page in enumerate(pages):
            # Get Title
            title = "Untitled"
            if "properties" in page:
                 # Handle Database Properties (Title)
                for prop in page["properties"].values():
                    if prop["type"] == "title":
                        title = "".join([t["plain_text"] for t in prop["title"]])
                        break
            
            # Handle Page in Page (child_page)
            if "child_page" in page:
                 title = page["child_page"].get("title", "Untitled")

            page_url = page["url"]
            logger.info(f"[{i+1}/{len(pages)}] Processing: {title}")
            
            # Get Text
            text = self.get_page_text(page["id"])
            if not text:
                logger.warning("No text found, skipping.")
                continue
                
            # Extract with retry
            terms = []
            max_retries = 5
            base_wait = 60
            
            for attempt in range(max_retries):
                try:
                    terms = self.extract_terms(text)
                    if terms: # If successful/empty list returned without error
                        break
                except Exception as e:
                    # Check for rate limit error in the exception string or type
                    error_str = str(e)
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        wait_time = base_wait * (attempt + 1)
                        logger.warning(f"Rate limit hit. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Extraction error: {e}")
                        break
            
            logger.info(f"  Extracted {len(terms)} terms.")
            
            # Append Metadata
            for term in terms:
                term["source_title"] = title
                term["source_url"] = page_url
                all_terms.append(term)
            
            # Note: Fixed sleep removed as _enforce_rate_limit handles it now.

        # Aggregate and Export
        if not all_terms:
            logger.warning("No terms extracted.")
            return

        df = pd.DataFrame(all_terms)
        
        # Simple aggregation: Group by word
        # We will keep the first occurrence for meaning/pinyin, and count frequency
        agg_df = df.groupby('word').agg({
            'pinyin': 'first',
            'meaning_ja': 'first',
            'word': 'count', # Frequency
            'source_title': lambda x: ", ".join(set(x)),
            'context_cn': 'first',
             # For Source URL, we just take the first one (or could join unique like title)
            'source_url': 'first' 
        }).rename(columns={'word': 'frequency'})
        
        agg_df = agg_df.reset_index()
        
        # Save to Notion instead of Excel
        # agg_df.to_excel(self.output_file, index=False)
        # logger.info(f"Saved vocabulary to {self.output_file}")
        
        self.export_to_notion(agg_df)
        logger.info("Export to Notion completed.")

if __name__ == "__main__":
    extractor = VocabExtractor()
    # Run with limit=1 for verification
    extractor.run(limit=1)
