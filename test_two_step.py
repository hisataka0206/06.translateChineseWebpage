"""
Two-step approach: 1) List text, 2) Translate separately
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

print("Step 1: Asking GPT to list all Chinese text it sees...\n")

# Step 1: Just list the text
response1 = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Please list all the Chinese text labels and phrases you can see in this technical diagram. "
                        "Just list them, one per line, without translation."
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
    max_tokens=2000
)

chinese_text = response1.choices[0].message.content

print("="*80)
print("Chinese text found:")
print("="*80)
print(chinese_text)
print("="*80)

# Step 2: Translate the listed text
print("\nStep 2: Translating the listed Chinese text to Japanese...\n")

response2 = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {
            "role": "user",
            "content": (
                f"Please translate each of the following Chinese phrases to Japanese. "
                f"Format: Chinese|Japanese (one per line)\n\n{chinese_text}"
            )
        }
    ],
    max_tokens=2000,
    temperature=0.1
)

translations = response2.choices[0].message.content

print("="*80)
print("Translations:")
print("="*80)
print(translations)
print("="*80)
