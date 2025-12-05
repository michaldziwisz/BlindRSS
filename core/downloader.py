import os
import sys
import threading
import datetime
import logging
import time
from dataclasses import dataclass, field
import re
from dateutil import parser
from core import utils
from core.db import get_connection

# Setup basic logging (inherits level from app)
logger = logging.getLogger(__name__)

def get_download_path():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "Podcasts")
    if not os.path.exists(path):
        os.makedirs(path)
    return path

class Downloader:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.stop_event = threading.Event()
        self.max_workers = int(self.config_manager.get("max_downloads", 10) or 10)
        self.jobs = []
        self.jobs_lock = threading.Lock()
        self.workers = []
        for _ in range(self.max_workers):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
            self.workers.append(t)

    @dataclass
    class Job:
        article_id: str
        title: str
        url: str
        target: str
        status: str = "queued"
        progress: float = 0.0
        error: str = None
        started: float = None
        finished: float = None
        feed_id: str = ""
        paused: bool = False
        cancel_requested: bool = False
        feed_title: str = ""

    def start_auto_download(self, provider):
        """Starts the auto-download process in a separate thread."""
        if not self.config_manager.get("auto_download_podcasts", False):
            return
        threading.Thread(target=self._download_loop, args=(provider,), daemon=True).start()

    def _download_loop(self, provider):
        period_str = self.config_manager.get("auto_download_period", "1w")
        cutoff_date = self._calculate_cutoff(period_str)
        
        try:
            feeds = provider.get_feeds()
            for feed in feeds:
                if self.stop_event.is_set():
                    break
                
                try:
                    # Fetch articles for feed
                    # Optimization: If provider supports since_date, use it.
                    # But base provider doesn't seem to enforce that args.
                    # We'll just fetch and filter.
                    articles = provider.get_articles(feed.id)
                    for article in articles:
                        if self.stop_event.is_set():
                            break
                        
                        if not article.media_url:
                            continue
                            
                        # Check Date
                        if cutoff_date:
                            try:
                                article_date = parser.parse(article.date)
                                # Ensure timezone awareness consistency
                                if article_date.tzinfo and not cutoff_date.tzinfo:
                                    cutoff_date = cutoff_date.replace(tzinfo=article_date.tzinfo)
                                elif not article_date.tzinfo and cutoff_date.tzinfo:
                                    # If article date is naive, assume UTC or local?
                                    # normalize_date usually returns a string without tz if I recall correctly,
                                    # but dateutil.parser might add it.
                                    # Let's assume UTC if naive for comparison to be safe, or just drop tz from cutoff.
                                    article_date = article_date.replace(tzinfo=cutoff_date.tzinfo)
                                    
                                if article_date < cutoff_date:
                                    continue
                            except Exception as e:
                                logger.warning(f"Could not parse date {article.date}: {e}")
                                continue

                        # Check if exists and download
                        self.queue_article(article)
                except Exception as e:
                    logger.error(f"Error processing feed {feed.title}: {e}")
        except Exception as e:
            logger.error(f"Auto-download loop error: {e}")

    # Public API
    def queue_article(self, article):
        """Queue single article for download (most recent first upstream)."""
        if not article.media_url:
            return
        base = get_download_path()

        # per-feed subfolder (use feed_id; optional title if available)
        feed_id = str(getattr(article, "feed_id", "unknown_feed") or "unknown_feed")
        feed_title = getattr(article, "feed_title", "") or self._lookup_feed_title(feed_id)
        feed_folder = self._sanitize(feed_title) or feed_id
        subdir = os.path.join(base, feed_folder)
        os.makedirs(subdir, exist_ok=True)

        # derive extension from media url
        url_part = article.media_url.split("/")[-1].split("?")[0]
        ext = os.path.splitext(url_part)[1].lower()
        if ext not in (".mp3", ".m4a", ".ogg", ".opus", ".wav", ".flac"):
            ext = ".mp3"

        # safe title and date suffix
        title_part = self._sanitize(getattr(article, "title", "untitled"))
        date_raw = getattr(article, "date", "")
        date_part = ""
        if date_raw:
            date_part = date_raw.split(" ")[0]
            date_part = re.sub(r"[^0-9\\-]", "", date_part)
        filename = title_part
        if date_part:
            filename += f" - {date_part}"
        filename += ext

        target = os.path.join(subdir, filename)

        # Skip if already exists
        if os.path.exists(target):
            return

        job = Downloader.Job(
            article_id=str(getattr(article, "id", "")),
            feed_id=str(getattr(article, "feed_id", "")),
            feed_title=str(getattr(article, "feed_title", "")),
            title=article.title,
            url=article.media_url,
            target=target,
        )
        with self.jobs_lock:
            self.jobs.append(job)

    def queue_articles(self, articles):
        # Assume incoming articles are newest first; keep order
        for art in articles:
            self.queue_article(art)

    def get_jobs_snapshot(self):
        with self.jobs_lock:
            return [job.__dict__.copy() for job in self.jobs]

    def pause_job(self, job_idx):
        with self.jobs_lock:
            if 0 <= job_idx < len(self.jobs):
                job = self.jobs[job_idx]
                if job.status == "queued":
                    job.paused = True
                    job.status = "paused"
                elif job.status == "downloading":
                    job.cancel_requested = True
                    job.paused = True

    def resume_job(self, job_idx):
        with self.jobs_lock:
            if 0 <= job_idx < len(self.jobs):
                job = self.jobs[job_idx]
                if job.status in ("paused", "error"):
                    job.paused = False
                    job.cancel_requested = False
                    job.status = "queued"

    def cancel_job(self, job_idx):
        with self.jobs_lock:
            if 0 <= job_idx < len(self.jobs):
                job = self.jobs[job_idx]
                job.cancel_requested = True
                if job.status == "queued":
                    job.status = "cancelled"
                elif job.status == "downloading":
                    job.status = "cancelling"

    def cancel_all(self):
        with self.jobs_lock:
            for job in self.jobs:
                job.cancel_requested = True
                if job.status == "queued":
                    job.status = "cancelled"
                elif job.status == "downloading":
                    job.status = "cancelling"

    def pause_all(self):
        with self.jobs_lock:
            for job in self.jobs:
                if job.status == "queued":
                    job.paused = True
                    job.status = "paused"

    def resume_all(self):
        with self.jobs_lock:
            for job in self.jobs:
                if job.status == "paused":
                    job.paused = False
                    job.cancel_requested = False
                    job.status = "queued"

    def _calculate_cutoff(self, period_str):
        now = datetime.datetime.now(datetime.timezone.utc)
        if period_str == "unlimited":
            return None
        
        mapping = {
            "1d": datetime.timedelta(days=1),
            "5d": datetime.timedelta(days=5),
            "1w": datetime.timedelta(weeks=1),
            "2w": datetime.timedelta(weeks=2),
            "1m": datetime.timedelta(days=30),
            "3m": datetime.timedelta(days=90),
            "6m": datetime.timedelta(days=180),
            "1y": datetime.timedelta(days=365),
            "2y": datetime.timedelta(days=365*2),
            "5y": datetime.timedelta(days=365*5),
            "10y": datetime.timedelta(days=365*10),
        }
        
        delta = mapping.get(period_str, datetime.timedelta(weeks=1))
        return now - delta

    def _download_article(self, job: Job):
        url = job.url
        target = job.target
        tmp_path = target + ".part"
        try:
            job.status = "downloading"
            resp = utils.safe_requests_get(url, stream=True, timeout=60)
            resp.raise_for_status()
            
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(tmp_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if self.stop_event.is_set():
                        return
                    if job.cancel_requested:
                        job.status = "cancelled"
                        break
                    f.write(chunk)
                    if resp.headers.get("Content-Length"):
                        total = int(resp.headers["Content-Length"])
                        job.progress = min(0.999, f.tell()/total)
            
            if not self.stop_event.is_set():
                if job.status != "cancelled":
                    os.rename(tmp_path, target)
                    job.status = "done"
                    job.progress = 1.0
                    job.finished = time.time()
            else:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        except Exception as e:
            job.status = "error"
            job.error = str(e)
            if os.path.exists(target + ".part"):
                try: os.remove(target + ".part")
                except: pass
    
    def stop(self):
        self.stop_event.set()
        for t in self.workers:
            t.join(timeout=2)

    def _worker(self):
        while True:
            if self.stop_event.is_set():
                break
            job = None
            with self.jobs_lock:
                for j in reversed(self.jobs):  # newest first
                    if j.status == "queued" and not j.paused and not j.cancel_requested:
                        job = j
                        job.status = "downloading"
                        job.started = time.time()
                        break
            if not job:
                time.sleep(0.1)
                continue
            # Skip if already downloaded
            if os.path.exists(job.target):
                job.status = "done"
                job.progress = 1.0
                job.finished = time.time()
                continue
            self._download_article(job)

    def _sanitize(self, text: str) -> str:
        text = text.strip() if text else "untitled"
        text = re.sub(r"[\\/:*?\"<>|]", "_", text)
        return text[:180]

    def _lookup_feed_title(self, feed_id: str) -> str:
        try:
            with get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT title FROM feeds WHERE id=?", (feed_id,))
                row = c.fetchone()
                if row and row[0]:
                    return row[0]
        except Exception:
            pass
        return ""
