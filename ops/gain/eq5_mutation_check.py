#!/usr/bin/env python3
"""EQ5 臂的植入缺陷測試：把三個「等預算宣稱會安靜死掉」的突變體種進去，
確認偵測器**看到的那個量**真的改變（不是只看 rc≠0）。

為什麼判準不能寫 rc≠0（記憶鐵律，r674 咬過）：突變體放錯 import 環境害 import 失敗
也是 rc≠0＝infra 壞掉被誤判成偵測器有牙齒。所以突變體與正本放在**同一個目錄**
（`ops/gain/_eq5_mutant.py`，同一套相對 import），而且每一條都寫死
「偵測器該看到的那個量」與它在乾淨版上的值。

三個突變體對應 EQ5 的三個承重宣稱：
  M1 預算不再是 k（早停回來了）           → 量：`A.calls`（乾淨 5）
  M2 多數決那條規則其實抄了閘門的答案     → 量：`B.vote_matches_off5`（乾淨 True）
  M3 閘門改挑「最後一個」通過的候選       → 量：`A.gate_matches_conform`（乾淨 True）

兩個夾具缺一不可：夾具 A 抽到的候選裡多數本來就是對的（`A.same_choice=True`），
M2 在它上面**看不見**；夾具 B 的多數是錯的（`B.same_choice=False`），M2 才現形。
「同一個夾具測所有突變體」正是 r674 那類假測試的來源。

M2/M3 是這支實驗最貴的一種安靜失敗：兩條規則若其實是同一條，
配對比較會給出「沒有差異」，而那跟「等預算下真的打平」長得一模一樣。
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import random
import sys

os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz")
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SRC = ROOT / "ops" / "gain" / "gain_run.py"
MUT = ROOT / "ops" / "gain" / "_eq5_mutant.py"

GOOD = "def similar_elements(a, b):\n    return tuple(sorted(set(a) & set(b)))\n"
GOOD2 = ("def similar_elements(a, b):\n"
         "    out = [x for x in set(a) if x in set(b)]\n"
         "    return tuple(sorted(out))\n")
BAD = "def similar_elements(a, b):\n    return ()\n"
BAD2 = "def similar_elements(a, b):\n    return tuple()\n"
# 夾具 A：驗「閘門挑第一個通過的」（M1／M3）——要有兩個不同的通過者、首尾不同。
CODES_A = [BAD, BAD2, GOOD, GOOD2, BAD]
# 夾具 B：驗「多數決是另一條規則」（M2）——多數是錯的、只有一份通過可見驗收，
# 乾淨版在這裡 same_choice 必須是 False；兩條規則若其實同一條，這裡才看得出來。
CODES_B = [BAD, BAD2, BAD, GOOD, BAD2]
SEED_A = "eq5-fixture-2"   # 選它的理由見 _fixture_ok：這顆 seed 抽到的 5 份候選裡
                         # 有兩個**不同**的通過者、且第一個與最後一個不是同一份，
                         # M3（改挑最後一個通過的）才有東西可偵測。

SEED_B = "eq5-contrast-1"   # 抽到 [GOOD, BAD2, BAD, BAD2, BAD2]：多數是錯的

MUTATIONS = {
    "M1_early_stop_returns": ("    for a in assigned:\n", "    for a in assigned[:1]:\n"),
    "M2_vote_copies_gate": ("    vote_code, vote_worker = rng.choice(win)\n",
                            "    vote_code, vote_worker = gate_code, gate_worker\n"),
    "M3_gate_takes_last_pass": ("        if vis_ok and chosen is None:\n",
                                "        if vis_ok:\n"),
}


class _FakeAgent:
    def __init__(self, aid, code):
        self.agent_id, self._code = aid, code
        self.cost = self.market_cost = 0.0

    def generate(self, prompt, role=None, meta=None):
        return f"```python\n{self._code}\n```"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _one(mod, task, codes, seed):
    from vacant.identity import Identity
    from vacant.logbook import Logbook
    agents = [_FakeAgent(f"w{i}", c) for i, c in enumerate(codes)]
    calls = [0]
    gate_code, _w, _inv, extra = mod.arm_eq5(
        task, agents, random.Random(seed), calls, Logbook(), Identity.generate())
    off5_code, _ow, _oi, _oe = mod.arm_off5(task, agents, random.Random(seed), [0])
    conform_code, _cw, _ci, _ce = mod.arm_conform(
        task, agents, random.Random(seed), [0], Logbook(), Identity.generate())
    return {"calls": calls[0],
            "vote_matches_off5": extra["vote_code"] == off5_code,
            "gate_matches_conform": gate_code == conform_code,
            "same_choice": bool(extra["same_choice"])}


def _measure(mod, task):
    """回傳兩個夾具各自的偵測量。任何一個算不出來就是 BROKEN，不准當成偵測到。"""
    a = _one(mod, task, CODES_A, SEED_A)
    b = _one(mod, task, CODES_B, SEED_B)
    return {f"A.{k}": v for k, v in a.items()} | {f"B.{k}": v for k, v in b.items()}


def _fixture_ok() -> tuple[bool, list[int]]:
    """夾具自檢（r682 的 C 類：夾具自己不自洽時不准算成『沒偵測到缺陷』）。

    M3 要偵測的是「挑第一個通過的」vs「挑最後一個通過的」。若這顆 seed 抽到的
    5 份候選裡只有一個通過者，兩者本來就同一份 ⇒ 測不出來，而輸出會長得像
    「這個缺陷不存在」。所以先驗夾具：抽樣序列裡的通過者要有兩個不同的、
    且第一個與最後一個不同。
    """
    r = random.Random(SEED_A)
    idx = [r.choice(range(len(CODES_A))) for _ in range(5)]
    passing = [i for i in idx if CODES_A[i] in (GOOD, GOOD2)]
    ok = len(set(passing)) >= 2 and passing[0] != passing[-1]
    return ok, idx


def main() -> int:
    from vacant.codebench import EvalPlusMBPPLoader
    task = next(t for t in EvalPlusMBPPLoader(expose_contract=True).iter_tasks("x")
                if t["entry_point"] == "similar_elements")
    src = SRC.read_text(encoding="utf-8")

    fx_ok, fx_idx = _fixture_ok()
    print(f"夾具抽樣序列（agent 索引）：{fx_idx}　兩個不同通過者且首尾不同={fx_ok}")
    if not fx_ok:
        print("BROKEN：夾具測不到 M3——換 seed，不准把它記成 MISSED 以外的東西。")
        return 1

    clean = _measure(_load(SRC, "_eq5_clean"), task)
    print(f"乾淨版偵測量：{clean}")
    expected_clean = {
        "A.calls": 5, "A.vote_matches_off5": True, "A.gate_matches_conform": True,
        "A.same_choice": True,
        "B.calls": 5, "B.vote_matches_off5": True, "B.gate_matches_conform": True,
        # 夾具 B 的自檢就寫在這裡：乾淨版兩條規則必須交出不同的東西。
        "B.same_choice": False}
    if clean != expected_clean:
        print(f"BROKEN：乾淨版就不符合 {expected_clean}——偵測器沒有基準，停。")
        return 1

    rc = 0
    for name, (old, new) in MUTATIONS.items():
        if src.count(old) != 1:
            print(f"BROKEN  {name}：錨點在正本出現 {src.count(old)} 次（要恰好 1 次）"
                  "——突變沒種進去不是『沒有缺陷』。")
            rc = 1
            continue
        MUT.write_text(src.replace(old, new, 1), encoding="utf-8")
        try:
            got = _measure(_load(MUT, f"_eq5_mut_{name}"), task)
        except Exception as e:                                    # noqa: BLE001
            print(f"BROKEN  {name}：突變體跑不起來（{type(e).__name__}: {e}）"
                  "——這是 infra 壞掉，不算偵測到。")
            rc = 1
            continue
        finally:
            MUT.unlink(missing_ok=True)
        changed = {k: (clean[k], got[k]) for k in clean if clean[k] != got[k]}
        if changed:
            print(f"DETECTED {name}：偵測量改變 {changed}")
        else:
            print(f"MISSED   {name}：三個偵測量與乾淨版完全相同 {got}"
                  "——這個缺陷會安靜通過，測試沒有牙齒。")
            rc = 1
    print("EQ5_MUTATION_CHECK=" + ("PASS" if rc == 0 else "FAIL"))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
