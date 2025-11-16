"""
Final comprehensive test of image translation
"""

import sys
sys.path.insert(0, '.')

from src.translation.image_translator import ImageTextTranslator
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

load_dotenv()

test_image_url = "https://mmbiz.qpic.cn/sz_mmbiz_png/nKJJU3IO9Elyia9qcCZ8sa7DJbzMCCoKxzMJN95nPjj88PtHYttkdT1eLnl1QlJR74RHwPIjV9ghaFaaM5l7SJA/640?wx_fmt=png&from=appmsg&wxfrom=5&wx_lazy=1&tp=webp"

print("="*80)
print("FINAL TEST: Image Text Extraction and Translation")
print("="*80)
print(f"Testing URL: {test_image_url}\n")

translator = ImageTextTranslator()

print("Starting translation process...")
print("-"*80)

result = translator.extract_and_translate_image_text(test_image_url)

print("\n" + "="*80)
print("RESULTS:")
print("="*80)

if result.get("error"):
    print(f"\nError occurred: {result['error']}")
else:
    translations = result.get("translations", [])
    print(f"\nTotal translations found: {len(translations)}\n")

    if translations:
        for i, (chinese, japanese) in enumerate(translations[:20], 1):  # Show first 20
            print(f"{i:2d}. {chinese[:50]:50s} -> {japanese[:50]}")

        if len(translations) > 20:
            print(f"\n... and {len(translations) - 20} more translations")
    else:
        print("No translations found!")

print("\n" + "="*80)
