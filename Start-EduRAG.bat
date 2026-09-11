@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONPATH=%cd%"
title EduRAG server

rem Cap Ollama when we start it: one model, one slot, idle unload.
set "OLLAMA_MAX_LOADED_MODELS=1"
set "OLLAMA_NUM_PARALLEL=1"
set "OLLAMA_KEEP_ALIVE=5m"
set "OLLAMA_FLASH_ATTENTION=1"

set "PY="
if exist "%cd%\runtime\venv\Scripts\python.exe" set "PY=%cd%\runtime\venv\Scripts\python.exe"
if not defined PY if exist "%cd%\.venv\Scripts\python.exe" set "PY=%cd%\.venv\Scripts\python.exe"
if not defined PY (
  echo Runtime missing. Run Setup-EduRAG.bat once on this PC.
  pause
  exit /b 1
)

rem Double-click PATH is often missing Ollama. Prefer known install folders.
set "OLLAMA_EXE="
where ollama >nul 2>&1 && for /f "delims=" %%I in ('where ollama 2^>nul') do if not defined OLLAMA_EXE set "OLLAMA_EXE=%%I"
if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA_EXE if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"
if defined OLLAMA_EXE (
  for %%I in ("%OLLAMA_EXE%") do set "PATH=%%~dpI;%PATH%"
) else (
  echo Ollama.exe not found on PATH or in Local\Programs\Ollama.
  echo Install from https://ollama.com/download then open a NEW Start menu / terminal,
  echo or start the Ollama app from the tray and run this bat again.
  pause
  exit /b 1
)

echo Checking Ollama on port 11434...
"%PY%" -m app ensure-ollama
if errorlevel 1 (
  echo.
  echo Could not reach or start Ollama. If the app is in the system tray, wait a few seconds and retry.
  pause
  exit /b 1
)

set "OPEN_URL=http://127.0.0.1:4747"
if /I "%~1"=="companion" set "OPEN_URL=http://127.0.0.1:4747/companion"
start "" cmd /c "timeout /t 2 /nobreak >nul & start "" %OPEN_URL%"

echo.
echo  EduRAG is starting. Leave this window open.
echo  This PC:   http://127.0.0.1:4747
echo  Chat model: Qwen 2.5 7B via Ollama (see config.yaml). Stay on Qwen on this 12GB GPU.
echo  Stop with Stop-EduRAG.bat — frees 4747; stops Ollama only if nothing else is using it.
echo.

"%PY%" -m app serve --host 0.0.0.0 --port 4747
echo.
echo Server window ended. Cleaning up...
"%PY%" -m app stop
echo.
pause
