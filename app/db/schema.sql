PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS institutions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'teacher', 'admin')),
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE TABLE IF NOT EXISTS courses (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    knowledge_base_id TEXT NOT NULL,
    name TEXT NOT NULL,
    age_band TEXT NOT NULL DEFAULT 'adult',
    created_at TEXT NOT NULL,
    FOREIGN KEY (institution_id) REFERENCES institutions(id),
    FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id)
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    source_path TEXT,
    format TEXT,
    page_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ready',
    created_at TEXT NOT NULL,
    FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    knowledge_base_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    chapter TEXT,
    section TEXT,
    page INTEGER,
    source_file TEXT,
    content_type TEXT NOT NULL DEFAULT 'text',
    heading_path TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id),
    FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id TEXT PRIMARY KEY,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL,
    FOREIGN KEY (chunk_id) REFERENCES chunks(id)
);

CREATE TABLE IF NOT EXISTS topics (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL,
    name TEXT NOT NULL,
    parent_topic_id TEXT,
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

CREATE TABLE IF NOT EXISTS student_progress (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    mastery_score REAL NOT NULL DEFAULT 0,
    last_interaction_at TEXT NOT NULL,
    UNIQUE (student_id, topic_id),
    FOREIGN KEY (student_id) REFERENCES users(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    topic_id TEXT,
    course_id TEXT,
    question TEXT NOT NULL,
    student_answer TEXT,
    correct INTEGER,
    persona_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    course_id TEXT,
    persona_id TEXT NOT NULL DEFAULT 'tutor',
    title TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations_json TEXT,
    debug_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS escalations (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    conversation_id TEXT,
    reason TEXT NOT NULL,
    snippet TEXT,
    handled_by TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    status TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_course ON chunks(course_id);
CREATE INDEX IF NOT EXISTS idx_chunks_kb ON chunks(knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_progress_student ON student_progress(student_id);

CREATE TABLE IF NOT EXISTS answer_feedback (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    conversation_id TEXT,
    rating INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
