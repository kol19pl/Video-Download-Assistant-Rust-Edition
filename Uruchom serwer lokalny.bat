@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Enable ANSI colors (works without chcp)
for /F "tokens=1,2 delims=#" %%a in ('"prompt #$H#$E# & echo on & for %%b in (1) do rem"') do set "ESC=%%b"

mode con: cols=88 lines=42
title VDA SERVER v2.0
color 0A

REM ==================== BOOT ====================
cls
echo.
echo.
echo.
echo.
echo               %ESC%[96m================================================%ESC%[0m
echo               %ESC%[96m                                                %ESC%[0m
echo               %ESC%[96m       %ESC%[95mINITIALIZING VDA SERVER...%ESC%[96m        %ESC%[0m
echo               %ESC%[96m                                                %ESC%[0m
echo               %ESC%[96m================================================%ESC%[0m
echo.
echo.
echo                      %ESC%[92m[%ESC%[93m##################%ESC%[92m]%ESC%[0m
echo.
timeout /t 2 /nobreak >nul

REM ==================== MAIN ====================
cls
echo.
echo  %ESC%[90m  -----------------------------------------------------------------------------%ESC%[0m
echo  %ESC%[90m  ^> Timestamp: %date% %time%%ESC%[0m
echo  %ESC%[90m  ^> Location: %~dp0%ESC%[0m
echo  %ESC%[90m  -----------------------------------------------------------------------------%ESC%[0m
echo.

REM ==================== DIAGNOSTICS ====================
echo  %ESC%[93m  ============================================================================%ESC%[0m
echo  %ESC%[93m    SYSTEM DIAGNOSTICS%ESC%[0m
echo  %ESC%[93m  ============================================================================%ESC%[0m
echo.

echo   %ESC%[96m  ^>^>%ESC%[0m %ESC%[97mScanning Python runtime...%ESC%[0m
timeout /t 1 /nobreak >nul
python --version >nul 2>&1
if !errorlevel! neq 0 (
    echo   %ESC%[91m    [X] CRITICAL: Python not detected!%ESC%[0m
    echo.
    echo   %ESC%[91m    ^> System requirements not met%ESC%[0m
    echo   %ESC%[96m    ^> Install: https://python.org%ESC%[0m
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo   %ESC%[92m    [OK] Python !PYTHON_VER! online%ESC%[0m
echo.

REM ==================== DEPENDENCIES ====================
echo  %ESC%[93m  ============================================================================%ESC%[0m
echo  %ESC%[93m    DEPENDENCY MATRIX%ESC%[0m
echo  %ESC%[93m  ============================================================================%ESC%[0m
echo.

echo   %ESC%[96m  ^>^>%ESC%[0m %ESC%[97mVerifying yt-dlp module...%ESC%[0m
timeout /t 1 /nobreak >nul
python -c "import yt_dlp" 2>nul
if !errorlevel! neq 0 (
    echo   %ESC%[93m    [!] Module not found%ESC%[0m
    echo   %ESC%[96m  ^>^>%ESC%[0m %ESC%[97mInstalling yt-dlp...%ESC%[0m
    python -m pip install yt-dlp --upgrade --quiet
    if !errorlevel! neq 0 (
        echo   %ESC%[91m    [X] Installation failed%ESC%[0m
        pause
        exit /b 1
    )
    echo   %ESC%[92m    [OK] Installation complete%ESC%[0m
) else (
    echo   %ESC%[92m    [OK] Module loaded%ESC%[0m
)

echo   %ESC%[96m  ^>^>%ESC%[0m %ESC%[97mChecking updates...%ESC%[0m
python -m pip install yt-dlp --upgrade --quiet >nul 2>&1
for /f "delims=" %%i in ('yt-dlp --version 2^>^&1') do set YTDLP_VER=%%i
echo   %ESC%[92m    [OK] Version !YTDLP_VER!%ESC%[0m

echo   %ESC%[96m  ^>^>%ESC%[0m %ESC%[97mVerifying tkinter module...%ESC%[0m
timeout /t 1 /nobreak >nul
python -c "import tkinter" 2>nul
if !errorlevel! neq 0 (
    echo   %ESC%[93m    [!] Module not found%ESC%[0m
    
    REM Sprawdź system operacyjny
    python -c "import platform; exit(0 if platform.system() == 'Linux' else 1)" 2>nul
    if !errorlevel! equ 0 (
        echo   %ESC%[96m  ^>^>%ESC%[0m %ESC%[97mDetected Linux - attempting auto-install...%ESC%[0m
        echo   %ESC%[90m    ^> Running: apt-get install python3-tk%ESC%[0m
        sudo apt-get install -y python3-tk >nul 2>&1
        if !errorlevel! neq 0 (
            echo   %ESC%[91m    [X] Auto-install failed%ESC%[0m
            echo.
            echo   %ESC%[96m    ^> Manual install: sudo apt-get install python3-tk%ESC%[0m
            echo.
            pause
            exit /b 1
        )
        echo   %ESC%[92m    [OK] Installation complete%ESC%[0m
        
        REM Sprawdź ponownie
        python -c "import tkinter" 2>nul
        if !errorlevel! neq 0 (
            echo   %ESC%[91m    [X] Installation failed%ESC%[0m
            pause
            exit /b 1
        )
    ) else (
        echo   %ESC%[91m    [X] Windows detected - cannot auto-install%ESC%[0m
        echo.
        echo   %ESC%[96m    ^> Reinstall Python with "tcl/tk and IDLE" option%ESC%[0m
        echo   %ESC%[96m    ^> Download: https://python.org%ESC%[0m
        echo.
        pause
        exit /b 1
    )
) else (
    echo   %ESC%[92m    [OK] Module loaded%ESC%[0m
)

echo.

REM ==================== FFMPEG ====================
echo  %ESC%[93m  ============================================================================%ESC%[0m
echo  %ESC%[93m    CODEC LIBRARY%ESC%[0m
echo  %ESC%[93m  ============================================================================%ESC%[0m
echo.

echo   %ESC%[96m  ^>^>%ESC%[0m %ESC%[97mScanning FFmpeg...%ESC%[0m
timeout /t 1 /nobreak >nul
ffmpeg -version >nul 2>&1
if !errorlevel! equ 0 (
    echo   %ESC%[92m    [OK] FFmpeg in system PATH%ESC%[0m
    goto :ffmpeg_ok
)

if exist "%~dp0ffmpeg\bin\ffmpeg.exe" (
    echo   %ESC%[92m    [OK] Local installation%ESC%[0m
    set "PATH=%~dp0ffmpeg\bin;%PATH%"
    goto :ffmpeg_ok
)

echo   %ESC%[93m    [!] Not found%ESC%[0m
echo.
echo   %ESC%[96m  ^>^>%ESC%[0m %ESC%[97mDownloading FFmpeg...%ESC%[0m
echo   %ESC%[90m    ^> Size: ~70MB%ESC%[0m
echo   %ESC%[90m    ^> Time: 1-2 min%ESC%[0m
echo.

(
echo try {
echo   $ProgressPreference = 'SilentlyContinue'
echo   Write-Host "    ^> Connecting..." -ForegroundColor Cyan
echo   Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile "%~dp0ffmpeg.zip" -UseBasicParsing
echo   Write-Host "    ^> Downloading..." -ForegroundColor Cyan
echo   Write-Host "    ^> Extracting..." -ForegroundColor Cyan
echo   Expand-Archive -Path "%~dp0ffmpeg.zip" -DestinationPath "%~dp0" -Force
echo   Remove-Item "%~dp0ffmpeg.zip" -Force
echo   $folder = Get-ChildItem "%~dp0" -Filter "ffmpeg-*" -Directory ^| Select-Object -First 1
echo   if ($folder^) { Rename-Item -Path $folder.FullName -NewName "ffmpeg" -Force }
echo   Write-Host "    ^> Complete!" -ForegroundColor Green
echo   exit 0
echo } catch {
echo   Write-Host "    ^> Error!" -ForegroundColor Red
echo   exit 1
echo }
) > "%temp%\ffmpeg_dl.ps1"

powershell -ExecutionPolicy Bypass -File "%temp%\ffmpeg_dl.ps1"
set DL_ERR=!errorlevel!
del "%temp%\ffmpeg_dl.ps1" >nul 2>&1

if !DL_ERR! neq 0 (
    echo   %ESC%[91m    [X] Download failed%ESC%[0m
    echo.
    echo   %ESC%[96m    ^> Manual: https://www.gyan.dev/ffmpeg/builds/%ESC%[0m
    echo.
    pause
    goto :ffmpeg_ok
)

if exist "%~dp0ffmpeg\bin\ffmpeg.exe" (
    echo   %ESC%[92m    [OK] Installation successful%ESC%[0m
    set "PATH=%~dp0ffmpeg\bin;%PATH%"
) else (
    echo   %ESC%[91m    [X] Incomplete%ESC%[0m
)

:ffmpeg_ok
echo.

REM ==================== FILES ====================
echo  %ESC%[93m  ============================================================================%ESC%[0m
echo  %ESC%[93m    FILE SYSTEM%ESC%[0m
echo  %ESC%[93m  ============================================================================%ESC%[0m
echo.

set "files_ok=1"

echo   %ESC%[96m  ^>^>%ESC%[0m %ESC%[97mVerifying start_server.py%ESC%[0m
timeout /t 1 /nobreak >nul
if not exist "%~dp0start_server.py" (
    echo   %ESC%[91m    [X] Missing%ESC%[0m
    set "files_ok=0"
) else (
    echo   %ESC%[92m    [OK] Found%ESC%[0m
)

echo   %ESC%[96m  ^>^>%ESC%[0m %ESC%[97mVerifying server.py%ESC%[0m
timeout /t 1 /nobreak >nul
if not exist "%~dp0server.py" (
    echo   %ESC%[91m    [X] Missing%ESC%[0m
    set "files_ok=0"
) else (
    echo   %ESC%[92m    [OK] Found%ESC%[0m
)

if !files_ok! equ 0 (
    echo.
    echo   %ESC%[91m    CRITICAL: Files missing!%ESC%[0m
    echo.
    pause
    exit /b 1
)

echo.

REM ==================== READY ====================
echo.
echo  %ESC%[92m===============================================================================%ESC%[0m
echo  %ESC%[92m                                                                               %ESC%[0m
echo  %ESC%[92m                     [OK] ALL SYSTEMS OPERATIONAL [OK]%ESC%[0m
echo  %ESC%[92m                                                                               %ESC%[0m
echo  %ESC%[96m    ^> Server:%ESC%[0m %ESC%[97mhttp://localhost:8080%ESC%[0m
echo  %ESC%[96m    ^> Interface:%ESC%[0m %ESC%[97mGUI%ESC%[0m
echo  %ESC%[96m    ^> Status:%ESC%[0m %ESC%[97mReady to launch%ESC%[0m
echo  %ESC%[92m                                                                               %ESC%[0m
echo  %ESC%[92m===============================================================================%ESC%[0m
echo.

REM ==================== COUNTDOWN ====================
echo  %ESC%[93m  *** LAUNCH SEQUENCE ***%ESC%[0m
echo.

for /l %%i in (3,-1,1) do (
    echo   %ESC%[92m  ^>^>%ESC%[0m %ESC%[97mInitiating in T-%%i...%ESC%[0m
    timeout /t 1 /nobreak >nul
)

echo.
echo   %ESC%[96m  *** LAUNCHING SERVER ***%ESC%[0m
echo.
echo  %ESC%[90m  -----------------------------------------------------------------------------%ESC%[0m
echo   %ESC%[96m  ^> Opening GUI interface...%ESC%[0m
echo  %ESC%[90m  -----------------------------------------------------------------------------%ESC%[0m
echo.

REM ==================== EXECUTE ====================
python "%~dp0start_server.py"

if !errorlevel! neq 0 (
    echo.
    echo  %ESC%[91m===============================================================================%ESC%[0m
echo  %ESC%[91m                      [X] LAUNCH SEQUENCE FAILED [X]%ESC%[0m
echo  %ESC%[91m===============================================================================%ESC%[0m
    echo.
    pause
    exit /b 1
)

echo.
echo  %ESC%[92m===============================================================================%ESC%[0m
echo  %ESC%[92m                   [OK] SERVER TERMINATED GRACEFULLY [OK]%ESC%[0m
echo  %ESC%[92m===============================================================================%ESC%[0m
echo.
timeout /t 2 /nobreak >nul
exit /b 0