#!/usr/bin/env python3
"""這支在架構裡承重什麼：R535 的**事後計分**——零模型呼叫、可離線重跑、確定性。

它與發射驅動（`ops/gain/r535/run_r535.py`）**刻意分開兩支**。理由不是整潔：
計分要能在一台沒有模型端點的機器上、在任何時間、對同一份快照重跑出**同一個
sha256**。混進驅動裡就做不到——驅動要有端點、要有 pi、要有 load 才跑得動。

## 它讀什麼

每一格的 `_frozen_RUN-ON[_a<n>]/`＝**當時交付那一刻的凍結快照**
（`vacant/vrun/launcher.py` 在驗收之前凍的那一份，`ws_end_sha256` 綁在收據裡）。
計分跑的是同一支驗收 runner `vacant/vrun/acceptance.py::run_suite`
（`bank_manifest.json`：**不准另寫第二把尺**），`suite="hidden"`。

## V/GT 紅線（這一支存在的全部理由）

* harness 只准用 `visible_check`——回饋、重試、拒交，全部只吃可見驗收。
* `hidden_check` **只計分不回饋**：它在這裡第一次被執行，而這裡已經是
  agent 行程結束、快照凍結之後。隱藏測資**不進工作區、不進回饋、不進 argv**。
* 因此本檔**不呼叫 `acceptance.render_failures()`**，也**不落盤 case 的
  `message`／`output`**——那兩個欄位逐字含著隱藏測資的期望值
  （`want=%r`）。落盤的是 case 名稱、`kind`、通過與否、以及
  `result_sha256`。要看細節就在稽核的人自己的機器上加 `--unsafe-keep-messages`，
  而那個旗標會把警告一起寫進輸出，不會有人事後說「我不知道」。

## 逐次嘗試都算

只算最後一次會丟掉一個**免費的單發基線**：三條重試臂的第 1 次嘗試與
`--retry none` 逐位元同構（同 argv、同 TASK.md、launcher 第 1 次不注入任何
東西）⇒ 每格的 `attempt 1` 就是一個單發觀測。所以本檔對**每一個** `_frozen_*`
都算一次，輸出 `by_attempt`，並另外標出哪一次是交付那一次（`delivered`）。

## 確定性

`--twice` 會把每一格算兩遍並比對 `result_sha256`。不同 ⇒ 判 `nondeterministic`
並在輸出裡點名。**「跑一遍看起來對」不是確定性**，負向控制才是。

⚠ 誠實邊界：隱藏驗收通過**不代表題目做對了**。它與可見驗收一樣是單邊保證
（`vacant/suitegauge.py`）：擋得住已知壞解 ≠ 涵蓋真需求。
兩者的差別只是 agent 看不到它，所以它擋得住「照著可見測資寫死」。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from vacant.vrun import acceptance                    # noqa: E402
from vacant.vrun.sandbox import make_sandbox          # noqa: E402

#: 隱藏 case 落盤時**只留這幾個欄位**。`message`／`output` 逐字含隱藏測資。
SAFE_CASE_FIELDS = ("case", "ok", "kind")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_result(result: dict, *, keep_messages: bool) -> dict:
    """把驗收結果縮成**不含隱藏測資**的形狀。"""
    files = []
    for f in result.get("files") or []:
        cases = []
        for c in f.get("cases") or []:
            rec = {k: c.get(k) for k in SAFE_CASE_FIELDS}
            if keep_messages:
                rec["message"] = c.get("message")
                rec["output"] = c.get("output")
            cases.append(rec)
        files.append({"file": f.get("file"), "passed": f.get("passed"),
                      "total": f.get("total"), "cases": cases})
    return {"suite": result.get("suite"), "task_id": result.get("task_id"),
            "passed": result.get("passed"), "total": result.get("total"),
            "all_pass": bool(result.get("all_pass")),
            "empty_reason": result.get("empty_reason"),
            "result_sha256": result.get("result_sha256"), "files": files}


def frozen_dirs(cell: pathlib.Path, summary: dict) -> list[tuple[int, pathlib.Path]]:
    """逐次嘗試的凍結快照。

    ⚠ **用約定的相對路徑，不用 summary 裡那條絕對路徑**：那是發射那台機器上的
    路徑，搬到別台機器計分就指不到。對不到才退回 summary 那一條。
    """
    arm = summary.get("arm", "RUN-ON")
    out: list[tuple[int, pathlib.Path]] = []
    for a in summary.get("attempts") or []:
        n = a["attempt"]
        suffix = "" if n == 1 else f"_a{n}"
        p = cell / "run" / f"_frozen_{arm}{suffix}"
        if not p.is_dir() and a.get("frozen_path"):
            q = pathlib.Path(a["frozen_path"])
            if q.is_dir():
                p = q
        if p.is_dir():
            out.append((n, p))
    return out


def score_cell(sb, cell: pathlib.Path, bank: pathlib.Path, *,
               scratch: pathlib.Path, timeout_s: float, twice: bool,
               keep_messages: bool) -> dict:
    cj = cell / "cell.json"
    if not cj.exists():
        return {"cell": cell.name, "status": "no_cell_json"}
    state = json.loads(cj.read_text(encoding="utf-8"))
    rec: dict = {
        "cell": state.get("cell", cell.name), "task_id": state.get("task_id"),
        "arm": state.get("arm"), "stratum": state.get("stratum"),
        "cell_status": state.get("cell_status"),
        "run_complete": bool(state.get("run_complete")),
        # 驅動已經量到的東西照抄過來，收官時一張表看得完
        "visible_accepted": state.get("accepted"),
        "stop_reason": state.get("stop_reason"),
        "attempts_used": state.get("attempts_used"),
        "requests_seen": state.get("requests_seen"),
        "m7_file": state.get("m7_file"), "m7_file_reason": state.get("m7_file_reason"),
        "m7_ws": state.get("m7_ws"), "m7_ws_ratio": state.get("m7_ws_ratio"),
        "f6": state.get("f6"), "suspect_timeout": state.get("suspect_timeout"),
        "infra_void": state.get("infra_void"),
        "hidden_pass": None, "hidden_passed": None, "hidden_total": None,
        "hidden_result_sha256": None, "by_attempt": [],
        "deterministic": None, "status": None,
    }
    if not rec["run_complete"]:
        rec["status"] = "not_complete"          # **不是 0 分，是沒量完**
        return rec
    if state.get("cell_status") != "measured":
        rec["status"] = state.get("cell_status") or "unmeasured"
        return rec
    sp = cell / "run" / "run_RUN-ON.json"
    if not sp.exists():
        rec["status"] = "no_run_summary"
        return rec
    summary = json.loads(sp.read_text(encoding="utf-8"))
    hidden_dir = bank / rec["task_id"] / "hidden"
    if not hidden_dir.is_dir():
        rec["status"] = "no_hidden_suite"
        return rec

    fz = frozen_dirs(cell, summary)
    if not fz:
        rec["status"] = "no_frozen_snapshot"
        return rec
    vroot = scratch / f"_v_{cell.name}"
    for n, path in fz:
        t0 = time.time()
        res = acceptance.run_suite(sb, path, hidden_dir, suite="hidden",
                                   task_id=rec["task_id"], verify_root=vroot,
                                   timeout_s=timeout_s)
        det = None
        if twice:
            res2 = acceptance.run_suite(sb, path, hidden_dir, suite="hidden",
                                        task_id=rec["task_id"],
                                        verify_root=vroot, timeout_s=timeout_s)
            det = (res.get("result_sha256") == res2.get("result_sha256"))
            rec["deterministic"] = det if rec["deterministic"] is None \
                else (rec["deterministic"] and det)
        va = next((a for a in summary.get("attempts") or []
                   if a["attempt"] == n), {})
        rec["by_attempt"].append({
            "attempt": n,
            "frozen": str(path.relative_to(cell)) if cell in path.parents
            else str(path),
            "ws_end_sha256": va.get("ws_end_sha256"),
            "visible_accepted": va.get("accepted"),
            "visible_passed": va.get("visible_passed"),
            "visible_total": va.get("visible_total"),
            "hidden_pass": bool(res.get("all_pass")),
            "hidden_passed": res.get("passed"), "hidden_total": res.get("total"),
            "hidden_result_sha256": res.get("result_sha256"),
            "deterministic": det,
            "score_wall_s": round(time.time() - t0, 3),
            "hidden": safe_result(res, keep_messages=keep_messages),
        })
    shutil.rmtree(vroot, ignore_errors=True)
    # 交付那一次＝最後一次嘗試（哪一次是最後一次由 `attempts` 說了算，不猜檔名）
    last = rec["by_attempt"][-1]
    rec.update({"delivered_attempt": last["attempt"],
                "hidden_pass": last["hidden_pass"],
                "hidden_passed": last["hidden_passed"],
                "hidden_total": last["hidden_total"],
                "hidden_result_sha256": last["hidden_result_sha256"],
                "status": "scored"})
    # 可見過了而隱藏沒過 ＝ 「照著可見測資寫死」的現場證據。標出來，不加權。
    rec["visible_pass_hidden_fail"] = bool(
        rec["visible_accepted"] and rec["hidden_pass"] is False)
    return rec


def summarise(rows: list[dict]) -> dict:
    """**S1 與 S2 分開報，不合併**（manifest 的 `report_rule`＝裁決）。"""
    out: dict = {}
    for stratum in ("S1", "S2"):
        per: dict = {}
        for arm in ("RS", "RF", "RP", "PC"):
            sel = [r for r in rows
                   if r.get("stratum") == stratum and r.get("arm") == arm]
            scored = [r for r in sel if r.get("status") == "scored"]
            first = [a for r in scored for a in r["by_attempt"]
                     if a["attempt"] == 1]
            per[arm] = {
                "n_cells": len(sel), "n_scored": len(scored),
                "n_void": len([r for r in sel
                               if r.get("status") != "scored"]),
                "visible_pass": sum(1 for r in scored
                                    if r.get("visible_accepted")),
                "hidden_pass": sum(1 for r in scored if r.get("hidden_pass")),
                "visible_pass_hidden_fail": sum(
                    1 for r in scored if r.get("visible_pass_hidden_fail")),
                # 免費的單發基線：三臂第 1 次嘗試
                "attempt1_visible_pass": sum(1 for a in first
                                             if a["visible_accepted"]),
                "attempt1_hidden_pass": sum(1 for a in first
                                            if a["hidden_pass"]),
                "attempt1_n": len(first),
                "suspect_timeout": sum(1 for r in sel
                                       if r.get("suspect_timeout")),
                "m7_file_true": sum(1 for r in sel if r.get("m7_file") is True),
                "m7_file_false": sum(1 for r in sel
                                     if r.get("m7_file") is False),
                "m7_file_null": sum(1 for r in sel if r.get("m7_file") is None),
                "m7_ws_true": sum(1 for r in sel if r.get("m7_ws") is True),
                "m7_ws_false": sum(1 for r in sel if r.get("m7_ws") is False),
                "m7_ws_null": sum(1 for r in sel if r.get("m7_ws") is None),
                "f6_true": sum(1 for r in sel if r.get("f6") is True),
                "f6_false": sum(1 for r in sel if r.get("f6") is False),
            }
        out[stratum] = per
    out["_note"] = (
        "S1 與 S2 分開報，不合併（裁決）。分母是 n_scored 不是 n_cells——"
        "void 的格子沒量到，不可以當成 0 分。"
        "PC < 0.5 ⇒ 該層判 CEILING_TOO_LOW（題目對這顆模型太難）。")
    out["_attempt1_note"] = (
        "免費的單發基線只包含 **RS／RF／RP** 的 attempt 1："
        "那三臂第 1 次的 argv 逐位元相同（V2 的 placeholder 換成空字串）"
        "**而且 TASK.md 也相同** ⇒ 可以合起來當 n=3×題數 的單發觀測。"
        "**PC 的 attempt 1 不可以併進去**：它的 argv 雖然一樣，"
        "工作區的 TASK.md 換成了 TASK_explicit.md ——那是另一個條件，"
        "併表就是把天花板當成基線。")
    return out


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="score_r535.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("R535 事後計分：讀每格的 `_frozen_*` 快照，用 "
                     "`<bank>/<task>/hidden/test_hidden.py` 計分。"
                     "零模型呼叫、可離線重跑、對同一份快照確定性。"),
        epilog=("V/GT 紅線：harness 只准用 visible_check；hidden_check "
                "只計分不回饋。本檔預設**不落盤** case 的 message／output"
                "（那兩個欄位逐字含隱藏測資的期望值）。"))
    ap.add_argument("--out", required=True, help="發射驅動的 run 目錄")
    ap.add_argument("--bank", default=None,
                    help="題庫根（預設 ops/gain/r535/bank）")
    ap.add_argument("--json", default=None,
                    help="結果落點（預設 <out>/scores_<ts>.json）")
    ap.add_argument("--arm", default=None)
    ap.add_argument("--stratum", default=None, choices=["S1", "S2"])
    ap.add_argument("--task", default=None)
    ap.add_argument("--cell", default=None, help="只算一格（目錄名）")
    ap.add_argument("--sandbox", default="none")
    ap.add_argument("--test-timeout", type=float, default=30.0)
    ap.add_argument("--scratch", default=None,
                    help="暫存驗收目錄（**不可以在 cells/ 底下**：隱藏套件會在"
                         "那裡短暫落地）")
    ap.add_argument("--twice", action="store_true",
                    help="每格算兩遍比 result_sha256（確定性的負向控制）")
    ap.add_argument("--unsafe-keep-messages", action="store_true",
                    help="把隱藏 case 的 message／output 一起落盤。"
                         "**那是隱藏測資**——只在稽核的人自己機器上用")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = pathlib.Path(args.out).resolve()
    bank = pathlib.Path(args.bank).resolve() if args.bank else (HERE / "bank")
    cells_dir = out / "cells"
    if not cells_dir.is_dir():
        raise SystemExit(f"找不到 {cells_dir}")
    scratch = pathlib.Path(
        args.scratch or os.path.join(
            os.environ.get("TMPDIR", "/var/tmp"),
            f"r535_score_{os.getpid()}")).resolve()
    if cells_dir == scratch or cells_dir in scratch.parents:
        raise SystemExit("--scratch 不可以在 cells/ 底下（隱藏套件會短暫落在那裡）")
    scratch.mkdir(parents=True, exist_ok=True)
    sb, meta = make_sandbox(args.sandbox, workdir=str(scratch))

    names = sorted(p.name for p in cells_dir.iterdir() if p.is_dir())
    rows: list[dict] = []
    for name in names:
        if args.cell and name != args.cell:
            continue
        task_id, _, arm = name.rpartition("__")
        if args.arm and arm != args.arm:
            continue
        if args.task and task_id != args.task:
            continue
        r = score_cell(sb, cells_dir / name, bank, scratch=scratch,
                       timeout_s=args.test_timeout, twice=args.twice,
                       keep_messages=args.unsafe_keep_messages)
        if args.stratum and r.get("stratum") != args.stratum:
            continue
        rows.append(r)
        print(f"  {name:<28} {r.get('status')}"
              f"  visible={r.get('visible_accepted')}"
              f"  hidden={r.get('hidden_pass')}"
              f"  m7_file={r.get('m7_file')}  m7_ws={r.get('m7_ws')}"
              f"  f6={r.get('f6')}", file=sys.stderr)
    shutil.rmtree(scratch, ignore_errors=True)

    doc = {
        "run": "R535", "scored_at": now_iso(), "out": str(out),
        "bank": str(bank), "sandbox": meta.get("backend"),
        "test_timeout_s": args.test_timeout, "twice": bool(args.twice),
        "keep_messages": bool(args.unsafe_keep_messages),
        "scorer": "ops/gain/r535/score_r535.py",
        "acceptance_runner": "vacant/vrun/acceptance.py::run_suite",
        "vgt": ("harness 只用 visible_check；hidden_check 只計分不回饋。"
                "隱藏 case 的 message／output 預設不落盤。"),
        "n_cells": len(rows), "summary": summarise(rows), "cells": rows,
    }
    p = pathlib.Path(args.json) if args.json else \
        out / f"scores_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    print(json.dumps(doc["summary"], ensure_ascii=False, indent=2))
    print(f"\n[r535] {len(rows)} 格 → {p}  sha256={sha256_file(p)}",
          file=sys.stderr)
    nd = [r["cell"] for r in rows if r.get("deterministic") is False]
    if nd:
        print(f"⚠ 不確定性：{nd}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
