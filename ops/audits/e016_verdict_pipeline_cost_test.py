"""e016 判決管線成本來源測試（round 954，監督者 11/04 🔴 點名）。

事實：成本在 cell.json.metrics（model_calls / input_tokens / output_tokens）；
score.json 只有 pass / tests_*，**沒有** model_calls / tokens 欄位。舊 load() 從
score.json 讀成本 ⇒ 恆 None ⇒ 被 `int(x or 0)` 靜默當 0 ⇒ 成本紅線（>2×A）從未
真正檢查過（形同沒在檢查）。

裁決準則（NOW.md 11/04，先寫後改）：
 1. load() 改讀 cell.json.metrics（tok＝input＋output）；
 2. 該格任一成本欄位缺失／cell.json 缺失 ⇒ 該格成本 UNKNOWN（None），**不是 0**；
 3. 任何一格成本 UNKNOWN ⇒ 成本判定 UNKNOWN——不是 0、不是通過（優於 COST_BREACH）；
 4. 資料完整的格，紅線照舊能觸發（UNKNOWN 機制不放松既有紅線）。

fixture＝真實格子檔位元組複製（/srv/vlab/runs/e016_failed_step_ablation 的
polyglot_py-pg_affine_cipher A/C 兩格，2026-11-04 複製）：
 A: model_calls=15, input=160651, output=8815  ⇒ tok=169466
 C: model_calls=14, input=74564,  output=3848  ⇒ tok=78412
（兩格皆 pass=true ⇒ 分歧＝0，成本路徑獨立可判。）

跑：python3 -m unittest e016_verdict_pipeline_cost_test -v
（unittest 形式，非 CLI selftest——round 836 背景：CLI 形式不落在測試命令分類。）
"""
import json, pathlib, shutil, tempfile, unittest

import e016_verdict_pipeline as vp

FIX = pathlib.Path(__file__).parent / "fixtures" / "e016_cell_cost"
EXP = "e016_cost_fixture"
A_CELL = f"polyglot_py-pg_costfix-pi-A-r1"
C_CELL = f"polyglot_py-pg_costfix-pi-C-r1"


def _build(tmp: pathlib.Path, mutate: str | None = None) -> None:
    """把 fixture 排成 run 目錄結構（臂名/後綴與 load() 約定一致）。"""
    for arm in ("A", "C"):
        cell = tmp / EXP / (A_CELL if arm == "A" else C_CELL)
        cell.mkdir(parents=True)
        shutil.copy(FIX / arm / "cell.json", cell / "cell.json")
        shutil.copy(FIX / arm / "score.json", cell / "score.json")
    if mutate == "drop-calls":
        p = tmp / EXP / C_CELL / "cell.json"
        d = json.loads(p.read_text())
        del d["metrics"]["model_calls"]
        p.write_text(json.dumps(d))
    elif mutate == "drop-cell":
        (tmp / EXP / C_CELL / "cell.json").unlink()


class CostSource(unittest.TestCase):
    def test_load_reads_cell_json_metrics(self):
        """準則 1：成本必須等於 cell.json.metrics 的值（改前從 score.json 讀⇒恆 None⇒失敗）。"""
        with tempfile.TemporaryDirectory() as td:
            _build(pathlib.Path(td))
            rows, total, missing = vp.load(pathlib.Path(td), EXP)
            self.assertEqual((total, missing), (2, 0))
            a = next(r for r in rows if r["arm"] == "A")
            c = next(r for r in rows if r["arm"] == "C")
            self.assertTrue(a["pass"] and c["pass"])
            self.assertEqual((a["calls"], a["tok"]), (15, 160651 + 8815))
            self.assertEqual((c["calls"], c["tok"]), (14, 74564 + 3848))

    def test_missing_metric_is_unknown_not_zero(self):
        """準則 2＋3：model_calls 缺失⇒該格成本 None⇒判定 UNKNOWN（改前當 0⇒NO_MECHANISM⇒失敗）。"""
        with tempfile.TemporaryDirectory() as td:
            _build(pathlib.Path(td), mutate="drop-calls")
            rows, _, _ = vp.load(pathlib.Path(td), EXP)
            c = next(r for r in rows if r["arm"] == "C")
            self.assertIsNone(c["calls"])
            v = vp.decide(rows, 2, 0)
            self.assertEqual(v["state"], "UNKNOWN")
            self.assertIn("成本", v["why"])

    def test_missing_cell_json_is_unknown_not_zero(self):
        """準則 2＋3：cell.json 整份缺失⇒該格成本 UNKNOWN⇒判定 UNKNOWN。"""
        with tempfile.TemporaryDirectory() as td:
            _build(pathlib.Path(td), mutate="drop-cell")
            rows, _, _ = vp.load(pathlib.Path(td), EXP)
            v = vp.decide(rows, 2, 0)
            self.assertEqual(v["state"], "UNKNOWN")
            self.assertIn("成本", v["why"])

    def test_breach_still_fires_with_complete_data(self):
        """準則 4：資料完整時紅線照觸（C 45 calls > 2×15）⇒ COST_BREACH，不被 UNKNOWN 機制放松。"""
        with tempfile.TemporaryDirectory() as td:
            _build(pathlib.Path(td))
            rows = list(vp.load(pathlib.Path(td), EXP)[0])
            for r in rows:
                if r["arm"] == "C":
                    r["calls"] = 45
                    r["tok"] = 3 * (74564 + 3848)
            v = vp.decide(rows, 2, 0)
            self.assertEqual(v["state"], "COST_BREACH")


if __name__ == "__main__":
    unittest.main()
