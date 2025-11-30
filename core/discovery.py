import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

def discover_feed(url: str) -> str:
    """
    Attempts to find an RSS/Atom feed URL from a given website URL.
    """
    if not url.startswith("http"):
        url = "http://" + url

    # YouTube Logic
    if "youtube.com" in url or "youtu.be" in url:
        # Channel
        if "/channel/" in url:
            channel_id = url.split("/channel/")[1].split("/")[0].split("?")[0]
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        # User
        if "/user/" in url:
            user = url.split("/user/")[1].split("/")[0].split("?")[0]
            return f"https://www.youtube.com/feeds/videos.xml?user={user}"
        # Playlist
        if "list=" in url:
            match = re.search(r'list=([a-zA-Z0-9_-]+)', url)
            if match:
                return f"https://www.youtube.com/feeds/videos.xml?playlist_id={match.group(1)}"
        # Handle (needs scraping usually, but let's try requests first as some handles redirect)
        # Simpler: If it's a @handle or /c/ custom URL, we might need to fetch the page to find the channel_id
        # Fallthrough to standard discovery which often works for YouTube channel pages if they contain the RSS link tag
        
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # If the URL itself is an XML feed, feedparser might handle it, 
        # but we can check content type or basic sniffing.
        content_type = response.headers.get('content-type', '').lower()
        if 'xml' in content_type or response.text.strip().startswith('<?xml'):
            return url

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for <link rel="alternate" type="application/rss+xml" ...>
        links = soup.find_all('link', rel='alternate')
        for link in links:
            type_attr = link.get('type', '').lower()
            if 'rss' in type_attr or 'atom' in type_attr:
                href = link.get('href')
                if href:
                    return urljoin(url, href)
                    
        return None
    except Exception as e:
        print(f"Discovery failed: {e}")
        return None
