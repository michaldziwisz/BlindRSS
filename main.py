import sys
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # Ensure dependencies/media tools are present (even when frozen)
    try:
        from core.dependency_check import check_and_install_dependencies
        check_and_install_dependencies()
    except Exception:
        pass 

    import wx
    from core.config import ConfigManager
    from core.factory import get_provider
    from gui.mainframe import MainFrame

    class GlobalMediaKeyFilter(wx.EventFilter):
        """Capture media shortcuts globally so they work in dialogs too."""

        def __init__(self, frame: MainFrame):
            super().__init__()
            self.frame = frame

        def FilterEvent(self, event):
            try:
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
                        except Exception:
                            pass
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
            except Exception:
                pass
            return wx.EventFilter.Event_Skip

    class RSSApp(wx.App):
        def OnInit(self):
            self.config_manager = ConfigManager()
            self.provider = get_provider(self.config_manager)
            
            self.frame = MainFrame(self.provider, self.config_manager)
            self.frame.Show()

            # Install a global filter so media shortcuts work everywhere (including modal dialogs)
            try:
                # Keep a reference so it is not garbage-collected.
                self._media_filter = GlobalMediaKeyFilter(self.frame)
                wx.EvtHandler.AddFilter(self._media_filter)
            except Exception:
                pass
            return True

    app = RSSApp()
    app.MainLoop()