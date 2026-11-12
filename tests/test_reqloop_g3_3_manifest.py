import copy
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
MANIFEST = "ops/reqloop/g3_3/manifest.json"
DRY = ["python3", "-m", "vacant_network.reqloop.g3", "--manifest", MANIFEST, "--dry-run"]

class TestG3_3Manifest(unittest.TestCase):
    def test_precheck_success(self):
        """G3.3 預檢查：sha256 雙核（local==ref==manifest）＋選題一致＋選題規則機械核；VERDICT OK。"""
        r = subprocess.run(["python3", "ops/audits/g3_3_precheck.py", "--selftest"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERDICT: G3_3_PRECHECK_OK", r.stdout)

    def test_dry_run_success(self):
        """G3 管線官方乾跑（plan schema＋凍結＋預算）：exit 0、DRY-RUN OK、0 model calls。"""
        r = subprocess.run(DRY, capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("DRY-RUN OK", r.stdout)
        self.assertIn("0 模型呼叫", r.stdout)

    def test_cell_frozen_single(self):
        """1 格＝dab_725×full_rloop（唯一目標題）；content_reverify 開；其餘 3 題不在格單。"""
        r = subprocess.run(DRY, capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CELL dab_725/full_rloop:", r.stdout)
        self.assertIn("content_reverify=True", r.stdout)
        self.assertNotIn("CELL dab_587/full_rloop:", r.stdout)
        self.assertNotIn("CELL dab_657/full_rloop:", r.stdout)
        self.assertNotIn("CELL dab_517/full_rloop:", r.stdout)

class TestG3_3PrecheckInject(unittest.TestCase):
    """R20261112_0455-1：check_precheck 純函式可注入＋4 類負控制（任篡改必攔）。"""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "g3_3_precheck_mod", ROOT / "ops/audits/g3_3_precheck.py")
        cls.M = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.M)
        cls.m = json.loads((ROOT / "ops/reqloop/g3_3/manifest.json").read_text(encoding="utf-8"))
        cls.p = json.loads((ROOT / "ops/audits/g3_2_h0_prerun_report.json").read_text(encoding="utf-8"))

    def test_positive_real_files(self):
        self.assertEqual(self.M.check_precheck(self.m, self.p), [])

    def test_n1_bad_sha(self):
        m = copy.deepcopy(self.m)
        f0 = next(iter(m["tasks"][0]["files"]))
        m["tasks"][0]["files"][f0] = "0" * 64
        self.assertTrue(self.M.check_precheck(m, self.p))

    def test_n2_bad_order(self):
        m = copy.deepcopy(self.m)
        m["tasks"][0]["task_id"] = "dab_039"
        self.assertTrue(self.M.check_precheck(m, self.p))

    def test_n3_h0_not_zero(self):
        p = copy.deepcopy(self.p)
        for t in p.get("tasks", []):
            if t.get("task_id") == "dab_725":
                t["n_deterministic_claims"] = 0
        self.assertTrue(self.M.check_precheck(self.m, p))

    def test_n4_bad_budget(self):
        m = copy.deepcopy(self.m)
        m["budget"]["timeout_s_per_round"] = 999
        self.assertTrue(self.M.check_precheck(m, self.p))
        a = copy.deepcopy(self.m)
        a["arms"] = ["native_pi", "reqlist_only", "full_rloop"]
        self.assertTrue(self.M.check_precheck(a, self.p))

    def test_ref_missing_fail_closed(self):
        errs = self.M.check_precheck(self.m, self.p, ref_dir=ROOT / "nonexistent_ref_g33")
        self.assertTrue(errs and any("missing ref" in s for s in errs), errs)


if __name__ == "__main__":
    unittest.main()
