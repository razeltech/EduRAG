@echo off
title Share EduRAG Companion
echo.
echo =======================================================
echo          Sharing EduRAG Companion over the Internet
echo =======================================================
echo.
echo Make sure EduRAG Companion is already running first!
echo.
echo Generating a public link using LocalTunnel...
echo Give the generated URL to your friend.
echo The unlock key they will need is: home-4747
echo.
echo (Press Ctrl+C to stop sharing when done)
echo.
call npx -y localtunnel --port 4747
pause
