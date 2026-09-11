# Private room

This is **not** part of the school app. EduRAG’s Characters editor is 16+ only. The private room is a separate page, unlocked with a key, and is not linked from the school UI.

## Start

1. Double-click **`Start-Companion.bat`** (starts Ollama + the same server if they are not already up).
2. Browser: **http://127.0.0.1:4747/companion**
3. Enter the key and confirm 18+.

Default key: `home-4747`  
After the first start it is also in `data\companion.key`. Change the file and delete `data\companion.json`’s `unlock_hash` only if you intend to rotate the key (then restart once so a new hash is written).

## What it is

- Own HTML/CSS/JS (`web/companion.html`), own API under `/v1/companion/...`
- Profile (name, partner role, prompt) in `data/companion.json`
- After unlock, first screen is **You / Them**: your name, gender, pronouns, and their role
- **Us** drawer: full character card, dynamics sliders, reply shape, generation presets, debug prompt
- Relationship numbers and memories persist in `data/companion_state.json` and `data/companion_memory.json`. Full chat logs still are not stored. **New** starts a new scene; **Forget** in Debug clears memory.
- Distress/crisis in this room is self-harm only (no school staff flag). Under-18 and real-world harm still stop.
- Click the big name (default **Maya**) to rename
- **Chats are not stored.** Refresh, lock, or New chat wipes them. Use **Export .md** if you want a file
- Distress flags still fire (safety is not turned off)

## Model

Same local Ollama model as EduRAG (Qwen 2.5 7B instruct on this box). You do **not** need a second model for gender — that comes from the You card injected into the prompt. A dedicated RP model can wait; 12GB VRAM should keep only one LLM loaded.

Keep this URL and the key off student-facing screens and off `Start-EduRAG.bat`’s school banner.
