import copy
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
MANIFEST = "ops/reqloop/g3_2/manifest.json"
DRY = ["python3", "-m", "vacant_network.reqloop.g3", "--manifest", MANIFEST, "--dry-run"]


class TestG3_2Manifest(unittest.TestCase):
    def test_precheck_success(self):
        """G3.2 預檢查：sha256 雙核（local==ref==manifest）＋選題一致＋screen hash；VERDICT OK。"""
        r = subprocess.run(["python3", "ops/audits/g3_2_precheck.py", "--selftest"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERDICT: G3_2_PRECHECK_OK", r.stdout)

    def test_dry_run_success(self):
        """G3 管線官方乾跑（plan schema＋凍結＋預算）：exit 0、DRY-RUN OK、0 model calls。"""
        r = subprocess.run(DRY, capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("DRY-RUN OK", r.stdout)
        self.assertIn("0 模型呼叫", r.stdout)

    def test_cell_order_frozen(self):
        """乾跑 4 格順序＝凍結選題清單（725→587→657→517），full_rloop 臂、content_reverify 開。"""
        r = subprocess.run(DRY, capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        pos = [r.stdout.index(f"CELL dab_{t}/full_rloop:") for t in ("725", "587", "657", "517")]
        self.assertEqual(pos, sorted(pos))
        self.assertIn("content_reverify=True", r.stdout)


class TestG3_2PrecheckInject(unittest.TestCase):
    """R20261112_0820-1：check_precheck 純函式可注入＋負控制（純記憶體深拷貝，嚴禁寫入實盤）。"""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "g3_2_precheck_mod", ROOT / "ops/audits/g3_2_precheck.py")
        cls.M = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.M)
        cls.m = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"))
        cls.screen_stdout = subprocess.run(
            ["python3", str(ROOT / "ops/audits/g3_2_bank_screen.py")],
            capture_output=True, text=True, cwd=ROOT, check=True,
        ).stdout

    def test_positive_real_files(self):
        self.assertEqual(self.M.check_precheck(self.m, self.screen_stdout), [])

    def test_n1_bad_sha(self):
        m = copy.deepcopy(self.m)
        f0 = next(iter(m["tasks"][0]["files"]))
        m["tasks"][0]["files"][f0] = "0" * 64
        self.assertTrue(self.M.check_precheck(m, self.screen_stdout))

    def test_n2_bad_order_and_seen_set_contamination(self):
        m = copy.deepcopy(self.m)
        m["tasks"][0]["task_id"] = "dab_039"
        self.assertTrue(self.M.check_precheck(m, self.screen_stdout))
        m_seen = copy.deepcopy(self.m)
        m_seen["seen_set"].append("dab_725")
        self.assertTrue(self.M.check_precheck(m_seen, self.screen_stdout))

    def test_n3_bad_screen_sha_and_missing(self):
        m = copy.deepcopy(self.m)
        m["screening"]["output_sha256"] = "0" * 64
        self.assertTrue(self.M.check_precheck(m, self.screen_stdout))
        m_del = copy.deepcopy(self.m)
        del m_del["screening"]["output_sha256"]
        self.assertTrue(self.M.check_precheck(m_del, self.screen_stdout))

    def test_n4_bad_budget_and_missing_fields(self):
        m = copy.deepcopy(self.m)
        m["budget"]["timeout_s_per_round"] = 999
        self.assertTrue(self.M.check_precheck(m, self.screen_stdout))
        a = copy.deepcopy(self.m)
        a["arms"] = ["native_pi"]
        self.assertTrue(self.M.check_precheck(a, self.screen_stdout))
        m_del = copy.deepcopy(self.m)
        del m_del["arms"]
        self.assertTrue(self.M.check_precheck(m_del, self.screen_stdout))
        m_empty_b = copy.deepcopy(self.m)
        m_empty_b["budget"] = {}
        self.assertTrue(self.M.check_precheck(m_empty_b, self.screen_stdout))

    def test_ref_missing_fail_closed(self):
        errs = self.M.check_precheck(
            self.m, self.screen_stdout, ref_dir=ROOT / "nonexistent_ref_g32"
        )
        self.assertTrue(errs and any("missing ref" in s for s in errs), errs)


if __name__ == "__main__":
    unittest.main()
