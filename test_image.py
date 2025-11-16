"""
Test script to debug image text extraction
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Test with one of the actual image URLs from the logs
test_image_url = "https://mmbiz.qpic.cn/sz_mmbiz_png/nKJJU3IO9Elyia9qcCZ8sa7DJbzMCCoKxzMJN95nPjj88PtHYttkdT1eLnl1QlJR74RHwPIjV9ghaFaaM5l7SJA/640?wx_fmt=png&from=appmsg&wxfrom=5&wx_lazy=1&tp=webp"

print("Testing image text extraction...")
print(f"Image URL: {test_image_url}\n")

try:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a helpful OCR assistant. "
                            "Please look at this technical diagram/infographic and extract ALL visible Chinese text from it. "
                            "Then translate each Chinese phrase to Japanese. "
                            "This is for educational and technical documentation purposes.\n\n"
                            "Format your response as:\n"
                            "Chinese text 1|Japanese translation 1\n"
                            "Chinese text 2|Japanese translation 2\n\n"
                            "If you cannot see any text, reply with: NO_TEXT"
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": test_image_url,
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        max_tokens=2000
    )
except Exception as e:
    print(f"Error: {e}")
    exit(1)

content = response.choices[0].message.content
print("="*80)
print("GPT Response:")
print("="*80)
print(content)
print("="*80)
