#!/usr/bin/env python3
"""redo — 原生 agent 的「工作區自己的測試沒過，就開一個全新的嘗試」量測 harness。

這支在架構裡承重什麼
====================
過去所有量到交付變好的設定都同時有「真的知道對錯的訊號」＋「重來的權力」
（`docs/ZERO_CONFIG_EVAL_REPORT_2026-09-26.md` §八；realrun v4／v6／v7 在沒有工具的
mini_agent 上重現）。**在本來就會自己迴圈的原生 agent（pi 等）上，這個配方從來沒有實跑過**
——e001／e002／e016 量的都是「同一個工作階段裡退回」。本檔就是那一格的量具，而且只做這一件事：

    A   = 原生 agent 跑一次（一個長時限）
    R3  = 同一個 agent，每次嘗試較短；工作區**原本的**測試沒過 ⇒ 丟掉工作區、全新行程重來，
          最多 3 次，總牆鐘不超過 A 的時限（等預算）

迴圈在**父行程**（`decisions/DECISION_20260929_LOOP_WITHOUT_POSSESSION.md`，分支
`design/loop-without-possession`）：只要求 agent 是一個可以 spawn 的 CLI，不需要掛鉤、
不需要通道中介，所以換平台只換 `agent.argv`。

設計上刻意擋掉的幾種量錯（每一條在過去的 run 裡都真的發生過）
----------------------------------------------------------------
1. **政策只讀驗收訊號，永遠不讀評分器。** 每一次嘗試都會被評分（為了事後算訊號的混淆矩陣），
   但 `_policy_*` 只拿得到 `accept`。把 test-restart（用評分器決定重抽）講成成效，是
   `NEXT_AGENT_TASKS.md` 開頭那則更正的原因。
2. **驗收跑的是題目一開始的測試檔原件**：agent 改過測試檔也沒用（還原後才跑），而且記
   `tests_tampered`。
3. **一對（task, rep）的兩臂綁在同一台機器、先後順序交替**：e002 的 C 獨過 7 題裡 5 題是
   A 逾時，分不開是不是機器／時段的差。
4. **每一次嘗試在自己的暫存目錄**：重抽的那一次看不到上一次的工作區（`resample` 的定義）。
5. **基礎設施失敗不算嘗試**（鐵律 3）：工作區沒動＋模型呼叫 0 次或連線錯誤 ⇒ `void`，
   等端點回來後重試，最多 4 次；還是不行，那一格 `infra_void`，不進分母、另外列出。
6. **計畫檔（預註冊）在第一通模型呼叫之前必須已經 commit**；同一個 root 換了計畫內容就拒跑。

誠實邊界（改碼請保留）
----------------------
- agent 以你的帳號執行：暫存工作區不是沙箱，它讀得到磁碟上的 hidden／別次嘗試的歸檔。
  本檔只保證「沒有主動把那些東西放在它面前」。
- 驗收＝「擋得住工作區測試會抓到的錯」，**不等於需求被滿足**（suitegauge 的單邊保證）。
  polyglot_py 的可見測試就是評分器，所以那裡訊號是真的；別的題庫要先看報告裡的
  `signal`（accepted 卻被評分器判錯的比例）再決定能不能引用。
- 等預算是牆鐘的等預算，不是 token 的。token／呼叫數照實報，缺值是 `null` 不是 0。
- 本檔量的是機制（harness 裡的迴圈）。產品指令做到同一件事之後，要用 arm 的 `agent`
  覆寫再量一次，兩個數字不可混講。

用法
----
    python3 ops/redo/redo.py selftest                       # 假 agent，0 次模型呼叫
    python3 ops/redo/redo.py preflight --plan ops/redo/plans/<x>.json
    python3 ops/redo/redo.py run       --plan ops/redo/plans/<x>.json --root <輸出目錄>
    python3 ops/redo/redo.py report    --root <輸出目錄>
    python3 ops/redo/redo.py status    --root <輸出目錄>
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import pathlib
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from typing import Any

SCHEMA = "vacant.redo.plan/1"
DEFAULT_PROMPT = ("Read goal.md and contract.md in this directory and do what they say. "
                  "Use your tools to write the file.")          # 與 stage_task_bank.py 逐字相同
SKIP_DIRS = frozenset({".git", "node_modules", "__pycache__", ".venv", ".pytest_cache", ".mypy_cache"})
ARCHIVE_FILE_CAP = 2 * 1024 * 1024       # 歸檔時單檔上限（解答檔都很小；大檔只記雜湊）
LOG_CAP = 16 * 1024 * 1024               # 一次嘗試的 agent 輸出上限
VOID_RETRIES = 4                         # 鐵律 3：retry×4
VOID_BACKOFF_S = (30, 60, 120, 240)
INFRA_RE_DEFAULT = (r"ECONNREFUSED|ECONNRESET|ENOTFOUND|EAI_AGAIN|fetch failed|socket hang up|"
                    r"Connection error|connection refused|Premature close|\bterminated\b|"
                    r"model[^\n]{0,40}(?:not (?:found|loaded)|crashed|unloaded)|"
                    r"\b50[234]\b[^\n]{0,40}(?:Bad Gateway|Service Unavailable|Gateway Timeout)")
HINT_CAP = 400                           # 與 v5 的 fresh_hint 同一個上限
HINT_HEAD = ("An earlier attempt at this task ended with the tests in this directory not passing. "
             "First failing test output from that attempt:\n")
# KS-1：提示文字不准有責任／懲罰類措辭。這裡是可執行防呆的最小版（harness 不依賴套件本體）。
_KS1_BANNED = re.compile(r"你有責任|會被懲罰|負責任|responsib|punish|penal|blame|fault of", re.I)


# ── 小工具 ────────────────────────────────────────────────────────────────

def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_json(p: pathlib.Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + f".tmp{os.getpid()}.{threading.get_ident()}")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def read_json(p: pathlib.Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def expand(p: str) -> pathlib.Path:
    return pathlib.Path(os.path.expandvars(os.path.expanduser(p)))


def snapshot(d: pathlib.Path) -> dict[str, str]:
    """`{相對路徑: sha256}`；跳過 SKIP_DIRS。用來判斷「工作區有沒有被動過」與歸檔清單。"""
    out: dict[str, str] = {}
    for root, dirs, files in os.walk(d):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
        for f in sorted(files):
            fp = pathlib.Path(root) / f
            rel = fp.relative_to(d).as_posix()
            try:
                out[rel] = "link:" + os.readlink(fp) if fp.is_symlink() else sha256_bytes(fp.read_bytes())
            except OSError:
                out[rel] = "unreadable"
    return out


def mcnemar_exact(b: int, c: int) -> float:
    """精確雙尾 McNemar（不一致對的二項檢定）；與 `vacant_network.research.mcnemar_exact` 同式。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / 2.0 ** n)


# ── 計畫 ──────────────────────────────────────────────────────────────────

class PlanError(SystemExit):
    pass


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_plan(path: pathlib.Path) -> dict:
    plan = read_json(path)
    if plan.get("schema") != SCHEMA:
        raise PlanError(f"計畫檔 schema 應為 {SCHEMA}：{path}")
    for k in ("id", "tasks", "reps", "arms", "pair", "agent", "providers", "attempt_timeout_s"):
        if k not in plan:
            raise PlanError(f"計畫檔缺欄位 {k}：{path}")
    if len(plan["pair"]) != 2 or any(a not in plan["arms"] for a in plan["pair"]):
        raise PlanError("pair 必須是 arms 裡的兩個名字 [對照, 處理]")
    for name, arm in plan["arms"].items():
        if arm.get("policy") not in ("single", "restart", "controller"):
            raise PlanError(f"arm {name}: policy 只能是 single／restart／controller")
        if arm.get("hint", "none") not in ("none", "first_failure", "failing_tests"):
            raise PlanError(f"arm {name}: hint 只能是 none／first_failure／failing_tests")
    if len(set(plan["tasks"])) != len(plan["tasks"]):
        raise PlanError("tasks 有重複")
    acfg = plan.get("acceptance", {})
    if acfg.get("kind", "workspace_tests") not in ("workspace_tests", "command"):
        raise PlanError(f"acceptance.kind 只能是 workspace_tests／command：{acfg.get('kind')!r}")
    if acfg.get("kind") == "command":
        cmd = acfg.get("cmd")
        if not (isinstance(cmd, list) and cmd and all(isinstance(x, str) for x in cmd)):
            raise PlanError("acceptance.kind=command 時 cmd 必須是非空的字串清單")
    plan["_sha256"] = sha256_bytes(canonical({k: v for k, v in plan.items() if not k.startswith("_")}))
    plan["_path"] = str(path)
    return plan


def resolve_bank(plan: dict, override: str | None) -> pathlib.Path:
    """第一個存在、而且每一題都有 `workspace/` 的候選目錄。找不到就說清楚缺什麼。"""
    cands = [override, os.environ.get("REDO_BANK"), plan.get("bank"), *plan.get("bank_candidates", [])]
    tried: list[str] = []
    for c in cands:
        if not c:
            continue
        d = expand(c)
        missing = [t for t in plan["tasks"] if not (d / t / "workspace").is_dir()]
        if d.is_dir() and not missing:
            return d
        tried.append(f"{d}（{'不存在' if not d.is_dir() else '缺 ' + str(len(missing)) + ' 題，如 ' + missing[0]}）")
    raise PlanError("找不到題庫（每題要有 <題庫>/<題>/workspace/）。試過：\n  " + "\n  ".join(tried or ["（沒有候選）"])
                    + "\n用 --bank 或環境變數 REDO_BANK 指定。")


def planned_pairs(plan: dict) -> list[tuple[str, int]]:
    """rep 為主序（先把第 1 次重複整輪跑完），rep 內用計畫的種子洗牌。"""
    out: list[tuple[str, int]] = []
    for rep in range(1, int(plan["reps"]) + 1):
        tasks = list(plan["tasks"])
        random.Random(f"{plan.get('seed', 0)}:{rep}").shuffle(tasks)
        out += [(t, rep) for t in tasks]
    return out


def provider_slots(plan: dict) -> list[dict]:
    slots: list[dict] = []
    for p in plan["providers"]:
        slots += [p] * int(p.get("jobs", 1))
    return slots


def provider_for(plan: dict, index: int) -> dict:
    """一對的兩臂用同一台：由這一對在計畫裡的序號決定，續跑時不會變。"""
    slots = provider_slots(plan)
    return slots[index % len(slots)]


def arm_order(plan: dict, task: str, rep: int) -> list[str]:
    arms = list(plan["arms"])
    h = int(sha256_bytes(f"{plan.get('seed', 0)}:{task}:{rep}".encode())[:8], 16)
    return arms[h % len(arms):] + arms[:h % len(arms)]


# ── 題目 ──────────────────────────────────────────────────────────────────

def task_prompt(tdir: pathlib.Path) -> str:
    f = tdir / "instruction.txt"
    return f.read_text(encoding="utf-8").strip() if f.is_file() else DEFAULT_PROMPT


def test_files(origin: pathlib.Path, patterns: list[str]) -> list[str]:
    out = []
    for rel in sorted(snapshot(origin)):
        name = rel.rsplit("/", 1)[-1]
        if any(pathlib.PurePath(name).match(p) for p in patterns):
            out.append(rel)
    return out


# ── 跑 agent ──────────────────────────────────────────────────────────────

_LIVE: set[subprocess.Popen] = set()
_LIVE_LOCK = threading.Lock()


def _track(proc: subprocess.Popen, on: bool) -> None:
    with _LIVE_LOCK:
        (_LIVE.add if on else _LIVE.discard)(proc)


def kill_all_live() -> None:
    """runner 要結束了：把還活著的 agent／驗收／評分行程群組全部收掉（它們各自在自己的 session）。"""
    with _LIVE_LOCK:
        procs = list(_LIVE)
    for proc in procs:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def _kill_group(proc: subprocess.Popen) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            continue


def run_agent(argv: list[str], env: dict[str, str], cwd: pathlib.Path, timeout_s: float,
              log_path: pathlib.Path, drop_re: re.Pattern | None) -> dict:
    """spawn agent（自己的行程群組），輸出逐行寫進 log（丟掉 drop_re 命中的行、有大小上限）。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    timed_out = False
    try:
        proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                start_new_session=True)
    except OSError as e:
        log_path.write_text(f"[redo] spawn failed: {e}\n", encoding="utf-8")
        return {"rc": None, "wall_s": 0.0, "timed_out": False, "spawn_error": str(e)}
    _track(proc, True)

    def pump() -> None:
        written = 0
        with open(log_path, "wb") as lf:
            assert proc.stdout is not None
            for line in proc.stdout:
                if drop_re is not None and drop_re.search(line.decode("utf-8", "replace")):
                    continue
                if written < LOG_CAP:
                    lf.write(line)
                    written += len(line)

    th = threading.Thread(target=pump, daemon=True)
    th.start()
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_group(proc)
    finally:
        # agent 正常結束後留下的子孫行程也收掉（它們還握著工作區）
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        _track(proc, False)
    th.join(timeout=15)
    return {"rc": proc.returncode, "wall_s": round(time.time() - t0, 1), "timed_out": timed_out}


def usage_from_log(log_path: pathlib.Path) -> dict | None:
    """pi `--mode json` 的事件流：一個 assistant `message_end`＝一次模型呼叫。讀不出來＝None（不填 0）。

    與 `vacant_network/reqloop/repair.py` 的讀法同一個口徑，多分一件事（真的 pi 0.87.1 對著死掉的
    端點實測）：端點連不上時 pi 的結束碼是 0，而且照樣送出 `message_end`，只是
    `stopReason="error"`、usage 全 0——那不是一次模型呼叫。所以 `calls` 只算沒出錯的回應，
    出錯的另計 `errors`，最後一則 assistant 訊息的錯誤原文放在 `final_error`
    （判斷「模型跑到一半死掉」用）。
    """
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    calls = errors = tin = tout = 0
    saw_json = False
    final_error: str | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
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
    return {"calls": calls, "errors": errors, "input": tin or None, "output": tout or None,
            "final_error": final_error}


def usage_from_devin_log(log_path: pathlib.Path) -> dict | None:
    """Devin CLI（DECISION 修正 5）：用量來自 wrapper 用 `--export` 寫的 ATIF 匯出 `<attempt>/logs/devin_export.json`
    （`log_path` 是 agent.log，匯出在同一個嘗試目錄的 logs/ 下）。

    匯出**實際含有**的欄位只有：每個 agent 步驟的 `metrics{prompt_tokens, completion_tokens, cached_tokens}`、
    `final_metrics{total_prompt_tokens, total_completion_tokens, total_cached_tokens, total_steps}`、步驟時間戳、
    `agent.model_name`／`version`。**沒有費用欄位**（免費模型）⇒ `cost_usd` 固定 None，不編數字。
    `calls`＝帶 metrics 的 agent 步驟數；`input`＝prompt_tokens 加總（cached 是其中的子集，實測三步加總＝總和）；
    `cache_read`＝cached_tokens；`uncached_input`＝input−cache_read；`num_turns`＝total_steps。
    匯出沒有「這一回合以錯誤結束」的欄位 ⇒ `final_error` 取 agent.log 裡的 `Error: Agent error: …` 行（有就記一次 error，限流等會被 infra_re 當成 infra 失敗）；被逾時殺掉時匯出可能不存在 ⇒ 回 None
    （redo 把「工作區沒動＋usage None」當成需看 log 尾端的 infra 判斷，見 one_attempt）。
    另附 `first_ts`／`last_ts`（匯出裡步驟時間戳，ISO 字串）供牆鐘對照。
    """
    exp = log_path.parent / "logs" / "devin_export.json"
    try:
        d = json.loads(exp.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    steps = [x for x in d.get("steps", []) if isinstance(x, dict)]
    ag = [x for x in steps if x.get("source") == "agent" and isinstance(x.get("metrics"), dict)]
    fm = d.get("final_metrics") if isinstance(d.get("final_metrics"), dict) else None
    inp = sum(int(x["metrics"].get("prompt_tokens") or 0) for x in ag)
    outp = sum(int(x["metrics"].get("completion_tokens") or 0) for x in ag)
    cr = sum(int(x["metrics"].get("cached_tokens") or 0) for x in ag)
    if fm:
        inp = int(fm.get("total_prompt_tokens") or inp)
        outp = int(fm.get("total_completion_tokens") or outp)
        cr = int(fm.get("total_cached_tokens") or cr)
    ts = [x.get("timestamp") for x in steps if x.get("timestamp")]
    # 這一跑以錯誤結束時，CLI 把 "Error: Agent error: ..." 印在 agent.log（匯出裡沒有這個欄位）
    ferr = None
    try:
        m = re.search(r"^Error: Agent error: (.{0,300})", log_path.read_text(encoding="utf-8", errors="replace"), re.M)
        ferr = m.group(1) if m else None
    except OSError:
        pass
    return {"calls": len(ag), "errors": 1 if ferr else 0, "final_error": ferr, "cost_usd": None,
            "num_turns": (fm or {}).get("total_steps"), "input": inp or None, "output": outp or None,
            "cache_read": cr, "cache_create": None, "uncached_input": inp - cr if inp else None,
            "terminal_reason": None, "first_ts": ts[0] if ts else None, "last_ts": ts[-1] if ts else None}


def usage_from_claude_log(log_path: pathlib.Path) -> dict | None:
    """Claude Code `--output-format stream-json --verbose` 的事件流（DECISION 修正 4，worker 改 Haiku）。

    `calls`＝不同 message.id 的 assistant 回應（不含 `<synthetic>`，那是 CLI 自己合成的錯誤訊息）；
    token／費用優先取最後的 `result` 事件（`modelUsage` 逐模型加總，含快取讀寫）；沒有 result（被逾時殺掉）時用
    assistant 訊息自己的 usage 加總、`cost_usd`＝None（不編數字）。`input`＝送進模型的全部 token
    （未快取＋快取建立＋快取讀取），分項另列。`result.is_error` 算一次 error，原文放 `final_error`
    （判斷基礎設施失敗用）。讀不出任何 JSON 事件＝None。
    """
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    saw = False
    per_msg: dict[str, dict] = {}
    result: dict | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if not isinstance(o, dict) or "type" not in o:
            continue
        saw = True
        if o["type"] == "assistant" and isinstance(o.get("message"), dict):
            m = o["message"]
            if m.get("model") == "<synthetic>" or not m.get("id"):
                continue
            per_msg[m["id"]] = m.get("usage") or {}
        elif o["type"] == "result":
            result = o
    if not saw:
        return None
    out: dict = {"calls": len(per_msg), "errors": 0, "final_error": None, "cost_usd": None, "num_turns": None,
                 "input": None, "output": None, "cache_read": None, "cache_create": None, "uncached_input": None,
                 "terminal_reason": None}
    mu = (result or {}).get("modelUsage") if isinstance((result or {}).get("modelUsage"), dict) else None
    if mu:
        def tot(key: str) -> int:
            return sum(int(v.get(key) or 0) for v in mu.values() if isinstance(v, dict))
        unc, cc, cr, outp = tot("inputTokens"), tot("cacheCreationInputTokens"), tot("cacheReadInputTokens"), tot("outputTokens")
        out["cost_usd"] = round(sum(float(v.get("costUSD") or 0) for v in mu.values() if isinstance(v, dict)), 6)
    else:
        unc = sum(int(u.get("input_tokens") or 0) for u in per_msg.values())
        cc = sum(int(u.get("cache_creation_input_tokens") or 0) for u in per_msg.values())
        cr = sum(int(u.get("cache_read_input_tokens") or 0) for u in per_msg.values())
        outp = sum(int(u.get("output_tokens") or 0) for u in per_msg.values())
        if result and result.get("total_cost_usd") is not None:
            out["cost_usd"] = round(float(result["total_cost_usd"]), 6)
    out.update(uncached_input=unc, cache_create=cc, cache_read=cr, output=outp or None, input=(unc + cc + cr) or None)
    if result:
        out["num_turns"] = result.get("num_turns")
        out["terminal_reason"] = result.get("terminal_reason")
        if result.get("is_error"):
            out["errors"] = 1
            out["final_error"] = (f"{result.get('terminal_reason')}: " + str(result.get("result") or ""))[:300]
    return out


# ── 驗收（政策唯一讀得到的訊號）與評分（政策讀不到）─────────────────────────

_UNITTEST_RUNNER = r"""
import json, sys, traceback, unittest
sys.path.insert(0, ".")
class _TrackResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.test_results = {}
    def _tid(self, test):
        return test.id() if hasattr(test, "id") else str(test)
    def addSuccess(self, test):
        super().addSuccess(test); self.test_results[self._tid(test)] = True
    def addFailure(self, test, err):
        super().addFailure(test, err); self.test_results[self._tid(test)] = False
    def addError(self, test, err):
        super().addError(test, err); self.test_results[self._tid(test)] = False
    def addSkip(self, test, reason):
        super().addSkip(test, reason); self.test_results[self._tid(test)] = False
    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err); self.test_results[self._tid(test)] = True
    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test); self.test_results[self._tid(test)] = False
out = {"run": 0, "failures": 0, "errors": 0, "skipped": 0, "unexpected_successes": 0,
       "load_error": None, "first_problem": None, "test_results": {}}
for mod in sys.argv[1:]:
    try:
        suite = unittest.TestLoader().loadTestsFromName(mod)
    except BaseException:
        out["load_error"] = traceback.format_exc(limit=3)[-800:]
        break
    res = _TrackResult()
    suite.run(res)
    out["run"] += res.testsRun; out["failures"] += len(res.failures); out["errors"] += len(res.errors)
    out["skipped"] += len(res.skipped); out["unexpected_successes"] += len(res.unexpectedSuccesses)
    out["test_results"].update(res.test_results)
    probs = res.failures + res.errors
    if probs and out["first_problem"] is None:
        out["first_problem"] = (str(probs[0][0]) + "\n" + probs[0][1])[-800:]
sys.stdout.flush()
print("\n@@REDO_RESULT@@" + json.dumps(out))
"""


def _clean_env(home: pathlib.Path) -> dict[str, str]:
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home), "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "PYTHONNOUSERSITE": "1"}


def _run_quiet(argv: list[str], cwd: pathlib.Path, env: dict[str, str], timeout_s: float) -> tuple[int | None, str]:
    try:
        proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as e:
        return None, f"spawn failed: {e}"
    _track(proc, True)
    try:
        out, _ = proc.communicate(timeout=timeout_s)
        return proc.returncode, out.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        return None, "timeout"
    finally:
        _track(proc, False)


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_JEST_TESTS_RE = re.compile(r"^Tests:\s+(.*)$", re.M)


def _parse_command_counts(out: str) -> tuple[int | None, int | None]:
    """若輸出有 Jest 的 `Tests: ... N total` 摘要列就順手讀出 (passed, run)，否則 (None, None)。"""
    clean = _ANSI_RE.sub("", out)
    m = None
    for m in _JEST_TESTS_RE.finditer(clean):
        pass
    if not m:
        return None, None
    line = m.group(1)
    mt = re.search(r"(\d+)\s+total\b", line)
    if not mt:
        return None, None
    total = int(mt.group(1))
    mp = re.search(r"(\d+)\s+passed\b", line)
    if mp:
        return int(mp.group(1)), total
    if re.search(r"\d+\s+(?:failed|skipped|todo)\b", line):
        return 0, total
    return None, total


def _acceptance_command(origin: pathlib.Path, final_ws: pathlib.Path, cfg: dict) -> dict:
    """`kind="command"` 驗收：在工作區副本裡還原受保護檔案（以及 origin 頂層 SKIP_DIRS 的符號連結）後執行 cmd。"""
    protect = cfg.get("protect", cfg.get("patterns", []))
    protected = test_files(origin, protect) if protect else []
    base = {"accept": False, "kind": "command", "tests": protected, "passed": None, "run": None,
            "tests_tampered": [], "status": None, "first_problem": None,
            "test_results": {}, "failing_tests": []}
    if protect and not protected:
        return {**base, "status": "no_tests_in_origin"}
    cmd = cfg.get("cmd")
    if isinstance(cmd, str):
        argv = ["bash", "-c", cmd]
    elif isinstance(cmd, list) and cmd and all(isinstance(x, str) for x in cmd):
        argv = list(cmd)
    else:
        return {**base, "status": "invalid_cmd"}
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="redo-acc-"))
    try:
        work = tmp / "w"
        shutil.copytree(final_ws, work, symlinks=True, ignore=shutil.ignore_patterns(*SKIP_DIRS))
        for name in sorted(SKIP_DIRS):
            src_link = origin / name
            if src_link.is_symlink():
                os.symlink(os.readlink(src_link), work / name)
        for rel in protected:
            want = (origin / rel).read_bytes()
            dst = work / rel
            have = dst.read_bytes() if (dst.is_file() and not dst.is_symlink()) else None
            if have != want:
                base["tests_tampered"].append(rel)
                if dst.is_symlink() or dst.is_file():
                    dst.unlink()
                elif dst.is_dir():
                    shutil.rmtree(dst)
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(want)
        env = _clean_env(tmp)
        for k, v in cfg.get("env", {}).items():
            env[str(k)] = str(v)
        rc, out = _run_quiet(argv, work, env, float(cfg.get("timeout_s", 120)))
        if rc is None:
            status = "timeout" if out == "timeout" else "spawn_error"
            return {**base, "accept": False, "status": status, "first_problem": out[-800:]}
        passed, run = _parse_command_counts(out)
        first = None if rc == 0 else (out.strip()[-800:] or f"exit {rc}")
        return {**base, "accept": rc == 0, "status": "ok", "passed": passed, "run": run, "first_problem": first}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def acceptance(origin: pathlib.Path, final_ws: pathlib.Path, cfg: dict) -> dict:
    """在最後工作區的**副本**裡、把題目原本的測試檔還原之後，跑那些測試。

    回傳 `{"accept": bool, "passed": int|None, ...}`。驗收自己壞掉（逾時、沒有輸出、沒有測試檔）
    ＝ `accept=False` 且 `status` 寫明原因——**壞掉的驗收不是通過**（I-4）。
    """
    kind = cfg.get("kind", "workspace_tests")
    if kind == "command":
        return _acceptance_command(origin, final_ws, cfg)
    patterns = cfg.get("patterns", ["*_test.py", "test_*.py"])
    tests = test_files(origin, patterns)
    base = {"accept": False, "kind": kind, "tests": tests, "passed": None, "run": None,
            "tests_tampered": [], "status": None, "first_problem": None,
            "test_results": {}, "failing_tests": []}
    if not tests:
        return {**base, "status": "no_tests_in_origin"}
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="redo-acc-"))
    try:
        work = tmp / "w"
        shutil.copytree(final_ws, work, symlinks=True, ignore=shutil.ignore_patterns(*SKIP_DIRS))
        for rel in tests:
            want = (origin / rel).read_bytes()
            have = (work / rel).read_bytes() if (work / rel).is_file() else None
            if have != want:
                base["tests_tampered"].append(rel)
                (work / rel).parent.mkdir(parents=True, exist_ok=True)
                (work / rel).write_bytes(want)
        by_dir: dict[str, list[str]] = {}
        for rel in tests:
            d, _, name = rel.rpartition("/")
            by_dir.setdefault(d, []).append(name[:-3])
        agg = {"run": 0, "failures": 0, "errors": 0, "skipped": 0, "unexpected_successes": 0}
        test_results: dict[str, bool] = {}
        first = None
        for d, mods in sorted(by_dir.items()):
            rc, out = _run_quiet([sys.executable, "-B", "-c", _UNITTEST_RUNNER, *mods], work / d if d else work,
                                 _clean_env(tmp), float(cfg.get("timeout_s", 120)))
            if "@@REDO_RESULT@@" not in out:
                return {**base, "status": "timeout" if out == "timeout" else "runner_no_output",
                        "first_problem": out[-800:]}
            r = json.loads(out.rsplit("@@REDO_RESULT@@", 1)[1].strip().splitlines()[0])
            if r["load_error"]:
                return {**base, "status": "load_error", "first_problem": r["load_error"], "run": agg["run"]}
            for k in agg:
                agg[k] += r[k]
            for tid, passed_flag in (r.get("test_results") or {}).items():
                key = f"{d}/{tid}" if d else tid
                test_results[key] = bool(passed_flag)
            first = first or r["first_problem"]
        bad = agg["failures"] + agg["errors"] + agg["unexpected_successes"]
        failing_tests = sorted(k for k, ok in test_results.items() if not ok)
        return {**base, "status": "ok", "run": agg["run"], "passed": agg["run"] - bad - agg["skipped"],
                "accept": agg["run"] > 0 and bad == 0 and agg["skipped"] == 0, "first_problem": first,
                "test_results": test_results, "failing_tests": failing_tests}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def grade(tdir: pathlib.Path, origin: pathlib.Path, final_ws: pathlib.Path, cfg: dict, acc: dict) -> dict:
    """題庫自己的評分器：`python3 <題>/scorer.py <題>/hidden <最後工作區>`，stdout 最後一行是含 `pass` 的 JSON。

    沒有 scorer.py 時，只有計畫明講 `visible_equals_grader` 才退回「原件測試的驗收結果」，
    而且每一格記 `grader_kind`，報告不會把兩種混在一起算。
    """
    scorer, hidden = tdir / "scorer.py", tdir / "hidden"
    if scorer.is_file() and hidden.is_dir():
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="redo-grade-"))
        try:
            rc, out = _run_quiet([sys.executable, str(scorer), str(hidden), str(final_ws)], tmp,
                                 {**_clean_env(tmp), "SUITE_TIMEOUT_S": str(cfg.get("suite_timeout_s", 60))},
                                 float(cfg.get("timeout_s", 240)))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        for line in reversed(out.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict) and "pass" in obj:
                    return {"pass": bool(obj["pass"]), "grader_kind": "staged_scorer",
                            "detail": {k: obj.get(k) for k in ("tests_passed", "tests_total", "status")}}
        return {"pass": None, "grader_kind": "staged_scorer", "detail": {"error": out[-400:]}}
    if cfg.get("visible_equals_grader"):
        return {"pass": bool(acc["accept"]), "grader_kind": "visible_tests_pristine", "detail": None}
    return {"pass": None, "grader_kind": "none", "detail": {"error": "no scorer.py/hidden and visible_equals_grader is false"}}


# ── 一次嘗試 ──────────────────────────────────────────────────────────────

def _subst(s: str, m: dict[str, str]) -> str:
    for k, v in m.items():
        s = s.replace("{" + k + "}", v)
    return s


def _archive(src: pathlib.Path, dst: pathlib.Path) -> None:
    for root, dirs, files in os.walk(src):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            fp = pathlib.Path(root) / f
            try:
                if fp.is_symlink() or fp.stat().st_size > ARCHIVE_FILE_CAP:
                    continue
                out = dst / fp.relative_to(src)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(fp, out)
            except OSError:
                continue


def health_wait(provider: dict, log) -> bool:
    url = provider.get("health_url")
    if not url:
        return True
    deadline = time.time() + float(provider.get("health_wait_s", 900))
    while True:
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                body = r.read(200_000).decode("utf-8", "replace")
            need = provider.get("health_contains")
            if r.status == 200 and (not need or need in body):
                return True
            why = f"HTTP {r.status}，或回應裡沒有 {need!r}"
        except Exception as e:           # noqa: BLE001 — 端點壞掉的方式很多，全都只是「還沒好」
            why = repr(e)
        if time.time() >= deadline:
            log(f"端點 {provider['name']} 一直沒好：{why}")
            return False
        log(f"端點 {provider['name']} 還沒好（{why}），30 秒後再看")
        time.sleep(30)


def one_attempt(plan: dict, arm: dict, tdir: pathlib.Path, provider: dict, adir: pathlib.Path,
                timeout_s: float, hint: str | None, cell_id: str, attempt_no: int,
                *, start_ws: pathlib.Path | None = None,
                snapshot_out: pathlib.Path | None = None) -> dict:
    """跑一次嘗試。回傳的 dict 一定有 `void`（基礎設施失敗）或 `acc`＋`grade`。"""
    agent = {**plan["agent"], **arm.get("agent", {})}
    origin = tdir / "workspace"
    src_ws = start_ws if start_ws is not None else origin
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="redo-"))
    os.chmod(tmp, 0o700)
    ws, logs = tmp / "w", adir / "logs"
    try:
        shutil.copytree(src_ws, ws, symlinks=True)
        origin_snap = snapshot(ws)
        prompt = task_prompt(tdir)
        if hint:
            prompt = prompt + "\n\n---\n" + hint
        env = dict(os.environ)
        for k in list(env):
            if k.startswith("VACANT_PI_") or k in ("VACANT_DO_RUN",):   # e016 attempt-1 的 env 洩漏
                del env[k]
        cfgdir = agent.get("config_dir")
        if cfgdir:
            cd = tmp / "agentcfg"
            cd.mkdir()
            src = expand(cfgdir["from"])
            for name in cfgdir.get("copy", []):
                s = src / name
                if s.is_dir():
                    shutil.copytree(s, cd / name, symlinks=True)
                elif s.is_file():
                    shutil.copyfile(s, cd / name)
            env[cfgdir["env"]] = str(cd)
        m = {"prompt": prompt, "provider": str(provider.get("provider", "")), "model": str(provider.get("model", "")),
             "logs": str(logs), "workspace": str(ws)}
        for k, v in {**agent.get("env", {}), **provider.get("env", {})}.items():
            env[k] = _subst(str(v), m)
        env["PWD"] = str(ws)
        if agent.get("export_cell_env"):            # 只給 selftest 的假 agent 用
            env["REDO_CELL"], env["REDO_ATTEMPT"] = cell_id, str(attempt_no)
        argv = [_subst(a, m) for a in agent["argv"]]
        drop = re.compile(agent["log_drop_re"]) if agent.get("log_drop_re") else None
        logs.mkdir(parents=True, exist_ok=True)
        started = now()
        r = run_agent(argv, env, ws, timeout_s, adir / "agent.log", drop)
        final_snap = snapshot(ws)
        changed = final_snap != origin_snap
        _uk = agent.get("usage", "pi_json")
        usage = (usage_from_log(adir / "agent.log") if _uk == "pi_json" else
                 usage_from_claude_log(adir / "agent.log") if _uk == "claude_stream_json" else
                 usage_from_devin_log(adir / "agent.log") if _uk == "devin_atif" else None)
        try:
            tail = (adir / "agent.log").read_bytes()[-20000:].decode("utf-8", "replace")
        except OSError:
            tail = ""
        infra_re = re.compile(agent.get("infra_re", INFRA_RE_DEFAULT), re.I)
        meta = {"started": started, "argv0": argv[0], "provider": provider["name"], "timeout_s": timeout_s,
                "workspace_changed": changed, "usage": usage, "hint_bytes": len(hint.encode()) if hint else 0,
                "hint_text": hint, **r}
        # 基礎設施失敗（不算嘗試）的三種樣子，判定都與「過不過」無關：
        #  a. agent 起不來；b. 工作區沒動，而且一次成功的模型回應都沒有，或輸出尾端是連線類錯誤；
        #  c. 做到一半模型死掉：最後一則 assistant 訊息是連線類錯誤（工作區可能已經動過）。
        # 不是連線類的最後錯誤（例如超過上下文長度）算這個 agent＋模型自己的失敗，照常驗收、計入分母，
        # 原文記在 usage.final_error，報告會列出來給人判斷。
        died = bool(usage and usage.get("final_error") and infra_re.search(usage["final_error"]))
        if r.get("spawn_error") or died or (not changed and ((usage is not None and usage["calls"] == 0)
                                                             or infra_re.search(tail))):
            why = r.get("spawn_error") or ("model_died_mid_run" if died and changed else
                                           "no_model_calls" if usage is not None and usage["calls"] == 0 else "infra_marker")
            write_json(adir / "attempt.json", {**meta, "void": why})
            return {**meta, "void": why}
        acc = acceptance(origin, ws, plan.get("acceptance", {}))
        gr = grade(tdir, origin, ws, plan.get("grader", {}), acc)
        _archive(ws, adir / "workspace")
        if snapshot_out is not None:
            if snapshot_out.exists():
                shutil.rmtree(snapshot_out)
            shutil.copytree(ws, snapshot_out, symlinks=True, ignore=shutil.ignore_patterns(*SKIP_DIRS))
            # Restore pristine original test files in the live snapshot so carried-over workspaces stay clean.
            acfg = plan.get("acceptance", {})
            if acfg.get("kind", "workspace_tests") == "workspace_tests":
                for rel in test_files(origin, acfg.get("patterns", ["*_test.py", "test_*.py"])):
                    dst = snapshot_out / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes((origin / rel).read_bytes())
        write_json(adir / "files.json", {"origin": origin_snap, "final": final_snap})
        return {**meta, "void": None, "acc": acc, "grade": gr}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def make_hint(acc: dict) -> str:
    body = (acc.get("first_problem") or acc.get("status") or "").encode("utf-8")[:HINT_CAP - len(HINT_HEAD.encode())]
    text = HINT_HEAD + body.decode("utf-8", "ignore")
    if _KS1_BANNED.search(HINT_HEAD):
        raise AssertionError("KS-1：提示模板含責任／懲罰類措辭")
    return text


def _import_controller():
    """Import vacant_network.controller (and logbook/identity) from the repo root."""
    repo_root = str(pathlib.Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from vacant_network import controller as ctl
    from vacant_network.identity import Identity
    from vacant_network.logbook import Logbook
    return ctl, Identity, Logbook


def _acc_to_ctl_record(acc: dict) -> dict:
    """Extract strictly acceptance-only fields for the evidence controller (never reads grade)."""
    return {
        "tests": dict(acc.get("test_results") or {}),
        "failing_tests": list(acc.get("failing_tests") or []),
        "passed": int(acc["passed"]) if acc.get("passed") is not None else 0,
        "total": int(acc["run"]) if acc.get("run") is not None else len(acc.get("test_results") or {}),
        "accepted": bool(acc.get("accept")),
        "status": acc.get("status"),
        "first_problem": acc.get("first_problem"),
    }


# ── 一格（一題 × 一次重複 × 一臂）──────────────────────────────────────────

def run_cell(plan: dict, bank: pathlib.Path, task: str, rep: int, arm_name: str, provider: dict,
             root: pathlib.Path, log) -> dict:
    cdir = root / "cells" / task / f"r{rep}" / arm_name
    done = cdir / "cell.json"
    if done.is_file():
        return read_json(done)
    if cdir.exists():                       # 上一次被中斷的半成品：整格重來（嘗試之間不能留東西）
        shutil.rmtree(cdir)
    cdir.mkdir(parents=True)
    arm, tdir = plan["arms"][arm_name], bank / task
    cell_id = f"{task}/r{rep}/{arm_name}"
    policy = arm["policy"]
    max_attempts = 1 if policy == "single" else int(arm.get("max_attempts", 3))
    T = float(arm.get("attempt_timeout_s", plan["attempt_timeout_s"]))
    budget = float(arm.get("budget_s", T * max_attempts))
    min_attempt_s = float(arm.get("min_attempt_s", 60))
    t0, spent = time.time(), 0.0
    attempts: list[dict] = []
    voids = 0
    cell: dict[str, Any] = {"cell": cell_id, "task": task, "rep": rep, "arm": arm_name, "provider": provider["name"],
                            "plan_sha256": plan["_sha256"], "harness_sha256": HARNESS_SHA, "started": now(),
                            "infra_void": None}
    hint: str | None = None
    is_ctl = policy == "controller"
    ctl_snap_root: pathlib.Path | None = pathlib.Path(tempfile.mkdtemp(prefix="redo-ctlsnap-")) if is_ctl else None
    ctl_mod = ctl_id = ctl_book = None
    chain_path = cdir / "controller_chain.ndjson"
    if is_ctl:
        ctl_mod, _Identity, _Logbook = _import_controller()
        ctl_id = _Identity.generate()
        ctl_book = _Logbook()
    ctl_history: list[dict] = []
    ctl_snaps: list[pathlib.Path] = []
    best_idx: int | None = None
    best_rec: dict | None = None
    next_start_ws: pathlib.Path | None = None
    start_ws_label = "origin"
    try:
        while len(attempts) < max_attempts:
            remaining = budget - spent
            if attempts and remaining < min_attempt_s:
                break
            if not health_wait(provider, log):
                cell["infra_void"] = "endpoint_down"
                break
            k = len(attempts) + 1
            adir = cdir / f"attempt_{k}"
            if adir.exists():
                shutil.rmtree(adir)
            snap_out = (ctl_snap_root / f"attempt_{k}") if is_ctl and ctl_snap_root is not None else None
            res = one_attempt(plan, arm, tdir, provider, adir, min(T, remaining), hint, cell_id, k,
                              start_ws=next_start_ws if is_ctl else None,
                              snapshot_out=snap_out)
            if res["void"]:
                voids += 1
                os.replace(adir, cdir / f"void_{voids}_attempt_{k}")
                log(f"{cell_id} 第 {k} 次嘗試是基礎設施失敗（{res['void']}），不算嘗試（{voids}/{VOID_RETRIES}）")
                if voids >= VOID_RETRIES:
                    cell["infra_void"] = f"void×{voids}:{res['void']}"
                    break
                time.sleep(VOID_BACKOFF_S[voids - 1] * float(plan.get("backoff_scale", 1.0)))
                continue
            spent += res["wall_s"]
            attempts.append(res)
            if is_ctl:
                assert ctl_mod is not None and ctl_book is not None and ctl_id is not None and snap_out is not None
                ctl_snaps.append(snap_out)
                cur_rec = _acc_to_ctl_record(res["acc"])
                rem_after = budget - spent
                rem_attempts = max_attempts - len(attempts)
                dec = ctl_mod.decide(
                    cur_rec,
                    ctl_history,
                    best_rec,
                    remaining_attempts=rem_attempts,
                    remaining_budget_s=rem_after,
                    min_attempt_s=min_attempt_s,
                )
                ctl_mod.controller_event(
                    ctl_book,
                    ctl_id,
                    attempt=k,
                    decision=dec,
                    extra={"cell": cell_id, "start_workspace": start_ws_label},
                )
                ctl_mod.save_controller_chain(ctl_book, ctl_id, chain_path)
                res["controller"] = {
                    "action": dec.action,
                    "rule": dec.rule,
                    "passed": dec.evidence["passed"],
                    "total": dec.evidence["total"],
                    "signature": dec.evidence["failure_signature"],
                    "reason": dec.reason,
                    "feedback_source": dec.feedback_source,
                    "start_workspace": start_ws_label,
                }
                write_json(adir / "attempt.json", res)
                # Update best_idx / best_rec (tie goes to latest, accepted wins).
                if best_rec is None or cur_rec["accepted"] or (
                    not best_rec["accepted"] and cur_rec["passed"] >= best_rec["passed"]
                ):
                    best_idx = len(attempts) - 1
                    best_rec = cur_rec
                ctl_history.append(cur_rec)
                if dec.action in (ctl_mod.ACTION_STOP_SUCCESS, ctl_mod.ACTION_DELIVER_BEST_BUDGET):
                    break
                if dec.action == ctl_mod.ACTION_RESTORE_BEST:
                    assert best_idx is not None
                    next_start_ws = ctl_snaps[best_idx]
                    start_ws_label = f"restore_best:attempt_{best_idx + 1}"
                    fb_acc = attempts[best_idx]["acc"]
                elif dec.action == ctl_mod.ACTION_RESTART_FRESH:
                    next_start_ws = None
                    start_ws_label = "restart_fresh:origin"
                    fb_acc = res["acc"]
                else:
                    # repair or continue -> keep current workspace
                    next_start_ws = ctl_snaps[-1]
                    start_ws_label = f"{dec.action}:attempt_{k}"
                    fb_acc = res["acc"]
                hint = ctl_mod.build_controller_feedback(
                    dec.action,
                    fb_acc.get("failing_tests") or [],
                    fb_acc.get("first_problem"),
                    status=fb_acc.get("status"),
                )
            else:
                write_json(adir / "attempt.json", res)
                # ── 政策：只讀 acc，不讀 grade ──
                if _policy_stop(arm, res["acc"]):
                    break
                hint_mode = arm.get("hint", "none")
                if hint_mode == "first_failure":
                    hint = make_hint(res["acc"])
                elif hint_mode == "failing_tests":
                    _ctl, _, _ = _import_controller()
                    hint = _ctl.build_feedback(
                        res["acc"].get("failing_tests") or [],
                        res["acc"].get("first_problem"),
                        status=res["acc"].get("status"),
                    )
    finally:
        if ctl_snap_root is not None:
            shutil.rmtree(ctl_snap_root, ignore_errors=True)
    cell["voids"] = voids
    cell["n_attempts"] = len(attempts)
    cell["wall_s"] = round(time.time() - t0, 1)
    cell["agent_wall_s"] = round(spent, 1)
    cell["attempts"] = [
        {
            "k": i + 1, "accept": a["acc"]["accept"], "acc_status": a["acc"]["status"],
            "acc_passed": a["acc"]["passed"], "acc_run": a["acc"]["run"],
            "tests_tampered": a["acc"]["tests_tampered"], "grade_pass": a["grade"]["pass"],
            "grader_kind": a["grade"]["grader_kind"], "wall_s": a["wall_s"], "timed_out": a["timed_out"],
            "rc": a["rc"], "usage": a["usage"], "workspace_changed": a["workspace_changed"],
            **(
                {
                    "action": a["controller"]["action"],
                    "rule": a["controller"]["rule"],
                    "passed": a["controller"]["passed"],
                    "total": a["controller"]["total"],
                    "signature": a["controller"]["signature"],
                    "start_workspace": a["controller"]["start_workspace"],
                }
                if "controller" in a else {}
            ),
        }
        for i, a in enumerate(attempts)
    ]
    if is_ctl and chain_path.is_file():
        cell["chain_path"] = str(chain_path)
    if cell["infra_void"] is None and not attempts:
        cell["infra_void"] = "no_attempt"
    if cell["infra_void"] is None:
        d = _policy_deliver([a["acc"] for a in attempts])
        cell["delivered_attempt"] = d + 1
        cell["accepted"] = bool(attempts[d]["acc"]["accept"])
        cell["pass"] = attempts[d]["grade"]["pass"]
        cell["grader_kind"] = attempts[d]["grade"]["grader_kind"]
        if cell["pass"] is None:
            cell["infra_void"] = "grader_failed"
    cell["ended"] = now()
    write_json(done, cell)
    return cell


def _policy_stop(arm: dict, acc: dict) -> bool:
    """政策唯一的輸入是驗收結果。single 一律停；restart 在驗收通過時停。"""
    return arm["policy"] == "single" or bool(acc["accept"])


def _policy_deliver(accs: list[dict]) -> int:
    """交哪一次：第一個驗收通過的；都沒過就交原件測試過最多的（同分取最後一次）。只讀驗收結果。"""
    for i, a in enumerate(accs):
        if a["accept"]:
            return i
    best = max(range(len(accs)), key=lambda i: (accs[i]["passed"] or 0, i))
    return best


# ── 整批 ──────────────────────────────────────────────────────────────────

def _git(args: list[str], cwd: pathlib.Path) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def cmd_run(a: argparse.Namespace) -> int:
    plan_path = pathlib.Path(a.plan).resolve()
    plan = load_plan(plan_path)
    root = pathlib.Path(a.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    # 每台機器一把鎖（2026-11-25，--only-providers）：兩份 runner 可以在同一個 root 各跑不同的機器，
    # 但同一台機器的佇列永遠只有一份在跑；沒給篩選＝這份要跑全部機器＝拿全部的鎖。
    names = [p["name"] for p in plan["providers"]]
    only_p = [x for x in (getattr(a, "only_providers", None) or "").split(",") if x]
    if any(x not in names for x in only_p):
        print(f"拒絕啟動：--only-providers 裡有計畫沒有的機器 {only_p}（計畫裡有 {names}）", file=sys.stderr)
        return 2
    locks = []
    for name in (only_p or names):
        lk = open(root / f".lock-{name}", "w")
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print(f"拒絕啟動：{root} 已經有一份 runner 在跑機器 {name}", file=sys.stderr)
            return 2
        locks.append(lk)
    rjl = open(root / ".lock-runjson", "w")
    fcntl.flock(rjl, fcntl.LOCK_EX)          # RUN.json 的建立／比對不能兩份同時做
    runf = root / "RUN.json"
    if runf.is_file():
        prev = read_json(runf)
        if prev["plan_sha256"] != plan["_sha256"]:
            print(f"拒絕啟動：這個 root 是用另一份計畫內容開的（{prev['plan_sha256'][:12]} ≠ {plan['_sha256'][:12]}）。"
                  "計畫改了就換一個新的 root。", file=sys.stderr)
            return 2
    else:
        if not a.allow_uncommitted_plan:
            dirty = _git(["status", "--porcelain", "--", str(plan_path)], plan_path.parent)
            if dirty is None or dirty != "":
                print("拒絕啟動：計畫檔還沒 commit（預註冊要在第一通模型呼叫之前凍結）。先 commit 再跑；"
                      "selftest／冒煙用的臨時計畫才加 --allow-uncommitted-plan。", file=sys.stderr)
                return 2
        write_json(runf, {"plan_id": plan["id"], "plan_sha256": plan["_sha256"], "plan_path": str(plan_path),
                          "plan": {k: v for k, v in plan.items() if not k.startswith("_")},
                          "git_head": _git(["rev-parse", "HEAD"], plan_path.parent), "created": now()})
    fcntl.flock(rjl, fcntl.LOCK_UN)
    bank = resolve_bank(plan, a.bank)
    loglock = threading.Lock()

    def log(msg: str) -> None:
        line = f"{now()}  {msg}"
        with loglock:
            print(line, flush=True)
            with open(root / "runner.log", "a", encoding="utf-8") as f:
                f.write(line + "\n")

    pairs = planned_pairs(plan)
    only_t = set(a.only_tasks.split(",")) if a.only_tasks else None
    only_r = {int(x) for x in a.only_reps.split(",")} if a.only_reps else None
    work: dict[str, list[tuple[int, str, int]]] = {p["name"]: [] for p in plan["providers"]}
    for i, (t, r) in enumerate(pairs):
        if (only_t and t not in only_t) or (only_r and r not in only_r):
            continue
        if only_p and provider_for(plan, i)["name"] not in only_p:
            continue
        work[provider_for(plan, i)["name"]].append((i, t, r))
    if a.max_pairs:
        left = int(a.max_pairs)
        for name in work:
            work[name], left = work[name][:left], max(0, left - len(work[name]))
    log(f"計畫 {plan['id']}（{plan['_sha256'][:12]}） 題庫 {bank}  這次要處理 {sum(map(len, work.values()))} 對"
        f"（全計畫 {len(pairs)} 對）  harness {HARNESS_SHA[:12]}")
    stop = threading.Event()

    def worker(pname: str, q: list[tuple[int, str, int]]) -> None:
        prov = next(p for p in plan["providers"] if p["name"] == pname)
        while not stop.is_set():
            with loglock:
                if not q:
                    return
                i, t, r = q.pop(0)
            for arm in arm_order(plan, t, r):
                if stop.is_set():
                    return
                try:
                    c = run_cell(plan, bank, t, r, arm, prov, root, log)
                except Exception as e:      # noqa: BLE001 — 一格壞掉不能拖垮整批；那一格沒有 cell.json，下次續跑會重做
                    log(f"{t}/r{r}/{arm} harness 例外（這一格沒有結果，續跑時重做）：{e!r}")
                    continue
                log(f"{c['cell']:<44} " + (f"infra_void={c['infra_void']}" if c["infra_void"] else
                    f"pass={c['pass']} accepted={c['accepted']} attempts={c['n_attempts']} wall={c['agent_wall_s']}s"))

    threads = []
    for p in plan["providers"]:
        for _ in range(int(p.get("jobs", 1))):
            th = threading.Thread(target=worker, args=(p["name"], work[p["name"]]), daemon=True)
            th.start()
            threads.append(th)
    def _term(signum, frame):               # noqa: ARG001
        raise KeyboardInterrupt

    old_handlers = {}
    if threading.current_thread() is threading.main_thread():
        for sg in (signal.SIGTERM, signal.SIGHUP):
            old_handlers[sg] = signal.signal(sg, _term)
    try:
        for th in threads:
            while th.is_alive():
                th.join(timeout=1)
    except KeyboardInterrupt:
        stop.set()
        kill_all_live()
        log("收到中斷：正在跑的那一格會被丟掉（下次續跑重做），已完成的格保留")
        return 130
    finally:
        for sg, h in old_handlers.items():
            signal.signal(sg, h)
    rep = build_report(root)
    log(f"這一輪結束。狀態：{rep['state']}（完成 {rep['pairs_complete']}/{rep['pairs_planned']} 對）")
    return 0


# ── 報告 ──────────────────────────────────────────────────────────────────

def load_cells(root: pathlib.Path) -> list[dict]:
    return [read_json(p) for p in sorted((root / "cells").glob("*/r*/*/cell.json"))]


def _count(xs: list) -> dict[str, int]:
    out: dict[str, int] = {}
    for x in xs:
        if x:
            out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items()))


def build_report(root: pathlib.Path) -> dict:
    run = read_json(root / "RUN.json")
    plan = run["plan"]
    cells = [c for c in load_cells(root) if c["plan_sha256"] == run["plan_sha256"]]
    ctrl, treat = plan["pair"]
    by = {(c["task"], c["rep"], c["arm"]): c for c in cells}
    per_arm: dict[str, dict] = {}
    for arm in plan["arms"]:
        cs = [c for c in cells if c["arm"] == arm]
        ok = [c for c in cs if not c["infra_void"]]
        calls = [sum((x["usage"] or {}).get("calls") or 0 for x in c["attempts"]) for c in ok
                 if all(x["usage"] is not None for x in c["attempts"])]
        per_arm[arm] = {
            "cells": len(cs), "scored": len(ok), "infra_void": len(cs) - len(ok),
            "pass": sum(1 for c in ok if c["pass"]),
            "rate": round(sum(1 for c in ok if c["pass"]) / len(ok), 4) if ok else None,
            "accepted": sum(1 for c in ok if c["accepted"]),
            "accepted_but_wrong": sum(1 for c in ok if c["accepted"] and not c["pass"]),
            "mean_attempts": round(sum(c["n_attempts"] for c in ok) / len(ok), 3) if ok else None,
            "mean_agent_wall_s": round(sum(c["agent_wall_s"] for c in ok) / len(ok), 1) if ok else None,
            "timeouts": sum(1 for c in ok for x in c["attempts"] if x["timed_out"]),
            "tests_tampered_attempts": sum(1 for c in ok for x in c["attempts"] if x["tests_tampered"]),
            "mean_model_calls": round(sum(calls) / len(calls), 1) if calls else None,
            "model_calls_known_cells": len(calls),
            "grader_kinds": sorted({c.get("grader_kind") for c in ok if c.get("grader_kind")}),
            "final_errors_counted_as_attempts": _count([(x["usage"] or {}).get("final_error") for c in ok
                                                         for x in c["attempts"]]),
        }
    # 訊號的混淆矩陣：每一次嘗試的「驗收」對「評分器」（政策只看前者）
    sig = {"accept_pass": 0, "accept_fail": 0, "reject_pass": 0, "reject_fail": 0}
    for c in cells:
        for x in c.get("attempts", []):
            if x["grade_pass"] is None:
                continue
            sig[("accept" if x["accept"] else "reject") + ("_pass" if x["grade_pass"] else "_fail")] += 1
    pairs_planned = len(plan["tasks"]) * int(plan["reps"])
    b = c_ = both = neither = 0
    void_pairs: list[str] = []
    per_rep: dict[int, dict] = {}
    per_task: dict[str, dict] = {t: {"ctrl": 0, "treat": 0, "pairs": 0} for t in plan["tasks"]}
    complete = 0
    for t in plan["tasks"]:
        for r in range(1, int(plan["reps"]) + 1):
            x, y = by.get((t, r, ctrl)), by.get((t, r, treat))
            if x is None or y is None:
                continue
            complete += 1
            if x["infra_void"] or y["infra_void"]:
                void_pairs.append(f"{t}/r{r}")
                continue
            pr = per_rep.setdefault(r, {"pairs": 0, "ctrl_pass": 0, "treat_pass": 0, "b": 0, "c": 0})
            pr["pairs"] += 1
            pr["ctrl_pass"] += bool(x["pass"]); pr["treat_pass"] += bool(y["pass"])
            per_task[t]["pairs"] += 1
            per_task[t]["ctrl"] += bool(x["pass"]); per_task[t]["treat"] += bool(y["pass"])
            if x["pass"] and y["pass"]:
                both += 1
            elif x["pass"]:
                b += 1; pr["b"] += 1
            elif y["pass"]:
                c_ += 1; pr["c"] += 1
            else:
                neither += 1
    for pr in per_rep.values():
        pr["p"] = round(mcnemar_exact(pr["b"], pr["c"]), 6)
    p = mcnemar_exact(b, c_)
    alpha = float(plan.get("analysis", {}).get("alpha", 0.05))
    scored_pairs = both + b + c_ + neither
    kinds = {k for v in per_arm.values() for k in v["grader_kinds"]}
    if complete < pairs_planned:
        state = "INCOMPLETE"
    elif len(kinds) > 1:
        state = "MIXED_GRADER"            # 兩種評分方式混在一批裡：不下結論
    elif c_ > b and p < alpha:
        state = "EFFECTIVE"
    elif b > c_ and p < alpha:
        state = "CONTRADICTS"
    else:
        state = "UNRESOLVED"
    tasks_pos = sum(1 for v in per_task.values() if v["treat"] > v["ctrl"])
    tasks_neg = sum(1 for v in per_task.values() if v["treat"] < v["ctrl"])
    harness = sorted({c["harness_sha256"] for c in cells})
    rep = {
        "schema": "vacant.redo.report/1", "plan_id": plan["id"], "plan_sha256": run["plan_sha256"],
        "generated": now(), "state": state, "control": ctrl, "treatment": treat,
        "pairs_planned": pairs_planned, "pairs_complete": complete, "pairs_scored": scored_pairs,
        "pairs_infra_void": void_pairs,
        "paired": {"both": both, "control_only_b": b, "treatment_only_c": c_, "neither": neither,
                   "mcnemar_exact_p_two_sided": round(p, 6), "alpha": alpha,
                   "delta_pp": round(100.0 * (c_ - b) / scored_pairs, 2) if scored_pairs else None,
                   "distinct_tasks_net_positive": tasks_pos, "distinct_tasks_net_negative": tasks_neg},
        "per_rep": {str(k): v for k, v in sorted(per_rep.items())},
        "per_arm": per_arm,
        "signal": {**sig, "note": "每一次嘗試的驗收（政策看得到）對評分器（政策看不到）。accept_fail＝驗收放行了錯的；"
                                   "這個數字大的題庫，驗收訊號不能當真訊號引用。"},
        "per_task": per_task,
        "harness_sha256": harness, "harness_changed_mid_run": len(harness) > 1,
        "quoting_rule": "只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講："
                        "模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。",
    }
    write_json(root / "REPORT.json", rep)
    (root / "REPORT.md").write_text(render_md(rep), encoding="utf-8")
    return rep


def render_md(r: dict) -> str:
    pa, p = r["per_arm"], r["paired"]
    lines = [f"# {r['plan_id']} — {r['state']}", "",
             f"計畫 sha256 `{r['plan_sha256'][:16]}…`　完成 {r['pairs_complete']}/{r['pairs_planned']} 對"
             f"（有效 {r['pairs_scored']}，infra_void {len(r['pairs_infra_void'])}）　產生於 {r['generated']}", "",
             "| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |",
             "|---|---|---|---|---|---|---|---|"]
    for name, v in pa.items():
        lines.append(f"| {name} | {v['pass']}/{v['scored']} | {v['rate']} | {v['mean_attempts']} | "
                     f"{v['mean_agent_wall_s']}s | {v['timeouts']} | {v['accepted_but_wrong']} | {v['mean_model_calls']} |")
    lines += ["", f"**配對（{r['control']} 對 {r['treatment']}）**：只有對照過 b＝{p['control_only_b']}、只有處理過 "
              f"c＝{p['treatment_only_c']}、都過 {p['both']}、都沒過 {p['neither']}；精確 McNemar 雙尾 "
              f"p＝{p['mcnemar_exact_p_two_sided']}；差 {p['delta_pp']} 個百分點；"
              f"題數上淨正 {p['distinct_tasks_net_positive']}／淨負 {p['distinct_tasks_net_negative']}。", "",
              "| rep | 對數 | 對照過 | 處理過 | b | c | p |", "|---|---|---|---|---|---|---|"]
    for k, v in r["per_rep"].items():
        lines.append(f"| {k} | {v['pairs']} | {v['ctrl_pass']} | {v['treat_pass']} | {v['b']} | {v['c']} | {v['p']} |")
    s = r["signal"]
    lines += ["", f"**驗收訊號對評分器（每一次嘗試）**：放行且對 {s['accept_pass']}、放行卻錯 {s['accept_fail']}、"
              f"擋下卻對 {s['reject_pass']}、擋下且錯 {s['reject_fail']}。", "",
              f"引用規則：{r['quoting_rule']}", ""]
    errs = {k: v["final_errors_counted_as_attempts"] for k, v in pa.items() if v["final_errors_counted_as_attempts"]}
    if errs:
        lines.append("⚠ 有嘗試以模型錯誤結束、但沒被歸成基礎設施失敗（照常計入分母）。看原文決定是不是該歸成 void："
                     f"`{json.dumps(errs, ensure_ascii=False)}`\n")
    if r["harness_changed_mid_run"]:
        lines.append("⚠ 這一批跑到一半 harness 改過（多個 harness_sha256）——不可引用，要說明差異或重跑。\n")
    return "\n".join(lines)


def cmd_report(a: argparse.Namespace) -> int:
    rep = build_report(pathlib.Path(a.root).resolve())
    print(render_md(rep))
    return 0


def cmd_status(a: argparse.Namespace) -> int:
    root = pathlib.Path(a.root).resolve()
    rep = build_report(root)
    print(f"{rep['plan_id']}: {rep['state']}  {rep['pairs_complete']}/{rep['pairs_planned']} 對  "
          + "  ".join(f"{k}={v['pass']}/{v['scored']}" for k, v in rep["per_arm"].items())
          + f"  b={rep['paired']['control_only_b']} c={rep['paired']['treatment_only_c']}"
          + f"  infra_void 對={len(rep['pairs_infra_void'])}")
    return 0


# ── 發射前檢查 ────────────────────────────────────────────────────────────

def cmd_preflight(a: argparse.Namespace) -> int:
    """不呼叫模型。把「一發射就會白跑」的事情先查出來，一行一個 OK／FAIL。"""
    plan = load_plan(pathlib.Path(a.plan).resolve())
    ok = True

    def say(good: bool, msg: str) -> None:
        nonlocal ok
        ok = ok and good
        print(("OK    " if good else "FAIL  ") + msg)

    try:
        bank = resolve_bank(plan, a.bank)
        say(True, f"題庫 {bank}（{len(plan['tasks'])} 題都有 workspace/）")
    except PlanError as e:
        say(False, str(e))
        bank = None
    if bank is not None:
        acfg, gcfg = plan.get("acceptance", {}), plan.get("grader", {})
        if acfg.get("kind") == "command":
            cmd0 = acfg["cmd"][0]
            cexe = shutil.which(cmd0)
            say(cexe is not None, f"驗收指令 {cmd0} → {cexe}")
            protect = acfg.get("protect", [])
            if protect:
                no_tests = [t for t in plan["tasks"] if not test_files(bank / t / "workspace", protect)]
                say(not no_tests,
                    f"每一題的工作區都有受保護檔案（{protect}）" if not no_tests
                    else f"{len(no_tests)} 題的工作區缺受保護檔案 {protect}：{no_tests[:5]}")
        else:
            no_tests = [t for t in plan["tasks"]
                        if not test_files(bank / t / "workspace", acfg.get("patterns", ["*_test.py", "test_*.py"]))]
            say(not no_tests,
                "每一題的工作區都有測試檔（驗收訊號的來源）" if not no_tests else f"{len(no_tests)} 題的工作區沒有測試檔：{no_tests[:5]}")
        no_scorer = [t for t in plan["tasks"] if not ((bank / t / "scorer.py").is_file() and (bank / t / "hidden").is_dir())]
        if no_scorer and gcfg.get("visible_equals_grader"):
            say(len(no_scorer) == len(plan["tasks"]),
                f"{len(no_scorer)} 題沒有 scorer.py／hidden：用「原件測試」當評分（visible_equals_grader）"
                + ("" if len(no_scorer) == len(plan["tasks"]) else "——但不是每一題都這樣，會變成 MIXED_GRADER"))
        else:
            say(not no_scorer, "每一題都有 scorer.py＋hidden/" if not no_scorer else f"{len(no_scorer)} 題缺 scorer.py 或 hidden/：{no_scorer[:5]}")
        # 起點必須是紅的：原封不動的工作區不可以通過驗收（否則「通過」沒有資訊）
        t0 = plan["tasks"][0]
        acc0 = acceptance(bank / t0 / "workspace", bank / t0 / "workspace", acfg)
        neg_ok = (not acc0["accept"] and acc0["status"] == "ok") if acfg.get("kind") == "command" else (not acc0["accept"])
        say(neg_ok, f"負控制：{t0} 原封不動的工作區被驗收擋下（status={acc0['status']}）"
            if neg_ok else f"負控制失敗：{t0} 原封不動的工作區 accept={acc0['accept']} status={acc0['status']}")
    agent = plan["agent"]
    exe = shutil.which(agent["argv"][0])
    say(exe is not None, f"agent 指令 {agent['argv'][0]} → {exe}")
    cfgdir = agent.get("config_dir")
    if cfgdir:
        src = expand(cfgdir["from"])
        miss = [n for n in cfgdir.get("copy", []) if not (src / n).exists()]
        say(not miss, f"agent 設定來源 {src}（複製 {cfgdir.get('copy')}）" if not miss else f"{src} 缺 {miss}")
        mj = src / "models.json"
        if mj.is_file():
            text = mj.read_text(encoding="utf-8", errors="replace")
            for p in plan["providers"]:
                if p.get("provider"):
                    say(p["provider"] in text, f"provider {p['provider']} 在 {mj} 裡" if p["provider"] in text
                        else f"provider {p['provider']} 不在 {mj} 裡——改計畫的 providers（還沒發射前可以改，改完 commit）")
    for p in plan["providers"]:
        if p.get("health_url"):
            say(health_wait({**p, "health_wait_s": 0}, lambda m: None), f"端點 {p['name']} {p['health_url']}")
    dirty = _git(["status", "--porcelain", "--", plan["_path"]], pathlib.Path(plan["_path"]).parent)
    if getattr(a, "allow_uncommitted_plan", False):
        say(True, "計畫檔尚未 commit（--allow-uncommitted-plan 已允許）" if dirty != "" else "計畫檔已 commit（預註冊凍結）")
    else:
        say(dirty == "", "計畫檔已 commit（預註冊凍結）" if dirty == "" else "計畫檔還沒 commit")
    print(f"\n計畫 {plan['id']} sha256 {plan['_sha256']}\nVERDICT: {'PREFLIGHT_OK' if ok else 'PREFLIGHT_FAIL'}")
    return 0 if ok else 1


# ── selftest：假 agent、玩具題庫，0 次模型呼叫 ─────────────────────────────

_STUB_AGENT = r'''
import json, os, pathlib, sys, time
state = pathlib.Path(os.environ["STUB_STATE"]); state.mkdir(exist_ok=True)
cell = os.environ["REDO_CELL"]; task = cell.split("/")[0]
cf = state / (cell.replace("/", "__") + ".n")
n = int(cf.read_text()) + 1 if cf.exists() else 1
cf.write_text(str(n))
(state / (cell.replace("/", "__") + f".prompt{n}")).write_text(sys.argv[1])
GOOD, BAD = "def f(x):\n    return x + 1\n", "def f(x):\n    return x\n"
def emit(calls=1):
    for _ in range(calls):
        print(json.dumps({"type": "message_end", "message": {"role": "assistant", "usage": {"input": 100, "output": 10}}}))
print(json.dumps({"type": "session_start"}))
def err(msg):
    print(json.dumps({"type": "message_end", "message": {"role": "assistant", "stopReason": "error",
                                                           "errorMessage": msg, "usage": {"input": 0, "output": 0}}}))
if task == "t_died" and n == 1:
    emit(); pathlib.Path("sol.py").write_text(BAD); err("Connection error."); sys.exit(0)   # 寫到一半模型死掉
if task == "t_ctxlen":
    emit(); pathlib.Path("sol.py").write_text(BAD); err("400 context length exceeded"); sys.exit(0)
if task == "t_infra" and n == 1:
    print("Error: connect ECONNREFUSED 127.0.0.1:1234"); sys.exit(1)      # 模型沒起來：0 次呼叫、沒動工作區
if task == "t_always":
    emit(); pathlib.Path("sol.py").write_text(GOOD)
elif task == "t_never":
    emit(); pathlib.Path("sol.py").write_text(BAD)
elif task in ("t_second", "t_infra", "t_died"):
    emit(); pathlib.Path("sol.py").write_text(GOOD if (n >= 2) else BAD)
elif task == "t_tamper":
    emit(); pathlib.Path("sol.py").write_text(BAD)
    pathlib.Path("sol_test.py").write_text("import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        pass\n")
elif task == "t_timeout":
    emit()
    if n == 1:
        pathlib.Path("sol.py").write_text(BAD); sys.stdout.flush(); time.sleep(60)
    pathlib.Path("sol.py").write_text(GOOD)
'''
_TOY_TEST = ("import unittest\nfrom sol import f\n\nclass T(unittest.TestCase):\n"
             "    def test_one(self):\n        self.assertEqual(f(1), 2)\n"
             "    def test_two(self):\n        self.assertEqual(f(41), 42)\n")
_TOY_SCORER = r'''
import json, os, shutil, subprocess, sys, tempfile
hidden, ws = sys.argv[1], sys.argv[2]
d = tempfile.mkdtemp()
ok = False
if os.path.isfile(os.path.join(ws, "sol.py")):
    shutil.copy(os.path.join(ws, "sol.py"), d); shutil.copy(os.path.join(hidden, "tests", "sol_test.py"), d)
    ok = subprocess.run([sys.executable, "-B", "-m", "unittest", "sol_test"], cwd=d, capture_output=True).returncode == 0
print(json.dumps({"pass": ok}))
'''


def selftest(verbose: bool = True) -> int:
    """整條流程（兩臂政策、驗收、評分、void 重試、逾時殺行程群組、續跑、計畫漂移、報告）跑一遍並核對數字。"""
    checks: list[tuple[bool, str]] = []

    def chk(cond: bool, msg: str) -> None:
        checks.append((bool(cond), msg))
        if verbose:
            print(("ok    " if cond else "FAIL  ") + msg)

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="redo-selftest-"))
    try:
        bank, state = tmp / "bank", tmp / "state"
        tasks = ["t_always", "t_never", "t_second", "t_tamper", "t_timeout", "t_infra", "t_died", "t_ctxlen"]
        for t in tasks:
            (bank / t / "workspace").mkdir(parents=True)
            (bank / t / "hidden" / "tests").mkdir(parents=True)
            (bank / t / "workspace" / "goal.md").write_text(f"task: {t}\nWrite sol.py with f(x) = x + 1.\n")
            (bank / t / "workspace" / "sol_test.py").write_text(_TOY_TEST)
            (bank / t / "hidden" / "tests" / "sol_test.py").write_text(_TOY_TEST)
            (bank / t / "scorer.py").write_text(_TOY_SCORER)
        stub = tmp / "stub_agent.py"
        stub.write_text(_STUB_AGENT)
        plan = {"schema": SCHEMA, "id": "selftest", "seed": 7, "bank": str(bank), "tasks": tasks, "reps": 1,
                "arms": {"A": {"policy": "single", "attempt_timeout_s": 6},
                         "R3": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 2, "budget_s": 6,
                                "min_attempt_s": 0.5},
                         "R3H": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 2, "budget_s": 6,
                                 "min_attempt_s": 0.5, "hint": "first_failure"}},
                "pair": ["A", "R3"], "attempt_timeout_s": 2, "backoff_scale": 0.0,
                "agent": {"argv": [sys.executable, str(stub), "{prompt}"], "env": {"STUB_STATE": str(state)},
                          "export_cell_env": True, "usage": "pi_json"},
                "providers": [{"name": "stub", "provider": "p", "model": "m", "jobs": 3}],
                "acceptance": {"kind": "workspace_tests", "timeout_s": 30}, "grader": {"timeout_s": 30},
                "analysis": {"alpha": 0.05}}
        pf = tmp / "plan.json"
        write_json(pf, plan)
        root = tmp / "root"
        ns = argparse.Namespace(plan=str(pf), root=str(root), bank=None, only_tasks=None, only_reps=None,
                                max_pairs=None, only_providers=None, allow_uncommitted_plan=True)
        out = open(os.devnull, "w")
        old = sys.stdout
        sys.stdout = out if not verbose else old
        try:
            rc = cmd_run(ns)
        finally:
            sys.stdout = old
        chk(rc == 0, "run 結束碼 0")
        rep = read_json(root / "REPORT.json")
        cell = lambda t, arm: read_json(root / "cells" / t / "r1" / arm / "cell.json")       # noqa: E731
        chk(rep["pairs_complete"] == 8 and rep["pairs_scored"] == 8, "8 對全部完成、沒有 infra_void 對")
        chk(rep["per_arm"]["A"]["pass"] == 3, f"A：只有 t_always、t_infra、t_died 過（實得 {rep['per_arm']['A']['pass']}）")
        chk(rep["per_arm"]["R3"]["pass"] == 5,
            f"R3：t_always、t_second、t_timeout、t_infra、t_died 過（實得 {rep['per_arm']['R3']['pass']}）")
        td = cell("t_died", "A")
        chk(td["voids"] == 1 and td["n_attempts"] == 1 and td["pass"] is True,
            "t_died：寫到一半模型死掉（連線類錯誤）的那一次是 void——A 也會重試，重開不白賺這一題")
        tx = cell("t_ctxlen", "R3")
        chk(tx["voids"] == 0 and tx["n_attempts"] == 3 and tx["pass"] is False
            and rep["per_arm"]["R3"]["final_errors_counted_as_attempts"] == {"400 context length exceeded": 3},
            "t_ctxlen：不是連線類的模型錯誤照算嘗試、計入分母，原文列在報告")
        chk(rep["paired"]["control_only_b"] == 0 and rep["paired"]["treatment_only_c"] == 2, "配對 b=0、c=2")
        chk(abs(rep["paired"]["mcnemar_exact_p_two_sided"] - 0.5) < 1e-9, "精確 McNemar(0,2)=0.5")
        chk(rep["state"] == "UNRESOLVED", "完成但 p≥α ⇒ UNRESOLVED（不是 EFFECTIVE，也不是 INCOMPLETE）")
        chk(cell("t_second", "R3")["n_attempts"] == 2 and cell("t_second", "R3")["delivered_attempt"] == 2,
            "t_second：R3 第 2 次嘗試驗收通過就停、交第 2 次")
        chk(cell("t_never", "R3")["n_attempts"] == 3 and cell("t_never", "R3")["accepted"] is False
            and cell("t_never", "R3")["pass"] is False, "t_never：R3 用完 3 次、沒有驗收通過、照實記沒過")
        tc = cell("t_tamper", "R3")
        chk(tc["accepted"] is False and all(x["tests_tampered"] == ["sol_test.py"] for x in tc["attempts"]),
            "t_tamper：agent 改寫測試檔也過不了驗收（還原原件後才跑），且記下被改的檔")
        to = cell("t_timeout", "A")
        chk(to["attempts"][0]["timed_out"] is True and to["pass"] is False and to["n_attempts"] == 1,
            "t_timeout：A 逾時被殺、只有 1 次嘗試、照實記沒過")
        tr = cell("t_timeout", "R3")
        chk(tr["attempts"][0]["timed_out"] is True and tr["pass"] is True and tr["n_attempts"] == 2,
            "t_timeout：R3 第 1 次逾時被殺（行程群組）、第 2 次過")
        ti = cell("t_infra", "A")
        chk(ti["voids"] == 1 and ti["n_attempts"] == 1 and ti["pass"] is True,
            "t_infra：模型沒起來的那一次記成 void、不算嘗試，重試後照常")
        chk((root / "cells" / "t_infra" / "r1" / "A" / "void_1_attempt_1").is_dir(), "void 的那一次有留檔")
        chk(rep["signal"]["accept_fail"] == 0 and rep["signal"]["reject_pass"] == 0,
            "訊號混淆矩陣：玩具題庫上驗收與評分器完全一致")
        chk(rep["per_arm"]["R3"]["mean_model_calls"] is not None, "模型呼叫數讀得到（pi json 事件流）")
        # 重抽看不到上一次：R3 每一次的提示與 A 逐位元組相同；R3H 第 2 次起多一段 ≤400B 的提示
        p1 = (state / "t_never__r1__R3.prompt1").read_text()
        p3 = (state / "t_never__r1__R3.prompt3").read_text()
        pa = (state / "t_never__r1__A.prompt1").read_text()
        chk(p1 == p3 == pa == DEFAULT_PROMPT, "R3（不給提示）每一次的提示與 A 逐位元組相同")
        h2 = (state / "t_never__r1__R3H.prompt2").read_text()
        extra = h2[len(DEFAULT_PROMPT):]
        chk(h2.startswith(DEFAULT_PROMPT) and 0 < len(extra.encode()) <= HINT_CAP + 8 and "AssertionError" in extra,
            f"R3H 第 2 次的提示＝原提示＋失敗原文（{len(extra.encode())} 位元組）")
        chk(not _KS1_BANNED.search(extra), "KS-1：提示裡沒有責任／懲罰類措辭")
        # 續跑：已完成的格一格都不重跑
        before = {p.name: p.read_text() for p in state.glob("*.n")}
        sys.stdout = out if not verbose else old
        try:
            rc2 = cmd_run(ns)
        finally:
            sys.stdout = old
        chk(rc2 == 0 and before == {p.name: p.read_text() for p in state.glob("*.n")}, "續跑：0 次 agent 呼叫")
        # 計畫漂移：同一個 root 換了計畫內容要拒跑
        plan2 = {**plan, "reps": 2}
        write_json(pf, plan2)
        err = open(os.devnull, "w")
        olde = sys.stderr
        sys.stderr = err
        try:
            rc3 = cmd_run(ns)
        finally:
            sys.stderr = olde
        chk(rc3 == 2, "同一個 root 換了計畫內容 ⇒ 拒跑（結束碼 2）")
        write_json(pf, plan)
        # 沒 commit 的計畫在新的 root 上要拒跑
        ns2 = argparse.Namespace(**{**vars(ns), "root": str(tmp / "root2"), "allow_uncommitted_plan": False})
        sys.stderr = err
        try:
            rc4 = cmd_run(ns2)
        finally:
            sys.stderr = olde
        chk(rc4 == 2, "計畫檔沒 commit ⇒ 拒跑（結束碼 2）")
        # 政策看不到評分器：兩個政策函式的參數裡沒有 grade
        import inspect
        chk("grade" not in inspect.signature(_policy_stop).parameters
            and "grade" not in inspect.getsource(_policy_stop).split('"""')[-1]
            and "grade" not in inspect.getsource(_policy_deliver).split('"""')[-1],
            "政策函式的程式碼裡沒有出現 grade（只讀驗收）")
        # 和套件裡的檢定同式
        try:
            sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
            from vacant_network.research import mcnemar_exact as ref
            chk(all(abs(ref(b, c) - mcnemar_exact(b, c)) < 1e-12 for b in range(0, 9) for c in range(0, 25)),
                "mcnemar_exact 與 vacant_network.research 同值")
        except Exception as e:              # noqa: BLE001
            chk(True, f"（跳過與 vacant_network.research 的對照：{e!r}）")
        # ── command 驗收種類的 selftest ──
        cmd_bank = tmp / "cmd_bank"
        shared_nm = tmp / "shared_nm"
        shared_nm.mkdir()
        (shared_nm / "runner.py").write_text(
            "import pathlib, sys\n"
            "spec = pathlib.Path('toy.spec.js').read_text().strip()\n"
            "sol = pathlib.Path('sol.js').read_text().strip() if pathlib.Path('sol.js').is_file() else ''\n"
            "ok = (sol == spec)\n"
            "print('Tests:       1 passed, 1 total' if ok else 'Tests:       1 failed, 1 total')\n"
            "sys.exit(0 if ok else 1)\n"
        )
        cmd_cfg = {"kind": "command", "cmd": [sys.executable, "node_modules/runner.py"],
                   "timeout_s": 10, "protect": ["*.spec.js"]}
        orig_c = cmd_bank / "c_pass" / "workspace"
        orig_c.mkdir(parents=True)
        (orig_c / "toy.spec.js").write_text("EXPECTED=42\n")
        (orig_c / "sol.js").write_text("STUB\n")
        os.symlink(shared_nm, orig_c / "node_modules")
        # 1) 負控制：stub 失敗，回傳 accept=False、status=ok、parsed passed/run
        acc_stub = acceptance(orig_c, orig_c, cmd_cfg)
        chk(acc_stub["accept"] is False and acc_stub["status"] == "ok"
            and acc_stub["passed"] == 0 and acc_stub["run"] == 1 and acc_stub["tests_tampered"] == [],
            "command 驗收：stub 失敗（accept=False, status=ok, passed=0, run=1）")
        # 2) 正確解答通過，且 node_modules symlink 雖在 SKIP_DIRS 裡仍被正確還原
        ws_ok = tmp / "ws_ok"
        shutil.copytree(orig_c, ws_ok, symlinks=True)
        (ws_ok / "sol.js").write_text("EXPECTED=42\n")
        (ws_ok / "node_modules").unlink()   # 即使 agent 刪掉 node_modules symlink，驗收仍還原 origin 的
        acc_ok = acceptance(orig_c, ws_ok, cmd_cfg)
        chk(acc_ok["accept"] is True and acc_ok["status"] == "ok"
            and acc_ok["passed"] == 1 and acc_ok["run"] == 1 and acc_ok["tests_tampered"] == [],
            "command 驗收：正確解答 exit 0 通過，且 origin 的 node_modules symlink 被還原")
        # 3) 竄改受保護 spec 檔：還原原件後仍失敗，且記下 tests_tampered
        ws_tamp = tmp / "ws_tamp"
        shutil.copytree(orig_c, ws_tamp, symlinks=True)
        (ws_tamp / "toy.spec.js").write_text("STUB\n")
        acc_tamp = acceptance(orig_c, ws_tamp, cmd_cfg)
        chk(acc_tamp["accept"] is False and acc_tamp["tests_tampered"] == ["toy.spec.js"],
            "command 驗收：竄改 *.spec.js 被還原原件擋下並記 tests_tampered")
        # 4) 逾時：status=timeout、accept=False
        acc_to = acceptance(orig_c, orig_c, {"kind": "command", "cmd": [sys.executable, "-c", "import time; time.sleep(30)"],
                                             "timeout_s": 0.5, "protect": ["*.spec.js"]})
        chk(acc_to["accept"] is False and acc_to["status"] == "timeout",
            "command 驗收：逾時回傳 accept=False、status=timeout")
        # 5) 一般指令沒有 Jest 摘要時 passed/run=None
        acc_plain = acceptance(orig_c, orig_c, {"kind": "command", "cmd": [sys.executable, "-c", "print('ok')"],
                                                "timeout_s": 5, "protect": ["*.spec.js"]})
        chk(acc_plain["accept"] is True and acc_plain["passed"] is None and acc_plain["run"] is None,
            "command 驗收：無 Jest 摘要時 passed=None、run=None")
        # 6) 整條 cmd_run 搭配 kind=command + visible_equals_grader=True（A 對 R3）
        cmd_tasks = ["c_second", "c_tamper"]
        for t in cmd_tasks:
            w = cmd_bank / t / "workspace"
            w.mkdir(parents=True)
            (w / "toy.spec.js").write_text("EXPECTED=42\n")
            (w / "sol.js").write_text("STUB\n")
            os.symlink(shared_nm, w / "node_modules")
        cmd_stub = tmp / "cmd_stub.py"
        cmd_stub.write_text(
            "import json, os, pathlib\n"
            "state = pathlib.Path(os.environ['STUB_STATE']); state.mkdir(exist_ok=True)\n"
            "cell = os.environ['REDO_CELL']; task = cell.split('/')[0]\n"
            "cf = state / (cell.replace('/', '__') + '.n')\n"
            "n = int(cf.read_text()) + 1 if cf.exists() else 1; cf.write_text(str(n))\n"
            "print(json.dumps({'type': 'message_end', 'message': {'role': 'assistant', 'usage': {'input': 10, 'output': 5}}}))\n"
            "if task == 'c_second':\n"
            "    pathlib.Path('sol.js').write_text('EXPECTED=42\\n' if n >= 2 else 'WRONG\\n')\n"
            "elif task == 'c_tamper':\n"
            "    pathlib.Path('toy.spec.js').write_text('STUB\\n')\n"
        )
        cmd_plan = {"schema": SCHEMA, "id": "selftest_cmd", "seed": 11, "bank": str(cmd_bank),
                    "tasks": cmd_tasks, "reps": 1,
                    "arms": {"A": {"policy": "single", "attempt_timeout_s": 10},
                             "R3": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                                    "min_attempt_s": 0.5}},
                    "pair": ["A", "R3"], "attempt_timeout_s": 5, "backoff_scale": 0.0,
                    "agent": {"argv": [sys.executable, str(cmd_stub), "{prompt}"],
                              "env": {"STUB_STATE": str(tmp / "cmd_state")},
                              "export_cell_env": True, "usage": "pi_json"},
                    "providers": [{"name": "stub", "provider": "p", "model": "m", "jobs": 2}],
                    "acceptance": cmd_cfg,
                    "grader": {"timeout_s": 30, "visible_equals_grader": True},
                    "analysis": {"alpha": 0.05}}
        cmd_pf = tmp / "cmd_plan.json"
        write_json(cmd_pf, cmd_plan)
        cmd_root = tmp / "cmd_root"
        cmd_ns = argparse.Namespace(plan=str(cmd_pf), root=str(cmd_root), bank=None, only_tasks=None,
                                    only_reps=None, max_pairs=None, only_providers=None, allow_uncommitted_plan=True)
        sys.stdout = out if not verbose else old
        try:
            rc_cmd = cmd_run(cmd_ns)
        finally:
            sys.stdout = old
        cmd_rep = read_json(cmd_root / "REPORT.json")
        ccell = lambda t, arm: read_json(cmd_root / "cells" / t / "r1" / arm / "cell.json")    # noqa: E731
        chk(rc_cmd == 0 and cmd_rep["pairs_scored"] == 2
            and cmd_rep["per_arm"]["A"]["pass"] == 0 and cmd_rep["per_arm"]["R3"]["pass"] == 1
            and ccell("c_second", "R3")["grader_kind"] == "visible_tests_pristine"
            and ccell("c_tamper", "R3")["accepted"] is False
            and all(x["tests_tampered"] == ["toy.spec.js"] for x in ccell("c_tamper", "R3")["attempts"]),
            "command 驗收端到端（visible_equals_grader=True）：R3 第 2 次過、竄改者被擋下")
        # --only-providers（2026-11-25）：兩台機器的佇列各由一份 runner 跑、同一個 root；同一台不能有兩份
        ah = read_json(root / "cells" / "t_second" / "r1" / "R3H" / "attempt_2" / "attempt.json")
        chk(isinstance(ah.get("hint_text"), str) and ah["hint_text"].startswith(HINT_HEAD)
            and ah["hint_bytes"] == len(ah["hint_text"].encode()), "attempt.json 記下送出的 hint 原文（RF 截斷率用）")
        mp = {**plan, "id": "selftest_mp", "tasks": ["t_always", "t_second", "t_never", "t_tamper"],
              "arms": {"A": plan["arms"]["A"], "R3": plan["arms"]["R3"]},
              "providers": [{"name": "s1", "provider": "p", "model": "m", "jobs": 1},
                            {"name": "s2", "provider": "p", "model": "m", "jobs": 1}]}
        mp_pf = tmp / "mp_plan.json"
        write_json(mp_pf, mp)
        mp_root = tmp / "mp_root"
        mk = lambda prov: argparse.Namespace(plan=str(mp_pf), root=str(mp_root), bank=None, only_tasks=None,  # noqa: E731
                                             only_reps=None, max_pairs=None, only_providers=prov,
                                             allow_uncommitted_plan=True)
        sys.stdout = out if not verbose else old
        try:
            rc_bad = cmd_run(mk("nope"))
            mp_root.mkdir(parents=True, exist_ok=True)
            held = open(mp_root / ".lock-s1", "w")
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            rc_busy = cmd_run(mk("s1"))
            rc_s2 = cmd_run(mk("s2"))
            fcntl.flock(held, fcntl.LOCK_UN)
            held.close()
            provs_after_s2 = {read_json(f)["provider"] for f in (mp_root / "cells").glob("*/r*/*/cell.json")}
            rc_s1 = cmd_run(mk("s1"))
        finally:
            sys.stdout = old
        mp_cells = [read_json(f) for f in (mp_root / "cells").glob("*/r*/*/cell.json")]
        by_pair = {}
        for c in mp_cells:
            by_pair.setdefault((c["task"], c["rep"]), set()).add(c["provider"])
        chk(rc_bad == 2, "--only-providers 給了計畫沒有的機器 ⇒ 拒絕啟動")
        chk(rc_busy == 2, "同一台機器已經有 runner 在跑（鎖被拿著）⇒ 拒絕啟動")
        chk(rc_s2 == 0 and provs_after_s2 == {"s2"}, "只跑 s2：只產生 s2 的格")
        chk(rc_s1 == 0 and len(mp_cells) == 8 and all(len(v) == 1 for v in by_pair.values())
            and read_json(mp_root / "REPORT.json")["pairs_complete"] == 4,
            "再跑 s1：同一個 root 補齊 4 對 8 格，每一對兩臂在同一台")
        # ── controller 政策（規則 1–6）＋ arm B（hint=failing_tests）的 selftest ──
        ctl_bank = tmp / "ctl_bank"
        ctl_state = tmp / "ctl_state"
        ctl_test_4 = (
            "import unittest\nfrom sol import f\n\nclass T(unittest.TestCase):\n"
            "    def test_1(self):\n        self.assertEqual(f(1), 1)\n"
            "    def test_2(self):\n        self.assertEqual(f(2), 2)\n"
            "    def test_3(self):\n        self.assertEqual(f(3), 3)\n"
            "    def test_4(self):\n        self.assertEqual(f(4), 4)\n"
        )
        ctl_tasks = ["c_r1_pass", "c_r2_budget", "c_r3_restore", "c_r4_stuck", "c_r5_repair", "c_r6_continue"]
        for t in ctl_tasks:
            (ctl_bank / t / "workspace").mkdir(parents=True)
            (ctl_bank / t / "hidden" / "tests").mkdir(parents=True)
            (ctl_bank / t / "workspace" / "goal.md").write_text(f"task: {t}\n")
            (ctl_bank / t / "workspace" / "sol_test.py").write_text(ctl_test_4)
            (ctl_bank / t / "hidden" / "tests" / "sol_test.py").write_text(ctl_test_4)
            (ctl_bank / t / "scorer.py").write_text(_TOY_SCORER)
        ctl_stub = tmp / "ctl_stub.py"
        ctl_stub.write_text(
            "import json, os, pathlib, sys\n"
            "state = pathlib.Path(os.environ['STUB_STATE']); state.mkdir(exist_ok=True)\n"
            "cell = os.environ['REDO_CELL']; task = cell.split('/')[0]\n"
            "cf = state / (cell.replace('/', '__') + '.n')\n"
            "n = int(cf.read_text()) + 1 if cf.exists() else 1; cf.write_text(str(n))\n"
            "(state / (cell.replace('/', '__') + f'.prompt{n}')).write_text(sys.argv[1])\n"
            "mk = pathlib.Path('marker.txt')\n"
            "(state / (cell.replace('/', '__') + f'.marker{n}')).write_text(mk.read_text() if mk.is_file() else '<NONE>')\n"
            "print(json.dumps({'type': 'message_end', 'message': {'role': 'assistant', 'usage': {'input': 50, 'output': 20}}}))\n"
            "def w(k):\n"
            "    pathlib.Path('sol.py').write_text(f'def f(x):\\n    return x if x <= {k} else -1\\n')\n"
            "if task == 'c_r1_pass':\n"
            "    w(4)\n"
            "elif task == 'c_r2_budget':\n"
            "    w({1: 2, 2: 3, 3: 1}[n]); mk.write_text(f'b{n}')\n"
            "elif task == 'c_r3_restore':\n"
            "    if n == 1:\n"
            "        w(2); mk.write_text('from_att1')\n"
            "    elif n == 2:\n"
            "        w(1); mk.write_text('from_att2')\n"
            "    else:\n"
            "        w(4)\n"
            "elif task == 'c_r4_stuck':\n"
            "    if n in (1, 2):\n"
            "        w(1); mk.write_text(f'stuck{n}')\n"
            "    else:\n"
            "        w(4)\n"
            "elif task == 'c_r5_repair':\n"
            "    if n == 1:\n"
            "        w(3); mk.write_text('keep_repair')\n"
            "    else:\n"
            "        w(4)\n"
            "elif task == 'c_r6_continue':\n"
            "    if n == 1:\n"
            "        w(1); mk.write_text('keep_continue')\n"
            "    else:\n"
            "        w(4)\n"
        )
        ctl_plan = {
            "schema": SCHEMA, "id": "selftest_ctl", "seed": 20261127, "bank": str(ctl_bank),
            "tasks": ctl_tasks, "reps": 1,
            "arms": {
                "B": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                      "min_attempt_s": 0.5, "hint": "failing_tests"},
                "C": {"policy": "controller", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                      "min_attempt_s": 0.5},
            },
            "pair": ["B", "C"], "attempt_timeout_s": 5, "backoff_scale": 0.0,
            "agent": {"argv": [sys.executable, str(ctl_stub), "{prompt}"],
                      "env": {"STUB_STATE": str(ctl_state)},
                      "export_cell_env": True, "usage": "pi_json"},
            "providers": [{"name": "stub", "provider": "p", "model": "m", "jobs": 2}],
            "acceptance": {"kind": "workspace_tests", "timeout_s": 30},
            "grader": {"timeout_s": 30},
            "analysis": {"alpha": 0.05},
        }
        ctl_pf = tmp / "ctl_plan.json"
        write_json(ctl_pf, ctl_plan)
        ctl_root = tmp / "ctl_root"
        ctl_ns = argparse.Namespace(plan=str(ctl_pf), root=str(ctl_root), bank=None, only_tasks=None,
                                    only_reps=None, max_pairs=None, only_providers=None, allow_uncommitted_plan=True)
        sys.stdout = out if not verbose else old
        try:
            rc_ctl = cmd_run(ctl_ns)
        finally:
            sys.stdout = old
        ctl_mod, _, _ = _import_controller()
        cc = lambda t, arm: read_json(ctl_root / "cells" / t / "r1" / arm / "cell.json")  # noqa: E731
        c1, c2, c3, c4, c5, c6 = (cc(t, "C") for t in ctl_tasks)
        chk(rc_ctl == 0, "controller selftest 結束碼 0")
        chk(c1["n_attempts"] == 1 and c1["attempts"][0]["rule"] == 1 and c1["attempts"][0]["action"] == "stop_success"
            and c1["pass"] is True, "controller 規則 1（stop_success）：第 1 次全過即停")
        chk(c2["n_attempts"] == 3 and [a["rule"] for a in c2["attempts"]] == [6, 5, 2]
            and c2["attempts"][2]["action"] == "deliver_best_budget" and c2["delivered_attempt"] == 2,
            "controller 規則 2（deliver_best_budget）：預算耗盡交最佳版（attempt 2）")
        chk([a["rule"] for a in c3["attempts"]] == [6, 3, 1]
            and c3["attempts"][1]["action"] == "restore_best"
            and (ctl_state / "c_r3_restore__r1__C.marker3").read_text() == "from_att1"
            and ctl_mod.ACTION_LINE_RESTORE_BEST in (ctl_state / "c_r3_restore__r1__C.prompt3").read_text(),
            "controller 規則 3（restore_best）：變差時回到最佳快照（marker=from_att1）與最佳回饋")
        chk([a["rule"] for a in c4["attempts"]] == [6, 4, 1]
            and c4["attempts"][1]["action"] == "restart_fresh"
            and (ctl_state / "c_r4_stuck__r1__C.marker3").read_text() == "<NONE>"
            and ctl_mod.ACTION_LINE_RESTART_FRESH in (ctl_state / "c_r4_stuck__r1__C.prompt3").read_text(),
            "controller 規則 4（restart_fresh）：連續 2 次同簽章無進展 ⇒ 從原件重開（無 marker）")
        chk([a["rule"] for a in c5["attempts"]] == [5, 1]
            and c5["attempts"][0]["action"] == "repair"
            and (ctl_state / "c_r5_repair__r1__C.marker2").read_text() == "keep_repair"
            and ctl_mod.ACTION_LINE_REPAIR in (ctl_state / "c_r5_repair__r1__C.prompt2").read_text(),
            "controller 規則 5（repair）：≥70%（3/4）保留工作區並修復")
        chk([a["rule"] for a in c6["attempts"]] == [6, 1]
            and c6["attempts"][0]["action"] == "continue"
            and (ctl_state / "c_r6_continue__r1__C.marker2").read_text() == "keep_continue"
            and ctl_mod.ACTION_LINE_CONTINUE in (ctl_state / "c_r6_continue__r1__C.prompt2").read_text(),
            "controller 規則 6（continue）：<70% 保留工作區續做")
        # 驗證每一格 C 的簽章鏈都能驗過並重建決策歷史
        chains_ok = True
        for t in ctl_tasks:
            cp = cc(t, "C").get("chain_path")
            if not cp or not pathlib.Path(cp).is_file():
                chains_ok = False
                break
            hist = ctl_mod.reconstruct(cp, emit=False)
            if len(hist) != cc(t, "C")["n_attempts"]:
                chains_ok = False
                break
        chk(chains_ok, "controller 每格皆有合法簽章鏈且 reconstruct() 驗過並還原全部決策")
        # 驗證 arm B（hint=failing_tests）：用共用回饋產生器（≤400B、KS-1 乾淨）且從原件重開
        b_prompt2 = (ctl_state / "c_r5_repair__r1__B.prompt2").read_text()
        b_extra = b_prompt2[len(DEFAULT_PROMPT) + len("\n\n---\n"):]
        chk(b_prompt2.startswith(DEFAULT_PROMPT) and "Failing tests:" in b_extra
            and len(b_extra.encode("utf-8")) <= ctl_mod.FEEDBACK_MAX_BYTES
            and not _KS1_BANNED.search(b_extra)
            and (ctl_state / "c_r5_repair__r1__B.marker2").read_text() == "<NONE>",
            f"arm B（hint=failing_tests）：共用回饋 ≤400B（{len(b_extra.encode())}B）且從原件重開")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [m for ok_, m in checks if not ok_]
    print(f"VERDICT: {'REDO_SELFTEST_OK' if not bad else 'REDO_SELFTEST_FAIL'}（{len(checks) - len(bad)}/{len(checks)}）")
    return 0 if not bad else 1


HARNESS_SHA = sha256_bytes(pathlib.Path(__file__).read_bytes())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("selftest"); s.add_argument("--quiet", action="store_true")
    for name in ("preflight", "run"):
        s = sub.add_parser(name)
        s.add_argument("--plan", required=True)
        s.add_argument("--bank")
        s.add_argument("--allow-uncommitted-plan", action="store_true")
        if name == "run":
            s.add_argument("--root", required=True)
            s.add_argument("--only-tasks", help="逗號分隔；只是篩選，不改計畫")
            s.add_argument("--only-reps", help="逗號分隔，例如 1 或 1,2")
            s.add_argument("--max-pairs", type=int)
            s.add_argument("--only-providers", help="逗號分隔的機器名；只是篩選，不改計畫（一對的機器由計畫決定）")
    for name in ("report", "status"):
        s = sub.add_parser(name); s.add_argument("--root", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return selftest(verbose=not a.quiet)
    return {"preflight": cmd_preflight, "run": cmd_run, "report": cmd_report, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
