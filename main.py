import warnings
# Suppress pkg_resources deprecation noise from webrtcvad immediately
warnings.filterwarnings("ignore", category=UserWarning, message=r"pkg_resources is deprecated as an API.*")
warnings.filterwarnings("ignore", category=UserWarning, module="pkg_resources")

import sys
import multiprocessing
import logging
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Silence noisy third-party loggers
logging.getLogger("trafilatura").setLevel(logging.CRITICAL)
logging.getLogger("readability").setLevel(logging.CRITICAL)
log = logging.getLogger(__name__)

# Essential imports
from core.dependency_check import check_and_install_dependencies
import wx
from core.config import ConfigManager
from core.factory import get_provider
from gui.mainframe import MainFrame
from core.stream_proxy import get_proxy
from core.range_cache_proxy import get_range_cache_proxy

class GlobalMediaKeyFilter(wx.EventFilter):
    """Capture media shortcuts globally so they work in dialogs too."""

    def __init__(self, frame: MainFrame):
        super().__init__()
        self.frame = frame

    def FilterEvent(self, event):
        try:
            # Check if the frame is still alive (C++ object valid)
            if not self.frame:
                return wx.EventFilter.Event_Skip

            if not isinstance(event, wx.KeyEvent):
                return wx.EventFilter.Event_Skip

            # Only react to key-down/char events. Handling KEY_UP can cause double-seeks.
            try:
                et = int(event.GetEventType())
            except Exception:
                et = -1
            if et not in (getattr(wx, 'wxEVT_KEY_DOWN', -1), getattr(wx, 'wxEVT_CHAR_HOOK', -1), getattr(wx, 'wxEVT_CHAR', -1)):
                return wx.EventFilter.Event_Skip

            if event.ControlDown():
                key = int(event.GetKeyCode())

                # Ctrl+P: toggle player window
                if key in (ord('P'), ord('p')):
                    try:
                        self.frame.toggle_player_visibility()
                    except Exception as e:
                        log.debug(f"Error toggling player visibility: {e}")
                    return wx.EventFilter.Event_Processed

                pw = getattr(self.frame, "player_window", None)
                if pw:
                    # Use the same hold-to-repeat gate everywhere to avoid multi-seek bursts.
                    hk = getattr(self.frame, "_media_hotkeys", None)
                    if hk is not None:
                        actions = {
                            wx.WXK_UP: lambda: pw.adjust_volume(int(getattr(pw, "volume_step", 5))),
                            wx.WXK_DOWN: lambda: pw.adjust_volume(-int(getattr(pw, "volume_step", 5))),
                        }
                        if getattr(pw, "has_media_loaded", lambda: False)():
                            actions[wx.WXK_LEFT] = lambda: pw.seek_relative_ms(-int(getattr(pw, "seek_back_ms", 10000)))
                            actions[wx.WXK_RIGHT] = lambda: pw.seek_relative_ms(int(getattr(pw, "seek_forward_ms", 10000)))
                        if hk.handle_ctrl_key(event, actions):
                            return wx.EventFilter.Event_Processed
        except Exception as e:
            # Suppress dead object errors during shutdown
            if "PyDeadObjectError" not in str(e):
                log.debug(f"Error in GlobalMediaKeyFilter: {e}")
        return wx.EventFilter.Event_Skip

class RSSApp(wx.App):
    def OnInit(self):
        # Run dependency check in background so GUI is not blocked
        threading.Thread(target=check_and_install_dependencies, daemon=True).start()

        self.config_manager = ConfigManager()
        self.provider = get_provider(self.config_manager)
        
        self.frame = MainFrame(self.provider, self.config_manager)
        self.frame.Show()

        # Install a global filter so media shortcuts work everywhere (including modal dialogs)
        try:
            # Keep a reference so it is not garbage-collected.
            self._media_filter = GlobalMediaKeyFilter(self.frame)
            wx.EvtHandler.AddFilter(self._media_filter)
        except Exception as e:
            log.error(f"Failed to install global media filter: {e}")
        return True

    def OnExit(self):
        log.info("Shutting down proxies...")
        try:
            get_proxy().stop()
        except Exception as e:
            log.error(f"Error stopping StreamProxy: {e}")
        
        try:
            get_range_cache_proxy().stop()
        except Exception as e:
            log.error(f"Error stopping RangeCacheProxy: {e}")
        return 0

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = RSSApp()
    app.MainLoop()