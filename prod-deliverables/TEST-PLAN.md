# Client test plan

Do these on the server PC and one phone/laptop on the same Wi-Fi.

1. Start-EduRAG.bat opens http://127.0.0.1:4747. Sign in as Teacher.
2. New library → upload a small PDF or index a folder. Wait until the job finishes.
3. Ask Tutor a question that is in the file. You should see a cited answer, not an invention.
4. Sign out. Sign in as Student. Same library is visible. Chat works.
5. From another device, open `http://<server-lan-ip>:4747` (printed in the Start window). Sign in. Chat works.
6. Mark the library K-12. Ask something off-tone; it should stay school-conservative.
7. Stop-EduRAG.bat. Port 4747 should be free. GPU memory for the chat model should drop (Task Manager → GPU).
8. Start again. Demo logins still work.

## Fail if

- The UI is reachable on the internet (it must be LAN/Private only)
- Answers cite files that were never ingested
- Start uses port 8080 or 3636
- Closing the window leaves the 7B model loaded in VRAM for hours (Stop.bat should unload it)
