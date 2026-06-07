@echo off
title JOI — Justified Operative Interface
cd /d "%~dp0"

<<<<<<< HEAD
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
=======
echo.
echo  =====================================================
echo   J O I  —  Justified Operative Interface
echo  =====================================================
echo.
echo  Starting backend (FastAPI)...
echo  Starting frontend (React dev server)...
echo.
echo  Web UI will be at: http://localhost:3000/chat
echo  Backend API at:    http://localhost:8000
echo.
echo  Close this window to stop both servers.
echo  =====================================================
echo.
>>>>>>> b2dbefe (initial commit — JOI-lite v2 with React frontend)

:: Activate venv if present
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

<<<<<<< HEAD
echo.
echo  J O I  —  Justified Operative Interface
echo  Starting system tray...
echo  Ctrl+Shift+J to open / hide the interface
echo  Right-click the tray icon to quit
echo.

python tray_app.py
=======
:: Start the FastAPI backend in a new window
start "JOI Backend" cmd /k "cd /d "%~dp0" && py -3.13 -m uvicorn server:app --reload --port 8000"

:: Wait a moment for backend to initialise before opening the browser
timeout /t 4 /nobreak >nul

:: Start the React frontend in a new window
start "JOI Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

:: Wait for frontend to spin up then open the browser
timeout /t 5 /nobreak >nul
start "" "http://localhost:3000/chat"

echo  Both servers are running in separate windows.
echo  Close those windows individually to stop each server.
echo.
pause
>>>>>>> b2dbefe (initial commit — JOI-lite v2 with React frontend)
