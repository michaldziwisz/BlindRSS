@echo off
setlocal enabledelayedexpansion

set PID=%~1
set INSTALL_DIR=%~2
set STAGING_DIR=%~3
set EXE_NAME=%~4

if "%PID%"=="" goto :usage
if "%INSTALL_DIR%"=="" goto :usage
if "%STAGING_DIR%"=="" goto :usage
if "%EXE_NAME%"=="" goto :usage

if not exist "%STAGING_DIR%" (
    echo [BlindRSS Update] Staging folder not found: "%STAGING_DIR%"
    exit /b 1
)

echo [BlindRSS Update] Waiting for process %PID% to exit...
:wait_loop
for /f "tokens=1" %%A in ('tasklist /FI "PID eq %PID%" /NH') do (
    if /I not "%%A"=="INFO:" (
        timeout /t 1 /nobreak >nul
        goto wait_loop
    )
)
timeout /t 1 /nobreak >nul

for /f %%T in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyyMMddHHmmss\")"') do set STAMP=%%T
set BACKUP_DIR=%INSTALL_DIR%_backup_%STAMP%

if exist "%BACKUP_DIR%" rd /s /q "%BACKUP_DIR%"

echo [BlindRSS Update] Backing up current install...
move /Y "%INSTALL_DIR%" "%BACKUP_DIR%" >nul
if errorlevel 1 goto :rollback

echo [BlindRSS Update] Applying update...
move /Y "%STAGING_DIR%" "%INSTALL_DIR%" >nul
if errorlevel 1 goto :rollback

echo [BlindRSS Update] Launching app...
start "" "%INSTALL_DIR%\%EXE_NAME%"
exit /b 0

:rollback
echo [BlindRSS Update] Update failed. Restoring backup...
if exist "%BACKUP_DIR%" (
    if not exist "%INSTALL_DIR%" (
        move /Y "%BACKUP_DIR%" "%INSTALL_DIR%" >nul
    )
)
start "" "%INSTALL_DIR%\%EXE_NAME%"
exit /b 1

:usage
echo Usage: update_helper.bat ^<pid^> ^<install_dir^> ^<staging_dir^> ^<exe_name^>
exit /b 1
