# Architecture

EduRAG is an on-prem appliance: one server process, one school UI, many thin browser clients.

## Pipeline

```
files on the server PC
        │
        ▼
   ingest (PDF, DOCX, PPTX, HTML, MD, TXT, images)
        │  OCR only when a page has no usable text
        ▼
   structure-aware chunks  (one teachable unit each)
        │
        ▼
   embed (MiniLM ONNX) + store in SQLite
        │
        ▼
   hybrid retrieve  (vector + BM25 + exact terms)
        │
        ▼
   rerank  (lexical now; cross-encoder if you add a model)
        │
        ▼
   generate with Ollama  + citation cleanup
```

Libraries (called “courses” in the database) are isolated indexes. Chat without a library is ordinary conversation; how-to / API questions can still pull from a selected library depending on the persona.

## One core, many personas

`app/personas.py` holds built-in characters. `app/characters.py` stores user overlays in `data/characters.json`. The same `generate_answer` path runs for all of them.

| Id | Name | Typical use |
|----|------|-------------|
| `chat` | Chat | Casual talk; docs only when asked |
| `unity_dev` | Unity Dev | Game-dev coworker, tighter code |
| `tutor` | Tutor | Grounded explanations + cites |
| `docs` | Docs | Manual-first answers |
| `study_companion` | Study Companion | Confused-notes help |
| `teacher` | Teacher | Quizzes, weak-topic drill |
| `exam_coach` | Exam Coach | Practice questions |
| `guide` | Guide | Listen + escalate; not a counselor |

School characters are **16+**. K-12 on a library forces conservative tone even if the persona would otherwise be looser.

## Roles

| Role | Can |
|------|-----|
| Student | Chat, quizzes, own threads |
| Teacher | Ingest libraries, staff flags |
| Admin | Same as teacher + audit log, user list |

Distress detection in `app/safety.py` runs on every message, any persona. Staff see flags; the model does not give crisis advice.

## Data on disk

| Path | Contents |
|------|----------|
| `data/edurag.db` | Users, libraries, chunks, chats |
| `data/uploads/` | Files dropped through the UI |
| `data/characters.json` | School character overrides |
| `config.yaml` | Port, Ollama model, embedding/OCR paths |
| `models/embedding/` | MiniLM |
| `models/ocr/` | EasyOCR weights |

`data/` is gitignored. JWT secret lives in `config.yaml` — do not commit or paste it.

## HTTP

- UI: `GET /`
- API: `/v1/...` (health, auth, chat SSE, courses, ingest, audit)
- OpenAPI: `/v1/docs`

The process binds `0.0.0.0` so other LAN devices can connect. Clients never read the server’s disks; folder ingest runs on the server PC only.
