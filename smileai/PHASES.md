# Project Smiley — Phased Development & Testing Roadmap
> **Branch:** `smileai` | **Target:** Air-Gapped Indian Institutional Labs (20–30 PCs) | **Tech:** 100% Pure Vanilla HTML/CSS/JS + Python (No React, No npm)

---

## Architecture Principles
1. **Zero Intrusion on Main EduRAG:** All SmileAI code resides in `smileai/` and on the `smileai` branch.
2. **Self-Contained & Deliverable:** No dependencies on external folders or Node.js build steps.
3. **Phase-by-Phase Testing:** Each phase delivers an independently testable module with verification commands.

---

## Phases Overview

```
[ Phase 1: Voice Engine ]  --->  User Tests: Audio synthesis & warm teacher voice
          │
[ Phase 2: Institutional DB ]  --->  User Tests: CSV roster import & student PIN logins
          │
[ Phase 3: Snap & Solve ]  --->  User Tests: Exam paper image upload & step-by-step solution
          │
[ Phase 4: AI Builder Lab ]  --->  User Tests: Interactive tokens, vector plot & mini-bot export
          │
[ Phase 5: Web UI Suite ]  --->  User Tests: Student, Teacher, Admin workspaces (Pure HTML/CSS/JS)
          │
[ Phase 6: Control Center EXE ] ---> User Tests: Desktop GUI, LAN mode on 20-30 PCs, Clean Shutdown
```

---

## Phase 1: Voice & Persona Engine
- [x] **Objective:** Neural speech synthesis engine featuring Aarti warm voice default + regional languages + browser Web Speech fallback. (COMPLETED)
- **Components:**
  - `smileai/voice_engine.py`: Edge-TTS neural engine with zero GPU VRAM impact.
  - Default Persona: **Aarti** (`en-IN-NeerjaExpressiveNeural`), rate `-15%`, pitch `+15Hz` (gentle, smiling Indian school teacher).
  - Regional voices: **Shruti** (`te-IN-ShrutiNeural` / Telugu), **Swara** (`hi-IN-SwaraNeural` / Hindi), **Prabhat** (`en-IN-PrabhatNeural` / Male).
  - Standalone test server endpoint: `GET /api/smileai/voice/speak?text=...&voice=...`
- **Testing Procedure for User:**
  - Run test script: `.venv\Scripts\python smileai/test_voice.py`
  - Play back generated `.mp3` or listen in browser at `http://localhost:4747/api/smileai/voice/speak?text=Hello+students`.
  - Confirm Aarti sounds gentle, smiling, and patient.

---

## Phase 2: Institutional Database & Roster Manager
- [x] **Objective:** Production SQLite database for school/college labs with bulk student enrollment. (COMPLETED & VERIFIED)
- **Components:**
  - `smileai/db.py`: SQLite schema for institutions, streams (MPC, BiPC, CEC, HEC, NEET, MBBS, BDS, Law, B.Tech), classes, students, and grades.
  - `smileai/roster.py`: Bulk CSV/Excel parser that auto-provisions student accounts and 4-digit PINs.
  - ERP export: One-click export of student mastery and quiz logs to CSV.
- **Testing Procedure for User:**
  - Run: `.venv\Scripts\python smileai/test_roster.py`
  - Import sample CSV (`roll_no, name, stream, batch`).
  - Verify generated student PIN credentials and database queries.

---

## Phase 3: Snap & Solve Exam Paper Pipeline
- [x] **Objective:** Students/teachers upload photos of exam questions or handwritten math/physics problems to receive step-by-step solutions with textbook citations. (COMPLETED & VERIFIED)
- **Components:**
  - `smileai/solver.py`: Image upload (PNG, JPG, WEBP, PDF), OCR text extraction, formula parsing.
  - Syllabus Cross-Reference: Retrieves matching concepts and formulas from EduRAG's vector index.
  - 4-Part Pedagogical Output:
    1. 🎯 Core Concept & Formula
    2. 📝 Step-by-Step Derivation
    3. 💡 Exam Tip & Common Pitfalls
    4. 📖 Textbook Citation (NCERT / Syllabus)
- **Testing Procedure for User:**
  - Run: `.venv\Scripts\python smileai/test_solver.py --image test_question.png`
  - Verify structured response and textbook citation accuracy.

---

## Phase 4: AI Builder Lab
- [x] **Objective:** Interactive curriculum where Smiley teaches students how to build their own miniature AI models. (COMPLETED & VERIFIED)
- **Components:**
  - `smileai/builder.py`:
    - Module 1: Live Byte-Pair Encoding Tokenizer with color-coded tokens and vocabulary IDs.
    - Module 2: 2D Embedding Space Visualizer with live Cosine Similarity calculator.
    - Module 3: Mini-RAG in 10 lines of code.
    - Module 4: Prompt Persona tuning.
    - Module 5: Standalone mini-bot script exporter (`mini_ai_bot.py`).
- **Testing Procedure for User:**
  - Run: `.venv\Scripts\python smileai/test_builder.py`
  - Verify token breakdown and generated runnable mini-bot file.

---

## Phase 5: Pure HTML/CSS/JS Institutional Web Suite & Vocabulary Practice Engine
- [x] **Objective:** Complete, responsive frontend with zero dependencies, Dignified Educational Theme, Stream Vocabulary Practice, and Real-time Student Scoring. (COMPLETED & VERIFIED)
- **Components:**
  - `smileai/vocab.py`: Stream-tailored technical vocabulary & terminology practice engine (Definition Match, Fill-in-Blank, Sentence Usage Evaluator, instant score /10, zero-voice-engine required).
  - `smileai/web/index.html`: Responsive single-page app with 60px firm header.
  - `smileai/web/styles.css`: High-contrast Educational Palette (White, Slate, Academic Navy, Emerald, Amber), audio visualizer, scorecard badges, typography (`Outfit` + `Inter`).
  - `smileai/web/app.js`: Dynamic client logic, Web Speech STT/TTS fallback, image drag & drop, quiz player, vocabulary trainer, and live scoring.
  - Role switcher: Instant toggle between **Student Workspace**, **Vocabulary Trainer**, **AI Builder Lab**, **Teacher Portal**, and **Admin Hub**.
- **Testing Procedure for User:**
  - Open `http://localhost:4747` in any browser.
  - Test student chat with Aarti's warm voice.
  - Test Snap & Solve photo drag-and-drop.
  - Test Vocabulary Practice exercise and live score report.
  - Test AI Builder Lab and mini-bot download.

---

## Phase 6: Desktop Control Center & LAN Lab Launcher
- [x] **Objective:** Standalone Windows executable (`SmileAI.exe`) for lab teachers and admins. (COMPLETED & VERIFIED)
- **Components:**
  - `smileai/launcher.py`: Tkinter native GUI with:
    - **Start Server** button (port 4747).
    - **Open Web App** button.
    - **LAN Server Mode**: Displays host IP (`http://192.168.x.x:4747`) and QR code for 20–30 lab PCs.
    - **Hardware Monitor**: CPU, RAM, and GPU VRAM indicators.
    - **Clean Shutdown**: Graceful worker and database WAL flush.
  - Rebuilt `SmileAI.exe`.
- **Testing Procedure for User:**
  - Double click `SmileAI.exe`.
  - Connect a second PC or phone on the same Wi-Fi/LAN to the shown IP.
  - Test Clean Shutdown button.
