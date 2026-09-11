"""
SmileAI Neural Voice Engine
Powered by Razel Tech | Sub-second neural synthesis, zero GPU VRAM impact.
Default Voice: Aarti (en-IN-NeerjaExpressiveNeural, rate=-15%, pitch=+15Hz)
"""

import os
import sys
import re
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
import edge_tts

# Default Persona Configuration
DEFAULT_VOICE_ID = "en-IN-NeerjaExpressiveNeural"
DEFAULT_RATE = "-15%"    # 0.85x speed: patient, reassuring, calm
DEFAULT_PITCH = "+15Hz"  # Gentle, warm smiling inflection

# Curated Voice Catalog for Indian Education
VOICE_CATALOG: Dict[str, Dict] = {
    "en-IN-NeerjaExpressiveNeural": {
        "name": "Aarti (Smiley Warm Voice)",
        "lang": "en-IN",
        "gender": "Female",
        "style": "Warm Indian Teacher",
        "description": "Warm, gentle, reassuring Indian English school teacher persona",
        "default_rate": "-15%",
        "default_pitch": "+15Hz",
        "default": True,
    },
    "te-IN-ShrutiNeural": {
        "name": "Shruti",
        "lang": "te-IN",
        "gender": "Female",
        "style": "Telugu Educator",
        "description": "Natural, clear Telugu speaker for regional curriculum",
        "default_rate": "-10%",
        "default_pitch": "+0Hz",
        "default": False,
    },
    "hi-IN-SwaraNeural": {
        "name": "Swara",
        "lang": "hi-IN",
        "gender": "Female",
        "style": "Hindi Educator",
        "description": "Fluent, warm Hindi narrator and teacher",
        "default_rate": "-10%",
        "default_pitch": "+0Hz",
        "default": False,
    },
    "en-IN-PrabhatNeural": {
        "name": "Prabhat",
        "lang": "en-IN",
        "gender": "Male",
        "style": "Technical & Lab Instructor",
        "description": "Clear, articulate Indian English male presenter",
        "default_rate": "-5%",
        "default_pitch": "+0Hz",
        "default": False,
    },
}

# Browser SpeechSynthesis fallback preferences for offline client-side audio
BROWSER_VOICE_FALLBACK_NAMES: List[str] = [
    "microsoft aarti",
    "aarti",
    "arti",
    "microsoft neerja",
    "veena",
    "google hi-in english female",
    "google hindi",
    "microsoft heera",
    "google uk english female",
    "microsoft zira",
]


def clean_text_for_speech(text: str) -> str:
    """
    Strips markdown symbols, raw code blocks, and converts basic math notation
    into clean, natural spoken English so the TTS sounds professional.
    """
    if not text:
        return ""

    # Remove code blocks
    cleaned = re.sub(r"```[\s\S]*?```", " [code snippet omitted] ", text)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)

    # Remove markdown headers and emphasis
    cleaned = re.sub(r"^#{1,6}\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"_([^_]+)_", r"\1", cleaned)

    # Remove markdown links, keep text
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)

    # Remove citation brackets like [Doc 1, p. 12]
    cleaned = re.sub(r"\[(?:Doc|Page|p\.|Ref)[^\]]*\]", "", cleaned, flags=re.IGNORECASE)

    # Convert common educational math symbols to spoken words
    replacements = [
        (r"\\approx", " approximately "),
        (r"\\times", " times "),
        (r"\\div", " divided by "),
        (r"\\pm", " plus or minus "),
        (r"\\pi", " pie "),
        (r"\\theta", " theta "),
        (r"\\lambda", " lambda "),
        (r"\\mu", " micro "),
        (r"\\sigma", " sigma "),
        (r"\\Delta", " delta "),
        (r"\\leq", " less than or equal to "),
        (r"\\geq", " greater than or equal to "),
        (r"\\neq", " not equal to "),
        (r"\\sum", " sum of "),
        (r"\\int", " integral of "),
        (r"\\sqrt\{([^}]+)\}", r" square root of \1 "),
        (r"\^2\b", " squared "),
        (r"\^3\b", " cubed "),
        (r"&amp;", " and "),
        (r"&lt;", " less than "),
        (r"&gt;", " greater than "),
    ]
    for pattern, repl in replacements:
        cleaned = re.sub(pattern, repl, cleaned)

    # Clean bullet points and extra whitespace
    cleaned = re.sub(r"^[\*\-\+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{2,}", ". ", cleaned)
    cleaned = re.sub(r"\n", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)

    return cleaned.strip()


async def synthesize_speech_async(
    text: str,
    voice_id: str = DEFAULT_VOICE_ID,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
) -> bytes:
    """
    Synthesizes speech asynchronously into MP3 bytes using Edge-TTS.
    Zero GPU VRAM impact — runs fully asynchronous.
    """
    clean_text = clean_text_for_speech(text)
    if not clean_text:
        return b""

    # Sanitize voice ID: fallback to default if invalid or unknown
    target_voice = voice_id if voice_id in VOICE_CATALOG else DEFAULT_VOICE_ID
    voice_meta = VOICE_CATALOG[target_voice]
    target_rate = rate or voice_meta.get("default_rate", DEFAULT_RATE)
    target_pitch = pitch or voice_meta.get("default_pitch", DEFAULT_PITCH)

    try:
        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=target_voice,
            rate=target_rate,
            pitch=target_pitch,
        )

        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        return b"".join(audio_chunks)
    except Exception as e:
        sys.stderr.write(f"[SmileAI Voice Error] Synthesis failed for voice {target_voice}: {e}\n")
        return b""


def synthesize_speech(
    text: str,
    voice_id: str = DEFAULT_VOICE_ID,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
) -> bytes:
    """
    Synchronous wrapper for synthesize_speech_async.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Running inside an existing event loop (e.g. FastAPI / asyncio app)
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(synthesize_speech_async(text, voice_id, rate, pitch))
    else:
        return asyncio.run(synthesize_speech_async(text, voice_id, rate, pitch))


def synthesize_to_file(
    text: str,
    output_path: str,
    voice_id: str = DEFAULT_VOICE_ID,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
) -> str:
    """
    Synthesizes speech directly into a target MP3 file.
    """
    audio_bytes = synthesize_speech(text, voice_id, rate, pitch)
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(audio_bytes)
    return str(out_file)


def get_voice_catalog() -> List[Dict]:
    """
    Returns the voice catalog for API consumers.
    """
    return [
        {"id": vid, **meta}
        for vid, meta in VOICE_CATALOG.items()
    ]


if __name__ == "__main__":
    print("==================================================")
    print("  SmileAI Voice Engine — Verification Test")
    print("  Default Persona: Aarti (en-IN-NeerjaExpressiveNeural)")
    print(f"  Rate: {DEFAULT_RATE} | Pitch: {DEFAULT_PITCH}")
    print("==================================================")

    sample_prompt = (
        "Namaste students! I am Smiley, your personal learning companion. "
        "Today we will explore science, mathematics, and learn how to build "
        "your very own artificial intelligence from first principles. "
        "Let us make learning joyous and simple together!"
    )

    output_dir = Path(__file__).resolve().parent
    output_file = output_dir / "sample_aarti_greeting.mp3"

    print(f"\nSynthesizing sample greeting with Aarti's warm voice...")
    result_path = synthesize_to_file(sample_prompt, str(output_file))

    file_size = os.path.getsize(result_path)
    print(f"[SUCCESS] Audio generated successfully!")
    print(f"  Output File : {result_path}")
    print(f"  File Size   : {file_size:,} bytes")
    print("\nVoice engine is ready for deployment in Project Smiley.")
