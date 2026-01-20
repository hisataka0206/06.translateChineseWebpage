
import os
import yaml
from google import genai
from dotenv import load_dotenv

def list_models():
    # Load Config to get key the same way extractor does
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)
        
    load_dotenv()
    
    # Logic from extractor
    api_key = config.get("GOOGLE_API_KEY")
    if not api_key and "openai" in config:
            api_key = config["openai"].get("GOOGLE_API_KEY") 
    if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY")
            
    if not api_key:
        print("API Key not found")
        return

    client = genai.Client(api_key=api_key)
    try:
        print("Listing models...")
        # The method to list models might be different in google-genai 0.3.0 vs older lib
        # Trying common patterns
        models_iter = client.models.list() 
        for model in models_iter:
            print(f"- {model.name}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_models()
