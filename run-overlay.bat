@echo off
rem Controller Response Overlay - starts the read-only XInput reader.
rem   Double-click, or from a terminal:  run-overlay.bat [--demo] [--port N] [--no-hotkey]
rem   Then open http://127.0.0.1:47820/ in a browser or as an OBS Browser Source.
rem   Close this window (or press Ctrl+C) to stop; the overlay then turns gray.
setlocal
cd /d "%~dp0"
title Controller Response Overlay

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH. Install Python 3.12 or newer and try again.
    pause
    exit /b 1
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
if errorlevel 1 (
    echo Python 3.12 or newer is required. Found:
    python --version
    pause
    exit /b 1
)

python -m cro %*
if errorlevel 1 pause
