# BlindRSS

BlindRSS is a Screen-reader friendly vibed RSS & Podcast player. It is fast, easy to use, and it supports all the rss feed providers you expect.

## Quick Start

### Windows (Easy)
1. Download `BlindRSS.exe` from [releases](https://github.com/serrebi/BlindRSS/releases
   .
2. Extract it to a portable location of your choice, and Run `BlindRSS.exe`.

## Updater (Windows)
BlindRSS can check GitHub Releases for updates, verify integrity, and safely swap in new files when there is a new version available.

- Checks GitHub Releases for `BlindRSS-update.json` and the versioned zip asset.
- Verifies SHA-256 of the downloaded zip and Authenticode signature of `BlindRSS.exe`.
- Uses `update_helper.bat` to stage, swap, keep a backup, and restart.
- Toggle auto-check in Settings: "Check for updates on startup" (default ON).
- Manual check: Tools → "Check for Updates..."

### Build it yourself (PyInstaller)
1. Install Python 3.12+ and requirements: `pip install -r requirements.txt`.
2. Ensure **VLC Media Player (64-bit)** is installed at `C:\Program Files\VideoLAN\VLC`.
3. Run the build script:
### Prerequisites for the build.bat
- Code signing certificate installed and accessible to `signtool`.
- `signtool.exe` from Windows SDK (override path with `SIGNTOOL_PATH`).
- GitHub CLI (`gh`) authenticated (`gh auth login`).

### How to build with build.bat
  `.\build.bat` with one of these options:
- `build.bat build`   builds + signs + zips locally (no git/release).
- `build.bat release` computes next version, bumps code, builds, signs, zips, generates update manifest, tags, pushes, and creates a GitHub release.
- `build.bat dry-run` prints what it would do.

4. The application will be generated in `dist/BlindRSS/`. Run `dist/BlindRSS/BlindRSS.exe`.

### Python (All OS)
1. Install Python 3.12.
2. Run: `pip3 install -r requirements.txt`
3. Run: `python main.py`




### Update Manifest
Each release includes `BlindRSS-update.json` with:
- version, asset name, download URL, SHA-256, publish date, and summary.
