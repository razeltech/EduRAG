"""
SmileAI Vocabulary & Technical Terminology Practice Engine
Powered by Razel Tech | Stream-Tailored Academic Terminology & Real-Time Performance Scoring
100% Lightweight & Text-Based — Runs Offline with Zero Voice Engine Dependencies

Supports:
- School K-10 (Science, Math, Civics)
- Intermediate MPC (Physics, Chemistry, Advanced Math)
- Intermediate BiPC & NEET (Botany, Zoology, Genetics)
- Legal Studies & Judiciary (Legal Maxims, Statutory Terms, Constitutional Concepts)
- Medical MBBS & BDS (Pathology, Anatomy, Pharmacology)
- Engineering B.Tech & CS (Data Structures, Algorithms, AI/ML Concepts)

Exercise Types:
1. Definition & Meaning Quiz (4 options, instant grading)
2. Fill-in-the-Blank Terminology Challenge
3. Sentence Usage Evaluator (Scores student's custom sentence out of 10 with constructive feedback)
"""

import os
import sys
import re
import random
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Any

# Stream-tailored technical vocabulary bank
VOCABULARY_BANK: Dict[str, List[Dict[str, Any]]] = {
    "K10": [
        {
            "word": "Photosynthesis",
            "definition": "The biological process by which green plants synthesize nutrients from carbon dioxide and water using sunlight and chlorophyll.",
            "example": "During photosynthesis, plants absorb sunlight and release oxygen into the atmosphere.",
            "context_keywords": ["plant", "sunlight", "chlorophyll", "food", "leaf", "carbon", "oxygen", "energy"],
        },
        {
            "word": "Osmosis",
            "definition": "The movement of solvent molecules through a selectively permeable membrane from a region of lower solute concentration to higher solute concentration.",
            "example": "Plant roots absorb water from the surrounding soil through the process of osmosis.",
            "context_keywords": ["water", "membrane", "solvent", "permeable", "concentration", "cell", "root"],
        },
        {
            "word": "Acceleration",
            "definition": "The rate of change of velocity of an object with respect to time.",
            "example": "When the driver stepped on the pedal, the car experienced rapid acceleration.",
            "context_keywords": ["velocity", "speed", "time", "rate", "motion", "m/s", "change"],
        },
        {
            "word": "Democracy",
            "definition": "A system of government where the citizens exercise power directly or elect representatives from among themselves to form a governing body.",
            "example": "India is the world's largest constitutional democracy with universal adult franchise.",
            "context_keywords": ["government", "people", "vote", "election", "citizen", "rights", "rule"],
        },
    ],
    "MPC": [
        {
            "word": "Trajectory",
            "definition": "The curved path that a projectile or moving object follows through space under the influence of gravity and air resistance.",
            "example": "The artillery shell followed a parabolic trajectory before landing at its target.",
            "context_keywords": ["path", "projectile", "motion", "curve", "gravity", "parabola", "angle", "flight"],
        },
        {
            "word": "Viscosity",
            "definition": "A fluid's internal resistance to gradual deformation by shear or tensile stress; its thickness or friction.",
            "example": "Honey has a much higher viscosity than water at room temperature.",
            "context_keywords": ["fluid", "liquid", "friction", "flow", "resistance", "thickness", "honey", "water"],
        },
        {
            "word": "Electronegativity",
            "definition": "A chemical property describing the tendency of an atom to attract a shared pair of electrons towards itself.",
            "example": "Fluorine is the most electronegative element in the modern periodic table.",
            "context_keywords": ["atom", "electron", "bond", "attract", "periodic", "fluorine", "chemical"],
        },
        {
            "word": "Asymptote",
            "definition": "A line that a curve approaches arbitrarily closely as the coordinates head toward infinity, but never actually crosses.",
            "example": "The hyperbola approaches the x-axis as a horizontal asymptote as x tends to infinity.",
            "context_keywords": ["curve", "line", "infinity", "limit", "graph", "hyperbola", "approach"],
        },
    ],
    "BIPC": [
        {
            "word": "Mitochondria",
            "definition": "Double-membrane-bound cellular organelles that generate most of the chemical energy needed to power the cell's biochemical reactions via ATP.",
            "example": "Mitochondria are known as the cellular powerhouses because they synthesize ATP.",
            "context_keywords": ["cell", "atp", "energy", "powerhouse", "organelle", "respiration", "membrane"],
        },
        {
            "word": "Homeostasis",
            "definition": "The self-regulating biological process by which a living organism maintains internal physiological stability while adjusting to changing external conditions.",
            "example": "The human body maintains thermal homeostasis through sweating and shivering.",
            "context_keywords": ["balance", "stability", "body", "temperature", "internal", "regulate", "organism"],
        },
        {
            "word": "Homozygous",
            "definition": "Having two identical alleles of a particular gene or genes on homologous chromosomes.",
            "example": "A pea plant with genotype TT is homozygous dominant for tallness.",
            "context_keywords": ["gene", "allele", "identical", "chromosome", "genotype", "trait", "mendel"],
        },
        {
            "word": "Phagocytosis",
            "definition": "The cellular process where white blood cells engulf and ingest foreign particles, pathogens, or cellular debris.",
            "example": "Macrophages clear bacterial infections through active phagocytosis.",
            "context_keywords": ["cell", "engulf", "macrophage", "white blood", "pathogen", "bacteria", "immune"],
        },
    ],
    "LAW": [
        {
            "word": "Habeas Corpus",
            "definition": "A prerogative legal writ requiring a person under arrest to be brought before a judge or into court, especially to secure the person's release unless lawful grounds are shown for their detention.",
            "example": "The High Court issued a writ of habeas corpus directing police to produce the detained student.",
            "context_keywords": ["writ", "court", "detention", "arrest", "liberty", "police", "article 32", "illegal"],
        },
        {
            "word": "Mens Rea",
            "definition": "The intention or knowledge of wrongdoing that constitutes part of a crime, as opposed to the action or conduct of the accused.",
            "example": "To establish a conviction for murder under Section 300, the prosecution must prove mens rea beyond reasonable doubt.",
            "context_keywords": ["intent", "mind", "crime", "guilty", "knowledge", "criminal", "prosecution"],
        },
        {
            "word": "Audi Alteram Partem",
            "definition": "The fundamental principle of natural justice stating that no person should be judged or condemned unheard; both sides must be given a fair hearing.",
            "example": "The disciplinary order was set aside because the university violated audi alteram partem by not hearing the candidate.",
            "context_keywords": ["natural justice", "hearing", "both sides", "fair", "listen", "court", "judge"],
        },
        {
            "word": "Ultra Vires",
            "definition": "Acting beyond the scope of legal powers or authority granted by law, statute, or a corporate charter.",
            "example": "The municipal corporation's regulation was struck down as ultra vires the parent municipal act.",
            "context_keywords": ["power", "authority", "beyond", "statute", "illegal", "act", "jurisdiction"],
        },
    ],
    "MBBS": [
        {
            "word": "Myocardial Infarction",
            "definition": "Ischemic necrosis of heart muscle resulting from sudden, prolonged occlusion of a coronary arterial blood supply; commonly known as a heart attack.",
            "example": "The patient presented to the emergency room with severe chest pain indicative of an acute myocardial infarction.",
            "context_keywords": ["heart", "coronary", "ischemia", "chest pain", "artery", "cardiac", "necrosis"],
        },
        {
            "word": "Ischemia",
            "definition": "A condition in which blood flow, and thus oxygen and glucose supply, is restricted or reduced in a specific tissue or organ.",
            "example": "Severe peripheral arterial disease can cause chronic limb ischemia.",
            "context_keywords": ["blood flow", "oxygen", "tissue", "artery", "reduced", "vessel", "organ"],
        },
        {
            "word": "Etiology",
            "definition": "The study or cause of a disease or medical pathological condition.",
            "example": "The physician ordered blood cultures to determine the underlying bacterial etiology of the patient's fever.",
            "context_keywords": ["cause", "disease", "origin", "pathology", "diagnosis", "infection", "factor"],
        },
        {
            "word": "Tachycardia",
            "definition": "An abnormally rapid resting heart rate, typically exceeding 100 beats per minute in an adult.",
            "example": "The ECG confirmed sinus tachycardia with a pulse rate of 125 beats per minute.",
            "context_keywords": ["heart rate", "pulse", "fast", "beats", "bpm", "ecg", "cardiac", "rapid"],
        },
    ],
    "BTECH": [
        {
            "word": "Polymorphism",
            "definition": "The object-oriented programming concept that allows objects of different classes to be treated as objects of a common superclass, typically through method overriding.",
            "example": "By utilizing polymorphism, the graphics engine calls the draw method on any shape subclass without knowing its concrete type.",
            "context_keywords": ["oop", "class", "object", "method", "override", "interface", "code", "inheritance"],
        },
        {
            "word": "Concurrency",
            "definition": "The ability of different parts or units of a program, algorithm, or problem to be executed out-of-order or in partial order, without affecting the final outcome.",
            "example": "Modern web servers use asynchronous concurrency to handle thousands of simultaneous client connections.",
            "context_keywords": ["thread", "parallel", "asynchronous", "simultaneous", "execution", "process", "lock"],
        },
        {
            "word": "Deadlock",
            "definition": "A state in computing where a set of processes are blocked because each process is holding a resource and waiting for another resource acquired by another process.",
            "example": "The operating system resolved the deadlock by terminating the lower-priority thread and releasing its mutex.",
            "context_keywords": ["resource", "thread", "process", "mutex", "lock", "block", "wait", "starvation"],
        },
        {
            "word": "Latency",
            "definition": "The time delay between a stimulus and its response, or the time taken for a packet of data to travel across a network from source to destination.",
            "example": "Deploying edge server caches reduced round-trip network latency from 150ms to under 15ms.",
            "context_keywords": ["time", "delay", "network", "packet", "speed", "response", "millisecond", "ping"],
        },
    ],
}


def get_stream_vocab(stream: str) -> List[Dict[str, Any]]:
    """Returns the vocabulary list matching the user's educational stream."""
    stream_clean = stream.strip().upper()
    if stream_clean in ("MPC", "JEE", "PHYSICS", "CHEMISTRY", "MATH"):
        return VOCABULARY_BANK["MPC"]
    elif stream_clean in ("BIPC", "NEET", "BIOLOGY", "BOTANY", "ZOOLOGY"):
        return VOCABULARY_BANK["BIPC"]
    elif stream_clean in ("LAW", "LLB", "JUDICIARY", "LEGAL"):
        return VOCABULARY_BANK["LAW"]
    elif stream_clean in ("MBBS", "BDS", "MEDICAL", "NURSING", "PHARMACY"):
        return VOCABULARY_BANK["MBBS"]
    elif stream_clean in ("BTECH", "BE", "CS", "CSE", "IT", "MCA"):
        return VOCABULARY_BANK["BTECH"]
    else:
        return VOCABULARY_BANK["K10"]


def generate_vocab_challenge(stream: str = "K10") -> Dict[str, Any]:
    """
    Generates a 4-option multiple-choice vocabulary challenge for the student.
    Returns: Word, Definition, Options, Correct Answer, and Example sentence.
    """
    bank = get_stream_vocab(stream)
    target = random.choice(bank)

    # Gather distractor options from the same stream or global bank
    distractors = [item["word"] for item in bank if item["word"] != target["word"]]
    if len(distractors) < 3:
        all_words = [item["word"] for cat in VOCABULARY_BANK.values() for item in cat if item["word"] != target["word"]]
        distractors.extend(random.sample(all_words, 3 - len(distractors)))

    options = random.sample(distractors, 3) + [target["word"]]
    random.shuffle(options)

    return {
        "challenge_id": f"vocab_{secrets.token_hex(4)}",
        "stream": stream,
        "question": f"Which term matches this definition: \"{target['definition']}\"?",
        "definition": target["definition"],
        "options": options,
        "correct_answer": target["word"],
        "example_usage": target["example"],
    }


def evaluate_sentence_usage(
    word: str,
    student_sentence: str,
    stream: str = "K10",
) -> Dict[str, Any]:
    """
    Evaluates how accurately and naturally a student used a technical word in a sentence.
    Computes a score out of 10 with constructive feedback from Smiley.
    """
    word_clean = word.strip()
    sentence_clean = student_sentence.strip()

    if not sentence_clean:
        return {
            "score": 0,
            "max_score": 10,
            "status": "Incomplete",
            "feedback": "Please type a sentence using the word to receive a performance score!",
        }

    # Find the target word in bank for context keywords
    target_item = None
    for cat in VOCABULARY_BANK.values():
        for item in cat:
            if item["word"].lower() == word_clean.lower():
                target_item = item
                break
        if target_item:
            break

    s_lower = sentence_clean.lower()
    w_lower = word_clean.lower()

    # Criterion 1: Word inclusion (Must be present for credit)
    stem = w_lower[:max(4, len(w_lower) - 2)]
    has_word = (w_lower in s_lower) or (stem in s_lower)
    if not has_word:
        return {
            "word": word_clean,
            "student_sentence": sentence_clean,
            "score": 0,
            "max_score": 10,
            "percentage": 0.0,
            "feedback": f"Smiley noticed you didn't include the word '{word_clean}' in your sentence. Try writing a sentence that features the word directly!",
            "example_solution": target_item["example"] if target_item else f"Example: Understanding {word_clean} is essential in {stream}.",
        }

    # Criterion 2: Sentence structure & length (0 to 4 pts)
    words = sentence_clean.split()
    word_count = len(words)
    if word_count >= 8:
        score_length = 4
    elif word_count >= 5:
        score_length = 3
    elif word_count >= 3:
        score_length = 2
    else:
        score_length = 1

    # Criterion 3: Contextual relevance & depth (0 to 3 pts)
    score_context = 0
    if target_item:
        matches = [kw for kw in target_item.get("context_keywords", []) if kw in s_lower]
        if len(matches) >= 2:
            score_context = 3
        elif len(matches) == 1:
            score_context = 2
        else:
            score_context = 1
    else:
        score_context = 2 if word_count >= 8 else 1

    total_score = min(10, 3 + score_length + score_context)

    # Generate constructive pedagogical feedback from Smiley
    if not has_word:
        feedback = f"Smiley noticed you didn't include the word '{word_clean}' in your sentence. Try writing a sentence that features the word directly!"
    elif total_score >= 9:
        feedback = f"Outstanding vocabulary mastery! You used '{word_clean}' accurately with rich context and clear sentence structure."
    elif total_score >= 7:
        feedback = f"Good sentence! You used '{word_clean}' correctly. Try adding one more detail about why or how it works to earn a full 10/10."
    else:
        feedback = f"Nice attempt! To boost your score, make your sentence a bit longer and explain the meaning of '{word_clean}' in action."

    return {
        "word": word_clean,
        "student_sentence": sentence_clean,
        "score": total_score,
        "max_score": 10,
        "percentage": round((total_score / 10.0) * 100.0, 1),
        "feedback": feedback,
        "example_solution": target_item["example"] if target_item else f"Example: Understanding {word_clean} is essential in {stream}.",
    }
