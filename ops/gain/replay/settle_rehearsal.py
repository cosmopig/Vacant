#!/usr/bin/env python3
"""收官預演（round669）：在 r444 落地**之前**，把收官那條沒被執行過的路徑先跑一遍。

判準見 `CRITERION_20260903_R669_SETTLEMENT_REHEARSAL.md`。

為什麼要有這一支：
  round666/667/668 造的三支尺，`terminal=True` 的硬擋門**只在人造 selftest 裡被碰過**，
  真資料上每一次都是 `terminal=False`＝被降級成「照實報 skew」的那一支。
  收官只發生一次，而那一次跑的是沒被執行過的分支。

零模型呼叫、零沙箱。**唯讀** run 目錄，所有 fixture 建在 --work（預設 /dev/shm/r669）。

fixture：
  A  真快照＋`terminal` 強制 true               ＝健康收官長什麼樣
  B  A 再把一格改成「吃掉呼叫的 void」          ＝健康但有 void（碼允許，見判準 §二 H1-H4）
  C  B 再把 summary.calls 灌大                  ＝真竄改（修完必須仍 BROKEN）
  D  A 悄悄刪掉一列、summary 完全不動           ＝列不見了（processed 不變性該抓到）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

ARMS = ("OFF", "CONFORM", "OFF5")
HERE = pathlib.Path(__file__).resolve().parent


def _rows(raw: bytes) -> list[dict]:
    return [json.loads(l) for l in raw.decode("utf-8").splitlines() if l.strip()]


def consistent(raw_rows: bytes, raw_sum: bytes) -> tuple[bool, str]:
    """rows 與 summary 是不是同一個時刻的？逐臂比對，不一致就說出是哪一項。"""
    rows, summ = _rows(raw_rows), json.loads(raw_sum.decode("utf-8"))
    for a in ARMS:
        sa = summ["arms"].get(a)
        if sa is None:
            return False, f"summary 沒有 {a}"
        ra = [r for r in rows if r.get("arm") == a]
        if len(ra) != sa["processed"] - sa["infra_void"]:
            return False, f"{a} 列數 {len(ra)} != processed-void {sa['processed']-sa['infra_void']}"
        for field, got in (("accepted", sum(1 for r in ra if r["accepted"])),
                           ("accepted_and_meets_demand",
                            sum(1 for r in ra if r["accepted"] and r["meets_demand"])),
                           ("leaked", sum(1 for r in ra if r["accepted"] and not r["meets_demand"]))):
            if sa[field] != got:
                return False, f"{a}.{field} {sa[field]} != {got}"
        if sa["infra_void"] == 0 and sa["calls"] != sum(int(r["calls_used"]) for r in ra):
            return False, f"{a}.calls {sa['calls']} != 逐列和"
    return True, "ok"


def snapshot(run: pathlib.Path, work: pathlib.Path) -> dict:
    """重建「最後一次 write_summary 的那一刻」，不用輪詢去等窗口。

    為什麼可以直接重建（不是近似，是精確）：
      - `rows.jsonl` 是 append-only，且每臂的列按題序寫入（`gain_run.py:1299-1390`）。
      - `summary.json` 在**每題所有臂跑完之後**整份重寫一次（`gain_run.py:1395-1399`）。
    ⇒ 該時刻的狀態 ≡ 每臂只保留前 `processed - infra_void` 列。
    輪詢版本抓不到窗口：實測 r444 卡在一格慢呼叫上超過 8 分鐘（round669），
    自然一致的瞬間只有一次呼叫那麼長。

    截完之後**必須**通過 `consistent()`——那就是「重建對不對」的證據；
    對不起來就 BROKEN，不准擅自往下走。
    """
    work.mkdir(parents=True, exist_ok=True)
    raw = (run / "rows.jsonl").read_bytes()
    summ_raw = (run / "summary.json").read_bytes()
    lines = raw.decode("utf-8").splitlines()
    partial = 0
    if lines:
        try:
            json.loads(lines[-1])
        except json.JSONDecodeError:      # 正在寫一半的最後一列
            lines, partial = lines[:-1], 1
    rows = [json.loads(l) for l in lines if l.strip()]
    summ = json.loads(summ_raw.decode("utf-8"))

    kept, dropped = [], {}
    for a in ARMS:
        sa = summ["arms"][a]
        want = sa["processed"] - sa["infra_void"]
        ra = [r for r in rows if r.get("arm") == a]
        if len(ra) < want:
            raise SystemExit(
                f"BROKEN: {a} 只有 {len(ra)} 列，但 summary 說 processed-void={want}"
                "——rows 落後 summary，這不是 append-only 該有的樣子")
        dropped[a] = len(ra) - want
        kept.extend(ra[:want])

    order = {r_id: i for i, r_id in enumerate(id(r) for r in rows)}
    kept.sort(key=lambda r: order[id(r)])     # 還原原始落盤順序
    rows_out = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept).encode("utf-8")

    ok, why = consistent(rows_out, summ_raw)
    if not ok:
        raise SystemExit(f"BROKEN: 截斷後仍與 summary 對不起來（{why}）——重建假設不成立")

    (work / "rows.jsonl").write_bytes(rows_out)
    (work / "summary.json").write_bytes(summ_raw)
    np = run / "notes.jsonl"
    (work / "notes.jsonl").write_bytes(np.read_bytes() if np.exists() else b"")
    return {"n_rows_raw": len(rows), "n_rows_kept": len(kept),
            "dropped_after_last_summary": dropped, "partial_line_dropped": partial,
            "rows_sha256_8": hashlib.sha256(rows_out).hexdigest()[:8],
            "summary_sha256_8": hashlib.sha256(summ_raw).hexdigest()[:8]}


def _load(d: pathlib.Path):
    return (_rows((d / "rows.jsonl").read_bytes()),
            json.loads((d / "summary.json").read_text(encoding="utf-8")),
            [json.loads(l) for l in (d / "notes.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()])


def _write(d: pathlib.Path, rows, summ, notes):
    d.mkdir(parents=True, exist_ok=True)
    (d / "rows.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (d / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / "notes.jsonl").write_text(
        "".join(json.dumps(n, ensure_ascii=False) + "\n" for n in notes), encoding="utf-8")


def _recompute_rates(sa: dict) -> None:
    """照 gain_run.py:1256-1280 的算式重算（分母 measured = processed - n_void）。"""
    measured = sa["processed"] - sa["infra_void"]
    acc, ok = sa["accepted"], sa["accepted_and_meets_demand"]
    sa["leaked"] = acc - ok
    sa["calls_per_task"] = (sa["calls"] / measured) if measured else None
    sa["coverage"] = (acc / measured) if measured else None
    sa["correct_delivery_rate"] = (ok / measured) if measured else None
    sa["demand_equals_output_rate"] = (ok / acc) if acc else None
    sa["calls_per_correct_delivery"] = (sa["calls"] / ok) if ok else None


def build(work: pathlib.Path, arm: str) -> dict:
    rows, summ, notes = _load(work)

    # A：真快照，只把 terminal 翻成 true（收官那一刻的形狀）
    a_rows = [dict(r) for r in rows]
    a_summ = json.loads(json.dumps(summ))
    for x in ARMS:
        a_summ["arms"][x]["terminal"] = True
    a_summ["run_terminal"] = True
    _write(work / "A", a_rows, a_summ, notes)

    # B：A 再把該臂**最後一列**改成「吃掉呼叫的 void」
    #    ——碼上的樣子：不寫列、processed 照加、n_void+1、calls[0] 不回捲。
    victim = [r for r in a_rows if r["arm"] == arm][-1]
    b_rows = [r for r in a_rows if not (r["arm"] == arm and r["task_id"] == victim["task_id"])]
    b_summ = json.loads(json.dumps(a_summ))
    sb = b_summ["arms"][arm]
    sb["infra_void"] += 1
    sb["accepted"] -= int(bool(victim["accepted"]))
    sb["accepted_and_meets_demand"] -= int(bool(victim["accepted"]) and bool(victim["meets_demand"]))
    # calls 刻意不動＝void 格子消耗的呼叫留在 summary 裡（判準 §二 H3）
    _recompute_rates(sb)
    b_notes = notes + [{"arm": arm, "task_id": victim["task_id"],
                        "infra_void": "sandbox verifier unavailable: simulated(round669)"}]
    _write(work / "B", b_rows, b_summ, b_notes)

    # C：B 再把 calls 灌大（真竄改，遠超過 n_void × 單格上限）
    c_summ = json.loads(json.dumps(b_summ))
    c_summ["arms"][arm]["calls"] += 50
    _recompute_rates(c_summ["arms"][arm])
    _write(work / "C", b_rows, c_summ, b_notes)

    # D：A 悄悄少一列，summary 一個字都不改
    _write(work / "D", b_rows, a_summ, notes)

    return {"victim_task_id": victim["task_id"], "victim_arm": arm,
            "victim_calls_used": victim["calls_used"],
            "victim_accepted": victim["accepted"], "victim_meets_demand": victim["meets_demand"]}


def run_tool(tool: str, d: pathlib.Path, arm: str) -> dict:
    cmd = [sys.executable, str(HERE / tool), "--run", str(d), "--test-arm", arm]
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout + p.stderr).strip().splitlines()
    broken = [l for l in out if l.startswith("BROKEN")]
    return {"rc": p.returncode, "broken": broken[0] if broken else None,
            "tail": out[-1][:160] if out else ""}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--work", default="/dev/shm/r669")
    ap.add_argument("--test-arm", default="CONFORM")
    ap.add_argument("--json")
    args = ap.parse_args()

    work = pathlib.Path(args.work)
    if work.exists():
        shutil.rmtree(work)
    snap = snapshot(pathlib.Path(args.run), work)
    meta = build(work, args.test_arm)

    res = {}
    for fx in ("A", "B", "C", "D"):
        res[fx] = {t: run_tool(t, work / fx, args.test_arm)
                   for t in ("conform_settle.py", "leak_decomp.py")}

    out = {"snapshot": snap, "fixture": meta, "results": res}
    print(f"重建快照：落盤 {snap['n_rows_raw']} 列 → 截到 {snap['n_rows_kept']} 列 "
          f"（summary 之後多出來的：{snap['dropped_after_last_summary']}，"
          f"寫一半的列：{snap['partial_line_dropped']}）")
    print(f"  rows sha8={snap['rows_sha256_8']}  summary sha8={snap['summary_sha256_8']}")
    print(f"被改成 void 的那一格：{meta['victim_arm']}/{meta['victim_task_id']} "
          f"calls_used={meta['victim_calls_used']} accepted={meta['victim_accepted']} "
          f"meets_demand={meta['victim_meets_demand']}")
    print(f"{'fixture':9s} {'conform_settle':>16s} {'leak_decomp':>14s}   說明")
    desc = {"A": "健康收官（terminal=true）", "B": "健康但有吃掉呼叫的 void",
            "C": "真竄改：calls 灌大 50", "D": "列不見了、summary 不動"}
    for fx in ("A", "B", "C", "D"):
        cs, ld = res[fx]["conform_settle.py"], res[fx]["leak_decomp.py"]
        f = lambda x: ("rc=0 PASS" if x["rc"] == 0 else f"rc={x['rc']} BROKEN")
        print(f"{fx:9s} {f(cs):>16s} {f(ld):>14s}   {desc[fx]}")
    for fx in ("A", "B", "C", "D"):
        for t in ("conform_settle.py", "leak_decomp.py"):
            if res[fx][t]["broken"]:
                print(f"  [{fx}/{t}] {res[fx][t]['broken'][:200]}")
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
