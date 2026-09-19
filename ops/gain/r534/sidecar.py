#!/usr/bin/env python3
"""這支在架構裡承重什麼：R534 的**判斷都在 Python 這一邊**。

pi 的擴充是 TypeScript，而 Vacant 的承重件（沙箱、目錄級驗收、樹雜湊、
簽章鏈）全部是 Python。如果在 TS 裡再寫一份 bwrap 呼叫、再寫一份預算判準、
再寫一份 DENY 正則，那就是**第二把會漂的尺**——而且漂掉的那一天沒有人會發現，
因為兩份各自都「看起來對」。

所以切法是：

    TS 擴充 ＝ pi 這一側的接線（掛鉤、工具註冊、把訊息送回去、抓 wire payload）
    本檔案   ＝ 所有的**判斷**（要不要擋這條指令、驗收過了沒、預算撞線沒、
                這一格的裁決是什麼、簽哪一筆收據）

擴充每做一個決定都來問一次，問的方式是 unix socket 上的 JSONL（一個連線一個
請求一個回應）。`op` 一共八個：

  · `ping`     ——零副作用，預檢用
  · `hello`    ——握手：起點樹雜湊對不上就叫 pi 收掉（起點不對，後面全白跑）
  · `exec`     ——跑一條指令：`deny_reason()` → `Sandbox.run()`，**全文落盤**，
                  回給模型的是截斷版（`piarms.TOOL_OUTPUT_CLIP`）
  · `turn_end` ——預算：回 `stop_reason` 或 null（判準只有 `piarms.budget_stop`）
  · `settled`  ——**閘門本體**：宣告完成之後要 nudge／回饋重改／收掉，這裡決定
  · `message`  ——一則訊息的全文；同時餵 `conversation_sha256`
  · `event`    ——擴充那一側看到的其他東西逐字落盤（wire payload 斷言結果等）
  · `final`    ——簽 `ws_verdict`，封存這一格的狀態

為什麼是**常駐**而不是每次 `python3 -c`：Logbook 的鏈頭與一次性 Ed25519
私鑰要跨呼叫活著。私鑰落盤＝違反 RECORD_SPEC §7，所以它只存在於行程記憶體裡，
行程結束就沒了——這也正是這條鏈能說「事後沒被改過」、不能說「是誰簽的」的原因
（`gain_run.save_receipts` 的同一條誠實邊界，逐字沿用）。

⚠ **紅線**：本檔案沒有任何一條路徑碰得到 `hidden/`。`settled` 跑的是
  **樣板裡那一份**可見驗收（不是工作區裡那一份——模型改得到工作區裡的檔案），
  回饋只轉發 `acceptance.render_failures()` 對可見驗收的渲染。
  隱藏測資由 driver 在工作區凍結＋打包之後、在另一個目錄裡跑，與本檔案無關。

⚠ **誠實邊界（改碼請保留）**：閘門 records and gates，不 proves。它證明
  「宣告完成之後可見驗收先跑了一次，沒過就沒出貨」，**不**證明交出去的東西
  是對的——可見驗收是客戶給的那幾條，不是真需求（`vacant/suitegauge.py`
  的單邊保證）。
"""
from __future__ import annotations

import json
import os
import pathlib
import socket
import sys
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from ops.gain.r530 import acceptance, receipts, wshash  # noqa: E402
from ops.gain.r530.openwork_arms import (SELF_RAN_MARKERS,  # noqa: E402
                                         deny_reason, strip_heredoc_bodies)
from ops.gain.r530.sandbox import SandboxInfraError  # noqa: E402
from ops.gain.r534 import piarms  # noqa: E402

#: unix socket 路徑的核心限制（`sun_path`）。超過就是一個完全不提長度的
#: `OSError` ⇒ 自己先擋，訊息自己寫清楚。
SUN_PATH_MAX = 104

#: provider 連不上時 pi 會自己重試（`auto_retry`），重試耗盡後以 stopReason
#: "error" 的空訊息結束。連續這麼多次就判這一格 infra_void——**基建事件不是結果**。
_PROVIDER_ERROR_LIMIT = 4

#: `calls.jsonl` 的寫入鎖。四格併跑時各有自己的檔案，但同一格的擴充會從
#: 多條連線同時寫 ⇒ 沒有這把鎖，JSONL 會出現半行。
_LOG_LOCK = threading.Lock()


def looks_like_self_ran_visible(command: str) -> bool:
    """「worker 自己跑過可見驗收沒有」——沿用 R530 §四-1 P-W7 的操作型定義。"""
    shell = strip_heredoc_bodies(command)
    return any(m in shell for m in SELF_RAN_MARKERS)


class CellSidecar:
    """一格（一個 cell × 一題 × 一份 attempt）的判斷端。

    每個連線一條執行緒；共享狀態一律走 `self._lock`，簽章走 `book_lock`
    （同一條鏈四格共用時必須序列化）。跑完 driver 取走 `self.state`。
    """

    def __init__(self, *, sock_path: str | os.PathLike, cell: str, arm: str,
                 policy: str, task_id: str,
                 workspace: pathlib.Path, visible_dir: pathlib.Path,
                 verify_root: pathlib.Path, sandbox, book, ident,
                 book_lock: threading.Lock, calls_path: pathlib.Path,
                 ws_start_sha256: str, attempt: int, t0: float,
                 offsets: dict | None = None) -> None:
        self.sock_path = str(sock_path)
        if len(self.sock_path.encode("utf-8")) > SUN_PATH_MAX:
            raise SystemExit(
                f"socket 路徑 {len(self.sock_path)} 位元組 > {SUN_PATH_MAX}："
                f"{self.sock_path}——換一個短的 --sock-dir。停。")
        self.cell = cell
        self.arm = arm
        self.policy = policy
        self.task_id = task_id
        self.workspace = pathlib.Path(workspace)
        self.visible_dir = pathlib.Path(visible_dir)
        self.verify_root = pathlib.Path(verify_root)
        self.sandbox = sandbox
        self.book = book
        self.ident = ident
        self.book_lock = book_lock
        self.calls_path = pathlib.Path(calls_path)
        self.ws_start_sha256 = ws_start_sha256
        self.attempt = attempt
        self.t0 = t0
        #: `resample` 政策下，前幾份已經用掉的額度。**預算跨份累計**——
        #: 否則「最多三份」會變成「三倍預算」，那就不是同預算上限了。
        self.offsets = {"calls_used": 0, "completion_tokens": 0,
                        "prompt_tokens": 0, "reasoning_tokens": 0,
                        "tool_calls": 0, **(offsets or {})}

        self._srv: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        #: 擴充成功握手就 set。driver 等這一個再送 prompt——**不要用 pi 的
        #: stdout 當就緒訊號**：`--mode rpc` 不吐 session header（那是 json 模式
        #: 才有的東西），等它會等到逾時，而且看起來像「模型不回話」
        #: （2026-09-18 smoke1 就是這樣紅的）。
        self.hello_event = threading.Event()
        #: `conversation_sha256` 的唯一輸入：擴充逐則回報的 role/content。
        self._messages: list[dict] = []

        b = piarms.R534_BUDGET
        self.state: dict = {
            "cell": cell, "arm": arm, "policy": policy, "task_id": task_id,
            "attempt": attempt,
            "ws_start_sha256": ws_start_sha256, "ws_end_sha256": None,
            "calls_used": int(self.offsets["calls_used"]),
            "completion_tokens": int(self.offsets["completion_tokens"]),
            "prompt_tokens": int(self.offsets["prompt_tokens"]),
            "reasoning_tokens": int(self.offsets["reasoning_tokens"]),
            "tool_calls": int(self.offsets["tool_calls"]),
            "tool_blocked_n": 0, "deny_hidden_read_n": 0,
            "deny_escape_n": 0, "deny_network_n": 0,
            "self_ran_visible": False,
            "gate_rounds": 0, "nudges": 0,
            "nudge_budget": int(b["nudge_budget"]),
            "declared_done": False, "settled_n": 0,
            "visible_pass": None, "visible_passed": None, "visible_total": None,
            "verdict_sha256": None,
            "accepted": None, "stop_reason": None, "refused": None,
            "infra_void": None, "harness_void_reason": None,
            "system_prompt_sha256": None, "tools_schema_sha256": None,
            "wire_reasoning_effort_seen": [],
            "attempt_hashes": [], "verdict_hash": None,
            "requests_seen": 0, "messages_n": 0,
            "provider_errors": 0,
        }

    # ── 生命週期 ──────────────────────────────────────────────────────
    def start(self) -> None:
        pathlib.Path(self.sock_path).parent.mkdir(parents=True, exist_ok=True)
        if os.path.exists(self.sock_path):
            os.unlink(self.sock_path)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(self.sock_path)
        srv.listen(64)
        srv.settimeout(0.5)
        self._srv = srv
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
        if self._srv is not None:
            try:
                self._srv.close()
            except OSError:
                pass
        try:
            os.unlink(self.sock_path)
        except OSError:
            pass

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._srv.accept()
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                break
            threading.Thread(target=self._serve, args=(conn,),
                             daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        with conn:
            conn.settimeout(3600)
            buf = b""
            try:
                while b"\n" not in buf:
                    chunk = conn.recv(1 << 16)
                    if not chunk:
                        return
                    buf += chunk
                line, _, _rest = buf.partition(b"\n")
                req = json.loads(line.decode("utf-8"))
            except Exception as exc:                        # noqa: BLE001
                self._log({"kind": "sidecar_protocol_error", "error": repr(exc)})
                return
            try:
                resp = self._dispatch(req)
            except SandboxInfraError as exc:
                # 沙箱起不來＝基建故障，不是候選的錯（`checks.CheckInfraError`
                # 的同一條紀律）。這一格作廢，不進分子也不進分母。
                with self._lock:
                    self.state["infra_void"] = f"sandbox: {exc}"
                self._log({"kind": "infra_void", "op": req.get("op"),
                           "error": repr(exc)})
                resp = {"ok": False, "infra_void": str(exc)}
            except Exception as exc:                        # noqa: BLE001
                self._log({"kind": "sidecar_error", "op": req.get("op"),
                           "error": repr(exc),
                           "traceback": traceback.format_exc()})
                resp = {"ok": False, "error": repr(exc)}
            try:
                conn.sendall(
                    (json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
            except OSError:
                pass

    # ── 落盤（**唯一**寫入 calls.jsonl 的地方）────────────────────────
    def _log(self, rec: dict) -> None:
        rec = {"ts_ms": int(time.time() * 1000), "cell": self.cell,
               "task_id": self.task_id, "attempt": self.attempt, **rec}
        self.calls_path.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_LOCK:
            with self.calls_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())    # 中途被砍也要留得住（鐵律 3）

    def _dispatch(self, req: dict) -> dict:
        op = req.get("op")
        fn = getattr(self, f"_op_{op}", None)
        if fn is None:
            return {"ok": False, "error": f"unknown op {op!r}"}
        return fn(req)

    # ── op ────────────────────────────────────────────────────────────
    def _op_ping(self, req: dict) -> dict:
        return {"ok": True, "pong": True, "cell": self.cell,
                "task_id": self.task_id}

    def _op_hello(self, req: dict) -> dict:
        got = wshash.tree_hash(self.workspace)
        ok = (got == self.ws_start_sha256)
        self._log({"kind": "hello", "pi_cwd": req.get("cwd"),
                   "pi_mode": req.get("mode"), "pi_version": req.get("version"),
                   "ws_sha256": got, "ws_start_expected": self.ws_start_sha256,
                   "ws_start_ok": ok})
        if not ok:
            with self._lock:
                self.state["harness_void_reason"] = (
                    f"ws_start mismatch: got {got} want {self.ws_start_sha256}")
            return {"ok": False, "void": True,
                    "reason": "workspace start hash mismatch"}
        self.hello_event.set()
        return {"ok": True, "arm": self.arm, "policy": self.policy,
                "tool_timeout_s": int(piarms.R534_BUDGET["tool_timeout_s"]),
                "tool_timeout_max_s":
                    int(piarms.R534_BUDGET["tool_timeout_max_s"])}

    def _op_event(self, req: dict) -> dict:
        """擴充那一側看到的東西**逐字**落盤。不截斷、不去識別。"""
        rec = dict(req.get("record") or {})
        kind = rec.get("kind", "pi_event")
        with self._lock:
            if kind == "provider_request":
                self.state["requests_seen"] += 1
                eff = rec.get("reasoning_effort", "<absent>")
                if eff not in self.state["wire_reasoning_effort_seen"]:
                    self.state["wire_reasoning_effort_seen"].append(eff)
                if rec.get("tools_schema_sha256"):
                    self.state["tools_schema_sha256"] = rec["tools_schema_sha256"]
                if rec.get("system_prompt_sha256"):
                    self.state["system_prompt_sha256"] = \
                        rec["system_prompt_sha256"]
            elif kind == "system_prompt":
                self.state["system_prompt_sha256"] = rec.get("sha256")
            elif kind == "harness_void":
                self.state["harness_void_reason"] = rec.get("reason")
        self._log({**rec, "kind": kind, "src": "pi_extension"})
        return {"ok": True}

    def _op_message(self, req: dict) -> dict:
        """一則訊息的全文（`message_end`）。**不截斷。**"""
        msg = req.get("message") or {}
        with self._lock:
            self._messages.append({"role": msg.get("role"),
                                   "content": msg.get("content", "")})
            self.state["messages_n"] = len(self._messages)
        self._log({"kind": "message", "src": "pi_extension", "message": msg})
        return {"ok": True, "n": self.state["messages_n"]}

    def _op_turn_end(self, req: dict) -> dict:
        """預算。**判準只有 `piarms.budget_stop` 一份。**"""
        with self._lock:
            st = self.state
            off = self.offsets
            st["calls_used"] = off["calls_used"] + int(req.get("calls_used", 0))
            st["completion_tokens"] = off["completion_tokens"] + int(
                req.get("completion_tokens", 0))
            st["prompt_tokens"] = off["prompt_tokens"] + int(
                req.get("prompt_tokens", 0))
            st["reasoning_tokens"] = off["reasoning_tokens"] + int(
                req.get("reasoning_tokens", 0))
            st["tool_calls"] = max(int(st["tool_calls"]),
                                   off["tool_calls"] + int(req.get("tool_calls", 0)))
            stop = piarms.budget_stop(
                calls_used=st["calls_used"],
                completion_tokens=st["completion_tokens"],
                tool_calls=st["tool_calls"],
                elapsed_s=time.time() - self.t0,
                last_prompt_tokens=int(req.get("last_prompt_tokens", 0)))
            # provider 連不上／回錯：pi 自己重試三次然後以空訊息結束。
            # 那不是模型的表現，是基建事件 ⇒ 累積到上限就作廢這一格，
            # **不要讓它變成一列看起來正常的失敗**。
            if req.get("assistant_stop_reason") == "error":
                st["provider_errors"] += 1
                if st["provider_errors"] >= _PROVIDER_ERROR_LIMIT:
                    st["infra_void"] = (
                        f"provider_error x{st['provider_errors']}: "
                        f"{req.get('error_message')}")
                    stop = stop or "harness_void"
            if stop is not None and st["stop_reason"] is None:
                st["stop_reason"] = stop
            snapshot = {k: st[k] for k in
                        ("calls_used", "completion_tokens", "prompt_tokens",
                         "reasoning_tokens", "tool_calls", "provider_errors")}
        self._log({"kind": "turn_end", "usage": req.get("usage"),
                   **snapshot, "budget_stop": stop})
        return {"ok": True, "stop_reason": stop}

    def _op_exec(self, req: dict) -> dict:
        """一條指令：擋門 → 沙箱 → **全文落盤** → 回截斷版給模型。"""
        command = req.get("command") or ""
        timeout_s = float(req.get("timeout_s")
                          or piarms.R534_BUDGET["tool_timeout_s"])
        timeout_s = min(timeout_s,
                        float(piarms.R534_BUDGET["tool_timeout_max_s"]))
        with self._lock:
            self.state["tool_calls"] += 1
            n = self.state["tool_calls"]
        hit = deny_reason(command)
        if hit is not None:
            why, tag = hit
            with self._lock:
                self.state["tool_blocked_n"] += 1
                key = {"r530_hidden_read": "deny_hidden_read_n",
                       "r530_escape": "deny_escape_n",
                       "r530_network": "deny_network_n"}.get(tag)
                if key:
                    self.state[key] += 1
            self._log({"kind": "tool_exec", "n": n, "command": command,
                       "blocked": True, "deny_tag": tag, "deny_why": why})
            return {"ok": True, "blocked": True, "deny_tag": tag,
                    "text": piarms.BLOCKED_TEMPLATE.format(
                        header=piarms.TOOL_RESULT_HEADER, command=command,
                        why=why)}
        res = self.sandbox.run(command, workspace=self.workspace,
                               timeout_s=timeout_s)
        if looks_like_self_ran_visible(command) and res.rc is not None:
            with self._lock:
                self.state["self_ran_visible"] = True
        self._log({"kind": "tool_exec", "n": n, "command": command,
                   "blocked": False, "rc": res.rc, "timed_out": res.timed_out,
                   "wall_ms": res.wall_ms, "stdout": res.stdout,
                   "stderr": res.stderr, "argv": res.argv})
        return {"ok": True, "blocked": False, "rc": res.rc,
                "timed_out": res.timed_out,
                "text": piarms.TOOL_RESULT_TEMPLATE.format(
                    header=piarms.TOOL_RESULT_HEADER, command=command,
                    rc=("timeout" if res.timed_out else res.rc),
                    stdout=piarms.clip(res.stdout),
                    stderr=piarms.clip(res.stderr))}

    # ── 閘門本體（四格唯一的分岔點）────────────────────────────────────
    def _op_settled(self, req: dict) -> dict:
        """宣告完成之後要做什麼。回 action ∈ {"nudge","feedback","stop"}。

        ⚠ `plain` 的 `accepted` **結構性恆為 True**，包含「宣告完成但什麼都
          沒寫」那一格（nudge 額度用完之後）。這不是量測差是結構差，
          **每一次引用都要跟著講這一句**。
        """
        with self._lock:
            self.state["settled_n"] += 1
            self.state["declared_done"] = True
            pre_stop = self.state["stop_reason"]
        ws_now = wshash.tree_hash(self.workspace)
        untouched = (ws_now == self.ws_start_sha256)

        # 0) 預算已經撞線（`turn_end` 判的）⇒ 直接收，不再進閘門。
        if pre_stop is not None:
            return self._settle_stop(pre_stop, ws_now,
                                     accepted=(self.arm == "plain"))

        # 1) nudge：**四格共用**，擋的是「自認完成 ≠ 真的完成」。
        #    只給 vacant 會變成四格之間的第二個差異，那樣就切不出閘門的效果。
        if untouched:
            with self._lock:
                used, budget = self.state["nudges"], self.state["nudge_budget"]
            if used < budget:
                with self._lock:
                    self.state["nudges"] += 1
                self._log({"kind": "nudge", "n": used + 1, "ws_sha256": ws_now})
                return {"ok": True, "action": "nudge",
                        "message": piarms.NUDGE_NO_WORK}
            return self._settle_stop("nudge_exhausted", ws_now,
                                     accepted=(self.arm == "plain"))

        # 2) plain：宣告完成就收。沒有閘門、沒有回饋、沒有拒交語意。
        if self.arm == "plain":
            return self._settle_stop("declared_done", ws_now, accepted=True)

        # 3) vacant：跑**樣板那一份**可見驗收（不是工作區那一份——模型改得到）
        result = acceptance.run_suite(
            self.sandbox, self.workspace, self.visible_dir, suite="visible",
            task_id=self.task_id, verify_root=self.verify_root,
            timeout_s=float(piarms.R534_BUDGET["gate_test_timeout_s"]))
        with self._lock:
            self.state["gate_rounds"] += 1
            gate_round = self.state["gate_rounds"]
            self.state["visible_pass"] = bool(result.get("all_pass"))
            self.state["visible_passed"] = result.get("passed")
            self.state["visible_total"] = result.get("total")
            self.state["verdict_sha256"] = result.get("result_sha256")
        self._log({"kind": "gate", "gate_round": gate_round,
                   "ws_sha256": ws_now, "visible_result": result})
        entry_hash = self._sign_attempt(gate_round, ws_now,
                                        result.get("result_sha256"))
        with self._lock:
            self.state["attempt_hashes"].append(entry_hash)

        if result.get("all_pass"):
            return self._settle_stop("visible_pass", ws_now, accepted=True)

        if self.policy == "revise":
            if gate_round < int(piarms.R534_BUDGET["max_gate_rounds"]):
                return {"ok": True, "action": "feedback",
                        "gate_round": gate_round,
                        "message": piarms.FEEDBACK_TEMPLATE.format(
                            block=acceptance.render_failures(result))}
            return self._settle_stop("gate_exhausted", ws_now, accepted=False)

        # policy == "resample"：這一份不過就收掉，由 driver 重置工作區重抽。
        if self.attempt < int(piarms.R534_BUDGET["max_conf_attempts"]):
            return self._settle_stop("conf_attempt_failed", ws_now,
                                     accepted=False, final=False)
        return self._settle_stop("attempts_exhausted", ws_now, accepted=False)

    def _settle_stop(self, stop_reason: str, ws_sha256: str, *,
                     accepted: bool, final: bool = True) -> dict:
        if final and stop_reason not in piarms.STOP_REASONS:
            raise ValueError(f"stop_reason {stop_reason!r} 不在封閉集合裡")
        with self._lock:
            self.state["stop_reason"] = stop_reason
            self.state["accepted"] = bool(accepted)
            self.state["ws_end_sha256"] = ws_sha256
            self.state["refused"] = stop_reason in piarms.REFUSAL_REASONS
        self._log({"kind": "settle", "stop_reason": stop_reason,
                   "accepted": bool(accepted), "ws_sha256": ws_sha256,
                   "final": final})
        return {"ok": True, "action": "stop", "stop_reason": stop_reason,
                "accepted": bool(accepted), "final": final}

    # ── 收據 ──────────────────────────────────────────────────────────
    def _sign_attempt(self, gate_round: int, ws_sha256: str,
                      verdict_sha256: str | None) -> str:
        """每一個閘門輪簽一筆 `ws_attempt`。**鏈上放雜湊，全文放 calls.jsonl。**

        `etype` 逐字沿用 `ops/gain/r530/receipts.py` 的兩個常數 ⇒
        `ops/gain/replay/verify_run_receipts.py` 一個字都不用改。
        """
        with self.book_lock:
            entry = receipts.append_attempt(
                self.book, self.ident, task_id=self.task_id, arm=self.cell,
                attempt=self.attempt, gate_round=gate_round,
                ws_sha256=ws_sha256, verdict_sha256=verdict_sha256,
                conversation_sha256=self.conversation_sha256(),
                run="r534", policy=self.policy)
        return entry.hash()

    def _op_final(self, req: dict) -> dict:
        """每格一筆 `ws_verdict`。擴充在 `session_shutdown` 打這一通。"""
        ws_end = wshash.tree_hash(self.workspace)
        with self._lock:
            st = self.state
            st["ws_end_sha256"] = ws_end
            if st["stop_reason"] is None:
                # pi 結束了但 harness 一次裁決都沒收到＝**基建事件不是結果**。
                st["stop_reason"] = "pi_exit_unsettled"
                st["accepted"] = bool(self.arm == "plain" and st["declared_done"])
                st["refused"] = False
            snapshot = dict(st)
        with self.book_lock:
            entry = receipts.append_verdict(
                self.book, self.ident, task_id=self.task_id, arm=self.cell,
                accepted=bool(snapshot["accepted"]),
                ws_start_sha256=self.ws_start_sha256, ws_end_sha256=ws_end,
                verdict_sha256=snapshot["verdict_sha256"],
                conversation_sha256=self.conversation_sha256(),
                stop_reason=snapshot["stop_reason"],
                run="r534", policy=self.policy,
                calls_used=snapshot["calls_used"],
                gate_rounds=snapshot["gate_rounds"])
        with self._lock:
            self.state["verdict_hash"] = entry.hash()
        self._log({"kind": "final", "state": dict(self.state)})
        return {"ok": True, "verdict_hash": entry.hash()}

    def conversation_sha256(self) -> str:
        """整段對話的 sha256。

        **口徑講清楚**：pi 的對話存在 pi 自己的 session JSONL 裡，sidecar 看不到
        provider 的原始訊息陣列。這裡簽的是**擴充逐則回報的 `message_end`**
        （`pi_ext/vacant_gate.ts` 每一則訊息都送一次 `message`），欄位選法與
        `receipts.conversation_digest` 一致（只取 role 與 content），
        但**來源是擴充的回報，不是 provider 的 wire bytes**。
        wire 的真相在 `wire.jsonl`；兩邊對不起來就是 harness 有問題。
        """
        with self._lock:
            msgs = list(self._messages)
        return receipts.conversation_digest(msgs)


def main() -> int:
    """零模型呼叫的自我檢查：起一個 sidecar、打 `ping`、關掉。

    用途是**發射前**證明 unix socket 這條路在這台機器上通得了，
    而不是等到第一格跑到一半才發現路徑太長或權限不對。
    """
    import argparse
    import tempfile

    from vacant.identity import Identity
    from vacant.logbook import Logbook

    ap = argparse.ArgumentParser(description="R534 sidecar 自我檢查（零模型呼叫）")
    ap.add_argument("--sock", default=None)
    args = ap.parse_args()

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="r534sc_"))
    (tmp / "ws").mkdir()
    (tmp / "ws" / "a.txt").write_text("x", encoding="utf-8")
    sc = CellSidecar(
        sock_path=args.sock or str(tmp / "s.sock"), cell="A1", arm="vacant",
        policy="revise", task_id="selftest", workspace=tmp / "ws",
        visible_dir=tmp / "ws", verify_root=tmp / "v", sandbox=None,
        book=Logbook(), ident=Identity.generate(), book_lock=threading.Lock(),
        calls_path=tmp / "calls.jsonl",
        ws_start_sha256=wshash.tree_hash(tmp / "ws"), attempt=1, t0=time.time())
    sc.start()
    c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    c.connect(sc.sock_path)
    c.sendall(json.dumps({"op": "ping"}).encode("utf-8") + b"\n")
    resp = c.recv(1 << 16).decode("utf-8")
    c.close()
    # hello 走一次真的樹雜湊比對
    c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    c.connect(sc.sock_path)
    c.sendall(json.dumps({"op": "hello", "cwd": str(tmp)}).encode("utf-8") + b"\n")
    hello = c.recv(1 << 16).decode("utf-8")
    c.close()
    sc.stop()
    ok = (json.loads(resp).get("pong") is True
          and json.loads(hello).get("ok") is True)
    print(resp.strip())
    print(hello.strip())
    print("sidecar selftest", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
