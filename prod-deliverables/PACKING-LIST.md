# What to copy for a client

From the build PC, copy this tree (or run `python -m app pack-client --zip`):

```
EduRAG/
  app/
  web/
  models/          (embedding + OCR weights)
  scripts/
  tests/           (optional)
  Setup-EduRAG.bat
  Start-EduRAG.bat
  Stop-EduRAG.bat
  requirements.txt
  README.md
  docs/            (architecture + CLI; skip private-room.md for school clients)
  prod-deliverables/   (this folder)
```

## Leave out

- `.venv/` / `runtime/` — Setup creates these on the client PC
- `data/` — local chats, uploads, companion key
- `config.yaml` — contains a machine JWT secret; client runs `python -m app model-discovery` or Setup
- `.git/`
- `prod-deliverables/*.zip` (do not nest zips)

## After copy

On the client PC: Setup-EduRAG.bat once, then Start-EduRAG.bat.  
Confirm `python -m app package-check` is all OK.
