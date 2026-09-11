@echo off
cd /d "%~dp0.."
set "PYTHONPATH=%cd%"
if not exist ".venv\Scripts\python.exe" (
  echo Runtime missing. Run Setup-EduRAG.bat first.
  pause
  exit /b 1
)
set "COMPANION_E2E=1"
".venv\Scripts\python.exe" -m pytest tests/e2e -m e2e -q --tb=short %*
