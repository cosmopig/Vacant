"""G3 發射管線（vq-1zf；g3gate 宣告「本輪未接線」的發射側那一半）。

g3gate（`vacant_network/reqloop/g3gate.py`）只核「發射前置」：選題/凍結/預算/核准
四門＋`--fire` fail-closed。核准後真正要發射時，本模組把三臂
（native_pi / reqlist_only / full_rloop）×4 凍結未見題＝12 格跑起來。

復用（不重發明，紅線「不得重造 contract/retry/receipt」）：
- g3gate: G3Plan.load / verify_frozen / check_budget / approval_gate（同義 RC 碼）
- extract: extract_requirements（需求清單；extractor 與作答模型分離）
- requirements: RequirementSet（渲染進 prompt 的需求清單）
- glm CLI（11/07 唯一模型入口）：GlmChannel 包 subprocess；成本從
  state/vibe_calls.jsonl 的 raw usage 讀（input/output/total_tokens）。

紅線（對齊 manifest.leak_guard，本檔不得弱化）：
- 不讀 /srv/eval/hidden/ 與 scorer.py 內容；hidden_after 一律 UNKNOWN
  （打分流給 /srv/vlab 既有 scorer，本管線不打本地分）
- 成本缺值＝UNKNOWN（None）絕不填 0；撞日額度即停、不得重試
- 模型呼叫唯一入口＝glm CLI；本檔不持金鑰、不反向代理、不轉額度
- 不寫任何任務檔到 /srv/vlab/queue/
- 發射授權：人類核准文件（approved=true、epic=vq-1zf、by=核准者）；
  無核准→RC 2、0 模型呼叫（與 g3gate 同 fail-closed）。

本模組 0 模型呼叫：通道可注入（測試用假通道）；GlmChannel 只在真發射時使用。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

from vacant_network.reqloop import extract as _extract
from vacant_network.reqloop import g3gate
from vacant_network.reqloop.requirements import RequirementSet

SCHEMA_RESULT = "vacant.reqloop.g3.result/1"

# 與 g3gate 同義（發射側不自訂第二套碼）：
RC_OK = g3gate.RC_OK
RC_PLAN = g3gate.RC_PLAN
RC_NOT_APPROVED = g3gate.RC_NOT_APPROVED

HIDDEN_AFTER_UNKNOWN = "UNKNOWN"

DEFAULT_ANSWER_MODEL = "deepseek41"     # 作答模型（glm CLI 別名）
DEFAULT_EXTRACT_MODEL = "glm53"         # 擷取模型（必須不同於作答模型）
DATA_PREVIEW_BYTES = 64 * 1024          # 進 prompt 的單資料檔上限（超出截斷並如實標註）

REPO = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO / "ops" / "reqloop" / "g3_gate" / "manifest.json"
DEFAULT_STATE_DIR = pathlib.Path(os.environ.get("VACANT_OPS_STATE", str(pathlib.Path.home() / "dev" / "ops" / "state")))

# 三臂內容契約（逐字對齊 manifest.arm_defs，2026-11-08 凍結）：
#   native_pi    「再檢查修正一次」（一輪可見回饋），無需求清單、無 R-loop 修復循環
#   reqlist_only 作答模型另得 extract.py 擷取的需求清單；無 localized 修復循環、無全條目重驗
#   full_rloop   自動擷取需求＋localized 修復＋重驗所有必要條目
ARM_SPECS: dict[str, dict] = {
    "native_pi": {
        "requirement_list": False,
        "max_rounds": 1,
        "localized_repair": False,
        "reverify_all": False,
        "instruction": (
            "再檢查修正一次：先作答，然後對自己的草稿做一輪可見回饋檢查並修正；"
            "沒有需求清單、沒有修復循環。只依任務與資料作答。"
        ),
    },
    "reqlist_only": {
        "requirement_list": True,
        "max_rounds": 1,
        "localized_repair": False,
        "reverify_all": False,
        "instruction": (
            "你另得一份由 extract.py 擷取的需求清單（見下）。依需求清單與任務作答；"
            "沒有 localized 修復循環、沒有全條目重驗。"
        ),
    },
    "full_rloop": {
        "requirement_list": True,
        "max_rounds": 2,
        "localized_repair": True,
        "reverify_all": True,
        "instruction": (
            "完整 R-loop：依需求清單作答。若草稿未滿足清單，只修未滿足的條目、"
            "已滿足部分保持不變；輸出前重驗所有必要條目。"
        ),
    },
}

_ANSWER_ITEM_RE = re.compile(r"@([A-Za-z0-9_]+)\[[^\]]*\]")


class G3QuotaError(RuntimeError):
    """撞日額度（或 glm rc=3）。停、不重試（quota_fail_closed）。"""


class G3CallError(RuntimeError):
    """單格模型呼叫失敗（glm rc=4 等）。該格記 error、不重試、管線繼續。"""


class G3NotApproved(RuntimeError):
    """核准門不過（RC 2 語義；0 模型呼叫）。"""


# ── 用量與通道 ─────────────────────────────────────────────────────────


class RoundUsage:
    """單輪 raw usage。tokens 缺失＝None（UNKNOWN，絕不填 0）。"""

    __slots__ = ("calls", "tokens", "wall_ms")

    def __init__(self, calls: int, tokens: int | None, wall_ms: int | None) -> None:
        self.calls = int(calls)
        self.tokens = tokens
        self.wall_ms = wall_ms

    def to_dict(self) -> dict:
        return {"calls": self.calls, "tokens": self.tokens, "wall_ms": self.wall_ms}


class Channel:
    """模型通道協議：call() → (text, RoundUsage)。可注入（測試假通道、真 GlmChannel）。"""

    def call(self, *, prompt: str, model: str, purpose: str, timeout_s: float) -> tuple[str, RoundUsage]:
        raise NotImplementedError


def _tail_usage(path: pathlib.Path, n_lines: int) -> list[dict]:
    """讀 vibe_calls.jsonl 末 n_lines 行（該檔由 glm CLI 每次呼叫追加一行）。"""
    if n_lines <= 0 or not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out = []
    for ln in lines[-n_lines:]:
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            out.append({})
    return out


class GlmChannel(Channel):
    """真通道：唯一入口＝glm CLI（11/07）；成本從 state/vibe_calls.jsonl raw usage 讀。

    退出碼：0 成功、3 今日預算用完（→ G3QuotaError，停不重試）、4/其他失敗
    （→ G3CallError，該格 error、不重試）。空暫存目錄、不給工具、單回合、
    每天 ≤200 萬 token 的限制都在 glm 指令內，本檔不持有金鑰、不繞過。
    """

    def __init__(self, glm_bin: str = "glm", state_dir: str | pathlib.Path | None = None) -> None:
        self.glm_bin = glm_bin
        self.state_dir = pathlib.Path(state_dir) if state_dir is not None else DEFAULT_STATE_DIR
        self._calls_log = self.state_dir / "vibe_calls.jsonl"

    def call(self, *, prompt: str, model: str, purpose: str, timeout_s: float) -> tuple[str, RoundUsage]:
        before_lines = self._calls_log.count_lines() if self._calls_log.is_file() else 0
        fd, prompt_path = tempfile.mkstemp(prefix="vacant_g3_", suffix=".md")
        t0 = time.monotonic()
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(prompt)
            proc = subprocess.run(
                [self.glm_bin, "--model", model, "--purpose", purpose,
                 "--prompt-file", prompt_path, "--time-limit", str(int(timeout_s))],
                capture_output=True, text=True, timeout=timeout_s + 30,
            )
        except subprocess.TimeoutExpired as e:
            raise G3CallError(f"glm timed out after {timeout_s + 30:.0f}s") from e
        finally:
            try:
                os.unlink(prompt_path)
            except OSError:
                pass
        wall_ms = int((time.monotonic() - t0) * 1000)
        if proc.returncode == 3:
            raise G3QuotaError("glm rc=3：今日預算用完——停、不重試")
        if proc.returncode != 0:
            lines = [ln for ln in (proc.stderr or proc.stdout or "").strip().splitlines() if ln.strip()]
            raise G3CallError(f"glm rc={proc.returncode}: {lines[-1][:200] if lines else 'no output'}")
        new = _tail_usage(self._calls_log, self._calls_log.count_lines() - before_lines
                          if self._calls_log.is_file() else 0)
        if new:
            tokens = None
            for rec in new:
                try:
                    v = int(rec.get("total_tokens"))
                except (TypeError, ValueError):
                    v = None
                if v is None:
                    tokens = None  # 任一筆缺值 → UNKNOWN（不填 0）
                    break
                tokens = (tokens or 0) + v
        else:
            tokens = None  # raw usage 無新增行 → UNKNOWN
        return proc.stdout, RoundUsage(calls=1, tokens=tokens, wall_ms=wall_ms)


class QuotaGuard:
    """日額度 fail-closed 護欄（11/07「撞 2M/日額度即停、不得重試」）：
    呼叫前已知 tokens ≥ cap → 直接 G3QuotaError（0 呼叫）；呼叫後累計。
    缺值 tokens 不累計（UNKNOWN 不假裝 0）。
    """

    def __init__(self, channel: Channel, daily_token_cap: int) -> None:
        self.channel = channel
        self.cap = int(daily_token_cap)
        self.known_tokens = 0
        self.total_calls = 0

    def call(self, *, prompt: str, model: str, purpose: str, timeout_s: float) -> tuple[str, RoundUsage]:
        if self.known_tokens >= self.cap:
            raise G3QuotaError(f"已知 tokens {self.known_tokens} ≥ 日額度 {self.cap}——停、不重試")
        text, usage = self.channel.call(prompt=prompt, model=model, purpose=purpose, timeout_s=timeout_s)
        if usage.tokens is not None:
            self.known_tokens += usage.tokens
        self.total_calls += usage.calls
        return text, usage


class _ChannelExtractClient:
    """把 Channel 適配成 extract.ExtractClient（complete(prompt)→str）。

    G3QuotaError 必須穿透（管線級停發信號，絕不降級成「擷取失敗＝沒有需求」）；
    G3CallError → ExtractError（extract_requirements fail-closed 記為空集合）。
    """

    def __init__(self, guard: QuotaGuard, model: str, purpose: str, timeout_s: float,
                 ledger: list[RoundUsage]) -> None:
        self.guard = guard
        self.model = model
        self.purpose = purpose
        self.timeout_s = timeout_s
        self.ledger = ledger

    def complete(self, prompt: str) -> str:
        try:
            text, usage = self.guard.call(prompt=prompt, model=self.model,
                                          purpose=self.purpose, timeout_s=self.timeout_s)
        except G3QuotaError:
            raise
        except G3CallError as e:
            raise _extract.ExtractError(f"glm 擷取呼叫失敗：{e}") from e
        self.ledger.append(usage)
        return text


# ── 任務輸入與 prompt（決定性；無 hidden、無 scorer）──────────────────


def _read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def _data_preview(data: pathlib.Path) -> str:
    raw = data.read_bytes()
    if len(raw) <= DATA_PREVIEW_BYTES:
        return raw.decode("utf-8", errors="replace")
    head = raw[:DATA_PREVIEW_BYTES].decode("utf-8", errors="replace")
    return head + f"\n[資料截斷：共 {len(raw)} bytes，以上為前 {DATA_PREVIEW_BYTES} bytes]"


def load_task_inputs(task_dir: pathlib.Path) -> dict:
    """讀凍結任務輸入（instruction.txt＋workspace/goal.md＋contract.md＋data/*）。

    只讀 repo 內凍結副本；不讀 /srv/eval/hidden/、不讀 scorer.py。
    """
    instruction = (task_dir / "instruction.txt")
    goal = (task_dir / "workspace" / "goal.md")
    contract = (task_dir / "workspace" / "contract.md")
    for p in (instruction, goal, contract):
        if not p.is_file():
            raise FileNotFoundError(f"任務輸入缺檔：{p}")
    data_dir = task_dir / "workspace" / "data"
    datas = sorted(data_dir.glob("*")) if data_dir.is_dir() else []
    datas = [d for d in datas if d.is_file()]
    return {
        "instruction": _read(instruction),
        "goal": _read(goal),
        "contract": _read(contract),
        "data": {d.name: _data_preview(d) for d in datas},
    }


def input_sha256(task_dir: pathlib.Path, files: dict[str, str]) -> str:
    """按 manifest 凍結檔清單重算輸入指纹（檔案順序不敏感；逐檔 sha 再總和）。"""
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode("utf-8"))
        h.update(files[rel].encode("utf-8"))
    return h.hexdigest()


def required_answer_names(contract: str) -> list[str]:
    """從可見 contract.md 解析必要答案項名（@name[...]）。"""
    return sorted(set(_ANSWER_ITEM_RE.findall(contract)))


def render_requirement_list(req_set: RequirementSet | None) -> str:
    """需求清單 → 決定性文字塊（進 prompt；只含 quote/deliverable/狀態）。"""
    if req_set is None or not req_set.items:
        return "（需求清單：擷取失敗或無條目——按無清單處理，不得自行編造需求。）"
    lines = []
    for it in req_set.items:
        status = "unverified" if it.unverified else it.kind
        req = "required" if it.required else "optional"
        lines.append(f"- [{it.id}] ({req}, {status}) {it.quote}")
        lines.append(f"    deliverable: {it.deliverable}")
    return "\n".join(lines)


def build_cell_prompt(task: dict, spec: dict, *, req_list_text: str = "",
                      round_no: int = 1, missing: tuple[str, ...] = ()) -> str:
    """決定性 prompt：任務＋資料＋（臂）需求清單＋（臂）指令＋（第 2 輪）缺口證據。

    紅線：不含 /srv/eval/hidden/、scorer.py 或任何隱藏內容；缺口證據只含
    可見 contract 的答案項名與上一稿原文（無測試資料）。
    """
    data_block = ""
    for name in sorted(task["data"]):
        data_block += f"--- data/{name} ---\n{task['data'][name]}\n"
    parts = [
        "你是作答模型。只依下方任務、資料與（如有）需求清單完成任務，輸出最終答案。",
        "【任務】",
        task["instruction"].strip(),
        "--- goal.md ---",
        task["goal"].strip(),
        "--- contract.md ---",
        task["contract"].strip(),
        "【資料】",
        data_block.strip(),
    ]
    if spec["requirement_list"]:
        parts += ["【需求清單（extract.py 擷取）】", req_list_text or render_requirement_list(None)]
    parts += ["【本輪要求】", spec["instruction"]]
    if round_no >= 2 and missing:
        parts += [
            "【上一稿與缺口】以下必要答案項在上一稿缺失：",
            "、".join(f"@{n}[...]" for n in missing),
            "只修未滿足的條目、已滿足部分保持不變；輸出前重驗所有必要條目。",
        ]
    parts += ["【輸出】", "只輸出最終答案項（contract 格式），每項一行，不要多餘說明。"]
    return "\n\n".join(parts) + "\n"


# ── 結果與總量（缺值 UNKNOWN 絕不填 0）────────────────────────────────


def _sum_tokens(usages: list[RoundUsage]) -> int | None:
    """任一筆缺 tokens → None；零筆 → None（不報 0 成本）。"""
    if not usages:
        return None
    total = 0
    for u in usages:
        if u.tokens is None:
            return None
        total += u.tokens
    return total


def _sum_calls(usages: list[RoundUsage]) -> int:
    return sum(u.calls for u in usages)


def _cell_usage(cell: dict) -> list[RoundUsage]:
    return [u for r in cell["rounds"] for u in r["usages"]]


def result_totals(result: dict) -> dict:
    """總量：cells 各輪＋各 task 擷取；tokens 缺值 → None（UNKNOWN 不填 0）。"""
    cell_usages = [u for c in result["cells"] for u in _cell_usage(c)]
    ext_usages = [u for t in result["tasks"] for u in t["extract_usages"]]
    tokens = _sum_tokens(cell_usages + ext_usages)
    return {
        "cells": len(result["cells"]),
        "cells_run": sum(1 for c in result["cells"] if c["status"] != "not_run"),
        "model_calls": _sum_calls(cell_usages + ext_usages),
        "tokens": tokens,                      # None = UNKNOWN
        "tokens_missing": tokens is None,
    }


def write_result(out_root: pathlib.Path, result: dict) -> pathlib.Path:
    out_root = pathlib.Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    p = out_root / "g3_result.json"
    p.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return p


# ── 發射主體（零模型呼叫：通道注入）──────────────────────────────────


def run_g3(plan: g3gate.G3Plan, base: pathlib.Path, out_root: pathlib.Path, *,
           channel: Channel, approval: dict,
           answer_model: str = DEFAULT_ANSWER_MODEL,
           extract_model: str = DEFAULT_EXTRACT_MODEL) -> dict:
    """三臂×N 格發射主體。返回結果 dict（write_result 落 g3_result.json）。

    門（順序即優先級）：
      1) verify_frozen＋check_budget（完整性先於核准判定，篡改→G3Plan 層 ValueError）
      2) approval_gate（不過→G3NotApproved，0 模型呼叫）
      3) 每 task：需求清單擷取一次（供 reqlist_only/full_rloop 兩臂共用＝同資料）
      4) 每格逐輪：QuotaGuard 撞額→停、不重試；G3CallError→該格 error、管線繼續
    """
    base = pathlib.Path(base)
    out_root = pathlib.Path(out_root)
    plan.verify_frozen(base)
    g3gate.check_budget(plan)
    ok, why = g3gate.approval_gate(approval)
    if not ok:
        raise G3NotApproved(why)

    cap = int(plan.budget["daily_token_cap"])
    tpr = int(plan.budget["timeout_s_per_round"])
    guard = QuotaGuard(channel, cap)
    arm_order = tuple(plan.arms)
    tasks = [t["task_id"] for t in plan.tasks]

    result: dict = {
        "schema": SCHEMA_RESULT,
        "fired_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ticket": plan.ticket,
        "approval": {"approved": bool(approval.get("approved")),
                     "epic": approval.get("epic"), "by": approval.get("by")},
        "answer_model": answer_model,
        "extract_model": extract_model,
        "arms": list(arm_order),
        "budget": dict(plan.budget),
        "tasks": [],
        "cells": [],
        "stop_reason": None,
        "totals": None,
    }

    needs_list = any(ARM_SPECS[a]["requirement_list"] for a in arm_order)
    stopped = False

    for t in plan.tasks:
        tid = t["task_id"]
        tdir = base / "tasks" / tid
        inputs = load_task_inputs(tdir)
        trec: dict = {
            "task_id": tid,
            "input_sha256": input_sha256(tdir, t["files"]),
            "required_answer_names": required_answer_names(inputs["contract"]),
            "extract_error": None,
            "n_requirements": 0,
            "extract_usages": [],
        }
        req_set = None
        if needs_list and not stopped:
            ledger: list[RoundUsage] = []
            client = _ChannelExtractClient(guard, extract_model,
                                           purpose=f"G3 {tid} 擷取需求",
                                           timeout_s=tpr, ledger=ledger)
            try:
                req_set, report = _extract.extract_requirements(
                    user_text=inputs["goal"], client=client, task_id=tid)
            except G3QuotaError:
                stopped = True
                result["stop_reason"] = "quota"
                trec["extract_usages"] = ledger
                result["tasks"].append(trec)
                _finalize_and_write(result, guard, out_root)
                return result
            trec["extract_error"] = report.extract_error or report.parse_error
            trec["n_requirements"] = len(req_set.items)
            trec["extract_usages"] = ledger
        result["tasks"].append(trec)

        for arm in arm_order:
            spec = ARM_SPECS[arm]
            cell: dict = {
                "task": tid, "arm": arm, "status": "not_run",
                "requirement_list": bool(spec["requirement_list"]),
                "input_sha256": trec["input_sha256"],
                "rounds": [], "answer": None, "answer_sha256": None,
                "hidden_after": HIDDEN_AFTER_UNKNOWN, "error": None,
            }
            if stopped:
                result["cells"].append(cell)
                continue
            req_list_text = render_requirement_list(req_set) if spec["requirement_list"] else ""
            needed = trec["required_answer_names"]
            missing: tuple[str, ...] = ()
            for round_no in range(1, spec["max_rounds"] + 1):
                if round_no > 1 and not missing:
                    break  # full_rloop：上一稿已覆蓋必要答案項→不花第 2 輪（無額外呼叫）
                prompt = build_cell_prompt(inputs, spec, req_list_text=req_list_text,
                                           round_no=round_no, missing=missing)
                rec: dict = {"round": round_no, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                             "usages": [], "error": None}
                try:
                    text, usage = guard.call(prompt=prompt, model=answer_model,
                                             purpose=f"G3 {tid}/{arm} r{round_no}",
                                             timeout_s=tpr)
                except G3QuotaError as e:
                    rec["error"] = f"quota: {e}"
                    cell["rounds"].append(rec)
                    cell["status"] = "partial_quota" if cell["answer"] is not None else "not_run"
                    stopped = True
                    result["stop_reason"] = "quota"
                    result["cells"].append(cell)
                    _finalize_and_write(result, guard, out_root)
                    return result
                except G3CallError as e:
                    rec["error"] = str(e)
                    cell["rounds"].append(rec)
                    cell["status"] = "error"
                    cell["error"] = str(e)
                    result["cells"].append(cell)
                    break
                cell["rounds"].append(rec)
                rec["usages"].append(usage)
                cell["answer"] = text
                cell["answer_sha256"] = hashlib.sha256(text.encode()).hexdigest()
                # full_rloop：第 2 輪僅在必要答案項缺失時才花（localized 修復）
                missing = tuple(n for n in needed
                                if not re.search(rf"@{re.escape(n)}\[[^\]]*\]", text))
            if cell["status"] == "not_run":
                cell["status"] = "ok"  # 至少一輪成功且無錯誤＝完成（初始值即 not_run）
            result["cells"].append(cell)

    _finalize_and_write(result, guard, out_root)
    return result


def _finalize_and_write(result: dict, guard: QuotaGuard, out_root: pathlib.Path) -> None:
    result["totals"] = result_totals(result)
    result["quota"] = {"known_tokens": guard.known_tokens, "daily_token_cap": guard.cap,
                       "total_calls": guard.total_calls}
    write_result(out_root, result)


# ── CLI ───────────────────────────────────────────────────────────────


def _print_cell_lines(result: dict) -> None:
    for c in result["cells"]:
        toks = _sum_tokens(_cell_usage(c))
        toks_s = "UNKNOWN" if toks is None else str(toks)
        print(f"CELL {c['task']}/{c['arm']}: status={c['status']} "
              f"rounds={len(c['rounds'])} tokens={toks_s} hidden_after={c['hidden_after']}")
    t = result["totals"]
    tot_s = "UNKNOWN" if t["tokens"] is None else str(t["tokens"])
    print(f"TOTALS cells={t['cells']} run={t['cells_run']} model_calls={t['model_calls']} tokens={tot_s}")
    if result["stop_reason"]:
        print(f"STOP_REASON {result['stop_reason']}（停、不重試）")


def main(argv: list[str] | None = None, *, channel: Channel | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vacant_network.reqloop.g3",
                                 description="G3 發射管線（vq-1zf；核准前禁止發射）")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="只核 plan/凍結/預算＋列出 12 格；0 模型呼叫")
    mode.add_argument("--fire", action="store_true",
                      help="需 --approval 人類核准文件；無核准→RC 2、0 模型呼叫")
    ap.add_argument("--approval", default=None, help="核准文件 JSON（approved=true、epic=vq-1zf、by=核准者）")
    ap.add_argument("--out", default=None, help="結果輸出目錄（預設 ops/reqloop/g3_gate/fire_<ts>）")
    ap.add_argument("--answer-model", default=DEFAULT_ANSWER_MODEL)
    ap.add_argument("--extract-model", default=DEFAULT_EXTRACT_MODEL)
    args = ap.parse_args(argv)

    try:
        plan = g3gate.G3Plan.load(args.manifest)
    except Exception as e:
        print(f"G3 FIRE PLAN BAD: {e}")
        return RC_PLAN

    if args.dry_run:
        try:
            plan.verify_frozen(pathlib.Path(args.manifest).parent)
            g3gate.check_budget(plan)
        except Exception as e:
            print(f"G3 FIRE PLAN BAD: {e}")
            return RC_PLAN
        cells = g3gate.plan_cells(plan)
        print(f"G3 DRY-RUN: {len(cells)} cells, arms={list(plan.arms)}, budget={json.dumps(plan.budget, ensure_ascii=False)}")
        for t, a in cells:
            spec = ARM_SPECS[a]
            print(f"  CELL {t}/{a}: list={spec['requirement_list']} rounds<={spec['max_rounds']} "
                  f"localized={spec['localized_repair']} reverify={spec['reverify_all']}")
        print("DRY-RUN OK（0 模型呼叫；未發射）")
        return RC_OK

    # --fire：核准門 fail-closed（無核准→RC 2、0 模型呼叫）
    if args.approval is None:
        print("G3 FIRE NOT APPROVED: 無核准文件——0 模型呼叫（fail-closed）")
        return RC_NOT_APPROVED
    try:
        approval = json.loads(pathlib.Path(args.approval).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"G3 FIRE NOT APPROVED: 核准文件不可讀——0 模型呼叫（{e}）")
        return RC_NOT_APPROVED
    ok, why = g3gate.approval_gate(approval)
    if not ok:
        print(f"G3 FIRE NOT APPROVED: {why}——0 模型呼叫（fail-closed）")
        return RC_NOT_APPROVED

    base = pathlib.Path(args.manifest).parent
    out_root = pathlib.Path(args.out) if args.out else base / f"fire_{time.strftime('%Y%m%d_%H%M%S')}"
    chan = channel if channel is not None else GlmChannel()
    try:
        result = run_g3(plan, base, out_root, channel=chan, approval=approval,
                        answer_model=args.answer_model, extract_model=args.extract_model)
    except G3NotApproved as e:
        print(f"G3 FIRE NOT APPROVED: {e}——0 模型呼叫（fail-closed）")
        return RC_NOT_APPROVED
    except Exception as e:
        print(f"G3 FIRE FAIL: {type(e).__name__}: {e}")
        return RC_PLAN
    _print_cell_lines(result)
    print(f"G3 FIRE DONE: out={out_root}（hidden_after 全 UNKNOWN；打分流給 /srv/vlab scorer）")
    return RC_OK


if __name__ == "__main__":
    raise SystemExit(main())
