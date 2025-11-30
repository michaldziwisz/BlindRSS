@echo off
setlocal

echo [BlindRss Setup] Checking system requirements...

:: 1. Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python not found.
    echo [*] Attempting to install Python 3 (64-bit) via Winget...
    
    :: Check if Winget is available
    winget --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [X] Winget is not available. Please install Python 3.13+ (64-bit) manually from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    
    :: Install Python
    winget install -e --id Python.Python.3.13 --scope machine
    if %errorlevel% neq 0 (
        echo [X] Python installation failed. Please install manually.
        pause
        exit /b 1
    )
    
    echo [+] Python installed. You may need to restart your terminal or computer to refresh environment variables.
    echo     Please restart this script after doing so.
    pause
    exit /b 0
) else (
    echo [V] Python is present.
)

:: 2. Check for Pip
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Pip not found. Installing pip...
    python -m ensurepip --default-pip
    if %errorlevel% neq 0 (
        echo [X] Failed to install pip.
        pause
        exit /b 1
    )
) else (
    echo [V] Pip is present.
)

:: 3. Install Dependencies
echo [*] Installing dependencies from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [X] Failed to install base requirements.
    pause
    exit /b 1
)

echo [*] Ensuring yt-dlp is up to date...
pip install --upgrade yt-dlp
if %errorlevel% neq 0 (
    echo [X] Failed to update yt-dlp.
    pause
    exit /b 1
)

echo [V] Setup complete! You can now run the application using: python main.py
pause
