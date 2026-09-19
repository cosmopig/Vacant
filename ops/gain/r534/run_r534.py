#!/usr/bin/env python3
"""這支在架構裡承重什麼：R534 的四格 driver——**起格、看著、收證據**。

四格 ＝ 2（有／沒有 Vacant 閘門）× 2（有／沒有思考）：

    A1 pi＋Vacant＋有思考      B1 純 pi＋有思考
    A2 pi＋Vacant＋沒思考      B2 純 pi＋沒思考

四格同 prompt、同工具、同預算上限；唯一差別是 `arm` 與 `reasoning_effort`
（`ops/gain/r534/piarms.py` 的 `assert_cells_differ_only_as_declared` 是可執行防呆）。

一格一題的生命週期：

    prepare_workspace(樣板 → 工作區)         # openwork_arms，唯讀沿用
        ↓  起點樹雜湊落盤（wshash）
    起 CellSidecar（unix socket；Logbook ＋ 一次性 Ed25519 身分在本行程記憶體）
        ↓
    spawn pi --mode rpc（cwd ＝ agentcwd，**不是工作區**）
        │   stdout 事件流逐行寫 pi_events.jsonl
        │   LLM 請求走 wire tap → LM Studio，request/response 原樣寫 wire.jsonl
        │   run_bash／閘門走 socket → sidecar → bwrap 沙箱／acceptance
        ↓  pi 結束（擴充 ctx.shutdown()，或撞預算，或被 driver 逾時砍掉）
    工作區凍結 → tar.gz（含 .git，留住 git diff 這條證據）
        ↓
    隱藏測資**在另一個目錄的副本上**跑（原工作區跑完再驗一次樹雜湊沒動）
        ↓
    rows.jsonl 一列

為什麼 pi 的 cwd 不是工作區：pi 自己會在 cwd 附近放東西（session、暫存），
那些東西會進樹雜湊 ⇒ 「模型改了什麼」與「pi 放了什麼」混在一起。
模型碰得到工作區的唯一路徑是 `run_bash` → sidecar → 沙箱（cwd ＝ 工作區）。

⚠ **隱藏測資的紅線**：`hidden/` 只在本檔案的計分段出現，而且是在工作區
  凍結＋打包**之後**、在另一個目錄裡。sidecar、擴充、prompt、回饋一律碰不到它。

⚠ **主指標走既有那條**（`bank_manifest.json` 的 `scoring.primary_numerator`）：
  `gain_run.meets_demand(solution.py, codebench._lcb_check_code(ep, visible+hidden))`。
  渲染出來的 `test_hidden.py` 是**第二條**路徑，它沒有 `vacant/checks.py` 的
  AST 政策 ⇒ 對用到被政策擋掉的東西的碼會比較寬。兩條路徑的數字逐列分開落盤，
  **不可混報**。

⚠ **R534 的數字只准在 R534 內部配對**：pi 的 prompt 組裝與工具協定與
  `ops/gain/r530/openwork_arms.py` 不同，不得與 `runs/g_r530_*`／`g_r460_*`／
  `g_r532_*` 跨 run 併算。
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import pathlib
import queue
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from ops.gain.r530 import acceptance, wshash  # noqa: E402
from ops.gain.r530.openwork_arms import (archive_workspace,  # noqa: E402
                                         persona_for, prepare_workspace,
                                         remove_workspace)
from ops.gain.r530.sandbox import make_sandbox  # noqa: E402
from ops.gain.r534 import piarms, preflight  # noqa: E402
from ops.gain.r534.build_bank import _bank_records  # noqa: E402
from ops.gain.r534.sidecar import CellSidecar  # noqa: E402
from vacant.crypto import pub_to_hex  # noqa: E402
from vacant.identity import Identity  # noqa: E402
from vacant.logbook import Logbook  # noqa: E402

TEMPLATES = pathlib.Path(HERE) / "templates"
HIDDEN = pathlib.Path(HERE) / "hidden"
MANIFEST = pathlib.Path(HERE) / "bank_manifest.json"
EXTENSION = pathlib.Path(HERE) / "pi_ext" / "vacant_gate.ts"
NODE_BIN_DEFAULT = os.path.expanduser("~/.local/opt/node-v22.23.2-linux-x64/bin")

#: pi 行程被 driver 砍掉之前的寬限：預算是在呼叫**之間**檢查的，
#: 單次請求可以燒掉遠多於 `max_wall_s` ⇒ driver 這一層要有一把硬的剪刀，
#: 否則一格卡住會把整批拖死。**這是基建上界不是預算判準**，兩者分開記。
HARD_KILL_MARGIN_S = 900

#: `--preflight-json` 能重用一份預檢多久。六小時是**推導不是裁決**：
#: 端點會換模型、LM Studio 會被重啟、沙箱政策會被改，這幾件事都不會通知我們。
PREFLIGHT_MAX_AGE_S = 6 * 3600


def _tree_listing(workspace: pathlib.Path) -> str:
    """給 worker 看的檔案清單——**按路徑排序**，所以四格拿到的字串相同。"""
    leaves = wshash.tree_leaves(workspace)
    return "\n".join(f"  {leaf['path']}" for leaf in leaves) or "  (empty)"


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class WireTap:
    """一格一個 tap：**wire log 的檔名本身就是歸屬**，不必只靠 header。"""

    def __init__(self, cell: str, port: int, upstream: str,
                 log: pathlib.Path) -> None:
        self.cell, self.port, self.upstream, self.log = cell, port, upstream, log
        self.proc: subprocess.Popen | None = None

    def start(self) -> None:
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self.proc = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "wire_tap.py"),
             "--listen", f"127.0.0.1:{self.port}",
             "--upstream", self.upstream, "--log", str(self.log)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(150):
            try:
                with socket.create_connection(("127.0.0.1", self.port), 0.3):
                    return
            except OSError:
                time.sleep(0.1)
        raise SystemExit(f"wire tap 起不來（{self.cell} port {self.port}）。停。")

    def stop(self) -> None:
        if self.proc is None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def run_pi(*, argv: list[str], env: dict, cwd: pathlib.Path, prompt: str,
           events_path: pathlib.Path, stderr_path: pathlib.Path,
           timeout_s: float, ready: threading.Event) -> dict:
    """起一個 pi（`--mode rpc`），送一則 prompt，等它自己收掉。

    為什麼是 rpc 而不是 `-p`：`-p` 是一次性的——擴充在 `agent_settled` 送回去的
    回饋訊息會被接受（`before_agent_start` 會觸發），但行程在那之前就開始拆了，
    第二通 provider request 一次都沒送出去（2026-09-18 實測）。
    rpc 模式的行程活著等下一個命令 ⇒ 閘門的「重改」迴圈才跑得起來，
    而且**整段對話留在同一個 session 裡**（重改的定義）。

    `ctx.shutdown()` 在 rpc 模式是「等到 idle 再收」，所以擴充決定收的時候
    這裡會自然看到行程結束；逾時才由 driver 動手砍。
    """
    events_path.parent.mkdir(parents=True, exist_ok=True)
    ev = events_path.open("a", encoding="utf-8")
    err = stderr_path.open("ab")
    proc = subprocess.Popen(
        argv, cwd=str(cwd), env=env, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=err, text=True, bufsize=1,
        start_new_session=True)

    lines: list[str] = []

    def _pump() -> None:
        try:
            for line in proc.stdout:            # type: ignore[union-attr]
                ev.write(line if line.endswith("\n") else line + "\n")
                ev.flush()
                lines.append(line.rstrip("\n"))
        except Exception:                        # noqa: BLE001
            pass

    t = threading.Thread(target=_pump, daemon=True)
    t.start()
    # **等擴充握手成功才送 prompt**，不要用固定的 sleep，也不要等 pi 的 stdout：
    # `--mode rpc` 不吐 session header（那是 `--mode json` 才有的），而擴充要經過
    # jiti 轉譯、要連 sidecar、要算起點樹雜湊，慢的時候遠不只一秒。
    # 在那之前送進去的命令會掉在地上——掉了的話這一格會看起來像「模型不回話」。
    t_ready = time.time()
    while time.time() - t_ready < 180:
        if ready.is_set() or proc.poll() is not None:
            break
        time.sleep(0.2)
    killed = False
    if not ready.is_set():
        with contextlib.suppress(Exception):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        t.join(timeout=10)
        ev.close()
        err.close()
        return {"rc": proc.poll(), "killed": True, "events_n": len(lines),
                "startup_error": "擴充沒有在 180 秒內完成 hello 握手",
                "wall_s": round(time.time() - t_ready, 2)}
    try:
        proc.stdin.write(json.dumps(
            {"id": "r534", "type": "prompt", "message": prompt},
            ensure_ascii=False) + "\n")
        proc.stdin.flush()
    except (BrokenPipeError, OSError) as exc:
        return {"rc": proc.poll(), "killed": False, "stdin_error": repr(exc),
                "events_n": len(lines)}
    t0 = time.time()
    while proc.poll() is None:
        if time.time() - t0 > timeout_s:
            killed = True
            with contextlib.suppress(Exception):
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(Exception):
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            break
        time.sleep(0.5)
    with contextlib.suppress(Exception):
        proc.stdin.close()
    t.join(timeout=15)
    ev.close()
    err.close()
    return {"rc": proc.returncode, "killed": killed, "events_n": len(lines),
            "wall_s": round(time.time() - t0, 2)}


def score_cell(*, sandbox, bank_rec: dict, ws: pathlib.Path,
               score_root: pathlib.Path, hidden_dir: pathlib.Path,
               task_id: str) -> dict:
    """事後計分。**工作區凍結＋打包之後才跑，而且跑在副本上。**

    兩條路徑都量，逐列分開落盤（`bank_manifest.scoring.rule`）：
      · `meets_demand`（**主指標**）＝ 既有沙箱判準，與 r460／r532 同一把尺
      · `rendered_hidden`（第二條）＝ 渲染出來的 `test_hidden.py`，沒有 AST 政策
    """
    out: dict = {"task_id": task_id}
    ws_before = wshash.tree_hash(ws)

    sol = ws / "solution.py"
    out["solution_present"] = sol.exists()
    out["solution_bytes"] = sol.stat().st_size if sol.exists() else 0
    code = sol.read_text(encoding="utf-8", errors="replace") if sol.exists() else ""
    out["solution_sha256"] = _sha256_text(code) if sol.exists() else None

    # ── 主指標 ───────────────────────────────────────────────────────
    if sol.exists():
        try:
            from ops.gain.brain_cline import InfraVoid
            from ops.gain.gain_run import meets_demand
            from vacant.codebench import _lcb_check_code
            check = _lcb_check_code(
                bank_rec["entry_point"],
                bank_rec["visible_tests"] + bank_rec["hidden_tests"])
            ok, msg = meets_demand(code, check, 10,
                                   entry_point=bank_rec["entry_point"])
            out["meets_demand"] = bool(ok)
            out["meets_demand_msg"] = msg
        except InfraVoid as exc:
            out["meets_demand"] = None
            out["meets_demand_infra_void"] = repr(exc)
        except Exception as exc:                        # noqa: BLE001
            out["meets_demand"] = None
            out["meets_demand_error"] = repr(exc)
    else:
        # 沒交出檔案**是一個真實結果**，不是缺資料——分子 False，理由寫清楚。
        out["meets_demand"] = False
        out["meets_demand_msg"] = "no_solution_file"

    # ── 第二條：渲染出來的 hidden 套件，跑在副本上 ─────────────────────
    copy_dir = score_root / f"{task_id}_wscopy"
    if copy_dir.exists():
        shutil.rmtree(copy_dir, ignore_errors=True)
    copy_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", "-a", f"{ws}/.", str(copy_dir)], check=True)
    try:
        res = acceptance.run_suite(
            sandbox, copy_dir, hidden_dir, suite="hidden", task_id=task_id,
            verify_root=score_root / "verify",
            timeout_s=float(piarms.R534_BUDGET["gate_test_timeout_s"]))
        out["rendered_hidden_all_pass"] = bool(res.get("all_pass"))
        out["rendered_hidden_passed"] = res.get("passed")
        out["rendered_hidden_total"] = res.get("total")
        out["rendered_hidden_sha256"] = res.get("result_sha256")
    except Exception as exc:                            # noqa: BLE001
        out["rendered_hidden_all_pass"] = None
        out["rendered_hidden_error"] = repr(exc)
    finally:
        shutil.rmtree(copy_dir, ignore_errors=True)

    # 原工作區在計分前後必須一模一樣——不然「交出去的東西」就不是收據上那個。
    out["ws_unchanged_by_scoring"] = (wshash.tree_hash(ws) == ws_before)
    return out


class Runner:
    def __init__(self, args) -> None:
        self.args = args
        self.run_dir = pathlib.Path(args.run_dir).resolve()
        # ⚠ run 目錄**必須在 repo 外面**。理由不是整潔，是隔離：
        # bwrap 為了掛上工作區會把它的每一層父目錄在沙箱裡建出來 ⇒ run 目錄
        # 放在 repo 底下，`<repo>` 這條路徑在沙箱裡就「存在」（雖然是空的），
        # 而 `sandbox.probe` 的 `repo_hidden_from_sandbox` 量的正是這一條。
        # R530 的既有慣例是 `/var/tmp/vacant_r530_work/…`（SANDBOX.md），照抄。
        if self.run_dir == pathlib.Path(REPO) or pathlib.Path(REPO) in self.run_dir.parents:
            raise SystemExit(
                f"--run-dir 不可以在 repo 底下（{self.run_dir}）：bwrap 會把父目錄"
                f"在沙箱裡建出來，repo_hidden_from_sandbox 就永遠是 False。"
                f"用 /var/tmp/vacant_r534_work/<tag> 這種路徑。停。")
        self.cells = tuple(c.strip() for c in args.cells.split(",") if c.strip())
        bad = [c for c in self.cells if c not in piarms.CELLS]
        if bad:
            raise SystemExit(f"未知的格：{bad}（可用 {piarms.CELL_ORDER}）")
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.bank = _bank_records()
        self.tasks = self._select_tasks()
        self.rows_lock = threading.Lock()
        self.book_lock = threading.Lock()
        self.books: dict[str, Logbook] = {c: Logbook() for c in self.cells}
        self.idents: dict[str, Identity] = {c: Identity.generate()
                                            for c in self.cells}
        self.taps: list[WireTap] = []
        self.sandbox = None
        self.sandbox_meta: dict = {}
        self.tap_ports: dict[str, int] = {}
        self.node_bin = args.node_bin

    def _select_tasks(self) -> list[str]:
        layers = self.manifest["layers"]
        if self.args.layer == "A":
            ids = list(layers["A_high_divergence"])
        elif self.args.layer == "B":
            ids = list(layers["B_random"])
        else:
            ids = list(layers["A_high_divergence"]) + list(layers["B_random"])
        if self.args.tasks:
            want = [t.strip() for t in self.args.tasks.split(",") if t.strip()]
            unknown = [t for t in want if t not in ids]
            if unknown:
                raise SystemExit(f"不在題庫裡的題：{unknown}。停。")
            ids = want
        if self.args.limit:
            ids = ids[: self.args.limit]
        return ids

    # ── 一格一題 ──────────────────────────────────────────────────────
    def run_cell_task(self, cell: str, task_id: str) -> dict:
        cfg = piarms.CELLS[cell]
        arm = cfg["arm"]
        policy = self.args.policy if arm == "vacant" else "revise"
        cell_dir = self.run_dir / "cells" / cell / task_id
        ws = cell_dir / "ws"
        agentcwd = cell_dir / "agentcwd"
        sessions = cell_dir / "sessions"
        verify = cell_dir / "verify"
        for d in (agentcwd, sessions, verify):
            d.mkdir(parents=True, exist_ok=True)
        calls_path = self.run_dir / "cells" / cell / "calls.jsonl"
        ext_log = self.run_dir / "cells" / cell / "pi_ext.jsonl"

        tpl = TEMPLATES / task_id
        goal = (tpl / "goal.md").read_text(encoding="utf-8")
        contract = (tpl / "contract.md").read_text(encoding="utf-8")
        bank_rec = self.bank[task_id]

        t_cell0 = time.time()
        attempt = 1
        states: list[dict] = []
        pi_runs: list[dict] = []
        offsets = {"calls_used": 0, "completion_tokens": 0, "prompt_tokens": 0,
                   "reasoning_tokens": 0, "tool_calls": 0}

        while True:
            start_manifest = prepare_workspace(tpl, ws, git_init=True,
                                               world_writable=False)
            ws_start = start_manifest["ws_sha256"]
            persona_name, persona_text = persona_for(self.args.seed, task_id,
                                                     attempt)
            system_prompt = piarms.system_prompt(persona_text)
            prompt = piarms.task_message(goal, contract, _tree_listing(ws))

            sock = self.run_dir / "s" / f"{cell}{len(states)}.sock"
            sc = CellSidecar(
                sock_path=sock, cell=cell, arm=arm, policy=policy,
                task_id=task_id, workspace=ws, visible_dir=tpl / "tests_visible",
                verify_root=verify, sandbox=self.sandbox,
                book=self.books[cell], ident=self.idents[cell],
                book_lock=self.book_lock, calls_path=calls_path,
                ws_start_sha256=ws_start, attempt=attempt, t0=t_cell0,
                offsets=dict(offsets))
            sc.start()

            pi_cfg = {
                "sock": str(sock), "cell": cell, "arm": arm, "policy": policy,
                "task_id": task_id, "attempt": attempt,
                "model": piarms.MODEL_ID,
                "provider": f"r534_{cell.lower()}",
                "system_prompt": system_prompt,
                "run_bash_description": piarms.RUN_BASH_DESCRIPTION,
                "expect_reasoning_effort_none": (not cfg["think"]),
                "tool_timeout_s": int(piarms.R534_BUDGET["tool_timeout_s"]),
                "tool_timeout_max_s":
                    int(piarms.R534_BUDGET["tool_timeout_max_s"]),
                "ext_log": str(ext_log),
            }
            cfg_path = cell_dir / f"pi_config_{attempt}.json"
            cfg_path.write_text(json.dumps(pi_cfg, ensure_ascii=False, indent=2),
                                encoding="utf-8")

            env = dict(os.environ)
            env["PATH"] = self.node_bin + os.pathsep + env.get("PATH", "")
            env["PI_CODING_AGENT_DIR"] = str(self.run_dir / "piconf")
            env["R534_CONFIG"] = str(cfg_path)
            env["PI_OFFLINE"] = "1"
            argv = [
                "pi", "--model", f"r534_{cell.lower()}/{piarms.MODEL_ID}",
                "--mode", "rpc",
                "--no-builtin-tools", "--tools", "run_bash",
                "--no-context-files", "--no-skills", "--no-prompt-templates",
                "--no-themes", "--no-approve", "--no-extensions",
                "--offline",
                "--session-dir", str(sessions),
                "--system-prompt", system_prompt,
                "-e", str(EXTENSION),
            ]
            (cell_dir / f"argv_{attempt}.json").write_text(
                json.dumps(argv, ensure_ascii=False, indent=2), encoding="utf-8")

            pi_run = run_pi(
                argv=argv, env=env, cwd=agentcwd, prompt=prompt,
                events_path=cell_dir / f"pi_events_{attempt}.jsonl",
                stderr_path=cell_dir / f"pi_stderr_{attempt}.log",
                timeout_s=float(piarms.R534_BUDGET["max_wall_s"])
                + HARD_KILL_MARGIN_S,
                ready=sc.hello_event)
            pi_runs.append(pi_run)

            # pi 走了但 `final` 沒被打到（被砍／擴充炸了）⇒ 自己補一筆裁決，
            # 不留一個沒有收據的格子。
            if sc.state["verdict_hash"] is None:
                with contextlib.suppress(Exception):
                    sc._op_final({"op": "final", "reason": "driver_fallback"})
            sc.stop()
            st = dict(sc.state)
            st["persona"] = persona_name
            st["system_prompt_sha256_expected"] = _sha256_text(system_prompt)
            st["pi_run"] = pi_run
            states.append(st)

            for k in offsets:
                offsets[k] = int(st.get(k) or 0)

            if st.get("stop_reason") != "conf_attempt_failed":
                break
            if attempt >= int(piarms.R534_BUDGET["max_conf_attempts"]):
                break
            attempt += 1

        final = states[-1]
        ws_archive = self.run_dir / "ws" / f"{cell}__{task_id}.tar.gz"
        archive_sha = archive_workspace(ws, ws_archive)
        score = score_cell(sandbox=self.sandbox, bank_rec=bank_rec, ws=ws,
                           score_root=self.run_dir / "score" / cell,
                           hidden_dir=HIDDEN / task_id, task_id=task_id)

        tmeta = self.manifest["tasks"][task_id]
        row = {
            "run": "r534", "tag": self.args.tag, "cell": cell, "arm": arm,
            "think": bool(cfg["think"]), "policy": policy,
            "task_id": task_id, "layer": tmeta["layer"],
            "difficulty": tmeta["difficulty"],
            "entry_point": tmeta["entry_point"],
            "seed": self.args.seed, "persona": final["persona"],
            "attempts": len(states), "attempt_final": final["attempt"],
            "stop_reason": final["stop_reason"],
            "accepted": final["accepted"], "refused": final["refused"],
            "declared_done": final["declared_done"],
            "visible_pass": final["visible_pass"],
            "visible_passed": final["visible_passed"],
            "visible_total": final["visible_total"],
            "gate_rounds": final["gate_rounds"], "nudges": final["nudges"],
            "calls_used": final["calls_used"],
            "completion_tokens": final["completion_tokens"],
            "prompt_tokens": final["prompt_tokens"],
            "reasoning_tokens": final["reasoning_tokens"],
            "tool_calls": final["tool_calls"],
            "tool_blocked_n": final["tool_blocked_n"],
            "deny_hidden_read_n": final["deny_hidden_read_n"],
            "deny_escape_n": final["deny_escape_n"],
            "deny_network_n": final["deny_network_n"],
            "self_ran_visible": final["self_ran_visible"],
            "ws_start_sha256": states[0]["ws_start_sha256"],
            "ws_end_sha256": final["ws_end_sha256"],
            "ws_archive": str(ws_archive.relative_to(self.run_dir)),
            "ws_archive_sha256": archive_sha,
            "verdict_hash": final["verdict_hash"],
            "attempt_hashes": final["attempt_hashes"],
            "requests_seen": final["requests_seen"],
            "wire_reasoning_effort_seen": final["wire_reasoning_effort_seen"],
            "system_prompt_sha256": final["system_prompt_sha256"],
            "system_prompt_sha256_expected": final["system_prompt_sha256_expected"],
            "tools_schema_sha256": final["tools_schema_sha256"],
            "infra_void": final["infra_void"],
            "harness_void_reason": final["harness_void_reason"],
            "pi_rc": final["pi_run"]["rc"],
            "pi_killed": final["pi_run"]["killed"],
            "wall_s": round(time.time() - t_cell0, 2),
            "token_accounting": piarms.TOKEN_ACCOUNTING_NOTE,
            **{k: v for k, v in score.items() if k != "task_id"},
            "states": states,
        }
        self._write_row(row)
        return row

    def _write_row(self, row: dict) -> None:
        p = self.run_dir / "rows.jsonl"
        with self.rows_lock:
            with p.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())

    # ── 整批 ──────────────────────────────────────────────────────────
    def go(self) -> int:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        for sub in ("cells", "ws", "score", "s", "wire", "piconf"):
            (self.run_dir / sub).mkdir(parents=True, exist_ok=True)

        base = self.args.base_port
        self.tap_ports = {c: base + piarms.TAP_PORTS[c]
                          - min(piarms.TAP_PORTS.values())
                          for c in piarms.CELL_ORDER}

        # ── 零容忍預檢：不過就拒跑。**沒有 --force。** ──────────────────
        #
        # `--preflight-json` 不是繞過，是**重用一份還沒過期的實測證據**：
        # 那份 JSON 必須 ok=True、必須涵蓋這一次要跑的每一格、而且必須在
        # `PREFLIGHT_MAX_AGE_S` 之內。三條有一條不符就自己重跑一次。
        # 重用這件事本身會寫進 meta.json（`preflight_reused` 與 `age_s`），
        # 因為「這批資料是靠多久以前的證據發射的」是收官要回答的問題。
        pre = self._reuse_preflight()
        if pre is None:
            pre = preflight.run(
                node_bin=self.node_bin, backend=self.args.sandbox_backend,
                upstream=self.args.upstream, base_port=base + 100,
                workdir=self.run_dir / "preflight", cells=self.cells)
        (self.run_dir / "preflight.json").write_text(
            json.dumps(pre, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        for c in pre["checks"]:
            print(f"{'OK  ' if c['ok'] else 'FAIL'}  {c['id']}", flush=True)
        if not pre["ok"]:
            print("PREFLIGHT FAILED —— 拒跑。證據在 preflight.json。", flush=True)
            return 2

        # 正式跑用的 pi 設定目錄（`PI_CODING_AGENT_DIR`，跑完就丟）
        preflight.write_pi_conf(self.run_dir / "piconf", self.tap_ports,
                                self.args.upstream, self.args.upstream)

        self.sandbox, self.sandbox_meta = make_sandbox(
            self.args.sandbox_backend, workdir=str(self.run_dir / "sbprobe"))
        need = ("network_isolated", "write_confined", "repo_hidden_from_sandbox")
        if not all(self.sandbox_meta.get(k) is True for k in need):
            print(f"沙箱隔離不完整：{ {k: self.sandbox_meta.get(k) for k in need} }。停。")
            return 2

        upstream_base = piarms.UPSTREAM[self.args.upstream]
        for cell in self.cells:
            tap = WireTap(cell, self.tap_ports[cell], upstream_base,
                          self.run_dir / "wire" / f"{cell}.jsonl")
            tap.start()
            self.taps.append(tap)

        self._write_meta(pre)

        jobs: dict[str, queue.Queue] = {}
        for cell in self.cells:
            q: queue.Queue = queue.Queue()
            for t in self.tasks:
                q.put(t)
            jobs[cell] = q

        errors: list[str] = []

        def _worker(cell: str) -> None:
            while True:
                try:
                    task_id = jobs[cell].get_nowait()
                except queue.Empty:
                    return
                t0 = time.time()
                try:
                    row = self.run_cell_task(cell, task_id)
                    print(f"[{cell}] {task_id} stop={row['stop_reason']} "
                          f"accepted={row['accepted']} "
                          f"meets_demand={row['meets_demand']} "
                          f"calls={row['calls_used']} "
                          f"{time.time() - t0:.0f}s", flush=True)
                except Exception as exc:                # noqa: BLE001
                    import traceback
                    errors.append(f"{cell}/{task_id}: {exc!r}")
                    self._write_row({"run": "r534", "cell": cell,
                                     "task_id": task_id,
                                     "driver_error": repr(exc),
                                     "traceback": traceback.format_exc()})
                    print(f"[{cell}] {task_id} DRIVER ERROR {exc!r}", flush=True)

        threads = [threading.Thread(target=_worker, args=(c,), daemon=True)
                   for c in self.cells]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for tap in self.taps:
            tap.stop()
        self._save_receipts()
        self._write_meta(pre, done=True, errors=errors)
        backup = self._backup()
        print(f"rows: {self.run_dir / 'rows.jsonl'}")
        print(f"backup: {backup}")
        return 0 if not errors else 1

    def _reuse_preflight(self) -> dict | None:
        path = self.args.preflight_json
        if not path:
            return None
        p = pathlib.Path(path)
        if not p.exists():
            raise SystemExit(f"--preflight-json 指的檔案不存在：{p}。停。")
        rec = json.loads(p.read_text(encoding="utf-8"))
        age = time.time() - float(rec.get("ts") or 0)
        covered = set(rec.get("cells") or [])
        why = []
        if rec.get("ok") is not True:
            why.append("那一份預檢本身是 FAILED")
        if age > PREFLIGHT_MAX_AGE_S:
            why.append(f"已經過了 {age / 3600:.1f} 小時 "
                       f"(上限 {PREFLIGHT_MAX_AGE_S / 3600:.0f})")
        if not set(self.cells) <= covered:
            why.append(f"沒有涵蓋 {sorted(set(self.cells) - covered)}")
        if rec.get("upstream") != self.args.upstream:
            why.append(f"upstream 不同（{rec.get('upstream')} vs "
                       f"{self.args.upstream}）")
        if why:
            raise SystemExit("拒絕重用這一份預檢：" + "；".join(why) + "。停。")
        rec = dict(rec)
        rec["reused_from"] = str(p)
        rec["reused_age_s"] = round(age, 1)
        return rec

    def _save_receipts(self) -> None:
        """每格的鏈 ＋ 公鑰落盤。**私鑰不落盤**（RECORD_SPEC §7）。

        這條鏈能說的是「事後沒有被改過」（要改就得重簽，而私鑰隨行程消失），
        **不是**「由某個已知的人簽的」——身份是一次性的匿名身份。
        """
        for cell, book in self.books.items():
            if not len(book):
                continue
            book.save(self.run_dir / f"receipts_{cell}.ndjson")
            ident = self.idents[cell]
            (self.run_dir / f"receipts_{cell}.pub.json").write_text(
                json.dumps({"vacant_id": ident.vacant_id,
                            "pub_hex": pub_to_hex(ident.pub)},
                           ensure_ascii=False) + "\n", encoding="utf-8")

    def _write_meta(self, pre: dict, *, done: bool = False,
                    errors: list[str] | None = None) -> None:
        meta = {
            "run": "r534", "tag": self.args.tag,
            "started_iso": getattr(self, "_started",
                                   time.strftime("%Y-%m-%dT%H:%M:%S%z")),
            "done": done, "errors": errors or [],
            "host": socket.gethostname(),
            "cells": {c: piarms.CELLS[c] for c in self.cells},
            "tasks": self.tasks,
            "policy": self.args.policy, "seed": self.args.seed,
            "upstream": self.args.upstream,
            "upstream_base": piarms.UPSTREAM[self.args.upstream],
            "model": piarms.MODEL_ID,
            "tap_ports": self.tap_ports,
            "budget": piarms.R534_BUDGET,
            "stop_reasons": sorted(piarms.STOP_REASONS),
            "refusal_reasons": list(piarms.REFUSAL_REASONS),
            "sandbox_meta": self.sandbox_meta,
            "bank_manifest_sha256": hashlib.sha256(
                MANIFEST.read_bytes()).hexdigest(),
            "extension_sha256": hashlib.sha256(
                EXTENSION.read_bytes()).hexdigest(),
            "piarms_sha256": hashlib.sha256(
                (pathlib.Path(HERE) / "piarms.py").read_bytes()).hexdigest(),
            "sidecar_sha256": hashlib.sha256(
                (pathlib.Path(HERE) / "sidecar.py").read_bytes()).hexdigest(),
            "rules_sha256": _sha256_text(piarms.RULES),
            "feedback_sha256": _sha256_text(piarms.FEEDBACK_TEMPLATE),
            "preflight_ok": pre["ok"],
            "preflight_reused": pre.get("reused_from"),
            "preflight_reused_age_s": pre.get("reused_age_s"),
            "scoring": self.manifest["scoring"],
            "not_poolable_with": ["g_r530_*", "g_r460_*", "g_r532_*"],
            "not_poolable_why": (
                "pi 的 system prompt 組裝方式與工具協定（native tool-calling）"
                "與 ops/gain/r530/openwork_arms.py 的 bash 圍欄文字協定不同；"
                "R534 的數字只准在 R534 內部配對。"),
            "honesty_bounds": [
                "plain 兩格的 accepted 結構性恆為 True（包含宣告完成但什麼都沒寫）"
                "——這是結構差不是量測差，每一次引用都要跟著講。",
                "閘門 records and gates，不 proves：它證明宣告完成之後可見驗收"
                "先跑了一次、沒過就沒出貨，不證明交出去的東西是對的。",
                "max_wall_s 在呼叫之間檢查，不是每題牆鐘的硬上界；"
                "driver 另有一把硬剪刀（HARD_KILL_MARGIN_S），兩者分開記。",
                "主指標（meets_demand）與渲染 hidden 套件是兩條路徑，不可混報。",
            ],
        }
        (self.run_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")

    def _backup(self) -> str:
        """整個 run 目錄打包——**人類明確要求「所有的 ai 輸出也都要記錄備份」**。

        含 wire.jsonl（逐字 bytes）、pi 的 session JSONL、擴充日誌、
        calls.jsonl、每格工作區的 tar.gz、收據鏈與公鑰。
        """
        out = self.run_dir.parent / f"{self.run_dir.name}_backup.tar.gz"
        with tarfile.open(out, "w:gz") as tf:
            tf.add(self.run_dir, arcname=self.run_dir.name)
        sha = hashlib.sha256(out.read_bytes()).hexdigest()
        (self.run_dir.parent / f"{self.run_dir.name}_backup.sha256").write_text(
            f"{sha}  {out.name}\n", encoding="utf-8")
        return f"{out} (sha256 {sha})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="R534 四格 driver（pi ＋ Vacant 閘門 × 思考／不思考）")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--tag", default=time.strftime("%Y%m%d_%H%M%S"))
    ap.add_argument("--cells", default=",".join(piarms.CELL_ORDER))
    ap.add_argument("--layer", default="AB", choices=["A", "B", "AB"])
    ap.add_argument("--tasks", default=None, help="逗號分隔的 task_id 白名單")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--policy", default="revise", choices=["revise", "resample"],
                    help="vacant 兩格沒過之後怎麼辦：重改（同一段 session）／重抽")
    ap.add_argument("--seed", default="r534-2026-09-18")
    ap.add_argument("--upstream", default="1003", choices=sorted(piarms.UPSTREAM))
    ap.add_argument("--base-port", type=int, default=8541,
                    help="每格一個 wire tap 埠，從這裡連號四個；"
                         "**同時跑兩批就要換這個**，否則兩批的 tap 會搶同一個埠")
    ap.add_argument("--sandbox-backend", default="bwrap",
                    choices=["auto", "bwrap", "unshare", "none"])
    ap.add_argument("--node-bin", default=NODE_BIN_DEFAULT)
    ap.add_argument("--preflight-json", default=None,
                    help="重用一份還沒過期、而且涵蓋這些格的預檢證據"
                         "（不是繞過：ok 必須為真、六小時內、upstream 相同）")
    ap.add_argument("--clean", action="store_true",
                    help="跑之前把 run 目錄整個刪掉重建")
    args = ap.parse_args(argv)

    # **先建 Runner 再清目錄**：Runner 的建構式擋掉「run 目錄在 repo 底下」，
    # 而 `--clean` 是一個會刪東西的動作。順序反過來就等於先刪再檢查。
    r = Runner(args)
    run_dir = pathlib.Path(args.run_dir).resolve()
    if args.clean and run_dir.exists():
        remove_workspace(run_dir)
    r._started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    return r.go()


if __name__ == "__main__":
    raise SystemExit(main())
