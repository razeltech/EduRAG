# EduRAG

Local, offline learning assistant for one school or studio LAN. One PC runs the engine; phones and laptops on the same Wi-Fi open a browser. Nothing is sent to the cloud.

One retrieval core, one web shell. Personas (Tutor, Teacher, Unity Dev, …) are prompts and settings, not separate apps.

**Port:** `4747` (do not use 8080 or 3636).

## Quick start (this PC)

1. First time only: right-click **`Setup-EduRAG.bat`** → Run as administrator.  
   It installs a local Python runtime if needed, Ollama, the chat model, English OCR, demo logins, then starts the server.
2. Every later day: double-click **`Start-EduRAG.bat`**.  
   It starts Ollama, waits until it answers, then starts the HTML/API server and opens the UI. Leave that window open. Open **http://127.0.0.1:4747** on this PC, or the LAN URL printed in the window on other devices.
3. Stop: double-click **`Stop-EduRAG.bat`**. That unloads the chat model from VRAM and frees port 4747.

Hand a client the files in **`prod-deliverables/`** (or `python -m app pack-client --zip`).

Demo seats (passwords reset on each server start):

| Seat    | Email                 | Password     |
|---------|-----------------------|--------------|
| Admin   | `admin@edurag.local`  | `admin123`   |
| Teacher | `teacher@edurag.local`| `teacher123` |
| Student | `student@edurag.local`| `student123` |

Students chat and take quizzes. Teachers ingest libraries. Admins can audit.

## What you do in the UI

- Pick a **character** (Chat, Unity Dev, Tutor, Docs, Study Companion, Teacher, Exam Coach, Guide) and optionally a **library** of indexed files.
- Staff create a library, then **Upload** a file or **Folder**-index a tree on the server PC (Unity manuals, course PDFs, notes).
- Mark a library **K-12** for school-conservative tone. Distress phrases raise a staff flag from every persona.
- Characters stay **16+**. Custom personas you save are school-facing only.

## Layout

```
app/            API, RAG, ingest, auth
web/            School UI (one shell)
data/           SQLite, uploads, local JSON  (not committed)
models/         Embedding + OCR weights
Start-EduRAG.bat
Setup-EduRAG.bat
config.yaml     Models, port, paths (written by model-discovery)
```

Stack: FastAPI + SQLite, MiniLM embeddings, hybrid search (vector + BM25 + lexical rerank), Ollama `qwen2.5:7b-instruct`. Cross-encoder rerank and TTS are optional / off until you add those models.

## Docs

| File | What it is |
|------|------------|
| [docs/architecture.md](docs/architecture.md) | How ingest, retrieve, personas, and roles fit together |
| [docs/cli.md](docs/cli.md) | `python -m app` commands |
| [docs/private-room.md](docs/private-room.md) | Separate keyed UI, not part of the school app |
| [prod-deliverables/](prod-deliverables/) | Client handoff (README, test plan, firewall, packing list) |
| [plan.md](plan.md) | Original design spec (historical) |

## Copying to another PC

Copy this folder (including `models/` and the venv or `runtime/`). On the new machine run `Setup-EduRAG.bat` if Python/Ollama are missing, then:

```
python -m app package-check
python -m app model-discovery
```

Bind stays `0.0.0.0:4747`. Open Windows Firewall for TCP 4747 on the Private/LAN profile only.

## Tests

```
set PYTHONPATH=%cd%
.venv\Scripts\python.exe -m pytest tests -q
```
