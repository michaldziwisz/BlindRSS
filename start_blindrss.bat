@echo off
setlocal

echo [BlindRss Launcher]
echo Checking system...

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python not found. Attempting install...
    winget install -e --id Python.Python.3.13 --scope machine
    if %errorlevel% neq 0 (
        echo [X] Failed to install Python. Please install manually.
        pause
        exit /b 1
    )
    echo [+] Python installed. Restarting script...
    endlocal
    %0
    exit /b
)

:: 2. Check Pip
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Pip not found. Installing...
    python -m ensurepip --default-pip
)

:: 3. Run Application
:: main.py contains internal dependency checks (invisible)
echo Starting BlindRSS...
python main.py
