import wx
import wx.media
import threading
import yt_dlp
import tempfile
import os
import time 
import sys
import re
from core import utils
from core.proxy import StreamProxy

try:
    import vlc
    HAVE_VLC = True
except ImportError:
    HAVE_VLC = False

class MediaPlayerPanel(wx.Panel):
    def __init__(self, parent, config_manager=None, downloader=None):
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.downloader = downloader
        self.proxy = None
        
        # UI Sizer
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Controls Row
        self.ctrl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.btn_play = wx.Button(self, label="Play")
        self.btn_pause = wx.Button(self, label="Pause")
        self.btn_stop = wx.Button(self, label="Stop")
        
        self.ctrl_sizer.Add(self.btn_play, 0, wx.ALL, 5)
        self.ctrl_sizer.Add(self.btn_pause, 0, wx.ALL, 5)
        self.ctrl_sizer.Add(self.btn_stop, 0, wx.ALL, 5)
        
        # Seek Slider
        self.slider = wx.Slider(self, minValue=0, maxValue=100)
        
        # Volume Slider
        self.vol_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.st_vol = wx.StaticText(self, label="Volume")
        self.volume_slider = wx.Slider(self, value=100, minValue=0, maxValue=100, style=wx.SL_HORIZONTAL)
        self.vol_sizer.Add(self.st_vol, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        self.vol_sizer.Add(self.volume_slider, 1, wx.EXPAND|wx.ALL, 5)
        
        # Speed Control
        self.lbl_speed = wx.StaticText(self, label="Speed:")
        self.speed_choice = wx.Choice(self, choices=["0.5x", "0.8x", "1.0x", "1.2x", "1.5x", "1.8x", "2.0x"])
        self.speed_choice.SetSelection(2) # 1.0x
        self.vol_sizer.Add(self.lbl_speed, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 10)
        self.vol_sizer.Add(self.speed_choice, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        self.Bind(wx.EVT_CHOICE, self.on_speed_change, self.speed_choice)

        # Download Button
        self.btn_download = wx.Button(self, label="Download")
        self.btn_download.SetToolTip("Download episode to Podcasts folder")
        self.vol_sizer.Add(self.btn_download, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 10)
        self.Bind(wx.EVT_BUTTON, self.on_download_btn, self.btn_download)
        
        # Chapters list
        self.chapters = wx.ListBox(self)

        # Status
        self.st_status = wx.StaticText(self, label="Ready")

        # Media Control Backend
        self.use_vlc = HAVE_VLC
        self.media_ctrl = None
        self.vlc_instance = None
        self.vlc_player = None
        
        if self.use_vlc:
            try:
                self.vlc_instance = vlc.Instance([
                    "--network-caching=50",
                    "--file-caching=50",
                    "--live-caching=50",
                    "--clock-jitter=0",
                    "--clock-synchro=0"
                ])
                self.vlc_player = self.vlc_instance.media_player_new()
                self.vlc_player.set_hwnd(self.GetHandle())
                self.event_manager = self.vlc_player.event_manager()
                self.event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self.on_vlc_end)
                self.event_manager.event_attach(vlc.EventType.MediaPlayerOpening, lambda e: wx.CallAfter(self.st_status.SetLabel, "Opening..."))
                self.event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self.on_vlc_playing)
            except Exception as e:
                self.use_vlc = False

        if not self.use_vlc:
            self.media_ctrl = wx.media.MediaCtrl(self, style=wx.SIMPLE_BORDER)
            self.media_ctrl.Show(False)
            self.Bind(wx.media.EVT_MEDIA_LOADED, self.on_media_loaded, self.media_ctrl)
            self.Bind(wx.media.EVT_MEDIA_FINISHED, self.on_media_finished, self.media_ctrl)
        
        self.sizer.Add(self.ctrl_sizer, 0, wx.ALIGN_CENTER)
        self.sizer.Add(self.slider, 0, wx.EXPAND|wx.ALL, 5)
        self.sizer.Add(self.chapters, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 5)
        self.sizer.Add(self.vol_sizer, 0, wx.EXPAND|wx.ALL, 5)
        self.sizer.Add(self.st_status, 0, wx.ALIGN_CENTER|wx.ALL, 5)
        
        self.SetSizer(self.sizer)
        
        self.Bind(wx.EVT_BUTTON, self.on_play, self.btn_play)
        self.Bind(wx.EVT_BUTTON, self.on_pause, self.btn_pause)
        self.Bind(wx.EVT_BUTTON, self.on_stop, self.btn_stop)
        self.Bind(wx.EVT_SLIDER, self.on_seek, self.slider)
        self.Bind(wx.EVT_SLIDER, self.on_volume_change, self.volume_slider)
        
        if not self.use_vlc:
            self.Bind(wx.media.EVT_MEDIA_LOADED, self.on_media_loaded, self.media_ctrl)
            self.Bind(wx.media.EVT_MEDIA_FINISHED, self.on_media_finished, self.media_ctrl)
            
        self.chapters.Bind(wx.EVT_LISTBOX_DCLICK, self.on_chapter_activated)
        self.chapters.Bind(wx.EVT_KEY_DOWN, self.on_chapter_key)
        self.chapters.Bind(wx.EVT_CHAR_HOOK, self.on_chapter_key)
        
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
        
        self.safety_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_safety_timer, self.safety_timer)
        
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key)

        self.current_url = None
        self.current_chapters = []
        self.fallback_active = False
        self.temp_file = None
        self.queue = []
        self.last_load_start_time = None
        self.silence_intervals = []
        self.current_rate = 1.0

    def on_key(self, event):
        code = event.GetKeyCode()
        ctrl = event.ControlDown()
        obj = event.GetEventObject()
        if code == wx.WXK_SPACE and isinstance(obj, (wx.CheckBox, wx.Button, wx.Slider)):
            event.Skip()
            return

        if code == wx.WXK_SPACE:
            if self.st_status.GetLabel() == "Playing":
                self.on_pause(None)
            else:
                self.on_play(None)
        elif code == wx.WXK_ESCAPE:
             self.GetParent().Close()
        elif ctrl and code == wx.WXK_UP:
            self.adjust_volume(10)
        elif ctrl and code == wx.WXK_DOWN:
            self.adjust_volume(-10)
        elif event.ShiftDown() and code == wx.WXK_UP:
            self.adjust_speed(1)
        elif event.ShiftDown() and code == wx.WXK_DOWN:
            self.adjust_speed(-1)
        elif ctrl and code == wx.WXK_RIGHT:
            self.adjust_seek(10000) # 10s
        elif ctrl and code == wx.WXK_LEFT:
            self.adjust_seek(-10000)
        else:
            event.Skip()

    def adjust_speed(self, delta):
        idx = self.speed_choice.GetSelection()
        count = self.speed_choice.GetCount()
        new_idx = max(0, min(count - 1, idx + delta))
        if new_idx != idx:
            self.speed_choice.SetSelection(new_idx)
            self.on_speed_change(None)

    def adjust_volume(self, delta):
        val = self.volume_slider.GetValue() + delta
        val = max(0, min(100, val))
        self.volume_slider.SetValue(val)
        self.on_volume_change(None)

    def on_volume_change(self, event):
        val = self.volume_slider.GetValue()
        if self.use_vlc and self.vlc_player:
            self.vlc_player.audio_set_volume(val)
        elif self.media_ctrl:
            self.media_ctrl.SetVolume(val / 100.0)

    def adjust_seek(self, delta_ms):
        if self.use_vlc and self.vlc_player:
            current = self.vlc_player.get_time()
            length = self.vlc_player.get_length()
            new_pos = max(0, min(length, current + delta_ms))
            self.vlc_player.set_time(new_pos)
            self.slider.SetValue(new_pos)
        elif self.media_ctrl:
            current = self.media_ctrl.Tell()
            new_pos = current + delta_ms
            length = self.media_ctrl.Length()
            if length > 0:
                new_pos = max(0, min(length, new_pos))
                self.media_ctrl.Seek(new_pos)
                self.slider.SetValue(new_pos)

    def load_media(self, article, is_youtube=False):
        """article should have media_url, title, id, feed_id, chapters optional."""
        url = getattr(article, "media_url", None)
        chapters = getattr(article, "chapters", None)
        self.current_article = article

        self.on_stop(None)
        self.st_status.SetLabel("Loading...")
        self.safety_attempts = 0
        self.pending_url = url
        self.last_load_start_time = time.time()
        self.silence_intervals = [] 
    
        if not chapters:
            self._set_chapters([])
        else:
             self._set_chapters(chapters)

        should_skip_silence = False
        if self.config_manager:
            should_skip_silence = self.config_manager.get("skip_silence", False)
        
        threading.Thread(target=self._smart_load_thread, args=(url, is_youtube, chapters, should_skip_silence), daemon=True).start()

    def _smart_load_thread(self, url, is_youtube, chapters, should_skip_silence):
        resolved_url = url
        
        # 1. Check local file
        try:
            folder = self.get_download_path()
            filename = url.split("/")[-1].split("?")[0]
            if not filename.endswith((".mp3", ".m4a", ".ogg")):
                filename += ".mp3"
            local_path = os.path.join(folder, filename)
            if os.path.exists(local_path):
                 if should_skip_silence:
                     wx.CallAfter(self.st_status.SetLabel, "Analyzing silence...")
                     intervals = self._analyze_silence_ffmpeg(local_path)
                     wx.CallAfter(self._set_silence_intervals, intervals)
                 
                 wx.CallAfter(self._load_direct, local_path)
                 if not chapters:
                     c = self._maybe_fetch_chapters(local_path, False)
                     wx.CallAfter(self._set_chapters, c)
                 return
        except: pass

        # 2. Resolve URL
        try:
            if is_youtube:
                resolved_url = self._resolve_with_ytdlp(url)
            elif url.startswith("http"):
                resolved_url, content_type = self._resolve_redirects(url)
                if content_type and "text/html" in content_type.lower():
                    wx.CallAfter(self.st_status.SetLabel, "Parsing page...")
                    try:
                        extracted = self._resolve_with_ytdlp(url)
                        if extracted:
                            resolved_url = extracted
                    except Exception:
                         pass
        except Exception as e:
            print(f"DEBUG: Resolution error: {e}")

        # 3. Silence Analysis (Download required)
        if should_skip_silence:
            self._download_and_analyze_silence(resolved_url)
            return

        # 4. Update Chapters
        if not chapters and resolved_url and resolved_url != url:
             c = self._maybe_fetch_chapters(resolved_url, False)
             if c: wx.CallAfter(self._set_chapters, c)

        # 5. Play Stream directly
        wx.CallAfter(self._load_direct, resolved_url)

    def _set_silence_intervals(self, intervals):
        self.silence_intervals = intervals

    def _download_and_analyze_silence(self, url):
        import shutil
        import subprocess
        try:
            wx.CallAfter(self.st_status.SetLabel, "Downloading for analysis...")
            resp = utils.safe_requests_get(url, stream=True, timeout=30)
            resp.raise_for_status()
            
            suffix = ".mp3"
            if ".m4a" in url: suffix = ".m4a"
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                for chunk in resp.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                raw_path = tmp.name
            
            wx.CallAfter(self.st_status.SetLabel, "Analyzing silence...")
            intervals = self._analyze_silence_ffmpeg(raw_path)
            wx.CallAfter(self._set_silence_intervals, intervals)
            
            # Play the local file
            wx.CallAfter(self._load_local_file, raw_path)
            
        except Exception as e:
            print(f"Silence analysis failed: {e}")
            wx.CallAfter(self.st_status.SetLabel, "Analysis failed, playing stream...")
            wx.CallAfter(self._load_direct, url)

    def _analyze_silence_ffmpeg(self, input_path):
        import shutil
        import subprocess
        import re
        
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg: return []
            
        # Detect silence: -60dB (was -50dB), min duration 0.4s (400ms) (was 0.25s)
        # Less aggressive to prevent cutting sentence tails/heads
        cmd = [ffmpeg, "-i", input_path, "-af", "silencedetect=noise=-60dB:d=0.4", "-f", "null", "-"]
        intervals = []
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            starts = re.findall(r'silence_start: (\d+(?:\.\d+)?)', res.stderr)
            ends = re.findall(r'silence_end: (\d+(?:\.\d+)?)', res.stderr)
            
            for s, e in zip(starts, ends):
                intervals.append((float(s), float(e)))
        except Exception as e:
            print(f"FFmpeg analysis error: {e}")
        return intervals

    # Removed _resolve_redirects and subsequent methods to rely on existing code, 
    # but wait, I'm replacing a big block. I need to be careful about what I am replacing.
    # The block starts at `load_media` and goes down.
    # I will include `on_speed_change` as the end anchor to ensure I replace the correct section.
    
    # ... Wait, the replacement block above ends at `_analyze_silence_ffmpeg`.
    # I need to make sure I replace `on_skip_silence_toggle` which was AFTER `on_speed_change` in the previous version?
    # Let's check the file structure again.
    # `on_speed_change` is usually near `on_volume_change`.
    # `on_skip_silence_toggle` was added near the end of the file or after `on_speed_change`.
    
    # In the last `read_file` output:
    # `on_speed_change` is followed by `on_skip_silence_toggle`, `on_vlc_end`, `on_vlc_playing`, `on_media_finished`, `on_timer`.
    
    # So I should replace the block from `load_media` down to `on_speed_change` (exclusive) with the new `load_media`...`_analyze_silence_ffmpeg`.
    # And then I need to remove `on_skip_silence_toggle`.
    
    # Actually, `load_media` is quite far up (line ~206).
    # `_analyze_silence_ffmpeg` is after `_download_and_analyze_silence`.
    # `on_skip_silence_toggle` is much further down (line ~866).
    
    # I should do this in multiple replacements.
    
    # 1. Replace `load_media` through `_analyze_silence_ffmpeg` (which covers `_smart_load_thread`, `_download_and_analyze_silence`).
    # 2. Remove `on_skip_silence_toggle`.
    # 3. Update `on_timer`.
    
    # Let's start with step 1: Updating `load_media` and the helper methods.


    def _resolve_redirects(self, url):
        import requests
        headers = {"User-Agent": "BlindRSS/1.0"}
        try:
            resp = requests.head(url, allow_redirects=True, headers=headers, timeout=5)
            if resp.status_code >= 400:
                 resp = requests.get(url, stream=True, allow_redirects=True, headers=headers, timeout=5)
                 resp.close()
            return resp.url, resp.headers.get("Content-Type")
        except Exception as e:
            print(f"DEBUG: Redirect check failed: {e}")
            return url, None

    def _resolve_with_ytdlp(self, url):
        import shutil
        import os
        
        ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = os.path.dirname(ffmpeg_path)
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info['url']
        except Exception as e:
            print(f"DEBUG: yt-dlp failed: {e}. Attempting fallback parsing...")
            try:
                headers = {"User-Agent": "BlindRSS/1.0"}
                resp = utils.safe_requests_get(url, headers=headers, timeout=10)
                if resp.ok:
                    content = resp.text
                    match = re.search(r'href=["\'](https?://[^"\']+\.mp3)(\?[^"\']*)?["\']', content, re.IGNORECASE)
                    if match:
                        return match.group(1)
                    match = re.search(r'src=["\'](https?://[^"\']+\.mp3)(\?[^"\']*)?["\']', content, re.IGNORECASE)
                    if match:
                        return match.group(1)
            except Exception:
                pass
            raise e

    def get_download_path(self):
        base = os.path.dirname(os.path.abspath(sys.argv[0])) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "Podcasts")
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def on_download_btn(self, event):
        if not self.pending_url:
            return
        if self.downloader and getattr(self, "current_article", None):
            # Queue via download manager
            art = self.current_article
            class Stub:
                pass
            stub = Stub()
            stub.id = getattr(art, "id", "")
            stub.feed_id = getattr(art, "feed_id", "")
            stub.title = getattr(art, "title", "Unknown")
            stub.media_url = getattr(art, "media_url", self.pending_url)
            self.downloader.queue_article(stub)
            wx.CallAfter(self.st_status.SetLabel, "Queued for download.")
        else:
            threading.Thread(target=self._manual_download_thread, args=(self.pending_url,), daemon=True).start()

    def _manual_download_thread(self, url):
        try:
            folder = self.get_download_path()
            filename = url.split("/")[-1].split("?")[0]
            if not filename.endswith((".mp3", ".m4a", ".ogg")):
                filename += ".mp3"
            
            target = os.path.join(folder, filename)
            wx.CallAfter(self.st_status.SetLabel, "Downloading...")
            
            resp = utils.safe_requests_get(url, stream=True, timeout=30)
            resp.raise_for_status()
            
            with open(target, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            wx.CallAfter(self.st_status.SetLabel, f"Downloaded: {filename}")
        except Exception as e:
            print(f"Download failed: {e}")
            wx.CallAfter(self.st_status.SetLabel, "Download failed.")

    def _load_direct(self, url):
        if not url:
            self.st_status.SetLabel("No media URL provided.")
            return

        filename = url.split("/")[-1].split("?")[0]
        if not filename.endswith((".mp3", ".m4a", ".ogg")):
            filename += ".mp3"
        
        local_path = os.path.join(self.get_download_path(), filename)
        if os.path.exists(local_path):
             url = local_path
        elif url.startswith("http"):
            if self.proxy:
                self.proxy.stop()
            
            self.st_status.SetLabel("Buffering...")
            self.proxy = StreamProxy(url)
            try:
                url = self.proxy.start()
            except Exception as e:
                print(f"Proxy start failed: {e}")
                self.proxy = None
        
        self.safety_timer.Stop()
        
        if self.use_vlc and self.vlc_player:
            try:
                media = self.vlc_instance.media_new(url)
                media.add_option(":network-caching=100")
                media.add_option(":file-caching=100")
                media.add_option(":live-caching=100")
                
                self.vlc_player.set_media(media)
                
                if self.vlc_player.play() == -1:
                    self.st_status.SetLabel("Error starting playback")
                else:
                    self.st_status.SetLabel("Playing (VLC)")
                    self.timer.Start(100)
                    self._apply_rate()
            except Exception as e:
                print(f"VLC Load Error: {e}")
                self.st_status.SetLabel("VLC Error")
        if self.media_ctrl:
            if not self.media_ctrl.Load(url):
                self._trigger_fallback(url)
            else:
                self.st_status.SetLabel("Loading media stream...")
                self.safety_timer.Start(500)

    def _load_local_file(self, path):
        self.temp_file = path
        self.st_status.SetLabel("Playing Downloaded File")
        
        if self.use_vlc and self.vlc_player:
            try:
                media = self.vlc_instance.media_new(path)
                self.vlc_player.set_media(media)
                self.vlc_player.play()
                self.timer.Start(100)
            except Exception as e:
                print(f"VLC Local Load Error: {e}")
        elif self.media_ctrl:
            if self.media_ctrl.Load(path):
                self.media_ctrl.Play()
                self.timer.Start(100)
            else:
                self.st_status.SetLabel("Playback failed even after download.")

    def _activate_chapter(self, idx):
        if idx < 0 or idx >= self.chapters.GetCount():
            return
        ms = self.chapters_ms[idx] if hasattr(self, "chapters_ms") and idx < len(self.chapters_ms) else 0
        if self.use_vlc and self.vlc_player:
            self.vlc_player.set_time(ms)
            self.slider.SetValue(ms)
        elif self.media_ctrl:
            try:
                self.media_ctrl.Pause()
                self.media_ctrl.Seek(ms)
                self.slider.SetValue(ms)
                self.media_ctrl.Play()
                self.timer.Start(100)
            except Exception as e:
                print(f"Chapter seek failed: {e}")

    def on_safety_timer(self, event):
        if self.use_vlc: 
            self.safety_timer.Stop()
            return
        try:
            state = self.media_ctrl.GetState()
        except Exception:
            state = None
        if state == wx.media.MEDIASTATE_PLAYING:
            self.safety_timer.Stop()
            self.st_status.SetLabel("Playing")
            return
        if getattr(self, "safety_attempts", 0) >= 10:
            self.safety_timer.Stop()
            self._trigger_fallback(self.pending_url)
            return
        self.safety_attempts += 1
        if not self.media_ctrl.Play():
            try:
                self.media_ctrl.Seek(0)
                self.media_ctrl.Play()
            except Exception:
                pass
        else:
            self.timer.Start(100)
            self.st_status.SetLabel("Playing")

    def on_media_loaded(self, event):
        self.safety_timer.Stop()
        self.st_status.SetLabel("Media Loaded")
        if not self.media_ctrl.Play():
            if not self.safety_timer.IsRunning():
                self.safety_timer.Start(500)
            self.st_status.SetLabel("Ready to Play")
        else:
            self.timer.Start(100)
            self.st_status.SetLabel("Playing")
            self.btn_pause.SetFocus()
            self._apply_rate()

    def on_play(self, event):
        if self.use_vlc and self.vlc_player:
            self.vlc_player.play()
        elif self.media_ctrl:
            self.media_ctrl.Play()
        self.timer.Start(100)
        self.st_status.SetLabel("Playing")
        self.btn_pause.SetFocus()

    def on_pause(self, event):
        if self.use_vlc and self.vlc_player:
            self.vlc_player.pause()
        elif self.media_ctrl:
            self.media_ctrl.Pause()
        self.timer.Stop()
        self.st_status.SetLabel("Paused")
        self.btn_play.SetFocus()

    def on_stop(self, event):
        if self.use_vlc and self.vlc_player:
            self.vlc_player.stop()
        elif self.media_ctrl:
            self.media_ctrl.Stop()
        self.timer.Stop()
        self.safety_timer.Stop()
        self.slider.SetValue(0)
        self.st_status.SetLabel("Stopped")
        self.btn_play.SetFocus()
        
        if self.proxy:
            self.proxy.stop()
            self.proxy = None

    def on_speed_change(self, event):
        val = self.speed_choice.GetStringSelection()
        try:
            rate = float(val.replace("x", ""))
            self.current_rate = rate
            self._apply_rate()
        except Exception as e:
            print(f"Speed change error: {e}")

    def _apply_rate(self):
        try:
            if self.use_vlc and self.vlc_player:
                self.vlc_player.set_rate(self.current_rate)
            elif self.media_ctrl:
                self.media_ctrl.SetPlaybackRate(self.current_rate)
        except Exception:
            pass

    def on_vlc_end(self, event):
        wx.CallAfter(self.on_media_finished, None)

    def on_vlc_playing(self, event):
        wx.CallAfter(self.st_status.SetLabel, "Playing")
        wx.CallAfter(self.on_speed_change, None)

    def on_media_finished(self, event):
        if self.queue:
            next_item = self.queue.pop(0)
            wx.CallAfter(self.st_status.SetLabel, f"Playing next: {next_item['url']}")
            wx.CallAfter(self.load_media, next_item['url'], next_item['is_youtube'], next_item['chapters'])
        else:
            self.on_stop(None)
            self.st_status.SetLabel("Finished")

    def on_timer(self, event):
        if self.use_vlc and self.vlc_player:
            length = self.vlc_player.get_length()
            if length > 0:
                current_ms = self.vlc_player.get_time()
                current_sec = current_ms / 1000.0
                
                # Check global config for skipping
                should_skip = False
                if self.config_manager:
                    should_skip = self.config_manager.get("skip_silence", False)

                # Cooldown check to prevent rapid-fire seeking loops
                now = time.time()
                if getattr(self, '_last_seek_time', 0) + 0.5 < now:
                    if should_skip and self.silence_intervals:
                        for start, end in self.silence_intervals:
                            # If we are inside a silence interval (and not just at the edge)
                            if start <= current_sec < end - 0.05:
                                target_ms = int(end * 1000) + 30 # Ensure we land PAST the silence
                                self.vlc_player.set_time(target_ms)
                                self._last_seek_time = now
                                current_ms = target_ms
                                break
                            # Optimization: intervals are sorted
                            if start > current_sec + 2.0: 
                                break

                self.slider.SetMax(length)
                self.slider.SetValue(current_ms)
                self._highlight_chapter(current_ms / 1000.0)
        elif self.media_ctrl:
            offset = self.media_ctrl.Tell()
            length = self.media_ctrl.Length()
            if length > 0:
                self.slider.SetMax(length)
                self.slider.SetValue(offset)
                self._highlight_chapter(offset / 1000.0)

    def on_seek(self, event):
        offset = self.slider.GetValue()
        if self.use_vlc and self.vlc_player:
            self.vlc_player.set_time(offset)
        elif self.media_ctrl:
            self.media_ctrl.Seek(offset)

    def _set_chapters(self, chapters):
        self.current_chapters = chapters
        self.chapters.Clear()
        for ch in chapters:
            start = ch.get("start", 0)
            mins = int(start // 60)
            secs = int(start % 60)
            start_str = f"{mins:02d}:{secs:02d}"
            title = ch.get("title", "")
            display = f"{start_str}  {title}"
            self.chapters.Append(display)
        self.chapters_ms = [int((ch.get("start", 0) or 0) * 1000) for ch in chapters]

    def _trigger_fallback(self, url):
        if self.fallback_active:
            return
        self.fallback_active = True
        self.st_status.SetLabel("Streaming failed. Downloading...")
        threading.Thread(target=self._download_and_play_thread, args=(url,), daemon=True).start()

    def _download_and_play_thread(self, url):
        try:
            resp = utils.safe_requests_get(url, stream=True, timeout=30)
            resp.raise_for_status()
            suffix = ".mp3"
            if ".m4a" in url: suffix = ".m4a"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                for chunk in resp.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                tmp_path = tmp.name
            wx.CallAfter(self._load_local_file, tmp_path)
        except Exception as e:
            print(f"Fallback download error: {e}")
            wx.CallAfter(self.st_status.SetLabel, "Download failed.")

    def update_chapters(self, chapters):
        wx.CallAfter(self._set_chapters, chapters)

    def add_to_queue(self, url, is_youtube=False, chapters=None):
        self.queue.append({"url": url, "is_youtube": is_youtube, "chapters": chapters})
        self.st_status.SetLabel(f"Added to queue ({len(self.queue)} items)")

    def on_chapter_activated(self, event):
        idx = event.GetSelection()
        self._activate_chapter(idx)

    def on_chapter_key(self, event):
        code = event.GetKeyCode()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            idx = self.chapters.GetSelection()
            if idx != -1:
                self._activate_chapter(idx)
                return
        event.Skip()

    def _highlight_chapter(self, current_seconds):
        if not self.current_chapters:
            return
        active_idx = -1
        for i, ch in enumerate(self.current_chapters):
            start = ch.get("start", 0)
            next_start = self.current_chapters[i+1].get("start", 1e12) if i+1 < len(self.current_chapters) else 1e12
            if start <= current_seconds < next_start:
                active_idx = i
                break
        if active_idx >= 0:
            # wx.ListBox uses IsSelected; GetFirstSelected is ListCtrl-only
            if not self.chapters.IsSelected(active_idx):
                self.chapters.SetSelection(active_idx)
                self.chapters.EnsureVisible(active_idx)

    def _maybe_fetch_chapters(self, url, is_youtube):
        if is_youtube or not url or not url.lower().endswith((".mp3", ".m4a", ".m4b", ".aac", ".ogg", ".opus")):
            return []
        try:
            import requests, io
            from mutagen.id3 import ID3
            head = requests.get(url, headers={"Range": "bytes=0-4000000"}, timeout=12).content
            id3 = ID3(io.BytesIO(head))
            chapters = []
            for frame in id3.getall("CHAP"):
                start = frame.start_time / 1000.0 if frame.start_time else 0
                title_ch = ""
                tit2 = frame.sub_frames.get("TIT2")
                if tit2 and tit2.text:
                    title_ch = tit2.text[0]
                chapters.append({"start": float(start), "title": title_ch, "href": None})
            return chapters
        except Exception:
            return []

class PlayerFrame(wx.Frame):
    def __init__(self, parent, downloader=None):
        super().__init__(parent, title="Media Player", size=(400, 200))
        self.panel = MediaPlayerPanel(
            self,
            config_manager=getattr(parent, 'config_manager', None),
            downloader=downloader
        )
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.panel, 1, wx.EXPAND)
        self.SetSizer(sizer)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_close(self, event):
        self.Hide() 
        
    def load_media(self, article, is_youtube=False):
        self.panel.load_media(article, is_youtube)
        if not self.IsShown():
            self.Show()
        self.Raise()

    def add_to_queue(self, url, is_youtube=False, chapters=None):
        self.panel.add_to_queue(url, is_youtube, chapters)

    def update_chapters(self, chapters):
        self.panel.update_chapters(chapters)

    def stop(self):
        self.panel.stop()
