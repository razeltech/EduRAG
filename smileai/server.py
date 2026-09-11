"""
SmileAI Unified Educational Server & API
Powered by Razel Tech | FastAPI + Uvicorn

Mounts:
- Voice Engine (Aarti warm voice default + regional voices)
- Institutional Database & Roster Manager (CSV import, PIN authentication, gradebook)
- Snap & Solve Exam Solver (OCR + SymPy exact math + pedagogical explanations)
- AI Builder Lab (Visual tokenizer, 2D vector cosine map, CBSE/NEP rubric, bot export)
- Pure HTML5/CSS3/JS Web Interface (Served from smileai/web)
"""

import os
import sys
import json
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from smileai.voice_engine import (
    synthesize_speech_async,
    get_voice_catalog,
    DEFAULT_VOICE_ID,
)
from smileai.db import (
    init_db,
    create_institution,
    create_stream,
    import_roster_csv,
    authenticate_student,
    save_assessment,
    submit_assessment,
    export_gradebook_csv,
    get_db_connection,
)
from smileai.solver import (
    extract_text_from_image_bytes,
    generate_pedagogical_solution,
    snap_and_solve_file,
)
from smileai.builder import (
    analyze_tokens,
    compute_concept_embeddings,
    evaluate_student_bot,
    export_standalone_bot,
)
from smileai.vocab import (
    generate_vocab_challenge,
    evaluate_sentence_usage,
)

app = FastAPI(
    title="SmileAI Institutional Platform",
    description="Offline-Ready Educational Virtual Teacher & AI Builder Lab",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static directory for pure HTML/CSS/JS frontend
WEB_DIR = Path(__file__).resolve().parent / "web"
WEB_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def startup_event():
    """Ensure database schema is initialized on boot."""
    init_db()


# ==============================================================================
# 1. Voice Engine Endpoints
# ==============================================================================

@app.get("/api/smileai/voice/catalog")
def api_voice_catalog():
    """Returns available educational voices (Aarti default, Shruti, Swara, Prabhat)."""
    return {"catalog": get_voice_catalog(), "default_voice": DEFAULT_VOICE_ID}


@app.get("/api/smileai/voice/speak")
async def api_voice_speak(
    text: str = Query(..., description="Text for Smiley to speak"),
    voice: Optional[str] = Query(DEFAULT_VOICE_ID, description="Voice ID"),
    rate: Optional[str] = Query(None, description="Speech rate override, e.g. -15%"),
    pitch: Optional[str] = Query(None, description="Speech pitch override, e.g. +15Hz"),
):
    """Streams synthesized MP3 audio with Aarti's warm teacher voice."""
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text parameter cannot be empty.")

    audio_bytes = await synthesize_speech_async(text, voice_id=voice, rate=rate, pitch=pitch)
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="Voice synthesis failed.")

    return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")


# ==============================================================================
# 2. Institutional Roster & Authentication Endpoints
# ==============================================================================

@app.post("/api/smileai/auth/student")
def api_student_login(
    institution_id: str = Form(...),
    roll_no: str = Form(...),
    pin: str = Form(...),
):
    """Authenticates student via roll number and 4-digit PIN."""
    student = authenticate_student(institution_id, roll_no, pin)
    if not student:
        raise HTTPException(status_code=401, detail="Invalid Roll Number or 4-digit PIN.")
    return {"status": "success", "student": student}


@app.post("/api/smileai/roster/import")
async def api_roster_import(
    institution_id: str = Form(...),
    file: UploadFile = File(...),
):
    """Bulk imports student roster from CSV file and auto-provisions PIN logins."""
    content = (await file.read()).decode("utf-8-sig", errors="ignore")
    result = import_roster_csv(content, institution_id)
    return {"status": "success", "result": result}


@app.get("/api/smileai/gradebook/export")
def api_gradebook_export(institution_id: str = Query(...)):
    """Exports student assessment scores formatted as a school ERP CSV."""
    csv_data = export_gradebook_csv(institution_id)
    return StreamingResponse(
        io.StringIO(csv_data),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=gradebook_export.csv"},
    )


# ==============================================================================
# 3. Snap & Solve Exam Paper Endpoints
# ==============================================================================

@app.post("/api/smileai/solve/snap")
async def api_solve_snap(
    file: UploadFile = File(...),
    stream: str = Form("MPC"),
    student_id: Optional[str] = Form(None),
):
    """Upload an exam paper photo (PNG/JPG/WEBP/PDF) and get step-by-step solution."""
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    ocr_res = extract_text_from_image_bytes(file_bytes, filename=file.filename)
    text = ocr_res.get("extracted_text", "")
    if not text:
        return {
            "status": "warning",
            "message": "Could not extract legible text. Please upload a clearer photo or enter question manually.",
            "ocr_result": ocr_res,
            "solution": None,
        }

    questions = ocr_res.get("questions_detected", [text])
    primary_q = questions[0]
    solution = generate_pedagogical_solution(primary_q, stream=stream)

    return {
        "status": "success",
        "filename": file.filename,
        "ocr_result": ocr_res,
        "primary_question": primary_q,
        "all_questions": questions,
        "solution": solution,
    }


# ==============================================================================
# 4. AI Builder Lab Endpoints
# ==============================================================================

@app.post("/api/smileai/builder/tokens")
def api_builder_tokens(payload: Dict[str, Any]):
    """Analyzes text into visual tokens, token IDs, and compression metrics."""
    text = payload.get("text", "")
    return analyze_tokens(text)


@app.post("/api/smileai/builder/embeddings")
def api_builder_embeddings(payload: Dict[str, Any]):
    """Projects concepts into 2D vector space with live cosine similarity calculations."""
    concepts = payload.get("concepts", [])
    return compute_concept_embeddings(concepts)


@app.post("/api/smileai/builder/evaluate")
def api_builder_evaluate(payload: Dict[str, Any]):
    """Evaluates student's bot against CBSE / NEP 2020 100-point competency rubric."""
    bot_name = payload.get("bot_name", "My AI")
    notes_text = payload.get("notes_text", "")
    persona_prompt = payload.get("persona_prompt", "")
    return evaluate_student_bot(bot_name, notes_text, persona_prompt)


@app.post("/api/smileai/builder/export")
def api_builder_export(payload: Dict[str, Any]):
    """Generates and downloads a standalone, zero-dependency offline mini-bot script."""
    bot_name = payload.get("bot_name", "Student_Mini_AI")
    author_name = payload.get("author_name", "Student")
    notes_text = payload.get("notes_text", "")
    persona_prompt = payload.get("persona_prompt", "")

    out_file = ROOT_DIR / "smileai" / "exports" / f"{re.sub(r'[^a-zA-Z0-9]', '_', bot_name).lower()}_bot.py"
    out_path = export_standalone_bot(bot_name, author_name, notes_text, persona_prompt, str(out_file))

    return FileResponse(
        path=out_path,
        media_type="text/x-python",
        filename=Path(out_path).name,
    )


# ==============================================================================
# 5. Vocabulary & Terminology Practice (100% Offline & Text-Based)
# ==============================================================================

@app.get("/api/smileai/vocab/challenge")
def api_vocab_challenge(stream: str = Query("K10")):
    """Generates a multiple-choice technical terminology challenge for the given stream."""
    return generate_vocab_challenge(stream=stream)


@app.post("/api/smileai/vocab/evaluate")
def api_vocab_evaluate(payload: Dict[str, Any]):
    """Evaluates student's usage of a technical word in a sentence, returning score /10 and constructive feedback."""
    word = payload.get("word", "")
    sentence = payload.get("sentence", "")
    stream = payload.get("stream", "K10")
    return evaluate_sentence_usage(word=word, student_sentence=sentence, stream=stream)


# ==============================================================================
# 6. Interactive Chat with Smiley
# ==============================================================================

@app.post("/api/smileai/chat")
def api_chat(payload: Dict[str, Any]):
    """
    Direct student chat endpoint with Smiley.
    Returns structured pedagogical reply with textbook citations.
    """
    message = payload.get("message", "").strip()
    stream = payload.get("stream", "General")
    student_name = payload.get("student_name", "Student")

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Generate grounded pedagogical response
    solution = generate_pedagogical_solution(message, stream=stream)

    reply_content = (
        f"Hello {student_name}! I am happy to help you with this topic in {stream}.\n\n"
        f"**Core Concept:** {solution['concept']}\n\n"
        f"**Governing Principles:** {solution['formula']}\n\n"
        + "\n\n".join(solution["steps"]) +
        f"\n\n> **Teacher's Note:** {solution['pitfall']}\n\n"
        f"📖 *Reference:* {solution['citation']}"
    )

    return {
        "role": "assistant",
        "content": reply_content,
        "concept": solution["concept"],
        "citation": solution["citation"],
    }


# Mount static frontend files if web directory exists
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def serve_index():
        index_file = WEB_DIR / "index.html"
        if index_file.exists():
            return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>SmileAI Web Suite Loading...</h1>")


if __name__ == "__main__":
    port = int(os.environ.get("SMILEAI_PORT", 4747))
    print(f"Starting SmileAI Educational Platform on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
