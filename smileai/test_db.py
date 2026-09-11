"""
SmileAI Database & Roster Manager — Comprehensive Test Suite (Phase 2)
Tests schema integrity, flexible CSV roster importing, PIN hashing/verification,
assessment grading, and ERP CSV export with zero errors.
"""

import os
import sys
import unittest
import tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smileai.db import (
    init_db,
    create_institution,
    create_stream,
    get_or_create_batch,
    import_roster_csv,
    authenticate_student,
    save_assessment,
    submit_assessment,
    export_gradebook_csv,
    hash_pin,
    verify_pin,
)


class TestSmileAIDatabase(unittest.TestCase):

    def setUp(self):
        """Create a fresh isolated temporary SQLite database for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db = str(Path(self.temp_dir.name) / "test_smileai.db")
        init_db(self.test_db)

    def tearDown(self):
        """Clean up the temporary database."""
        self.temp_dir.cleanup()

    def test_01_pin_hashing_and_verification(self):
        """Verify 4-digit PIN cryptographic hashing and verification."""
        pin = "4912"
        h, salt = hash_pin(pin)
        self.assertTrue(verify_pin("4912", h, salt))
        self.assertFalse(verify_pin("0000", h, salt))
        self.assertFalse(verify_pin("4913", h, salt))
        print("  [PASS] test_01_pin_hashing_and_verification")

    def test_02_institution_and_stream_creation(self):
        """Verify dynamic institution and multi-stream creation."""
        inst_id = create_institution(
            name="Delhi Public School & Junior College",
            code="DPSJC",
            board_type="CBSE",
            contact_email="principal@dpsjc.edu.in",
            db_path=self.test_db,
        )
        self.assertTrue(inst_id.startswith("inst_"))

        # Create streams for intermediate & professional
        mpc_id = create_stream(inst_id, "MPC", "Intermediate Mathematics, Physics, Chemistry (JEE)", "intermediate", db_path=self.test_db)
        bipc_id = create_stream(inst_id, "BIPC", "Intermediate Biology, Physics, Chemistry (NEET)", "intermediate", db_path=self.test_db)
        btech_id = create_stream(inst_id, "BTECH-CSE", "B.Tech Computer Science & AI", "higher_ed", db_path=self.test_db)

        self.assertTrue(mpc_id.startswith("stream_"))
        self.assertTrue(bipc_id.startswith("stream_"))
        self.assertTrue(btech_id.startswith("stream_"))
        print("  [PASS] test_02_institution_and_stream_creation")

    def test_03_flexible_csv_roster_import(self):
        """Verify importing a multi-stream student roster CSV with various column headers."""
        inst_id = create_institution("Narayana Educational Institute", "NARAYANA", "State Board", db_path=self.test_db)

        # Sample CSV with varied case and column names
        sample_csv = """Roll Number,Student Name,Stream,Class,Section,Phone
AP-2026-101,Rahul Sharma,MPC,11,A,9876543210
AP-2026-102,Priya Venkatesh,BIPC,11,A,9876543211
AP-2026-103,Mohammed Faiz,CEC,11,B,9876543212
AP-2026-104,Ananya Reddy,NEET,12,Batch-1,9876543213
AP-2026-105,Siddharth Verma,BTECH,1st Year,CSE-A,9876543214
"""
        result = import_roster_csv(sample_csv, inst_id, db_path=self.test_db)
        self.assertEqual(result["imported"], 5)
        self.assertEqual(len(result["errors"]), 0)
        self.assertEqual(len(result["credentials"]), 5)

        # Verify credential structure
        for cred in result["credentials"]:
            self.assertIn("roll_no", cred)
            self.assertIn("pin", cred)
            self.assertEqual(len(cred["pin"]), 4)  # Must be 4-digit PIN
            self.assertTrue(cred["pin"].isdigit())

        print("  [PASS] test_03_flexible_csv_roster_import")

    def test_04_student_authentication(self):
        """Verify student login via roll number and 4-digit PIN."""
        inst_id = create_institution("Sri Chaitanya College", "SRICHAI", "State Board", db_path=self.test_db)
        csv_data = "roll_no,name,stream,class_grade,section\nSC-501,Kavya Nair,BIPC,12,A"
        import_res = import_roster_csv(csv_data, inst_id, db_path=self.test_db)
        student_cred = import_res["credentials"][0]

        # Valid login
        student = authenticate_student(inst_id, "SC-501", student_cred["pin"], db_path=self.test_db)
        self.assertIsNotNone(student)
        self.assertEqual(student["name"], "Kavya Nair")
        self.assertEqual(student["stream"], "BIPC")

        # Invalid PIN
        bad_login = authenticate_student(inst_id, "SC-501", "0000", db_path=self.test_db)
        self.assertIsNone(bad_login)

        # Invalid Roll No
        ghost_login = authenticate_student(inst_id, "SC-999", student_cred["pin"], db_path=self.test_db)
        self.assertIsNone(ghost_login)

        print("  [PASS] test_04_student_authentication")

    def test_05_assessment_creation_and_grading(self):
        """Verify assessment saving, student submission evaluation, and scoring."""
        inst_id = create_institution("Osmania University", "OU", "University", db_path=self.test_db)
        stream_id = create_stream(inst_id, "LAW", "LLB Constitutional Law", db_path=self.test_db)

        # Import a student
        csv_data = "roll_no,name,stream\nOU-LAW-01,Vikram Rao,LAW"
        res = import_roster_csv(csv_data, inst_id, db_path=self.test_db)
        student_id = authenticate_student(inst_id, "OU-LAW-01", res["credentials"][0]["pin"], db_path=self.test_db)["id"]

        # Save an assessment
        questions = [
            {
                "id": 1,
                "question": "Which article of the Indian Constitution guarantees the Right to Life?",
                "options": ["Article 14", "Article 19", "Article 21", "Article 32"],
                "correct_answer": "Article 21",
                "explanation": "Article 21 guarantees protection of life and personal liberty.",
            },
            {
                "id": 2,
                "question": "Who is known as the Chief Architect of the Constitution of India?",
                "options": ["Mahatma Gandhi", "Dr. B.R. Ambedkar", "Jawaharlal Nehru", "Sardar Patel"],
                "correct_answer": "Dr. B.R. Ambedkar",
                "explanation": "Dr. B.R. Ambedkar was the Chairman of the Drafting Committee.",
            }
        ]

        assess_id = save_assessment(
            inst_id, stream_id,
            title="Constitutional Law Quiz 1",
            topic="Fundamental Rights",
            difficulty="medium",
            questions=questions,
            db_path=self.test_db,
        )

        # Student takes test: 1 correct, 1 wrong
        answers = {
            "1": "Article 21",              # Correct
            "2": "Mahatma Gandhi",          # Incorrect
        }

        eval_result = submit_assessment(assess_id, student_id, answers, db_path=self.test_db)
        self.assertEqual(eval_result["score"], 1.0)
        self.assertEqual(eval_result["total_marks"], 2.0)
        self.assertEqual(eval_result["mastery_percentage"], 50.0)
        self.assertTrue(eval_result["feedback"][0]["is_correct"])
        self.assertFalse(eval_result["feedback"][1]["is_correct"])

        print("  [PASS] test_05_assessment_creation_and_grading")

    def test_06_erp_gradebook_csv_export(self):
        """Verify exporting student grades to CSV formatted for school management software."""
        inst_id = create_institution("IIT Hyderabad Prep", "IITHP", "CBSE", db_path=self.test_db)
        stream_id = create_stream(inst_id, "MPC", "JEE Advanced Physics", db_path=self.test_db)

        # Import 2 students
        csv_data = "roll_no,name,stream,class_grade,section\nJEE-101,Aarav Gupta,MPC,12,A\nJEE-102,Diya Sen,MPC,12,A"
        import_res = import_roster_csv(csv_data, inst_id, db_path=self.test_db)

        stu1_id = authenticate_student(inst_id, "JEE-101", import_res["credentials"][0]["pin"], db_path=self.test_db)["id"]
        stu2_id = authenticate_student(inst_id, "JEE-102", import_res["credentials"][1]["pin"], db_path=self.test_db)["id"]

        questions = [
            {"id": 1, "question": "Unit of force?", "correct_answer": "Newton"}
        ]
        assess_id = save_assessment(inst_id, stream_id, "Physics Units", "Mechanics", "easy", questions, db_path=self.test_db)

        submit_assessment(assess_id, stu1_id, {"1": "Newton"}, db_path=self.test_db)
        submit_assessment(assess_id, stu2_id, {"1": "Joule"}, db_path=self.test_db)

        # Export CSV
        csv_out = export_gradebook_csv(inst_id, db_path=self.test_db)
        self.assertIn("Roll Number,Student Name,Stream", csv_out)
        self.assertIn("JEE-101,Aarav Gupta,MPC,12,A,Physics Units,Mechanics,1.0,1.0,100.0", csv_out)
        self.assertIn("JEE-102,Diya Sen,MPC,12,A,Physics Units,Mechanics,0.0,1.0,0.0", csv_out)

        print("  [PASS] test_06_erp_gradebook_csv_export")

    def test_07_empty_and_malformed_csv_handling(self):
        """Verify error handling on empty or invalid CSV files."""
        inst_id = create_institution("Test School", "TEST", db_path=self.test_db)

        # Empty CSV
        res_empty = import_roster_csv("", inst_id, db_path=self.test_db)
        self.assertEqual(res_empty["imported"], 0)
        self.assertGreater(len(res_empty["errors"]), 0)

        # CSV missing roll_no
        res_bad = import_roster_csv("name,stream\nJohn Doe,MPC", inst_id, db_path=self.test_db)
        self.assertEqual(res_bad["imported"], 0)
        self.assertIn("roll_no", res_bad["errors"][0])

        print("  [PASS] test_07_empty_and_malformed_csv_handling")


if __name__ == "__main__":
    print("\n=======================================================")
    print("  Running SmileAI Database & Roster Suite (Phase 2)    ")
    print("=======================================================")
    runner = unittest.TextTestRunner(verbosity=0)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSmileAIDatabase)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("=======================================================")
        print("  ALL 7 TESTS PASSED — ZERO ERRORS OR WARNINGS         ")
        print("=======================================================\n")
        sys.exit(0)
    else:
        print("\n[ERROR] One or more test cases failed!")
        sys.exit(1)
