@echo off
setlocal EnableExtensions
cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Requesting Administrator so Setup can install Ollama and open the LAN firewall...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo.
echo  EduRAG first-time setup
echo  -----------------------
echo  This does NOT ask anyone to install Python by hand.
echo  It will: find or create a local runtime, install Ollama, pull the
echo  chat model, add English OCR, seed Admin/Teacher/Student logins,
echo  then start the LAN server.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
if errorlevel 1 (
  echo Setup failed.
  pause
  exit /b 1
)

echo.
echo Setup finished. Starting EduRAG...
call "%~dp0Start-EduRAG.bat"
