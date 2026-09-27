"""批次的運作紀錄（2026-09-27；人類：「就繼續，但有超時等的最後要一並記錄」）。

u274（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md`）在人類的兩台機器上大多數跑碰到 1800 秒時限（RUNLOG §17）。
這一支把**運作面**整批記下來，和預註冊的主要分析（`unseen_analyze.py`）一起交；它**不是**預註冊的一部分，是事後加的描述，
在批次結束之前寫好、commit（寫的時候沒有看任何評分）。

**只讀運作資料，不讀評分**：每一跑的 `result.json` 只讀 `started_at`／`finished_at`／`agent_setup`／`agent_execution`／
`exception_info`（不讀 `verifier_result`），`config.json` 讀機器（`/up/<名字>/`），代理帳本讀每一通的狀態、延遲、提示長度、串流錯誤，
`progress.jsonl` 讀驅動記下的跑。不讀 `verifier/`、`agent/pi.txt`、答案檔。

每一跑：組別、題目、機器、**並行時期**（依開始時間落在哪一段 `--period`）、開始／結束、牆鐘、agent 執行秒數、例外類型（`AgentTimeoutError`＝1800 秒時限）、
模型請求數（成功／失敗／串流錯誤）、提示 token 中位數、延遲中位數、驅動有沒有記到（停驅動時在跑的那幾跑沒有 `progress.jsonl` 的行）。
加總：組別 × 時期 × 機器的跑數、時限次數、牆鐘中位數；每台機器的延遲與錯誤；沒開始的題（時間上限）；`_void_first/` 的補跑。

    python3 ops/eval/local/ops_report.py --jobs <jobs> --ledger <代理 ledger 目錄> --prefix u274 \
        --manifest ops/eval/evidence_20260927_nocap/unseen/UNSEEN_MANIFEST.json \
        --period 4+4=2026-09-27T10:50:44Z --period 3+3=2026-09-27T11:28:25Z --out <輸出目錄>
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import re
import statistics
from typing import Any


def _t(s: str | None) -> float | None:
    if not s:
        return None
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def _span(d: dict[str, Any] | None) -> float | None:
    if not d or not d.get("started_at") or not d.get("finished_at"):
        return None
    return round(_t(d["finished_at"]) - _t(d["started_at"]), 1)  # type: ignore[operator]


def _med(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 1) if xs else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--ledger", required=True, type=pathlib.Path)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--manifest", type=pathlib.Path)
    ap.add_argument("--period", action="append", default=[], help="名字=UTC 開始時間（依時間排序）")
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args(argv)
    periods = sorted(((_t(v), k) for k, v in (p.split("=", 1) for p in a.period)), key=lambda x: x[0] or 0)

    def period_of(ts: float | None) -> str:
        name = "before"
        for start, k in periods:
            if ts is not None and start is not None and ts >= start:
                name = k
        return name

    calls: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for ln in (a.ledger / "ledger.jsonl").read_text().splitlines():
        if f'"{a.prefix}-g12-off-' not in ln:
            continue
        r = json.loads(ln)
        calls[r["tag"]].append(r)
    logged = set()
    if (a.jobs / "progress.jsonl").is_file():
        for ln in (a.jobs / "progress.jsonl").read_text().splitlines():
            try:
                r = json.loads(ln)
                logged.add((str(r["task"]), r["arm"], int(r["sample"])))
            except (ValueError, KeyError):
                continue
    rows = []
    for res in sorted(a.jobs.glob("g12-off-*-s*/*/dabstep-*__*/result.json")):
        trial = res.parent
        arm, s = trial.parents[1].name.removeprefix("g12-off-").rsplit("-s", 1)
        task = trial.name.split("__")[0].removeprefix("dabstep-")
        r = json.loads(res.read_text())
        cfg = (trial / "config.json").read_text(errors="replace") if (trial / "config.json").is_file() else ""
        m = re.search(r"/up/([A-Za-z0-9_.-]+)/", cfg)
        tag = f"{a.prefix}-g12-off-{arm}-{task}-s{s}"
        cs = calls.get(tag, [])
        ok = [c for c in cs if c.get("status") == 200 and not c.get("stream_error")]
        start = _t(r.get("started_at"))
        rows.append({
            "task": task, "arm": arm, "sample": int(s), "trial": trial.name, "job": trial.parent.name,
            "upstream": m.group(1) if m else None, "period": period_of(start),
            "started_at": r.get("started_at"), "finished_at": r.get("finished_at"),
            "wall_s": _span(r), "agent_setup_s": _span(r.get("agent_setup")),
            "agent_execution_s": _span(r.get("agent_execution")),
            "exception": (r.get("exception_info") or {}).get("exception_type"),
            "timeout": (r.get("exception_info") or {}).get("exception_type") == "AgentTimeoutError",
            "requests_ok": len(ok), "requests_failed": sum(1 for c in cs if c.get("status") != 200),
            "stream_errors": sum(1 for c in cs if c.get("stream_error")),
            "prompt_tokens_median": _med([float((c.get("usage") or {}).get("prompt_tokens") or 0) for c in ok
                                          if (c.get("usage") or {}).get("prompt_tokens")]),
            "latency_median_s": _med([float(c.get("latency_s") or 0) for c in ok]),
            "driver_logged": (task, arm, int(s)) in logged,
            "void_rerun_copy": False})
    for res in sorted(a.jobs.glob("_void_first/*/dabstep-*__*/result.json")):
        rows.append({"task": res.parent.name.split("__")[0].removeprefix("dabstep-"), "void_rerun_copy": True,
                     "moved_dir": res.parent.parent.name,
                     "exception": (json.loads(res.read_text()).get("exception_info") or {}).get("exception_type")})
    main_rows = [x for x in rows if not x["void_rerun_copy"]]
    groups: dict[str, dict[str, Any]] = {}
    for x in main_rows:
        for key in (f"{x['arm']}", f"{x['arm']}／{x['period']}", f"{x['arm']}／{x['period']}／{x['upstream']}"):
            g = groups.setdefault(key, {"runs": 0, "timeouts": 0, "other_exceptions": 0, "wall": []})
            g["runs"] += 1
            g["timeouts"] += int(x["timeout"])
            g["other_exceptions"] += int(bool(x["exception"]) and not x["timeout"])
            if x["wall_s"] is not None:
                g["wall"].append(x["wall_s"])
    for g in groups.values():
        g["wall_median_s"] = _med(g.pop("wall"))
    per_up: dict[str, dict[str, Any]] = {}
    for tag, cs in calls.items():
        for c in cs:
            u = per_up.setdefault(c.get("upstream") or "?", {"calls": 0, "failed": 0, "stream_errors": 0, "lat": [],
                                                              "tok": [], "errors": collections.Counter()})
            u["calls"] += 1
            u["failed"] += int(c.get("status") != 200)
            if c.get("stream_error"):
                u["stream_errors"] += 1
                u["errors"][str(c["stream_error"])[:80]] += 1
            if c.get("status") == 200:
                u["lat"].append(float(c.get("latency_s") or 0))
                if (c.get("usage") or {}).get("prompt_tokens"):
                    u["tok"].append(float(c["usage"]["prompt_tokens"]))
    for u in per_up.values():
        lat = sorted(u.pop("lat"))
        u["latency_p50_s"] = _med(lat)
        u["latency_p90_s"] = round(lat[int(0.9 * len(lat))], 1) if lat else None
        u["prompt_tokens_median"] = _med(u.pop("tok"))
        u["errors"] = dict(u["errors"])
    started = {x["task"] for x in main_rows}
    not_started = []
    if a.manifest:
        not_started = [t["task"] for t in json.loads(a.manifest.read_text())["tasks"] if t["task"] not in started]
    half = sorted(t for t in started if len({x["arm"] for x in main_rows if x["task"] == t}) < 2)
    summ = {"runs": len(main_rows), "timeouts": sum(x["timeout"] for x in main_rows),
            "by_group": dict(sorted(groups.items())), "by_machine": per_up,
            "runs_not_logged_by_driver": [f"{x['task']}-{x['arm']}" for x in main_rows if not x["driver_logged"]],
            "runs_with_zero_ok_requests": [f"{x['task']}-{x['arm']}" for x in main_rows if not x["requests_ok"]],
            "tasks_started": len(started), "tasks_not_started": len(not_started), "tasks_one_arm_only": half,
            "void_rerun_copies": [x for x in rows if x["void_rerun_copy"]]}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "ops_runs.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n")
    (a.out / "ops_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1) + "\n")
    lines = ["# 運作紀錄（`ops/eval/local/ops_report.py`；不含評分）", "",
             f"跑數 {summ['runs']}、碰到 1800 秒時限 {summ['timeouts']}；開始的題 {summ['tasks_started']}、"
             f"沒開始的題 {summ['tasks_not_started']}、只有一組的題 {len(half)}。", "",
             "| 組別｜時期｜機器 | 跑數 | 時限 | 其他例外 | 牆鐘中位數（秒） |", "|---|---|---|---|---|"]
    lines += [f"| {k} | {g['runs']} | {g['timeouts']} | {g['other_exceptions']} | {g['wall_median_s']} |"
              for k, g in sorted(groups.items())]
    lines += ["", "| 機器 | 請求 | 失敗 | 串流錯誤 | 延遲 p50／p90（秒） | 提示 token 中位數 |", "|---|---|---|---|---|---|"]
    lines += [f"| {k} | {u['calls']} | {u['failed']} | {u['stream_errors']} | {u['latency_p50_s']}／{u['latency_p90_s']} "
              f"| {u['prompt_tokens_median']} |" for k, u in sorted(per_up.items())]
    lines += ["", f"驅動沒有記到的跑（停驅動時在跑）：{len(summ['runs_not_logged_by_driver'])}；"
              f"一通成功請求都沒有的跑：{len(summ['runs_with_zero_ok_requests'])}；"
              f"infra_void 補跑移開的：{len(summ['void_rerun_copies'])}。", ""]
    (a.out / "ops_report.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
