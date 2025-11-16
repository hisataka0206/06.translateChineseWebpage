"""
Test a different approach - translate without "extracting"
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

print("Testing translation with a different approach...\n")

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Please help me translate this technical diagram from Chinese to Japanese. "
                        "List all the Chinese labels and text you see in the image, "
                        "and provide the Japanese translation for each. "
                        "Format each as: Chinese text|Japanese translation"
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

# Parse the response
print("\nParsing translations...")
lines = content.split('\n')
count = 0
for line in lines:
    if '|' in line:
        count += 1
        print(f"{count}. {line}")

print(f"\nTotal translations found: {count}")
