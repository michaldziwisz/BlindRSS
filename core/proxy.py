import threading
import socket
import os
import time
import requests
import tempfile
import math
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    pass

class MultiPartDownloader:
    def __init__(self, url, temp_path, num_threads=4, chunk_size=512*1024):
        self.url = url
        self.temp_path = temp_path
        self.num_threads = num_threads
        self.chunk_size = chunk_size
        
        self.total_size = None
        self.contiguous_size = 0
        self.finished = False
        self.error = None
        
        self.lock = threading.Lock()
        self.file_lock = threading.Lock()
        self.condition = threading.Condition(self.lock) # Notify on data available
        
        self.chunks_to_do = []
        self.completed_chunks = set()
        self.running = True
        self.threads = []
        self.support_ranges = False

    def start(self):
        # Check size and range support
        try:
            headers = {"User-Agent": "BlindRSS/1.0"}
            resp = requests.head(self.url, headers=headers, timeout=5, allow_redirects=True)
            if resp.status_code < 400:
                self.total_size = int(resp.headers.get('content-length', 0))
                if resp.headers.get('Accept-Ranges') == 'bytes' and self.total_size > 0:
                    self.support_ranges = True
        except:
            pass

        if not self.support_ranges or not self.total_size:
            # Fallback to single thread
            t = threading.Thread(target=self._single_thread_download, daemon=True)
            t.start()
            self.threads.append(t)
        else:
            # Resize file
            try:
                with open(self.temp_path, "wb") as f:
                    f.seek(self.total_size - 1)
                    f.write(b'\0')
            except Exception as e:
                print(f"Resize failed: {e}")
                # Fallback
                t = threading.Thread(target=self._single_thread_download, daemon=True)
                t.start()
                self.threads.append(t)
                return

            # Populate queue
            num_chunks = math.ceil(self.total_size / self.chunk_size)
            self.chunks_to_do = list(range(num_chunks))
            
            for _ in range(self.num_threads):
                t = threading.Thread(target=self._worker, daemon=True)
                t.start()
                self.threads.append(t)

    def stop(self):
        self.running = False

    def _single_thread_download(self):
        try:
            headers = {"User-Agent": "BlindRSS/1.0"}
            with requests.get(self.url, headers=headers, stream=True, timeout=15) as r:
                r.raise_for_status()
                if not self.total_size:
                    try: self.total_size = int(r.headers.get('content-length', 0))
                    except: pass
                
                with open(self.temp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if not self.running: break
                        f.write(chunk)
                        f.flush()
                        with self.lock:
                            self.contiguous_size += len(chunk)
                            self.condition.notify_all()
            with self.lock:
                self.finished = True
                self.condition.notify_all()
        except Exception as e:
            with self.lock:
                self.error = e
                self.finished = True
                self.condition.notify_all()

    def _worker(self):
        while self.running:
            idx = -1
            with self.lock:
                if not self.chunks_to_do:
                    if not any(t.is_alive() for t in self.threads if t != threading.current_thread()):
                         # All done?
                         pass
                    break
                idx = self.chunks_to_do.pop(0) # FIFO
            
            if idx == -1: 
                time.sleep(0.1)
                continue

            start = idx * self.chunk_size
            end = min(start + self.chunk_size - 1, self.total_size - 1)
            headers = {"User-Agent": "BlindRSS/1.0", "Range": f"bytes={start}-{end}"}
            
            success = False
            try:
                resp = requests.get(self.url, headers=headers, timeout=10)
                if resp.ok:
                    with self.file_lock:
                        with open(self.temp_path, "r+b") as f:
                            f.seek(start)
                            f.write(resp.content)
                    success = True
            except Exception as e:
                print(f"Chunk {idx} failed: {e}")

            with self.lock:
                if success:
                    self.completed_chunks.add(idx)
                    # Update contiguous size
                    check = int(self.contiguous_size // self.chunk_size)
                    while check in self.completed_chunks:
                        check += 1
                    
                    self.contiguous_size = min(check * self.chunk_size, self.total_size)
                    if len(self.completed_chunks) * self.chunk_size >= self.total_size:
                        self.finished = True
                    self.condition.notify_all()
                else:
                    # Push back to front
                    self.chunks_to_do.insert(0, idx)

class StreamHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self):
        proxy = self.server.proxy_instance
        
        range_header = self.headers.get('Range')
        start_byte = 0
        
        if range_header:
            try:
                _, r = range_header.split('=')
                start_str, _ = r.split('-')
                start_byte = int(start_str)
            except: pass
        
        # Wait for data
        # We wait until bytes up to start_byte are available
        # Note: contiguous_size tracks the continuous stream from 0
        # If user seeks far ahead (start_byte > contiguous_size), we might block forever unless we implement sparse reading.
        # For now, assume linear play or enough buffer. 
        # Improved: Check if the specific chunk for start_byte is downloaded.
        
        chunk_idx = int(start_byte // proxy.downloader.chunk_size)
        
        # Wait for initial data
        with proxy.downloader.lock:
            while not proxy.downloader.finished:
                if proxy.downloader.error:
                    self.send_error(500, "Stream error")
                    return
                
                is_available = False
                if proxy.downloader.support_ranges:
                    is_available = chunk_idx in proxy.downloader.completed_chunks
                else:
                    is_available = start_byte < proxy.downloader.contiguous_size
                
                if is_available:
                    break
                
                proxy.downloader.condition.wait(1.0)

        file_size = proxy.downloader.total_size if proxy.downloader.total_size else proxy.downloader.contiguous_size
        
        if range_header:
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start_byte}-{file_size-1}/{file_size}")
        else:
            self.send_response(200)
            
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Accept-Ranges", "bytes")
        if file_size:
            self.send_header("Content-Length", str(file_size - start_byte))
        self.end_headers()

        try:
            with open(proxy.temp_path, 'rb') as f:
                f.seek(start_byte)
                while True:
                    # Determine available bytes linearly from current pos
                    current_pos = f.tell()
                    
                    if proxy.downloader.support_ranges:
                        # Sparse logic
                        curr_chunk = int(current_pos // proxy.downloader.chunk_size)
                        with proxy.downloader.lock:
                            while curr_chunk not in proxy.downloader.completed_chunks:
                                if proxy.downloader.finished: break
                                proxy.downloader.condition.wait(1.0)
                            
                            # If still not available after wait loop (and finished), break
                            if curr_chunk not in proxy.downloader.completed_chunks and proxy.downloader.finished:
                                break
                                
                        # Chunk is available, read up to end of chunk
                        chunk_end = (curr_chunk + 1) * proxy.downloader.chunk_size
                        available = min(chunk_end, file_size) - current_pos
                    else:
                        with proxy.downloader.lock:
                            while proxy.downloader.contiguous_size - current_pos <= 0:
                                if proxy.downloader.finished: break
                                proxy.downloader.condition.wait(1.0)
                            
                            available = proxy.downloader.contiguous_size - current_pos
                            if available <= 0: # Finished
                                break
                    
                    chunk = f.read(min(65536, available))
                    if not chunk: break
                    try: self.wfile.write(chunk)
                    except: break
        except: pass

class StreamProxy:
    def __init__(self, url):
        self.url = url
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        self.temp_path = self.temp_file.name
        self.temp_file.close()
        
        # Increase threads for speed, chunk size optimal for connections
        self.downloader = MultiPartDownloader(url, self.temp_path, num_threads=3, chunk_size=256*1024)
        self.server = None
        self.thread = None

    def start(self):
        self.downloader.start()
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', 0))
        port = sock.getsockname()[1]
        sock.close()
        
        self.server = ThreadingHTTPServer(('localhost', port), StreamHandler)
        self.server.proxy_instance = self
        
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        
        return f"http://localhost:{port}/stream.mp3"

    def stop(self):
        if self.downloader:
            self.downloader.stop()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if os.path.exists(self.temp_path):
            try: os.remove(self.temp_path)
            except: pass