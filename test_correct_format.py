"""
Test sending the downloaded image with correct format
"""

import os
from dotenv import load_dotenv
from openai import OpenAI
import base64

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Read the downloaded image
with open('test_image.webp', 'rb') as f:
    image_data = f.read()

# Encode to base64
base64_image = base64.b64encode(image_data).decode('utf-8')

print(f"Image size: {len(image_data)} bytes")
print(f"Base64 size: {len(base64_image)} chars")
print(f"First 100 chars of base64: {base64_image[:100]}")
print("\nSending to GPT-4o with correct WebP format...\n")

# Send to GPT-4o with proper WebP mime type
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Please analyze this image and extract ALL Chinese text you can see. "
                        "Translate each Chinese phrase to Japanese. "
                        "Format: Chinese|Japanese (one per line). "
                        "If no text, say NO_TEXT."
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/webp;base64,{base64_image}",
                        "detail": "high"
                    }
                }
            ]
        }
    ],
    max_tokens=3000,
    temperature=0.1
)

content = response.choices[0].message.content

print("="*80)
print("GPT-4o RESPONSE:")
print("="*80)
print(content)
print("="*80)
