#!/usr/bin/env python3
"""haiku_call — 一通無工具的 `claude -p --model haiku` 呼叫＋JSONL 紀錄＋花費上限。

寫考卷／寫錯解共用。環境清空、HOME 全新、cwd 空目錄、`--tools ""`（無任何工具）；CLI 沒有溫度設定＝預設值。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import subprocess
import tempfile
import threading
import time

BANK = pathlib.Path("/opt/ctlwork/bm_tasks/ctl37")
SRC = pathlib.Path("/opt/ctlwork/src/exercism-python/exercises/practice")
OUT = pathlib.Path(__file__).resolve().parents[1] / "exams_haiku_20261127"
CALLS = OUT / "calls.jsonl"
CAP_USD = 5.0
_LOCK = threading.Lock()
CLAUDE = "/opt/node22/bin/claude"


def sha(b: bytes | str) -> str:
    if isinstance(b, str):
        b = b.encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def tasks() -> list[str]:
    return json.loads((BANK / "MANIFEST.json").read_text())["task_order"]


def task_inputs(task: str) -> dict:
    slug = task[3:].replace("_", "-")
    goal_p = BANK / task / "workspace" / "goal.md"
    stub_p = SRC / slug / f"{slug.replace('-', '_')}.py"
    return {"slug": slug, "module": slug.replace("-", "_"), "goal_path": goal_p, "stub_path": stub_p,
            "goal": goal_p.read_text(encoding="utf-8"), "stub": stub_p.read_text(encoding="utf-8")}


def fill(template: str, **kw: str) -> str:
    for k, v in kw.items():
        template = template.replace("{" + k + "}", v)
    return template


def spent() -> float:
    if not CALLS.exists():
        return 0.0
    t = 0.0
    for line in CALLS.read_text().splitlines():
        try:
            t += float(json.loads(line).get("cost_usd") or 0)
        except Exception:
            pass
    return t


class CapExceeded(Exception):
    pass


def call_haiku(prompt: str, meta: dict, tries: int = 4) -> dict:
    """回傳 {text, cost_usd, model, rc, attempts, ok}；每次嘗試（含失敗）都寫一行 JSONL。"""
    last = None
    for attempt in range(1, tries + 1):
        with _LOCK:
            if spent() >= CAP_USD:
                raise CapExceeded(f"spend {spent():.4f} >= cap {CAP_USD}")
        t0 = time.time()
        with tempfile.TemporaryDirectory(prefix="hk_cwd_") as cwd, tempfile.TemporaryDirectory(prefix="hk_home_") as home:
            env = {"PATH": "/opt/node22/bin:/usr/local/bin:/usr/bin:/bin", "HOME": home, "LANG": "C.UTF-8",
                   "LC_ALL": "C.UTF-8", "DISABLE_AUTOUPDATER": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
                   "DISABLE_TELEMETRY": "1"}
            argv = [CLAUDE, "-p", "--model", "haiku", "--output-format", "json", "--tools", "",
                    "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                    "--no-session-persistence", "--", prompt]
            try:
                p = subprocess.run(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                                   text=True, timeout=300)
                rc, out, err = p.returncode, p.stdout, p.stderr
            except subprocess.TimeoutExpired:
                rc, out, err = -9, "", "timeout"
        resp = None
        try:
            resp = json.loads(out)
        except Exception:
            pass
        ok = bool(resp and not resp.get("is_error") and resp.get("subtype") == "success" and (resp.get("result") or "").strip())
        model = None
        if resp:
            mu = resp.get("modelUsage") or {}
            model = next((v.get("canonicalModel") or k for k, v in mu.items()), None)
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "attempt": attempt, "ok": ok, "rc": rc,
               "elapsed_s": round(time.time() - t0, 2), "meta": meta, "prompt_sha256": sha(prompt),
               "request_prompt": prompt, "model": model, "cost_usd": (resp or {}).get("total_cost_usd"),
               "response": resp, "stdout_if_unparsed": None if resp else out[:2000], "stderr": err[-1000:]}
        with _LOCK:
            with CALLS.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if ok:
            return {"text": resp["result"], "cost_usd": resp.get("total_cost_usd"), "model": model, "rc": rc,
                    "attempts": attempt, "ok": True}
        last = rec
        time.sleep(5 * attempt)
    return {"text": None, "cost_usd": None, "model": None, "rc": (last or {}).get("rc"), "attempts": tries, "ok": False}


FENCE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.S)


def extract_code(text: str) -> tuple[str, str]:
    """回傳 (code, how)：how＝fenced／unfenced。取第一個圍欄區塊（無圍欄＝整段文字，原樣）。"""
    m = FENCE.search(text)
    if m:
        return m.group(1), "fenced"
    return text, "unfenced"
