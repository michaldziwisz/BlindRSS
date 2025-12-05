import feedparser
import time
import uuid
import threading
import sqlite3
import concurrent.futures
from typing import List, Dict, Any
from .base import RSSProvider, Feed, Article
from core.db import get_connection, init_db
from core.discovery import discover_feed
from core import utils
from core.signals import SignalManager
from bs4 import BeautifulSoup as BS
import xml.etree.ElementTree as ET
import logging

log = logging.getLogger(__name__)

class LocalProvider(RSSProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        init_db()

    def get_name(self) -> str:
        return "Local RSS"

    def refresh(self) -> bool:
        # log.debug("LocalProvider.refresh() called.")
        conn = get_connection()
        c = conn.cursor()
        # Fetch etag/last_modified for conditional get
        c.execute("SELECT id, url, etag, last_modified FROM feeds")
        feeds = c.fetchall()
        conn.close()

        if not feeds:
            return True

        # Increase workers for network-bound tasks
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(self._refresh_single_feed, f[0], f[1], f[2], f[3]): f for f in feeds}
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    log.error(f"Refresh worker error: {e}")
        return True

    def _refresh_single_feed(self, feed_id, feed_url, etag, last_modified):
        # Each thread gets its own connection
        try:
            current_url = feed_url
            page_count = 0
            visited_urls = set()
            
            while current_url and page_count < 50: # Limit to prevent infinite loops
                if current_url in visited_urls:
                    break
                visited_urls.add(current_url)
                
                headers = {}
                # Only use conditional GET for the main feed URL (first page)
                # DISABLED for debugging: Force refresh
                # if page_count == 0:
                #     if etag: headers['If-None-Match'] = etag
                #     if last_modified: headers['If-Modified-Since'] = last_modified
                
                try:
                    resp = utils.safe_requests_get(current_url, headers=headers, timeout=15)
                    if resp.status_code == 304:
                        # Not modified. If it's the first page, we assume nothing changed.
                        if page_count == 0:
                            return
                        else:
                            # Weird for subsequent pages but break just in case
                            break
                    resp.raise_for_status()
                    xml_text = resp.text
                    
                    # Capture ETag/LM only for the first page
                    new_etag = resp.headers.get('ETag') if page_count == 0 else None
                    new_last_modified = resp.headers.get('Last-Modified') if page_count == 0 else None
                except Exception as e:
                    log.error(f"Network error fetching {current_url}: {e}")
                    break

                d = feedparser.parse(xml_text)
                # log.debug(f"Parsed {len(d.entries)} entries for {feed_url}")
                
                # Build chapter map
                chapter_map = {}
                # ... (rest of chapter map logic) ...

                conn = get_connection()
                c = conn.cursor()
                
                # ... (rest of feed title update) ...
                
                new_items_in_batch = 0
                
                for entry in d.entries:
                    content = ""
                    # ... (rest of content parsing) ...
                    
                    article_id = entry.get('id', entry.get('link', ''))
                    if not article_id:
                        continue

                    title = entry.get('title', 'No Title')
                    url = entry.get('link', '')
                    author = entry.get('author', 'Unknown')

                    raw_date = entry.get('published') or entry.get('updated') or entry.get('pubDate') or entry.get('date')
                    parsed_date_obj = entry.get('published_parsed') or entry.get('updated_parsed')
                    
                    date = utils.normalize_date(
                        parsed_date_obj if parsed_date_obj else (str(raw_date) if raw_date else ""), 
                        title, 
                        content or (entry.get('summary') or ''),
                        url
                    )

                    c.execute("SELECT date FROM articles WHERE id = ? AND feed_id = ?", (article_id, feed_id))
                    row = c.fetchone()
                    if row:
                        existing_date = row[0] or ""
                        # Update if date changed OR if we are fixing a bad date (0001...)
                        if existing_date != date and (date != "0001-01-01 00:00:00" or existing_date == "0001-01-01 00:00:00"):
                                c.execute("UPDATE articles SET date = ? WHERE id = ? AND feed_id = ?", (date, article_id, feed_id))
                        continue
                    
                    # New item logic
                    media_url = None
                    media_type = None
                    # ... (rest of media_url/type extraction) ...

                    try:
                        c.execute("INSERT INTO articles (id, feed_id, title, url, content, date, author, is_read, media_url, media_type) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
                                    (article_id, feed_id, title, url, content, date, author, media_url, media_type))
                        new_items_in_batch += 1
                    except Exception as e:
                        log.error(f"Failed to insert article '{article_id}' for feed '{feed_id}': {e}")
                    
                    # Chapter fetching is now lazy-loaded on selection/play to prevent performance issues
                    chapter_url = None
                
                conn.commit()
                conn.close()

                if new_items_in_batch > 0:
                    SignalManager.emit("feed_update", {"feed_id": feed_id, "count": new_items_in_batch})
                
                # Check for next page
                next_link = None
                if hasattr(d, 'feed') and hasattr(d.feed, 'links'):
                    for link in d.feed.links:
                        if link.get('rel') == 'next':
                            next_link = link.get('href')
                            break
                
                # If no new items were found in this batch, and we are deep in history (page > 0),
                # we can assume we have everything else.
                if new_items_in_batch == 0 and page_count > 0:
                    break
                
                if next_link:
                    current_url = next_link
                    page_count += 1
                else:
                    break

        except Exception as e:
            log.error(f"Error processing feed {feed_url}: {e}")

    def get_feeds(self) -> List[Feed]:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, title, url, category, icon_url FROM feeds")
        rows = c.fetchall()

        c.execute("SELECT feed_id, COUNT(*) FROM articles WHERE is_read = 0 GROUP BY feed_id")
        unread_map = {row[0]: row[1] for row in c.fetchall()}
        
        feeds = []
        for row in rows:
            f = Feed(id=row[0], title=row[1], url=row[2], category=row[3], icon_url=row[4])
            f.unread_count = unread_map.get(f.id, 0)
            feeds.append(f)
        conn.close()
        return feeds

    def get_articles(self, feed_id: str, max_items: int = None) -> List[Article]:
        conn = get_connection()
        c = conn.cursor()
        
        if feed_id == "all":
            query = "SELECT id, feed_id, title, url, content, date, author, is_read, media_url, media_type FROM articles ORDER BY date DESC"
            if max_items:
                query += f" LIMIT {int(max_items)}"
            c.execute(query)
        elif feed_id.startswith("category:"):
            cat_name = feed_id.split(":", 1)[1]
            query = """
                SELECT a.id, a.feed_id, a.title, a.url, a.content, a.date, a.author, a.is_read, a.media_url, a.media_type
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE f.category = ?
                ORDER BY a.date DESC
            """
            if max_items:
                query += f" LIMIT {int(max_items)}"
            c.execute(query, (cat_name,))
        else:
            query = "SELECT id, feed_id, title, url, content, date, author, is_read, media_url, media_type FROM articles WHERE feed_id = ? ORDER BY date DESC"
            if max_items:
                query += f" LIMIT {int(max_items)}"
            c.execute(query, (feed_id,))
            
        rows = c.fetchall()
        
        # Batch fetch chapters for these articles
        article_ids = [r[0] for r in rows]
        chapters_map = {}
        
        if article_ids:
            # SQLite limits variables, simple chunking
            chunk_size = 900
            for i in range(0, len(article_ids), chunk_size):
                chunk = article_ids[i:i+chunk_size]
                placeholders = ','.join(['?'] * len(chunk))
                c.execute(f"SELECT article_id, start, title, href FROM chapters WHERE article_id IN ({placeholders})", chunk)
                for ch_row in c.fetchall():
                    aid = ch_row[0]
                    if aid not in chapters_map: chapters_map[aid] = []
                    chapters_map[aid].append({"start": ch_row[1], "title": ch_row[2], "href": ch_row[3]})

        articles = []
        for row in rows:
            chs = chapters_map.get(row[0], [])
            chs.sort(key=lambda x: x["start"])
            
            articles.append(Article(
                id=row[0], feed_id=row[1], title=row[2], url=row[3], content=row[4], date=row[5], author=row[6], is_read=bool(row[7]),
                media_url=row[8], media_type=row[9], chapters=chs
            ))
        conn.close()
        return articles

    def mark_read(self, article_id: str) -> bool:
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE articles SET is_read = 1 WHERE id = ?", (article_id,))
        conn.commit()
        conn.close()
        return True

    def add_feed(self, url: str, category: str = "Uncategorized") -> bool:
        real_url = discover_feed(url) or url
        
        try:
            resp = utils.safe_requests_get(real_url, timeout=10)
            d = feedparser.parse(resp.text)
            title = d.feed.get('title', real_url)
        except:
            title = real_url
            
        conn = get_connection()
        c = conn.cursor()
        feed_id = str(uuid.uuid4())
        c.execute("INSERT INTO feeds (id, url, title, category, icon_url) VALUES (?, ?, ?, ?, ?)",
                  (feed_id, real_url, title, category, ""))
        conn.commit()
        conn.close()
        return True

    def remove_feed(self, feed_id: str) -> bool:
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM articles WHERE feed_id = ?", (feed_id,))
        c.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
        conn.commit()
        conn.close()
        return True

    # ... import/export/category methods ...

    def import_opml(self, path: str, target_category: str = None) -> bool:
        import os
        import sys
        
        log_filename = os.path.join(os.getcwd(), f"opml_debug_{int(time.time())}_{uuid.uuid4().hex[:4]}.log")
        print(f"DEBUG: Attempting to log to {log_filename}")
        
        try:
            with open(log_filename, "w", encoding="utf-8") as log:
                def write_log(msg):
                    log.write(msg + "\n")
                    log.flush()
                    print(f"DEBUG_OPML: {msg}")

                write_log(f"Starting import from: {path}")
                write_log(f"Target category: {target_category}")
                write_log(f"Global sqlite3 present: {'sqlite3' in globals()}")
                
                try:
                    content = ""
                    # Try to read file with different encodings
                    for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
                        try:
                            with open(path, 'r', encoding=encoding) as f:
                                content = f.read()
                            write_log(f"Read successfully with encoding: {encoding}")
                            break
                        except UnicodeDecodeError:
                            continue
                    
                    if not content:
                        write_log("OPML Import: Could not read file with supported encodings")
                        return False

                    # Try parsing with BS4
                    soup = None
                    try:
                        soup = BS(content, 'xml')
                        write_log("Parsed with 'xml' parser.")
                    except Exception as e:
                        write_log(f"XML parse failed: {e}")
                    
                    if not soup or not soup.find('opml'):
                        # Fallback to html.parser if xml fails or doesn't find root
                        write_log("Fallback to 'html.parser'.")
                        soup = BS(content, 'html.parser')

                    # Find body
                    body = soup.find('body')
                    if not body:
                        write_log("OPML Import: No body found")
                        return False
                    
                    write_log(f"Body found. Children: {len(body.find_all('outline', recursive=False))}")

                    conn = get_connection()
                    c = conn.cursor()
                    
                    if target_category and target_category != "Uncategorized":
                         self.add_category(target_category)

                    def process_outline(outline, current_category="Uncategorized"):
                        # Case insensitive attribute lookup helper
                        def get_attr(name):
                            # Direct lookup first
                            if name in outline.attrs:
                                return outline.attrs[name]
                            # Case insensitive lookup
                            for k, v in outline.attrs.items():
                                if k.lower() == name.lower():
                                    return v
                            return None

                        text = get_attr('text') or get_attr('title')
                        if not text: text = "Unknown Feed"
                        
                        xmlUrl = get_attr('xmlUrl')
                        
                        if xmlUrl:
                            write_log(f"Found feed: {text} -> {xmlUrl}")
                            # It's a feed
                            c.execute("SELECT id FROM feeds WHERE url = ?", (xmlUrl,))
                            if not c.fetchone():
                                feed_id = str(uuid.uuid4())
                                cat_to_use = target_category if target_category else current_category
                                
                                c.execute("INSERT INTO feeds (id, url, title, category, icon_url) VALUES (?, ?, ?, ?, ?)",
                                          (feed_id, xmlUrl, text, cat_to_use, ""))
                        
                        # Recursion for children
                        # In BS4, children include newlines/NavigableString, so filtering for Tags is important
                        children = outline.find_all('outline', recursive=False)
                        if children:
                            new_cat = current_category
                            if not target_category:
                                 # If it's a folder (no xmlUrl), use its text as category
                                 if not xmlUrl:
                                    new_cat = text
                                 
                            for child in children:
                                process_outline(child, new_cat)

                    # Process top-level outlines in body
                    for outline in body.find_all('outline', recursive=False):
                        process_outline(outline)
                        
                    conn.commit()
                    conn.close()
                    write_log("Import completed successfully.")
                    return True
                except Exception as e:
                    import traceback
                    write_log(f"OPML Import error: {e}")
                    write_log(traceback.format_exc())
                    return False
        except Exception as e:
            print(f"DEBUG: FATAL ERROR opening log file: {e}")
            return False

    def export_opml(self, path: str) -> bool:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT title, url, category FROM feeds")
        feeds = c.fetchall()
        conn.close()
        
        root = ET.Element("opml", version="1.0")
        head = ET.SubElement(root, "head")
        ET.SubElement(head, "title").text = "RSS Exports"
        body = ET.SubElement(root, "body")
        
        # Group by category
        categories = {}
        for title, url, cat in feeds:
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((title, url))
            
        for cat, items in categories.items():
            if cat == "Uncategorized":
                for title, url in items:
                    ET.SubElement(body, "outline", text=title, xmlUrl=url)
            else:
                cat_outline = ET.SubElement(body, "outline", text=cat)
                for title, url in items:
                    ET.SubElement(cat_outline, "outline", text=title, xmlUrl=url)
                    
        tree = ET.ElementTree(root)
        tree.write(path, encoding='utf-8', xml_declaration=True)
        return True

    def get_categories(self) -> List[str]:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT title FROM categories ORDER BY title")
        rows = c.fetchall()
        conn.close()
        return [r[0] for r in rows]

    def add_category(self, title: str) -> bool:
        import sqlite3 # Defensive import
        conn = get_connection()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO categories (id, title) VALUES (?, ?)", (str(uuid.uuid4()), title))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False # Already exists
        finally:
            conn.close()

    def rename_category(self, old_title: str, new_title: str) -> bool:
        conn = get_connection()
        c = conn.cursor()
        try:
            # Update categories table
            c.execute("UPDATE categories SET title = ? WHERE title = ?", (new_title, old_title))
            # Update feeds
            c.execute("UPDATE feeds SET category = ? WHERE category = ?", (new_title, old_title))
            conn.commit()
            return True
        except Exception as e:
            print(f"Rename error: {e}")
            return False
        finally:
            conn.close()

    def delete_category(self, title: str) -> bool:
        if title.lower() == "uncategorized": return False
        conn = get_connection()
        c = conn.cursor()
        # Move feeds to Uncategorized? Or delete them? usually move.
        c.execute("UPDATE feeds SET category = 'Uncategorized' WHERE category = ?", (title,))
        c.execute("DELETE FROM categories WHERE title = ?", (title,))
        conn.commit()
        conn.close()
        return True

    # Optional API used by GUI when present
    def get_article_chapters(self, article_id: str):
        return utils.get_chapters_from_db(article_id)
