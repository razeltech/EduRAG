"""
SmileAI AI Builder Lab — Comprehensive Test Suite (Phase 4)
Tests visual token analysis, 2D vector cosine map, CBSE/NEP competency rubric scoring,
and standalone runnable mini-bot export.
"""

import os
import sys
import unittest
import tempfile
import subprocess
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smileai.builder import (
    analyze_tokens,
    compute_concept_embeddings,
    evaluate_student_bot,
    export_standalone_bot,
)


class TestSmileAIBuilder(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_analyze_tokens(self):
        """Verify token analysis splits text, assigns IDs, and computes compression ratio."""
        text = "Namaste students! Today we learn E = mc^2."
        res = analyze_tokens(text)
        self.assertGreater(res["token_count"], 5)
        self.assertEqual(res["character_count"], len(text))
        self.assertEqual(len(res["tokens"]), len(res["token_ids"]))
        self.assertTrue(all(isinstance(t["token_id"], int) for t in res["tokens"]))

        # Empty string test
        empty_res = analyze_tokens("")
        self.assertEqual(empty_res["token_count"], 0)
        self.assertEqual(empty_res["tokens"], [])
        print("  [PASS] test_01_analyze_tokens")

    def test_02_concept_embeddings_and_cosine_similarity(self):
        """Verify 2D vector space mapping and pairwise cosine similarity calculations."""
        concepts = ["Doctor", "Hospital", "Cricket", "Stadium"]
        res = compute_concept_embeddings(concepts)
        self.assertEqual(len(res["points"]), 4)
        self.assertEqual(len(res["similarity_matrix"]), 4)

        # Doctor and Hospital should be semantically closer than Doctor and Cricket
        # Check matrix row 0 (Doctor)
        doc_hosp_sim = res["similarity_matrix"][0][1]["cosine_similarity"]
        doc_cric_sim = res["similarity_matrix"][0][2]["cosine_similarity"]

        # Doctor and Hospital have positive alignment
        self.assertGreater(doc_hosp_sim, doc_cric_sim)
        print("  [PASS] test_02_concept_embeddings_and_cosine_similarity")

    def test_03_cbse_nep_rubric_scoring_high_score(self):
        """Verify rubric evaluation assigns distinction to well-grounded student bots."""
        notes = (
            "Newton's First Law states that an object remains at rest unless acted upon by an external force.\n\n"
            "Newton's Second Law defines force as F = ma, where m is mass and a is acceleration.\n\n"
            "Newton's Third Law states that for every action, there is an equal and opposite reaction.\n\n"
            "Example: When a bird flaps its wings, it pushes air downward, and the air pushes the bird upward."
        )
        persona = (
            "You are an encouraging high school physics teacher. "
            "Explain concepts clearly in bullet points. "
            "If the answer is not in the provided notes, say: I cannot find that in my notes."
        )

        res = evaluate_student_bot("PhysicsHelper", notes, persona)
        self.assertGreaterEqual(res["total_score"], 85)
        self.assertIn("A+", res["grade"])
        self.assertIn("Brilliant work", res["smiley_mentor_message"])
        self.assertGreater(len(res["praise"]), 2)
        print("  [PASS] test_03_cbse_nep_rubric_scoring_high_score")

    def test_04_cbse_nep_rubric_constructive_coaching(self):
        """Verify rubric offers constructive coaching when notes or safety instructions are missing."""
        brief_notes = "Mitochondria is the powerhouse of the cell."
        weak_persona = "Just answer questions."

        res = evaluate_student_bot("BioBot", brief_notes, weak_persona)
        self.assertLess(res["total_score"], 70)
        self.assertGreater(len(res["suggestions"]), 0)
        # Should gently guide student to add anti-hallucination instruction
        self.assertTrue(any("anti-hallucination" in s.lower() or "notes" in s.lower() for s in res["suggestions"]))
        print("  [PASS] test_04_cbse_nep_rubric_constructive_coaching")

    def test_05_export_standalone_runnable_bot(self):
        """Verify exported mini-bot is syntactically valid and executes offline via Python subprocess."""
        out_script = Path(self.temp_dir.name) / "test_mini_bot.py"
        notes = (
            "The Constitution of India was adopted on 26 November 1949.\n\n"
            "Article 21 guarantees the Protection of Life and Personal Liberty."
        )
        persona = "You are a legal studies tutor."

        bot_path = export_standalone_bot(
            bot_name="LawExamBot",
            author_name="Rohan Verma",
            notes_text=notes,
            persona_prompt=persona,
            output_path=str(out_script),
        )

        self.assertTrue(Path(bot_path).exists())
        self.assertGreater(Path(bot_path).stat().st_size, 1000)

        # Test running the exported Python script with input "Article 21" and then "exit"
        proc = subprocess.Popen(
            [sys.executable, str(out_script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(input="Article 21\nexit\n", timeout=10)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("LawExamBot Answer", stdout)
        self.assertIn("Protection of Life and Personal Liberty", stdout)
        self.assertIn("Source Citation", stdout)
        print("  [PASS] test_05_export_standalone_runnable_bot")


if __name__ == "__main__":
    print("\n=======================================================")
    print("  Running SmileAI AI Builder Lab Test Suite (Phase 4)  ")
    print("=======================================================")
    runner = unittest.TextTestRunner(verbosity=0)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSmileAIBuilder)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("=======================================================")
        print("  ALL 5 TESTS PASSED — ZERO ERRORS OR WARNINGS         ")
        print("=======================================================\n")
        sys.exit(0)
    else:
        print("\n[ERROR] One or more test cases failed!")
        sys.exit(1)
