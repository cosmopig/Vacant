import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
AUDIT = ROOT / "ops/audits/g3_series_unverified_taxonomy.py"
REPORT = ROOT / "ops/audits/g3_series_unverified_taxonomy.json"


class TestG3SeriesTaxonomy(unittest.TestCase):
    def test_selftest_ok(self):
        """--selftest：正控制（真檔重算＝票面分母）＋3 負控制；rc=0、VERDICT OK。"""
        r = subprocess.run(["python3", str(AUDIT), "--selftest"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERDICT: G3_SERIES_TAXONOMY_OK", r.stdout)

    def test_report_identities(self):
        """報告 JSON 分母與子類加總恆等（每個數字帶分母）。"""
        r = json.loads(REPORT.read_text(encoding="utf-8"))
        t, per = r["totals"], r["per_batch"]
        self.assertEqual(t["requirements"], 76)
        self.assertEqual(t["deterministic_claims"], 2)
        self.assertEqual(t["unverified"], 74)
        self.assertEqual(sum(v["n_requirements"] for v in per.values()), t["requirements"])
        self.assertEqual(sum(v["n_unverified"] for v in per.values()), t["unverified"])
        self.assertEqual(sum(t["prefix_distribution"].values()), t["unverified"])
        self.assertEqual(t["dnr_total"], t["prefix_distribution"]["deliverable_not_in_request"], 52)
        self.assertEqual(sum(t["dnr_taxonomy"].values()), t["dnr_total"])
        for v in per.values():
            self.assertEqual(sum(v["dnr_taxonomy"].values()), v["dnr_total"])
        g3 = per["g3_3_call3"]
        self.assertEqual(g3["dnr_taxonomy"],
                         {"contains_answer_txt": 1, "contains_input_path_only": 1, "no_filename_token": 3})
        self.assertEqual(g3["claims_by_id"],
                         {"R1": "no_filename_token", "R2": "no_filename_token", "R3": "no_filename_token",
                          "R4": "contains_answer_txt", "R5": "contains_input_path_only"})

    def test_source_shas_grounded(self):
        """4 份來源報告的 sha256 與實際檔案一致（缺檔/漂移即紅，fail-closed）。"""
        r = json.loads(REPORT.read_text(encoding="utf-8"))
        for name, s in r["sources"].items():
            p = ROOT / s["file"]
            self.assertTrue(p.is_file(), name)
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), s["sha256"], name)

    def test_run_is_idempotent(self):
        """--run 對既有相同證據重跑時應保持 generated_at 冪等，不得弄髒 git worktree。"""
        before = REPORT.read_bytes()
        try:
            r = subprocess.run(["python3", str(AUDIT), "--run"], capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(REPORT.read_bytes(), before)
        finally:
            if REPORT.read_bytes() != before:
                REPORT.write_bytes(before)

    def test_verify_catches_per_batch_deterministic_conservation_and_fire_claim_count(self):
        """verify() 必須檢查每批 n_requirements == n_deterministic + n_unverified，且 load_batches 對 g3_2_fire 讀 claims.pass+fail（不因 deterministic_cells='see h0_reproducibility' 崩潰）。"""
        import copy
        import ops.audits.g3_series_unverified_taxonomy as mod
        b = mod.load_batches()
        b_bad = copy.deepcopy(b)
        b_bad["g3_1_prerun"]["n_deterministic"] = 999
        b_bad["g3_2_prerun"]["n_deterministic"] = -997
        errs = mod.verify(mod.build(b_bad))
        self.assertTrue(errs, "per_batch n_deterministic 篡改但總和抵銷時 verify() 仍須攔截")


if __name__ == "__main__":
    unittest.main()
