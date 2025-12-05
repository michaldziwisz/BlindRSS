import requests
import re
import uuid
import logging
import sqlite3
from datetime import datetime, timezone, timedelta
import email.utils
from dateutil import parser as dateparser
from io import BytesIO
from core.db import get_connection

log = logging.getLogger(__name__)

# Default headers for network calls
HEADERS = {
    "User-Agent": "BlindRSS/1.0 (+https://github.com/)",
    "Accept": "*/*",
}

def safe_requests_get(url, **kwargs):
    """requests.get with default headers and sane timeouts."""
    headers = kwargs.pop("headers", None) or {}
    merged = HEADERS.copy()
    merged.update(headers)
    if "timeout" not in kwargs:
        kwargs["timeout"] = 15
    return requests.get(url, headers=merged, **kwargs)

# --- Date Parsing ---

def format_datetime(dt: datetime) -> str:
    """Return UTC-normalized string for consistent ordering."""
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def extract_date_from_text(text: str, require_day: bool = False):
    """
    Try multiple date patterns inside arbitrary text.
    Returns datetime or None.
    """
    if not text:
        return None
    # 1) numeric with / or -
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
    if m:
        a, b, year = m.groups()
        try:
            year_int = int(year)
            if year_int < 100:
                year_int += 2000 if year_int < 70 else 1900
            a_int, b_int = int(a), int(b)
            # heuristic: if both <=12, prefer US mm/dd
            if a_int > 12 and b_int <= 12:
                day, month = a_int, b_int
            elif b_int > 12 and a_int <= 12:
                day, month = b_int, a_int
            else:
                month, day = a_int, b_int
            return datetime(year_int, month, day)
        except Exception:
            pass
    # 2) URL-style /yyyy/mm/dd/ (common in blogs)
    m_url = re.search(r"/(20\d{2}|19\d{2})/(0?[1-9]|1[0-2])/(0?[1-9]|[12][0-9]|3[01])/", text)
    if m_url:
        try:
            y, mth, d = m_url.groups()
            return datetime(int(y), int(mth), int(d))
        except Exception:
            pass

    # 3) ISO-like yyyy-mm-dd
    m_iso = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m_iso:
        try:
            y, mth, d = map(int, m_iso.groups())
            return datetime(y, mth, d)
        except Exception:
            pass
    # 4) Month name forms (e.g., May 17 2021)
    # Clean up timezone abbreviations that confuse parser
    clean_text = re.sub(r'\b(PST|PDT|EST|EDT|CST|CDT|MST|MDT|AI|GMT|UTC)\b', '', text, flags=re.IGNORECASE)
    # Insert a space before month names if glued to previous letters (e.g., "ASHWINNov 17, 2025")
    clean_text = re.sub(r'([A-Za-z])(?=(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b)', r'\1 ', clean_text)
    # Only attempt parsing if we see something that looks like a date (Month name)
    # Simple heuristic: Check for month names
    if re.search(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', clean_text, re.IGNORECASE):
        # If caller wants a day, skip month-year only matches
        if require_day and not re.search(r'\b\d{1,2}\b', clean_text):
            pass
        else:
            # Inject current year when none present to avoid defaulting to 1900
            if not re.search(r'\b(19|20)\d{2}\b', clean_text):
                now_year = datetime.now(timezone.utc).year
                clean_text = f"{clean_text} {now_year}"
            try:
                dt = dateparser.parse(clean_text, fuzzy=True, default=datetime(1900, 1, 1))
                if dt.year > 1900:
                    # If inferred date is >60 days in future, roll back one year (year-boundary heuristic)
                    if (dt - datetime.now(timezone.utc)).days > 60:
                        dt = dt.replace(year=dt.year - 1)
                    return dt
            except Exception:
                pass
    return None

def normalize_date(raw_date_input: any, title: str = "", content: str = "", url: str = "", fallback_iso: str = "") -> str:
    """
    Robust date normalizer.
    Prioritizes dates found explicitly in the Title or URL, as some feeds (e.g. archives) 
    put the original air date there while using a recent timestamp for pubDate.
    
    raw_date_input can be a string, a datetime object, or a time.struct_time.
    """
    now = datetime.now(timezone.utc)
    
    def to_utc(dt: datetime):
        if not dt:
            return None
        if dt.tzinfo:
            return dt.astimezone(timezone.utc)
        return dt.replace(tzinfo=timezone.utc)

    def valid(dt: datetime):
        if not dt:
            return False
        dt = to_utc(dt)
        return dt.year >= 1990 and (dt - now) <= timedelta(days=2)

    def parse_any(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return to_utc(val)
        if hasattr(val, 'tm_year'):
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                return None
        if isinstance(val, (int, float)) or (isinstance(val, str) and re.fullmatch(r"-?\\d+(?:\\.\\d+)?", val.strip())):
            try:
                ts = float(val)
                if abs(ts) > 1e12:
                    ts /= 1000.0
                return datetime.fromtimestamp(ts, timezone.utc)
            except Exception:
                return None
        if isinstance(val, str):
            s = val.strip()
            try:
                return to_utc(email.utils.parsedate_to_datetime(s))
            except Exception:
                pass
            try:
                tzinfos = {"PST": -28800, "PDT": -25200, "EST": -18000, "EDT": -14400, "CST": -21600, "CDT": -18000, "MST": -25200, "MDT": -21600}
                return to_utc(dateparser.parse(s, tzinfos=tzinfos))
            except Exception:
                return None
        return None

    # 1) raw input
    dt = parse_any(raw_date_input)
    if valid(dt):
        return format_datetime(dt)

    # 2) title (requires day)
    dt = extract_date_from_text(title, require_day=True) if title else None
    if valid(dt):
        return format_datetime(dt)

    # 3) url
    dt = extract_date_from_text(url, require_day=True) if url else None
    if valid(dt):
        return format_datetime(dt)

    # 4) content
    dt = extract_date_from_text(content, require_day=True) if content else None
    if valid(dt):
        return format_datetime(dt)

    # 5) fallback_iso
    dt = parse_any(fallback_iso)
    if valid(dt):
        return format_datetime(dt)

    # 6) now
    return format_datetime(now)


# --- Chapters ---

def get_chapters_from_db(article_id: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT start, title, href FROM chapters WHERE article_id = ? ORDER BY start", (article_id,))
    rows = c.fetchall()
    conn.close()
    return [{"start": r[0], "title": r[1], "href": r[2]} for r in rows]

def get_chapters_batch(article_ids: list) -> dict:
    """
    Fetches chapters for multiple articles in chunks to optimize performance.
    Returns a dict: {article_id: [chapter_list]}
    """
    if not article_ids:
        return {}
    
    conn = get_connection()
    c = conn.cursor()
    chapters_map = {}
    
    # SQLite limit usually 999 vars
    chunk_size = 900
    for i in range(0, len(article_ids), chunk_size):
        chunk = article_ids[i:i+chunk_size]
        placeholders = ','.join(['?'] * len(chunk))
        c.execute(f"SELECT article_id, start, title, href FROM chapters WHERE article_id IN ({placeholders}) ORDER BY article_id, start", chunk)
        for row in c.fetchall():
            aid = row[0]
            if aid not in chapters_map: chapters_map[aid] = []
            chapters_map[aid].append({"start": row[1], "title": row[2], "href": row[3]})
            
    conn.close()
    return chapters_map

def fetch_and_store_chapters(article_id, media_url, media_type, chapter_url=None):
    """
    Fetches chapters from chapter_url (JSON) or media_url (ID3 tags).
    Stores them in DB linked to article_id.
    Returns list of chapter dicts.
    """
    # Check DB first
    existing = get_chapters_from_db(article_id)
    if existing:
        return existing

    chapters_out = []
    
    # 1) Explicit chapter URL (Podcasting 2.0)
    if chapter_url:
        try:
            resp = safe_requests_get(chapter_url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            chapters = data.get("chapters", [])
            conn = get_connection()
            c = conn.cursor()
            for ch in chapters:
                ch_id = str(uuid.uuid4())
                start = ch.get("startTime") or ch.get("start_time") or 0
                title_ch = ch.get("title", "")
                href = ch.get("url") or ch.get("link")
                c.execute("INSERT OR REPLACE INTO chapters (id, article_id, start, title, href) VALUES (?, ?, ?, ?, ?)",
                              (ch_id, article_id, float(start), title_ch, href))
                chapters_out.append({"start": float(start), "title": title_ch, "href": href})
            conn.commit()
            conn.close()
            if chapters_out:
                return chapters_out
        except Exception as e:
            log.warning(f"Chapter fetch failed for {chapter_url}: {e}")

    # 2) ID3 CHAP frames if audio
    if media_url and media_type and (media_type.startswith("audio/") or "podcast" in media_type or media_url.lower().split("?")[0].endswith("mp3")):
        try:
            from mutagen.id3 import ID3
            # Fetch first 2MB (usually enough for ID3v2 header)
            resp = safe_requests_get(media_url, headers={"Range": "bytes=0-2000000"}, timeout=12)
            if resp.ok:
                id3 = ID3(BytesIO(resp.content))
                conn = get_connection()
                c = conn.cursor()
                found_any = False
                for frame in id3.getall("CHAP"):
                    found_any = True
                    ch_id = str(uuid.uuid4())
                    start = frame.start_time / 1000.0 if frame.start_time else 0
                    title_ch = ""
                    tit2 = frame.sub_frames.get("TIT2")
                    if tit2 and tit2.text:
                        title_ch = tit2.text[0]
                    href = None
                    # Extract URL from WXXX if needed? Usually just title.
                    
                    c.execute("INSERT OR REPLACE INTO chapters (id, article_id, start, title, href) VALUES (?, ?, ?, ?, ?)",
                                  (ch_id, article_id, float(start), title_ch, href))
                    chapters_out.append({"start": float(start), "title": title_ch, "href": href})
                
                conn.commit()
                conn.close()
        except ImportError:
            log.info("mutagen not installed, skipping ID3 chapter parse.")
        except Exception as e:
            log.debug(f"ID3 chapter parse failed for {media_url}: {e}")

    return chapters_out
