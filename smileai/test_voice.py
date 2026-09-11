"""
SmileAI Voice Engine — Comprehensive Test Suite & Edge Case Verification
Tests error handling, edge cases, input normalization, and audio integrity.
"""

import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smileai.voice_engine import (
    clean_text_for_speech,
    synthesize_speech,
    synthesize_to_file,
    get_voice_catalog,
    DEFAULT_VOICE_ID,
    VOICE_CATALOG,
)


class TestSmileAIVoiceEngine(unittest.TestCase):

    def test_01_text_cleaner_markdown_and_citations(self):
        """Verify markdown, citations, and brackets are cleanly removed."""
        raw_text = (
            "### Chapter 4: Motion in a Plane\n\n"
            "According to **Newton's Laws** of Motion [Doc 1, p. 45], "
            "the acceleration is `a = F / m`. Also see [Ref: NCERT p. 12]."
        )
        cleaned = clean_text_for_speech(raw_text)
        self.assertNotIn("###", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("`", cleaned)
        self.assertNotIn("[Doc 1, p. 45]", cleaned)
        self.assertNotIn("[Ref: NCERT p. 12]", cleaned)
        self.assertIn("Newton's Laws", cleaned)
        print("  [PASS] test_01_text_cleaner_markdown_and_citations")

    def test_02_text_cleaner_math_symbols(self):
        """Verify educational math notation is transliterated to spoken English."""
        math_text = "The formula is \\pi r^2 and \\Delta x \\approx 5 \\times 10."
        cleaned = clean_text_for_speech(math_text)
        self.assertIn("pie", cleaned.lower())
        self.assertIn("delta", cleaned.lower())
        self.assertIn("approximately", cleaned.lower())
        self.assertIn("times", cleaned.lower())
        print("  [PASS] test_02_text_cleaner_math_symbols")

    def test_03_empty_and_whitespace_inputs(self):
        """Verify empty and whitespace inputs return empty bytes without raising exceptions."""
        res_empty = synthesize_speech("")
        self.assertEqual(res_empty, b"")

        res_spaces = synthesize_speech("     \n\t   ")
        self.assertEqual(res_spaces, b"")
        print("  [PASS] test_03_empty_and_whitespace_inputs")

    def test_04_unknown_voice_fallback(self):
        """Verify requesting an unknown or invalid voice ID falls back safely to Aarti."""
        audio_bytes = synthesize_speech("Testing voice fallback.", voice_id="nonexistent-voice-999")
        self.assertGreater(len(audio_bytes), 1000)
        # Check MP3 magic header (either 'ID3' tag or 0xFF sync frame)
        is_valid_mp3 = audio_bytes.startswith(b"ID3") or (audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0)
        self.assertTrue(is_valid_mp3, "Generated audio must be a valid MP3 stream")
        print("  [PASS] test_04_unknown_voice_fallback")

    def test_05_curated_voice_catalog(self):
        """Verify the voice catalog contains Aarti (default), Shruti, Swara, and Prabhat."""
        catalog = get_voice_catalog()
        self.assertGreaterEqual(len(catalog), 4)

        voice_ids = [v["id"] for v in catalog]
        self.assertIn("en-IN-NeerjaExpressiveNeural", voice_ids)
        self.assertIn("te-IN-ShrutiNeural", voice_ids)
        self.assertIn("hi-IN-SwaraNeural", voice_ids)
        self.assertIn("en-IN-PrabhatNeural", voice_ids)

        # Check default voice
        default_voices = [v for v in catalog if v.get("default")]
        self.assertEqual(len(default_voices), 1)
        self.assertEqual(default_voices[0]["id"], "en-IN-NeerjaExpressiveNeural")
        print("  [PASS] test_05_curated_voice_catalog")

    def test_06_synthesis_to_file(self):
        """Verify synthesizing speech directly to a file creates valid output on disk."""
        out_path = Path(__file__).resolve().parent / "test_output.mp3"
        if out_path.exists():
            out_path.unlink()

        result = synthesize_to_file("This is a verified test of Smiley's speech engine.", str(out_path))
        self.assertTrue(out_path.exists())
        self.assertGreater(out_path.stat().st_size, 5000)

        # Cleanup test file
        out_path.unlink()
        print("  [PASS] test_06_synthesis_to_file")

    def test_07_special_educational_characters(self):
        """Verify chemistry, physics, and currency symbols don't crash the engine."""
        chem_physics_text = "Water is H2O, carbon dioxide is CO2, and velocity is 25 m/s at 30 degrees celsius."
        audio_bytes = synthesize_speech(chem_physics_text)
        self.assertGreater(len(audio_bytes), 2000)
        print("  [PASS] test_07_special_educational_characters")


if __name__ == "__main__":
    print("\n=======================================================")
    print("  Running SmileAI Voice Engine Test Suite (Phase 1)    ")
    print("=======================================================")
    runner = unittest.TextTestRunner(verbosity=0)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSmileAIVoiceEngine)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("=======================================================")
        print("  ALL 7 TESTS PASSED — ZERO ERRORS OR WARNINGS         ")
        print("=======================================================\n")
        sys.exit(0)
    else:
        print("\n[ERROR] One or more test cases failed!")
        sys.exit(1)
