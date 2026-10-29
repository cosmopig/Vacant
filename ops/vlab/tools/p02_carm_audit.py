#!/usr/bin/env python3
"""p02_carm_audit — GPT 審查 P0-2 的 C 臂逐題紀錄量具（round 173）。

背景（GPT_REVIEW_20261028.md P0-2 驗收）：
  - 「34 題的測試發現與實際執行均有逐題可查紀錄」
  - 「修改測試、塞 helper、混合方言做負對照」（負對照＝本倉 unit 層，見
    tests/test_p02_star_test_discovery.py A2/A3/B3/C1/C2；本量具不重複）
  - 「無 no_suite 假成功」（unit 層 D2 已釘；本量具看 C 臂實跑有沒有零測試過門）
本量具的分工＝**實跑層的逐題紀錄**：e002 的 C 臂（Vacant 安裝形態，pi 真跑
polyglot_py）每格落盤的 events.jsonl（agent 的工具流）、vacant_home.tgz 裡的
chain.ndjson（Vacant 的 review 判定）、score.json（隱藏評分結果）。逐題可查、
可重算、跑批中也能量。

誠實規則（不變量 5）：
  - 格未完成（無 cell.json）→ state=incomplete，全部 NA/None，不計入任何判定。
  - C 格完成但 vacant_home.tgz 缺（Vacant 沒裝上）→ c_installed=FAIL（線路斷）。
  - C 格完成但 chain.ndjson 找不到 review 條目 → review=NO_EVIDENCE（不是 allow，
    也不是 refuse；門有沒有跑是 UNKNOWN）。
  - score.json 缺 → score=NO_EVIDENCE。score 的 pass/fail 是**測得結果**（模型行
    為），不影響退出碼——本量具驗的是「逐題紀錄是否存在」，不是模型對錯。
  - test_files_referenced／test_exec_evidence 是**證據**（agent 有沒有碰到/跑
    *_test.py），空清單是實測觀察，不是 FAIL。
  - 期望題集不寫死：從該實驗的 A 臂 cell 名推導（A 臂沒裝 Vacant，是完整題集的
    見證）；找不到 A 臂就從所有 cell 名推導，並在輸出裡標明 source。

本腳本是**獨立量具**（與 e002_wiring_gauge.py 同規矩）：只讀 /srv/vlab/runs
下的 cell 目錄；不碰 cell.py / labd.py / report.py；預設不寫任何檔（--out 才寫）。

用法：
  python3 ops/vlab/tools/p02_carm_audit.py <exp> [--base /srv/vlab/runs] [--out PATH]
  python3 ops/vlab/tools/p02_carm_audit.py --selftest
輸出 JSON：{exp, base, n_cells, expected_tasks, cells:[...], per_task:[...],
           criteria:{...}}
退出碼：0 無線路 FAIL；1 有 FAIL；2 selftest 失敗或輸入不可讀。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tarfile
from pathlib import Path

TESTFILE = re.compile(r"\b([A-Za-z0-9_][A-Za-z0-9_]*_(?:test|Test)\.py|test_[A-Za-z0-9_]+\.py)\b")
# 「執行證據」＝bash 工具參數裡，解釋器/runner 緊接著（或同命令裡）出現測試檔名
EXEC = re.compile(r"(?:\bpython[0-9.]*\b|\bpytest\b|\bunittest\b)[^\n]{0,80}?([A-Za-z0-9_][A-Za-z0-9_]*_(?:test|Test)\.py|test_[A-Za-z0-9_]+\.py)")


def _load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _read_chain(cell: Path) -> list[dict]:
    """讀 vacant_home.tgz 裡的 chain.ndjson（找不到 → []）。只讀，不解壓到磁碟。"""
    tgz = cell / "vacant_home.tgz"
    if not tgz.is_file():
        return []
    out: list[dict] = []
    try:
        with tarfile.open(tgz, "r:gz") as tf:
            for m in tf.getmembers():
                if m.isfile() and m.name.endswith("chain.ndjson"):
                    f = tf.extractfile(m)
                    if f is None:
                        continue
                    for line in f.read().decode("utf-8", errors="replace").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            e = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(e, dict) and e.get("type") == "review":
                            out.append(e.get("payload") or {})
    except (tarfile.TarError, OSError):
        return []
    return out


def _scan_events(cell: Path) -> dict:
    """events.jsonl：agent 有無參考/執行測試檔（證據，不是判定）。"""
    ev = cell / "events.jsonl"
    if not ev.is_file():
        return {"test_files_referenced": [], "test_exec_evidence": None,
                "exec_samples": []}
    try:
        text = ev.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"test_files_referenced": [], "test_exec_evidence": None,
                "exec_samples": []}
    refs = sorted(set(TESTFILE.findall(text)))
    execs = sorted(set(EXEC.findall(text)))
    samples: list[str] = []
    if execs:
        for line in text.splitlines():
            if EXEC.search(line):
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("type") in ("tool_execution_start", "tool_execution_update",
                                    "tool_execution_end"):
                    args = e.get("args") or {}
                    cmd = args.get("command") if isinstance(args, dict) else None
                    if isinstance(cmd, str) and cmd.strip() and cmd not in samples:
                        samples.append(cmd.strip()[:200])
                if len(samples) >= 3:
                    break
    return {"test_files_referenced": refs,
            "test_exec_evidence": bool(execs),
            "exec_samples": samples}


def cell_record(cell: Path) -> dict:
    cj = _load_json(cell / "cell.json")
    name = cell.name
    # cell 名形如 polyglot_py-pg_bowling-pi-C-r1：suite-task…-agent-arm-rN（從右解析，
    # task 可含連字號）。.infra-<ts> 隔離目錄（infra 失敗被隔離）不解析任務，
    # 只記為 quarantined（與 e002_wiring_gauge 同樣把 .infra- 排除在判定外）。
    if ".infra-" in name:
        return {"cell": name, "task": None, "state": "quarantined_infra",
                "arm": None, "c_installed": None, "review": None, "score": None,
                "test_files_referenced": None, "test_exec_evidence": None,
                "infra": None}
    parts = name.split("-")
    task = "-".join(parts[1:-3]) if len(parts) >= 5 else None
    rec = {"cell": name, "task": task,
           "state": "complete" if cj is not None else "incomplete"}
    if cj is None:
        rec.update({"arm": None, "c_installed": None, "review": None,
                    "score": None, "test_files_referenced": None,
                    "test_exec_evidence": None, "infra": None})
        return rec
    arm = str(cj.get("arm") or "")
    rec["arm"] = arm
    rec["infra"] = "OK" if (cj.get("agent_rc") == 0 and not cj.get("timed_out")) else "BAD"
    if not arm.startswith("C"):
        rec.update({"c_installed": None, "review": None, "score": None,
                    "test_files_referenced": None, "test_exec_evidence": None})
        return rec
    # C 臂：Vacant 安裝＋review 判定＋評分＋測試檔證據
    rec["c_installed"] = (cell / "vacant_home.tgz").is_file() and (cj.get("install_rc") in (None, 0))
    reviews = _read_chain(cell)
    if reviews:
        # 全數留檔（逐題可查）；末條是最終判定。
        rec["review"] = [{"action": r.get("action"),
                          "findings": r.get("findings") or [],
                          "deliverables": r.get("deliverables") or []} for r in reviews]
    else:
        rec["review"] = None
    sc = _load_json(cell / "score.json")
    rec["score"] = {"pass": sc.get("pass"), "tests_passed": sc.get("tests_passed"),
                    "tests_total": sc.get("tests_total")} if sc is not None else None
    ev = _scan_events(cell)
    rec["test_files_referenced"] = ev["test_files_referenced"]
    rec["test_exec_evidence"] = ev["test_exec_evidence"]
    if ev["exec_samples"]:
        rec["exec_samples"] = ev["exec_samples"]
    return rec


def expected_tasks(cells: list[dict]) -> tuple[list[str], str]:
    a = sorted({r["task"] for r in cells if r.get("arm") == "A" and r.get("task")})
    if a:
        return a, "arm_A"
    return sorted({r["task"] for r in cells if r.get("task")}), "all_cells"


def per_task_table(records: list[dict], tasks: list[str]) -> list[dict]:
    out = []
    for t in tasks:
        rows = [r for r in records if r.get("task") == t and r.get("arm") == "C"]
        comp = [r for r in rows if r["state"] == "complete"]
        out.append({
            "task": t,
            "c_cells": len(rows),
            "c_complete": len(comp),
            "c_installed_all": (len(comp) > 0 and all(r["c_installed"] for r in comp)) or None,
            "review_actions": [[x["action"] for x in r["review"]] if r.get("review") else None
                              for r in comp],
            "score": [r["score"] for r in comp if r.get("score") is not None],
            "test_files_referenced": sorted({f for r in comp for f in (r.get("test_files_referenced") or [])}),
            "test_exec_evidence_all": (len(comp) > 0 and all(r.get("test_exec_evidence") for r in comp)) or None,
            "record_complete": bool(comp) and all(
                r["c_installed"] and r.get("review") is not None and r.get("score") is not None
                for r in comp),
        })
    return out


def criteria(records: list[dict], per_task: list[dict]) -> dict:
    c = [r for r in records if r.get("arm") == "C" and r["state"] == "complete"]

    def final_action(r):
        rev = r.get("review")
        return rev[-1].get("action") if isinstance(rev, list) and rev else None

    return {
        "c_complete_cells": len(c),
        "c_installed_FAIL": sum(1 for r in c if not r["c_installed"]),
        "review_NO_EVIDENCE": sum(1 for r in c if r.get("review") is None),
        "review_allow": sum(1 for r in c if final_action(r) == "allow"),
        "review_refuse": sum(1 for r in c if final_action(r) == "refuse"),
        "review_other": sum(1 for r in c if final_action(r) not in (None, "allow", "refuse")),
        "score_NO_EVIDENCE": sum(1 for r in c if r.get("score") is None),
        "score_pass": sum(1 for r in c if (r.get("score") or {}).get("pass") is True),
        "score_fail": sum(1 for r in c if (r.get("score") or {}).get("pass") is False),
        "score_zero_tests": sum(1 for r in c if (r.get("score") or {}).get("tests_total") == 0),
        "test_files_referenced_in_all": sum(1 for r in c if r.get("test_files_referenced")),
        "test_exec_evidence_in_all": sum(1 for r in c if r.get("test_exec_evidence") is True),
        "tasks_with_complete_record": sum(1 for p in per_task if p["record_complete"]),
        "tasks_total": len(per_task),
    }


def selftest() -> int:
    """合成兩格（C 完成／C 未完成），驗抽取邏輯。"""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "runs" / "exp_p02"
        good = base / "polyglot_py-pg_demo-pi-C-r1"
        good.mkdir(parents=True)
        (good / "cell.json").write_text(json.dumps(
            {"arm": "C", "agent_rc": 0, "timed_out": False, "install_rc": 0}), encoding="utf-8")
        (good / "score.json").write_text(json.dumps(
            {"pass": True, "tests_passed": 31, "tests_total": 31}), encoding="utf-8")
        (good / "events.jsonl").write_text(
            '{"type":"tool_execution_end","args":{"command":"python bowling_test.py"}}\n',
            encoding="utf-8")
        tgz = good / "vacant_home.tgz"
        import io
        with tarfile.open(tgz, "w:gz") as tf:
            payload = json.dumps({"type": "review", "payload": {
                "action": "allow", "deliverables": ["demo.py"], "findings": []}})
            data = payload.encode()  # noqa
            info = tarfile.TarInfo("home/.vacant/trace/p/chain.ndjson")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        bad = base / "polyglot_py-pg_other-pi-C-r1"
        bad.mkdir(parents=True)   # 無 cell.json → incomplete
        a = base / "polyglot_py-pg_demo-pi-A-r1"
        a.mkdir()
        (a / "cell.json").write_text(json.dumps({"arm": "A", "agent_rc": 0, "timed_out": False}), encoding="utf-8")

        records = [cell_record(p) for p in sorted(base.iterdir())]
        tasks, source = expected_tasks(records)
        table = per_task_table(records, tasks)
        crit = criteria(records, table)
        ok = (
            tasks == ["pg_demo"] and source == "arm_A"
            and crit["c_complete_cells"] == 1
            and crit["review_allow"] == 1
            and crit["score_pass"] == 1
            and crit["tasks_with_complete_record"] == 1
            and any(r["cell"].endswith("-C-r1") and r["test_exec_evidence"] is True
                    and r["test_files_referenced"] == ["bowling_test.py"] for r in records)
        )
        print(json.dumps({"selftest": "PASS" if ok else "FAIL", "criteria": crit},
                         ensure_ascii=False))
        return 0 if ok else 2
    return 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exp", nargs="?", help="實驗名（/srv/vlab/runs 下的目錄名）")
    ap.add_argument("--base", default="/srv/vlab/runs")
    ap.add_argument("--out", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.exp:
        ap.error("exp 或 --selftest 必給其一")
    run = Path(a.base) / a.exp
    if not run.is_dir():
        print(json.dumps({"error": f"找不到執行目錄 {run}"}, ensure_ascii=False), file=sys.stderr)
        return 2
    records = [cell_record(p) for p in sorted(p for p in run.iterdir() if p.is_dir())]
    if not records:
        print(json.dumps({"error": "no cells"}, ensure_ascii=False), file=sys.stderr)
        return 2
    tasks, source = expected_tasks(records)
    table = per_task_table(records, tasks)
    crit = criteria(records, table)
    doc = {"exp": a.exp, "base": str(a.base), "n_cells": len(records),
           "expected_tasks": tasks, "expected_tasks_source": source,
           "cells": records, "per_task": table, "criteria": crit}
    text = json.dumps(doc, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    # 只算「線路斷」為 FAIL；score 的 pass/fail 是模型實測結果，不影響退出碼。
    fails = crit["c_installed_FAIL"]
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
