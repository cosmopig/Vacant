#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""這支在架構裡承重什麼：把 `--test-timeout` 從「抄來的常數」變成「量到的數字」。

⚠ **本目錄不是預註冊實驗**，判讀紀律見 `README.md` 最上面那一節。

為什麼需要這一支
----------------
`vacant/vrun/launcher.py` 的 `--test-timeout` 預設 10 秒，來源是 R530 凍結的
`sandbox.DEFAULT_TEST_TIMEOUT_S`；R535 的發射腳本用的是 30 秒，那是為**秒級微型題**
定的。兩個數字都**不是在這個題庫上量的**。

逾時值訂太低會製造**假逾時**：一份其實正確的 `solution.py` 被記成
`kind="timeout"` ⇒ 可見失敗 ⇒ 重試 ⇒ 整格的 `stop_reason` 說的是另一件事。
那種格子在資料上與「模型寫錯了」**同形**，事後分不開。所以要先量。

量什麼（逾時的單位就是量測的單位）
----------------------------------
`vacant/vrun/acceptance.py::run_suite` **一個測試檔一個子行程**，`--test-timeout`
是**每檔**的上限。而 `ops/gain/r530/export_bank.py` 把整個 `tests_visible/` 投影成
**一個** `test_visible.py`、整個 `hidden/` 投影成**一個** `test_hidden.py`
⇒ 一題的可見驗收（2–4 條）與隱藏驗收（6–16 條）各自**整組**要在那個上限內跑完。
所以這支量的就是「參考解 ＋ 整組驗收」的單檔牆鐘。

判準：**最慢那一檔的 3 倍**（`--multiplier`，預設 3）。三倍不是統計量，是
工程餘裕——同一台機器上同時有別的 agent 在跑，單次觀測不是上界。

`--parallel` 存在的理由
-----------------------
正式跑會有 2 條流 ＋ 別的 agent 同時在這台機器上。逾時是**牆鐘**，所以競爭會
直接抬高它。只在閒置時量等於量了一個樂觀的下界；這支預設把序列與並行兩種
條件都量，報告引用的是**兩者的最大值**。

誠實邊界
--------
* 這支量的是**參考解**的執行時間。模型寫出來的解可能更慢（多一層迴圈、
  多一次 subprocess）。所以「3 倍」擋的是餘裕不是上界，**逾時格仍然可能出現**，
  出現時要當成觀測不是 bug。
* 參考解**沒有全過**的那一題不計入 max，而且整支 exit 1——那代表驗收與契約
  對不起來（`TASK_FORMAT.md` §七），在那種題目上量出來的時間沒有意義。

用法
----
    python3 ops/gain/r530vrun/probe_timeout.py --out /var/tmp/vacant_r530vrun/probe
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import pathlib
import shutil
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from vacant.vrun import acceptance                      # noqa: E402
from vacant.vrun.sandbox import make_sandbox            # noqa: E402

R530 = REPO / "ops" / "gain" / "r530"
BANK = R530 / "bank"
TEMPLATES = R530 / "templates"
HIDDEN = R530 / "hidden"
GAUGE = R530 / "gauge"

#: 餘裕倍數。**工程餘裕不是統計量**（docstring 的誠實邊界）。
DEFAULT_MULTIPLIER = 3.0
#: 量測用的天花板。量的時候要比正式值寬很多，否則量到的是天花板不是題目。
DEFAULT_CEILING_S = 300.0


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def task_ids() -> list[str]:
    return sorted(d.name for d in BANK.iterdir()
                  if d.is_dir() and d.name.startswith("ow_"))


def one_measure(task_id: str, suite: str, ceiling_s: float,
                sandbox_name: str, scratch: pathlib.Path) -> dict:
    """一題一組驗收跑一次，回 per-file 的牆鐘與是否全過。"""
    work = pathlib.Path(tempfile.mkdtemp(prefix=f"p_{task_id}_{suite}_",
                                         dir=str(scratch)))
    ws = work / "ws"
    ws.mkdir()
    # 參考解 ＝ `gauge/<task>/good.py`（`export_bank.py` 從 `reference/solution.py`
    # 投影出來的同一份位元組）。工作區只放它——驗收自己 `import solution`。
    shutil.copy2(GAUGE / task_id / "good.py", ws / "solution.py")
    suite_dir = (TEMPLATES / task_id / "tests_visible") if suite == "visible" \
        else (HIDDEN / task_id)
    # `make_sandbox` 回 `(sandbox, backend_meta)`，與 launcher 同一條路徑
    # ——量測與正式跑必須用同一個後端，否則量到的是另一個東西的時間。
    sb, backend_meta = make_sandbox(sandbox_name, workdir=str(work / "sb"))
    t0 = time.time()
    res = acceptance.run_suite(sb, ws, suite_dir, suite=suite, task_id=task_id,
                               verify_root=work / "verify", timeout_s=ceiling_s)
    wall_s = time.time() - t0
    files = [{"file": f["file"], "wall_ms": f["wall_ms"],
              "timed_out": f["timed_out"], "rc": f["rc"],
              "passed": f["passed"], "total": f["total"]}
             for f in res.get("files", [])]
    backend = backend_meta.get("backend")
    shutil.rmtree(work, ignore_errors=True)
    return {
        "task_id": task_id, "suite": suite, "backend": backend,
        "all_pass": res.get("all_pass"), "passed": res.get("passed"),
        "total": res.get("total"), "files": files,
        "suite_wall_s": round(wall_s, 3),
        "max_file_wall_s": round(
            max([f["wall_ms"] for f in files] or [0]) / 1000.0, 3),
    }


def sweep(tasks: list[str], *, suites: tuple[str, ...], ceiling_s: float,
          sandbox_name: str, scratch: pathlib.Path, parallel: int,
          label: str) -> list[dict]:
    jobs = [(t, s) for t in tasks for s in suites]
    out: list[dict] = []

    def show(rec: dict) -> None:
        flag = "" if rec["all_pass"] else "  ** NOT ALL PASS **"
        print(f"  [{label}] {rec['task_id']:<20} {rec['suite']:<7} "
              f"{rec['max_file_wall_s']:>7.3f}s  "
              f"{rec['passed']}/{rec['total']}{flag}", flush=True)

    if parallel <= 1:
        for t, s in jobs:
            rec = one_measure(t, s, ceiling_s, sandbox_name, scratch)
            rec["condition"] = label
            out.append(rec)
            show(rec)
        return out
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as pool:
        futs = {pool.submit(one_measure, t, s, ceiling_s, sandbox_name,
                            scratch): (t, s) for t, s in jobs}
        for fut in concurrent.futures.as_completed(futs):
            rec = fut.result()
            rec["condition"] = label
            out.append(rec)
            show(rec)
    return sorted(out, key=lambda r: (r["task_id"], r["suite"]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="量 r530 題庫的 --test-timeout")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tasks", default="all", help="all 或逗號分隔的 task_id")
    ap.add_argument("--ceiling", type=float, default=DEFAULT_CEILING_S)
    ap.add_argument("--multiplier", type=float, default=DEFAULT_MULTIPLIER)
    ap.add_argument("--sandbox", default="auto")
    ap.add_argument("--parallel", type=int, default=2,
                    help="並行條件用幾條流（正式跑打算開幾條就填幾條）")
    ap.add_argument("--serial-only", action="store_true")
    args = ap.parse_args(argv)

    out = pathlib.Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    scratch = out / "_scratch"
    scratch.mkdir(exist_ok=True)
    tasks = task_ids() if args.tasks == "all" else \
        [t.strip() for t in args.tasks.split(",") if t.strip()]

    print(f"# probe_timeout  tasks={len(tasks)}  ceiling={args.ceiling}s  "
          f"sandbox={args.sandbox}  {now_iso()}", flush=True)
    records: list[dict] = []
    print("## 條件 A：序列（機器相對閒置）", flush=True)
    records += sweep(tasks, suites=("visible", "hidden"),
                     ceiling_s=args.ceiling, sandbox_name=args.sandbox,
                     scratch=scratch, parallel=1, label="serial")
    if not args.serial_only:
        print(f"## 條件 B：並行 {args.parallel} 條（正式跑的條件）", flush=True)
        records += sweep(tasks, suites=("visible", "hidden"),
                         ceiling_s=args.ceiling, sandbox_name=args.sandbox,
                         scratch=scratch, parallel=args.parallel,
                         label=f"parallel{args.parallel}")

    bad = [r for r in records if not r["all_pass"]]
    ok = [r for r in records if r["all_pass"]]
    worst = max(ok, key=lambda r: r["max_file_wall_s"]) if ok else None
    recommended = (math.ceil(worst["max_file_wall_s"] * args.multiplier)
                   if worst else None)
    by_cond: dict[str, float] = {}
    for r in ok:
        by_cond[r["condition"]] = max(by_cond.get(r["condition"], 0.0),
                                      r["max_file_wall_s"])

    report = {
        "generated": now_iso(),
        "tasks_n": len(tasks),
        "measurements_n": len(records),
        "sandbox_requested": args.sandbox,
        "ceiling_s": args.ceiling,
        "multiplier": args.multiplier,
        "reference_not_all_pass": [
            {"task_id": r["task_id"], "suite": r["suite"],
             "condition": r["condition"], "passed": r["passed"],
             "total": r["total"]} for r in bad],
        "max_file_wall_s_by_condition": by_cond,
        "worst": worst,
        "recommended_test_timeout_s": recommended,
        "records": records,
        "honest_bounds": [
            "量的是參考解，不是模型寫的解——3 倍是工程餘裕不是上界。",
            "逾時格仍然可能出現；出現時是觀測不是 bug。",
            "這個數字只對 ops/gain/r530/bank/ 這 20 題成立。",
        ],
    }
    (out / "timeout_probe.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(scratch, ignore_errors=True)

    print("")
    print("max_file_wall_s by condition: "
          + "  ".join(f"{k}={v:.3f}s" for k, v in sorted(by_cond.items())))
    if worst:
        print(f"worst = {worst['task_id']} / {worst['suite']} / "
              f"{worst['condition']} = {worst['max_file_wall_s']:.3f}s")
    print(f"RECOMMENDED --test-timeout = {recommended}  "
          f"(= ceil(worst × {args.multiplier}))")
    if bad:
        print(f"⚠ 參考解沒有全過的有 {len(bad)} 組——那不是「跑太慢」，"
              f"是驗收與契約對不起來。停。")
        for r in bad:
            print(f"   {r['task_id']} / {r['suite']} / {r['condition']}: "
                  f"{r['passed']}/{r['total']}")
        return 1
    print(f"wrote {out / 'timeout_probe.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
