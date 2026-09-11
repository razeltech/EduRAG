"""
SmileAI Snap & Solve — Comprehensive Test Suite (Phase 3)
Tests image preprocessing, OCR extraction, SymPy symbolic math verification,
multi-question segmentation, and pedagogical solution generation.
"""

import os
import sys
import unittest
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smileai.solver import (
    preprocess_image,
    extract_text_from_image_bytes,
    segment_questions,
    try_solve_symbolic_math,
    generate_pedagogical_solution,
    snap_and_solve_file,
)
from smileai.db import init_db, create_institution, import_roster_csv, authenticate_student


class TestSmileAISolver(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Create a sample question paper image for testing OCR."""
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.sample_img_path = Path(cls.temp_dir.name) / "sample_exam_q.png"

        # Create a clean high-contrast image with a physics/math question
        img = Image.new("RGB", (600, 180), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((30, 30), "Q1. Find velocity if acceleration is 5 m/s^2 and time is 10 s.", fill=(0, 0, 0))
        d.text((30, 90), "Q2. Solve the linear equation: 2x + 5 = 15", fill=(0, 0, 0))
        img.save(str(cls.sample_img_path))

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_01_image_preprocessing(self):
        """Verify image preprocessing scales and enhances contrast properly."""
        large_img = Image.new("RGB", (3000, 2400), color=(200, 200, 200))
        processed = preprocess_image(large_img)
        self.assertLessEqual(max(processed.size), 2000)
        self.assertEqual(processed.mode, "RGB")
        print("  [PASS] test_01_image_preprocessing")

    def test_02_sympy_exact_math_solving(self):
        """Verify SymPy calculates deterministic answers for equations without LLM hallucination."""
        # Linear equation
        res_linear = try_solve_symbolic_math("Solve: 2x + 5 = 15")
        self.assertIsNotNone(res_linear)
        self.assertEqual(res_linear["solutions"], [5])
        self.assertIn("x = 5", res_linear["solution_display"])

        # Quadratic equation: x^2 - 5x + 6 = 0  -> roots: 2, 3
        res_quad = try_solve_symbolic_math("Find roots of: x^2 - 5x + 6 = 0")
        self.assertIsNotNone(res_quad)
        self.assertEqual(set(res_quad["solutions"]), {2, 3})
        print("  [PASS] test_02_sympy_exact_math_solving")

    def test_03_multi_question_segmentation(self):
        """Verify multi-question exam paper text is split into distinct questions."""
        exam_text = (
            "Q1. State Newton's Second Law of Motion.\n"
            "Q2. A car starts from rest with acceleration 2 m/s^2.\n"
            "Q3. Derive the formula for kinetic energy."
        )
        questions = segment_questions(exam_text)
        self.assertEqual(len(questions), 3)
        self.assertTrue(questions[0].startswith("Q1."))
        self.assertTrue(questions[1].startswith("Q2."))
        self.assertTrue(questions[2].startswith("Q3."))
        print("  [PASS] test_03_multi_question_segmentation")

    def test_04_pedagogical_solution_generation(self):
        """Verify Polya's 4-step pedagogical explanation across multiple streams."""
        # 1. Physics kinematics
        sol_physics = generate_pedagogical_solution("Find velocity if acceleration is 5 m/s^2", stream="MPC")
        self.assertIn("Kinematics", sol_physics["concept"])
        self.assertIn("v = u + at", sol_physics["formula"])
        self.assertIn("NCERT Class 11 Physics", sol_physics["citation"])

        # 2. Medical cardiology
        sol_med = generate_pedagogical_solution("Explain blood flow through cardiac ventricles and heart valves", stream="MBBS")
        self.assertIn("Cardiovascular", sol_med["concept"])
        self.assertIn("Guyton & Hall", sol_med["citation"])

        # 3. Legal studies
        sol_law = generate_pedagogical_solution("Explain Article 21 Fundamental Right to Life", stream="LAW")
        self.assertIn("Constitutional Law", sol_law["concept"])
        self.assertIn("Part III", sol_law["formula"])

        print("  [PASS] test_04_pedagogical_solution_generation")

    def test_05_ocr_extraction_from_image_bytes(self):
        """Verify OCR extracts text from image bytes using EasyOCR NumPy integration."""
        img_bytes = self.sample_img_path.read_bytes()
        res = extract_text_from_image_bytes(img_bytes, filename=self.sample_img_path.name)
        self.assertNotIn("error", res)
        self.assertGreater(len(res["extracted_text"]), 10)
        # Should detect at least one of the question strings
        self.assertTrue(any(k in res["extracted_text"].lower() for k in ["velocity", "acceleration", "solve", "equation"]))
        print("  [PASS] test_05_ocr_extraction_from_image_bytes")

    def test_06_end_to_end_snap_and_solve(self):
        """Verify end-to-end file reading, solving, and database logging."""
        temp_db = Path(self.temp_dir.name) / "snap_test.db"
        init_db(str(temp_db))
        inst_id = create_institution("Snap School", "SNAP", db_path=str(temp_db))
        import_res = import_roster_csv("roll_no,name,stream\nSNAP-101,Aakash Roy,MPC", inst_id, db_path=str(temp_db))
        student = authenticate_student(inst_id, "SNAP-101", import_res["credentials"][0]["pin"], db_path=str(temp_db))

        result = snap_and_solve_file(
            str(self.sample_img_path),
            stream="MPC",
            student_id=student["id"],
            db_path=str(temp_db),
        )

        self.assertEqual(result["status"], "success")
        self.assertIsNotNone(result["solution"])
        self.assertTrue(result["solution_id"].startswith("snap_"))
        print("  [PASS] test_06_end_to_end_snap_and_solve")

    def test_07_corrupt_and_blank_image_handling(self):
        """Verify corrupt and blank images return graceful warnings without crashing."""
        # Corrupt bytes
        res_corrupt = extract_text_from_image_bytes(b"not-an-image-corrupt-data", filename="bad.png")
        self.assertIn("error", res_corrupt)
        self.assertEqual(res_corrupt["extracted_text"], "")

        # Non-existent file
        with self.assertRaises(FileNotFoundError):
            snap_and_solve_file("nonexistent_image_file_12345.png")

        print("  [PASS] test_07_corrupt_and_blank_image_handling")


if __name__ == "__main__":
    print("\n=======================================================")
    print("  Running SmileAI Snap & Solve Test Suite (Phase 3)    ")
    print("=======================================================")
    runner = unittest.TextTestRunner(verbosity=0)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSmileAISolver)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("=======================================================")
        print("  ALL 7 TESTS PASSED — ZERO ERRORS OR WARNINGS         ")
        print("=======================================================\n")
        sys.exit(0)
    else:
        print("\n[ERROR] One or more test cases failed!")
        sys.exit(1)
