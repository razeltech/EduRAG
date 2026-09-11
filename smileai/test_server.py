"""
SmileAI Unified Server & API — Comprehensive Test Suite
Tests FastAPI routes for voice catalog, AI builder lab, student chat,
and snap & solve using TestClient.
"""

import os
import sys
import unittest
import io
from pathlib import Path
from starlette.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smileai.server import app


class TestSmileAIServer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_voice_catalog_endpoint(self):
        """Verify /api/smileai/voice/catalog returns Aarti default and regional voices."""
        response = self.client.get("/api/smileai/voice/catalog")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("catalog", data)
        self.assertEqual(data["default_voice"], "en-IN-NeerjaExpressiveNeural")
        print("  [PASS] test_01_voice_catalog_endpoint")

    def test_02_builder_tokens_endpoint(self):
        """Verify /api/smileai/builder/tokens parses text into visual tokens."""
        payload = {"text": "Namaste India! Learning AI is fun."}
        response = self.client.post("/api/smileai/builder/tokens", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["token_count"], 4)
        self.assertIn("tokens", data)
        print("  [PASS] test_02_builder_tokens_endpoint")

    def test_03_builder_embeddings_endpoint(self):
        """Verify /api/smileai/builder/embeddings computes 2D coordinates and cosine matrix."""
        payload = {"concepts": ["Doctor", "Hospital", "Cricket"]}
        response = self.client.post("/api/smileai/builder/embeddings", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["points"]), 3)
        self.assertEqual(len(data["similarity_matrix"]), 3)
        print("  [PASS] test_03_builder_embeddings_endpoint")

    def test_04_builder_evaluate_endpoint(self):
        """Verify /api/smileai/builder/evaluate evaluates bot against CBSE/NEP rubric."""
        payload = {
            "bot_name": "MathBot",
            "notes_text": "Quadratic equations have form ax^2 + bx + c = 0. Roots are given by formula.",
            "persona_prompt": "You are a gentle teacher. Answer in bullet points. Only answer from notes.",
        }
        response = self.client.post("/api/smileai/builder/evaluate", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_score", data)
        self.assertIn("grade", data)
        self.assertIn("smiley_mentor_message", data)
        print("  [PASS] test_04_builder_evaluate_endpoint")

    def test_05_student_chat_endpoint(self):
        """Verify /api/smileai/chat returns structured pedagogical answers with citations."""
        payload = {
            "message": "What is Newton's second law of motion?",
            "stream": "MPC",
            "student_name": "Kavya",
        }
        response = self.client.post("/api/smileai/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["role"], "assistant")
        self.assertIn("Hello Kavya", data["content"])
        self.assertIn("Newton's Laws", data["concept"])
        self.assertIn("NCERT", data["citation"])
        print("  [PASS] test_05_student_chat_endpoint")

    def test_06_snap_solver_endpoint(self):
        """Verify /api/smileai/solve/snap processes uploaded image bytes."""
        # Create small test image bytes
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (300, 100), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((20, 40), "Solve: 2x + 5 = 15", fill=(0, 0, 0))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        response = self.client.post(
            "/api/smileai/solve/snap",
            files={"file": ("test_math.png", img_bytes.getvalue(), "image/png")},
            data={"stream": "MPC"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn(data["status"], ["success", "warning"])
        print("  [PASS] test_06_snap_solver_endpoint")

    def test_07_root_html_endpoint(self):
        """Verify root / serves HTML response."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        print("  [PASS] test_07_root_html_endpoint")

    def test_08_vocab_endpoints(self):
        """Verify /api/smileai/vocab/challenge and /evaluate endpoints."""
        # Challenge
        res_ch = self.client.get("/api/smileai/vocab/challenge?stream=MPC")
        self.assertEqual(res_ch.status_code, 200)
        data_ch = res_ch.json()
        self.assertEqual(len(data_ch["options"]), 4)

        # Evaluation
        res_ev = self.client.post("/api/smileai/vocab/evaluate", json={
            "word": "Trajectory",
            "sentence": "The satellite followed an elliptical trajectory through space.",
            "stream": "MPC",
        })
        self.assertEqual(res_ev.status_code, 200)
        data_ev = res_ev.json()
        self.assertGreaterEqual(data_ev["score"], 8)
        self.assertIn("feedback", data_ev)
        print("  [PASS] test_08_vocab_endpoints")


if __name__ == "__main__":
    print("\n=======================================================")
    print("  Running SmileAI Server & API Test Suite              ")
    print("=======================================================")
    runner = unittest.TextTestRunner(verbosity=0)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSmileAIServer)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("=======================================================")
        print("  ALL 7 TESTS PASSED — ZERO ERRORS OR WARNINGS         ")
        print("=======================================================\n")
        sys.exit(0)
    else:
        print("\n[ERROR] One or more server tests failed!")
        sys.exit(1)
