@echo off
title JOI — Justified Operative Interface
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo.
echo  J O I  —  Justified Operative Interface
echo  Launching desktop app...
echo.

python joi_app.py