import os
import json
import yaml
from dotenv import load_dotenv
from notion_client import Client

class VocabManager:
    def __init__(self, config_path="config/config.yaml", data_dir="data"):
        self.data_dir = data_dir
        self.local_json_path = os.path.join(data_dir, "local_vocab.json")
        
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
        # Load Config
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
            
        load_dotenv()
        
        self.notion_token = os.getenv("NOTION_TOKEN") or (self.config.get("notion") or {}).get("token")
        self.chinese_dictionary_id = (self.config.get("notion") or {}).get("chinese_dictionary_id")
        
        if self.chinese_dictionary_id:
             self.db_id = self.chinese_dictionary_id.split("?")[0]
        else:
             self.db_id = None

    def download_from_notion(self):
        """Fetches from Notion and saves to local JSON"""
        if not self.notion_token or not self.db_id:
             raise ValueError("Notion credentials not fully configured.")
             
        notion = Client(auth=self.notion_token)
        results = []
        has_more = True
        start_cursor = None
        
        while has_more:
            response = notion.databases.query(
                database_id=self.db_id,
                start_cursor=start_cursor
            )
            results.extend(response.get("results", []))
            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")
                
        vocab_list = []
        for page in results:
            props = page.get("properties", {})
            word = ""
            if "Word" in props and "title" in props["Word"]:
                title_arr = props["Word"]["title"]
                word = "".join([t.get("plain_text", "") for t in title_arr])
            
            meaning = ""
            if "Meaning_ja" in props and "rich_text" in props["Meaning_ja"]:
                rt_arr = props["Meaning_ja"]["rich_text"]
                meaning = "".join([t.get("plain_text", "") for t in rt_arr])
                    
            pinyin = ""
            if "Pinyin" in props and "rich_text" in props["Pinyin"]:
                rt_arr = props["Pinyin"]["rich_text"]
                pinyin = "".join([t.get("plain_text", "") for t in rt_arr])
                    
            context_cn = ""
            if "ContextCn" in props and "rich_text" in props["ContextCn"]:
                rt_arr = props["ContextCn"]["rich_text"]
                context_cn = "".join([t.get("plain_text", "") for t in rt_arr])
            
            if word and meaning:
                vocab_list.append({
                    "word": word,
                    "meaning": meaning,
                    "pinyin": pinyin,
                    "context_cn": context_cn
                })
                
        # Save to Local JSON
        with open(self.local_json_path, "w", encoding="utf-8") as f:
             json.dump(vocab_list, f, ensure_ascii=False, indent=2)
             
        return vocab_list
        
    def load_local_data(self):
        """Loads vocabulary from local JSON"""
        if not os.path.exists(self.local_json_path):
             return []
        with open(self.local_json_path, "r", encoding="utf-8") as f:
             return json.load(f)
             
    def has_local_data(self):
        """Checks if local data exists"""
        if not os.path.exists(self.local_json_path):
            return False
        data = self.load_local_data()
        return len(data) >= 4 # Quiz needs at least 4 items

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Download Notion Vocabulary to JSON for Static Site")
    parser.add_argument("--outdir", default="src/quiz/web/static", help="Directory to save local_vocab.json")
    args = parser.parse_args()
    
    # Try to load env/config, fallback to just env if in GitHub actions
    manager = VocabManager(data_dir=args.outdir)
    print(f"Downloading from Notion to {manager.local_json_path} ...")
    data = manager.download_from_notion()
    print(f"Success! {len(data)} words downloaded and saved.")
