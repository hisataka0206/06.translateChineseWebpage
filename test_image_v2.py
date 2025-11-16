"""
Test updated image text extraction with base64 encoding
"""

import sys
sys.path.insert(0, '.')

from src.translation.image_translator import ImageTextTranslator
from dotenv import load_dotenv

load_dotenv()

# Test with one of the actual image URLs
test_image_url = "https://mmbiz.qpic.cn/sz_mmbiz_png/nKJJU3IO9Elyia9qcCZ8sa7DJbzMCCoKxzMJN95nPjj88PtHYttkdT1eLnl1QlJR74RHwPIjV9ghaFaaM5l7SJA/640?wx_fmt=png&from=appmsg&wxfrom=5&wx_lazy=1&tp=webp"

print("="*80)
print("Testing Updated Image Text Extraction (Base64 Method)")
print("="*80)
print(f"Image URL: {test_image_url}\n")

translator = ImageTextTranslator()
result = translator.extract_and_translate_image_text(test_image_url)

print("\n" + "="*80)
print("Result:")
print("="*80)

if result.get("error"):
    print(f"Error: {result['error']}")
else:
    translations = result.get("translations", [])
    print(f"Found {len(translations)} text translations:\n")

    for i, (chinese, japanese) in enumerate(translations, 1):
        print(f"{i}. {chinese} -> {japanese}")

print("="*80)
