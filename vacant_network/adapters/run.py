"""run — **`vacant do <agent> "<任務>"`：最通用的那一層，行程＋工作區＋收件口。**

這支在架構裡承重什麼（`adapters/__init__.py` 共通面 1；報告 §11「能啟動完整 CLI agent：
包它的任務生命週期、工作區與成果交接，不必接管其每輪推理」）：

1. 契約所在的專案根目錄**複製**到一個隔離工作區（`git init` 過，所以會找 git 根的
   agent——OpenCode——也把它當專案根）。agent 在那裡工作；原專案不動。
2. 以 agent **自己的** headless 模式跑（`claude -p`、`codex exec`、`opencode run`、
   `pi -p`；或任何指令），`cwd` 與 `PWD` 都是工作區（agentlane 36609614 的洞：
   只設 `cwd` 不設 `PWD` 時 OpenCode 會寫到啟動目錄）。
   **使用者自己的設定原封不動**：不搬 `CODEX_HOME`／`CLAUDE_CONFIG_DIR`／
   `PI_CODING_AGENT_DIR`，不注入模型端點。要加掛鉤時只用各家的**加法式**入口。
3. 結束後量「原專案有沒有被動到」（`workspace_escape`）——寫到工作區外面是觀測到的
   事實，進帳本，不猜。
4. 把工作區交進收件口（`intake.flow.submit`）。契約允許多次嘗試時，把失敗摘要接在
   原提示後面再跑一次（只在工作區裡重做；**agent 在外部造成的效果不會被回滾**）。
5. 不發布。發布是 `vacant release`，由收件端自己重驗一切。

## 誠實邊界（改碼請保留）

1. 隔離工作區**不是沙箱**：agent 以你的帳號執行，讀寫得到你讀寫得到的一切。
   `workspace_escape` 只量「原專案」（含 `.git` 的設定／hooks／refs／index、`__pycache__`、
   空目錄——那些是會在你下一次 `git` 指令時執行程式碼的地方），量不到它寫去別處或打了
   外部 API；你自己同時在原專案裡的修改也會被算進去。
2. 退出碼 0 的 agent 不代表交件；這裡的裁決只來自契約的驗證器。
3. 中斷（Ctrl-C、SIGTERM、SIGHUP）會殺掉 agent 的行程群組並在帳本記 `infra_void`
   （stage=interrupted）。自己 `setsid` 出去的子孫行程不在那個群組裡，殺不到。
4. 只在有必要主張 **FAIL** 時才重試：hold／escalate（等審查、等獨立證據、審查分歧）
   不是 agent 改得動的，重跑只會重複它在外部造成的效果。
"""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import shutil
import signal
import subprocess
import time
from typing import Any, Callable

from ..intake import flow
from ..intake.contract import Contract
from .hookpolicy import vacant_state_dir

COPY_SKIP = frozenset({".git", "node_modules", "__pycache__", ".venv", ".pytest_cache"})
FEEDBACK_MODES = ("localized", "generic", "none")
#: `.git` 裡**會影響下一次 git 指令行為**的部分（objects 是內容定址的，多了不改變行為）。
_GIT_WATCH = ("config", "HEAD", "index", "packed-refs", "hooks", "refs", "info")


class Interrupted(Exception):
    """SIGTERM／SIGHUP 轉成例外，讓 `finally` 有機會殺掉 agent、寫帳本。"""


def origin_digest(base: pathlib.Path, skip: set[pathlib.Path]) -> dict[str, str]:
    """原專案的逃逸量具：`{相對路徑: 內容雜湊或 "dir"}`。

    不用 `vrun.wshash`（那支的排除清單是為了 R530 的可比性，刻意不看 `.git`、
    `__pycache__`、空目錄——正好是植入程式碼最方便的地方）。
    """
    import hashlib

    def leaf(fp: pathlib.Path) -> str:
        # 懸空的連結（husky／pre-commit 留下的 `.git/hooks/*` 很常見）、讀不了的檔案：
        # 記下它的樣子，不要讓量具自己崩掉（崩掉的話那一跑就沒有帳本紀錄）。
        try:
            if os.path.islink(fp):
                return "link:" + os.readlink(fp)
            st = fp.lstat()
            if st.st_size > 64 * 1024 * 1024:
                return f"big:{st.st_size}:{st.st_mtime_ns}"
            return hashlib.sha256(fp.read_bytes()).hexdigest() + f":{st.st_mode:o}"
        except OSError:
            return "unreadable"

    out: dict[str, str] = {}
    base = base.resolve()
    for root, dirs, files in os.walk(base, followlinks=False):
        r = pathlib.Path(root)
        rel_root = r.relative_to(base).as_posix()
        keep = []
        for d in sorted(dirs):
            full = r / d
            if full.resolve() in skip or d in ("node_modules", ".venv"):
                continue
            if rel_root == "." and d == ".git":
                for name in _GIT_WATCH:
                    gp = full / name
                    if gp.is_dir() and not gp.is_symlink():
                        for g2, _dd, ff in os.walk(gp):
                            for f in ff:
                                fp = pathlib.Path(g2) / f
                                out[fp.relative_to(base).as_posix()] = leaf(fp)
                    elif gp.is_symlink() or gp.exists():
                        out[f".git/{name}"] = leaf(gp)
                continue
            keep.append(d)
            out[(full.relative_to(base)).as_posix() + "/"] = "dir"
        dirs[:] = keep
        for f in files:
            fp = r / f
            out[fp.relative_to(base).as_posix()] = leaf(fp)
    return out


def _diff(a: dict[str, str], b: dict[str, str]) -> list[str]:
    return sorted({k for k in set(a) | set(b) if a.get(k) != b.get(k)})


def work_root() -> pathlib.Path:
    """隔離工作區放哪裡。**不可以在 `$VACANT_HOME` 底下**：那整棵樹是掛鉤政策保護的
    （金鑰、隔離區、帳本），agent 在裡面寫檔會被自己的掛鉤擋下——2026-09-24 端到端
    實測抓到的（pi 的全域 extension 正確地拒絕了寫入）。預設 `~/.vacant-work`。"""
    from ..intake.statepaths import work_dir
    return work_dir()


@dataclasses.dataclass
class Launch:
    argv: list[str]
    env: dict[str, str] = dataclasses.field(default_factory=dict)
    note: str = ""
    cleanup: Callable[[], None] | None = None


def _skip_dirs(contract: Contract) -> set[pathlib.Path]:
    """不複製、不量逃逸的目錄：收件端的目的端（若在專案裡），以及 Vacant 自己的狀態與
    工作區根目錄（`VACANT_HOME` 設在專案裡時——CI 常見——金鑰會被複製進 agent 的工作區，
    第二跑還會把工作區遞迴複製進工作區）。"""
    src = contract.base_dir
    out: set[pathlib.Path] = {vacant_state_dir().resolve(), work_root().resolve()}
    spec = str(contract.release.get("destination") or "")
    if spec.startswith("dir:"):
        p = pathlib.Path(spec[4:]).expanduser()
        out.add((p if p.is_absolute() else src / p).resolve())
    return out


def prepare_workspace(contract: Contract, dest: pathlib.Path) -> pathlib.Path:
    """把專案根複製成一個新的 git 專案（一個初始 commit）。"""
    src = contract.base_dir
    if dest.exists():
        shutil.rmtree(dest)
    # 契約的放行目的端若在專案裡（`dir:published`），不複製——那是收件端的東西，
    # 不是 agent 的材料；複製進去還會被下一次交件當成成果的一部分。
    skip_abs = _skip_dirs(contract)

    def ignore(d: str, names: list[str]) -> set[str]:
        out = {n for n in names if n in COPY_SKIP}
        for n in names:
            if (pathlib.Path(d) / n).resolve() in skip_abs:
                out.add(n)
        return out
    shutil.copytree(src, dest, symlinks=True, ignore=ignore)
    env = {**os.environ, "GIT_AUTHOR_NAME": "vacant", "GIT_AUTHOR_EMAIL": "vacant@localhost",
           "GIT_COMMITTER_NAME": "vacant", "GIT_COMMITTER_EMAIL": "vacant@localhost"}
    subprocess.run(["git", "init", "-q", str(dest)], check=True, env=env)
    subprocess.run(["git", "-C", str(dest), "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", str(dest), "commit", "-q", "--allow-empty", "-m",
                    "vacant: task start"], check=True, env=env)
    return dest


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def run_agent(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
              log_dir: pathlib.Path) -> dict[str, Any]:
    env = {**os.environ, **launch.env, "PWD": str(workspace)}
    log_dir.mkdir(parents=True, exist_ok=True)
    out_p, err_p = log_dir / "agent_stdout.log", log_dir / "agent_stderr.log"
    t0 = time.time()
    timed_out = False
    rc: int | None = None
    spawn_error = None
    with out_p.open("wb") as out, err_p.open("wb") as err:
        try:
            proc = subprocess.Popen(launch.argv, cwd=str(workspace), env=env,
                                    stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                    start_new_session=True)
        except OSError as e:
            spawn_error = f"{type(e).__name__}: {e}"
        else:
            try:
                rc = proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_group(proc)
                rc = proc.wait()
            except BaseException:
                # Ctrl-C／SIGTERM：agent 在自己的 session 裡，終端機的訊號到不了它 ⇒
                # 這裡不殺，它就成了孤兒，繼續寫工作區、繼續打外部 API。
                _kill_group(proc)
                try:
                    proc.wait(timeout=5)
                except Exception:  # noqa: BLE001
                    pass
                raise
            _kill_group(proc)
    return {"rc": rc, "timed_out": timed_out, "wall_ms": int((time.time() - t0) * 1000),
            "spawn_error": spawn_error, "stdout_log": str(out_p), "stderr_log": str(err_p)}


def do(task: flow.Task, *, agent: str, build: Callable[[str, pathlib.Path], Launch],
       prompt: str, in_place: bool = False, timeout_s: float = 1800.0,
       attempts: int | None = None, sandbox: str = "auto",
       feedback: Callable[[dict[str, Any]], str] | None = None,
       feedback_mode: str = "localized") -> dict[str, Any]:
    """跑一次（或契約允許的幾次）agent，交件，回裁決。不發布。

    `feedback_mode`（下一次嘗試的提示裡放什麼；預註冊實驗的三臂只差這一個）：
    `localized`＝追緝過的回饋（位置、應有的值、第一次出現的步驟）；`generic`＝原本的泛用回饋；
    `none`＝**重抽**：每一次都從乾淨的工作區、原提示重來（`in_place` 時無法重抽 ⇒ 拒絕）。
    同一個值也經環境變數傳給 agent 的回合邊界掛鉤，讓工作階段裡的回饋走同一種。"""
    if feedback_mode not in FEEDBACK_MODES:
        raise ValueError(f"feedback_mode must be one of {FEEDBACK_MODES}")
    if feedback_mode == "none" and in_place and (attempts or task.contract.max_attempts) > 1:
        raise ValueError("feedback_mode=none re-draws from a clean workspace; not with --in-place")
    run_id = time.strftime("%Y%m%dT%H%M%S") + f"-{os.getpid()}-{os.urandom(3).hex()}"
    base = work_root() / task.task_id / run_id
    try:
        ws = task.contract.base_dir if in_place else prepare_workspace(task.contract,
                                                                      base / "ws")
    except Exception as e:  # noqa: BLE001 — 準備失敗（gpgsign、FIFO、權限）也要上帳本
        task.ledger.append("infra_void", {"stage": "prepare_workspace",
                                          "error": f"{type(e).__name__}: {e}"[:500]})
        return {"outcome": None, "void": True, "reasons": [f"could not prepare the "
                                                           f"workspace: {e}"],
                "attempts": [], "workspace": None, "run_dir": str(base), "agent": agent}
    n_max = attempts or task.contract.max_attempts
    skip = _skip_dirs(task.contract)
    traced = _trace_start(task, ws, prompt, in_place=in_place)
    history: list[dict[str, Any]] = []
    cur_prompt = prompt
    res: dict[str, Any] = {}
    old_handlers = _install_signal_handlers()
    try:
        for i in range(1, n_max + 1):
            # 基準線每一跑重取：第一跑的逃逸不該被算到之後每一跑頭上
            try:
                origin_before = None if in_place else origin_digest(task.contract.base_dir,
                                                                    skip)
                if feedback_mode == "none" and i > 1:
                    # 重抽：乾淨的工作區、原提示（上一次的痕跡不留給這一次）
                    ws = prepare_workspace(task.contract, base / f"ws{i}")
                    traced = _trace_start(task, ws, prompt, in_place=False)
                launch = build(cur_prompt, ws)
                launch.env = {**launch.env, "VACANT_FEEDBACK_MODE": feedback_mode}
            except Exception as e:  # noqa: BLE001 — 跑之前就壞了：也要上帳本，不是丟 traceback
                task.ledger.append("infra_void", {"stage": "before_attempt", "attempt": i,
                                                  "error": f"{type(e).__name__}: {e}"[:500]})
                res = {"outcome": None, "void": True, "reasons": [f"before attempt {i}: {e}"]}
                break
            task.ledger.append("attempt_started", {
                "attempt": i, "agent": agent, "adapter": "process", "in_place": in_place,
                "argv0": launch.argv[0] if launch.argv else None,
                "argv_sha256": _sha(json.dumps(launch.argv)), "note": launch.note,
                "workspace": str(ws)})
            try:
                r = run_agent(launch, workspace=ws, timeout_s=timeout_s,
                              log_dir=base / f"a{i}")
            except BaseException as e:
                task.ledger.append("attempt_ended", {"attempt": i, "rc": None,
                                                     "interrupted": type(e).__name__})
                task.ledger.append("infra_void", {"stage": "interrupted", "attempt": i,
                                                  "error": type(e).__name__})
                raise
            finally:
                if launch.cleanup:
                    launch.cleanup()
            changed: list[str] = []
            if origin_before is not None:
                try:
                    changed = _diff(origin_before, origin_digest(task.contract.base_dir, skip))
                except Exception as e:  # noqa: BLE001 — 量不到逃逸 ≠ 沒有逃逸
                    changed = [f"<escape measurement failed: {type(e).__name__}: {e}>"]
            escaped = bool(changed) if origin_before is not None else None
            task.ledger.append("attempt_ended", {"attempt": i, "rc": r["rc"],
                                                 "timed_out": r["timed_out"],
                                                 "wall_ms": r["wall_ms"],
                                                 "spawn_error": r["spawn_error"],
                                                 "workspace_escape": escaped,
                                                 "escaped_paths": changed[:50]})
            if r["spawn_error"]:
                task.ledger.append("infra_void", {"stage": "spawn", "attempt": i,
                                                  "error": r["spawn_error"]})
                res = {"outcome": None, "void": True, "reasons": [r["spawn_error"]]}
                history.append({"attempt": i, **r, "outcome": None})
                break
            res = flow.submit(task, ws, source=f"{agent}:vacant-do:a{i}", sandbox=sandbox,
                              attempt=i)
            history.append({"attempt": i, **r, "workspace_escape": escaped,
                            "escaped_paths": changed[:50],
                            "outcome": res.get("outcome"),
                            "failing_required": sum(
                                1 for x in res.get("results") or []
                                if x.get("required", True) and x.get("status") != "PASS"),
                            "artifact_sha256": res.get("artifact_sha256")})
            last = res.get("outcome") == "accept" or res.get("void") or i == n_max
            tr = _trace_attempt(traced, res, why=None if not last else (
                "the last attempt" if res.get("outcome") != "accept" else None))
            if tr:
                history[-1]["trace"] = {k: tr.get(k) for k in ("report", "summary")}
                res["trace"] = history[-1]["trace"]
            if last:
                break
            if not any(x.get("status") == "FAIL" and x.get("required", True)
                       for x in res.get("results", [])):
                res["stopped"] = ("no required claim FAILs: what is left (review, independent "
                                  "evidence, disagreement) is not something another attempt "
                                  "can fix")
                break
            if feedback_mode == "none":
                cur_prompt = prompt
            elif feedback_mode == "localized" and tr and tr.get("text"):
                # 追緝過的回饋：哪個檔哪一行、應該是多少、第一次出現在第幾步（沒有行動者）
                cur_prompt = prompt + "\n\n" + str(tr["text"])
            elif feedback is not None:
                cur_prompt = prompt + "\n\n" + feedback(res)
    finally:
        _restore_signal_handlers(old_handlers)
    _trace_outcome(traced, res, agent=agent, run_id=run_id)
    return {**res, "attempts": history, "workspace": str(ws), "run_dir": str(base),
            "agent": agent}


# ── 可究責追緝（`vacant_network/trace/`；DECISION_20260924_ACCOUNTABLE_TRACE）────────
# 追緝壞掉只記錯，不影響交件與裁決（和掛鉤同一條：誠實邊界不在這一層）。

def _trace_start(task: flow.Task, ws: pathlib.Path, prompt: str, *,
                 in_place: bool) -> dict[str, Any] | None:
    """工作區的起點（之後每一步的差異都以它為準）＋任務訊息（追緝判斷「是不是任務給的值」）。"""
    try:
        from ..intake import contract as C
        from ..trace.recorder import Recorder
        contract = task.contract
        if not in_place and task.contract.path is not None:
            rel = task.contract.path.resolve().relative_to(task.contract.base_dir)
            contract = C.load(ws / rel)          # 隔離工作區裡那一份：輸入從工作區讀
        rec = Recorder(ws)
        rec.checkpoint("task_start")
        rec.prompt(prompt, source="vacant do")
        return {"rec": rec, "contract": contract, "ws": ws}
    except Exception as e:  # noqa: BLE001
        task.ledger.append("trace_error", {"stage": "start", "error": str(e)[:300]})
        return None


def _trace_attempt(traced: dict[str, Any] | None, res: dict[str, Any],
                   why: str | None) -> dict[str, Any] | None:
    if traced is None or not res.get("results"):
        return None
    try:
        from ..trace.stopcheck import localize
        return localize(traced["contract"], res, cwd=str(traced["ws"]), why_open=why,
                        workspace=traced["ws"])
    except Exception as e:  # noqa: BLE001
        res.setdefault("trace_error", f"{type(e).__name__}: {e}"[:300])
        return None


def _trace_outcome(traced: dict[str, Any] | None, res: dict[str, Any], *, agent: str,
                   run_id: str) -> None:
    """這一跑的結果：和工作階段結束走同一條規則（`actors.adoption_of`：hold／escalate 不算進
    adoption），**同時簽進這一跑的病歷**（`consequence`）——`actors.ndjson` 只是衍生檢視。"""
    if traced is None or res.get("outcome") is None:
        return
    try:
        from ..trace import actors as A
        # 同一個 agent 設定只該有一格：模型用掛鉤看到的主 agent 自稱的那個（審查 consequences#1）
        rec = traced["rec"]
        st = rec._state()
        model = next((v.get("model") for k, v in (st.get("sessions") or {}).items()
                      if k.startswith(f"{agent}:") and v.get("model")), None)
        A.record_run(rec, session_key=f"do:{run_id}", actor={"platform": agent, "model": model},
                     outcome=res.get("outcome"), adoption=A.adoption_of(res),
                     contract=traced["contract"], run_id=run_id, at="vacant_do")
    except Exception as e:  # noqa: BLE001
        res.setdefault("trace_error", f"{type(e).__name__}: {e}"[:300])


def _raise_interrupted(signum: int, _frame: Any) -> None:
    raise Interrupted(signal.Signals(signum).name)


def _install_signal_handlers() -> dict[int, Any]:
    old: dict[int, Any] = {}
    for sig in (signal.SIGTERM, signal.SIGHUP):
        try:
            old[sig] = signal.signal(sig, _raise_interrupted)
        except (ValueError, OSError):      # 不在主執行緒：沒辦法裝，照舊
            pass
    return old


def _restore_signal_handlers(old: dict[int, Any]) -> None:
    for sig, h in old.items():
        try:
            signal.signal(sig, h)
        except (ValueError, OSError):
            pass


def _sha(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
