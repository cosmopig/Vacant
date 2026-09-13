#!/usr/bin/env python3
"""R529 的 D5 歸因：把 H-MIX **初稿輪**的碼重新用 `meets_demand(hidden)` 評一次。

這支在架構裡承重什麼
────────────────────
R529 的收官只說得出「H-MIX 贏單發、不贏同預算重抽」。**贏在哪一段**是另一個問題：
是 prompt 措辭（第一輪就對），還是回饋迴圈（跑驗收測資、把失敗原文貼回去、讓它改）？
R460 §五 用 `--rescore-turn1` 答過這一題（答案是「幾乎全來自迴圈」），
但 `ops/gain/analyze_r529.py` **沒有**這個選項（它寫死「零沙箱」）。
本檔補上那一段，而且**不改 analyzer**：R529 的 analyzer 是收官仲裁尺，
它的輸出已經被三方對帳過，往裡面塞一條會跑沙箱的路徑等於改動仲裁器。

**方法（與 `ops/gain/analyze_r460.py` 逐字同一段）**
1. 取碼：`analyze_r460.rescore_turn1(rows, calls, tasks)` ——**直接呼叫那一支**，
   不是抄一份。它找每一列的第一個 `kind == "build"` 且 `used_output` 的輪次，
   從 `calls.jsonl` 的全文回應用 `gain_run.extract_code` 取碼（D4：初稿輪與 OFF
   同一個取碼器），再走與 dispatch 端逐字相同的 `meets_demand(hidden)`。
2. 題庫：逐塊讀 `summary.json` 的 `bank`／`bank_filter`／`seed`／`n`／`offset`，
   用 `gain_run.load_tasks` 重建同一批題（R529 四集的形狀都不一樣，
   不能像 R460R 那樣寫死 lcb2）。
3. 兩個差值，逐集算：
   · `delta_turn1_minus_off`＝（H-MIX 初稿輪 vs OFF）＝ **prompt 效果**；
   · `delta_final_minus_turn1`＝（H-MIX 最終 vs 它自己的初稿輪）＝ **迴圈效果**，
     另附只算「真的進過迴圈」那些題的版本（`looponly`）。

**誠實邊界（收官必帶，一條都不准掉）**
· **不是恆等式**：Δ_O ≈ prompt 效果 ＋ 迴圈效果，但 turn-1 那一份是**無條件計分**
  （沒有 accepted／拒交語意），最終那一份有 ⇒ 兩段加起來不會剛好等於 Δ_O。
· **重放不穩定**：`DECISION_20260911_R460_FABLE_AUDIT_HARNESS.md` §十 量到同一份
  資料在不同機器負載下重跑，每臂會差 1–3 題（沙箱 10 秒逾時的非決定性）。
  ⇒ 這裡的數字要當**區間**讀，不是定值；本檔把重放環境記進 JSON。
· **零模型呼叫，但會跑沙箱**（每題一次）⇒ 跑的時候機器不要同時跑全套 pytest。
· 本檔**不下任何裁決**、不進 Holm 家族、不改 R529 四狀態。分層 p 值印出來只是
  為了讓「四集方向一不一致」看得到，它是**事後**的，不在預註冊裡。

用法：
    python3 ops/gain/r529_rescore_turn1.py --json ops/gain/replay/r529/r529_rescore_turn1.json
    python3 ops/gain/r529_rescore_turn1.py --sets lcb3_hard      # 只跑一集
"""
from __future__ import annotations

import argparse
import json
import pathlib
import platform
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.gain.analyze_r460 import (_deliv, _pct,  # noqa: E402
                                   rescore_turn1)
from ops.gain.analyze_r529 import SETS  # noqa: E402
from ops.gain.replay.paired_ci import diff_ci  # noqa: E402
from vacant.research import mcnemar_exact, stratified_mcnemar_exact  # noqa: E402

ARM = "HMIX"
IDENTITY_WARNING = (
    "Δ_O ≈ prompt 效果 ＋ 迴圈效果，**不是恆等式**：turn-1 那一份無條件計分"
    "（沒有拒交語意），最終那一份有 accepted。")
REPLAY_WARNING = (
    "重放不穩定（R460 audit §十）：同一份資料在不同機器負載下重跑，"
    "hidden 重算每臂會差 1–3 題（沙箱逾時的非決定性）⇒ 這些數字要當**區間**讀。"
    "本檔把重放環境記在 `replay_env`。")
NO_ARBITRATION = (
    "本檔不下裁決、不進 Holm 家族、不改 R529 四狀態；"
    "分層 p 是**事後**的描述，不在預註冊裡。")


def load_block(name: str) -> tuple[list[dict], list[dict], dict]:
    d = ROOT / "runs" / name
    rows = [json.loads(l) for l in (d / "rows.jsonl").open(encoding="utf-8")
            if l.strip()]
    cp = d / "calls.jsonl"
    calls = ([json.loads(l) for l in cp.open(encoding="utf-8") if l.strip()]
             if cp.exists() else [])
    summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    return rows, calls, summary


def tasks_of_block(summary: dict) -> dict[str, dict]:
    """用該塊自己的 bank／filter／seed／n／offset 重建它跑過的那一批題。"""
    from ops.gain.gain_run import load_tasks
    ts = load_tasks(summary["bank"], summary["seed"], int(summary["n"]),
                    offset=int(summary.get("offset") or 0),
                    bank_filter=(summary.get("bank_filter") or None))
    return {t["task_id"]: t for t in ts}


def attribution(rows: list[dict], turn1: dict[str, dict[str, bool]]) -> dict:
    """D5：`delta_turn1_minus_off` 與 `delta_final_minus_turn1`（與 R460 同式）。"""
    by_arm: dict[str, list[dict]] = {}
    for r in rows:
        by_arm.setdefault(r.get("arm"), []).append(r)
    rs = by_arm.get(ARM, [])
    off = by_arm.get("OFF", [])
    hist: dict[str, int] = {}
    for r in rs:
        k = r.get("first_pass_turn")
        hist[str(k) if k is not None else "none"] = hist.get(
            str(k) if k is not None else "none", 0) + 1
    fpt1 = [r for r in rs if r.get("first_pass_turn") == 1]
    loop_needed = [r for r in rs if r.get("first_pass_turn") != 1]
    gained = [r for r in rs
              if r.get("first_pass_turn") not in (None, 1) and _deliv(r)]
    a: dict = {
        "arm": ARM,
        "n_rows": len(rs),
        "first_pass_turn_hist": dict(sorted(hist.items())),
        "turn1_visible_pass_n": len(fpt1),
        "turn1_visible_pass_pp": _pct(len(fpt1), len(rs)),
        "loop_touched_n": len(loop_needed),
        "loop_gain_n": len(gained),
        "loop_gain_pp": _pct(len(gained), len(rs)),
        "rescored": False,
        "identity_warning": IDENTITY_WARNING,
    }
    t1 = (turn1 or {}).get(ARM)
    if not t1 or not off:
        a["rescore_note"] = ("初稿輪重評不可得（沒有 turn-1 重算結果或沒有 OFF 臂）"
                             "⇒ 兩個差值是 **None，不是 0**。")
        return a
    a["rescored"] = True
    a["rescore_note"] = (
        "turn-1 的碼由 calls.jsonl 全文回應離線重取（`gain_run.extract_code`，D4），"
        "再走與 dispatch 端逐字相同的 `meets_demand(hidden)`。無條件計分"
        "（沒有 accepted 語意），形狀與 OFF 相同。")
    a["turn1_rescored_n"] = len(t1)
    a["turn1_rescored_pass_n"] = sum(1 for v in t1.values() if v)

    off_map = {r["task_id"]: _deliv(r) for r in off}
    common = sorted(set(t1) & set(off_map))
    b = sum(1 for t in common if t1[t] and not off_map[t])
    c = sum(1 for t in common if off_map[t] and not t1[t])
    if common:
        d1 = diff_ci(b, c, len(common))
        a.update({
            "delta_turn1_minus_off_pp": 100.0 * d1["delta"],
            "delta_turn1_minus_off_ci95_lo_pp": 100.0 * d1["lo"],
            "delta_turn1_minus_off_ci95_hi_pp": 100.0 * d1["hi"],
            "delta_turn1_minus_off_n_common": len(common),
            "delta_turn1_minus_off_b": b, "delta_turn1_minus_off_c": c,
            "delta_turn1_minus_off_p_mcnemar_exact": mcnemar_exact(b, c),
        })
    fin = {r["task_id"]: _deliv(r) for r in rs}
    com2 = sorted(set(t1) & set(fin))
    b2 = sum(1 for t in com2 if fin[t] and not t1[t])
    c2 = sum(1 for t in com2 if t1[t] and not fin[t])
    if com2:
        d2 = diff_ci(b2, c2, len(com2))
        a.update({
            "delta_final_minus_turn1_pp": 100.0 * d2["delta"],
            "delta_final_minus_turn1_ci95_lo_pp": 100.0 * d2["lo"],
            "delta_final_minus_turn1_ci95_hi_pp": 100.0 * d2["hi"],
            "delta_final_minus_turn1_n_common": len(com2),
            "delta_final_minus_turn1_b": b2, "delta_final_minus_turn1_c": c2,
        })
    loop_ids = {r["task_id"] for r in loop_needed}
    com3 = sorted(set(com2) & loop_ids)
    if com3:
        b3 = sum(1 for t in com3 if fin[t] and not t1[t])
        c3 = sum(1 for t in com3 if t1[t] and not fin[t])
        d3 = diff_ci(b3, c3, len(com3))
        a.update({
            "delta_final_minus_turn1_looponly_pp": 100.0 * d3["delta"],
            "delta_final_minus_turn1_looponly_n_common": len(com3),
            "delta_final_minus_turn1_looponly_b": b3,
            "delta_final_minus_turn1_looponly_c": c3,
        })
    return a


def run_set(name: str) -> dict:
    rows: list[dict] = []
    calls: list[dict] = []
    tasks: dict[str, dict] = {}
    missing: list[str] = []
    for blk in SETS[name]:
        d = ROOT / "runs" / blk
        if not (d / "rows.jsonl").exists():
            missing.append(blk)
            continue
        r, c, s = load_block(blk)
        rows += r
        calls += c
        tasks.update(tasks_of_block(s))
    if missing:
        return {"set": name, "status": "NOT_RUN", "missing": missing}
    t0 = time.time()
    turn1 = rescore_turn1(rows, calls, tasks)
    out = attribution(rows, turn1)
    out.update({"set": name, "status": "ANALYZED",
                "blocks_n": len(SETS[name]),
                "tasks_loaded": len(tasks),
                "rescore_wall_s": round(time.time() - t0, 1)})
    return out


def stratified(per_set: dict) -> dict:
    """四集的 turn1−OFF 不一致對做一次分層精確檢定（**事後、不進裁決**）。

    與 `analyze_r529.primary` 同一個統計量與同一句誠實邊界：分層買到的是解釋，
    不是更嚴的檢定；它與「把四集的 b/c 直接加起來做一次 McNemar」數值相同。
    """
    bc = [(d["delta_turn1_minus_off_b"], d["delta_turn1_minus_off_c"])
          for d in per_set.values()
          if d.get("status") == "ANALYZED"
          and d.get("delta_turn1_minus_off_b") is not None]
    bc2 = [(d["delta_final_minus_turn1_b"], d["delta_final_minus_turn1_c"])
           for d in per_set.values()
           if d.get("status") == "ANALYZED"
           and d.get("delta_final_minus_turn1_b") is not None]
    out = {"note": NO_ARBITRATION}
    for key, pairs in (("turn1_minus_off", bc), ("final_minus_turn1", bc2)):
        if not pairs:
            continue
        st = stratified_mcnemar_exact(pairs)
        out[key] = {"b_total": sum(b for b, _ in pairs),
                    "c_total": sum(c for _, c in pairs),
                    "k_strata": len(pairs), "p": st["p"]}
    return out


def render(o: dict) -> str:
    L = ["═══ R529 D5 歸因（--rescore-turn1 的同一段邏輯）═══",
         f"臂：{ARM}　重放環境：{o['replay_env']['python']} / "
         f"{o['replay_env']['platform']}", "",
         f"{'set':16}{'n':>5}{'第一輪就對':>11}{'Δ(turn1−OFF)':>15}"
         f"{'Δ(final−turn1)':>17}{'只算迴圈題':>13}{'迴圈救回':>10}"]
    for s, d in o["per_set"].items():
        if d.get("status") != "ANALYZED":
            L.append(f"{s:16}  {d.get('status')}（缺 {len(d.get('missing') or [])} 塊）")
            continue

        def f(k, nd=2):
            v = d.get(k)
            return "n/a" if v is None else f"{v:+.{nd}f}pp"
        L.append(f"{s:16}{d['n_rows']:>5}"
                 f"{(d['turn1_visible_pass_pp'] or 0):>10.1f}%"
                 f"{f('delta_turn1_minus_off_pp'):>15}"
                 f"{f('delta_final_minus_turn1_pp'):>17}"
                 f"{f('delta_final_minus_turn1_looponly_pp'):>13}"
                 f"{d['loop_gain_n']:>10}")
        L.append(f"{'':16}  b/c(turn1−OFF)="
                 f"{d.get('delta_turn1_minus_off_b')}/{d.get('delta_turn1_minus_off_c')}"
                 f"　b/c(final−turn1)="
                 f"{d.get('delta_final_minus_turn1_b')}/"
                 f"{d.get('delta_final_minus_turn1_c')}"
                 f"　first_pass_turn {d['first_pass_turn_hist']}")
    st = o.get("stratified") or {}
    for k in ("turn1_minus_off", "final_minus_turn1"):
        if k in st:
            v = st[k]
            L.append(f"  分層（事後）{k}: B={v['b_total']} C={v['c_total']} "
                     f"K={v['k_strata']} p={v['p']:.3g}")
    L += ["", f"⚠ {IDENTITY_WARNING}", f"⚠ {REPLAY_WARNING}", f"⚠ {NO_ARBITRATION}"]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", nargs="+", choices=list(SETS), default=list(SETS))
    ap.add_argument("--json")
    args = ap.parse_args()
    per_set = {s: run_set(s) for s in args.sets}
    out = {
        "run": "R529",
        "method": "ops/gain/analyze_r460.py::rescore_turn1（直接呼叫，不是抄一份）",
        "arm": ARM,
        "why_not_in_analyzer": (
            "`ops/gain/analyze_r529.py` 寫死零沙箱、而且它是已被三方對帳過的收官"
            "仲裁尺 ⇒ 不往裡面加會跑沙箱的路徑；D5 歸因另檔出。"),
        "replay_env": {"python": platform.python_version(),
                       "platform": platform.platform(),
                       "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                               time.gmtime())},
        "identity_warning": IDENTITY_WARNING,
        "replay_warning": REPLAY_WARNING,
        "no_arbitration": NO_ARBITRATION,
        "per_set": per_set,
        "stratified": stratified(per_set),
    }
    print(render(out))
    if args.json:
        p = pathlib.Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
        print(f"\nJSON → {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
