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
- 臂名實相符（conformance）：ARM_WIRED（實作接線）對照 ARM_REQUIRED（預註冊
  arm_defs 要求）逐臂核對；任何一臂不符→RC 3（同義 RC_APPROVED_NOT_WIRED）、
  0 模型呼叫——核准過了也不發。AMEND-1（2026-11-11 人類裁決）：native_pi
  接真 pi 工具迴圈＋本地模型（PiChannel；manifest budget 如實宣告
  'glm+local_pi'＋pi_provider/pi_model），不再是 glm 通道＋提示詞自檢的
  名實不符版本；run_g3 對 pi 臂要求注入 pi_channel，缺注入＝拒發。
- full_rloop 的 localized 修復與重驗＝真的接了 checks.run_requirement_checks
  （程式重算每輪重驗）＋build_repair_feedback（FAIL-only 反饋，不含重算期望
  值）＋repair.diff_results（FAIL→PASS／退步入帳）；不再是只有答案項名稱的
  正規表示式存在性檢查。

本模組 0 模型呼叫：通道可注入（測試用假通道）；GlmChannel 只在真發射時使用。
"""
from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
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
from vacant_network.reqloop import repair as _repair
from vacant_network.reqloop.requirements import RequirementSet
from vacant_network.reqloop.checks import run_requirement_checks
from vacant_network.reqloop.repair import diff_results as _diff_results

SCHEMA_RESULT = "vacant.reqloop.g3.result/1"

# 與 g3gate 同義（發射側不自訂第二套碼）；g3gate 本身沒有 plan 失敗碼
#（其 --fire 未接線用 RC_APPROVED_NOT_WIRED=3），發射側 plan/完整性失敗用 1：
RC_OK = g3gate.RC_OK
RC_PLAN = 1
RC_NOT_APPROVED = g3gate.RC_NOT_APPROVED

HIDDEN_AFTER_UNKNOWN = "UNKNOWN"

DEFAULT_ANSWER_MODEL = "deepseek41"     # 作答模型（glm CLI 別名）
DEFAULT_EXTRACT_MODEL = "glm53"         # 擷取模型（必須不同於作答模型）
DATA_PREVIEW_BYTES = 64 * 1024          # 進 prompt 的單資料檔上限（超出截斷並如實標註）

#: glm 臂 token_limit 修復（票 P20261111_0645-1，選項 a：提升 glm 上限）：
#: vibe --max-tokens＝「Maximum total prompt + completion tokens」（vibe help
#: 原文）——是 prompt+completion 總預算，不是 completion 上限。首發實證（8×
#: 「Stopped: token_limit」）：answer prompt input 32609–39266 tok
#: （state/vibe_calls.jsonl）全部 > glm CLI 預設 --max-tokens 30000→completion
#: 被擠成 55–181 tok；擷取 call（input ~5.7K tok）在 30000 內→全成。上限是
#: CLI 級參數（非每帳號設定），由本呼叫端顯式傳：60000 > 首發最大 prompt
#: 39266＋completion 空間。
GLM_MAX_TOKENS_TOTAL = 60_000

REPO = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO / "ops" / "reqloop" / "g3_gate" / "manifest.json"
DEFAULT_STATE_DIR = pathlib.Path(os.environ.get("VACANT_OPS_STATE", str(pathlib.Path.home() / "dev" / "ops" / "state")))

# 三臂（vq-1zf 預註冊 ops/reqloop/g3_gate/manifest.json arm_defs，2026-11-08 凍結）：
#   native_pi    「原生 pi：再檢查修正一次」（一輪可見回饋，無需求清單、無修復
#                 循環）。AMEND-1（2026-11-11 人類裁決）：接真 pi 工具迴圈＋
#                 本地模型（PiChannel；provider/model 由 manifest budget 宣告），
#                 不再是「glm 通道＋提示詞自檢」的名實不符版本。
#   reqlist_only 作答模型另得 extract.py 擷取的需求清單；無 localized 修復、無重驗。
#   full_rloop   需求清單＋每輪 checks.run_requirement_checks 程式重算（非模型自評）：
#                 必需條目有已確認缺口（FAIL／必要答案項缺失）才花下一輪；修復反饋
#                 逐條帶 FAIL 狀態與可見反例（不含重算期望值）、只修未滿足條目；
#                 修復後重驗所有必需條目（reverify_all），差異用 repair.diff_results
#                 記錄（FAIL→PASS／任何退步一律入帳）。UNKNOWN 不是缺口、也不是通過。
ARM_SPECS: dict[str, dict] = {
    "native_pi": {
        "pi_agent": True,
        "requirement_list": False,
        "max_rounds": 1,
        "localized_repair": False,
        "reverify_all": False,
        "content_reverify": False,
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
        "content_reverify": False,
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
        "content_reverify": True,
        "instruction": (
            "完整 R-loop：依需求清單作答。若草稿未滿足清單，只修未滿足的條目、"
            "已滿足部分保持不變；輸出前重驗所有必要條目。"
        ),
    },
}

# 臂名實相符（conformance 門；抓「臂名比實作先走」的 H-0 型假綠燈）。
# ARM_WIRED＝當前實作真正具備的機制（惟測試可證偽的宣告，見
# tests/test_reqloop_g3_conformance.py）；ARM_REQUIRED＝預註冊 arm_defs 對每臂的
# 要求。兩者不符 → 拒發（RC 3、0 模型呼叫）：發射跑完的數據會掛著名實不符的
# 臂名被引用，比不發射更糟。
ARM_WIRED: dict[str, dict[str, bool]] = {
    # AMEND-1（2026-11-11 人類裁決）：native_pi 接真 pi 工具迴圈＋本地模型
    # （PiChannel：pi_build/run_agent－prepare_workspace/parse_usage_from_log
    # 全部復用 G2 的既有機制；provider/model 由 manifest budget 宣告）。
    # 行為由 tests/test_reqloop_g3_conformance.py 的 PiChannel 測試背書
    # （fake build/run 注入：answer.txt 讀回、usage 解析、rc!=0/timeout/
    # 缺交付物→G3CallError）。
    "native_pi": {
        "pi_agent": True,           # PiChannel（pi 工具迴圈、本地模型）
        "requirement_list": False,
        "localized_repair": False,
        "content_reverify": False,
    },
    "reqlist_only": {
        "requirement_list": True,  # extract.py 擷取，作答 prompt 帶清單
        "localized_repair": False,
        "content_reverify": False,
    },
    "full_rloop": {
        "requirement_list": True,   # 同 reqlist_only 的擷取清單
        "localized_repair": True,   # FAIL-only 反饋＋只修缺口（build_repair_feedback）
        "content_reverify": True,   # checks.run_requirement_checks 程式重算每輪重驗
    },
}
# ARM_REQUIRED 是預註冊（manifest.arm_defs）的逐臂要求；改這裡＝改預註冊，
# 須人類重新核准，agent 不得自行放寬。
ARM_REQUIRED: dict[str, dict[str, bool]] = {
    "native_pi": {"pi_agent": True},   # arm_def:「原生 pi」
    "reqlist_only": {"requirement_list": True},
    "full_rloop": {"requirement_list": True, "localized_repair": True,
                   "content_reverify": True},
}

_ANSWER_ITEM_RE = re.compile(r"@([A-Za-z0-9_]+)\[[^\]]*\]")
# 契約範本列舉答案項的句子（dab 系任務固定用這個格式，例：
# "This task expects 2 item(s): `@mean_fare[...]`, `@std_dev_fare[...]`."）
_ANSWER_EXPECTS_RE = re.compile(r"expects\s+\d+\s+item\(s\)\s*:\s*([^\n]+)")


class G3QuotaError(RuntimeError):
    """撞日額度（或 glm rc=3）。停、不重試（quota_fail_closed）。"""


class G3CallError(RuntimeError):
    """單格模型呼叫失敗（glm rc=4 等）。該格記 error、不重試、管線繼續。"""


class G3NotApproved(RuntimeError):
    """核准門不過（RC 2 語義；0 模型呼叫）。"""


class G3ArmsNotConformant(RuntimeError):
    """臂與預註冊定義不符（RC 3 語義；0 模型呼叫——核准過了也不發）。"""


# ── 臂 conformance（名實相符門）──────────────────────────────────────


def arm_conformance(plan: g3gate.G3Plan) -> tuple[bool, list[str]]:
    """逐臂核對「預註冊要求（ARM_REQUIRED）」與「實作接線（ARM_WIRED）」。

    不符即回傳問題清單（發射側拒發）。兩個來源都不得自我宣告放行：
    - ARM_REQUIRED 缺項的臂＝預註冊沒寫清楚 → 也拒（不默默放行）；
    - ARM_SPECS 宣告 localized_repair／reverify_all 的臂，wired 必須真的有
      修復反饋與內容重算機制（規格旗標不得無實作支撐——舊 full_rloop 就是
      宣告了 localized_repair=True 卻只有答案項名稱正規表示式檢查）。
    """
    problems: list[str] = []
    for arm in plan.arms:
        if arm not in ARM_SPECS or arm not in ARM_WIRED:
            problems.append(f"{arm}: ARM_SPECS/ARM_WIRED 無此臂（manifest 與管線不同步）")
            continue
        spec = ARM_SPECS[arm]
        wired = ARM_WIRED[arm]
        for mech, need in ARM_REQUIRED.get(arm, {}).items():
            if need and not wired.get(mech, False):
                problems.append(
                    f"{arm}: 預註冊要求 {mech}=True，實作未接線"
                    f"（ARM_WIRED['{arm}']['{mech}']=False）")
        if arm not in ARM_REQUIRED or not ARM_REQUIRED[arm]:
            problems.append(f"{arm}: ARM_REQUIRED 未記載預註冊要求（不得默默放行）")
        if (spec.get("localized_repair") or spec.get("reverify_all")) and (
                not wired.get("localized_repair", False)
                or not wired.get("content_reverify", False)):
            problems.append(
                f"{arm}: ARM_SPECS 宣告 localized 修復/重驗，但 ARM_WIRED 未接線")
    return (not problems), problems


# ── 內容重驗（checks.py 程式重算，非模型自評）────────────────────────


#: 修復反饋中單段驗證詳情／反例的長度上限（與 repair._PROMPT_TEXT_CAP 同口徑：
#: 過長 JSON 對小模型是過載；截斷必須可見）
_FEEDBACK_TEXT_CAP = 800

DEFAULT_DELIVERABLE = "answer.txt"


def _cap_feedback_text(s: str) -> str:
    s = (s or "").strip()
    if len(s) <= _FEEDBACK_TEXT_CAP:
        return s
    return s[:_FEEDBACK_TEXT_CAP].rstrip() + f"…（已截斷，共 {len(s)} 字）"


def cell_round_dir(out_root: pathlib.Path, tid: str, arm: str,
                   round_no: int) -> pathlib.Path:
    """每格每輪的工作目錄（草稿在此落盤為交付物，供 checks 重算；保留供審計）。"""
    d = pathlib.Path(out_root) / "cells" / f"{tid}__{arm}" / f"round_{round_no}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def content_recheck(task_ws: pathlib.Path, req_set: RequirementSet,
                    deliverable_dir: pathlib.Path, text: str) -> list:
    """草稿落盤為 answer.txt → checks.run_requirement_checks 程式重算。

    同 G1/G2 口徑：檢查器從任務目錄自己的資料重算，模型自評不算數。
    未知檢查器／參數不合 → ClaimResult UNKNOWN（不是 PASS、不是 FAIL）。
    """
    deliverable_dir.mkdir(parents=True, exist_ok=True)
    (deliverable_dir / DEFAULT_DELIVERABLE).write_text(text, encoding="utf-8")
    return run_requirement_checks(task_ws, req_set, deliverable_dir)


def _claim_records(results: list, unverified_reasons: dict | None = None) -> list[dict]:
    """ClaimResult → 可落盤的逐條記錄（controller 自己的證據；不進 prompt 的部分
    如 evidence 原樣保留，leak_guard 管的是 prompt，不是結果檔）。

    unverified_reasons＝extract 報告 report.unverified 的 {claim_id: 原因} 映射；
    claim 的 evidence.unverified=true 且有對應原因時注入 evidence["reason"]——
    UNKNOWN 條目落盤可歸因（I-4：未測得≠通過，且寫下測不了的原因）。原
    ClaimResult 的 evidence 不改動（另建 dict，後端 diff/feedback 共用同一清單）。
    """
    out = []
    for c in results:
        ev = c.evidence
        if (isinstance(ev, dict) and ev.get("unverified")
                and unverified_reasons
                and c.claim_id in unverified_reasons):
            ev = {**ev, "reason": unverified_reasons[c.claim_id]}
        out.append({
            "id": c.claim_id,
            "status": c.status,
            "required": bool(c.required),
            "verifier": c.verifier,
            "detail": c.detail,
            "evidence": ev,
        })
    return out


def content_verdict(results: list) -> str:
    """必需條目裁決（I-4 口徑：未測得≠通過）。

    全必需 PASS → PASS；任一必需 FAIL → FAIL；查無必需條目、或含
    UNKNOWN/CONFLICT/缺項 → UNKNOWN（絕不因「沒量到」而 PASS）。
    """
    required = [c for c in results if getattr(c, "required", False)]
    if not required:
        return "UNKNOWN"
    if any(c.status == "FAIL" for c in required):
        return "FAIL"
    if all(c.status == "PASS" for c in required):
        return "PASS"
    return "UNKNOWN"


def confirmed_gap(results: list, missing: tuple[str, ...]) -> tuple[bool, str]:
    """已確認缺口：必需條目 FAIL，或必要答案項缺失。

    UNKNOWN 不是缺口（無從據以修復），但也不是通過——verdict 另記。
    回傳 (有缺口, 缺口所在)。
    """
    if missing:
        return True, "missing_answer_names"
    fails = [c.claim_id for c in results
             if getattr(c, "required", False) and c.status == "FAIL"]
    if fails:
        return True, "required_fail"
    return False, ""


def build_repair_feedback(req_set: RequirementSet, results: list,
                          missing: tuple[str, ...]) -> str:
    """localized 修復反饋（只有 full_rloop 的第 2 輪 prompt 帶）。

    內容與 G2 repair.build_repair_prompt 同口徑：逐條狀態（含 FAIL 的可見
    反例）、已 PASS 條目必須保持、只修缺口。檢查器（kv_recomputed 等）的
    反例依設計不含重算期望值——本函數原樣轉載，不添加任何答案。
    """
    by_id = {c.claim_id: c for c in results}
    lines = ["【逐條需求驗證結果（程式重算，非模型自評）】"]
    for it in req_set.items:
        c = by_id.get(it.id)
        if c is None:
            continue
        lines.append(f"- [{c.status}] {it.id}（交付物：{it.deliverable}）：{it.quote}")
        if c.status != "PASS":
            lines.append(f"  驗證結果：{_cap_feedback_text(str(c.detail))}")
            if c.evidence:
                ev = json.dumps(c.evidence, ensure_ascii=False, default=str)
                lines.append(f"  可見反例：{_cap_feedback_text(ev)}")
    lines.append("")
    keep = [c.claim_id for c in results if c.status == "PASS"]
    lines.append("【必須保持成立的條件】")
    lines.append(
        ("以下條目已 PASS，修正後必須仍然 PASS：" + "、".join(keep))
        if keep else "（沒有已 PASS 的條目）")
    if missing:
        lines.append(
            "另外，以下必要答案項在上一稿缺失："
            + "、".join(f"@{n}[...]" for n in missing))
    lines.append("只修上面的缺口，不要重寫不相關的部分；所有必需條目都要能通過重驗。")
    return "\n".join(lines)


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


class Channel(ABC):
    """模型通道協議：call() → (text, RoundUsage)。可注入（測試假通道、真 GlmChannel）。

    抽象契約（同 vacant_network/substrate.py 的 Substrate(ABC) 慣例）：裸 Channel
    不可實例化（TypeError）；具體通道必實作 call——GlmChannel（真發射、glm CLI）
    或測試假通道。未實作 call 的子類同樣不可實例化。
    """

    @abstractmethod
    def call(self, *, prompt: str, model: str, purpose: str, timeout_s: float) -> tuple[str, RoundUsage]:
        """具體通道必實作；裸 Channel 不可實例化（ABC TypeError），此體不執行。"""
        raise NotImplementedError


def _count_lines(path: pathlib.Path) -> int:
    """行數（Python 3.12 無 Path.count_lines；vibe_calls.jsonl 每天只有少量行）。"""
    if not path.is_file():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


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
        before_lines = _count_lines(self._calls_log)
        fd, prompt_path = tempfile.mkstemp(prefix="vacant_g3_", suffix=".md")
        t0 = time.monotonic()
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(prompt)
            proc = subprocess.run(
                [self.glm_bin, "--model", model, "--purpose", purpose,
                 "--prompt-file", prompt_path, "--time-limit", str(int(timeout_s)),
                 "--max-tokens", str(GLM_MAX_TOKENS_TOTAL)],
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
        new = _tail_usage(self._calls_log, _count_lines(self._calls_log) - before_lines)
        if new:
            tokens = None
            for rec in new:
                v = rec.get("total_tokens")
                # r1419（vq-el4.94，真產品 bug）：舊碼 `int(rec.get("total_tokens"))`
                # 把 JSON bool 當 int（false→0＝實際耗 token 的呼叫記成本 0、true→1）、
                # 負數（-100 → QuotaGuard known_tokens 被扣減、日額度更遲才觸發）、
                # float（截斷）／string（自我聲明文字）全靜默接受——quota fail-open
                # （r1376 同族：工作量的界不得依賴「用量恰好被測到」；r1405 strict-int／
                # r1408 預算同族；門不得信被驗方的自我聲明）。本檔由外部 glm CLI 寫，
                # 只認嚴格 int≥0；否則 UNKNOWN（None，不填 0）。真 CLI 形狀即嚴格 int
                # （實測 vibe_calls.jsonl 如 "total_tokens": 10164），正控制不受影響。
                if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                    v = None
                if v is None:
                    tokens = None  # 任一筆缺值/不可信 → UNKNOWN（不填 0）
                    break
                tokens = (tokens or 0) + v
        else:
            tokens = None  # raw usage 無新增行 → UNKNOWN
        return proc.stdout, RoundUsage(calls=1, tokens=tokens, wall_ms=wall_ms)


class PiChannel(Channel):
    """native_pi 的真通道（AMEND-1，2026-11-11）：pi 工具迴圈＋本地模型。

    一個 call＝一次 pi session：在任務輸入複本（prepare_workspace：G2 既有機制）
    裡跑 agent、讀回 answer.txt 作為本輪草稿。作答的「self-check 一輪可見回饋」
    由 pi 原生 agent 迴圈完成——臂定義就是 pi 的原生行為，不是提示詞自檢。

    通道隔離：glm 臂走 GlmChannel（遠端／額度），pi 臂走本通道（本地模型，同
    QuotaGuard 日額度界）。provider/model 由 manifest budget（pi_provider/
    pi_model，AMEND-1 如實宣告）或 CLI 參數指定；本類不持金鑰。

    Usage：repair.parse_usage_from_log 讀 agent stdout raw usage（input+output+
    total、API 呼叫數）；缺值＝UNKNOWN（None），絕不填 0。build/run 可注入
    （測試用假通道；簽名與 adapters.agents.pi_build／adapters.run.run_agent 同）。

    錯誤語義（與 GlmChannel 同口徑）：pi 非零退出／逾時／spawn 失敗／agent
    沒寫 answer.txt → G3CallError（該格 error、不重試、管線繼續）。
    """

    def __init__(self, base: str | pathlib.Path, *,
                 out_root: str | pathlib.Path,
                 provider: str = "lms1003qwen", model: str = "qwen/qwen3.8-27b",
                 include_dirs: tuple[str, ...] = ("data",),
                 build=None, run=None,
                 deliverable: str = DEFAULT_DELIVERABLE) -> None:
        self.base = pathlib.Path(base)
        self.out_root = pathlib.Path(out_root)
        self.provider = provider
        self.model = model
        self.include_dirs = tuple(include_dirs)
        self.deliverable = deliverable
        self._build_fn = build
        self._run_fn = run

    def _build(self, prompt: str, ws: pathlib.Path):
        if self._build_fn is not None:
            return self._build_fn(prompt, ws)
        # 預設：真 pi（同 repair._default_build——pi_build＋pin_agent_python，
        # pin 讓 agent 的裸 python 與驗證重算同一個直譯器）
        from vacant_network.adapters.agents import pi_build
        extra = ["--provider", self.provider, "--model", self.model]
        return _repair.pin_agent_python(pi_build(prompt, ws, extra=extra))

    def _run(self, launch, *, workspace: pathlib.Path, timeout_s: float,
             log_dir: pathlib.Path) -> dict:
        if self._run_fn is not None:
            return self._run_fn(launch, workspace=workspace, timeout_s=timeout_s,
                                log_dir=log_dir)
        from vacant_network.adapters.run import run_agent
        return run_agent(launch, workspace=workspace, timeout_s=timeout_s,
                        log_dir=log_dir)

    def call(self, *, prompt: str, model: str, purpose: str,
             timeout_s: float) -> tuple[str, RoundUsage]:
        m = re.match(r"G3 (\S+?)/(\S+) r(\d+)$", purpose)
        if not m:
            raise G3CallError(f"native pi purpose 格式未預期：{purpose!r}")
        tid, arm, round_no = m.group(1), m.group(2), int(m.group(3))
        task_ws = self.base / "tasks" / tid / "workspace"
        if not task_ws.is_dir():
            raise G3CallError(f"任務工作目錄缺失：{task_ws}")
        cell_root = self.out_root / "cells" / f"{tid}__{arm}"
        cell_root.mkdir(parents=True, exist_ok=True)
        # 工作區＝G2 既有機制 prepare_workspace：task 輸入複本（goal/contract/
        # data/）＋逐輪快照（保留供審計；原任務檔不被改動）。pi 臂第 1 輪就
        # 自己作答、沒有草稿來源 → draft_dir 用不存在的哨兵路徑。
        ws = _repair.prepare_workspace(
            task_ws, cell_root / "_no_draft_",
            out_root=cell_root, round_n=round_no,
            include_dirs=self.include_dirs)
        log_dir = cell_root / f"round_{round_no}_agent"
        launch = self._build(prompt, ws)
        ret = self._run(launch, workspace=ws, timeout_s=timeout_s,
                        log_dir=log_dir)
        if ret.get("spawn_error"):
            raise G3CallError(f"pi spawn 失敗：{ret.get('spawn_error')}")
        if ret.get("budget_exceeded"):
            raise G3CallError(
                f"pi 預算超限被殺（budget_exceeded={ret.get('budget_exceeded')}"
                f"；observed tool_calls={ret.get('observed_tool_calls')}, "
                f"tokens={ret.get('observed_tokens')}）")
        if ret.get("timed_out"):
            raise G3CallError(f"pi timed out after {timeout_s:.0f}s")
        rc = ret.get("rc")
        if rc != 0:
            raise G3CallError(f"pi rc={rc}")
        answer = ws / self.deliverable
        if not answer.is_file():
            raise G3CallError(
                f"native pi 未產出交付物 {self.deliverable}（工作區：{ws}）")
        text = answer.read_text(encoding="utf-8", errors="replace")
        usage = _repair.parse_usage_from_log(ret.get("stdout_log", ""))
        tokens = usage["total"] if usage else None      # 缺值＝UNKNOWN，不填 0
        calls = usage["calls"] if usage else 1          # 沒量到 usage＝session 計 1
        wall = ret.get("wall_ms")
        return text, RoundUsage(calls=calls, tokens=tokens,
                                wall_ms=wall if isinstance(wall, int) else None)


class _ArmChannelRouter(Channel):
    """依 purpose 的臂名分流：pi 臂→PiChannel（本地模型），其他（glm 作答
    臂／擷取）→GlmChannel。兩個入口共用同一個 QuotaGuard（同一日額度界，
    AMEND-1 的 model_entry='glm+local_pi' 如實對應這個拓撲）。"""

    def __init__(self, channel: Channel, pi_channel: Channel) -> None:
        self.channel = channel
        self.pi_channel = pi_channel

    def call(self, *, prompt: str, model: str, purpose: str,
             timeout_s: float) -> tuple[str, RoundUsage]:
        m = re.match(r"G3 \S+?/(\S+) r\d+$", purpose)
        if m and ARM_SPECS.get(m.group(1), {}).get("pi_agent"):
            return self.pi_channel.call(prompt=prompt, model=model,
                                        purpose=purpose, timeout_s=timeout_s)
        return self.channel.call(prompt=prompt, model=model,
                                 purpose=purpose, timeout_s=timeout_s)


class QuotaGuard:
    """日額度 fail-closed 護欄（11/07「撞 2M/日額度即停、不得重試」）：
    呼叫前已知 tokens ≥ cap → 直接 G3QuotaError（0 呼叫）；呼叫後累計。
    缺值 tokens 不累計（UNKNOWN 不假裝 0）。

    呼叫數後備（r1376，vq-el4 真產品 bug）：token 用量全為 UNKNOWN（None）時
    known_tokens 恆 0、token cap 永不觸發→舊碼放行無限呼叫＝fail-open（實證：
    cap=250 仍放行 50 次）。呼叫數恆可測，故以 max_calls 兜底——工作量的界不該
    依賴「用量恰好被測到」。max_calls=None＝不啟用後備（既有呼叫形狀不變）。
    """

    def __init__(self, channel: Channel, daily_token_cap: int,
                 max_calls: int | None = None) -> None:
        self.channel = channel
        self.cap = int(daily_token_cap)
        self.max_calls = int(max_calls) if max_calls is not None else None
        self.known_tokens = 0
        self.total_calls = 0

    def call(self, *, prompt: str, model: str, purpose: str, timeout_s: float) -> tuple[str, RoundUsage]:
        if self.known_tokens >= self.cap:
            raise G3QuotaError(f"已知 tokens {self.known_tokens} ≥ 日額度 {self.cap}——停、不重試")
        if self.max_calls is not None and self.total_calls >= self.max_calls:
            raise G3QuotaError(
                f"呼叫數 {self.total_calls} ≥ 後備上限 {self.max_calls}"
                "（用量 UNKNOWN 時 token cap 不可測，以呼叫數兜底）——停、不重試")
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
        self.ledger.append(usage.to_dict())
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
    """從可見 contract.md 解析必要答案項名（@name[...]）。

    優先取「expects N item(s):」列舉的項名。契約範本用 `@name[value]` 描述
    輸出格式，那個 placeholder 不是答案項名——舊解析把 "name" 也算進必要項，
    對不含 `@name[...]` 的真實答案造成恆真假缺口。列舉句不存在時退回全文
    掃描並剔除範本 placeholder "name"（兩個來源都以可見 contract 為準，
    無隱藏資料）。
    """
    m = _ANSWER_EXPECTS_RE.search(contract)
    if m:
        return sorted(set(_ANSWER_ITEM_RE.findall(m.group(1))))
    return sorted(set(_ANSWER_ITEM_RE.findall(contract)) - {"name"})


def compose_extract_user_text(goal: str, contract: str | None) -> str:
    """擷取用的使用者原文＝goal＋公開 contract.md（對齊 G2.5 load_cell_request_text）。

    contract.md 是公開交付規格（寫到哪個檔、什麼格式），不含答案、不含 hidden。
    漏附它時交付檔名只存在於 contract，擷取模型猜出的檔名全數被判
    deliverable_not_in_request（假陽性，見 P20261111_1516-1）。
    contract 為空或已含於 goal 時原樣回傳 goal。
    """
    c = (contract or "").strip()
    if c and c not in goal:
        return goal.rstrip() + "\n\n" + c + "\n"
    return goal


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


#: 顯式無工具覆寫（2026-11-11，工單 P20261111_0840-1 項 1；AMEND-3
#: ops/approvals/g3_vq-1zf_fire_20261111_AMEND3.json 人類核准）：任務文本原為
#: 工具使用者所寫（agent 式指令），而無工具臂走 glm CLI
#: --max-turns 1 --enabled-tools none——模型照文本做讀檔/寫檔的 agent 動作，
#: 撞單回合無工具限制即 turn_limit（fire a/b：glm 臂 8/8 turn_limit、9-15s、
#: 輸出 67-164 tok）。修法：build_cell_prompt（round 1 與 round>=2 修復輪共用）
#: 頂部加顯式覆寫；不改變三臂同源的臂段指令；不改 ~/.local/bin/glm。
NO_TOOL_OVERRIDE = (
    "此任務文本原為工具使用者所寫；你沒有任何工具。不要讀檔、不要寫檔，"
    "僅依下文給出的任務與資料，在第一則訊息直接輸出全部 @name[值] 答案行。"
)


def build_cell_prompt(task: dict, spec: dict, *, req_list_text: str = "",
                      round_no: int = 1, missing: tuple[str, ...] = (),
                      prev_draft: str = "", feedback: str = "") -> str:
    """決定性 prompt：無工具覆寫＋任務＋資料＋（臂）需求清單＋（臂）指令＋（第 2 輪）缺口證據。

    紅線：不含 /srv/eval/hidden/、scorer.py 或任何隱藏內容；缺口證據只含
    可見 contract 的答案項名與上一稿原文＋檢查器反例（依設計不含重算期望值）。
    第 2 輪（localized 修復）必帶上一稿原文——模型必須看得到自己上一稿
    才能只修缺口；空白反例（無缺口卻進第 2 輪）在 run_g3 的輪迴圈已被擋下。
    """
    data_block = ""
    for name in sorted(task["data"]):
        data_block += f"--- data/{name} ---\n{task['data'][name]}\n"
    parts = [
        NO_TOOL_OVERRIDE,
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
    parts += ["【本輪要求】", spec["instruction"]]
    if spec["requirement_list"]:
        # 需求清單屬於「臂段」（【本輪要求】之後）：任務＋資料段三臂逐字相同
        parts += ["【需求清單（extract.py 擷取）】", req_list_text or render_requirement_list(None)]
    if round_no >= 2:
        parts += ["【上一稿與缺口】"]
        if prev_draft.strip():
            parts += ["--- 上一稿原文（可見回饋的對象）---", prev_draft.strip()]
        if missing:
            parts += ["以下必要答案項在上一稿缺失："
                      + "、".join(f"@{n}[...]" for n in missing)]
        if feedback:
            parts += [feedback]
        parts += ["只修未滿足的條目、已滿足部分保持不變；輸出前重驗所有必要條目。"]
    parts += ["【輸出】", "只輸出最終答案項（contract 格式），每項一行，不要多餘說明。"]
    return "\n\n".join(parts) + "\n"


def build_pi_cell_prompt(task: dict, spec: dict) -> str:
    """native_pi 臂的 prompt：工作區裡有真檔案（prepare_workspace 複本），
    pi 用工具自讀——不內嵌 64KB 資料預覽（截斷反而妨礙工具迴圈）。

    臂段指令與其他臂同源（ARM_SPECS['instruction']）＝臂間唯一差異段；
    任務「輸入」逐字＝凍結 instruction.txt（不是管線自撰）。
    """
    parts = [
        task["instruction"].strip(),
        "【本臂要求】",
        spec["instruction"],
        "【輸出】",
        "只把最終答案項寫進 answer.txt（contract 格式），每項一行，不寫其他說明。",
    ]
    return "\n\n".join(parts) + "\n"


# ── 結果與總量（缺值 UNKNOWN 絕不填 0）────────────────────────────────


def _sum_tokens(usages: list[dict]) -> int | None:
    """任一筆缺 tokens → None；零筆 → None（不報 0 成本）。usages 為 RoundUsage.to_dict() 記錄。"""
    if not usages:
        return None
    total = 0
    for u in usages:
        v = u["tokens"]
        if v is None:
            return None
        total += int(v)
    return total


def _sum_calls(usages: list[dict]) -> int:
    return sum(int(u["calls"]) for u in usages)


def _cell_usage(cell: dict) -> list[dict]:
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


#: pi session call 數上界（P20261111_0840-1 項 2；AMEND-3
#: ops/approvals/g3_vq-1zf_fire_20261111_AMEND3.json 人類核准）：PiChannel.call
#: 「一次通道呼叫＝一次 pi session」，session 內部 N 通 API 呼叫（工具迴圈：
#: 讀任務檔、寫 answer.txt），RoundUsage.calls＝實 call 數，QuotaGuard 累計的
#: 就是它——舊公式把 pi 格當 1 call 是名實不符。實測（raw，非轉抄）：fire a
#: dab_129＝7；fire b 4 格＝7/8/7/5（max 8，dab_144）。上界取實測 max 8；
#: fail-closed 語義不變（撞上界＝停、不重試）。理由＋算式已寫回票面與
#: commit 訊息（AMEND-3：不得靜默放寬）。
PI_SESSION_CALL_CAP = 8


def max_calls_bound(arm_order: tuple[str, ...], n_tasks: int) -> int:
    """QuotaGuard max_calls 後備上限（r1436 重測，P20261111_0840-1 項 2）。

    算式（嚴上界，逐臂）：
      擷取  n_tasks（每 task 1 guard.call；GlmChannel RoundUsage.calls＝1）
      臂 a  n_tasks × max_rounds_a ×（PI_SESSION_CALL_CAP 若 pi 臂，否則 1）
    舊公式 n_tasks + arms×n_tasks×max_rounds 把一次 pi session 當 1 call：
    4 題×3 臂＝4+3×4×2＝28 < fire b 實際 31（raw totals.model_calls：pi 27
    ＋extract 4）→QuotaGuard 中途假停（2 格 not_run/quota、非 token 額度）。
    新式每輪仍≤1 guard.call、pi session ≤cap 通內部呼叫——仍為嚴上界，只是
    依實測值定 pi 每-session 上界；無 pi 臂的計畫每輪＝1 call（既有形狀）。
    """
    cells = 0
    for a in arm_order:
        spec = ARM_SPECS[a]
        per_call = PI_SESSION_CALL_CAP if spec.get("pi_agent") else 1
        cells += int(n_tasks) * int(spec["max_rounds"]) * per_call
    return int(n_tasks) + cells


# ── 發射主體（零模型呼叫：通道注入）──────────────────────────────────


def load_frozen_spec(spec_dir: pathlib.Path, tid: str, inputs: dict) -> RequirementSet:
    """D4（11-13 定案第 2 條）：載入預跑通過的需求規格 <spec_dir>/<tid>.json。

    兩種合法格式（P20261113_0846-1）：
      - 巢狀：{task_id, goal_sha256, contract_sha256, reqset: <RequirementSet 序列化>}
      - 扁平（RequirementSet.load() 原生／G4 規格）：items 直接在根物件，
        goal_sha256／contract_sha256 可載於根或 reqset 內。
    任一不符／損壞→ValueError 拒發（fail-closed）；絕不默默降級為
    重新擷取——G3.3 證明重新擷取不穩定，發射必須 100% 重用凍結規格。
    """
    p = pathlib.Path(spec_dir) / f"{tid}.json"
    if not p.is_file():
        raise ValueError(
            f"D4 凍結規格缺檔：{p}——指定 spec_dir 卻無此 task 規格，拒發（不重新擷取）")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        raise ValueError(f"D4 凍結規格損壞：{p}: {e}") from e
    if not isinstance(raw, dict):
        raise ValueError(f"D4 凍結規格損壞（非 JSON 物件）：{p}")
    if raw.get("task_id") != tid:
        raise ValueError(
            f"D4 凍結規格 task_id 不符：{p} 記載 {raw.get('task_id')!r}、當前 {tid!r}——拒發")
    if isinstance(raw.get("reqset"), dict):
        spec_dict = raw["reqset"]
    elif isinstance(raw.get("items"), list):
        spec_dict = raw  # 扁平格式（RequirementSet 原生序列化／G4 規格）
    else:
        raise ValueError(f"D4 凍結規格損壞（缺少 reqset 或 items 物件）：{p}")
    try:
        req_set = RequirementSet.from_dict(spec_dict)
    except (KeyError, TypeError, AttributeError, ValueError) as e:
        raise ValueError(f"D4 凍結規格損壞（reqset 不可反序列化）：{p}: {e}") from e
    if req_set.task_id != tid:
        raise ValueError(
            f"D4 凍結規格 reqset.task_id 不符：{req_set.task_id!r} != {tid!r}——拒發")
    goal_sha = hashlib.sha256(inputs["goal"].encode("utf-8")).hexdigest()
    contract_sha = hashlib.sha256(inputs["contract"].encode("utf-8")).hexdigest()
    # 記載雜湊：根優先、reqset 兜底（兩格式皆合法；皆無＝fail-closed 拒發）。
    recorded_goal = str(raw.get("goal_sha256") or req_set.goal_sha256 or "")
    recorded_contract = str(raw.get("contract_sha256") or req_set.contract_sha256 or "")
    if recorded_goal != goal_sha:
        raise ValueError(
            f"D4 凍結規格 goal_sha256 不符：{p} 記載 {recorded_goal!r}、"
            f"當前 {goal_sha!r}——goal 已變動，拒發（不重新擷取）")
    if recorded_contract != contract_sha:
        raise ValueError(
            f"D4 凍結規格 contract_sha256 不符：{p} 記載 {recorded_contract!r}、"
            f"當前 {contract_sha!r}——contract 已變動，拒發（不重新擷取）")
    return req_set


def run_g3(plan: g3gate.G3Plan, base: pathlib.Path, out_root: pathlib.Path, *,
           channel: Channel, pi_channel: Channel | None = None, approval: dict,
           answer_model: str = DEFAULT_ANSWER_MODEL,
           extract_model: str = DEFAULT_EXTRACT_MODEL,
           spec_dir: pathlib.Path | None = None) -> dict:
    """三臂×N 格發射主體。返回結果 dict（write_result 落 g3_result.json）。

    D4（11-13 定案第 2 條）：spec_dir 指定時，需求清單直接重用凍結規格
    （<spec_dir>/<task_id>.json；0 模型擷取呼叫）；缺檔/雜湊不符/損壞→ValueError。

    門（順序即優先級）：
      1) verify_frozen＋check_budget（完整性先於核准判定，篡改→G3Plan 層 ValueError）
      2) approval_gate（不過→G3NotApproved，0 模型呼叫）
      3) arm_conformance＋pi_channel 注入檢查（不符/缺注入→G3ArmsNotConformant，
         0 模型呼叫——核准過了也不發）
      4) 每 task：需求清單擷取一次（供 reqlist_only/full_rloop 兩臂共用＝同資料）
      5) 每格逐輪：QuotaGuard 撞額→停、不重試；G3CallError→該格 error、管線繼續
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
    arm_order = tuple(plan.arms)
    # AMEND-2（2026-11-11，票 P20261111_0645-1）：per-channel 牆時——pi 臂每格＝
    # budget.timeout_s_per_round_pi（600s）；glm 臂與擷取維持 timeout_s_per_round
    # （300s）。check_budget 已驗（pi 臂在場而字段缺失/放寬/非 int→拒發）。
    needs_pi = any(ARM_WIRED.get(a, {}).get("pi_agent") for a in arm_order)
    tpr_pi = int(plan.budget["timeout_s_per_round_pi"]) if needs_pi else tpr
    # 臂 conformance（核准過了也不代表臂名實相符）：任何一臂與預註冊定義
    # 不符即拒發——0 模型呼叫（名實不符的發射比不發射更糟：數據會掛著
    # 錯的臂名被引用）。
    ok_arms, arm_problems = arm_conformance(plan)
    if not ok_arms:
        raise G3ArmsNotConformant("；".join(arm_problems))
    # pi 臂的執行通道必須真的注入（PiChannel 或測試假通道）；缺注入＝拒發
    if needs_pi and pi_channel is None:
        raise G3ArmsNotConformant(
            "native_pi: pi_agent 已接線（AMEND-1）但 pi_channel 未注入——"
            "拒發（0 模型呼叫）")
    tasks = [t["task_id"] for t in plan.tasks]
    # 呼叫數後備上限（r1376）：token 用量未知時 token cap 不可測→以呼叫數兜底。
    # 上界＝擷取（每 task 一次）＋每格最多 max_rounds 輪；實際呼叫少於此上界。
    # r1436（P20261111_0840-1 項 2／AMEND-3）：pi 臂每 session 內部 N 通呼叫
    # （實測 max 8），舊式把 pi 格當 1 call→28 < fire b 實際 31→假停；改用
    # max_calls_bound（逐臂嚴上界，算式見其 docstring；理由＋算式寫回票面）。
    n_tasks = len(plan.tasks)
    max_calls = max_calls_bound(arm_order, n_tasks)

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
    # 通道分流（AMEND-1）：pi 臂→PiChannel（本地模型）；其他→glm 通道；
    # 擷取一律 glm。兩入口同 QuotaGuard（同一日額度界）。
    guard = QuotaGuard(_ArmChannelRouter(channel,
                                         pi_channel), cap, max_calls=max_calls)

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
            "unverified_reasons": {},
            "extract_usages": [],
        }
        req_set = None
        if needs_list and not stopped:
            ledger: list[RoundUsage] = []
            report = None
            if spec_dir is not None:
                # D4（11-13 定案第 2 條）：預跑通過的需求規格凍結落盤、正式發射
                # 直接重用——0 模型擷取呼叫、條件 100% 重現（G3.3 證明重新擷取
                # 不穩定）；缺檔/雜湊不符/損壞→load_frozen_spec 拋 ValueError 拒發，
                # 絕不默默降級為重新擷取。
                req_set = load_frozen_spec(spec_dir, tid, inputs)
                report = _extract.ExtractReport()
            else:
                client = _ChannelExtractClient(guard, extract_model,
                                               purpose=f"G3 {tid} 擷取需求",
                                               timeout_s=tpr, ledger=ledger)
                try:
                    # D2（11-13 裁決第 2 條）：交付物是任務的事實——從原文（goal＋公開
                    # contract）抽唯一點名的非輸入輸出檔作為 trusted deliverable；抽不出
                    # （None）時 extract_requirements 保持舊行為（逐條照模型自報＋逐字點名檢查）。
                    _ut = compose_extract_user_text(
                        inputs["goal"], inputs.get("contract"))
                    req_set, report = _extract.extract_requirements(
                        user_text=_ut,
                        client=client, task_id=tid,
                        trusted_deliverable=_extract.trusted_deliverable_from_contract(
                            _ut, list(inputs["data"].keys())))
                except G3QuotaError as e:
                    # 撞額度＝停發、不重試（不得降級成「擷取失敗＝沒有需求」）
                    stopped = True
                    result["stop_reason"] = "quota"
                    trec["extract_error"] = f"G3QuotaError: {e}"
                    trec["extract_usages"] = ledger
                    result["tasks"].append(trec)
                    req_set = None
            if report is not None:
                trec["extract_error"] = report.extract_error or report.parse_error
                # 凍結的 extract_requirements 會把 client 例外吞進 extract_error，
                # 撞額度標記必須在此層取回（否則「撞額度即停」被降級成空清單繼續發）
                if (trec["extract_error"] or "").startswith("G3QuotaError"):
                    stopped = True
                    result["stop_reason"] = "quota"
                trec["n_requirements"] = len(req_set.items)
                # 逐條 unverified 原因（unknown_verifier／參數不合／deliverable 問題等）
                # 隨 task 記錄落盤，並透傳給 _claim_records 注入 evidence["reason"]——
                # 此前 report.unverified 在此被丟棄，26/26 UNKNOWN 收案無法歸因。
                trec["unverified_reasons"] = {u.id: u.reason for u in report.unverified}
                trec["extract_usages"] = ledger
                result["tasks"].append(trec)

        for arm in arm_order:
            spec = ARM_SPECS[arm]
            reverify_on = bool(spec["content_reverify"]) and req_set is not None \
                and bool(req_set.items)
            cell: dict = {
                "task": tid, "arm": arm, "status": "not_run",
                "requirement_list": bool(spec["requirement_list"]),
                "input_sha256": trec["input_sha256"],
                "rounds": [], "answer": None, "answer_sha256": None,
                "hidden_after": HIDDEN_AFTER_UNKNOWN, "error": None,
                "content_reverify": {
                    "enabled": reverify_on,
                    "rounds": [],          # 每輪逐條狀態（有檢查器的輪才有）
                    "final_verdict": None,  # PASS/FAIL/UNKNOWN
                    "diff": None,           # 修復前後差異（repair.diff_results）
                    "error": None,
                },
            }
            if stopped:
                result["cells"].append(cell)
                continue
            req_list_text = render_requirement_list(req_set) if spec["requirement_list"] else ""
            task_ws = tdir / "workspace"
            needed = trec["required_answer_names"]
            missing: tuple[str, ...] = ()
            gap = False                # 進第 2 輪的條件（缺口＝FAIL 或必要答案項缺失）
            feedback = ""
            prev_draft = ""
            prev_results: list = []
            for round_no in range(1, spec["max_rounds"] + 1):
                if round_no > 1 and not gap:
                    break  # 上一稿無已確認缺口→不花下一輪（無額外呼叫）
                if spec.get("pi_agent"):
                    # native_pi：pi 在工作區用工具自讀任務檔（不內嵌資料預覽）
                    prompt = build_pi_cell_prompt(inputs, spec)
                else:
                    prompt = build_cell_prompt(inputs, spec, req_list_text=req_list_text,
                                               round_no=round_no, missing=missing,
                                               prev_draft=prev_draft, feedback=feedback)
                rec: dict = {"round": round_no, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                             "usages": [], "error": None}
                try:
                    # AMEND-2：pi 臂每格 600s（tpr_pi）；glm 臂每輪 300s（tpr）。
                    text, usage = guard.call(prompt=prompt, model=answer_model,
                                             purpose=f"G3 {tid}/{arm} r{round_no}",
                                             timeout_s=tpr_pi if spec.get("pi_agent") else tpr)
                except G3QuotaError as e:
                    rec["error"] = f"quota: {e}"
                    cell["rounds"].append(rec)
                    cell["status"] = "partial_quota" if cell["answer"] is not None else "not_run"
                    stopped = True
                    result["stop_reason"] = "quota"
                    break
                except G3CallError as e:
                    rec["error"] = str(e)
                    cell["rounds"].append(rec)
                    cell["status"] = "error"
                    cell["error"] = str(e)
                    break
                cell["rounds"].append(rec)
                rec["usages"].append(usage.to_dict())
                cell["answer"] = text
                cell["answer_sha256"] = hashlib.sha256(text.encode()).hexdigest()
                prev_draft = text
                # 必要答案項＝可見 contract 的答案項名（結構性缺口，全臂通用）
                missing = tuple(n for n in needed
                                if not re.search(rf"@{re.escape(n)}\[[^\]]*\]", text))
                # 內容重驗（full_rloop）：checks 程式重算，非模型自評。
                if reverify_on:
                    rd = cell_round_dir(out_root, tid, arm, round_no)
                    try:
                        results = content_recheck(task_ws, req_set, rd, text)
                    except Exception as e:  # 檢查器例外不得炸掉整格：如實記錄、標 UNKNOWN
                        cell["content_reverify"]["error"] = f"{type(e).__name__}: {e}"
                        results = []
                    cell["content_reverify"]["rounds"].append({
                        "round": round_no,
                        "verdict": content_verdict(results) if results else "UNKNOWN",
                        "gap_reason": confirmed_gap(results, missing)[1] or None,
                        "claims": _claim_records(results, trec.get("unverified_reasons")),
                    })
                    if round_no >= 2 and prev_results and results:
                        # 檢查器例外（results 為空）不得被記成「全部退步」——
                        # diff 只在兩輪都有真實重算結果時記。
                        cell["content_reverify"]["diff"] = \
                            _diff_results(prev_results, results).to_dict()
                    cell["content_reverify"]["final_verdict"] = \
                        cell["content_reverify"]["rounds"][-1]["verdict"]
                    gap, gap_reason = confirmed_gap(results, missing)
                    if gap and round_no < spec["max_rounds"]:
                        feedback = build_repair_feedback(req_set, results, missing)
                    prev_results = results
            if cell["status"] == "not_run" and cell["answer"] is not None:
                cell["status"] = "ok"  # 至少一輪成功且無錯誤＝完成（撞額度無答案的 cell 保持 not_run）
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


def main(argv: list[str] | None = None, *, channel: Channel | None = None,
         pi_channel: Channel | None = None) -> int:
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
    ap.add_argument("--spec-dir", default=None,
                    help="D4 凍結需求規格目錄（<dir>/<task_id>.json）：發射時直接重用、"
                         "0 次擷取呼叫；task_id/goal/contract 雜湊不符或規格損壞→拒發。"
                         "省略＝舊行為（動態擷取）")
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
                  f"localized={spec['localized_repair']} reverify={spec['reverify_all']} "
                  f"content_reverify={spec['content_reverify']}")
        ok_arms, arm_problems = arm_conformance(plan)
        print(f"  arm conformance: {'OK' if ok_arms else 'NOT CONFORMANT（--fire 會拒發 RC 3）'}")
        for p in arm_problems:
            print(f"    - {p}")
        print("DRY-RUN OK（0 模型呼叫；未發射）")
        return RC_OK

    # --fire：門序＝完整性（凍結/預算）→ 核准 → 臂 conformance（fail-closed）
    base = pathlib.Path(args.manifest).parent
    try:
        plan.verify_frozen(base)
        g3gate.check_budget(plan)
    except Exception as e:
        print(f"G3 FIRE PLAN BAD: {e}")
        return RC_PLAN

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

    # 臂 conformance（核准之後、第一個模型呼叫之前）：臂名實不符→拒發。
    # 名實不符的發射比不發射更糟——跑出的數據會掛著錯的臂名被引用。
    ok_arms, arm_problems = arm_conformance(plan)
    if not ok_arms:
        print("G3 FIRE ARMS NOT CONFORMANT: 與預註冊定義不符——0 模型呼叫（fail-closed）")
        for p in arm_problems:
            print(f"  - {p}")
        print("處置二選一（兩者都是預註冊層級變更，須人類重新核准；agent 不得自改）：")
        print("  1) 接線缺失的機制後更新 ARM_WIRED（native_pi 需 pi_build/run_agent")
        print("     工具迴圈，且需放寬凍結 budget.model_entry='glm'）；")
        print("  2) 人類修預註冊（manifest arm_defs 改名，ARM_ORDER/ARM_SPECS/"
              "ARM_WIRED/ARM_REQUIRED 同步），舊核准作廢、重新核准。")
        return g3gate.RC_APPROVED_NOT_WIRED

    out_root = pathlib.Path(args.out) if args.out else base / f"fire_{time.strftime('%Y%m%d_%H%M%S')}"
    chan = channel if channel is not None else GlmChannel()
    # pi 臂的通道（AMEND-1）：預設真 PiChannel——provider/model 讀 manifest
    # budget（check_budget 已保證 model_entry='glm+local_pi' 時 pi_provider/
    # pi_model 為非空字串）；測試注入假 pi_channel，真 pi 只在真發射時被 import。
    pi_chan = pi_channel
    if pi_chan is None and any(ARM_SPECS.get(a, {}).get("pi_agent") for a in plan.arms):
        pi_chan = PiChannel(
            base, out_root=out_root,
            provider=str(plan.budget.get("pi_provider") or "lms1003qwen"),
            model=str(plan.budget.get("pi_model") or "qwen/qwen3.8-27b"))
    try:
        result = run_g3(plan, base, out_root, channel=chan, pi_channel=pi_chan,
                        approval=approval,
                        answer_model=args.answer_model, extract_model=args.extract_model,
                        spec_dir=pathlib.Path(args.spec_dir) if args.spec_dir else None)
    except G3NotApproved as e:
        print(f"G3 FIRE NOT APPROVED: {e}——0 模型呼叫（fail-closed）")
        return RC_NOT_APPROVED
    except G3ArmsNotConformant as e:
        print(f"G3 FIRE ARMS NOT CONFORMANT: {e}——0 模型呼叫（fail-closed）")
        return g3gate.RC_APPROVED_NOT_WIRED
    except Exception as e:
        print(f"G3 FIRE FAIL: {type(e).__name__}: {e}")
        return RC_PLAN
    _print_cell_lines(result)
    print(f"G3 FIRE DONE: out={out_root}（hidden_after 全 UNKNOWN；打分流給 /srv/vlab scorer）")
    return RC_OK


if __name__ == "__main__":
    raise SystemExit(main())
