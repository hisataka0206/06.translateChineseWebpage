
import os
import yaml
import json
from notion_client import Client
from dotenv import load_dotenv

def load_config(config_path="config/config.yaml"):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def main():
    load_dotenv()
    config = load_config()
    
    token = os.getenv("NOTION_TOKEN") or config["notion"]["token"]
    db_id = config["notion"].get("chinese_dictionary_id")
    
    if not db_id:
        print("Error: chinese_dictionary_id not found in config")
        return

    # Clean ID if it has query params
    if "?" in db_id:
        db_id = db_id.split("?")[0]
        
    client = Client(auth=token)
    
    try:
        print(f"Retrieving database: {db_id}")
        db = client.databases.retrieve(database_id=db_id)
        
        print("\nDatabase Properties:")
        properties = db.get("properties", {})
        for name, prop in properties.items():
            print(f"- Name: '{name}' | Type: {prop['type']}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
