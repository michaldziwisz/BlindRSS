# BlindRSS

Screen-reader friendly vibed RSS & Podcast player. Local, fast, and keyboard-first.

## Quick Start

### Windows (Easy)
1. Download `BlindRSS.exe` from releases.
2. Run `BlindRSS.exe`.

### Build it yourself (PyInstaller)
1. Install Python 3.13 and the requirements: `pip install -r requirements.txt`
2. From repo root run: `pyinstaller --clean --noconfirm main.spec`
3. Launch the generated `dist/BlindRSS.exe` (bundles casting stacks, full-text extraction, yt-dlp, certifi, and webrtcvad).

### Python (All OS)
1. Install Python 3.13.
2. Run: `pip install -r requirements.txt`
3. Run: `python main.py`

*Note: On first launch, the app automatically attempts to install system-level dependencies like **VLC** and **FFmpeg** (using Winget on Windows, Brew on macOS, or the system package manager on Linux). It also auto-downloads tools like `yt-dlp` if missing.*

## Troubleshooting

- **VLC Error:** If the app says VLC could not be initialized, make sure you have the **64-bit version** of VLC installed. The 32-bit version will not work with this application.
- **FFmpeg missing:** If "Skip Silence" or "Cast" doesn't work, ensure FFmpeg is installed and in your PATH. The app attempts to do this for you on Windows via Winget.

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
