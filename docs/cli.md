# CLI

From the repo root, with the project venv:

```
set PYTHONPATH=%cd%
.venv\Scripts\python.exe -m app <command>
```

Use `runtime\venv\Scripts\python.exe` instead if Setup created that runtime.

## Appliance

| Command | What it does |
|---------|----------------|
| `setup` | Demo users, English OCR, pull the Ollama model |
| `serve [--host] [--port]` | LAN UI + API (default `0.0.0.0:4747`) |
| `package-check` | Files, port, models — copy-to-another-PC checklist |
| `system-info` | GPU / RAM / CUDA report |
| `model-discovery` | Scan `models/`, write `config.yaml` |

Day-to-day you should use **`Start-EduRAG.bat`**, which starts Ollama then `serve`.

## Indexing and search (no UI)

| Command | What it does |
|---------|----------------|
| `ingest <path> [--list] [--no-ocr]` | Parse files; print structure. Does not index. |
| `chunk <path>` | Parse then print teachable-unit chunks |
| `index <path> --course NAME` | Parse, chunk, embed, store |
| `search "query" --course NAME [--top-k 5]` | Hybrid retrieval, no LLM |
| `chat "question" --course NAME [--persona tutor] [--debug]` | Grounded answer (needs Ollama) |
| `load-test [--clients 32]` | Concurrent hits against a running server (health by default) |

Examples:

```
python -m app ingest D:\Docs\unity-manual --list
python -m app index D:\Docs\unity-manual --course "unity 6 documentation" --max-files 4000
python -m app search "Transform.Translate" --course "unity 6 documentation"
python -m app chat "How do I move a transform?" --course "unity 6 documentation" --persona tutor --debug
```

## Tests

```
set PYTHONPATH=%cd%
.venv\Scripts\python.exe -m pytest tests -q
```
