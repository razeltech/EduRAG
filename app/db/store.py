from __future__ import annotations

import sqlite3
from typing import Any

import numpy as np

from app.db import default_institution_id, new_id, pack_vector, row_dict, unpack_vector, utcnow


class Store:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # --- users / auth -------------------------------------------------
    def user_count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def create_user(
        self,
        *,
        institution_id: str,
        role: str,
        name: str,
        email: str,
        password_hash: str,
    ) -> dict[str, Any]:
        uid = new_id()
        self.conn.execute(
            "INSERT INTO users (id, institution_id, role, name, email, password_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, institution_id, role, name, email.lower().strip(), password_hash, utcnow()),
        )
        self.conn.commit()
        return self.get_user(uid)  # type: ignore[return-value]

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        return row_dict(
            self.conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        )

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        return row_dict(
            self.conn.execute(
                "SELECT * FROM users WHERE email=?", (email.lower().strip(),)
            ).fetchone()
        )

    def set_password_hash(self, user_id: str, password_hash: str) -> None:
        self.conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?", (password_hash, user_id)
        )
        self.conn.commit()

    def list_users(self, institution_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id, institution_id, role, name, email, created_at FROM users "
            "WHERE institution_id=? ORDER BY created_at",
            (institution_id,),
        ).fetchall()
        return [row_dict(r) for r in rows]  # type: ignore[misc]

    # --- courses ------------------------------------------------------
    def get_or_create_course(
        self,
        name: str,
        institution_id: str | None = None,
        age_band: str = "adult",
    ) -> dict[str, Any]:
        iid = institution_id or default_institution_id(self.conn)
        row = self.conn.execute(
            "SELECT * FROM courses WHERE institution_id=? AND name=?",
            (iid, name),
        ).fetchone()
        if row:
            return row_dict(row)  # type: ignore[return-value]
        if age_band not in {"adult", "k12"}:
            age_band = "adult"
        kb_id = new_id()
        course_id = new_id()
        now = utcnow()
        self.conn.execute(
            "INSERT INTO knowledge_bases (id, institution_id, name, created_at) VALUES (?, ?, ?, ?)",
            (kb_id, iid, name, now),
        )
        self.conn.execute(
            "INSERT INTO courses (id, institution_id, knowledge_base_id, name, age_band, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (course_id, iid, kb_id, name, age_band, now),
        )
        self.conn.commit()
        return row_dict(
            self.conn.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
        )  # type: ignore[return-value]

    def list_courses(self, institution_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT c.*, "
            "(SELECT COUNT(*) FROM documents d WHERE d.course_id=c.id) AS document_count, "
            "(SELECT COUNT(*) FROM chunks k WHERE k.course_id=c.id) AS chunk_count "
            "FROM courses c WHERE c.institution_id=? ORDER BY c.created_at",
            (institution_id,),
        ).fetchall()
        return [row_dict(r) for r in rows]  # type: ignore[misc]

    def get_course(self, course_id: str) -> dict[str, Any] | None:
        return row_dict(
            self.conn.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
        )

    def set_course_age_band(self, course_id: str, age_band: str) -> None:
        if age_band not in {"adult", "k12"}:
            age_band = "adult"
        self.conn.execute("UPDATE courses SET age_band=? WHERE id=?", (age_band, course_id))
        self.conn.commit()

    def list_audit_conversations(self, institution_id: str, limit: int = 80) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT c.id, c.title, c.persona_id, c.course_id, c.created_at, "
            "u.name AS user_name, u.role AS user_role, u.email AS user_email, "
            "(SELECT m.content FROM messages m WHERE m.conversation_id=c.id "
            " ORDER BY m.created_at DESC LIMIT 1) AS last_message "
            "FROM conversations c JOIN users u ON u.id=c.user_id "
            "WHERE u.institution_id=? ORDER BY c.created_at DESC LIMIT ?",
            (institution_id, limit),
        ).fetchall()
        return [row_dict(r) for r in rows]  # type: ignore[misc]

    def delete_course(self, course_id: str) -> None:
        course = self.get_course(course_id)
        if not course:
            return
        kb_id = course["knowledge_base_id"]
        self.conn.execute(
            "DELETE FROM embeddings WHERE chunk_id IN (SELECT id FROM chunks WHERE course_id=?)",
            (course_id,),
        )
        self.conn.execute("DELETE FROM chunks WHERE course_id=?", (course_id,))
        self.conn.execute("DELETE FROM documents WHERE course_id=?", (course_id,))
        self.conn.execute(
            "DELETE FROM student_progress WHERE topic_id IN (SELECT id FROM topics WHERE course_id=?)",
            (course_id,),
        )
        self.conn.execute("DELETE FROM topics WHERE course_id=?", (course_id,))
        self.conn.execute("DELETE FROM quiz_attempts WHERE course_id=?", (course_id,))
        self.conn.execute(
            "UPDATE conversations SET course_id=NULL WHERE course_id=?",
            (course_id,),
        )
        self.conn.execute("DELETE FROM courses WHERE id=?", (course_id,))
        self.conn.execute("DELETE FROM knowledge_bases WHERE id=?", (kb_id,))
        self.conn.commit()

    # --- documents / chunks ------------------------------------------
    def add_document(
        self,
        *,
        course: dict[str, Any],
        filename: str,
        source_path: str | None,
        fmt: str,
        page_count: int,
        chunks: list[dict[str, Any]],
        vectors: np.ndarray,
    ) -> dict[str, Any]:
        doc_id = new_id()
        now = utcnow()
        self.conn.execute(
            "INSERT INTO documents (id, knowledge_base_id, course_id, filename, source_path, "
            "format, page_count, chunk_count, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?)",
            (
                doc_id,
                course["knowledge_base_id"],
                course["id"],
                filename,
                source_path,
                fmt,
                page_count,
                len(chunks),
                now,
            ),
        )
        for i, chunk in enumerate(chunks):
            cid = new_id()
            self.conn.execute(
                "INSERT INTO chunks (id, document_id, knowledge_base_id, course_id, chunk_index, "
                "text, chapter, section, page, source_file, content_type, heading_path, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cid,
                    doc_id,
                    course["knowledge_base_id"],
                    course["id"],
                    i,
                    chunk["text"],
                    chunk.get("chapter"),
                    chunk.get("section"),
                    chunk.get("page"),
                    chunk.get("source_file") or filename,
                    chunk.get("content_type") or "text",
                    chunk.get("heading_path"),
                    now,
                ),
            )
            vec = vectors[i]
            self.conn.execute(
                "INSERT INTO embeddings (chunk_id, dim, vector) VALUES (?, ?, ?)",
                (cid, int(vec.shape[0]), pack_vector(vec)),
            )
            self._ensure_topic(course["id"], chunk.get("chapter"), chunk.get("section"))
        self.conn.commit()
        return {"id": doc_id, "filename": filename, "chunk_count": len(chunks)}

    def _ensure_topic(self, course_id: str, chapter: str | None, section: str | None) -> None:
        parent_id = None
        if chapter:
            parent_id = self._topic_id(course_id, chapter, None)
        if section:
            self._topic_id(course_id, section, parent_id)

    def _topic_id(self, course_id: str, name: str, parent_id: str | None) -> str:
        row = self.conn.execute(
            "SELECT id FROM topics WHERE course_id=? AND name=? AND "
            "((parent_topic_id IS NULL AND ? IS NULL) OR parent_topic_id=?)",
            (course_id, name, parent_id, parent_id),
        ).fetchone()
        if row:
            return row["id"]
        tid = new_id()
        self.conn.execute(
            "INSERT INTO topics (id, course_id, name, parent_topic_id) VALUES (?, ?, ?, ?)",
            (tid, course_id, name, parent_id),
        )
        return tid

    def list_documents(self, course_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM documents WHERE course_id=? ORDER BY created_at DESC",
            (course_id,),
        ).fetchall()
        return [row_dict(r) for r in rows]  # type: ignore[misc]

    def delete_document(self, doc_id: str) -> None:
        ids = [
            r["id"]
            for r in self.conn.execute(
                "SELECT id FROM chunks WHERE document_id=?", (doc_id,)
            ).fetchall()
        ]
        if ids:
            self.conn.executemany("DELETE FROM embeddings WHERE chunk_id=?", [(i,) for i in ids])
        self.conn.execute("DELETE FROM chunks WHERE document_id=?", (doc_id,))
        self.conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        self.conn.commit()

    def load_index(self, course_id: str) -> tuple[list[dict[str, Any]], np.ndarray | None]:
        rows = self.conn.execute(
            "SELECT c.*, e.dim, e.vector FROM chunks c "
            "JOIN embeddings e ON e.chunk_id=c.id "
            "WHERE c.course_id=? ORDER BY c.source_file, c.chunk_index",
            (course_id,),
        ).fetchall()
        chunks = []
        vectors = []
        for row in rows:
            item = row_dict(row)
            assert item is not None
            dim = item.pop("dim")
            blob = item.pop("vector")
            chunks.append(item)
            vectors.append(unpack_vector(blob, dim))
        if not vectors:
            return [], None
        return chunks, np.vstack(vectors)

    def list_topics(self, course_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM topics WHERE course_id=? ORDER BY name", (course_id,)
        ).fetchall()
        return [row_dict(r) for r in rows]  # type: ignore[misc]

    def list_topics_with_mastery(
        self, course_id: str, student_id: str | None = None
    ) -> list[dict[str, Any]]:
        topics = self.list_topics(course_id)
        if not student_id:
            return topics
        prog = {p["topic_id"]: p for p in self.list_progress(student_id, course_id)}
        out: list[dict[str, Any]] = []
        for topic in topics:
            row = dict(topic)
            hit = prog.get(topic["id"])
            score = None if not hit else float(hit.get("mastery_score") or 0)
            row["mastery_score"] = score
            row["weak"] = score is not None and score < 0.45
            out.append(row)
        return out

    def list_course_progress(self, course_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT p.*, t.name AS topic_name, t.course_id, "
            "u.name AS student_name, u.email AS student_email "
            "FROM student_progress p "
            "JOIN topics t ON t.id=p.topic_id "
            "JOIN users u ON u.id=p.student_id "
            "WHERE t.course_id=? ORDER BY u.name, p.mastery_score ASC",
            (course_id,),
        ).fetchall()
        return [row_dict(r) for r in rows]  # type: ignore[misc]

    def topic_by_name(self, course_id: str, name: str) -> dict[str, Any] | None:
        return row_dict(
            self.conn.execute(
                "SELECT * FROM topics WHERE course_id=? AND name=?",
                (course_id, name),
            ).fetchone()
        )

    # --- conversations ------------------------------------------------
    def create_conversation(
        self, user_id: str, course_id: str | None, persona_id: str, title: str
    ) -> dict[str, Any]:
        cid = new_id()
        self.conn.execute(
            "INSERT INTO conversations (id, user_id, course_id, persona_id, title, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (cid, user_id, course_id, persona_id, title, utcnow()),
        )
        self.conn.commit()
        return self.get_conversation(cid)  # type: ignore[return-value]

    def get_conversation(self, conv_id: str) -> dict[str, Any] | None:
        return row_dict(
            self.conn.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
        )

    def list_conversations(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM conversations WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [row_dict(r) for r in rows]  # type: ignore[misc]

    def delete_conversation(self, conv_id: str, user_id: str) -> None:
        self.conn.execute("DELETE FROM messages WHERE conversation_id=?", (conv_id,))
        self.conn.execute(
            "DELETE FROM conversations WHERE id=? AND user_id=?", (conv_id, user_id)
        )
        self.conn.commit()

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        citations: str | None = None,
        debug: str | None = None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, citations_json, debug_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_id(), conversation_id, role, content, citations, debug, utcnow()),
        )
        self.conn.commit()

    def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at",
            (conversation_id,),
        ).fetchall()
        return [row_dict(r) for r in rows]  # type: ignore[misc]

    def update_conversation(self, conv_id: str, **fields: Any) -> None:
        allowed = {"persona_id", "course_id", "title"}
        fields = {k: v for k, v in fields.items() if k in allowed}
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [conv_id]
        self.conn.execute(f"UPDATE conversations SET {sets} WHERE id=?", vals)
        self.conn.commit()

    # --- learning -----------------------------------------------------
    def record_quiz(
        self,
        *,
        student_id: str,
        course_id: str | None,
        topic_id: str | None,
        question: str,
        student_answer: str | None,
        correct: bool | None,
        persona_id: str,
    ) -> str:
        qid = new_id()
        self.conn.execute(
            "INSERT INTO quiz_attempts (id, student_id, topic_id, course_id, question, "
            "student_answer, correct, persona_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                qid,
                student_id,
                topic_id,
                course_id,
                question,
                student_answer,
                None if correct is None else int(correct),
                persona_id,
                utcnow(),
            ),
        )
        if topic_id is not None and correct is not None:
            self._bump_mastery(student_id, topic_id, 0.12 if correct else -0.08)
        self.conn.commit()
        return qid

    def _bump_mastery(self, student_id: str, topic_id: str, delta: float) -> None:
        row = self.conn.execute(
            "SELECT id, mastery_score FROM student_progress WHERE student_id=? AND topic_id=?",
            (student_id, topic_id),
        ).fetchone()
        now = utcnow()
        if row:
            score = min(1.0, max(0.0, float(row["mastery_score"]) + delta))
            self.conn.execute(
                "UPDATE student_progress SET mastery_score=?, last_interaction_at=? WHERE id=?",
                (score, now, row["id"]),
            )
        else:
            score = min(1.0, max(0.0, 0.5 + delta))
            self.conn.execute(
                "INSERT INTO student_progress (id, student_id, topic_id, mastery_score, last_interaction_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (new_id(), student_id, topic_id, score, now),
            )

    def list_progress(self, student_id: str, course_id: str | None = None) -> list[dict[str, Any]]:
        sql = (
            "SELECT p.*, t.name AS topic_name, t.course_id FROM student_progress p "
            "JOIN topics t ON t.id=p.topic_id WHERE p.student_id=?"
        )
        args: list[Any] = [student_id]
        if course_id:
            sql += " AND t.course_id=?"
            args.append(course_id)
        sql += " ORDER BY p.mastery_score ASC"
        return [row_dict(r) for r in self.conn.execute(sql, args).fetchall()]  # type: ignore[misc]

    def add_escalation(
        self, student_id: str, conversation_id: str | None, reason: str, snippet: str
    ) -> dict[str, Any]:
        eid = new_id()
        self.conn.execute(
            "INSERT INTO escalations (id, student_id, conversation_id, reason, snippet, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (eid, student_id, conversation_id, reason, snippet[:500], utcnow()),
        )
        self.conn.commit()
        return row_dict(
            self.conn.execute("SELECT * FROM escalations WHERE id=?", (eid,)).fetchone()
        )  # type: ignore[return-value]

    def list_escalations(self, institution_id: str, open_only: bool = True) -> list[dict[str, Any]]:
        sql = (
            "SELECT e.*, u.name AS student_name, u.email AS student_email "
            "FROM escalations e JOIN users u ON u.id=e.student_id "
            "WHERE u.institution_id=?"
        )
        args: list[Any] = [institution_id]
        if open_only:
            sql += " AND e.handled_by IS NULL"
        sql += " ORDER BY e.created_at DESC"
        return [row_dict(r) for r in self.conn.execute(sql, args).fetchall()]  # type: ignore[misc]

    def handle_escalation(self, escalation_id: str, handled_by: str) -> None:
        self.conn.execute(
            "UPDATE escalations SET handled_by=? WHERE id=?",
            (handled_by, escalation_id),
        )
        self.conn.commit()

    def add_feedback(self, user_id: str, conversation_id: str | None, rating: int) -> None:
        self.conn.execute(
            "INSERT INTO answer_feedback (id, user_id, conversation_id, rating, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (new_id(), user_id, conversation_id, int(rating), utcnow()),
        )
        self.conn.commit()
