# BlindRSS

Screen-reader friendly vibed RSS & Podcast player. Local, fast, and keyboard-first.

## Quick Start

### Windows (Easy)
1. Download `BlindRSS.exe` from releases.
2. Run `BlindRSS.exe`.

### Python (All OS)
1. Install Python 3.13 and **VLC**.
2. Run: `pip install -r requirements.txt`
3. Run: `python main.py`

*Note: On launch, the app auto-downloads tools like `yt-dlp` and `ffmpeg`. On Linux, it tries to `sudo` install dependencies (`vlc`, `ffmpeg`). If this bothers you, there's other rss apps*

## Controls

| Key | Action |
| :--- | :--- |
| **F5** | Refresh feeds |
| **F6** | Switch focus (Feeds <-> Articles <-> Text) |
| **Ctrl + N** | Add new feed (paste URL) |
| **Delete** | Remove feed/category |
| **Enter** | Open article / Play audio |
| **Ctrl + P** | Toggle Player window |

## Player

- **Play/Pause:** Space (in player)
- **Seek:** Left/Right arrows
- **Volume:** Up/Down arrows
- **Cast:** Click "Cast" to play on Chromecast/AirPlay/DLNA.

## Tips

- **Tray Icon:** Right-click for quick controls or to restore the window.
- **Import:** File -> Import OPML to add many feeds at once.
- **Full Text:** The app automatically fetches full articles if the feed is just a snippet.
