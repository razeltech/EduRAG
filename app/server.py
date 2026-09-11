"""FastAPI LAN server — one API, one UI shell."""
from __future__ import annotations

from contextlib import asynccontextmanager
import json
import socket
from pathlib import Path
from typing import Any

from fastapi import Body, Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.auth import decode_token, hash_password, make_token, verify_password
from app.config_load import ROOT, load_config
from app.characters import delete as delete_character
from app.characters import editor_payload, private_adult_ids, public_list, upsert
try:
    from app.companion import OWNER_EMAIL as COMPANION_EMAIL
    from app.companion import PERSONA_ID as COMPANION_PERSONA_ID
    COMPANION_AVAILABLE = True
except ImportError:
    COMPANION_EMAIL = "companion@local.internal"
    COMPANION_PERSONA_ID = "companion"
    COMPANION_AVAILABLE = False
from app.db import default_institution_id, init_db
from app.db.store import Store
from app.fsbrowse import list_folder
from app.jobs import get_job, start_index_job
from app.personas import DEFAULT_PERSONA_ID
from app.pipeline import index_path
from app.rag import generate_answer, retrieve_for_course

WEB_DIR = ROOT / "web"
UPLOAD_DIR = ROOT / "data" / "uploads"
_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store(init_db())
        from app.bootstrap import seed_demo_users

        seed_demo_users(_store)
        if COMPANION_AVAILABLE:
            try:
                from app.companion import ensure_ready

                ensure_ready(_store)
            except Exception:
                pass
    return _store


def local_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "127.0.0.1"


def current_user(
    authorization: str | None = Header(default=None),
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in required")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    if payload.get("typ") == "companion":
        raise HTTPException(401, "Sign in required")
    user = store.get_user(payload["sub"])
    if not user:
        raise HTTPException(401, "User not found")
    return user


def require_roles(*roles: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "Not allowed for this role")
        return user

    return dep


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6, max_length=120)
    role: str | None = None


class LoginIn(BaseModel):
    email: str
    password: str


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = None
    course_id: str | None = None
    persona: str | None = None
    debug: bool = False


class CourseIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    age_band: str = "adult"


class CoursePatch(BaseModel):
    age_band: str = Field(min_length=2, max_length=8)


class IngestPathIn(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    max_files: int = Field(default=4000, ge=1, le=20000)


class SearchIn(BaseModel):
    query: str
    course_id: str
    top_k: int = 5


class QuizGradeIn(BaseModel):
    course_id: str | None = None
    topic: str | None = None
    question: str
    student_answer: str
    correct: bool
    persona: str = "chat"


class EscalationHandleIn(BaseModel):
    id: str


class FeedbackIn(BaseModel):
    conversation_id: str | None = None
    rating: int


class LlmSelectIn(BaseModel):
    model: str = Field(min_length=1, max_length=120)


class LlmPullIn(BaseModel):
    model: str = Field(min_length=1, max_length=120)


class CharacterIn(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=80)
    tagline: str = ""
    system_prompt: str = Field(min_length=8, max_length=8000)
    uses_library: bool = False
    temperature: float = 0.75
    history_turns: int = 20
    filters: dict[str, bool] | None = None
    private: bool = False
    rating: str = "teen"
    adult_confirm: bool = False
    partner_role: str = ""


class CompanionUnlockIn(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    adult_confirm: bool = False


class CompanionProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    partner_role: str = "girlfriend"
    partner_gender: str = ""
    partner_pronouns: str = ""
    system_prompt: str = ""
    temperature: float = 1.05
    adult_confirm: bool = False
    reset_voice: bool = False
    user_name: str = ""
    user_gender: str = "man"
    user_pronouns: str = "he/him"
    user_called: str = ""
    user_about: str = ""
    card: dict[str, Any] = Field(default_factory=dict)
    user_card: dict[str, Any] = Field(default_factory=dict)
    dynamics: dict[str, Any] = Field(default_factory=dict)
    generation: dict[str, Any] = Field(default_factory=dict)


class CompanionChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    history: list[dict[str, str]] = Field(default_factory=list)


def bind_companion_device(
    x_companion_device: str | None = Header(default=None),
    user_agent: str | None = Header(default=None),
) -> str:
    if not COMPANION_AVAILABLE:
        return ""
    from app.companion_engine import bind_device

    return bind_device(x_companion_device or "", user_agent or "")


def companion_user(
    authorization: str | None = Header(default=None),
    store: Store = Depends(get_store),
    _device: str = Depends(bind_companion_device),
) -> dict[str, Any]:
    del _device
    if not COMPANION_AVAILABLE:
        raise HTTPException(404, "Companion module not installed")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Unlock required")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    if payload.get("typ") != "companion":
        raise HTTPException(401, "Unlock required")
    user = store.get_user(payload["sub"])
    if not user or user.get("email") != COMPANION_EMAIL:
        raise HTTPException(401, "Unlock required")
    return user


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    yield
    from app.llm import unload_model

    unload_model()


def create_app() -> FastAPI:
    app = FastAPI(title="EduRAG", docs_url="/v1/docs", redoc_url=None, lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if WEB_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=str(WEB_DIR)), name="assets")

    @app.get("/")
    def home():
        index = WEB_DIR / "index.html"
        if not index.is_file():
            return {"ok": True, "service": "EduRAG"}
        return FileResponse(index)

    if COMPANION_AVAILABLE:
        @app.get("/companion")
        def companion_page():
            page = WEB_DIR / "companion.html"
            if not page.is_file():
                raise HTTPException(404, "Companion page missing")
            return FileResponse(page)

    @app.get("/v1/health")
    def health():
        cfg = load_config()
        from app.ingest.ocr import available_languages, model_dir
        from app.llm import llm_settings
        from app.rerank import rerank_available

        rerank_ok, rerank_kind = rerank_available()
        s = llm_settings()
        return {
            "ok": True,
            "llm": s.get("model"),
            "llm_label": s.get("label"),
            "reranker": rerank_ok,
            "rerank": rerank_kind,
            "ocr_languages": available_languages(model_dir()),
        }

    @app.get("/v1/llm/models")
    def llm_models():
        """List selectable chat backends (Ollama). No auth — used on lock/settings screens."""
        from app.llm import list_models, llm_settings, pull_status

        return {
            "active": llm_settings().get("model"),
            "models": list_models(),
            "pull": pull_status(),
            "base_url": llm_settings().get("base_url"),
        }

    @app.post("/v1/llm/model")
    def llm_select(body: LlmSelectIn):
        from app.llm import OllamaError, set_active_model

        try:
            return set_active_model(body.model.strip())
        except (ValueError, OllamaError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/v1/llm/pull")
    def llm_pull(body: LlmPullIn):
        """Start `ollama pull` in a background thread. Poll GET /v1/llm/models for status."""
        import threading

        from app.llm import OllamaError, get_model_entry, pull_model, pull_status

        entry = get_model_entry(body.model.strip())
        name = entry.get("ollama_name") or entry["id"]
        st = pull_status()
        if st.get("running"):
            raise HTTPException(409, f"Already pulling {st.get('model')}")

        def _job() -> None:
            try:
                pull_model(name)
            except Exception:
                pass

        threading.Thread(target=_job, daemon=True).start()
        return {"ok": True, "started": True, "model": name}

    @app.get("/v1/auth/defaults")
    def auth_defaults():
        from app.bootstrap import public_demo_accounts

        return public_demo_accounts()

    @app.get("/v1/personas")
    def personas(user: dict = Depends(current_user)):
        return public_list(user)

    @app.get("/v1/characters/{persona_id}")
    def character_get(persona_id: str, user: dict = Depends(current_user)):
        row = editor_payload(persona_id, user)
        if not row:
            raise HTTPException(404, "Character not found")
        return row

    @app.post("/v1/characters")
    def character_save(
        body: CharacterIn,
        user: dict = Depends(current_user),
    ):
        data = body.model_dump()
        data["private"] = False
        data["rating"] = "teen"
        data["adult_confirm"] = False
        if isinstance(data.get("filters"), dict):
            data["filters"]["adult_private"] = False
        try:
            return upsert(data, as_new=not body.id, owner=user)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.put("/v1/characters/{persona_id}")
    def character_update(
        persona_id: str,
        body: CharacterIn,
        user: dict = Depends(current_user),
    ):
        data = body.model_dump()
        data["id"] = persona_id
        data["private"] = False
        data["rating"] = "teen"
        data["adult_confirm"] = False
        if isinstance(data.get("filters"), dict):
            data["filters"]["adult_private"] = False
        try:
            return upsert(data, as_new=False, owner=user)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.delete("/v1/characters/{persona_id}")
    def character_delete(
        persona_id: str,
        user: dict = Depends(current_user),
    ):
        if not delete_character(persona_id, user):
            raise HTTPException(404, "No custom version to remove")
        return {"ok": True}

    @app.post("/v1/auth/register")
    def register(body: RegisterIn, store: Store = Depends(get_store)):
        if store.get_user_by_email(body.email):
            raise HTTPException(400, "Email already registered")
        iid = default_institution_id(store.conn)
        role = "admin" if store.user_count() == 0 else (body.role or "student")
        if role not in {"student", "teacher", "admin"}:
            role = "student"
        if store.user_count() > 0 and role == "admin":
            role = "student"
        user = store.create_user(
            institution_id=iid,
            role=role,
            name=body.name.strip(),
            email=str(body.email),
            password_hash=hash_password(body.password),
        )
        token = make_token(user)
        return {"token": token, "user": _public_user(user)}

    @app.post("/v1/auth/login")
    def login(body: LoginIn, store: Store = Depends(get_store)):
        user = store.get_user_by_email(str(body.email))
        if not user or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(401, "Wrong email or password")
        return {"token": make_token(user), "user": _public_user(user)}

    @app.get("/v1/me")
    def me(user: dict = Depends(current_user)):
        return _public_user(user)

    @app.get("/v1/courses")
    def courses(user: dict = Depends(current_user), store: Store = Depends(get_store)):
        return store.list_courses(user["institution_id"])

    @app.post("/v1/courses")
    def create_course(
        body: CourseIn,
        user: dict = Depends(require_roles("teacher", "admin")),
        store: Store = Depends(get_store),
    ):
        return store.get_or_create_course(
            body.name.strip(),
            user["institution_id"],
            age_band=body.age_band,
        )

    @app.patch("/v1/courses/{course_id}")
    def patch_course(
        course_id: str,
        body: CoursePatch,
        user: dict = Depends(require_roles("teacher", "admin")),
        store: Store = Depends(get_store),
    ):
        course = _course_or_404(store, course_id, user["institution_id"])
        store.set_course_age_band(course["id"], body.age_band)
        return store.get_course(course["id"])

    @app.get("/v1/courses/{course_id}/topics")
    def course_topics(
        course_id: str,
        user: dict = Depends(current_user),
        store: Store = Depends(get_store),
    ):
        _course_or_404(store, course_id, user["institution_id"])
        return store.list_topics_with_mastery(course_id, user["id"])

    @app.get("/v1/courses/{course_id}/progress")
    def course_progress(
        course_id: str,
        user: dict = Depends(require_roles("teacher", "admin")),
        store: Store = Depends(get_store),
    ):
        _course_or_404(store, course_id, user["institution_id"])
        return store.list_course_progress(course_id)

    @app.delete("/v1/courses/{course_id}")
    def delete_course(
        course_id: str,
        user: dict = Depends(require_roles("teacher", "admin")),
        store: Store = Depends(get_store),
    ):
        _course_or_404(store, course_id, user["institution_id"])
        store.delete_course(course_id)
        return {"ok": True}

    @app.get("/v1/fs")
    def browse_fs(
        path: str | None = None,
        user: dict = Depends(require_roles("teacher", "admin")),
    ):
        del user
        try:
            return list_folder(path)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, f"Cannot open that folder: {exc}") from exc

    @app.get("/v1/courses/{course_id}/documents")
    def documents(
        course_id: str,
        user: dict = Depends(current_user),
        store: Store = Depends(get_store),
    ):
        _course_or_404(store, course_id, user["institution_id"])
        return store.list_documents(course_id)

    @app.delete("/v1/documents/{doc_id}")
    def delete_doc(
        doc_id: str,
        user: dict = Depends(require_roles("teacher", "admin")),
        store: Store = Depends(get_store),
    ):
        store.delete_document(doc_id)
        return {"ok": True}

    @app.post("/v1/courses/{course_id}/ingest")
    async def ingest_upload(
        course_id: str,
        file: UploadFile = File(...),
        user: dict = Depends(require_roles("teacher", "admin")),
        store: Store = Depends(get_store),
    ):
        course = _course_or_404(store, course_id, user["institution_id"])
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest = UPLOAD_DIR / (file.filename or "upload.bin")
        dest.write_bytes(await file.read())
        result = index_path(dest, course["name"], institution_id=user["institution_id"])
        return result

    @app.post("/v1/courses/{course_id}/ingest-path")
    def ingest_folder(
        course_id: str,
        body: IngestPathIn,
        user: dict = Depends(require_roles("teacher", "admin")),
        store: Store = Depends(get_store),
    ):
        from pathlib import Path

        course = _course_or_404(store, course_id, user["institution_id"])
        target = Path(body.path).expanduser()
        try:
            target = target.resolve()
        except OSError as exc:
            raise HTTPException(400, f"Cannot read path: {exc}") from exc
        if not target.exists():
            raise HTTPException(
                400,
                f"Nothing at that path on this machine: {target}",
            )
        job = start_index_job(
            target,
            course["name"],
            institution_id=user["institution_id"],
            max_files=body.max_files,
        )
        return job

    @app.get("/v1/jobs/{job_id}")
    def ingest_job(
        job_id: str,
        user: dict = Depends(require_roles("teacher", "admin")),
    ):
        del user
        job = get_job(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return job

    @app.post("/v1/search")
    def search(
        body: SearchIn,
        user: dict = Depends(current_user),
        store: Store = Depends(get_store),
    ):
        _course_or_404(store, body.course_id, user["institution_id"])
        debug = retrieve_for_course(body.course_id, body.query, store, top_k=body.top_k)
        return debug

    @app.get("/v1/conversations")
    def conversations(user: dict = Depends(current_user), store: Store = Depends(get_store)):
        return store.list_conversations(user["id"])

    @app.get("/v1/conversations/{conv_id}/messages")
    def messages(
        conv_id: str,
        user: dict = Depends(current_user),
        store: Store = Depends(get_store),
    ):
        conv = store.get_conversation(conv_id)
        if not conv or conv["user_id"] != user["id"]:
            raise HTTPException(404, "Conversation not found")
        return store.list_messages(conv_id)

    @app.delete("/v1/conversations/{conv_id}")
    def delete_conv(
        conv_id: str,
        user: dict = Depends(current_user),
        store: Store = Depends(get_store),
    ):
        store.delete_conversation(conv_id, user["id"])
        return {"ok": True}

    @app.post("/v1/chat")
    def chat(
        body: ChatIn,
        user: dict = Depends(current_user),
        store: Store = Depends(get_store),
    ):
        persona = body.persona or DEFAULT_PERSONA_ID
        if persona == COMPANION_PERSONA_ID:
            persona = DEFAULT_PERSONA_ID
        if body.course_id:
            _course_or_404(store, body.course_id, user["institution_id"])

        if body.conversation_id:
            conv = store.get_conversation(body.conversation_id)
            if not conv or conv["user_id"] != user["id"]:
                raise HTTPException(404, "Conversation not found")
            if body.persona:
                store.update_conversation(conv["id"], persona_id=persona)
            if body.course_id:
                store.update_conversation(conv["id"], course_id=body.course_id)
            conv = store.get_conversation(conv["id"])
        else:
            title = body.message.strip()[:60]
            conv = store.create_conversation(user["id"], body.course_id, persona, title)

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in store.list_messages(conv["id"])
            if m["role"] in {"user", "assistant"}
        ]
        store.add_message(conv["id"], "user", body.message.strip())

        def events():
            answer = ""
            citations = []
            quiz = None
            debug = {}
            try:
                for event in generate_answer(
                    question=body.message.strip(),
                    persona_id=conv["persona_id"],
                    course_id=conv.get("course_id"),
                    history=history,
                    store=store,
                    user_id=user["id"],
                    conversation_id=conv["id"],
                    viewer=user,
                ):
                    name = event.get("event")
                    if name == "token":
                        answer += event.get("text") or ""
                        yield _sse("token", {"text": event.get("text")})
                    elif name == "meta":
                        citations = event.get("citations") or []
                        debug = event.get("debug") or {}
                        yield _sse(
                            "meta",
                            {
                                "conversation_id": conv["id"],
                                "persona": conv["persona_id"],
                                "citations": citations,
                            },
                        )
                    elif name == "escalation":
                        yield _sse("escalation", {"reason": event.get("reason")})
                    elif name == "done":
                        answer = event.get("answer") or answer
                        citations = event.get("citations") or citations
                        quiz = event.get("quiz")
                        debug = event.get("debug") or debug
            except Exception as exc:
                yield _sse("error", {"detail": str(exc)})
                return
            store.add_message(
                conv["id"],
                "assistant",
                answer,
                citations=json.dumps(citations),
                debug=json.dumps(debug) if body.debug else None,
            )
            if quiz and quiz.get("question"):
                topic = store.topic_by_name(conv.get("course_id") or "", quiz.get("topic") or "")
                store.record_quiz(
                    student_id=user["id"],
                    course_id=conv.get("course_id"),
                    topic_id=topic["id"] if topic else None,
                    question=quiz["question"],
                    student_answer=None,
                    correct=None,
                    persona_id=conv["persona_id"],
                )
            payload = {
                "conversation_id": conv["id"],
                "answer": answer,
                "citations": citations,
                "quiz": quiz,
            }
            if body.debug:
                payload["debug"] = debug
            yield _sse("done", payload)

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/v1/progress")
    def progress(
        course_id: str | None = None,
        user: dict = Depends(current_user),
        store: Store = Depends(get_store),
    ):
        return store.list_progress(user["id"], course_id)

    @app.post("/v1/quiz/grade")
    def grade_quiz(
        body: QuizGradeIn,
        user: dict = Depends(current_user),
        store: Store = Depends(get_store),
    ):
        topic = None
        if body.course_id and body.topic:
            topic = store.topic_by_name(body.course_id, body.topic)
        store.record_quiz(
            student_id=user["id"],
            course_id=body.course_id,
            topic_id=topic["id"] if topic else None,
            question=body.question,
            student_answer=body.student_answer,
            correct=body.correct,
            persona_id=body.persona,
        )
        return {"ok": True, "progress": store.list_progress(user["id"], body.course_id)}

    @app.get("/v1/escalations")
    def escalations(
        user: dict = Depends(require_roles("teacher", "admin")),
        store: Store = Depends(get_store),
    ):
        return store.list_escalations(user["institution_id"])

    @app.post("/v1/escalations/handle")
    def handle_esc(
        body: EscalationHandleIn,
        user: dict = Depends(require_roles("teacher", "admin")),
        store: Store = Depends(get_store),
    ):
        store.handle_escalation(body.id, user["id"])
        return {"ok": True}

    @app.post("/v1/feedback")
    def feedback(
        body: FeedbackIn,
        user: dict = Depends(current_user),
        store: Store = Depends(get_store),
    ):
        if body.rating not in (-1, 1):
            raise HTTPException(400, "Rating must be 1 or -1")
        store.add_feedback(user["id"], body.conversation_id, body.rating)
        return {"ok": True}

    @app.get("/v1/users")
    def users(
        user: dict = Depends(require_roles("admin")),
        store: Store = Depends(get_store),
    ):
        return [
            u
            for u in store.list_users(user["institution_id"])
            if u.get("email") != COMPANION_EMAIL
        ]

    @app.get("/v1/audit/conversations")
    def audit_conversations(
        user: dict = Depends(require_roles("admin")),
        store: Store = Depends(get_store),
    ):
        hidden = private_adult_ids() | {COMPANION_PERSONA_ID}
        rows = store.list_audit_conversations(user["institution_id"])
        return [
            r
            for r in rows
            if r.get("persona_id") not in hidden and r.get("user_email") != COMPANION_EMAIL
        ]

    @app.get("/v1/audit/conversations/{conv_id}/messages")
    def audit_messages(
        conv_id: str,
        user: dict = Depends(require_roles("admin")),
        store: Store = Depends(get_store),
    ):
        conv = store.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        owner = store.get_user(conv["user_id"])
        if not owner or owner["institution_id"] != user["institution_id"]:
            raise HTTPException(404, "Conversation not found")
        if conv.get("persona_id") == COMPANION_PERSONA_ID or (
            owner.get("email") == COMPANION_EMAIL
        ):
            raise HTTPException(404, "Conversation not found")
        return store.list_messages(conv_id)

    if COMPANION_AVAILABLE:
        _register_companion_routes(app)

    return app


def _register_companion_routes(app: FastAPI) -> None:
    @app.post("/v1/companion/unlock")
    def companion_unlock(
        body: CompanionUnlockIn,
        store: Store = Depends(get_store),
        _device: str = Depends(bind_companion_device),
    ):
        del _device
        from app.companion import unlock as companion_unlock_key

        try:
            return companion_unlock_key(body.key, store, adult_confirm=body.adult_confirm)
        except ValueError as exc:
            raise HTTPException(401, str(exc)) from exc

    @app.get("/v1/companion/profile")
    def companion_profile_get(user: dict = Depends(companion_user)):
        del user
        from app.companion import public_profile

        return public_profile()

    @app.put("/v1/companion/profile")
    def companion_profile_put(
        body: CompanionProfileIn,
        user: dict = Depends(companion_user),
    ):
        del user
        from app.companion import update_profile

        try:
            return update_profile(body.model_dump())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/v1/companion/chat")
    def companion_chat(
        body: CompanionChatIn,
        user: dict = Depends(companion_user),
    ):
        del user
        from app.companion import load_state
        from app.companion_engine import (
            append_chat,
            history_for_llm,
            stream_chat as companion_stream,
        )

        state = load_state()
        if not state.get("adult_confirm"):
            raise HTTPException(400, "Confirm you are 18+ in settings first.")
        msg = (body.message or "").strip()
        if not msg:
            raise HTTPException(400, "Empty message")
        user_item = append_chat("user", msg)
        history = history_for_llm()[:-1]
        user_id = user_item.get("id") or ""

        def events():
            answer = ""
            choices = []
            image_job = None
            try:
                for event in companion_stream(
                    profile=state,
                    question=msg,
                    history=history,
                ):
                    name = event.get("event")
                    if name == "token":
                        answer += event.get("text") or ""
                        yield _sse("token", {"text": event.get("text")})
                    elif name == "meta":
                        payload = {"persona": COMPANION_PERSONA_ID}
                        if event.get("debug"):
                            payload["debug"] = event["debug"]
                        yield _sse("meta", payload)
                    elif name == "done":
                        answer = event.get("answer") or answer
                        choices = event.get("choices") or []
                        image_job = event.get("image_job")
                        done = {"answer": answer, "user_id": user_id}
                        if event.get("debug"):
                            done["debug"] = event["debug"]
                        if image_job:
                            done["image_job"] = image_job
                        if choices:
                            done["choices"] = choices
                        if event.get("see_this"):
                            done["see_this"] = True
                        asst = append_chat(
                            "assistant",
                            answer,
                            choices=choices or None,
                            image_job=image_job,
                            see_this=bool(event.get("see_this")),
                        )
                        done["assistant_id"] = asst.get("id") or ""
                        yield _sse("done", done)
                        return
            except Exception as exc:
                yield _sse("error", {"detail": str(exc)})
                return
            asst = append_chat("assistant", answer, choices=choices or None, image_job=image_job)
            yield _sse("done", {"answer": answer, "user_id": user_id, "assistant_id": asst.get("id") or ""})

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/v1/companion/messages")
    def companion_messages(user: dict = Depends(companion_user)):
        del user
        from app.companion_engine import load_chat

        return {"messages": load_chat()}

    @app.post("/v1/companion/imagine")
    def companion_imagine(
        body: dict[str, Any],
        user: dict = Depends(companion_user),
    ):
        del user
        from app.companion import load_state
        from app.companion_engine import load_runtime, save_runtime
        from app.companion_image import images_ready, look_unknown, shot_choice_list
        from app.companion_jobs import image_busy

        state = load_state()
        if not state.get("adult_confirm"):
            raise HTTPException(400, "Confirm you are 18+ first.")
        runtime = load_runtime()
        if not images_ready(runtime):
            raise HTTPException(400, "Keep talking a bit first.")
        if image_busy():
            raise HTTPException(429, "A picture is already running. Stop it first.")
        text = str(body.get("text") or "").strip()
        if not text:
            raise HTTPException(400, "Nothing to show.")
        if look_unknown(state):
            raise HTTPException(400, "Tell her how she looks first — hair and what she is wearing.")
        runtime["pending_image"] = {
            "asked": "angle",
            "extra": text,
            "kind": "character",
            "user_text": text,
            "reply": text,
        }
        try:
            save_runtime(runtime)
        except Exception:
            pass
        return {"ok": True, "ask": "angle", "choices": shot_choice_list("angle")}

    @app.post("/v1/companion/choice")
    def companion_choice(
        body: dict[str, Any],
        user: dict = Depends(companion_user),
    ):
        del user
        from app.companion import load_state
        from app.companion_engine import load_runtime, save_runtime
        from app.companion_image import apply_shot_choice, images_ready, shot_choice_list

        state = load_state()
        if not state.get("adult_confirm"):
            raise HTTPException(400, "Confirm you are 18+ first.")
        choice_id = str(body.get("id") or "").strip().lower()
        labels = {}
        for ask in ("shot", "frame", "see", "angle"):
            for c in shot_choice_list(ask):
                labels[c["id"]] = c["label"]
        if choice_id not in labels:
            raise HTTPException(400, "Unknown choice")
        runtime = load_runtime()
        if not images_ready(runtime):
            raise HTTPException(400, "Keep talking a bit first.")
        job = apply_shot_choice(profile=state, runtime=runtime, choice_id=choice_id)
        try:
            save_runtime(runtime)
        except Exception:
            pass
        image_job = None
        if job:
            image_job = {"id": job["id"], "status": job.get("status")}
        pending = (runtime.get("pending_image") or {})
        next_ask = pending.get("asked")
        extra_choices = shot_choice_list(next_ask) if next_ask and not job else []
        return {"ok": True, "image_job": image_job, "choices": extra_choices}

    @app.post("/v1/companion/new")
    def companion_new(user: dict = Depends(companion_user)):
        del user
        from app.companion_engine import clear_chat, load_runtime, save_runtime
        from app.companion_jobs import request_stop, reset_session_caps

        request_stop(chat=True, image=True)
        reset_session_caps()
        clear_chat()

        runtime = load_runtime()
        runtime["interaction"] = {
            "mood": "at ease",
            "current_scene": "unspecified — with them",
            "current_dynamic": "none",
        }
        runtime["pending_image"] = {}
        emo = dict(runtime.get("emotion") or {})
        emo["intensity"] = 0.25
        runtime["emotion"] = emo
        save_runtime(runtime)
        return {"ok": True}

    @app.get("/v1/companion/debug")
    def companion_debug(user: dict = Depends(companion_user)):
        del user
        from app.companion_engine import last_debug, load_memory, load_runtime

        return {
            "last": last_debug(),
            "runtime": load_runtime(),
            "memory": load_memory(),
        }

    @app.post("/v1/companion/reset-memory")
    def companion_reset_memory(user: dict = Depends(companion_user)):
        del user
        from app.companion_engine import reset_memory, reset_runtime

        return {"runtime": reset_runtime(), "memory": reset_memory()}

    @app.get("/v1/companion/status")
    def companion_status(user: dict = Depends(companion_user)):
        del user
        from app.companion_engine import load_runtime
        from app.companion_image import images_ready
        from app.companion_jobs import image_busy, last_image_meta, resource_state

        runtime = load_runtime()
        ready = images_ready(runtime)
        return {
            "resource": resource_state(),
            "image_busy": image_busy(),
            "images_ready": ready,
            "images_unlocked": bool(runtime.get("images_unlocked") or ready),
            "turns": int(runtime.get("turns") or 0),
            **last_image_meta(),
        }

    @app.get("/v1/companion/jobs/{job_id}")
    def companion_job(job_id: str, user: dict = Depends(companion_user)):
        del user
        from app.companion_jobs import get_job

        job = get_job(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        public = {k: v for k, v in job.items() if k != "payload"}
        return public

    @app.get("/v1/companion/gallery")
    def companion_gallery(user: dict = Depends(companion_user)):
        del user
        from app.companion_image import list_gallery

        return {"images": list_gallery()}

    @app.get("/v1/companion/images/{name}")
    def companion_image_file(name: str, user: dict = Depends(companion_user)):
        del user
        from app.companion_image import find_image

        safe = Path(name).name
        if safe != name or ".." in name:
            raise HTTPException(400, "Bad filename")
        path = find_image(safe)
        if not path:
            raise HTTPException(404, "Image not found")
        return FileResponse(path, media_type="image/png")

    @app.post("/v1/companion/stop")
    def companion_stop(
        body: dict[str, Any] = Body(default_factory=dict),
        user: dict = Depends(companion_user),
    ):
        del user
        from app.companion_jobs import request_stop

        body = body or {}
        return request_stop(
            job_id=str(body["job_id"]) if body.get("job_id") else None,
            chat=body.get("chat", True),
            image=body.get("image", True),
        )

    @app.post("/v1/companion/jobs/{job_id}/cancel")
    def companion_job_cancel(job_id: str, user: dict = Depends(companion_user)):
        del user
        from app.companion_jobs import get_job, request_stop

        if not get_job(job_id):
            raise HTTPException(404, "Job not found")
        return request_stop(job_id=job_id, chat=False, image=True)

    @app.post("/v1/companion/image")
    def companion_image_post(
        body: dict[str, Any],
        user: dict = Depends(companion_user),
    ):
        del user
        from app.companion import load_state
        from app.companion_engine import load_runtime, save_runtime
        from app.companion_image import images_ready, parse_command, prepare_image_turn, queue_if_needed
        from app.companion_jobs import image_busy

        state = load_state()
        if not state.get("adult_confirm"):
            raise HTTPException(400, "Confirm you are 18+ first.")
        if image_busy():
            raise HTTPException(429, "A picture is already running. Stop it first.")
        runtime = load_runtime()
        if not images_ready(runtime):
            raise HTTPException(400, "Keep talking a bit first.")
        extra = str(body.get("extra") or "").strip()
        if not extra:
            extra = str((runtime.get("last_shot") or {}).get("extra") or "").strip()
        count = body.get("count")
        cmd = {"kind": "manual", "count": 1, "extra": extra}
        if count is not None:
            try:
                cmd["count"] = max(1, min(3, int(count)))
            except (TypeError, ValueError):
                cmd["count"] = 1
        if extra.startswith("/"):
            parsed = parse_command(extra)
            if parsed:
                cmd = parsed
        plan = prepare_image_turn(
            profile=state,
            runtime=runtime,
            user_text=extra or "/image",
            command=cmd,
        )
        if plan.get("hold"):
            runtime["pending_image"] = plan.get("pending") or {}
            try:
                save_runtime(runtime)
            except Exception:
                pass
            raise HTTPException(400, "Answer in chat first: the view, the two of you, or her.")
        job = queue_if_needed(
            profile=state,
            runtime=runtime,
            user_text=extra or "/image",
            reply="",
            command=cmd,
            shot_kind=plan.get("kind") or None,
        )
        try:
            save_runtime(runtime)
        except Exception:
            pass
        if not job:
            raise HTTPException(400, "Could not queue an image.")
        return job


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "institution_id": user["institution_id"],
    }


def _course_or_404(store: Store, course_id: str, institution_id: str) -> dict[str, Any]:
    course = store.get_course(course_id)
    if not course or course["institution_id"] != institution_id:
        raise HTTPException(404, "Course not found")
    return course


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


app = create_app()
