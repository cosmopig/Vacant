#!/usr/bin/env python3
"""R461 C4 難度閘門的判決量具（零 API、只讀落盤檔）。

**為什麼要有這支**：R461 §三 的五格判決表寫在量測之前，但「照表判」這件事本身
如果用眼睛做，下一輪就會在看過失敗率之後才決定要不要把 39% 讀成 40%。
把表變成程式碼 ⇒ 判決不再是當場的判斷。

**新增旋鈕零**：所有門檻逐字取自 `DECISION_20260904_R461_LCB3_REPLICATION_PREREG.md` §三，
不是本輪新訂的。工具啟動時會**回頭驗判準檔裡真的有這些數字**（來源漂移擋門）。

三型「安靜量不到」都要擋（memory 規則）：
  1. rows 檔不存在／讀不出來        → BROKEN
  2. rows 數少於 bank 題數           → INCOMPLETE（不是判決；run 可能還在跑）
  3. 分母為 0（全部 infra_void）      → GATE_UNSCANNED（是「沒量到」不是「量到 0」）

自檢：`--selftest`（植入缺陷測試；每個突變體都指名它該吐哪個 verdict 字串，
不是只看 rc≠0——rc≠0 也可能是 import 壞掉）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

# ── R461 §三 判決表（逐字搬，不是新旋鈕）────────────────────────────
WINDOW_LO = 40.0          # 40–60% ⇒ GATE_PASS
WINDOW_HI = 60.0
MARGINAL_LO = 30.0        # 30–40% ⇒ GATE_MARGINAL
VOID_MAX = 20.0           # 任一臂 infra_void > 20% ⇒ GATE_UNSCANNED
EXPECTED_N = 189          # lcb_bank_v3 題數（codebench.LCB_BANK_V3_COUNT）
DECISION = "DECISION_20260904_R461_LCB3_REPLICATION_PREREG.md"


def verdict_for(fail_pct: float) -> str:
    """五格表。邊界語意寫死：40 與 60 都**算在窗口內**（R461 §三 寫的是 40–60）。"""
    if fail_pct < MARGINAL_LO:
        return "GATE_FAIL_TOO_EASY"
    if fail_pct < WINDOW_LO:
        return "GATE_MARGINAL"
    if fail_pct <= WINDOW_HI:
        return "GATE_PASS"
    return "GATE_FAIL_TOO_HARD"


def check_decision_source(root: pathlib.Path) -> dict:
    """來源漂移擋門：判準檔裡必須真的寫著這幾個門檻與三個 run 名。

    工具與判準是兩份獨立的來源（一份 markdown、一份 py），所以這個一致性檢查
    不是同源自證——改動任一邊都會被抓到。
    """
    p = root / DECISION
    if not p.is_file():
        return {"ok": False, "why": f"判準檔不存在：{p}"}
    txt = p.read_text(encoding="utf-8")
    missing = [s for s in ("40–60%", "30–40%", "GATE_PASS", "GATE_MARGINAL",
                           "GATE_FAIL_TOO_EASY", "GATE_FAIL_TOO_HARD", "GATE_UNSCANNED",
                           "g_r461_off_gate_lcb3", "g_r461_lcb3_three_arm")
               if s not in txt]
    if missing:
        return {"ok": False, "why": f"判準檔缺這些字串（來源漂移）：{missing}"}
    if not re.search(r"infra_void`?\s*>\s*20%", txt):
        return {"ok": False, "why": "判準檔找不到 infra_void > 20% 的擋門"}
    return {"ok": True, "why": "判準檔與工具門檻一致"}


def judge(rows: list[dict], *, expected_n: int = EXPECTED_N) -> dict:
    n_rows = len(rows)
    void = [r for r in rows if r.get("infra_void")]
    scored = [r for r in rows if not r.get("infra_void")]
    void_pct = 100.0 * len(void) / n_rows if n_rows else 0.0
    out = {
        "n_rows": n_rows, "expected_n": expected_n,
        "n_void": len(void), "void_pct": round(void_pct, 2),
        "n_scored": len(scored),
    }
    if n_rows == 0:
        out["verdict"] = "BROKEN"
        out["why"] = "rows.jsonl 一列都沒有——這不是失敗率 0，是沒量到"
        return out
    if n_rows < expected_n:
        out["verdict"] = "INCOMPLETE"
        out["why"] = f"只有 {n_rows}/{expected_n} 列；run 可能還在跑，**不是判決**"
        return out
    if void_pct > VOID_MAX:
        out["verdict"] = "GATE_UNSCANNED"
        out["why"] = f"infra_void {void_pct:.2f}% > {VOID_MAX}%——沒量到，不是量到 0"
        return out
    if not scored:
        out["verdict"] = "GATE_UNSCANNED"
        out["why"] = "分母為 0（全部 infra_void）"
        return out
    ok = sum(1 for r in scored if r.get("meets_demand"))
    fail_pct = 100.0 * (len(scored) - ok) / len(scored)
    out.update({
        "n_meets_demand": ok,
        "fail_pct": round(fail_pct, 2),
        "verdict": verdict_for(fail_pct),
    })
    # R461 §六-2：能力下界。「任一臂通過過一次」的題數證明該題 hidden_check 不恆假；
    # 沒被示範的題數是**「量具假象」的上界**，不是「壞了幾題」。
    out["demonstrated"] = ok
    out["undemonstrated"] = len(scored) - ok
    out["undemonstrated_pct"] = round(100.0 * (len(scored) - ok) / len(scored), 2)
    out["gauge_note"] = ("undemonstrated 是量具假象的上界不是缺陷數；"
                         "OFF 單臂看不出「別的臂會不會過」⇒ 主 run 跑完要重算")
    return out


def _row(tid: str, ok: bool, void: bool = False) -> dict:
    return {"task_id": tid, "meets_demand": ok, "infra_void": void}


def selftest() -> int:
    """植入缺陷測試：每一格指名它**該吐哪個 verdict 字串**。"""
    cases = [
        ("乾淨：50% 落在窗口內", [_row(f"t{i}", i % 2 == 0) for i in range(189)], "GATE_PASS"),
        ("全過（天花板效應回來）", [_row(f"t{i}", True) for i in range(189)], "GATE_FAIL_TOO_EASY"),
        ("全滅（地板效應）", [_row(f"t{i}", False) for i in range(189)], "GATE_FAIL_TOO_HARD"),
        ("35% 失敗＝窗口下緣", [_row(f"t{i}", i >= 66) for i in range(189)], "GATE_MARGINAL"),
        ("安靜量不到①：rows 空", [], "BROKEN"),
        ("安靜量不到②：只跑了一半", [_row(f"t{i}", i % 2 == 0) for i in range(90)], "INCOMPLETE"),
        ("安靜量不到③：全 void", [_row(f"t{i}", False, True) for i in range(189)], "GATE_UNSCANNED"),
        ("void 21% 超過擋門", [_row(f"t{i}", i % 2 == 0, i < 40) for i in range(189)], "GATE_UNSCANNED"),
    ]
    bad = 0
    for name, rows, want in cases:
        got = judge(rows)["verdict"]
        flag = "✓" if got == want else "✗"
        if got != want:
            bad += 1
        print(f"  {flag} {name:28s} want={want:18s} got={got}")
    # 邊界：39.9 / 40.0 / 60.0 / 60.1 —— 邊界語意本身也要被釘住
    for pct, want in ((29.9, "GATE_FAIL_TOO_EASY"), (30.0, "GATE_MARGINAL"),
                      (39.9, "GATE_MARGINAL"), (40.0, "GATE_PASS"),
                      (60.0, "GATE_PASS"), (60.1, "GATE_FAIL_TOO_HARD")):
        got = verdict_for(pct)
        flag = "✓" if got == want else "✗"
        if got != want:
            bad += 1
        print(f"  {flag} 邊界 {pct:5.1f}%{'':17s} want={want:18s} got={got}")
    print(f"selftest: {'PASS' if bad == 0 else f'FAIL（{bad} 格不符）'}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="runs/g_r461_off_gate_lcb3")
    ap.add_argument("--expected-n", type=int, default=EXPECTED_N)
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    root = pathlib.Path(__file__).resolve().parents[2]
    src = check_decision_source(root)
    if not src["ok"]:
        print(json.dumps({"verdict": "BROKEN", "why": src["why"]}, ensure_ascii=False))
        return 1
    rp = root / a.run / "rows.jsonl"
    if not rp.is_file():
        print(json.dumps({"verdict": "BROKEN", "why": f"讀不到 {rp}"}, ensure_ascii=False))
        return 1
    rows = [json.loads(l) for l in rp.read_text(encoding="utf-8").splitlines() if l.strip()]
    res = judge(rows, expected_n=a.expected_n)
    res["run"] = a.run
    res["decision_source"] = src["why"]
    txt = json.dumps(res, ensure_ascii=False, indent=1)
    print(txt)
    if a.out:
        (root / a.out).write_text(txt + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
