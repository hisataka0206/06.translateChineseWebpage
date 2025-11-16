"""
Test if image download is working correctly
"""

import requests

test_image_url = "https://mmbiz.qpic.cn/sz_mmbiz_png/nKJJU3IO9Elyia9qcCZ8sa7DJbzMCCoKxzMJN95nPjj88PtHYttkdT1eLnl1QlJR74RHwPIjV9ghaFaaM5l7SJA/640?wx_fmt=png&from=appmsg&wxfrom=5&wx_lazy=1&tp=webp"

print("Downloading image...")
print(f"URL: {test_image_url}\n")

# Download image
response = requests.get(test_image_url, timeout=30)

print(f"Status Code: {response.status_code}")
print(f"Content-Type: {response.headers.get('Content-Type')}")
print(f"Content-Length: {len(response.content)} bytes")
print(f"First 100 bytes (hex): {response.content[:100].hex()}")
print(f"\nHeaders: {dict(response.headers)}")

# Save to file to verify
with open('test_image.webp', 'wb') as f:
    f.write(response.content)

print("\nImage saved to test_image.webp")
print("Please check if the image opens correctly.")

# Check if it's actually webp format
if response.content[:4] == b'RIFF' and response.content[8:12] == b'WEBP':
    print("✓ Confirmed: This is a valid WebP image")
elif response.content[:8] == b'\x89PNG\r\n\x1a\n':
    print("✓ Confirmed: This is a valid PNG image")
elif response.content[:2] == b'\xff\xd8':
    print("✓ Confirmed: This is a valid JPEG image")
else:
    print("✗ WARNING: Image format not recognized!")
    print(f"First 20 bytes: {response.content[:20]}")
