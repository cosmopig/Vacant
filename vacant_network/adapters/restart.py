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
- `budget_s` 是**整個指令**的牆鐘上限：agent、驗收、複製都算在內，每次嘗試前預留一次驗收的時間
  （2026-11-19：只算 agent 時間時，confirm1／confirm1c 各有 1 格第三次嘗試跑到外層時限被砍、什麼都沒交回）。
  ⚠ 這點和 `redo.py` 的 R3 不同（R3 只算 agent 牆鐘）：產品比量到的政策略保守，同樣預算下最後一次嘗試可能短一點。
- 符號連結：agent 在工作區裡做的 symlink 一律不寫回；驗收還原測試檔時，路徑上的 symlink 會被換成真的目錄
  （記為 tests_tampered）；寫回時目的地路徑經過專案裡既有的 symlink、或刪除會穿過工作區裡的 symlink，就跳過並記在
  `changed["skipped"]`，不寫到專案外面、也不刪專案裡的檔（2026-11-19 日報 P1）。
- 這一層不讀 agent 說了什麼；它只看測試。說「做完了」但測試沒過＝沒過。
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable

from .run import COPY_SKIP, Launch, run_agent, work_root

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


def _through_symlink(root: pathlib.Path, rel: str) -> bool:
    """root/rel 的路徑上（含最後一段）有沒有 symlink。root 本身不算。"""
    p = root
    for part in pathlib.PurePosixPath(rel).parts:
        p = p / part
        if p.is_symlink():
            return True
    return False


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
        shutil.copytree(ws, work, symlinks=True, ignore=shutil.ignore_patterns(*COPY_SKIP))
        for rel, want in originals.items():
            f = work / rel
            if _through_symlink(work, rel):
                # agent 把測試檔或它的某一層目錄換成 symlink：拆掉換成真的，免得還原時寫到工作區外面
                base["tests_tampered"].append(rel)
                p = work
                for part in pathlib.PurePosixPath(rel).parts[:-1]:
                    p = p / part
                    if p.is_symlink():
                        p.unlink()
                    p.mkdir(exist_ok=True)
                if f.is_symlink():
                    f.unlink()
                f.write_bytes(want)
                continue
            if not f.is_file() or f.read_bytes() != want:
                base["tests_tampered"].append(rel)
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(want)
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
    changed: dict[str, list[str]] = {"added": [], "modified": [], "deleted": [], "skipped": []}
    for rel in sorted(after - protected):
        src, dst = ws / rel, project / rel
        if _through_symlink(project, rel):          # 會經過專案裡既有的 symlink 寫到別處
            changed["skipped"].append(rel)
            continue
        if rel in before:
            if dst.read_bytes() == src.read_bytes():
                continue
            changed["modified"].append(rel)
        else:
            changed["added"].append(rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for rel in sorted(before - after - protected):
        if _through_symlink(ws, rel) or _through_symlink(project, rel):
            changed["skipped"].append(rel)           # 工作區裡那一層被換成 symlink ⇒ 不是 agent 刪了檔，不動專案
            continue
        (project / rel).unlink()
        changed["deleted"].append(rel)
    return changed


def run(project: pathlib.Path, build: Callable[[str, pathlib.Path], Launch], prompt: str, *,
        max_attempts: int = 3, attempt_timeout_s: float = 600.0, budget_s: float = 1800.0,
        min_attempt_s: float = 60.0, log: Callable[[str], None] | None = None) -> dict:
    project = project.resolve()
    say = log or (lambda m: None)
    originals = {rel: (project / rel).read_bytes() for rel in find_tests(project)}
    if not originals:
        max_attempts = 1
        attempt_timeout_s = budget_s
    run_dir = work_root() / f"restart-{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    attempts: list[dict] = []
    keep: list[pathlib.Path] = []
    spent = 0.0
    t0 = time.monotonic()
    reserve = min(ACC_TIMEOUT_S, budget_s / 10) if originals else 0.0   # 每次嘗試後留給驗收的時間
    while len(attempts) < max_attempts:
        remaining = budget_s - (time.monotonic() - t0) - reserve
        if attempts and remaining < min_attempt_s:
            break
        remaining = max(remaining, 1.0)
        k = len(attempts) + 1
        ws = run_dir / f"attempt_{k}" / "w"
        shutil.copytree(project, ws, symlinks=True, ignore=shutil.ignore_patterns(*COPY_SKIP))
        launch = build(prompt, ws)
        say(f"attempt {k} of {max_attempts} (up to {min(attempt_timeout_s, remaining):.0f}s)")
        try:
            r = run_agent(launch, workspace=ws, timeout_s=min(attempt_timeout_s, remaining),
                          log_dir=run_dir / f"attempt_{k}" / "logs")
        finally:
            if launch.cleanup:
                launch.cleanup()
        spent += r["wall_ms"] / 1000.0
        acc_t = max(5.0, min(ACC_TIMEOUT_S, budget_s - (time.monotonic() - t0)))
        acc = acceptance(originals, ws, acc_t) if originals else {"accept": None, "passed": None, "status": "no_tests",
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
           "agent_wall_s": round(spent, 1), "total_wall_s": round(time.monotonic() - t0, 1),
           "run_dir": str(run_dir)}
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
    if ch.get("skipped"):
        head += (f"\n  not written back ({len(ch['skipped'])}): the path goes through a symbolic link "
                 f"({', '.join(ch['skipped'][:5])}{' …' if len(ch['skipped']) > 5 else ''}); see the attempt workspace.")
    tam = sorted({t for a in res["attempts"] for t in a["tests_tampered"]})
    if tam:
        head += f"\n  the agent edited test files ({', '.join(tam)}); checked against the originals, not written back."
    return head + f"\n  attempts and logs: {res['run_dir']}"
