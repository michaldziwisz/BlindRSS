@echo off
setlocal enabledelayedexpansion

:: BlindRSS portable builder
:: Creates a local venv, installs build deps, runs PyInstaller, and stages
:: runtime companion files next to the generated exe.

set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%"

set VENV_DIR=%SCRIPT_DIR%.venv

echo [BlindRSS Build] Preparing Python environment...
if not exist "%VENV_DIR%" (
    python -m venv "%VENV_DIR%"
)

:: Use direct paths to venv binaries to avoid activation issues in some shells
set VENV_PYTHON="%VENV_DIR%\Scripts\python.exe"
set VENV_PIP="%VENV_DIR%\Scripts\pip.exe"
set VENV_PYINSTALLER="%VENV_DIR%\Scripts\pyinstaller.exe"

echo [BlindRSS Build] Updating build tools...
%VENV_PYTHON% -m pip install --upgrade pip >nul
%VENV_PYTHON% -m pip install --upgrade pyinstaller packaging >nul

echo [BlindRSS Build] Installing dependencies from requirements.txt...
if exist "requirements.txt" (
    %VENV_PYTHON% -m pip install -r requirements.txt >nul
) else (
    echo [!] requirements.txt not found. Installing defaults...
    %VENV_PYTHON% -m pip install wxPython feedparser requests beautifulsoup4 yt-dlp python-dateutil mutagen python-vlc pychromecast async-upnp-client pyatv trafilatura webrtcvad brotli html5lib lxml setuptools^<81 >nul
)

:: Ensure config.json exists at root for source runs and to be copied to dist
if not exist "%SCRIPT_DIR%config.json" (
    echo [BlindRSS Build] Creating default config.json...
    echo { "active_provider": "local" } > "%SCRIPT_DIR%config.json"
)

echo [BlindRSS Build] Cleaning previous build...
if exist "%SCRIPT_DIR%build" rd /s /q "%SCRIPT_DIR%build"
if exist "%SCRIPT_DIR%dist" rd /s /q "%SCRIPT_DIR%dist"

echo [BlindRSS Build] Running PyInstaller (main.spec)...
if exist "main.spec" (
    %VENV_PYINSTALLER% --clean --noconfirm main.spec
) else (
    echo [!] main.spec not found. Running basic one-file build...
    %VENV_PYINSTALLER% --onefile --noconfirm --name BlindRSS main.py
)

echo [BlindRSS Build] Refreshing VLC plugins cache...
set VLC_DIR=C:\Program Files\VideoLAN\VLC
if not exist "%VLC_DIR%\vlc-cache-gen.exe" set VLC_DIR=C:\Program Files (x86)\VideoLAN\VLC
set VLC_CACHE_GEN=%VLC_DIR%\vlc-cache-gen.exe

set DIST_PLUGINS=%SCRIPT_DIR%dist\BlindRSS\_internal\plugins
if not exist "%DIST_PLUGINS%" set DIST_PLUGINS=%SCRIPT_DIR%dist\BlindRSS\plugins

if exist "%DIST_PLUGINS%" (
    if exist "%DIST_PLUGINS%\plugins.dat" del /f /q "%DIST_PLUGINS%\plugins.dat"
    if exist "%VLC_CACHE_GEN%" (
        "%VLC_CACHE_GEN%" "%DIST_PLUGINS%" >nul 2>nul
    ) else (
        echo [!] vlc-cache-gen.exe not found. Plugins cache will be rebuilt at runtime.
    )
) else (
    echo [!] VLC plugins directory not found in dist. Skipping cache refresh.
)

echo [BlindRSS Build] Staging companion files into dist...
if exist "%SCRIPT_DIR%README.md" copy /Y "%SCRIPT_DIR%README.md" "%SCRIPT_DIR%dist\README.md" >nul

echo [BlindRSS Build] Copying exe to repo root...
if exist "%SCRIPT_DIR%dist\BlindRSS.exe" copy /Y "%SCRIPT_DIR%dist\BlindRSS.exe" "%SCRIPT_DIR%BlindRSS.exe" >nul

echo [BlindRSS Build] Done. Output: BlindRSS.exe and companion files in dist\ 

popd
endlocal
