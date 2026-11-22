"""零設定的重開模式——`vacant do <agent>` 在沒有任務契約時的預設行為（T05／S3，2026-11-17）。

這支在架構裡承重什麼：把 `ops/redo/redo.py` 的 R3 政策做成使用者打得到的一個指令。
R3 是這個 repo 裡第一個在**原生 agent**上量到交付變好的設定（redo1：pi＋gemma-4-12b、34 題×5，
進行中數字見 `ops/redo/`；結論以該批的 `REPORT.md` 為準，這裡不引用數字）。

政策（與 `redo.py` 的 `_policy_stop`／`_policy_deliver` 逐條相同，`tests/test_adapters_restart.py` 對照）：
1. 驗收訊號＝專案在**開始那一刻**就有的測試檔（`*_test.py`／`test_*.py`，`unittest` 跑）。
   跑驗收之前把它們還原成開始時的內容；被改過的記在 `tests_tampered`，也**不寫回專案**。
2. 每一次嘗試：全新的暫存副本＋全新的 agent 行程。嘗試之間不留東西、不給失敗原文。
3. 驗收通過就停、交那一次；最多 `max_attempts` 次、每次 `attempt_timeout_s`、合計 `budget_s`。
   都沒過就交原件測試過最多的那一次（同分取後面那次），給人的訊息明講測試沒有全過。
4. 專案裡沒有測試檔 ⇒ 跑一次、照實交回、明講「沒有可執行的驗收」，不假裝檢查過。

交回：被選中那一次的工作區同步回專案（新增／修改／刪除），**測試檔除外**——跟使用者直接在專案裡跑
agent 的結果同一種形狀，只是多了「選哪一次」。

誠實邊界（改碼請保留）：
- 驗收＝「擋得住專案自己的測試會抓到的錯」，**不等於需求被滿足**。測試寫得弱，這一層就弱。
- 暫存副本不是沙箱：agent 以使用者的帳號執行，讀得到磁碟上的其他東西。
- 等預算是牆鐘的；重開通常讓 agent 用掉更多模型呼叫（redo1 約兩倍），這一層不省算力。
- 這一層不讀 agent 說了什麼；它只看測試。說「做完了」但測試沒過＝沒過。
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable

from .run import COPY_SKIP, Launch, run_agent, work_root
from . import workspace as safe

PATTERNS = ("*_test.py", "test_*.py")
ACC_TIMEOUT_S = 120.0

_UNITTEST_RUNNER = r"""
import json, sys, traceback, unittest
sys.path.insert(0, ".")
out = {"run": 0, "failures": 0, "errors": 0, "skipped": 0, "unexpected_successes": 0,
       "load_error": None, "first_problem": None}
for mod in sys.argv[1:]:
    try:
        suite = unittest.TestLoader().loadTestsFromName(mod)
    except BaseException:
        out["load_error"] = traceback.format_exc(limit=3)[-800:]
        break
    res = unittest.TestResult()
    suite.run(res)
    out["run"] += res.testsRun; out["failures"] += len(res.failures); out["errors"] += len(res.errors)
    out["skipped"] += len(res.skipped); out["unexpected_successes"] += len(res.unexpectedSuccesses)
    probs = res.failures + res.errors
    if probs and out["first_problem"] is None:
        out["first_problem"] = (str(probs[0][0]) + "\n" + probs[0][1])[-800:]
sys.stdout.flush()
print("\n@@VACANT_RESULT@@" + json.dumps(out))
"""


def _files(root: pathlib.Path) -> list[str]:
    out: list[str] = []
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in COPY_SKIP)
        for fn in fns:
            p = pathlib.Path(dp) / fn
            if p.is_file() and not p.is_symlink():
                out.append(p.relative_to(root).as_posix())
    return sorted(out)


def find_tests(root: pathlib.Path) -> list[str]:
    return [r for r in _files(root) if any(pathlib.PurePath(r.rsplit("/", 1)[-1]).match(p) for p in PATTERNS)]


def _clean_env(home: pathlib.Path) -> dict[str, str]:
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home), "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "PYTHONNOUSERSITE": "1"}


def acceptance(originals: dict[str, bytes], ws: pathlib.Path, timeout_s: float = ACC_TIMEOUT_S) -> dict:
    """在工作區的**副本**裡、把開始時的測試檔還原之後跑它們。驗收自己壞掉＝沒過（不是通過）。"""
    tests = sorted(originals)
    base: dict[str, Any] = {"accept": False, "tests": tests, "passed": None, "run": None,
                            "tests_tampered": [], "status": None, "first_problem": None}
    if not tests:
        return {**base, "status": "no_tests"}
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="vacant-acc-"))
    try:
        work = tmp / "w"
        safe.copy_workspace(ws, work, COPY_SKIP)
        for rel, want in originals.items():
            f = work / rel
            if not f.is_file() or f.is_symlink() or safe.read(work, rel) != want:
                base["tests_tampered"].append(rel)
                if f.is_symlink():
                    safe.unlink(work, rel)
                safe.write(work, rel, want)
        by_dir: dict[str, list[str]] = {}
        for rel in tests:
            d, _, name = rel.rpartition("/")
            by_dir.setdefault(d, []).append(name[:-3])
        agg = {"run": 0, "failures": 0, "errors": 0, "skipped": 0, "unexpected_successes": 0}
        first = None
        for d, mods in sorted(by_dir.items()):
            try:
                cp = subprocess.run([sys.executable, "-B", "-c", _UNITTEST_RUNNER, *mods],
                                    cwd=str(work / d if d else work), env=_clean_env(tmp),
                                    stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout_s)
                out = cp.stdout.decode("utf-8", "replace")
            except subprocess.TimeoutExpired:
                return {**base, "status": "timeout"}
            if "@@VACANT_RESULT@@" not in out:
                return {**base, "status": "runner_no_output", "first_problem": out[-800:]}
            r = json.loads(out.rsplit("@@VACANT_RESULT@@", 1)[1].strip().splitlines()[0])
            if r["load_error"]:
                return {**base, "status": "load_error", "first_problem": r["load_error"], "run": agg["run"]}
            for k in agg:
                agg[k] += r[k]
            first = first or r["first_problem"]
        bad = agg["failures"] + agg["errors"] + agg["unexpected_successes"]
        return {**base, "status": "ok", "run": agg["run"], "passed": agg["run"] - bad - agg["skipped"],
                "accept": agg["run"] > 0 and bad == 0 and agg["skipped"] == 0, "first_problem": first}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def deliver_index(accs: list[dict]) -> int:
    """交哪一次：第一個驗收通過的；都沒過就交原件測試過最多的（同分取最後一次）。＝redo.py `_policy_deliver`。"""
    for i, a in enumerate(accs):
        if a["accept"]:
            return i
    return max(range(len(accs)), key=lambda i: (accs[i]["passed"] or 0, i))


def _write_back(project: pathlib.Path, ws: pathlib.Path, protected: set[str]) -> dict[str, list[str]]:
    before, after = set(_files(project)), set(_files(ws))
    changed: dict[str, list[str]] = {"added": [], "modified": [], "deleted": []}
    for rel in sorted(after - protected):
        src = ws / rel
        mode = stat.S_IMODE(src.stat().st_mode)
        if rel in before:
            if (safe.read(project, rel) == safe.read(ws, rel)
                    and stat.S_IMODE((project / rel).stat().st_mode) == mode):
                continue
            changed["modified"].append(rel)
        else:
            changed["added"].append(rel)
        safe.write(project, rel, safe.read(ws, rel), mode)
    for rel in sorted(before - after - protected):
        safe.unlink(project, rel)
        changed["deleted"].append(rel)
    return changed


def run(project: pathlib.Path, build: Callable[[str, pathlib.Path], Launch], prompt: str, *,
        max_attempts: int = 3, attempt_timeout_s: float = 600.0, budget_s: float = 1800.0,
        min_attempt_s: float = 60.0, log: Callable[[str], None] | None = None) -> dict:
    project = project.absolute()
    with safe.directory(project):
        pass
    say = log or (lambda m: None)
    originals = {rel: (project / rel).read_bytes() for rel in find_tests(project)}
    if not originals:
        max_attempts = 1
        attempt_timeout_s = budget_s
    run_dir = work_root() / f"restart-{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    with safe.directory(run_dir, True):
        pass
    attempts: list[dict] = []
    keep: list[pathlib.Path] = []
    spent = 0.0
    while len(attempts) < max_attempts:
        remaining = budget_s - spent
        if attempts and remaining < min_attempt_s:
            break
        k = len(attempts) + 1
        ws = run_dir / f"attempt_{k}" / "w"
        safe.copy_workspace(project, ws, COPY_SKIP)
        launch = build(prompt, ws)
        say(f"attempt {k} of {max_attempts} (up to {min(attempt_timeout_s, remaining):.0f}s)")
        try:
            r = run_agent(launch, workspace=ws, timeout_s=min(attempt_timeout_s, remaining),
                          log_dir=run_dir / f"attempt_{k}" / "logs")
        finally:
            if launch.cleanup:
                launch.cleanup()
        spent += r["wall_ms"] / 1000.0
        acc = acceptance(originals, ws) if originals else {"accept": None, "passed": None, "status": "no_tests",
                                                           "tests_tampered": [], "run": None}
        attempts.append({"attempt": k, "accept": acc["accept"], "passed": acc["passed"], "run": acc["run"],
                         "status": acc["status"], "tests_tampered": acc["tests_tampered"],
                         "rc": r["rc"], "timed_out": r["timed_out"], "wall_s": round(r["wall_ms"] / 1000.0, 1),
                         "spawn_error": r["spawn_error"], "workspace": str(ws)})
        keep.append(ws)
        say(f"attempt {k}: " + ("no tests to run" if not originals else
                                f"tests {'PASS' if acc['accept'] else 'FAIL'} ({acc['passed']}/{acc['run']})"))
        if not originals or acc["accept"]:
            break
    d = deliver_index([{"accept": bool(a["accept"]), "passed": a["passed"]} for a in attempts])
    changed = _write_back(project, keep[d], set(originals))
    res = {"mode": "restart", "project": str(project), "tests": sorted(originals), "max_attempts": max_attempts,
           "accepted": None if not originals else bool(attempts[d]["accept"]),
           "delivered_attempt": d + 1, "attempts": attempts, "changed": changed,
           "agent_wall_s": round(spent, 1), "run_dir": str(run_dir)}
    (run_dir / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def summary(res: dict) -> str:
    n = len(res["attempts"])
    ch = res["changed"]
    files = f"{len(ch['added'])} added, {len(ch['modified'])} modified, {len(ch['deleted'])} deleted"
    if res["accepted"] is None:
        head = (f"[vacant] ran once; no executable acceptance (no *_test.py / test_*.py in the project), "
                f"so nothing was checked. {files}.")
    elif res["accepted"]:
        head = (f"[vacant] the project's tests pass on attempt {res['delivered_attempt']} "
                f"(up to {res.get('max_attempts', n)} allowed); delivered that attempt. {files}.")
    else:
        a = res["attempts"][res["delivered_attempt"] - 1]
        head = (f"[vacant] not all tests pass after {n} attempt(s); delivered attempt "
                f"{res['delivered_attempt']} ({a['passed'] or 0}/{a['run'] or 0} tests). {files}.")
    tam = sorted({t for a in res["attempts"] for t in a["tests_tampered"]})
    if tam:
        head += f"\n  the agent edited test files ({', '.join(tam)}); checked against the originals, not written back."
    return head + f"\n  attempts and logs: {res['run_dir']}"
