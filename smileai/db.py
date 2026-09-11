"""
SmileAI Institutional Database & Roster Management Engine
Powered by Razel Tech | Agile, Fully Dynamic Multi-Tenant SQLite Database

Supports all Indian curriculum streams (K-10, MPC, BiPC, CEC, HEC, NEET, MBBS, BDS, Law, B.Tech, B.Com, Masters).
Zero hardcoded data: Dynamic institutions, streams, batches, student rosters, assessments, and gradebooks.
"""

import os
import sys
import csv
import io
import json
import sqlite3
import hashlib
import secrets
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

DEFAULT_DB_PATH = os.environ.get("SMILEAI_DB_PATH", str(Path(__file__).resolve().parent / "smileai.db"))


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Creates a thread-safe SQLite connection with WAL mode and foreign keys enabled."""
    target_path = db_path or DEFAULT_DB_PATH
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def hash_pin(pin: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hashes a 4-digit PIN using SHA256 with a random salt."""
    if not salt:
        salt = secrets.token_hex(8)
    hashed = hashlib.sha256(f"{salt}{pin}".encode("utf-8")).hexdigest()
    return hashed, salt


def verify_pin(pin: str, hashed: str, salt: str) -> bool:
    """Verifies a 4-digit PIN against stored hash and salt."""
    test_hash, _ = hash_pin(pin, salt)
    return secrets.compare_digest(test_hash, hashed)


def init_db(db_path: Optional[str] = None) -> None:
    """Initializes the institutional multi-tenant database schema."""
    conn = get_db_connection(db_path)
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS institutions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            board_type TEXT NOT NULL,  -- CBSE, ICSE, State Board, Autonomous, University
            contact_email TEXT,
            contact_phone TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS streams (
            id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            code TEXT NOT NULL,         -- e.g. K10, MPC, BIPC, CEC, HEC, NEET, MBBS, BDS, BTECH, LAW
            name TEXT NOT NULL,         -- e.g. Intermediate MPC (JEE), Medical MBBS
            category TEXT NOT NULL,     -- school, intermediate, higher_ed, professional
            description TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
            UNIQUE(institution_id, code)
        );

        CREATE TABLE IF NOT EXISTS batches_classes (
            id TEXT PRIMARY KEY,
            stream_id TEXT NOT NULL,
            class_grade TEXT NOT NULL,  -- e.g. "10", "11", "12", "1st Year", "2nd Year"
            section TEXT NOT NULL,      -- e.g. "A", "B", "Batch 1"
            academic_year TEXT NOT NULL,-- e.g. "2026-2027"
            created_at TEXT NOT NULL,
            FOREIGN KEY (stream_id) REFERENCES streams(id) ON DELETE CASCADE,
            UNIQUE(stream_id, class_grade, section, academic_year)
        );

        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            roll_no TEXT NOT NULL,
            name TEXT NOT NULL,
            pin_hash TEXT NOT NULL,
            pin_salt TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            parent_phone TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
            FOREIGN KEY (batch_id) REFERENCES batches_classes(id) ON DELETE CASCADE,
            UNIQUE(institution_id, roll_no)
        );

        CREATE TABLE IF NOT EXISTS teachers (
            id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            employee_id TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            specialization TEXT,
            pin_hash TEXT NOT NULL,
            pin_salt TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
            UNIQUE(institution_id, employee_id)
        );

        CREATE TABLE IF NOT EXISTS assessments (
            id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            stream_id TEXT NOT NULL,
            title TEXT NOT NULL,
            topic TEXT NOT NULL,
            difficulty TEXT NOT NULL,   -- easy, medium, hard
            questions_json TEXT NOT NULL,
            created_by TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
            FOREIGN KEY (stream_id) REFERENCES streams(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id TEXT PRIMARY KEY,
            assessment_id TEXT NOT NULL,
            student_id TEXT NOT NULL,
            answers_json TEXT NOT NULL,
            score REAL NOT NULL,
            total_marks REAL NOT NULL,
            mastery_percentage REAL NOT NULL,
            feedback_json TEXT,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS snap_solutions (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            image_filename TEXT NOT NULL,
            ocr_text TEXT,
            concept_identified TEXT NOT NULL,
            solution_markdown TEXT NOT NULL,
            citation TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_students_roll ON students(institution_id, roll_no);
        CREATE INDEX IF NOT EXISTS idx_students_batch ON students(batch_id);
        CREATE INDEX IF NOT EXISTS idx_submissions_student ON submissions(student_id);
        CREATE INDEX IF NOT EXISTS idx_submissions_assessment ON submissions(assessment_id);
        """)
    conn.close()


def create_institution(
    name: str,
    code: str,
    board_type: str = "State Board",
    contact_email: Optional[str] = None,
    contact_phone: Optional[str] = None,
    db_path: Optional[str] = None,
) -> str:
    """Registers an educational institution."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    inst_id = f"inst_{secrets.token_hex(6)}"
    now = datetime.utcnow().isoformat()
    with conn:
        conn.execute(
            """
            INSERT INTO institutions (id, name, code, board_type, contact_email, contact_phone, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (inst_id, name.strip(), code.strip().upper(), board_type.strip(), contact_email, contact_phone, now),
        )
    conn.close()
    return inst_id


def create_stream(
    institution_id: str,
    code: str,
    name: str,
    category: str = "intermediate",
    description: Optional[str] = None,
    db_path: Optional[str] = None,
) -> str:
    """Creates a curriculum stream (e.g. MPC, BiPC, NEET, MBBS, Law, B.Tech)."""
    conn = get_db_connection(db_path)
    stream_id = f"stream_{secrets.token_hex(6)}"
    now = datetime.utcnow().isoformat()
    with conn:
        conn.execute(
            """
            INSERT INTO streams (id, institution_id, code, name, category, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (stream_id, institution_id, code.strip().upper(), name.strip(), category.strip(), description, now),
        )
    conn.close()
    return stream_id


def get_or_create_batch(
    stream_id: str,
    class_grade: str,
    section: str = "A",
    academic_year: str = "2026-2027",
    db_path: Optional[str] = None,
) -> str:
    """Finds or creates a batch/class for a given stream."""
    conn = get_db_connection(db_path)
    class_grade = class_grade.strip()
    section = section.strip().upper()
    academic_year = academic_year.strip()

    with conn:
        cur = conn.execute(
            """
            SELECT id FROM batches_classes
            WHERE stream_id = ? AND class_grade = ? AND section = ? AND academic_year = ?
            """,
            (stream_id, class_grade, section, academic_year),
        )
        row = cur.fetchone()
        if row:
            batch_id = row["id"]
        else:
            batch_id = f"batch_{secrets.token_hex(6)}"
            now = datetime.utcnow().isoformat()
            conn.execute(
                """
                INSERT INTO batches_classes (id, stream_id, class_grade, section, academic_year, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (batch_id, stream_id, class_grade, section, academic_year, now),
            )
    conn.close()
    return batch_id


def import_roster_csv(
    csv_text_or_path: str,
    institution_id: str,
    default_stream_code: str = "GENERAL",
    academic_year: str = "2026-2027",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Agile CSV Roster Importer:
    Accepts flexible CSV headers (case-insensitive, handles various column namings).
    Auto-creates streams/batches dynamically and generates secure 4-digit PINs.
    Returns imported count and lab credential list.
    """
    init_db(db_path)
    conn = get_db_connection(db_path)

    # Read content
    if os.path.exists(csv_text_or_path):
        with open(csv_text_or_path, "r", encoding="utf-8-sig") as f:
            lines = f.read()
    else:
        lines = csv_text_or_path

    reader = csv.DictReader(io.StringIO(lines.strip()))
    if not reader.fieldnames:
        conn.close()
        return {"imported": 0, "errors": ["Empty or invalid CSV file"], "credentials": []}

    # Normalize field map
    field_map = {}
    for f in reader.fieldnames:
        norm = f.strip().lower().replace(" ", "_").replace("-", "_")
        if norm in ("roll_no", "roll_number", "rollno", "admission_no", "id", "student_id"):
            field_map["roll_no"] = f
        elif norm in ("name", "student_name", "full_name"):
            field_map["name"] = f
        elif norm in ("stream", "branch", "course", "department"):
            field_map["stream"] = f
        elif norm in ("class", "grade", "class_grade", "standard", "year"):
            field_map["class_grade"] = f
        elif norm in ("section", "sec", "batch"):
            field_map["section"] = f
        elif norm in ("email", "student_email"):
            field_map["email"] = f
        elif norm in ("phone", "mobile", "student_phone"):
            field_map["phone"] = f
        elif norm in ("parent_phone", "guardian_phone"):
            field_map["parent_phone"] = f

    if "roll_no" not in field_map or "name" not in field_map:
        conn.close()
        return {
            "imported": 0,
            "errors": ["CSV must contain 'roll_no' and 'name' columns"],
            "credentials": [],
        }

    imported_count = 0
    errors = []
    credentials = []
    now = datetime.utcnow().isoformat()

    with conn:
        for idx, row in enumerate(reader, start=1):
            roll_no = str(row[field_map["roll_no"]]).strip()
            name = str(row[field_map["name"]]).strip()
            if not roll_no or not name:
                errors.append(f"Row {idx}: Missing roll_no or name")
                continue

            stream_code = (
                str(row[field_map["stream"]]).strip().upper()
                if "stream" in field_map and row.get(field_map["stream"])
                else default_stream_code
            )
            class_grade = (
                str(row[field_map["class_grade"]]).strip()
                if "class_grade" in field_map and row.get(field_map["class_grade"])
                else "10"
            )
            section = (
                str(row[field_map["section"]]).strip().upper()
                if "section" in field_map and row.get(field_map["section"])
                else "A"
            )
            email = str(row[field_map["email"]]).strip() if "email" in field_map else None
            phone = str(row[field_map["phone"]]).strip() if "phone" in field_map else None
            parent_phone = str(row[field_map["parent_phone"]]).strip() if "parent_phone" in field_map else None

            # Get or create stream
            cur = conn.execute(
                "SELECT id FROM streams WHERE institution_id = ? AND code = ?",
                (institution_id, stream_code),
            )
            st_row = cur.fetchone()
            if st_row:
                stream_id = st_row["id"]
            else:
                stream_id = f"stream_{secrets.token_hex(6)}"
                conn.execute(
                    """
                    INSERT INTO streams (id, institution_id, code, name, category, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (stream_id, institution_id, stream_code, stream_code, "academic", now),
                )

            # Get or create batch
            cur = conn.execute(
                """
                SELECT id FROM batches_classes
                WHERE stream_id = ? AND class_grade = ? AND section = ? AND academic_year = ?
                """,
                (stream_id, class_grade, section, academic_year),
            )
            bt_row = cur.fetchone()
            if bt_row:
                batch_id = bt_row["id"]
            else:
                batch_id = f"batch_{secrets.token_hex(6)}"
                conn.execute(
                    """
                    INSERT INTO batches_classes (id, stream_id, class_grade, section, academic_year, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (batch_id, stream_id, class_grade, section, academic_year, now),
                )

            # Generate random 4-digit PIN (e.g. 1000 - 9999)
            raw_pin = f"{secrets.randbelow(9000) + 1000}"
            pin_hash, pin_salt = hash_pin(raw_pin)
            student_id = f"stu_{secrets.token_hex(6)}"

            try:
                conn.execute(
                    """
                    INSERT INTO students (id, institution_id, batch_id, roll_no, name, pin_hash, pin_salt, email, phone, parent_phone, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(institution_id, roll_no) DO UPDATE SET
                        name = excluded.name,
                        batch_id = excluded.batch_id,
                        email = excluded.email,
                        phone = excluded.phone,
                        parent_phone = excluded.parent_phone
                    """,
                    (student_id, institution_id, batch_id, roll_no, name, pin_hash, pin_salt, email, phone, parent_phone, now),
                )
                imported_count += 1
                credentials.append({
                    "roll_no": roll_no,
                    "name": name,
                    "stream": stream_code,
                    "class_grade": class_grade,
                    "section": section,
                    "pin": raw_pin,
                })
            except Exception as e:
                errors.append(f"Row {idx} (Roll: {roll_no}): {str(e)}")

    conn.close()
    return {
        "imported": imported_count,
        "errors": errors,
        "credentials": credentials,
    }


def authenticate_student(
    institution_id: str,
    roll_no: str,
    pin: str,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Authenticates a student using Roll Number and 4-digit PIN."""
    conn = get_db_connection(db_path)
    result = None
    try:
        with conn:
            cur = conn.execute(
                """
                SELECT s.id, s.name, s.roll_no, s.pin_hash, s.pin_salt, s.institution_id,
                       b.class_grade, b.section, b.academic_year,
                       st.code as stream_code, st.name as stream_name
                FROM students s
                JOIN batches_classes b ON s.batch_id = b.id
                JOIN streams st ON b.stream_id = st.id
                WHERE s.institution_id = ? AND s.roll_no = ? AND s.status = 'active'
                """,
                (institution_id, roll_no.strip()),
            )
            row = cur.fetchone()
            if row and verify_pin(pin.strip(), row["pin_hash"], row["pin_salt"]):
                result = {
                    "id": row["id"],
                    "name": row["name"],
                    "roll_no": row["roll_no"],
                    "institution_id": row["institution_id"],
                    "stream": row["stream_code"],
                    "stream_name": row["stream_name"],
                    "class_grade": row["class_grade"],
                    "section": row["section"],
                    "academic_year": row["academic_year"],
                }
    finally:
        conn.close()
    return result


def save_assessment(
    institution_id: str,
    stream_id: str,
    title: str,
    topic: str,
    difficulty: str,
    questions: List[Dict[str, Any]],
    created_by: Optional[str] = None,
    db_path: Optional[str] = None,
) -> str:
    """Saves an auto-generated assessment quiz."""
    conn = get_db_connection(db_path)
    assessment_id = f"assess_{secrets.token_hex(6)}"
    now = datetime.utcnow().isoformat()
    with conn:
        conn.execute(
            """
            INSERT INTO assessments (id, institution_id, stream_id, title, topic, difficulty, questions_json, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (assessment_id, institution_id, stream_id, title, topic, difficulty.lower(), json.dumps(questions), created_by, now),
        )
    conn.close()
    return assessment_id


def submit_assessment(
    assessment_id: str,
    student_id: str,
    answers: Dict[str, Any],
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates a student's submission against the assessment's answer key,
    computes score and percentage, and logs the result.
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            cur = conn.execute("SELECT questions_json FROM assessments WHERE id = ?", (assessment_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Assessment {assessment_id} not found")

            questions = json.loads(row["questions_json"])
            total_questions = len(questions)
            correct_count = 0
            detailed_feedback = []

            for q in questions:
                qid = str(q.get("id"))
                student_choice = answers.get(qid)
                correct_choice = q.get("correct_answer")
                is_correct = (student_choice == correct_choice)
                if is_correct:
                    correct_count += 1

                detailed_feedback.append({
                    "question_id": qid,
                    "question": q.get("question"),
                    "student_answer": student_choice,
                    "correct_answer": correct_choice,
                    "is_correct": is_correct,
                    "explanation": q.get("explanation", ""),
                })

            score = float(correct_count)
            total_marks = float(total_questions)
            mastery = (score / total_marks * 100.0) if total_marks > 0 else 0.0

            sub_id = f"sub_{secrets.token_hex(6)}"
            now = datetime.utcnow().isoformat()

            conn.execute(
                """
                INSERT INTO submissions (id, assessment_id, student_id, answers_json, score, total_marks, mastery_percentage, feedback_json, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sub_id, assessment_id, student_id, json.dumps(answers), score, total_marks, mastery, json.dumps(detailed_feedback), now),
            )

        return {
            "submission_id": sub_id,
            "score": score,
            "total_marks": total_marks,
            "mastery_percentage": round(mastery, 1),
            "feedback": detailed_feedback,
        }
    finally:
        conn.close()


def export_gradebook_csv(institution_id: str, stream_id: Optional[str] = None, db_path: Optional[str] = None) -> str:
    """Exports student assessment scores as a CSV formatted for school/college ERPs."""
    conn = get_db_connection(db_path)
    try:
        query = """
            SELECT s.roll_no, s.name as student_name, st.code as stream, b.class_grade, b.section,
                   a.title as assessment_title, a.topic, sub.score, sub.total_marks, sub.mastery_percentage, sub.submitted_at
            FROM submissions sub
            JOIN students s ON sub.student_id = s.id
            JOIN assessments a ON sub.assessment_id = a.id
            JOIN batches_classes b ON s.batch_id = b.id
            JOIN streams st ON b.stream_id = st.id
            WHERE s.institution_id = ?
        """
        params = [institution_id]
        if stream_id:
            query += " AND st.id = ?"
            params.append(stream_id)

        query += " ORDER BY b.class_grade, b.section, s.roll_no, sub.submitted_at DESC"

        with conn:
            cur = conn.execute(query, params)
            rows = cur.fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Roll Number", "Student Name", "Stream", "Class", "Section",
            "Assessment Title", "Topic", "Score", "Total Marks", "Mastery %", "Date Submitted"
        ])
        for r in rows:
            writer.writerow([
                r["roll_no"], r["student_name"], r["stream"], r["class_grade"], r["section"],
                r["assessment_title"], r["topic"], r["score"], r["total_marks"], r["mastery_percentage"], r["submitted_at"]
            ])

        return output.getvalue()
    finally:
        conn.close()
