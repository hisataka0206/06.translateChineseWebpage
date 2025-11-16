"""
Debug image text extraction to see actual GPT response
"""

import os
from dotenv import load_dotenv
from openai import OpenAI
import requests
import base64

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Test with one of the actual image URLs
test_image_url = "https://mmbiz.qpic.cn/sz_mmbiz_png/nKJJU3IO9Elyia9qcCZ8sa7DJbzMCCoKxzMJN95nPjj88PtHYttkdT1eLnl1QlJR74RHwPIjV9ghaFaaM5l7SJA/640?wx_fmt=png&from=appmsg&wxfrom=5&wx_lazy=1&tp=webp"

print("Downloading image...")
response = requests.get(test_image_url, timeout=30)
content_type = response.headers.get('Content-Type', 'image/png')
base64_image = base64.b64encode(response.content).decode('utf-8')
data_uri = f"data:{content_type};base64,{base64_image}"

print(f"Image size: {len(response.content)} bytes")
print(f"Content type: {content_type}")
print(f"Base64 size: {len(base64_image)} chars\n")

print("Sending to GPT-4o...")

gpt_response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "You are an OCR assistant for technical documentation. "
                        "Please extract ALL Chinese text visible in this image and translate each to Japanese. "
                        "This is for educational and technical translation purposes.\n\n"
                        "IMPORTANT: Return ONLY the translations in this exact format (one per line):\n"
                        "Chinese text|Japanese translation\n\n"
                        "Example:\n"
                        "人形机器人|人形ロボット\n"
                        "关节|関節\n\n"
                        "If there is absolutely no text, respond with: NO_TEXT"
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": data_uri,
                        "detail": "high"
                    }
                }
            ]
        }
    ],
    max_tokens=2000,
    temperature=0.1
)

content = gpt_response.choices[0].message.content

print("="*80)
print("FULL GPT RESPONSE:")
print("="*80)
print(content)
print("="*80)
