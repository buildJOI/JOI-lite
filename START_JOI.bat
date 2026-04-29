@echo off
title JOI — Justified Operative Interface
cd /d "%~dp0"

:: Activate venv if present
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo.
echo  J O I  —  Justified Operative Interface
echo  Starting system tray...
echo  Ctrl+Shift+J to open / hide the interface
echo  Right-click the tray icon to quit
echo.

python tray_app.py@echo off
title JOI — Justified Operative Interface
cd /d "%~dp0"

:: Activate venv if present
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo.
echo  J O I  —  Justified Operative Interface
echo  Starting system tray...
echo  Ctrl+Shift+J to open / hide the interface
echo  Right-click the tray icon to quit
echo.

python tray_app.py