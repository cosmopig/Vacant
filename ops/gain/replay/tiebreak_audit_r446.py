"""稽核 R446 等預算重放的 c=0：那是「篩選從沒輸過」，還是平手規則造出來的？

這支在架構裡承重什麼
--------------------
`equal_budget_rules.py` 的基線 `OFF5_REPLAY` 用 `_vote_first`，平手（含冠軍桶內部）
一律取抽樣序最前者。但真跑的 `arm_off5`（`ops/gain/gain_run.py:336-339`）是
`win = rng.choice(tied)` 再 `chosen = rng.choice(win)`——**冠軍桶內部是均勻隨機抽**。

而 `behavior_signature` 探的 `behavior_inputs` 對 MBPP+ 就是 `base`
（`vacant/codebench.py:656`，可見驗收用的同一組輸入），對 LCB 就是可見測資的 args
（同檔 870）。⇒ 所有「通過可見驗收」的候選在探針上輸出一致 ⇒ 落在**同一個簽名桶**。
於是只要冠軍桶是通過者那一桶，`_vote_first` 傳回的就是 min(通過者 index)
＝ `FILTER_FIRST` 的同一個 pick，兩條規則被**強制同意**——c=0 是算出來的，不是量出來的。

本支用 `equal_budget_rules._vote_dist`（該檔自己對 `arm_off5` 隨機性的忠實模型）
把真正的 OFF5 抽法接回去，算 FILTER_FIRST vs 真 OFF5 的期望 b/c。

零 API 呼叫；只讀既有事實表快取，不寫 runs/。
  export VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz
  .venv/bin/python ops/gain/replay/tiebreak_audit_r446.py
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ebr", HERE / "equal_budget_rules.py")
ebr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ebr)


def load(run: str) -> dict[str, list[dict]]:
    facts = json.loads(ebr.facts_path(run).read_text())
    cands, _ = ebr.collect_candidates(run)
    out = {}
    for tid, codes in sorted(cands.items()):
        if len(codes) != 5:
            continue
        view = [facts.get(f"{tid}#{i}") for i in range(5)]
        if any(not isinstance(f, dict) for f in view):
            continue
        out[tid] = view
    return out


def audit(label: str, runs: list[str]) -> None:
    views = [v for r in runs for v in load(r).values()]
    n = len(views)
    eb = ec = 0.0
    p_off5_real = ff_pass = struct_b = split = 0.0
    for v in views:
        idxs = list(range(5))
        dist = ebr._vote_dist(v, idxs)
        passers = [i for i in idxs if v[i]["vis"] is True]
        ff = bool(passers) and v[passers[0]]["hid"] is True
        po = sum(p for i, p in dist if v[i]["hid"] is True)   # 真 OFF5 的通過機率
        p_off5_real += po
        ff_pass += float(ff)
        eb += float(ff) * (1.0 - po)          # arm_off5 的 rng 與篩選的決定性互相獨立
        ec += (0.0 if ff else 1.0) * po
        if v[ebr._vote_first(v, idxs)]["vis"] is not True and ff:
            struct_b += 1                      # 冠軍桶裡沒有通過者 ⇒ 必敗（hidden ⊇ visible）
        if len({v[i]["hid"] is True for i in passers}) > 1:
            split += 1                         # 通過者彼此對 hidden 不同意 ⇒ 隨機抽有差
    det = sum(1 for v in views if v[ebr._vote_first(v, list(range(5)))]["hid"] is True)
    print(f"\n{label}  n={n}")
    print(f"  OFF5 平手取最前（腳本基線）  {det}/{n} = {100 * det / n:.2f}%")
    print(f"  OFF5 **真** 隨機平手 期望     {100 * p_off5_real / n:.2f}%")
    print(f"  FILTER_FIRST                 {ff_pass:.0f}/{n} = {100 * ff_pass / n:.2f}%")
    print(f"  vs 真 OFF5：E[b]={eb:.2f}  E[c]={ec:.2f}   ← 腳本報 c=0（對的是決定性變體）")
    print(f"  b 之中「冠軍桶無通過者」（結構性、與平手無關）= {struct_b:.0f}")
    print(f"  通過者對 hidden 意見分歧的題數（真 OFF5 得以贏的管道）= {split:.0f}")


def main() -> None:
    runs = list(ebr.DEFAULT_RUNS)
    audit("POOLED r444+r445（371 題，題目互斥）",
          ["g_r444_conform_mbpp", "g_r445_conform_mbpp_ext"])
    audit("POOLED 全部 5 個 run（788 題次，題目重複計數）", runs)
    for r in runs:
        audit(r, [r])


if __name__ == "__main__":
    main()
