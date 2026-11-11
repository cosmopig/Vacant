import unittest
import subprocess
import sys
from pathlib import Path

class TestHiddenFileTighten(unittest.TestCase):
    def test_selftest_success(self):
        # 驗證 --selftest 是否輸出正確的 VERDICT 並返回 0
        result = subprocess.run(
            ["python3", "ops/audits/hidden_file_in_workspace_tighten.py", "--selftest"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("VERDICT: HIDDEN_FILE_TIGHTEN_OK", result.stdout)

    def test_audit_r530_success(self):
        # 驗證 --audit-r530 是否產生正確的 JSON 檔案並返回 0
        result = subprocess.run(
            ["python3", "ops/audits/hidden_file_in_workspace_tighten.py", "--audit-r530"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        audit_path = Path("ops/audits/r530_hidden_file_tighten_audit.json")
        self.assertTrue(audit_path.exists())

if __name__ == "__main__":
    unittest.main()
