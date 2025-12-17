import time
import sys
import ctypes
from typing import Callable, Dict, Tuple, Optional

import wx


class HoldRepeatHotkeys:
    """Hold-to-repeat behavior for Ctrl+key shortcuts.

    Goals:
    - Quick tap fires exactly once.
    - Holding repeats after hold_delay_s, then every repeat_interval_s.
    - Repeat should not randomly stop on Windows.
    """

    def __init__(
        self,
        owner: wx.Window,
        hold_delay_s: float = 0.20,
        repeat_interval_s: float = 0.12,
        poll_interval_ms: int = 15,
        release_grace_polls: int = 6,
    ):
        self._owner = owner
        self._hold_delay_s = float(hold_delay_s)
        self._repeat_interval_s = float(repeat_interval_s)
        self._poll_interval_ms = int(poll_interval_ms)
        self._release_grace_polls = max(1, int(release_grace_polls))

        # Active combos: (mods_mask, keycode) -> state dict
        # mods_mask: bit1 == CTRL
        self._active: Dict[Tuple[int, int], Dict[str, object]] = {}

        self._timer = wx.Timer(owner)
        owner.Bind(wx.EVT_TIMER, self._on_timer, self._timer)

        # Best-effort KEY_UP stopping (helps when key-state polling is flaky)
        try:
            owner.Bind(wx.EVT_KEY_UP, self._on_key_up)
        except Exception:
            pass
        try:
            owner.Bind(wx.EVT_KILL_FOCUS, self._on_kill_focus)
        except Exception:
            pass
        try:
            owner.Bind(wx.EVT_ACTIVATE, self._on_activate)
        except Exception:
            pass

    def stop(self) -> None:
        try:
            if self._timer.IsRunning():
                self._timer.Stop()
        except Exception:
            pass
        self._active.clear()

    # ------------------------------------------------------------
    # Key state helpers
    # ------------------------------------------------------------

    def _win_key_down_vk(self, vk: int) -> bool:
        try:
            if not sys.platform.startswith("win"):
                return False
            state = ctypes.windll.user32.GetAsyncKeyState(int(vk))
            return bool(state & 0x8000)
        except Exception:
            return False

    def _keycode_to_vk(self, keycode: int) -> Optional[int]:
        # Virtual key codes for common special keys
        if keycode == wx.WXK_LEFT:
            return 0x25
        if keycode == wx.WXK_UP:
            return 0x26
        if keycode == wx.WXK_RIGHT:
            return 0x27
        if keycode == wx.WXK_DOWN:
            return 0x28
        if keycode == wx.WXK_CONTROL:
            return 0x11
        return None

    def _is_key_down(self, keycode: int) -> bool:
        """Return best-effort physical key state.

        Prefer wx.GetKeyState (works well with wx focus routing), and OR it with
        Win32 GetAsyncKeyState as a fallback.
        """
        down = False
        try:
            down = bool(wx.GetKeyState(int(keycode)))
        except Exception:
            down = False

        # Win32 fallback
        if not down and sys.platform.startswith("win"):
            vk = self._keycode_to_vk(int(keycode))
            if vk is not None:
                down = down or self._win_key_down_vk(vk)
            else:
                # For alphanumerics, VK codes match ASCII for A-Z and 0-9.
                try:
                    kc = int(keycode)
                    if 0x30 <= kc <= 0x39 or 0x41 <= kc <= 0x5A:
                        down = down or self._win_key_down_vk(kc)
                except Exception:
                    pass

        return bool(down)

    def _combo_is_down(self, keycode: int) -> bool:
        # Only CTRL combos are supported currently.
        try:
            return bool(self._is_key_down(wx.WXK_CONTROL) and self._is_key_down(int(keycode)))
        except Exception:
            return False

    # ------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------

    def handle_ctrl_key(
        self,
        event: wx.KeyEvent,
        actions_by_keycode: Dict[int, Callable[[], None]],
    ) -> bool:
        """Handle Ctrl+<key> with hold-to-repeat behavior.

        Returns True if handled and the event should be swallowed.
        """
        try:
            if not event.ControlDown():
                return False
            key = int(event.GetKeyCode())
        except Exception:
            return False

        cb = actions_by_keycode.get(key)
        if cb is None:
            return False

        combo_id = (1, key)  # 1 == CTRL
        now = time.monotonic()

        is_auto_repeat = False
        try:
            is_auto_repeat = bool(getattr(event, "IsAutoRepeat", lambda: False)())
        except Exception:
            is_auto_repeat = False

        st = self._active.get(combo_id)

        # Treat any non-auto-repeat event as a fresh press so taps never feel delayed.
        if st is None or not is_auto_repeat:
            st = {}
            self._active[combo_id] = st
            st["start"] = now
            st["last_fire"] = 0.0
            st["cb"] = cb
            st["key"] = key
            st["miss"] = 0
            st["last_event"] = now

            # Fire immediately once.
            try:
                cb()
            except Exception:
                pass
            st["last_fire"] = now
        else:
            # Auto-repeat keydown: just refresh callback and keep-alive.
            try:
                st["cb"] = cb
                st["last_event"] = now
            except Exception:
                pass

        # Ensure polling is running.
        try:
            if not self._timer.IsRunning():
                self._timer.Start(self._poll_interval_ms)
        except Exception:
            pass

        return True

    def _on_key_up(self, event: wx.KeyEvent) -> None:
        try:
            key = int(event.GetKeyCode())
        except Exception:
            key = None

        try:
            to_remove = []
            for (mods, k), st in list(self._active.items()):
                if mods != 1:
                    continue
                # If CTRL released, stop all CTRL combos.
                if key == wx.WXK_CONTROL:
                    to_remove.append((mods, k))
                    continue
                # If the combo key released, stop that combo.
                if key is not None and key == k:
                    to_remove.append((mods, k))
            for cid in to_remove:
                self._active.pop(cid, None)
        except Exception:
            pass

        try:
            if not self._active and self._timer.IsRunning():
                self._timer.Stop()
        except Exception:
            pass

        try:
            event.Skip()
        except Exception:
            pass

    def _on_kill_focus(self, event) -> None:
        try:
            self.stop()
        except Exception:
            pass
        try:
            event.Skip()
        except Exception:
            pass

    def _on_activate(self, event) -> None:
        try:
            if hasattr(event, "GetActive") and not event.GetActive():
                self.stop()
        except Exception:
            pass
        try:
            event.Skip()
        except Exception:
            pass

    def _on_timer(self, _evt: wx.TimerEvent) -> None:
        if not self._active:
            try:
                if self._timer.IsRunning():
                    self._timer.Stop()
            except Exception:
                pass
            return

        now = time.monotonic()

        for combo_id, st in list(self._active.items()):
            mods, key = combo_id
            if mods != 1:
                self._active.pop(combo_id, None)
                continue

            try:
                start = float(st.get("start", now))
            except Exception:
                start = now
            try:
                last_fire = float(st.get("last_fire", 0.0))
            except Exception:
                last_fire = 0.0
            try:
                miss = int(st.get("miss", 0))
            except Exception:
                miss = 0

            cb = st.get("cb")
            if not callable(cb):
                self._active.pop(combo_id, None)
                continue

            # Check for release. Use a small grace window to avoid random false negatives.
            down = True
            try:
                down = self._combo_is_down(int(key))
            except Exception:
                down = True

            if not down:
                miss += 1
                st["miss"] = miss
                if miss >= self._release_grace_polls:
                    self._active.pop(combo_id, None)
                    continue
            else:
                st["miss"] = 0

            if (now - start) < self._hold_delay_s:
                continue
            if (now - last_fire) < self._repeat_interval_s:
                continue

            try:
                cb()
            except Exception:
                pass
            st["last_fire"] = now

        # Stop timer if nothing active.
        try:
            if not self._active and self._timer.IsRunning():
                self._timer.Stop()
        except Exception:
            pass
