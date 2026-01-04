import sys
import os

# Add project root to path
sys.path.insert(0, os.getcwd())

from core.discovery import is_ytdlp_supported

url = "https://www.bbc.com/news/articles/crmlz7r0zrxo?at_medium=RSS&at_campaign=rss"
print(f"Checking URL: {url}")
supported = is_ytdlp_supported(url)
print(f"is_ytdlp_supported: {supported}")
