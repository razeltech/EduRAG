"""
SmileAI Vocabulary Practice & Scoring — Comprehensive Test Suite
Tests stream-based vocabulary lookups, challenge generation, and sentence usage scoring.
"""

import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smileai.vocab import (
    get_stream_vocab,
    generate_vocab_challenge,
    evaluate_sentence_usage,
    VOCABULARY_BANK,
)


class TestSmileAIVocab(unittest.TestCase):

    def test_01_all_stream_banks_populated(self):
        """Verify all streams (K10, MPC, BIPC, LAW, MBBS, BTECH) have technical terms."""
        streams = ["K10", "MPC", "BIPC", "LAW", "MBBS", "BTECH"]
        for s in streams:
            vocab = get_stream_vocab(s)
            self.assertGreaterEqual(len(vocab), 4, f"Stream {s} must have at least 4 terms")
            for item in vocab:
                self.assertIn("word", item)
                self.assertIn("definition", item)
                self.assertIn("example", item)
                self.assertIn("context_keywords", item)
        print("  [PASS] test_01_all_stream_banks_populated")

    def test_02_generate_vocab_challenge(self):
        """Verify challenge generator outputs 4 options, a correct answer, and an example."""
        challenge = generate_vocab_challenge("MPC")
        self.assertEqual(len(challenge["options"]), 4)
        self.assertIn(challenge["correct_answer"], challenge["options"])
        self.assertGreater(len(challenge["definition"]), 10)
        self.assertGreater(len(challenge["example_usage"]), 10)
        print("  [PASS] test_02_generate_vocab_challenge")

    def test_03_evaluate_sentence_usage_high_score(self):
        """Verify high-quality sentence with context keywords gets 9 or 10 points."""
        sentence = "During photosynthesis, green plant leaves absorb sunlight and release oxygen into the atmosphere."
        res = evaluate_sentence_usage("Photosynthesis", sentence, stream="K10")
        self.assertGreaterEqual(res["score"], 9)
        self.assertEqual(res["max_score"], 10)
        self.assertIn("Outstanding", res["feedback"])
        print("  [PASS] test_03_evaluate_sentence_usage_high_score")

    def test_04_evaluate_sentence_usage_missing_word(self):
        """Verify sentence omitting the target word receives constructive coaching."""
        sentence = "The green plants make food in sunlight."
        res = evaluate_sentence_usage("Photosynthesis", sentence, stream="K10")
        self.assertEqual(res["score"], 0)
        self.assertIn("didn't include the word", res["feedback"])
        print("  [PASS] test_04_evaluate_sentence_usage_missing_word")

    def test_05_evaluate_sentence_usage_empty(self):
        """Verify empty sentence returns 0 score without raising exceptions."""
        res = evaluate_sentence_usage("Osmosis", "", stream="K10")
        self.assertEqual(res["score"], 0)
        self.assertEqual(res["status"], "Incomplete")
        print("  [PASS] test_05_evaluate_sentence_usage_empty")

    def test_06_medical_and_law_scoring(self):
        """Verify legal and medical terminology scoring works accurately."""
        # Legal: Habeas Corpus
        law_sentence = "The lawyer filed a writ of habeas corpus in the high court to challenge the illegal detention."
        law_res = evaluate_sentence_usage("Habeas Corpus", law_sentence, stream="LAW")
        self.assertGreaterEqual(law_res["score"], 9)

        # Medical: Myocardial Infarction
        med_sentence = "The patient suffered an acute myocardial infarction due to severe coronary artery blockage."
        med_res = evaluate_sentence_usage("Myocardial Infarction", med_sentence, stream="MBBS")
        self.assertGreaterEqual(med_res["score"], 9)

        print("  [PASS] test_06_medical_and_law_scoring")


if __name__ == "__main__":
    print("\n=======================================================")
    print("  Running SmileAI Vocabulary & Scoring Test Suite      ")
    print("=======================================================")
    runner = unittest.TextTestRunner(verbosity=0)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSmileAIVocab)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("=======================================================")
        print("  ALL 6 TESTS PASSED — ZERO ERRORS OR WARNINGS         ")
        print("=======================================================\n")
        sys.exit(0)
    else:
        print("\n[ERROR] One or more vocabulary tests failed!")
        sys.exit(1)
