@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONPATH=%cd%"
title Stop EduRAG

set "PY="
if exist "%cd%\runtime\venv\Scripts\python.exe" set "PY=%cd%\runtime\venv\Scripts\python.exe"
if not defined PY if exist "%cd%\.venv\Scripts\python.exe" set "PY=%cd%\.venv\Scripts\python.exe"
if not defined PY (
  echo Runtime missing.
  pause
  exit /b 1
)

echo Stopping EduRAG (port 4747)...
echo If nothing else is using Ollama, the chat model is unloaded and Ollama may exit too.
echo If SmilAI or another app is still on 11434, Ollama is left running.
echo.
"%PY%" -m app stop
echo.
echo Done. You can close this window.
pause
