# Chat models (Ollama)

EduRAG talks to **Ollama only** for chat (`http://localhost:11434`).  
Embeddings, RAG, memory, personas, and UI stay the same — only the Ollama model tag changes.

| Id / tag | Role |
|----------|------|
| `qwen2.5:7b-instruct` | Default. Fits RTX 3060 12GB. |
| `gpt-oss:20b` | **Optional / not recommended on RTX 3060 12GB.** Ideal ~16GB+ VRAM. On this PC it spills heavily into RAM and feels slow. Prefer Qwen 7B for daily use. |

## Switch in the UI

**Companion:** Settings → Debug → **Chat model** → select → **Use selected**.  
**School:** header **Model** dropdown (next to Debug).

**Download:** UI **Download via Ollama** / **Pull**, or CLI below. Never download weights outside Ollama for these backends.

## Switch from the terminal

```bat
cd /d D:\AI_Tools\EduRAG
set PYTHONPATH=%cd%

rem List catalog + installed
.venv\Scripts\python.exe -m app list-models

rem Download GPT-OSS (one-time, large)
.venv\Scripts\python.exe -m app pull-model gpt-oss:20b

rem Activate it (unloads previous model from VRAM)
.venv\Scripts\python.exe -m app set-model gpt-oss:20b

rem Back to Qwen
.venv\Scripts\python.exe -m app set-model qwen2.5:7b-instruct
```

Or edit `config.yaml`:

```yaml
llm:
  model: gpt-oss:20b   # or qwen2.5:7b-instruct
  base_url: http://localhost:11434
  models:   # optional overrides; defaults live in app/llm.py
    - id: gpt-oss:20b
      ollama_name: gpt-oss:20b
      num_ctx: 2048
      num_predict: 1536
      num_thread: 6
      num_batch: 128
```

`base_url` and per-model knobs are configurable — no hard-coded install paths for chat weights (Ollama owns `%USERPROFILE%\.ollama` or `OLLAMA_MODELS`).

## RTX 3060 12GB notes

- Keep **one** loaded model (`OLLAMA_MAX_LOADED_MODELS=1` in Start-EduRAG.bat).
- Switching models unloads the previous one.
- GPT-OSS 20B: lower `num_ctx` / `keep_alive` so KV + weights fit with RAM spill.
- Do not run SDXL companion image gen while a 20B chat model is resident.

## API

- `GET /v1/llm/models` — catalog, active, installed, pull status  
- `POST /v1/llm/model` `{"model":"gpt-oss:20b"}` — set active  
- `POST /v1/llm/pull` `{"model":"gpt-oss:20b"}` — background `ollama pull`

## Files touched

| File | Change |
|------|--------|
| `app/llm.py` | Catalog, settings per model, set/pull/unload |
| `app/server.py` | `/v1/llm/*` routes |
| `app/__main__.py` | `list-models`, `set-model`, `pull-model` |
| `app/discovery.py` | Preserve `llm.models` when rewriting config |
| `config.yaml` / `prod-deliverables/config.example.yaml` | Catalog entries |
| `web/companion.html` + `companion.js` | Settings model picker |
| `web/index.html` + `app.js` | School header model picker |
| `tests/test_llm_catalog.py` | Catalog / switch tests |
| `docs/LLM_MODELS.md` | This guide |
