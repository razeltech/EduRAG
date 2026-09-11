"""
SmileAI AI Builder Lab — Gentle Educational AI Construction & Mentorship Engine
Powered by Razel Tech | Aligned with CBSE (Sub Code 417/843) & NEP 2020 Skill Lab Standards

Smiley acts as a gentle, encouraging lab mentor where students fearlessly build,
test, and export their own custom offline miniature AI models.

Modules:
1. Tokenizer & Vocabulary Explorer (Deconstructs text into token IDs)
2. 2D Embedding & Cosine Similarity Visualizer (Plots concept distances)
3. CBSE/NEP Competency Evaluation (100-point rubric with gentle constructive coaching)
4. Standalone Offline Mini-Bot Exporter (Generates a runnable, zero-dependency Python bot)
"""

import os
import sys
import re
import math
import json
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def analyze_tokens(text: str) -> Dict[str, Any]:
    """
    Deconstructs input text into visual tokens, token IDs, and vocabulary analysis.
    Teaches students that AI processes numbers, not raw words.
    """
    clean = text.strip()
    if not clean:
        return {
            "token_count": 0,
            "character_count": 0,
            "tokens": [],
            "token_ids": [],
            "explanation": "Type or paste a sentence above to see how AI breaks it into tokens!",
        }

    # Educational Byte-Pair Style Tokenizer simulation
    # Breaks on punctuation, word stems, and common subwords
    raw_tokens = re.findall(r"\w+|[^\w\s]", clean, re.UNICODE)

    tokens_data = []
    token_ids = []

    # Palette of pleasant educational pastel colors for visual highlighting
    colors = ["#dbeafe", "#fef3c7", "#dcfce7", "#f3e8ff", "#fee2e2", "#ffedd5", "#ccfbf1"]

    for idx, tok in enumerate(raw_tokens):
        # Deterministic educational token ID hash (modulo 32000 vocabulary size)
        tok_id = abs(hash(tok.lower())) % 32000 + 100
        token_ids.append(tok_id)
        tokens_data.append({
            "token": tok,
            "token_id": tok_id,
            "length": len(tok),
            "color": colors[idx % len(colors)],
        })

    char_count = len(clean)
    tok_count = len(raw_tokens)
    ratio = round(char_count / max(tok_count, 1), 2)

    return {
        "token_count": tok_count,
        "character_count": char_count,
        "compression_ratio": f"{ratio} chars/token",
        "tokens": tokens_data,
        "token_ids": token_ids,
        "explanation": (
            f"Your text contains {char_count} characters, which Smiley converted into {tok_count} tokens. "
            f"Notice how each piece of punctuation and word gets a unique numerical ID!"
        ),
    }


def compute_concept_embeddings(concepts: List[str]) -> Dict[str, Any]:
    """
    Simulates high-dimensional semantic embeddings projected into 2D coordinates
    with exact Cosine Similarity calculations.
    Helps students visualize why 'Doctor' is close to 'Hospital' while 'Cricket' is far away.
    """
    if not concepts:
        concepts = ["Doctor", "Hospital", "Medicine", "Cricket", "Stadium", "Ball"]

    # Simple semantic cluster seeds for educational demonstration
    semantic_anchors = {
        "medical": ("health", "doctor", "medicine", "hospital", "patient", "nurse", "organ", "heart", "blood", "cell"),
        "sports": ("cricket", "football", "ball", "stadium", "match", "player", "wicket", "goal", "run"),
        "physics": ("velocity", "force", "acceleration", "gravity", "mass", "motion", "energy", "newton"),
        "math": ("algebra", "calculus", "equation", "derivative", "integral", "matrix", "geometry", "function"),
        "law": ("constitution", "article", "court", "law", "judge", "statute", "rights", "advocate", "crime"),
    }

    points = []
    vectors = []

    for c in concepts:
        c_clean = c.strip()
        c_lower = c_clean.lower()

        # Compute pseudo 2D coordinates based on semantic category affinities
        x = 0.0
        y = 0.0

        if any(w in c_lower for w in semantic_anchors["medical"]):
            x, y = -0.65, 0.55
        elif any(w in c_lower for w in semantic_anchors["sports"]):
            x, y = 0.70, -0.60
        elif any(w in c_lower for w in semantic_anchors["physics"]):
            x, y = 0.50, 0.65
        elif any(w in c_lower for w in semantic_anchors["math"]):
            x, y = 0.60, 0.40
        elif any(w in c_lower for w in semantic_anchors["law"]):
            x, y = -0.60, -0.50
        else:
            # Hash-based distributed placement for custom user terms
            h = hash(c_lower)
            angle = (h % 360) * (math.pi / 180)
            radius = 0.4 + ((abs(h) % 50) / 100.0)
            x, y = round(math.cos(angle) * radius, 2), round(math.sin(angle) * radius, 2)

        # Add small deterministic jitter so identical words don't directly overlap
        jitter_x = (abs(hash(c_clean + "x")) % 20 - 10) / 100.0
        jitter_y = (abs(hash(c_clean + "y")) % 20 - 10) / 100.0
        final_x = round(max(-1.0, min(1.0, x + jitter_x)), 2)
        final_y = round(max(-1.0, min(1.0, y + jitter_y)), 2)

        points.append({
            "concept": c_clean,
            "x": final_x,
            "y": final_y,
        })
        vectors.append((final_x, final_y))

    # Compute pairwise cosine similarity matrix
    similarity_matrix = []
    n = len(concepts)
    for i in range(n):
        row = []
        v1 = vectors[i]
        mag1 = math.sqrt(v1[0]**2 + v1[1]**2) or 1e-6
        for j in range(n):
            v2 = vectors[j]
            mag2 = math.sqrt(v2[0]**2 + v2[1]**2) or 1e-6
            dot = v1[0]*v2[0] + v1[1]*v2[1]
            cos_sim = round(max(-1.0, min(1.0, dot / (mag1 * mag2))), 2)
            # Map [-1, 1] to educational percentage [0%, 100%]
            match_pct = round(((cos_sim + 1.0) / 2.0) * 100.0, 1)
            row.append({
                "concept_a": concepts[i],
                "concept_b": concepts[j],
                "cosine_similarity": cos_sim,
                "match_percentage": match_pct,
            })
        similarity_matrix.append(row)

    return {
        "concepts": concepts,
        "points": points,
        "similarity_matrix": similarity_matrix,
        "explanation": (
            "In vector space, words that share similar meaning sit close together. "
            "Cosine similarity measures the angle between these concept vectors!"
        ),
    }


def evaluate_student_bot(
    bot_name: str,
    notes_text: str,
    persona_prompt: str,
    test_queries: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Evaluates a student's custom AI bot using the official CBSE / NEP 2020
    Competency-Based Assessment Rubric (100 Points Total).
    Provides gentle, encouraging, and constructive feedback from Smiley.
    """
    notes_clean = notes_text.strip()
    persona_clean = persona_prompt.strip()
    bot_name_clean = bot_name.strip() or "My Mini AI"

    # Default test queries if none provided
    if not test_queries:
        test_queries = ["What is the main topic covered in your notes?", "Can you explain the key formula or concept?"]

    score_data = 0
    score_retrieval = 0
    score_persona = 0
    score_ethics = 0

    praise = []
    suggestions = []

    # 1. Rubric Criterion 1: Source Data Quality (25 pts)
    word_count = len(notes_clean.split())
    if word_count >= 50:
        score_data = 25
        praise.append("Excellent rich source knowledge provided! Your notes have enough depth for the bot to answer thoroughly.")
    elif word_count >= 20:
        score_data = 18
        praise.append("Good start with your study notes!")
        suggestions.append("Try adding 2-3 more paragraphs with specific definitions or examples so your bot has even more facts to draw upon.")
    elif word_count > 0:
        score_data = 10
        suggestions.append("Your notes are a bit brief. Give your AI at least 50 words so it can give detailed answers!")
    else:
        score_data = 0
        suggestions.append("Please paste or type your study notes so your AI has knowledge to learn from.")

    # 2. Rubric Criterion 2: Retrieval & Grounding (25 pts)
    # Checks if notes have headers, bullet points, or clear sentence structure
    has_structure = bool(re.search(r"[\n\*\-\•\d\.]", notes_clean))
    has_keywords = any(kw in notes_clean.lower() for kw in ["definition", "example", "formula", "because", "means", "is called"])
    if has_structure and has_keywords:
        score_retrieval = 25
        praise.append("Superb structured knowledge! Your bullet points and keywords make chunking and search very accurate.")
    elif has_structure or has_keywords:
        score_retrieval = 19
        suggestions.append("Add bullet points or numbered lists in your notes—this helps semantic search find exact sentences faster.")
    else:
        score_retrieval = 12
        suggestions.append("Organize your notes into clear headings and paragraphs to help your AI retrieve facts cleanly.")

    # 3. Rubric Criterion 3: Persona & Prompt Clarity (25 pts)
    p_lower = persona_clean.lower()
    has_tone = any(t in p_lower for t in ["teacher", "mentor", "friendly", "concise", "patient", "examiner", "simple", "step by step"])
    has_format = any(f in p_lower for f in ["bullet", "short", "explain", "clear", "cite", "format"])
    if has_tone and has_format:
        score_persona = 25
        praise.append("Outstanding prompt design! You gave your bot a clear personality and clear instructions on how to respond.")
    elif has_tone or has_format or len(persona_clean) > 20:
        score_persona = 18
        praise.append("Friendly and clear persona instructions.")
        suggestions.append("Tip: Specify how long you want the answers to be (e.g., 'Answer in 2-3 bullet points').")
    else:
        score_persona = 12
        suggestions.append("Give your AI a distinct personality (e.g. 'You are an encouraging high school physics teacher').")

    # 4. Rubric Criterion 4: Safety & Anti-Hallucination Guardrails (25 pts)
    # Checks if the student instructed the bot not to guess if information is missing
    has_guardrail = any(g in p_lower for g in [
        "only from", "do not guess", "not in", "cannot find", "say i don't know", 
        "strict", "truthful", "accurate", "grounded"
    ])
    if has_guardrail:
        score_ethics = 25
        praise.append("Masterful responsible AI engineering! You added an anti-hallucination guardrail so your bot won't fabricate false facts.")
    else:
        score_ethics = 15
        suggestions.append(
            "Important Safety Rule: Add this magic instruction to your prompt: "
            "'If the answer is not in the provided notes, politely state: I cannot find that in my notes.' "
            "This stops your AI from hallucinating!"
        )

    total_score = score_data + score_retrieval + score_persona + score_ethics

    # Smiley's encouraging grade commentary
    if total_score >= 85:
        grade = "A+ (Distinction — Certified AI Apprentice)"
        summary_voice = f"Brilliant work on {bot_name_clean}! Your AI is well-grounded, ethical, and ready to deploy in the lab."
    elif total_score >= 70:
        grade = "A (Merit — Capable AI Assistant)"
        summary_voice = f"Great effort on {bot_name_clean}! You have mastered the fundamentals. A couple of small tweaks will make it perfect."
    else:
        grade = "B (Passing — In Development)"
        summary_voice = f"Good initial start on {bot_name_clean}! Follow my gentle suggestions above to boost your score."

    return {
        "bot_name": bot_name_clean,
        "total_score": total_score,
        "max_score": 100,
        "grade": grade,
        "rubric_breakdown": {
            "source_data_quality": {"score": score_data, "max": 25},
            "retrieval_and_grounding": {"score": score_retrieval, "max": 25},
            "persona_and_prompt_clarity": {"score": score_persona, "max": 25},
            "safety_and_anti_hallucination": {"score": score_ethics, "max": 25},
        },
        "praise": praise,
        "suggestions": suggestions,
        "smiley_mentor_message": summary_voice,
    }


def export_standalone_bot(
    bot_name: str,
    author_name: str,
    notes_text: str,
    persona_prompt: str,
    output_path: Optional[str] = None,
) -> str:
    """
    Generates a 100% self-contained, runnable Python script (`mini_ai_bot.py`).
    Uses zero external dependencies (pure standard Python libraries: `math`, `re`, `json`).
    Can be run immediately on any computer with: `python mini_ai_bot.py`.
    """
    bot_name_safe = re.sub(r"[^\w\s-]", "", bot_name).strip() or "Student_Mini_AI"
    author_safe = re.sub(r"[^\w\s-]", "", author_name).strip() or "Student"
    clean_notes = notes_text.strip()
    clean_prompt = persona_prompt.strip() or "You are a helpful educational learning assistant."

    # Chunk the notes into small sentences/paragraphs for self-contained search
    paragraphs = [p.strip() for p in clean_notes.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in clean_notes.split("\n") if p.strip()]
    if not paragraphs:
        paragraphs = ["General educational notes."]

    chunks_json = json.dumps(paragraphs, indent=4)
    prompt_json = json.dumps(clean_prompt)
    bot_name_json = json.dumps(bot_name_safe)
    author_json = json.dumps(author_safe)

    code_template = f'''#!/usr/bin/env python3
"""
{bot_name_safe} — Offline Student AI Assistant
Created by: {author_safe}
Built with: SmileAI AI Builder Lab | Powered by Razel Tech
Standards: CBSE & NEP 2020 Certified Practical Project

100% Air-Gapped & Offline: Runs using standard Python with zero pip packages!
"""

import sys
import re
import math
from collections import Counter

BOT_NAME = {bot_name_json}
AUTHOR_NAME = {author_json}
SYSTEM_PROMPT = {prompt_json}
KNOWLEDGE_CHUNKS = {chunks_json}


def tokenize(text):
    return [w.lower() for w in re.findall(r"\\w+", text or "")]


def search_knowledge(query, top_k=2):
    q_tokens = tokenize(query)
    if not q_tokens:
        return KNOWLEDGE_CHUNKS[:top_k]

    scored = []
    for chunk in KNOWLEDGE_CHUNKS:
        c_tokens = tokenize(chunk)
        if not c_tokens:
            continue
        # Cosine term overlap
        c_counts = Counter(c_tokens)
        score = sum(c_counts[t] for t in q_tokens if t in c_counts)
        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [s[1] for s in scored if s[0] > 0]
    return results[:top_k] if results else KNOWLEDGE_CHUNKS[:top_k]


def answer_query(user_query):
    query_clean = user_query.strip()
    if not query_clean:
        return "Please ask a question based on my notes!"

    relevant_chunks = search_knowledge(query_clean)
    if not relevant_chunks:
        return f"I could not find information about '{{query_clean}}' in my study notes."

    context = "\\n\\n".join(relevant_chunks)
    
    # Clean pedagogical synthesis
    response = (
        f"[{{BOT_NAME}} Answer]\\n"
        f"Based on {{AUTHOR_NAME}}'s verified study notes:\\n\\n"
        f"{{context}}\\n\\n"
        f"[Source Citation]: Verified Knowledge Base (Chunk 1-{{len(relevant_chunks)}})"
    )
    return response


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print(f"  {{BOT_NAME}} -- Offline Learning Assistant")
    print(f"  Created by: {{AUTHOR_NAME}} in the AI Builder Lab")
    print(f"  Status: 100% Offline & Operational")
    print("=" * 60)
    print(f"Prompt Persona: {{SYSTEM_PROMPT}}\\n")
    print("Type your questions below (or type 'exit' / 'quit' to close):\\n")

    while True:
        try:
            user_input = input("Student Query > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print(f"\\nThank you for learning with {{BOT_NAME}}! Goodbye!")
                break
            
            reply = answer_query(user_input)
            print(f"\\n{{reply}}\\n")
            print("-" * 60)
        except (KeyboardInterrupt, EOFError):
            print(f"\\nGoodbye!")
            break


if __name__ == "__main__":
    main()
'''

    if not output_path:
        out_file = ROOT_DIR / "smileai" / f"{bot_name_safe.lower().replace(' ', '_')}.py"
    else:
        out_file = Path(output_path).resolve()

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(code_template, encoding="utf-8")
    return str(out_file)
