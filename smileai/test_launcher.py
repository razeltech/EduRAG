"""
SmileAI Desktop Launcher — Verification Test Suite (Phase 6)
Tests LAN IP detection, hardware metrics, background server lifecycle, and clean shutdown.
"""

import os
import sys
import time
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smileai.launcher import (
    get_local_ip,
    get_system_metrics,
    start_server_process,
    stop_server_process,
    DEFAULT_PORT,
)


class TestSmileAILauncher(unittest.TestCase):

    def test_01_local_ip_detection(self):
        """Verify LAN IP detection returns a valid IPv4 string."""
        ip = get_local_ip()
        self.assertTrue(isinstance(ip, str))
        self.assertGreater(len(ip), 6)
        parts = ip.split(".")
        self.assertEqual(len(parts), 4)
        print(f"  [PASS] test_01_local_ip_detection: Detected LAN IP {ip}")

    def test_02_system_metrics(self):
        """Verify hardware metrics returns valid CPU and RAM statistics."""
        metrics = get_system_metrics()
        self.assertIn("cpu_percent", metrics)
        self.assertIn("ram_used_gb", metrics)
        self.assertIn("ram_total_gb", metrics)
        self.assertGreater(metrics["ram_total_gb"], 0)
        print(f"  [PASS] test_02_system_metrics: CPU {metrics['cpu_percent']}% | RAM {metrics['ram_used_gb']}GB / {metrics['ram_total_gb']}GB")

    def test_03_server_process_lifecycle(self):
        """Verify starting server subprocess, checking alive state, and clean termination."""
        # Start server on test port 4789 to avoid conflicts
        test_port = 4789
        proc = start_server_process(test_port)
        self.assertIsNotNone(proc)
        self.assertIsNone(proc.poll())  # Must be running

        time.sleep(2)
        self.assertIsNone(proc.poll())  # Still running after boot

        # Clean shutdown
        stop_server_process()
        self.assertIsNotNone(proc.poll())  # Must be terminated
        print("  [PASS] test_03_server_process_lifecycle: Server booted and cleanly terminated")


if __name__ == "__main__":
    print("\n=======================================================")
    print("  Running SmileAI Desktop Launcher Test Suite (Phase 6)")
    print("=======================================================")
    runner = unittest.TextTestRunner(verbosity=0)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSmileAILauncher)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("=======================================================")
        print("  ALL 3 TESTS PASSED — ZERO ERRORS OR WARNINGS         ")
        print("=======================================================\n")
        sys.exit(0)
    else:
        print("\n[ERROR] One or more launcher tests failed!")
        sys.exit(1)
