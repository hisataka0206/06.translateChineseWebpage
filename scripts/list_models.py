
import os
import yaml
from google import genai
from dotenv import load_dotenv

def load_config(config_path="config/config.yaml"):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def main():
    load_dotenv()
    config = load_config()
    
    api_key = os.getenv("GOOGLE_API_KEY") or config.get("google", {}).get("api_key")
    if not api_key:
        print("No API Key found")
        return

    client = genai.Client(api_key=api_key)
    
    print("List of available models:")
    try:
        count = 0
        for model in client.models.list():
            count += 1
            print(f"- {model.name}")
        
        if count == 0:
            print("No models found in the list.")
            
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    main()
