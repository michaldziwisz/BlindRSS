# BlindRSS

This is an accessible, fast RSS + Podcast reader with a built‑in download manager, optamized for screen reader users.

## Features
- Screen reader friendly: standard wx controls, predictable focus.
- Fast refresh; parallel feed fetch.
- Podcast playback with chapters and playback speed changes.
- Download Manager: queue from article context menu or player; per-feed folders; filenames Title - with dates; pause/resume/cancel/cancel all; max concurrent downloads is configurable.
- Tray icon: restore, refresh, playback and download controls.
- Close-to-tray option (off by default).

## Get it
1) Download the latest `BlindRSS.exe` from Releases.
2) Keep `BlindRSS.exe`, `rss.db`, and `config.json` together (they’re auto-created on first run if missing).

## Quick use
1. Run `BlindRSS.exe`.
2. Add feed: `Ctrl+N`, paste URL.
3. Read: arrow in Feeds, `Tab`/`F6` to Articles, `Enter` to open.
4. Download an episode: right-click article → Download (or use the player Download button). Tools → Download Manager to watch/pause/cancel.
5. Settings: Tools → Settings (providers, refresh interval, max downloads, close-to-tray, etc.).

## Keyboard shortcuts
Main window:
- F6: cycle panes
- Ctrl+N: add feed
- Delete: remove feed/category
- Ctrl+P: open player
- F5 / Ctrl+R: refresh feeds
- Alt+F4: minimize to tray if enabled

Player:
- Space: play/pause
- Ctrl+Left/Right: seek 10s
- Ctrl+Up/Down: volume
- Shift+Up/Down: speed
- Enter: play selected chapter
- Escape: hide player

## Build from source
Prereqs: Python 3.13, pip, PyInstaller.
```
pip install -r requirements.txt
pyinstaller --clean main.spec
```
Output: `dist/BlindRSS.exe`.

## Support
Issues/PRs welcome; support is best-effort.
