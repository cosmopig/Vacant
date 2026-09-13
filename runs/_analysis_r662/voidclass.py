#!/usr/bin/env python3
"""round662: infra_void 根因分類器。判準見同目錄 CRITERION.md。
機制導出：InfraVoid 全域只有 2 個 raise 點，分類法由那 2 點窮舉導出。"""
import json, re, pathlib, collections, sys

SANDBOX_PREFIX = "sandbox verifier unavailable:"
ENDPOINT_RE = re.compile(r"^(?P<agent>.+?) 重試 (?P<n>\d+) 次仍失敗：(?P<last>.*)$", re.S)
HTTP_RE = re.compile(r"HTTP Error (\d{3})")


def classify(msg: str) -> str:
    """回傳類別字串。無法解析一律 UNPARSED（不得安靜跳過）。"""
    if msg.startswith(SANDBOX_PREFIX):          # M3: 錨開頭，不是子字串
        return "SANDBOX"
    m = ENDPOINT_RE.match(msg)
    if not m:
        return "UNPARSED"
    last = m.group("last")
    h = HTTP_RE.search(last)
    if h:
        return f"HTTP_{h.group(1)}"             # M1: 真的讀碼
    if re.search(r"timed out|timeout|TimeoutError", last, re.I):
        return "TIMEOUT"
    if re.search(r"Connection|Remote end closed|URLError", last):
        return "CONN"
    return "OTHER:" + last[:60]


def load_voids(run_dir: pathlib.Path):
    """(arm, task_id, msg) 逐筆，不去重。"""
    out = []
    p = run_dir / "notes.jsonl"
    if not p.exists():
        raise SystemExit(f"BROKEN: 找不到 {p}")
    for line in p.open():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if "infra_void" in r:
            out.append((r.get("arm"), r.get("task_id"), r["infra_void"]))
    return out


def load_rows_success(run_dir: pathlib.Path):
    """task_id -> set(有 meets_demand 紀錄的臂)。Q3 的分母來源。"""
    d = collections.defaultdict(set)
    p = run_dir / "rows.jsonl"
    for line in p.open():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("meets_demand") is True:
            d[r.get("task_id")].add(r.get("arm"))
    return d


def http400_attempts(run_dir: pathlib.Path):
    """Q2：ok=false 且 error 含 HTTP Error 400 的呼叫，其 attempt 分佈。"""
    c = collections.Counter()
    p = run_dir / "calls.jsonl"
    for line in p.open():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("ok") is False and "HTTP Error 400" in str(r.get("error") or ""):
            c[r.get("attempt")] += 1
    return c
