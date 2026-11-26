#!/usr/bin/env python3
"""ops.e1.run_e1 — E1′ 實驗執行器（B0／B0x3／B2／S／S+B2／O，真實 bwrap 隔離、續跑安全、JSONL 落盤）。

這支在架構裡承重什麼
====================
依據計畫檔（`PLAN.json`）在多條程式碼或文件任務鏈上依序執行各臂與各回合，並保證以下實驗紀律：
1. **未提交拒跑**：計畫檔或 `ops/e1/` 程式碼只要在 git 裡尚未 commit（或未追蹤），立刻拒絕啟動。
2. **負控制先行**：啟動任何 worker 之前必先對真實路徑跑完 `negative_controls.run_negative_controls`，
   任何一項洩漏即拒絕啟動。
3. **真實沙箱隔離**：每次 worker 執行都在獨立 `bwrap`（只讀掛載系統、pi、node、去敏 `PI_CODING_AGENT_DIR`；
   可寫僅限當回合 `/work` 副本；`HOME`/`/tmp` 為 tmpfs；`--clearenv`＋`--die-with-parent`）。
   B2 可見測試與獨立評分在另起的 `--unshare-net` bwrap（含記憶體與逾時限制）執行，結果只由宿主落盤。
4. **同提示公平比較**：`S`／`S+B2`／`O` 給 agent 的任務文字與 `B0` 逐字相同（絕不洩漏範圍）；
   範圍提交完全在宿主端原子執行。
5. **斷點續跑安全**：每個 `(chain, arm, round)` 獨立落地 `done.json`、`record.json` 與狀態檔，
   並將計畫 sha256 釘入 `ROOT/RUN.json`；續跑時自動跳過已完成回合、接續上一回合提交後的狀態，
   且同一個 `ROOT` 換計畫就拒跑。

誠實邊界（改碼請保留）
----------------------
- 本執行器量的是 harness 端範圍提交與驗收閘門機制的效果，不代表互動式安裝產品後的自然表現。
- `--calibrate` 僅跑 `B0`（校準基線回歸率與時間），不可拿來比較處理臂。
- 若遇到基礎設施失敗（0 次成功模型回應且有連線／端點錯誤），標記 `infra_void: true` 而不混入分母。

用法：
  python3 ops/e1/run_e1.py --plan PLAN.json --root ROOT [--calibrate]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import pathlib
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.e1 import (
    ARMS_CODE,
    ARMS_DOC,
    DEFAULT_PI_CFG_DIR,
    PLAN_SCHEMA,
    RESULT_SCHEMA,
    assert_ks1_clean,
    atomic_write_json,
    atomic_write_text,
    sha256_bytes,
    utc_now_iso,
)
from ops.e1.evaluate import (
    check_code_z_gate,
    check_doc_structural,
    compute_doc_scope_s,
    evaluate_code_source,
    evaluate_doc_report,
)
from ops.e1.negative_controls import run_claude_negative_controls, run_negative_controls
from ops.e1.netproxy import DEFAULT_ALLOWED_CONNECT_HOSTS, AllowlistUnixProxy
from ops.e1.sandbox import (
    build_claude_worker_bwrap_argv,
    build_worker_bwrap_argv,
    kill_all_live,
    prepare_claude_credentials,
    prepare_sanitized_pi_cfg,
    run_sandboxed,
)
from ops.e1.units import (
    atomic_commit_file,
    commit_code_scoped,
    commit_doc_scoped,
    extract_code_scope_from_task,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE_SERVER_PY = REPO_ROOT / "ops" / "d2" / "source_server.py"
HOST_FMT = "{chain_id}.e1-sources.example"

CLAUDE_ALLOWED_TOOLS = "Bash,Read,Edit,Write,Glob,Grep"
CLAUDE_DISALLOWED_TOOLS = "WebFetch,WebSearch"


def build_claude_cli_argv(model_id: str, prompt: str) -> list[str]:
    """組合 Claude Code worker 在沙箱內執行的 CLI 指令列（僅允許 6 項本機工具，禁用 WebFetch/WebSearch）。"""
    return [
        "claude",
        "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--model", model_id,
        "--permission-mode", "bypassPermissions",
        "--tools", CLAUDE_ALLOWED_TOOLS,
        "--allowedTools", CLAUDE_ALLOWED_TOOLS,
        "--disallowedTools", CLAUDE_DISALLOWED_TOOLS,
        "--no-session-persistence",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--",
        prompt,
    ]

_LOCK = threading.Lock()
_INFRA_ERR_RE = re.compile(
    r"ECONNREFUSED|ECONNRESET|ENOTFOUND|EAI_AGAIN|fetch failed|socket hang up|"
    r"Connection error|connection refused|Premature close|not loaded|unloaded|50[234]",
    re.I,
)


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _git(args: list[str], cwd: pathlib.Path) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=20)
        return r.returncode, (r.stdout + r.stderr).strip()
    except OSError as exc:
        return 1, str(exc)


def assert_git_clean(plan_path: pathlib.Path) -> str:
    """檢查 `ops/e1/` 與計畫檔皆已 commit 且工作樹乾淨；不符則立即拒絕啟動。回傳 HEAD sha。"""
    rc_head, head = _git(["rev-parse", "HEAD"], REPO_ROOT)
    if rc_head != 0 or not head:
        raise SystemExit(f"拒絕啟動：無法取得 git HEAD（{head}）")

    rc_code, dirty_code = _git(["status", "--porcelain", "--", "ops/e1"], REPO_ROOT)
    if rc_code != 0 or dirty_code:
        raise SystemExit(f"拒絕啟動：ops/e1/ 有未提交改動，請先 commit：\n{dirty_code}")

    p_abs = plan_path.resolve()
    try:
        rel = p_abs.relative_to(REPO_ROOT.resolve())
    except ValueError:
        raise SystemExit(f"拒絕啟動：計畫檔 {p_abs} 不在 repo 內，無法驗證已 commit")

    rc_trk, _ = _git(["ls-files", "--error-unmatch", "--", str(rel)], REPO_ROOT)
    if rc_trk != 0:
        raise SystemExit(f"拒絕啟動：計畫檔 {rel} 尚未加入 git 追蹤與 commit")

    rc_plan, dirty_plan = _git(["status", "--porcelain", "--", str(rel)], REPO_ROOT)
    if rc_plan != 0 or dirty_plan:
        raise SystemExit(f"拒絕啟動：計畫檔 {rel} 有未提交改動：\n{dirty_plan}")

    return head


def usage_from_pi_log(log_path: pathlib.Path) -> dict | None:
    """解析 `pi --mode json` NDJSON 事件流：每個成功 assistant `message_end` 計一次呼叫與 token。"""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    calls = errors = tin = tout = 0
    saw_json = False
    final_error: str | None = None
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("{"):
            continue
        try:
            obj = json.loads(s)
        except ValueError:
            continue
        if not isinstance(obj, dict) or "type" not in obj:
            continue
        saw_json = True
        if obj.get("type") != "message_end":
            continue
        msg = obj.get("message")
        if not isinstance(msg, dict) or msg.get("role") not in ("assistant", None):
            continue
        if msg.get("stopReason") == "error" or msg.get("errorMessage"):
            errors += 1
            final_error = str(msg.get("errorMessage") or "error")[:300]
            continue
        final_error = None
        u = msg.get("usage")
        if not isinstance(u, dict):
            continue
        calls += 1
        tin += int(u.get("input") or u.get("input_tokens") or u.get("prompt_tokens") or 0)
        tout += int(u.get("output") or u.get("output_tokens") or u.get("completion_tokens") or 0)
    if not saw_json:
        return None
    return {
        "calls": calls,
        "errors": errors,
        "input": tin,
        "output": tout,
        "final_error": final_error,
    }


def usage_from_claude_log(log_path: pathlib.Path) -> dict | None:
    """解析 `claude -p --output-format stream-json --verbose`（亦相容單筆 `result` JSON）的用量與費用。

    回傳與 pi 相同的基礎欄位（`calls`/`errors`/`input`/`output`/`final_error`），
    並補上 `cache_creation_input_tokens`、`cache_read_input_tokens`、`num_turns`、`cost_usd`。
    """
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    saw_json = False
    saw_assistant = False
    msg_usage: dict[str, dict] = {}
    err_ids: set[str] = set()
    errors = 0
    final_error: str | None = None
    result_obj: dict | None = None

    for idx, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if not isinstance(obj, dict) or "type" not in obj:
            continue
        saw_json = True
        etype = obj.get("type")
        if etype == "assistant":
            saw_assistant = True
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
            is_err = bool(
                obj.get("is_api_error_message")
                or obj.get("error")
                or obj.get("api_error")
                or msg.get("model") == "<synthetic>"
            )
            mid = msg.get("id")
            if is_err:
                ekey = str(mid) if mid else f"_err_{idx}"
                if ekey not in err_ids:
                    err_ids.add(ekey)
                    errors += 1
                err_txt = None
                content = msg.get("content")
                if isinstance(content, list):
                    parts = [str(c.get("text") or "") for c in content if isinstance(c, dict) and c.get("text")]
                    if parts:
                        err_txt = " ".join(parts)
                final_error = str(err_txt or obj.get("api_error") or obj.get("error") or "error")[:300]
            else:
                key = str(mid) if mid else f"_anon_{idx}"
                u = msg.get("usage")
                msg_usage[key] = u if isinstance(u, dict) else {}
                final_error = None
        elif etype == "result":
            result_obj = obj
            if obj.get("is_error"):
                if errors == 0:
                    errors = 1
                final_error = str(obj.get("result") or obj.get("api_error") or obj.get("subtype") or "error")[:300]

    if not saw_json:
        return None

    if saw_assistant:
        calls = len(msg_usage)
    elif result_obj is not None:
        ru_tmp = result_obj.get("usage") if isinstance(result_obj.get("usage"), dict) else {}
        has_usage = bool(result_obj.get("modelUsage")) or any(
            int(ru_tmp.get(k) or 0) > 0
            for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        )
        calls = int(result_obj.get("num_turns") or 0) if (not result_obj.get("is_error") and has_usage) else 0
    else:
        calls = 0

    ru = result_obj.get("usage") if isinstance(result_obj, dict) and isinstance(result_obj.get("usage"), dict) else None
    if ru is not None:
        tin = int(ru.get("input_tokens") or 0)
        tout = int(ru.get("output_tokens") or 0)
        cache_create = int(ru.get("cache_creation_input_tokens") or 0)
        cache_read = int(ru.get("cache_read_input_tokens") or 0)
    else:
        tin = sum(int(u.get("input_tokens") or 0) for u in msg_usage.values())
        tout = sum(int(u.get("output_tokens") or 0) for u in msg_usage.values())
        cache_create = sum(int(u.get("cache_creation_input_tokens") or 0) for u in msg_usage.values())
        cache_read = sum(int(u.get("cache_read_input_tokens") or 0) for u in msg_usage.values())

    num_turns = (
        int(result_obj.get("num_turns"))
        if isinstance(result_obj, dict) and result_obj.get("num_turns") is not None
        else calls
    )
    raw_cost = result_obj.get("total_cost_usd") if isinstance(result_obj, dict) else None
    cost_usd = float(raw_cost) if isinstance(raw_cost, (int, float)) else None

    return {
        "calls": calls,
        "errors": errors,
        "input": tin,
        "output": tout,
        "cache_creation_input_tokens": cache_create,
        "cache_read_input_tokens": cache_read,
        "num_turns": num_turns,
        "cost_usd": cost_usd,
        "final_error": final_error,
    }


def _parse_allowed_connect_hosts(raw_list: Any) -> list[tuple[str, int]]:
    if not raw_list:
        return list(DEFAULT_ALLOWED_CONNECT_HOSTS)
    out: list[tuple[str, int]] = []
    for item in raw_list:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            out.append((str(item[0]).strip().lower(), int(item[1])))
        elif isinstance(item, str) and ":" in item:
            h, p = item.rsplit(":", 1)
            out.append((h.strip().lower(), int(p)))
        else:
            raise SystemExit(f"不合法的 allowed_connect_hosts 項目：{item!r}")
    return out


def load_plan(plan_path: pathlib.Path) -> dict:
    raw = json.loads(plan_path.read_text(encoding="utf-8"))
    if raw.get("schema") != PLAN_SCHEMA:
        raise SystemExit(f"計畫檔 schema 應為 {PLAN_SCHEMA}：{plan_path}")
    for req_k in ("id", "arms", "model"):
        if req_k not in raw:
            raise SystemExit(f"計畫檔缺必要欄位 {req_k}：{plan_path}")

    # 解析鏈目錄清單
    chain_dirs: list[pathlib.Path] = []
    if "chains" in raw and raw["chains"]:
        for c in raw["chains"]:
            p = pathlib.Path(os.path.expandvars(os.path.expanduser(str(c))))
            if not p.is_absolute():
                p = (plan_path.parent / p).resolve()
            chain_dirs.append(p)
    elif "chains_dir" in raw and raw["chains_dir"]:
        base = pathlib.Path(os.path.expandvars(os.path.expanduser(str(raw["chains_dir"]))))
        if not base.is_absolute():
            base = (plan_path.parent / base).resolve()
        idx_p = base / "index.json"
        if idx_p.is_file():
            idx = json.loads(idx_p.read_text(encoding="utf-8"))
            for ch in idx.get("chains") or []:
                chain_dirs.append(pathlib.Path(ch["path"]))
        else:
            for d in sorted(base.iterdir()):
                if (d / "chain.json").is_file():
                    chain_dirs.append(d)
    else:
        raise SystemExit("計畫檔必須提供 `chains` 或 `chains_dir`")

    if not chain_dirs:
        raise SystemExit("計畫檔未解析到任何任務鏈")
    for d in chain_dirs:
        if not (d / "chain.json").is_file():
            raise SystemExit(f"找不到鏈規格檔：{d / 'chain.json'}")

    model_cfg = dict(raw["model"])
    agent = str(model_cfg.get("agent") or "pi")
    if agent not in ("pi", "claude"):
        raise SystemExit(f"不支援的 model.agent：{agent!r}（僅支援 'pi' 或 'claude'）")
    model_cfg["agent"] = agent
    providers = list(model_cfg.get("providers") or [])
    if not providers and model_cfg.get("provider"):
        providers = [str(model_cfg["provider"])]
    if agent == "claude":
        if not model_cfg.get("model"):
            raise SystemExit("計畫檔 model.agent='claude' 必須指定 `model.model`（例如 'claude-haiku-5-5'）")
        if not providers:
            providers = ["anthropic"]
    else:
        if not providers and not model_cfg.get("fake_agent"):
            raise SystemExit("計畫檔 model 必須指定 `provider` 或 `providers`（或 `fake_agent`）")
    model_cfg["providers"] = providers

    raw["_chain_dirs"] = [str(d.resolve()) for d in chain_dirs]
    raw["_model"] = model_cfg
    raw["_sha256"] = sha256_bytes(_canonical_json({k: v for k, v in raw.items() if not k.startswith("_")}))
    raw["_path"] = str(plan_path.resolve())
    return raw


def _pick_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _SourceServer:
    """管理 `ops/d2/source_server.py` 子行程與路由檔（供文件鏈透過 http_proxy 讀取各週期網站）。"""

    def __init__(self, root: pathlib.Path, port: int = 0) -> None:
        self.root = root
        self.port = port if port > 0 else _pick_free_port()
        self.routes_path = root / "routes.json"
        self.meta_path = root / "routes_meta.json"
        self.log_path = root / "access.jsonl"
        self.proc: subprocess.Popen | None = None
        self._err_fh = None

    def start(self) -> None:
        atomic_write_json(self.routes_path, {})
        atomic_write_json(self.meta_path, {})
        self._err_fh = open(self.root / "source_server.err", "a", encoding="utf-8")
        self.proc = subprocess.Popen(
            [
                sys.executable,
                str(SOURCE_SERVER_PY),
                "--port", str(self.port),
                "--routes", str(self.routes_path),
                "--meta", str(self.meta_path),
                "--log", str(self.log_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=self._err_fh,
            start_new_session=True,
        )
        # 等待監聽就緒
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"source_server 提前結束（rc={self.proc.returncode}）")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError(f"source_server 未於 10 秒內在 port {self.port} 就緒")

    def set_route(self, host: str, site_dir: str, arm: str, cycle: int) -> None:
        with _LOCK:
            routes = json.loads(self.routes_path.read_text(encoding="utf-8")) if self.routes_path.is_file() else {}
            meta = json.loads(self.meta_path.read_text(encoding="utf-8")) if self.meta_path.is_file() else {}
            routes[host] = site_dir
            meta[host] = {"arm": arm, "cycle": cycle}
            atomic_write_json(self.routes_path, routes)
            atomic_write_json(self.meta_path, meta)

    def stop(self) -> None:
        if self.proc is None:
            return
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(timeout=5)
        except Exception:
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except Exception:
                pass
        self.proc = None
        if self._err_fh is not None:
            try:
                self._err_fh.close()
            except OSError:
                pass
            self._err_fh = None


class E1Runner:
    """E1′ 主執行器：管理沙箱設定、負控制、多鏈平行排程、單鏈各臂依序執行與結果落盤。"""

    def __init__(
        self,
        plan_path: pathlib.Path,
        root: pathlib.Path,
        *,
        calibrate: bool = False,
        allow_uncommitted: bool = False,
    ) -> None:
        self.plan_path = plan_path.resolve()
        self.root = root.expanduser().resolve()
        self.calibrate = calibrate
        self.allow_uncommitted = allow_uncommitted
        self.plan = load_plan(self.plan_path)
        self.git_head: str | None = None

        if not self.allow_uncommitted:
            self.git_head = assert_git_clean(self.plan_path)
        else:
            _, h = _git(["rev-parse", "HEAD"], REPO_ROOT)
            self.git_head = h or "unknown"

        self.chains: list[dict] = []
        for cdir_s in self.plan["_chain_dirs"]:
            cdir = pathlib.Path(cdir_s)
            ch = json.loads((cdir / "chain.json").read_text(encoding="utf-8"))
            ch["_dir"] = cdir
            if ch["kind"] == "code":
                ch["_hidden"] = json.loads((cdir / "hidden_tests.json").read_text(encoding="utf-8"))
            elif ch["kind"] == "doc":
                ch["_hidden"] = json.loads((cdir / "hidden_truth.json").read_text(encoding="utf-8"))
            else:
                raise SystemExit(f"不支援的鏈類型：{ch['kind']!r}")
            self.chains.append(ch)

        self.arms: list[str] = ["B0"] if self.calibrate else list(self.plan["arms"])
        self.has_doc = any(c["kind"] == "doc" for c in self.chains)
        self.has_code = any(c["kind"] == "code" for c in self.chains)
        for arm in self.arms:
            if arm not in set(ARMS_CODE) | set(ARMS_DOC):
                raise SystemExit(f"未知的臂名稱：{arm!r}")

        self.attempt_timeout_s = float(self.plan.get("attempt_timeout_s", 600))
        self.eval_timeout_s = float(self.plan.get("eval_timeout_s", 45))
        self.eval_mem_mb = int(self.plan.get("eval_mem_mb", 1024))
        self.max_attempts_b2 = int(self.plan.get("max_attempts_b2", 3))
        self.max_attempts_b0x3 = int(self.plan.get("max_attempts_b0x3", 3))
        self.jobs = max(1, int(self.plan.get("jobs", 1)))

        self.agent_kind: str = str(self.plan["_model"]["agent"])
        self.pi_cfg_dst = self.root / "private_cfg"
        self.no_proxy_hosts: list[str] = []
        self.source_server: _SourceServer | None = None
        self.net_proxy: AllowlistUnixProxy | None = None
        self._claude_creds_tmp: tempfile.TemporaryDirectory[str] | None = None
        self.claude_creds_file: pathlib.Path | None = None
        self.results_path = self.root / "results.jsonl"

    def _log(self, msg: str) -> None:
        line = f"{utc_now_iso()} {msg}"
        with _LOCK:
            print(line, flush=True)
            with open(self.root / "runner.log", "a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def _init_root_and_check_resume(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        run_meta_p = self.root / "RUN.json"
        if run_meta_p.is_file():
            prev = json.loads(run_meta_p.read_text(encoding="utf-8"))
            if prev.get("plan_sha256") != self.plan["_sha256"]:
                raise SystemExit(
                    f"拒絕續跑：{self.root} 的既有計畫 sha256 ({prev.get('plan_sha256')}) "
                    f"與目前計畫 ({self.plan['_sha256']}) 不符"
                )
            if bool(prev.get("calibrate")) != bool(self.calibrate):
                raise SystemExit("拒絕續跑：--calibrate 模式與既有 RUN.json 不一致")
        else:
            atomic_write_json(
                run_meta_p,
                {
                    "schema": "vacant.e1.run/1",
                    "plan_id": self.plan["id"],
                    "plan_path": self.plan["_path"],
                    "plan_sha256": self.plan["_sha256"],
                    "git_head": self.git_head,
                    "agent": self.agent_kind,
                    "model": self.plan["_model"].get("model"),
                    "calibrate": self.calibrate,
                    "arms": self.arms,
                    "n_chains": len(self.chains),
                    "created_utc": utc_now_iso(),
                },
            )

        model_cfg = self.plan["_model"]
        if self.agent_kind == "claude":
            # 僅複製 ~/.claude/.credentials.json 到每跑專屬暫存目錄（run 結束即清理）
            creds_src_s = model_cfg.get("credentials_path")
            creds_src = (
                pathlib.Path(os.path.expandvars(os.path.expanduser(str(creds_src_s))))
                if creds_src_s
                else None
            )
            self._claude_creds_tmp = tempfile.TemporaryDirectory(prefix="e1_claude_creds_")
            self.claude_creds_file = prepare_claude_credentials(
                pathlib.Path(self._claude_creds_tmp.name),
                src_creds_path=creds_src,
            )
        else:
            # 準備去敏後的 pi 設定目錄
            src_cfg_s = model_cfg.get("pi_cfg_dir")
            src_cfg = pathlib.Path(os.path.expandvars(os.path.expanduser(src_cfg_s))) if src_cfg_s else DEFAULT_PI_CFG_DIR
            providers = model_cfg.get("providers") or None
            if src_cfg.is_dir():
                self.no_proxy_hosts = prepare_sanitized_pi_cfg(src_cfg, self.pi_cfg_dst, allowed_providers=providers)
            else:
                self.pi_cfg_dst.mkdir(parents=True, exist_ok=True)

    def _run_preflight_negative_controls(self) -> None:
        first_chain = self.chains[0]
        cdir: pathlib.Path = first_chain["_dir"]
        hidden_p = cdir / ("hidden_tests.json" if first_chain["kind"] == "code" else "hidden_truth.json")
        mat_dir = pathlib.Path(first_chain["materials_dir"]) if first_chain["kind"] == "doc" else None

        other_arm_canary = self.root / "_nc_other_arm_prev"
        other_arm_canary.mkdir(parents=True, exist_ok=True)
        (other_arm_canary / "canary.txt").write_text("other-arm-secret\n", encoding="utf-8")

        model_cfg = self.plan["_model"]
        if self.agent_kind == "claude":
            creds_src_s = model_cfg.get("credentials_path")
            creds_src = (
                pathlib.Path(os.path.expandvars(os.path.expanduser(str(creds_src_s))))
                if creds_src_s
                else None
            )
            claude_bin_s = model_cfg.get("claude_bin")
            rep = run_claude_negative_controls(
                hidden_tests_path=hidden_p,
                eval_dir=self.root,
                other_arm_ws=other_arm_canary,
                materials_dir=mat_dir,
                credentials_src=creds_src,
                claude_bin_override=claude_bin_s,
            )
            atomic_write_json(self.root / "negative_controls.json", rep)
            if not rep.get("passed"):
                raise SystemExit(
                    f"拒絕啟動：Claude 隔離負控制失敗（見 {self.root / 'negative_controls.json'}）："
                    f"leaks={rep.get('leaks')} sanity={rep.get('sanity')} "
                    f"net={rep.get('net')} eval_net={rep.get('eval_net_isolated')}"
                )
            self._log("preflight negative_controls (claude) PASS")
            return

        src_cfg_s = model_cfg.get("pi_cfg_dir")
        src_cfg = pathlib.Path(os.path.expandvars(os.path.expanduser(src_cfg_s))) if src_cfg_s else DEFAULT_PI_CFG_DIR

        rep = run_negative_controls(
            hidden_tests_path=hidden_p,
            eval_dir=self.root,
            other_arm_ws=other_arm_canary,
            materials_dir=mat_dir,
            pi_cfg_dir=src_cfg,
        )
        atomic_write_json(self.root / "negative_controls.json", rep)
        if not rep.get("passed"):
            raise SystemExit(
                f"拒絕啟動：隔離負控制失敗（見 {self.root / 'negative_controls.json'}）："
                f"leaks={rep.get('leaks')} sanity={rep.get('sanity')} eval_net={rep.get('eval_net_isolated')}"
            )
        self._log("preflight negative_controls PASS")

    def _run_worker_once(
        self,
        *,
        ws_dir: pathlib.Path,
        prompt: str,
        provider: str,
        log_path: pathlib.Path,
        is_doc: bool,
    ) -> dict:
        """在真實 bwrap 沙箱內執行一次 worker（真實 pi、真實 claude 或 selftest 假 agent）。"""
        assert_ks1_clean(prompt)
        model_cfg = self.plan["_model"]

        if self.agent_kind == "claude":
            assert self.net_proxy is not None, "claude mode requires allowlist proxy"
            assert self.claude_creds_file is not None, "claude mode requires credentials file"
            model_id = str(model_cfg["model"])
            cmd = build_claude_cli_argv(model_id, prompt)
            claude_bin_s = model_cfg.get("claude_bin")
            extra_env: dict[str, str] = {}
            if model_cfg.get("fake_mode"):
                extra_env["E1_FAKE_MODE"] = str(model_cfg["fake_mode"])
            argv = build_claude_worker_bwrap_argv(
                cmd,
                workspace_dir=ws_dir,
                proxy_sock_path=self.net_proxy.sock_path,
                credentials_file=self.claude_creds_file,
                claude_bin_override=claude_bin_s,
                extra_env=extra_env or None,
            )
            res = run_sandboxed(argv, timeout_s=self.attempt_timeout_s, log_path=log_path)
            usage = usage_from_claude_log(log_path)
            is_infra = False
            if usage is None:
                is_infra = True
            elif usage["calls"] == 0 and (
                usage["errors"] > 0
                or res["rc"] != 0
                or (usage.get("final_error") and _INFRA_ERR_RE.search(usage["final_error"]))
            ):
                is_infra = True
            return {
                "rc": res["rc"],
                "wall_s": res["wall_s"],
                "timed_out": res["timed_out"],
                "usage": usage,
                "cost_usd": usage.get("cost_usd") if isinstance(usage, dict) else None,
                "infra_error": is_infra,
            }

        fake_agent = model_cfg.get("fake_agent")
        extra_ro: list[tuple[pathlib.Path, str]] = []
        extra_env = {}

        if fake_agent:
            fa_path = pathlib.Path(os.path.expandvars(os.path.expanduser(str(fake_agent))))
            if not fa_path.is_absolute():
                fa_path = (REPO_ROOT / fa_path).resolve()
            extra_ro.append((fa_path, "/opt/bin/fake_agent.py"))
            if model_cfg.get("fake_mode"):
                extra_env["E1_FAKE_MODE"] = str(model_cfg["fake_mode"])
            cmd = ["python3", "/opt/bin/fake_agent.py", "--prompt", prompt]
            mount_pi = False
        else:
            model_id = str(model_cfg.get("model") or "qwen/qwen3.5-9b")
            cmd = [
                "pi",
                "-p",
                "--mode", "json",
                "--no-session",
                "--no-extensions",
                "--offline",
                "--provider", provider,
                "--model", model_id,
                prompt,
            ]
            mount_pi = True

        http_proxy = f"http://127.0.0.1:{self.source_server.port}" if (is_doc and self.source_server) else None
        argv = build_worker_bwrap_argv(
            cmd,
            workspace_dir=ws_dir,
            pi_cfg_dir=self.pi_cfg_dst,
            extra_ro_binds=extra_ro,
            http_proxy=http_proxy,
            no_proxy_hosts=self.no_proxy_hosts,
            extra_env=extra_env,
            mount_pi=mount_pi,
        )
        res = run_sandboxed(argv, timeout_s=self.attempt_timeout_s, log_path=log_path)
        usage = usage_from_pi_log(log_path)
        is_infra = False
        if not fake_agent:
            if usage is None:
                is_infra = True
            elif usage["calls"] == 0 and (usage["errors"] > 0 or (usage.get("final_error") and _INFRA_ERR_RE.search(usage["final_error"]))):
                is_infra = True
        return {
            "rc": res["rc"],
            "wall_s": res["wall_s"],
            "timed_out": res["timed_out"],
            "usage": usage,
            "infra_error": is_infra,
        }

    def _code_full_test_specs(self, chain: dict, fn_names: list[str]) -> dict[str, dict]:
        vis = chain["_hidden"]["visible_tests_by_function"]
        hid = chain["_hidden"]["hidden_tests_by_function"]
        out: dict[str, dict] = {}
        for fn in fn_names:
            v = vis[fn]
            h = hid[fn]
            out[fn] = {
                "cases": list(v["cases"]) + list(h["cases"]),
                "atol": v.get("atol", 0.0),
                "cmp_mode": v.get("cmp_mode", "exact"),
            }
        return out

    def _append_result_jsonl(self, record: dict) -> None:
        with _LOCK:
            with open(self.results_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def _load_doc_pages(self, site_dir: str, pages: list[str]) -> dict[str, str]:
        base = pathlib.Path(site_dir)
        return {pg: (base / pg).read_text(encoding="utf-8", errors="replace") for pg in pages}

    def _run_chain_arm(self, chain: dict, arm: str, provider: str) -> None:
        cid = chain["chain_id"]
        kind = chain["kind"]
        if kind == "doc" and arm == "B0x3":
            self._log(f"skip {cid}/{arm}: B0x3 is code-only")
            return
        if kind != "code" and arm == "Z":
            raise SystemExit("Z 臂只定義在程式類")

        target_fname = "solution.py" if kind == "code" else "report.md"
        arm_dir = self.root / "cells" / cid / arm
        arm_dir.mkdir(parents=True, exist_ok=True)

        # 初始狀態與初始全過基準
        state_text = chain["initial_solution"] if kind == "code" else chain["initial_report"]
        if kind == "code":
            prev_required = list(chain["initial_functions"])
        else:
            prev_required = list(chain["required_units"])
        prev_unit_passed: dict[str, bool] = {u: True for u in prev_required}

        for r_obj in chain["rounds"]:
            r_num = int(r_obj["round"])
            r_dir = arm_dir / f"round_{r_num}"
            done_p = r_dir / "done.json"
            state_p = r_dir / f"state_{target_fname}"
            rec_p = r_dir / "record.json"

            # 斷點續跑：若這一回合已完成，直接載入已提交狀態與評分結果
            if done_p.is_file() and state_p.is_file() and rec_p.is_file():
                state_text = state_p.read_text(encoding="utf-8")
                prev_rec = json.loads(rec_p.read_text(encoding="utf-8"))
                prev_required = list(r_obj["required_functions"] if kind == "code" else r_obj["required_units"])
                prev_unit_passed = {u: bool(v.get("passed")) for u, v in (prev_rec.get("eval", {}).get("units") or {}).items()}
                continue

            r_dir.mkdir(parents=True, exist_ok=True)
            baseline_text = state_text
            atomic_write_text(r_dir / f"baseline_{target_fname}", baseline_text)

            # 決定任務文字（所有臂逐字相同！）與文件路由
            if kind == "code":
                task_text = str(r_obj["task_text"])
                cur_required = list(r_obj["required_functions"])
                new_reqs = list(r_obj["new_requirements"])
                oracle_units = list(r_obj["oracle_affected_units"])
            else:
                host = HOST_FMT.format(chain_id=cid)
                assert self.source_server is not None
                self.source_server.set_route(host, r_obj["site_dir"], arm=arm, cycle=int(r_obj["cycle"]))
                index_url = f"http://{host}/{r_obj['index_file']}"
                task_text = str(r_obj["task_text_template"]).format(index_url=index_url)
                cur_required = list(r_obj["required_units"])
                new_reqs = list(r_obj["new_requirements"])
                oracle_units = list(r_obj["oracle_affected_units"])

            # 宿主端計算 S / Z / O 允許範圍（B0/B0x3/B2/P 不受限）
            allowed_scope: list[str] | None = None
            scope_detail: dict | None = None
            if arm in ("S", "S+B2", "Z"):
                if kind == "code":
                    allowed_scope = extract_code_scope_from_task(task_text)
                else:
                    prev_pages = self._load_doc_pages(r_obj["prev_site_dir"], r_obj["pages"])
                    cur_pages = self._load_doc_pages(r_obj["site_dir"], r_obj["pages"])
                    sc = compute_doc_scope_s(baseline_text, prev_pages, cur_pages)
                    allowed_scope = sc["allowed_units"]
                    scope_detail = sc["per_unit"]
            elif arm == "O":
                allowed_scope = list(oracle_units)

            # 決定嘗試上限與各臂迴圈策略
            if arm == "B0x3":
                max_att = self.max_attempts_b0x3
            elif arm in ("B2", "S+B2", "Z"):
                max_att = self.max_attempts_b2
            else:
                max_att = 1

            attempts_meta: list[dict] = []
            total_wall_s = 0.0
            total_in = 0
            total_out = 0
            total_calls = 0
            total_cache_create = 0
            total_cache_read = 0
            total_num_turns = 0
            total_cost_usd = 0.0
            any_usage = False
            any_cache = False
            any_cost = False
            infra_void = False

            committed_text = baseline_text
            last_candidate_text = baseline_text
            committed_units: list[str] = []
            rejected_units: list[str] = []
            rejected_non_unit_changes = False
            gate_passed: bool | None = None

            # B0x3 在連續嘗試之間沿用同一份工作區副本
            b0x3_carry_text = baseline_text

            for att in range(1, max_att + 1):
                att_dir = r_dir / f"attempt_{att}"
                att_dir.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix=f"e1_ws_{cid}_{arm}_r{r_num}_a{att}_") as ws_tmp:
                    ws_p = pathlib.Path(ws_tmp)
                    start_text = b0x3_carry_text if arm == "B0x3" else baseline_text
                    (ws_p / target_fname).write_text(start_text, encoding="utf-8")

                    wres = self._run_worker_once(
                        ws_dir=ws_p,
                        prompt=task_text,
                        provider=provider,
                        log_path=att_dir / "agent.log",
                        is_doc=(kind == "doc"),
                    )
                    total_wall_s += float(wres["wall_s"] or 0.0)
                    u = wres.get("usage")
                    if isinstance(u, dict):
                        any_usage = True
                        total_in += int(u.get("input") or 0)
                        total_out += int(u.get("output") or 0)
                        total_calls += int(u.get("calls") or 0)
                        if "cache_creation_input_tokens" in u or "cache_read_input_tokens" in u:
                            any_cache = True
                            total_cache_create += int(u.get("cache_creation_input_tokens") or 0)
                            total_cache_read += int(u.get("cache_read_input_tokens") or 0)
                        if "num_turns" in u and u.get("num_turns") is not None:
                            total_num_turns += int(u.get("num_turns") or 0)
                        if isinstance(u.get("cost_usd"), (int, float)):
                            any_cost = True
                            total_cost_usd += float(u["cost_usd"])
                    if wres.get("infra_error"):
                        infra_void = True

                    cand_file = ws_p / target_fname
                    cand_text = cand_file.read_text(encoding="utf-8", errors="replace") if cand_file.is_file() else ""
                    last_candidate_text = cand_text
                    atomic_write_text(att_dir / f"candidate_{target_fname}", cand_text)

                att_entry: dict[str, Any] = {
                    "attempt": att,
                    "rc": wres["rc"],
                    "wall_s": wres["wall_s"],
                    "timed_out": wres["timed_out"],
                    "usage": wres["usage"],
                    "infra_error": wres["infra_error"],
                }
                if "cost_usd" in wres:
                    att_entry["cost_usd"] = wres["cost_usd"]

                if arm == "B0":
                    committed_text = cand_text
                    attempts_meta.append(att_entry)
                    break

                if arm == "P":
                    # 只做語法檢查、不限範圍（ADDENDA 11-26，第七次稽核）：候選檔不能解析就保留基線，能解析就整檔收。
                    # 程式類＝ast.parse；與 S 的「候選檔語法不對就保留基線」同一個判準，用來分開「範圍限制」與「語法檢查」的效果。
                    if kind != "code":
                        raise SystemExit("P 臂只定義在程式類")
                    import ast as _ast
                    try:
                        _ast.parse(cand_text)
                        committed_text = cand_text
                        att_entry["syntax_error"] = False
                    except SyntaxError as _exc:
                        committed_text = baseline_text
                        att_entry["syntax_error"] = True
                        att_entry["error"] = f"SyntaxError: {_exc}"
                    attempts_meta.append(att_entry)
                    break

                if arm == "B0x3":
                    b0x3_carry_text = cand_text
                    committed_text = cand_text
                    attempts_meta.append(att_entry)
                    continue

                if arm == "Z":
                    # 零答案閘門（ADDENDA 11-26，第七次稽核＋vacant-hope）：
                    # ast.parse ＋ 無網路評分沙箱匯入（不跑測試、不讀測資）＋ 範圍檢查（同 S）。
                    # 三項全過就整檔提交；任一不過就回滾至基線，依 B2 同預算／同無回饋策略重試。
                    assert allowed_scope is not None
                    z_res = check_code_z_gate(
                        baseline_text,
                        cand_text,
                        allowed_scope,
                        load_timeout_s=min(8.0, self.eval_timeout_s),
                        total_timeout_s=self.eval_timeout_s,
                        mem_limit_mb=self.eval_mem_mb,
                    )
                    zc = z_res["z_check"]
                    z_ok = bool(z_res["passed"])
                    committed_units = list(z_res["committed_units"])
                    rejected_units = list(zc["rejected_units"])
                    rejected_non_unit_changes = bool(zc["rejected_non_unit_changes"])
                    att_entry["z_check"] = zc
                    att_entry["committed_units"] = committed_units
                    att_entry["rejected_units"] = rejected_units
                    att_entry["rejected_non_unit_changes"] = rejected_non_unit_changes
                    attempts_meta.append(att_entry)
                    if z_ok:
                        gate_passed = True
                        committed_text = cand_text
                        break
                    else:
                        gate_passed = False
                        committed_text = baseline_text
                        continue

                # 若是 S / S+B2 / O，先由宿主端執行範圍提交
                if arm in ("S", "S+B2", "O"):
                    assert allowed_scope is not None
                    if kind == "code":
                        sc_res = commit_code_scoped(baseline_text, cand_text, allowed_scope)
                        proposed_text = sc_res["committed_src"]
                    else:
                        sc_res = commit_doc_scoped(baseline_text, cand_text, allowed_scope)
                        proposed_text = sc_res["committed_text"]
                    committed_units = list(sc_res["committed_units"])
                    rejected_units = list(sc_res["rejected_units"])
                    rejected_non_unit_changes = bool(sc_res["rejected_non_unit_changes"])
                    att_entry["committed_units"] = committed_units
                    att_entry["rejected_units"] = rejected_units
                    att_entry["rejected_non_unit_changes"] = rejected_non_unit_changes
                else:
                    proposed_text = cand_text

                if arm in ("S", "O"):
                    committed_text = proposed_text
                    attempts_meta.append(att_entry)
                    break

                # B2 / S+B2：跑宿主可用檢查（code: visible tests; doc: structural check）
                if kind == "code":
                    chk = evaluate_code_source(
                        proposed_text,
                        r_obj["visible_tests"],
                        per_fn_timeout_s=min(8.0, self.eval_timeout_s),
                        total_timeout_s=self.eval_timeout_s,
                        mem_limit_mb=self.eval_mem_mb,
                    )
                    chk_ok = bool(chk["all_pass"])
                    att_entry["gate_check"] = {
                        "all_pass": chk_ok,
                        "load_error": chk.get("load_error"),
                        "failed_units": sorted(fn for fn, info in (chk.get("functions") or {}).items() if not info.get("passed")),
                    }
                else:
                    chk = check_doc_structural(proposed_text, cur_required)
                    chk_ok = bool(chk["all_pass"])
                    att_entry["gate_check"] = chk

                attempts_meta.append(att_entry)
                if chk_ok:
                    gate_passed = True
                    committed_text = proposed_text
                    break
                else:
                    # 未過檢查：回滾至本回合基線並重試
                    gate_passed = False
                    committed_text = baseline_text

            # 原子提交本回合最終狀態
            committed_sha = atomic_commit_file(state_p, committed_text)
            atomic_write_text(r_dir / f"candidate_{target_fname}", last_candidate_text)

            # ── 宿主端獨立評分（絕不回送給 agent）──────────────────────────────
            if kind == "code":
                full_specs = self._code_full_test_specs(chain, cur_required)
                ev_raw = evaluate_code_source(
                    committed_text,
                    full_specs,
                    per_fn_timeout_s=min(8.0, self.eval_timeout_s),
                    total_timeout_s=self.eval_timeout_s,
                    mem_limit_mb=self.eval_mem_mb,
                )
                units_eval = ev_raw["functions"]
                eval_summary = {
                    "all_pass": bool(ev_raw["all_pass"]),
                    "load_error": ev_raw.get("load_error"),
                    "wall_s": ev_raw.get("wall_s"),
                    "n_passed": sum(1 for u in cur_required if (units_eval.get(u) or {}).get("passed")),
                    "n_total": len(cur_required),
                    "units": units_eval,
                }
            else:
                truth_k = chain["_hidden"]["truth"][int(r_obj["cycle"])]
                claims = chain["_hidden"]["claims"]
                ev_raw = evaluate_doc_report(committed_text, claims, truth_k)
                units_eval = ev_raw["units"]
                eval_summary = {
                    "all_pass": bool(ev_raw["all_pass"]),
                    "n_passed": ev_raw["n_passed"],
                    "n_total": ev_raw["n_total"],
                    "units": units_eval,
                }

            cur_unit_passed = {u: bool((units_eval.get(u) or {}).get("passed")) for u in cur_required}

            # 回歸（regression）：上一回合通過且本回合仍要求、現在卻不通過的單元
            still_req = [u for u in prev_required if u in set(cur_required)]
            prev_pass_still_req = [u for u in still_req if prev_unit_passed.get(u, False)]
            regressed_units = [u for u in prev_pass_still_req if not cur_unit_passed.get(u, False)]

            # 新需求完成率
            new_req_passed = [u for u in new_reqs if cur_unit_passed.get(u, False)]
            new_req_completion = (len(new_req_passed) / len(new_reqs)) if new_reqs else None

            # S / S+B2 / O / Z 事後評分：被拒但其實正確的單元（false rejects）與範圍內接受卻錯誤的單元
            rejected_candidate_correct: list[str] = []
            rejected_but_correct: list[str] = []
            accepted_in_scope_but_wrong: list[str] = []

            if arm in ("S", "S+B2", "O", "Z"):
                # 若 S+B2 / Z 最後全部回滾至基線，實際上沒有提交範圍內變更
                eff_committed = [] if (arm in ("S+B2", "Z") and gate_passed is False) else committed_units
                accepted_in_scope_but_wrong = [
                    u for u in eff_committed if u in cur_unit_passed and not cur_unit_passed[u]
                ]
                rej_req = [u for u in rejected_units if u in set(cur_required)]
                if rej_req:
                    if kind == "code":
                        cand_specs = self._code_full_test_specs(chain, rej_req)
                        cand_ev = evaluate_code_source(
                            last_candidate_text,
                            cand_specs,
                            per_fn_timeout_s=min(8.0, self.eval_timeout_s),
                            total_timeout_s=self.eval_timeout_s,
                            mem_limit_mb=self.eval_mem_mb,
                        )
                        cand_units_ev = cand_ev.get("functions") or {}
                        for u in rej_req:
                            if (cand_units_ev.get(u) or {}).get("passed"):
                                rejected_candidate_correct.append(u)
                                if not cur_unit_passed.get(u, False):
                                    rejected_but_correct.append(u)
                    else:
                        truth_k = chain["_hidden"]["truth"][int(r_obj["cycle"])]
                        claims = chain["_hidden"]["claims"]
                        cand_ev = evaluate_doc_report(last_candidate_text, claims, truth_k)
                        cand_units_ev = cand_ev.get("units") or {}
                        for u in rej_req:
                            if (cand_units_ev.get(u) or {}).get("passed"):
                                rejected_candidate_correct.append(u)
                                if not cur_unit_passed.get(u, False):
                                    rejected_but_correct.append(u)

            record = {
                "schema": RESULT_SCHEMA,
                "ts_utc": utc_now_iso(),
                "plan_id": self.plan["id"],
                "chain_id": cid,
                "chain_kind": kind,
                "arm": arm,
                "provider": provider,
                "round": r_num,
                "round_kind": r_obj["kind"],
                "attempts_count": len(attempts_meta),
                "attempts": attempts_meta,
                "allowed_scope": allowed_scope,
                "oracle_affected_units": oracle_units,
                "committed_units": committed_units,
                "rejected_units": rejected_units,
                "rejected_non_unit_changes": rejected_non_unit_changes,
                "gate_passed": gate_passed,
                "committed_sha256": committed_sha,
                "wall_s": round(total_wall_s, 3),
                "calls": total_calls if any_usage else None,
                "tokens_in": total_in if any_usage else None,
                "tokens_out": total_out if any_usage else None,
                "cost_usd": round(total_cost_usd, 6) if any_cost else None,
                "infra_void": infra_void,
                "eval": eval_summary,
                "still_required_prev_passing_count": len(prev_pass_still_req),
                "regression_count": len(regressed_units),
                "regressed_units": regressed_units,
                "new_req_total": len(new_reqs),
                "new_req_passed": len(new_req_passed),
                "new_req_completion": new_req_completion,
                "rejected_but_correct": rejected_but_correct,
                "rejected_candidate_correct": rejected_candidate_correct,
                "accepted_in_scope_but_wrong": accepted_in_scope_but_wrong,
            }
            if any_cache:
                record["cache_creation_input_tokens"] = total_cache_create
                record["cache_read_input_tokens"] = total_cache_read
                record["num_turns"] = total_num_turns
            if scope_detail is not None:
                record["doc_scope_detail"] = scope_detail

            atomic_write_json(rec_p, record)
            atomic_write_json(done_p, {"done": True, "ts_utc": utc_now_iso(), "committed_sha256": committed_sha})
            self._append_result_jsonl(record)
            self._log(
                f"{cid}/{arm}/r{r_num} all_pass={eval_summary['all_pass']} "
                f"reg={len(regressed_units)}/{len(prev_pass_still_req)} "
                f"new={len(new_req_passed)}/{len(new_reqs)} rej={len(rejected_units)} "
                f"att={len(attempts_meta)} wall={record['wall_s']}s"
            )

            # 更新下一回合基線
            state_text = committed_text
            prev_required = cur_required
            prev_unit_passed = cur_unit_passed

    def _run_one_chain(self, chain_idx: int, chain: dict) -> None:
        providers = self.plan["_model"].get("providers") or ["fake"]
        provider = providers[chain_idx % len(providers)]
        for arm in self.arms:
            self._run_chain_arm(chain, arm, provider)

    def run(self) -> dict:
        self._init_root_and_check_resume()
        try:
            self._run_preflight_negative_controls()

            if self.has_doc:
                port = int(self.plan.get("source_server_port") or 0)
                self.source_server = _SourceServer(self.root, port=port)
                self.source_server.start()
                self._log(f"source_server listening on 127.0.0.1:{self.source_server.port}")

            if self.agent_kind == "claude":
                allowed_connect = _parse_allowed_connect_hosts(self.plan["_model"].get("allowed_connect_hosts"))
                self.net_proxy = AllowlistUnixProxy(
                    allowed_connect=allowed_connect,
                    source_server_port=(self.source_server.port if self.source_server else None),
                    log_path=self.root / "proxy.jsonl",
                )
                self.net_proxy.start()
                self._log(
                    f"allowlist_proxy listening on {self.net_proxy.sock_path} "
                    f"connect={sorted(self.net_proxy.allowed_connect)} "
                    f"source_port={self.net_proxy.source_server_port}"
                )

            if self.jobs == 1 or len(self.chains) == 1:
                for i, ch in enumerate(self.chains):
                    self._run_one_chain(i, ch)
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.jobs) as ex:
                    futs = [ex.submit(self._run_one_chain, i, ch) for i, ch in enumerate(self.chains)]
                    for fut in concurrent.futures.as_completed(futs):
                        fut.result()
        finally:
            if self.net_proxy is not None:
                self.net_proxy.stop()
                self.net_proxy = None
            if self.source_server is not None:
                self.source_server.stop()
                self.source_server = None
            if self._claude_creds_tmp is not None:
                self._claude_creds_tmp.cleanup()
                self._claude_creds_tmp = None
                self.claude_creds_file = None
            kill_all_live()

        return {
            "root": str(self.root),
            "results_jsonl": str(self.results_path),
            "n_chains": len(self.chains),
            "arms": self.arms,
        }


def main() -> int:
    ap = argparse.ArgumentParser(description="E1′ 實驗執行器（bwrap 隔離＋負控制＋續跑安全）")
    ap.add_argument("--plan", type=pathlib.Path, required=True, help="計畫檔 PLAN.json")
    ap.add_argument("--root", type=pathlib.Path, required=True, help="實驗輸出目錄 ROOT")
    ap.add_argument("--calibrate", action="store_true", help="校準模式：只跑 B0 臂")
    args = ap.parse_args()

    runner = E1Runner(args.plan, args.root, calibrate=args.calibrate)
    out = runner.run()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
