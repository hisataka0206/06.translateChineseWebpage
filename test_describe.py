"""
Test if GPT can at least see/describe the image
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

base64_image = base64.b64encode(image_data).decode('utf-8')

print("Testing if GPT can see the image at all...\n")

# Just ask it to describe what it sees
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "What do you see in this image? Please describe it in detail."
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
    max_tokens=1000
)

content = response.choices[0].message.content

print("="*80)
print("GPT-4o RESPONSE:")
print("="*80)
print(content)
print("="*80)
