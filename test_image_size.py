"""
Check image size and try with compressed version
"""

import requests
from PIL import Image
import io
import base64
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

test_url = "https://mmbiz.qpic.cn/sz_mmbiz_png/nKJJU3IO9Elyia9qcCZ8sa7DJbzMCCoKxzMJN95nPjj88PtHYttkdT1eLnl1QlJR74RHwPIjV9ghaFaaM5l7SJA/640?wx_fmt=png&from=appmsg&wxfrom=5&wx_lazy=1&tp=webp"

print("Downloading image...")
response = requests.get(test_url, timeout=30)
original_size = len(response.content)
print(f"Original size: {original_size} bytes ({original_size/1024:.1f} KB)")

# Open image with PIL
img = Image.open(io.BytesIO(response.content))
print(f"Image dimensions: {img.size[0]}x{img.size[1]}")
print(f"Image mode: {img.mode}")

# Convert to RGB if necessary
if img.mode == 'RGBA':
    img = img.convert('RGB')

# Resize if too large (max 2048 on longest side)
max_size = 2048
if max(img.size) > max_size:
    ratio = max_size / max(img.size)
    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
    img = img.resize(new_size, Image.LANCZOS)
    print(f"Resized to: {img.size[0]}x{img.size[1]}")

# Save as JPEG with quality 85
output = io.BytesIO()
img.save(output, format='JPEG', quality=85)
jpeg_data = output.getvalue()
jpeg_size = len(jpeg_data)

print(f"JPEG size: {jpeg_size} bytes ({jpeg_size/1024:.1f} KB)")
print(f"Size reduction: {(1 - jpeg_size/original_size)*100:.1f}%")

# Encode to base64
base64_image = base64.b64encode(jpeg_data).decode('utf-8')
base64_size = len(base64_image)

print(f"Base64 size: {base64_size} chars ({base64_size/1024:.1f} KB)")
print(f"\nOpenAI API limits:")
print(f"  - Max image size: 20MB")
print(f"  - Current size: {base64_size/1024/1024:.2f} MB")
print(f"  - Status: {'✓ OK' if base64_size < 20*1024*1024 else '✗ TOO LARGE'}")

# Try sending to OpenAI
print("\nTrying to send to OpenAI...")
try:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Please list all Chinese text you see in this image, one per line."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        max_tokens=2000
    )

    content = response.choices[0].message.content
    print("✓ SUCCESS!")
    print(f"Response: {content[:200]}...")

except Exception as e:
    print(f"✗ ERROR: {e}")
