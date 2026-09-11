@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONPATH=%cd%"
title Private room

set "PY="
if exist "%cd%\runtime\venv\Scripts\python.exe" set "PY=%cd%\runtime\venv\Scripts\python.exe"
if not defined PY if exist "%cd%\.venv\Scripts\python.exe" set "PY=%cd%\.venv\Scripts\python.exe"
if not defined PY (
  echo Runtime missing. Run Setup-EduRAG.bat once on this PC.
  pause
  exit /b 1
)

echo.
echo  Private room  (not the school app)
echo  http://127.0.0.1:4747/companion
echo.
echo  Unlock key:  home-4747
echo  Also saved in data\companion.key after the first start.
echo.

"%PY%" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:4747/v1/health', timeout=2)" >nul 2>&1
if not errorlevel 1 (
  start "" "http://127.0.0.1:4747/companion"
  echo Server already running. Opened the private room.
  pause
  exit /b 0
)

call "%~dp0Start-EduRAG.bat" companion
