"""
G2 局部修復切片（工單 P000-20261104-01-repair-slice，2026-11-04）。

垂直切片（RLOOP_PLAN.md G2，11/04 方向）：
    原生 pi 接收草稿與可見反例 → 修正產物 → 重驗所有必要條目 → 輸出前後差異及成本。

重用既有元件（不重造契約／重試／收據）：
- `reqloop.requirements.RequirementSet` — 需求條目
- `reqloop.checks.run_requirement_checks` — G1 程式重算檢查器
- `intake.verifiers.ClaimResult` — 四態結果
- `adapters.agents.pi_build` + `adapters.run.run_agent` — 原生 pi 執行（CLI 預設）

規則（RD_FOCUS_20261104，累積修復 P000-20261105-01；本模組的每個行為都在此約束下）：
- **保留原候選**：原草稿目錄永遠不被改動；每一輪複製到新的工作目錄 round_N/ 才讓 agent 動；
  每輪工作區即該輪候選快照，保留供審計。
- **權威輸入（P000-20261105-02）**：重驗的來源資料與需求讀**控制器保存的權威快照**
  （out_root/authoritative/＋authoritative_manifest.json），產物才讀候選工作區——
  agent 改寫工作區裡的來源 CSV／requirements.json 迎合交付，不得翻 FAIL→PASS。
  來源改動記錄為不可接受（逐輪 source_tampered＋outcome.source_tampered，退出碼 20）；
  驗證器程式是庫內閉集分派（未知 verifier→UNKNOWN），不可由候選工作區覆寫。
- **累積修復（2026-11-05）**：第 1 輪從原草稿起；第 N 輪（N≥2）承接第 N−1 輪工作區的
  候選與該輪已驗證狀態——不是每輪重抽原草稿。提示與逐輪差異同樣反映當前候選：
  逐輪 diff＝相鄰輪差異（上一輪狀態→本輪重驗）；原始級差異（原草稿初始驗→最終重驗）
  另記在 `final_diff`。
- **FAIL→UNKNOWN 不算修好**；缺項／UNKNOWN／CONFLICT 不得宣告完成（unresolved 裡列明）。
- **任何原有 PASS 退步**（PASS→FAIL／PASS→UNKNOWN）都要記錄在 `regressed`，
  不能用淨改善掩蓋。
- **連續兩次修復沒有消除已確認缺口** ⇒ 停止，回傳停因（`stopped`）及未解決項
  （`unresolved`）。預算由本控制器管（輪數上限），不靠提示詞。
  停滯判據（P000-20261105-01）＝**相鄰輪可確認改善**：上一輪狀態（第 1 輪＝初始驗）
  中非 PASS 的必需項，本輪確認轉 PASS 才算進度；非必需項 FAIL→PASS、FAIL→UNKNOWN
  不算進度、不重置停滯計數。
- **成本**：wall_ms／呼叫數由執行器（`run_agent`）實際攔截；token 從 agent 原始
  stdout 的 usage 讀，缺值＝UNKNOWN（None），**絕不填 0**。
  `cost.calls`＝修復 session（agent 啟動）數；`cost.model_calls`＝**實際模型 API 呼叫數**
  （各輪原始 stdout 的 usage 事件數），兩者不是一回事，絕不拿 session 數頂替。
  **任一輪 usage 缺值 ⇒ 總成本（model_calls/tokens）＝UNKNOWN**，已知部分不得被當成
  完整總和呈現（已知部分仍逐輪記錄在 `rounds[].usage`）。
- **自造 G1 案例**只用於離線修復單元測試，標 `synthetic=True`；不作為 G2 效果。
- 原型保持 opt-in：不改任何預設使用者流程；不呼叫本模組時系統行為不變。

呼叫契約（注入用，測試／換執行器用）：
    build(prompt: str, workspace: Path) -> Launch
    run(launch, *, workspace: Path, timeout_s: float, log_dir: Path) -> dict
    （與 `adapters.agents.pi_build`／`adapters.run.run_agent` 同簽名）

CLI（可重跑的原生 pi 命令；provider/model 用既有 pi 設定，不輸出憑證）：
    .venv/bin/python -m vacant_network.reqloop.repair \
        --task <task_dir> --draft <draft_dir> \
        --provider lms1003qwen --model qwen/qwen3.8-27b \
        --out <dir> --rounds 2 --timeout 300 --synthetic

一條指令離線 selftest（只驗管線，不宣稱效果；synthetic G1 案例＋fake agent，
零模型呼叫、零網路、不碰任何凍結 manifest）：
    .venv/bin/python -m vacant_network.reqloop.repair --selftest
    逐條驗 11/04 紅線（兩臂反饋差異、FAIL→PASS=fixed、FAIL→UNKNOWN 不算修好、
    PASS→FAIL 記錄、停滯停因、無缺口零呼叫、成本缺值 UNKNOWN、退出碼 0/20）；
    全過 ⇒ 退出碼 0，任一不過 ⇒ 1。
退出碼（照 `vacant run` 慣例）：0＝缺口關閉或無缺口；20＝跑過但缺口未閉；
22＝agent 應該跑但一次都沒跑起來（infra）。no_gap 但仍有未驗證項
（UNKNOWN/缺項）＝零呼叫是設計，退出碼 20（未驗證、拒收），不是 22。

真草稿冒煙（G2，工單 P000-20261104-02，2026-11-04）新增兩個參數：
- min_rounds：無已確認缺口時也至少跑幾輪（generic 臂＝1：對的草稿也要重驗，
  看會不會被改壞；localized 臂＝0：缺口驅動，無缺口＝0 模型呼叫）。預設 0，行為不變。
- include_dirs：把任務目錄下白名單子目錄（如 data/）帶進工作區；白名單外的
  子目錄（good/、bad_*/ 參考答案）仍然永不入場。
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
from typing import Any, Callable

from vacant_network.intake.verifiers import ClaimResult
from vacant_network.reqloop.checks import run_requirement_checks
from vacant_network.reqloop.requirements import RequirementSet

FEEDBACK_MODES = ("generic", "localized")

#: 可注入的呼叫型別
BuildFn = Callable[[str, pathlib.Path], Any]
RunFn = Callable[..., dict[str, Any]]

#: 停因（回傳給上層，不得省略）
STOP_NO_GAP = "no_gap"                # 原本就沒有必需條目 FAIL：零呼叫
STOP_GAP_CLOSED = "gap_closed"        # 重驗後無必需條目 FAIL
STOP_STALLED = "stalled"             # 連續兩次修復沒有消除已確認缺口
STOP_MAX_ROUNDS = "max_rounds"       # 輪數用盡，缺口仍在

_STALL_LIMIT = 2  # 連續兩次無進展即停（規則原文）


# ── 前後差異 ──────────────────────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class RepairDiff:
    """一次修復前後的需求狀態差異。四態口徑，不算「淨改善」。"""
    fixed: tuple[str, ...]                     # FAIL→PASS
    not_fixed: tuple[str, ...]                 # FAIL→FAIL／FAIL→UNKNOWN／FAIL→CONFLICT／缺項
    regressed: tuple[str, ...]                 # PASS→FAIL／PASS→UNKNOWN／PASS→CONFLICT／缺項
    transitions: dict[str, tuple[str, str]]    # claim_id → (before, after)；缺項記 "MISSING"
    required_fail_before: int
    required_fail_after: int
    closed_any_gap: bool                        # 至少一條 FAIL→PASS（FAIL→UNKNOWN 不算，規則原文）

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _status_map(results: list[ClaimResult]) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in results:
        out[c.claim_id] = c.status
    return out


def _required_all_pass(req_set: RequirementSet, results: list[ClaimResult]) -> bool:
    """缺口關閉的唯一口徑：**每條必需條目都明確 PASS**。

    FAIL→UNKNOWN 不算修好；缺項（MISSING）不算 PASS（照 run_g1 的 required_verified 口徑）。
    """
    am = _status_map(results)
    required = [i.id for i in req_set.items if i.required]
    return bool(required) and all(am.get(cid) == "PASS" for cid in required)


def diff_results(before: list[ClaimResult], after: list[ClaimResult]) -> RepairDiff:
    """前後兩輪 ClaimResult 的逐條差異。

    口徑（規則原文）：FAIL→UNKNOWN 不算修好；PASS→非 PASS 一律是退步、必須記錄；
    重驗後缺項＝MISSING，不是 PASS 也不是「沒有」。
    """
    bm = _status_map(before)
    am = _status_map(after)
    fixed: list[str] = []
    not_fixed: list[str] = []
    regressed: list[str] = []
    transitions: dict[str, tuple[str, str]] = {}
    for cid, b in bm.items():
        a = am.get(cid, "MISSING")
        transitions[cid] = (b, a)
        if b == "FAIL":
            if a == "PASS":
                fixed.append(cid)
            else:  # FAIL→FAIL／FAIL→UNKNOWN／FAIL→CONFLICT／缺項：都沒修好
                not_fixed.append(cid)
        elif b == "PASS" and a != "PASS":
            regressed.append(cid)
    rf_b = sum(1 for c in before if c.required and c.status == "FAIL")
    rf_a = sum(1 for c in after if c.required and c.status == "FAIL")
    return RepairDiff(
        fixed=tuple(fixed), not_fixed=tuple(not_fixed), regressed=tuple(regressed),
        transitions=transitions,
        required_fail_before=rf_b, required_fail_after=rf_a,
        closed_any_gap=bool(fixed),
    )


# ── 修復請求（原生 pi 收到的提示）────────────────────────────────────

def build_repair_prompt(
    task_dir: str | pathlib.Path,
    req_set: RequirementSet,
    draft_dir: str | pathlib.Path,
    before: list[ClaimResult],
    *,
    feedback_mode: str = "localized",
    include_dirs: tuple[str, ...] = ("data",),
    prev_round_agent: dict[str, Any] | None = None,
) -> str:
    """組修復請求。只帶：相關原文、目前交付物、失敗證據（可見反例）、
    允許改的範圍、必須保持成立的條件。不帶任何隱藏答案／hidden／scorer。

    兩臂（G2 對照）：
    - `localized`：逐條 FAIL 的驗證結果＋可見反例＋已 PASS 條目（必須保持）。
    - `generic`：只有原始需求＋「再檢查修正一次」（對照臂，不帶失敗證據）。

    `prev_round_agent`（第 2+ 輪）：上一輪 agent 欄位。localized 臂若其
    `tool_loop_suspected` 非空，提示點名上一輪重複的工具與次數（針對性反迴圈
    指令）——effects_20261105 dabstep-23：通用「不要重複同一命令」行不足以打破
    ×117 迴圈，具體證據才讓模型知道該避免哪一條。generic 對照臂不使用（定義不變）。
    """
    if feedback_mode not in FEEDBACK_MODES:
        raise ValueError(f"feedback_mode must be one of {FEEDBACK_MODES}")
    t = pathlib.Path(task_dir)
    d = pathlib.Path(draft_dir)
    request_p = t / "request.md"
    request = request_p.read_text(encoding="utf-8").strip() if request_p.is_file() else ""
    if not request and req_set.items:
        quotes: list[str] = []
        for it in req_set.items:
            q = (it.quote or "").strip()
            if q and q not in quotes:
                quotes.append(q)
        request = "\n".join(quotes)

    declared_deliverables = {it.deliverable for it in req_set.items if it.deliverable}
    task_rels: set[str] = set()
    if t.is_dir():
        for p in t.iterdir():
            if p.is_file() and p.name not in declared_deliverables:
                task_rels.add(p.name)
        for dd in include_dirs:
            dpath = t / dd
            if dpath.is_dir():
                for p in dpath.rglob("*"):
                    if p.is_file():
                        rel = str(p.relative_to(t))
                        if rel not in declared_deliverables:
                            task_rels.add(rel)

    draft_files = sorted(
        str(p.relative_to(d)) for p in d.rglob("*")
        if p.is_file() and str(p.relative_to(d)) not in task_rels
    ) if d.is_dir() else []
    # 工作區裡的「參考檔」＝task 目錄的顶层檔案（源資料、契約檔）；交付物檔與控制器內部 requirements.json 不在此列
    ref_files = sorted(
        p.name for p in t.iterdir()
        if p.is_file() and p.name != "requirements.json"
    ) if t.is_dir() else []
    draft_names = {pathlib.Path(f).name for f in draft_files}
    ref_files = [f for f in ref_files if f not in draft_names] or ref_files

    by_id = {c.claim_id: c for c in before}
    lines: list[str] = []
    lines.append("【原始需求（使用者原文）】")
    lines.append(request if request else "（缺 request.md）")
    lines.append("")
    lines.append("【目前交付物檔案（可以修改；若原始需求要求的交付物不存在，請依需求建立它）】")
    lines.append("\n".join(f"- {f}" for f in draft_files) if draft_files else "- （無）")
    ref_all = list(ref_files)
    for dd in include_dirs:
        dpath = t / dd
        if dpath.is_dir():
            ref_all += sorted(f"{dd}/{p.name}" for p in dpath.iterdir() if p.is_file())
    if ref_all:
        lines.append("")
        lines.append("【工作區裡的參考資料（可讀、不可改）】")
        lines.append("\n".join(f"- {f}" for f in ref_all))

    lines.append("")
    lines.append("【工作區邊界】所有操作僅限於當前工作目錄；交付物請在當前工作目錄建立或修改，請勿遍歷或讀取工作區外部目錄。")
    lines.append("【環境說明】本工作環境已安裝 scipy/numpy 等科學運算庫；需要的函式庫已安裝時請直接調用產出交付物，"
                 "不得因草稿內過時的註解或文字假設套件缺失而手刻替代演算法；某套件是否可用，以實際 import 的結果為準。")

    if feedback_mode == "localized":
        lines.append("")
        lines.append("【逐條需求驗證結果（程式重算，非模型自評）】")
        for item in req_set.items:
            c = by_id.get(item.id)
            if c is None:
                continue
            lines.append(f"- [{c.status}] {item.id}：{item.quote}")
            if c.status != "PASS":
                lines.append(f"  驗證結果：{_cap_prompt_text(c.detail)}")
                if c.evidence:
                    ev = json.dumps(c.evidence, ensure_ascii=False, default=str)
                    lines.append(f"  可見反例：{_cap_prompt_text(ev)}")
        lines.append("")
        lines.append("【必須保持成立的條件】")
        keep = [i.id for i in req_set.items
                if by_id.get(i.id) is not None and by_id[i.id].status == "PASS"]
        lines.append(
            ("以下條目已 PASS，修正後必須仍然 PASS：" + "、".join(keep))
            if keep else "（沒有已 PASS 的條目）")
        lines.append("只修上面的缺口，不要重寫不相關的部分；改完後所有必需條目都要能通過重驗。")
        lines.append("若同一條驗證命令重跑仍得相同結果，不要重複同一命令："
                     "換一種計算方式（重新檢查過濾條件與公式），與重算值一致後才產出交付物。")
        # 上一輪工具死迴圈觀察 → 本輪針對性指令（點名工具＋次數＋命令例）。
        # 只 localized 臂：generic 對照臂定義＝不帶任何逐輪觀察（保持兩臂差異乾淨）。
        # 只帶執行觀察，不帶需求失敗證據或重算值；不影響重驗／停滯判定。
        loop = (prev_round_agent or {}).get("tool_loop_suspected")
        if isinstance(loop, dict) and loop:
            lines.append(_loop_warning_line(loop))
    else:
        lines.append("")
        lines.append("請對照原始需求，重新檢查並修正工作區裡的交付物檔案一次。")
        lines.append("若原始需求要求的交付物（例如 answer.txt）不存在，請依原始需求把它建立出來。")
    return "\n".join(lines)


# ── 工作區（原草稿保留）──────────────────────────────────────────────

def prepare_workspace(
    task_dir: str | pathlib.Path,
    draft_dir: str | pathlib.Path,
    out_root: str | pathlib.Path,
    *,
    round_n: int = 1,
    include_dirs: tuple[str, ...] = ("data",),
) -> pathlib.Path:
    """建立第 round_n 輪的工作目錄：task 顶层檔案（源資料等）＋白名單子目錄＋草稿檔案。

    原草稿目錄只讀；同名檔以草稿為準。task 底下的目錄（good／bad 等參考答案）不帶進
    工作區；只有 include_dirs 白名單裡的子目錄（如 data/）才進場。
    """
    t = pathlib.Path(task_dir)
    d = pathlib.Path(draft_dir)
    ws = pathlib.Path(out_root) / f"round_{round_n}"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    for p in sorted(t.iterdir()) if t.is_dir() else []:
        if p.is_file():
            shutil.copy2(p, ws / p.name)
    for dd in include_dirs:
        src = t / dd
        if src.is_dir():
            shutil.copytree(src, ws / dd, dirs_exist_ok=True)
    for p in sorted(d.rglob("*")) if d.is_dir() else []:
        if p.is_file():
            dest = ws / p.relative_to(d)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
    if round_n >= 2:
        # 累積修復第 2+ 輪（d 為上一輪工作區）：確保權威來源檔案不被上一輪可能污染的副本覆寫
        for p in sorted(t.iterdir()) if t.is_dir() else []:
            if p.is_file():
                shutil.copy2(p, ws / p.name)
        for dd in include_dirs:
            src = t / dd
            if src.is_dir():
                shutil.copytree(src, ws / dd, dirs_exist_ok=True)
    return ws


# ── 成本 ──────────────────────────────────────────────────────────────

_USAGE_INPUT_KEYS = ("input", "inputTokens", "input_tokens", "promptTokens", "prompt_tokens")
_USAGE_OUTPUT_KEYS = ("output", "outputTokens", "output_tokens",
                      "completionTokens", "completion_tokens")


def _usage_int(u: dict, keys: tuple[str, ...]) -> int | None:
    for k in keys:
        v = u.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return int(v)
    return None


def parse_usage_from_log(log_path: str | pathlib.Path) -> dict[str, int] | None:
    """從 agent 的 stdout 原始輸出讀 usage（成本必須來自實際執行攔截／原始輸出）。

    支援兩種格式：
    - 單一 JSON 物件，頂層 `usage` 欄位；
    - JSONL 事件流（pi `--mode json`）：逐行解析，對每個含 `usage` 的事件
      把 input/output 加總（一次 agent 執行可能有多個 API 呼叫）。

    讀到真實 token 數才回傳 {"input","output","total","calls"}；沒有／解析不出／全為 0
    ＝None（呼叫端標 UNKNOWN）。**缺值不填 0。**

    calls＝本檔中「帶真實 usage 的事件數」——每個 usage 事件＝一次模型 API 呼叫。
    這是從原始輸出數出來的真實量，不是修復 session 數（agent 啟動次數：一次啟動
    可含多次 API 呼叫，也可能 0 次）。"""
    p = pathlib.Path(log_path)
    try:
        text = p.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not text:
        return None
    parsed: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            parsed.append(obj)
    # 真實 `pi --mode json` 事件流：每次 assistant LLM API 回應結束時，會送出一個
    # `type="message_end", message={"role":"assistant","usage":...}`；而流式過程中
    # `type="message_update"` 會在 text_delta/toolcall_delta 帶 `usage={input:0, output:0}`，
    # 並在同一次回應同時含文字與工具呼叫時於 text_end 與 toolcall_end 重複攜帶同一份 usage。
    # 故若事件流含 assistant message_end usage，優先以其為準（1 個 message_end＝1 次真實 API 呼叫）；
    # 否則退回掃描頂層 `obj["usage"]`（相容單一 JSON 或精簡測試事件流），且忽略全 0 streaming delta。
    msg_end_usages: list[dict] = []
    for obj in parsed:
        if obj.get("type") == "message_end":
            msg = obj.get("message")
            if isinstance(msg, dict) and msg.get("role") in ("assistant", None):
                u = msg.get("usage")
                if isinstance(u, dict):
                    msg_end_usages.append(u)
    usage_candidates = msg_end_usages if msg_end_usages else [
        obj["usage"] for obj in parsed if isinstance(obj.get("usage"), dict)
    ]
    tin = tout = n_calls = 0
    seen = False
    for u in usage_candidates:
        i = _usage_int(u, _USAGE_INPUT_KEYS)
        o = _usage_int(u, _USAGE_OUTPUT_KEYS)
        if i is None and o is None:
            continue
        if (i or 0) <= 0 and (o or 0) <= 0:
            continue
        seen = True
        n_calls += 1
        tin += i or 0
        tout += o or 0
    if not seen or (tin == 0 and tout == 0):
        return None
    return {"input": tin, "output": tout, "total": tin + tout, "calls": n_calls}


# 修復請求中單段驗證詳情／反例的長度上限：過長 JSON 對小模型是過載（
# effects_20261105 假設：localized 長反例＋保持清單誘發過度驗證／工具迴圈）。
_PROMPT_TEXT_CAP = 800


def _cap_prompt_text(s: str) -> str:
    """截斷修復請求裡的單段詳情／反例；截斷必須可見（不得靜默丟棄資訊）。"""
    s = (s or "").strip()
    if len(s) <= _PROMPT_TEXT_CAP:
        return s
    return s[:_PROMPT_TEXT_CAP].rstrip() + f"…（已截斷，共 {len(s)} 字）"


def _loop_warning_line(loop: dict[str, Any]) -> str:
    """上一輪工具死迴圈觀察（detect_tool_loop 回傳值）→ localized 提示的針對性行。

    與提示裡既有的通用行（「不要重複同一命令」）不同：點名上一輪實際重複的
    工具、次數與命令例，讓模型知道該避免**哪一條**。effects_20261105 證據：
    通用行已在提示中，dabstep-23-localized 仍 ×117 重複至超時——通用警告不足
    以打破迴圈。只帶執行觀察（工具名／參數／次數），不帶需求失敗證據或重算值；
    參數例截斷必須可見。
    """
    name = str(loop.get("tool_name") or "工具")
    reps = loop.get("consecutive_repetitions")
    reps = f" {reps}" if isinstance(reps, int) else ""
    try:
        args_text = json.dumps(loop.get("args"), ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        args_text = ""
    if args_text in ("", "{}"):
        example = ""
    else:
        if len(args_text) > 160:
            args_text = args_text[:160].rstrip() + "…"
        example = f"（例：{args_text}）"
    return (
        f"【上一輪執行觀察】上一輪偵測到 {name} 以相同參數連續執行{reps} 次、"
        f"中間沒有改動（疑似工具死迴圈）{example}。"
        "本輪禁止重複該命令；同一計算執行一次已得到結果後，直接以該結果推導並產出交付物，"
        "不要再次執行同一命令。"
    )


def detect_tool_loop(log_path: str | pathlib.Path, *, threshold: int = 4) -> dict[str, Any] | None:
    """偵測「工具死迴圈」：同一 (tool, args) 連續重複執行、中間沒有任何改動。

    來源（effects_20261105，dabstep-23-pi-C localized 兩階段皆敗）：模型把同一條
    python3 一行式重複執行 10 次以上（同 args、同結果、中間沒有寫檔）直到 300s
    預算耗盡，候選值全程未變。本函式把這個事實變機器可讀：
    - 依序掃 `tool_execution_start` 事件（pi --mode json JSONL）；
    - key＝(toolName, 正規化 args)；相鄰同 key 累積為一個「重複串」；
      中間出現不同 key（如 write／edit）即斷串——「改後重跑」是正常驗證，不是迴圈；
    - 最長串 ≥ threshold → 回傳 {"tool_name","args","consecutive_repetitions","threshold"}，
      否則 None（含無日誌）。

    這是觀察與標記，不是裁決：不改變任何 PASS/FAIL、停滯判定或退出碼；
    只記錄在該輪 agent 欄位（`tool_loop_suspected`），讓審計不必人讀 1MB 日誌。
    缺值＝None，不填假值。
    """
    p = pathlib.Path(log_path)
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    best: tuple[str, Any] | None = None
    best_streak = 0
    cur_key: tuple[str, Any] | None = None
    cur_streak = 0
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict) or obj.get("type") != "tool_execution_start":
            continue
        key = (str(obj.get("toolName")), obj.get("args"))
        if key == cur_key:
            cur_streak += 1
        else:
            cur_key = key
            cur_streak = 1
        if cur_streak > best_streak:
            best_streak = cur_streak
            best = key
    if best is None or best_streak < threshold:
        return None
    name, args = best
    return {"tool_name": name, "args": args,
            "consecutive_repetitions": best_streak, "threshold": threshold}


#: crash→放棄 偵測的崩潰簽名（effects_20261105 dabstep-1753 generic：
#: `NameError ... Command exited with code 1`，模型隨後把答案寫成「None」放棄）。
_CRASH_EXIT_RE = re.compile(r"Command exited with code (\d+)")
_CRASH_TRACEBACK_RE = re.compile(r"Traceback \(most recent call last\)")
# 注意：不能加 `\b` 前綴錨——pi --mode json 的日誌把換行轉義為字面 `\n`，
# 例外名可能緊接在字元 `n` 之後，`\b` 會漏掉（dabstep-1753 真實日誌即此形狀）。
_CRASH_EXC_RE = re.compile(
    r"(NameError|TypeError|AttributeError|KeyError|ValueError|IndexError"
    r"|ZeroDivisionError|SyntaxError|UnboundLocalError|ModuleNotFoundError)\s*:")
#: 最終答案＝放棄詞（strip+lower 比對）：空、None、N/A、Not Applicable、No answer。
_GIVEUP_ANSWERS = {"", "none", "n/a", "not applicable", "no answer"}


def detect_crash_giveup(log_path: str | pathlib.Path,
                        answer_path: str | pathlib.Path,
                        *, max_signatures: int = 12) -> dict[str, Any] | None:
    """偵測「crash→放棄」：session 內腳本崩潰，最終答案卻是一句放棄詞。

    來源（effects_20261105，dabstep-1753-pi-C generic 兩輪）：r1 腳本 NameError
    crash → 答「Not Applicable」；r2 四次 NameError crash → 答「None」＝模型在
    崩潰後放棄、沒有重試，300s 預算被反覆重寫腳本耗掉。
    - 條件一：該輪答案檔是放棄詞（空、None、N/A、Not Applicable、No answer）；
    - 條件二：agent 日誌有崩潰證據（非零 `Command exited with code N`、
      Python traceback、常見例外行）。
    兩者皆具 → 回傳 {"giveup_answer","crash_event_count","crash_signatures"}；
    任一缺 → None（不假設因果；無日誌／無答案檔同為 None＝缺值不造假）。

    這是觀察與標記，不是裁決：不改變任何 PASS/FAIL、停滯判定或退出碼；
    只記錄在該輪 agent 欄位（`crash_giveup_suspected`）。合法答案恰好是
    「None」時此標記可能為假陽性——審計時看 crash_signatures 自行裁決。
    """
    try:
        answer = pathlib.Path(answer_path).read_text(encoding="utf-8",
                                                     errors="replace").strip()
    except OSError:
        return None
    if answer.lower() not in _GIVEUP_ANSWERS:
        return None
    try:
        text = pathlib.Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    sigs: list[str] = []
    for m in _CRASH_EXIT_RE.finditer(text):
        if int(m.group(1)) != 0:
            sigs.append(m.group(0))
    sigs += _CRASH_TRACEBACK_RE.findall(text)
    sigs += _CRASH_EXC_RE.findall(text)
    if not sigs:
        return None
    uniq = sorted(set(sigs))
    return {
        "giveup_answer": answer,
        "crash_event_count": len(sigs),
        "crash_signatures": uniq[:max_signatures],
        "signatures_truncated": len(uniq) > max_signatures,
    }


# ── 單輪 ──────────────────────────────────────────────────────────────

@dataclasses.dataclass
class RepairRound:
    n: int
    feedback_mode: str
    workspace: str
    before: list[ClaimResult]
    after: list[ClaimResult]
    diff: RepairDiff
    agent: dict[str, Any]                 # rc／timed_out／wall_ms／spawn_error（執行器攔截）
    prompt_sha256: str
    usage: dict[str, int] | None          # None＝UNKNOWN
    error: str | None = None
    #: 來源改動（P000-20261105-02）：權威快照內檔案在工作區缺失或 hash 改變的相對路徑；
    #: 空＝未改。任何非空值＝該輪候選不可接受（控制器不得宣告缺口關閉）。
    source_tampered: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["before"] = [c.to_json() for c in self.before]
        d["after"] = [c.to_json() for c in self.after]
        return d


def create_authoritative_snapshot(
    task_dir: pathlib.Path,
    out_root: pathlib.Path,
    *,
    include_dirs: tuple[str, ...] = ("data",),
) -> pathlib.Path:
    """P000-20261105-02：控制器保存權威快照（重驗的來源基準）。

    把任務頂層檔案＋include_dirs 子樹逐位元組複製到 out_root/authoritative/，
    並寫 authoritative_manifest.json（relpath→sha256）。之後：
    - 重驗的來源資料與需求檔一律讀快照（agent 改工作區來源無效）；
    - 每輪用快照 hash 比對工作區，偵測來源改動。
    快照建一次、之後只讀；重驗與工作區準備都不得寫它。
    """
    import hashlib as _hashlib
    import json as _json
    snap = out_root / "authoritative"
    if snap.exists():
        shutil.rmtree(snap)
    snap.mkdir(parents=True)
    manifest: dict[str, str] = {}

    def _copy_one(src: pathlib.Path, rel: str) -> None:
        dst = snap / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        manifest[rel] = _hashlib.sha256(src.read_bytes()).hexdigest()

    for p in sorted(task_dir.iterdir()):
        if p.is_file():
            _copy_one(p, p.name)
    for d in include_dirs:
        src_dir = task_dir / d
        if src_dir.is_dir():
            for f in sorted(src_dir.rglob("*")):
                if f.is_file():
                    _copy_one(f, str(f.relative_to(task_dir)))
    (out_root / "authoritative_manifest.json").write_text(
        _json.dumps({"schema": "vacant.reqloop.authoritative/1",
                     "task": str(task_dir), "files": manifest},
                    ensure_ascii=False, indent=1),
        encoding="utf-8")
    return snap


def _source_tampered_files(authoritative: pathlib.Path, ws: pathlib.Path) -> tuple[str, ...]:
    """P000-20261105-02：偵測候選改寫權威來源（快照內檔案缺失或 hash 改變）。

    只比對快照內檔案（新交付物不在內，不誤報）；按相對路徑排序，確定性。
    """
    import hashlib as _hashlib
    bad: list[str] = []
    for rel, h in _load_manifest(authoritative).items():
        f = ws / rel
        if not f.is_file():
            bad.append(rel)
        elif _hashlib.sha256(f.read_bytes()).hexdigest() != h:
            bad.append(rel)
    return tuple(sorted(bad))


def _load_manifest(authoritative: pathlib.Path) -> dict[str, str]:
    """讀 authoritative_manifest.json（out_root 層）的 files 表。"""
    import json as _json
    man = _json.loads((authoritative.parent / "authoritative_manifest.json").read_text(encoding="utf-8"))
    return dict(man["files"])


def run_repair_round(
    n: int,
    task_dir: pathlib.Path,
    req_set: RequirementSet,
    draft_dir: pathlib.Path,
    before: list[ClaimResult],
    *,
    out_root: pathlib.Path,
    build: BuildFn,
    run: RunFn,
    feedback_mode: str,
    timeout_s: float,
    include_dirs: tuple[str, ...] = ("data",),
    authoritative: pathlib.Path | None = None,
    prev_round_agent: dict[str, Any] | None = None,
) -> RepairRound:
    """一輪修復：新工作區 → 原生 pi → 重驗 → 差異。來源目錄不被改動。

    `prev_round_agent`（第 2+ 輪）：上一輪 agent 欄位（第 1 輪＝None）。localized
    臂若其 tool_loop_suspected 非空，本輪提示點名上一輪重複的工具與次數（針對性
    反迴圈指令）；generic 臂不受影響。只進提示，不改重驗／停滯／退出碼。

    累積修復（P000-20261105-01）：
    - `draft_dir`＝本輪來源目錄：第 1 輪為原草稿；第 N 輪（N≥2）為上一輪工作區
      （承接上一輪候選）。重驗與重驗證據一律以本輪工作區為準。
    - `before`＝上一輪狀態：第 1 輪為原草稿初始驗；第 N 輪為上一輪 after。
      故本輪 `diff`＝相鄰輪差異（before→after），提示也反映當前候選狀態。

    權威輸入（P000-20261105-02）：
    - `authoritative`＝控制器保存的權威快照目錄（來源資料＋需求檔）。
      重驗的來源一律讀快照、產物才讀候選工作區；給 `task_dir` 的舊呼叫方式
      （工作區同時當來源）已禁用，防止 agent 改寫來源迎合交付。
    - 重驗後比對快照：快照內檔案在工作區缺失或 hash 改變＝來源改動，
      記錄在 `source_tampered`（逐輪），由控制器裁決為不可接受。
    """
    if authoritative is None:
        # 防呆：舊語義（工作區同時當來源）正是 P000-20261105-02 要堵的洞。
        # 本函式是內部入口，唯一合法呼叫方是 repair_slice（會傳快照）。
        raise ValueError(
            "run_repair_round 需要 authoritative（權威快照目錄）："
            "來源必須讀控制器保存的快照，不可用候選工作區當來源"
        )
    ws = prepare_workspace(task_dir, draft_dir, out_root,
                           round_n=n, include_dirs=include_dirs)
    prompt = build_repair_prompt(authoritative, req_set, draft_dir, before,
                                 feedback_mode=feedback_mode, include_dirs=include_dirs,
                                 prev_round_agent=prev_round_agent)
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    launch = build(prompt, ws)
    log_dir = pathlib.Path(out_root) / f"agent_round_{n}"
    try:
        agent = run(launch, workspace=ws, timeout_s=timeout_s, log_dir=log_dir)
        error = agent.get("spawn_error")
    except Exception as e:  # noqa: BLE001 — agent 崩潰＝該輪無進展，如實記錄
        agent = {"rc": None, "timed_out": False, "wall_ms": None,
                 "spawn_error": f"{type(e).__name__}: {e}"}
        error = agent["spawn_error"]
    # 重驗：來源讀權威快照（控制器保存），交付物才讀候選工作區
    # （P000-20261105-02：agent 改寫工作區來源不得翻 FAIL→PASS）
    after = run_requirement_checks(authoritative, req_set, ws)
    diff = diff_results(before, after)
    usage = parse_usage_from_log(log_dir / "agent_stdout.log")
    # 工具死迴圈觀察（effects_20261105 dabstep-23）：同一命令連續重複＝疑似迴圈。
    # 觀察與標記，不是裁決：不改變重驗結果與停滯判定（None＝未偵測到）。
    agent = {**agent, "tool_loop_suspected": detect_tool_loop(log_dir / "agent_stdout.log")}
    # crash→放棄觀察（effects_20261105 dabstep-1753 generic）：session 內崩潰＋
    # 最終答案是放棄詞（None/Not Applicable…）⇒ 標記。觀察與標記，不是裁決：
    # 不改變重驗結果與停滯判定（None＝未偵測到）。
    agent = {**agent,
             "crash_giveup_suspected":
             detect_crash_giveup(log_dir / "agent_stdout.log", ws / "answer.txt")}
    tampered = _source_tampered_files(authoritative, ws)
    return RepairRound(
        n=n, feedback_mode=feedback_mode, workspace=str(ws),
        before=before, after=after, diff=diff, agent=agent,
        prompt_sha256=prompt_sha, usage=usage, error=error,
        source_tampered=tampered,
    )


# ── 切片（有上限的執行入口）──────────────────────────────────────────

@dataclasses.dataclass
class RepairOutcome:
    synthetic: bool                       # G1 自造案例＝True（只作接線，不作效果）
    task_dir: str
    original_draft_dir: str               # 原候選，全程未改
    feedback_mode: str
    max_rounds: int
    rounds: list[RepairRound]
    final_status: dict[str, str]          # 最後一次重驗的逐條狀態
    stopped: str                          # 停因（見 STOP_*）
    fixed: tuple[str, ...]
    regressed: tuple[str, ...]
    unresolved: tuple[str, ...]           # 非 PASS（含 UNKNOWN／CONFLICT／缺項）
    final_diff: RepairDiff                # 原始級差異（原草稿初始驗→最終重驗）
    cost: dict[str, Any]
    draft_sha256: str                     # 原草稿目錄內容指紋（保留證據）
    #: 來源改動（P000-20261105-02）：任一輪候選改寫權威來源（快照內檔案缺失或 hash 改變）
    #: 即為 True；True 時本候選不可接受（退出碼 20），不得宣告缺口關閉。
    source_tampered: bool
    source_tampered_files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["rounds"] = [r.to_dict() for r in self.rounds]
        return d


def _dir_sha256(d: pathlib.Path) -> str:
    h = hashlib.sha256()
    for p in sorted(d.rglob("*")) if d.is_dir() else []:
        if p.is_file():
            h.update(str(p.relative_to(d)).encode("utf-8"))
            h.update(p.read_bytes())
    return h.hexdigest()


def repair_slice(
    task_dir: str | pathlib.Path,
    req_set: RequirementSet,
    draft_dir: str | pathlib.Path,
    out_root: str | pathlib.Path,
    build: BuildFn,
    run: RunFn,
    feedback_mode: str = "localized",
    *,
    max_rounds: int = 2,
    timeout_s: float = 300.0,
    synthetic: bool = False,
    min_rounds: int = 0,
    include_dirs: tuple[str, ...] = ("data",),
) -> RepairOutcome:
    """有上限的修復入口（預算由這裡管，不靠提示詞）。

    累積修復（P000-20261105-01）：第 1 輪從**原草稿**起新工作區（保留原候選）；
    第 N 輪（N≥2）承接第 N−1 輪工作區的候選與該輪已驗證狀態——不是每輪重抽原草稿。
    停滯按「相鄰輪可確認改善」計算：上一輪狀態（第 1 輪＝初始驗）中非 PASS 的必需項
    本輪確認轉 PASS 才算進度；連續兩輪無可確認改善即停（STOP_STALLED）；無缺口則零呼叫。

    min_rounds（真草稿冒煙，2026-11-04）：無已確認缺口時也至少跑幾輪。
    - localized（預設 0）：無缺口 ⇒ 0 模型呼叫（缺口驅動）。
    - generic（傳 1）：無缺口也重驗一次（看對的草稿會不會被改壞）。

    權威輸入（P000-20261105-02）：重驗的來源資料與需求一律讀本函式保存的權威快照
    （out_root/authoritative/＋authoritative_manifest.json），產物才讀候選工作區——
    agent 改寫工作區來源（CSV／requirements.json）不得翻 FAIL→PASS；任一輪來源改動
    記錄在 source_tampered（不可接受，退出碼 20），且不得宣告缺口關閉。
    """
    if feedback_mode not in FEEDBACK_MODES:
        raise ValueError(f"feedback_mode must be one of {FEEDBACK_MODES}")
    if max_rounds < 1:
        raise ValueError("max_rounds must be >= 1")
    if not 0 <= min_rounds <= max_rounds:
        raise ValueError("min_rounds must be in 0..max_rounds")
    t_dir = pathlib.Path(task_dir)
    d_dir = pathlib.Path(draft_dir)
    o_root = pathlib.Path(out_root)
    o_root.mkdir(parents=True, exist_ok=True)

    # 權威快照（P000-20261105-02）：重驗的來源基準，建一次、之後只讀。
    # 之後：重驗的來源一律讀快照（agent 改工作區來源無效）；每輪用快照 hash
    # 比對工作區，偵測來源改動。
    auth = create_authoritative_snapshot(t_dir, o_root, include_dirs=include_dirs)

    # 初始驗（原草稿）：來源讀權威快照，交付物讀原草稿
    before = run_requirement_checks(auth, req_set, d_dir)
    req_fail = [c.claim_id for c in before if c.required and c.status == "FAIL"]
    rounds: list[RepairRound] = []
    stalled = 0
    stopped = STOP_MAX_ROUNDS
    if not req_fail and min_rounds == 0:
        # 沒有已確認缺口（必需條目沒有 FAIL）：不呼叫模型。
        # 注意：若有必需條目是 UNKNOWN／缺項，unresolved 仍會列出、退出碼非 0——不得宣告完成。
        stopped = STOP_NO_GAP
    else:
        # 累積修復（P000-20261105-01）：第 1 輪來源＝原草稿；第 N 輪（N≥2）來源＝
        # 上一輪工作區（承接候選）＋上一輪已驗證狀態（prev_after）。原草稿永不改動；
        # 每輪工作區 round_N/ 即該輪快照。
        source_dir = d_dir
        prev_after = before
        prev_round_agent: dict[str, Any] | None = None
        tamper_seen = False   # P000-20261105-02：任一輪來源改動即不可接受
        for n in range(1, max_rounds + 1):
            r = run_repair_round(
                n, t_dir, req_set, source_dir, prev_after,
                out_root=o_root, build=build, run=run,
                feedback_mode=feedback_mode, timeout_s=timeout_s,
                include_dirs=include_dirs,
                authoritative=auth,
                prev_round_agent=prev_round_agent,
            )
            rounds.append(r)
            prev_round_agent = r.agent   # 第 N+1 輪提示可點名第 N 輪的工具死迴圈觀察
            if r.source_tampered:
                tamper_seen = True
            # 缺口關閉：全部必需項 PASS，且全程無來源改動（P000-20261105-02：
            # 改來源迎合交付不得關閉缺口）
            if not tamper_seen and _required_all_pass(req_set, r.after):
                stopped = STOP_GAP_CLOSED
                break
            # 停滯決策（P000-20261105-01：按「相鄰輪可確認改善」計算）：
            # 進度＝上一輪狀態（第 1 輪＝初始驗）中非 PASS 的**必需**項，本輪確認轉 PASS。
            # 以下**不**算進度：
            # - 非必需項 FAIL→PASS：不是已確認缺口。若算進度，一次非必需修復會
            #   每輪都重置停滯預算，迴圈燒盡 max_rounds——預算紀律失效。
            # - FAIL→UNKNOWN：紅線明列不算修好（不得用狀態變化偽裝進度）。
            # - 來源改動輪（P000-20261105-02）：不可接受，不算進度。
            prev_map = _status_map(prev_after)
            newly = {c.claim_id for c in r.after
                     if c.required and c.status == "PASS"
                     and prev_map.get(c.claim_id) != "PASS"}
            if newly and not r.source_tampered:
                stalled = 0
            else:
                stalled += 1
                if stalled >= _STALL_LIMIT:
                    stopped = STOP_STALLED
                    break
            # 下一輪承接本輪候選與本輪狀態（累積，不重抽原草稿）
            source_dir = pathlib.Path(r.workspace)
            prev_after = r.after

    last_after = rounds[-1].after if rounds else before
    final_status = _status_map(last_after)
    # 原始級差異（P000-20261105-01）：原草稿初始驗→最終重驗。逐輪 diff 是相鄰輪差異；
    # 此處記錄整段相對原草稿的淨變化（fixed 與 regressed 不得相互掩蓋）。
    final_diff = diff_results(before, last_after)
    # 缺項（在需求裡但最後重驗沒有）＝UNKNOWN 口徑，不得宣告完成
    for item in req_set.items:
        final_status.setdefault(item.id, "MISSING")
    unresolved = tuple(cid for cid, st in final_status.items() if st != "PASS")

    # 缺口真正修好＝最初為 FAIL 且最終重驗明確為 PASS（嚴禁未修好卻列入 fixed）
    initial_fail = {c.claim_id for c in before if c.status == "FAIL"}
    fixed = tuple(sorted(cid for cid in initial_fail if final_status.get(cid) == "PASS"))

    # 原有 PASS 退步＝最初為 PASS 且過程中或最終變為非 PASS（嚴禁淨改善掩蓋）
    initial_pass = {c.claim_id for c in before if c.status == "PASS"}
    regressed_set = {cid for r in rounds for cid in r.diff.regressed if cid in initial_pass}
    for cid in initial_pass:
        if final_status.get(cid) != "PASS":
            regressed_set.add(cid)
    regressed = tuple(sorted(regressed_set))

    # 來源改動（P000-20261105-02）：任一輪改寫權威來源即不可接受
    source_tampered = any(r.source_tampered for r in rounds)
    source_tampered_files = tuple(sorted({f for r in rounds for f in r.source_tampered}))

    calls = len(rounds)   # 修復 session 數（agent 啟動次數）——不是模型 API 請求數
    wall = [r.agent.get("wall_ms") for r in rounds]
    wall_total = sum(w for w in wall if isinstance(w, (int, float)))
    known = [r.usage for r in rounds if r.usage is not None]
    if calls == 0:
        # 零模型活動：0 次 API 呼叫是完整事實（agent 未啟動）；無 usage 來源 ⇒ tokens 仍 UNKNOWN
        model_calls: int | None = 0
        tokens: int | None = None
        token_source = "unavailable"
    elif len(known) == calls:
        # 每輪原始 usage 都在 ⇒ 總和是完整量；呼叫數從各輪原始 usage 事件數出
        model_calls = sum(u["calls"] for u in known)
        tokens = sum(u["total"] for u in known)
        token_source = "agent_stdout"
    else:
        # 至少一輪 usage 缺值 ⇒ 總成本不得把已知部分當完整總和 ⇒ UNKNOWN（P001-20261105-03）。
        # 已知部分仍逐輪記錄在 rounds[].usage，總和欄位不混已知/未知。
        model_calls = None
        tokens = None
        token_source = "partial" if known else "unavailable"
    cost: dict[str, Any] = {
        "calls": calls,             # 修復 session（agent 啟動）數，不是模型 API 請求數
        "model_calls": model_calls,  # 實際模型 API 呼叫數（各輪原始 stdout usage 事件數）；任一輪缺 ⇒ None（UNKNOWN）
        "wall_ms_total": int(wall_total) if wall_total else None,  # 無呼叫＝無 wall time
        "tokens": tokens,           # 全部輪 usage 齊全才是完整總和；任一輪缺 ⇒ None（不填 0）
        "token_source": token_source,  # agent_stdout | partial（部分輪缺）| unavailable（無任何輪有 usage 資料）
        "budget": {"max_rounds": max_rounds, "timeout_s_per_round": timeout_s,
                   "stall_limit": _STALL_LIMIT,
                   "note": "硬上限＝輪數×單輪 wall timeout＋輪數；無硬 token 限制能力，如實標記"},
    }
    return RepairOutcome(
        synthetic=synthetic,
        task_dir=str(t_dir),
        original_draft_dir=str(d_dir),
        feedback_mode=feedback_mode,
        max_rounds=max_rounds,
        rounds=rounds,
        final_status=dict(final_status),
        stopped=stopped,
        fixed=fixed,
        regressed=regressed,
        unresolved=unresolved,
        final_diff=final_diff,
        cost=cost,
        draft_sha256=_dir_sha256(d_dir),
        source_tampered=source_tampered,
        source_tampered_files=source_tampered_files,
    )


# ── CLI：可重跑的原生 pi 命令 ────────────────────────────────────────

def pin_agent_python(launch: Any, *, python: str | os.PathLike | None = None) -> Any:
    """把修復 agent 的裸 `python`／`python3` pin 到明確直譯器（預設＝本程序 sys.executable）。

    根因（2026-11-04 dab_039 冒煙停因）：agent 的 bash 裡裸 `python3` 依 PATH 解析；
    venv 在 PATH 前但當時缺 scipy/numpy，模型誤判科學堆疊不可用，兩輪都未產出交付物。
    pin 是 env 層保證（不是提示詞）：PATH 首位＝修復器與驗證重算同一個直譯器。
    找不到該直譯器＝fail-open，不動 env。

    ⚠ 故意**不** resolve 符號連結：venv 的 bin/python 是指向基礎直譯器的 symlink，
    venv 的判定看的是「以哪條路徑啟動」（可執行檔目錄下的 pyvenv.cfg）；resolve 之後
    pin 到的就是基礎直譯器、venv 的 site-packages 全部失效。
    """
    py = pathlib.Path(os.path.abspath(str(python) if python is not None else sys.executable))
    if not py.is_file():
        return launch
    bindir = str(py.parent)
    old = launch.env.get("PATH") or os.environ.get("PATH", "")
    rest = [e for e in old.split(os.pathsep) if e and e != bindir]
    launch.env["PATH"] = os.pathsep.join([bindir, *rest])
    launch.env["VACANT_REPAIR_PYTHON"] = str(py)
    return launch


def _default_build(provider: str | None, model: str | None, hooks: bool = True):
    from vacant_network.adapters.agents import pi_build
    extra: list[str] = []
    if provider:
        extra += ["--provider", provider]
    if model:
        extra += ["--model", model]

    def build(prompt: str, ws: pathlib.Path):
        return pin_agent_python(pi_build(prompt, ws, hooks=hooks, extra=extra or None))
    return build


# ── selftest（一條指令、離線、synthetic；只驗管線，不宣稱效果）──────────

def _selftest_fake_build() -> BuildFn:
    """離線 stand-in（selftest 專用，零模型呼叫）。與 pi_build 同簽名。"""
    def build(prompt: str, ws: pathlib.Path) -> Any:
        from vacant_network.adapters.agents import Launch
        return Launch(argv=["true"], note="selftest-fake")
    return build


def _selftest_fake_agent(ws_files: dict[str, str] | None = None) -> RunFn:
    """離線 stand-in：把 ws_files 寫進工作區（模擬修復模型改交付物），零模型呼叫。"""
    def run(launch: Any, *, workspace: pathlib.Path, timeout_s: float,
            log_dir: pathlib.Path) -> dict[str, Any]:
        for name, text in (ws_files or {}).items():
            p = pathlib.Path(workspace) / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 1200, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}
    return run


def _selftest() -> int:
    """一條指令離線 selftest：synthetic G1 案例（expense_category）＋fake agent。

    逐條驗 11/04 紅線，輸出每條一行；全過 ⇒ 0，任一不過 ⇒ 1。
    不呼叫模型、不碰任何凍結 manifest（g2/g3 發射紅線不受影響）。
    """
    repo = pathlib.Path(__file__).resolve().parents[2]
    g1 = repo / "ops" / "reqloop" / "g1" / "tasks" / "expense_category"
    if not (g1 / "requirements.json").is_file():
        print(f"SELFTEST: FAIL — G1 synthetic 案例不存在：{g1}")
        return 1
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="vacant-repair-selftest-"))
    try:
        task_dir = tmp / "task"
        shutil.copytree(g1, task_dir)
        rs = RequirementSet.load(task_dir / "requirements.json")
        draft = task_dir / "bad_grand_total_wrong"
        before = run_requirement_checks(task_dir, rs, draft)
        failed = [c.claim_id for c in before if c.required and c.status == "FAIL"]
        if not failed:
            print("SELFTEST: FAIL — G1 案例應有 1 條必需 FAIL 項，實際 0（案例已變？需重凍結案例）")
            return 1
        good_summary = (task_dir / "good" / "summary.md").read_text(encoding="utf-8")
        broken_csv = "category,total_amount\nit,3380.25\n"   # 缺 subcategory 欄位（與測試同）
        draft_hash0 = _dir_sha256(draft)
        fake = _selftest_fake_build()

        results: list[tuple[str, str | None]] = []   # (說明, None=ok / 失敗原因)

        def check(name: str, cond: bool, reason: str = "斷言不成立") -> None:
            results.append((name, None if cond else reason))

        # 1) 兩臂反饋差異：localized 帶失敗條目＋可見反例；generic 不帶（對照必須真實）
        loc = build_repair_prompt(task_dir, rs, draft, before, feedback_mode="localized")
        gen = build_repair_prompt(task_dir, rs, draft, before, feedback_mode="generic")
        check("兩臂反饋差異（localized 帶反例與失敗條目；generic 不帶）",
              all(cid in loc for cid in failed)
              and "10674.83" in loc                       # 可見反例（重算的正確值）
              and not any(cid in gen for cid in failed)
              and "10674.83" not in gen)

        # 2) FAIL→PASS＝fixed；原草稿逐位元組保留；成本缺值＝UNKNOWN（不填 0）
        o2 = repair_slice(task_dir, rs, draft, out_root=tmp / "s2",
                          build=fake, run=_selftest_fake_agent({"summary.md": good_summary}),
                          feedback_mode="localized", max_rounds=2, synthetic=True)
        check("FAIL→PASS=fixed、原草稿未動、tokens 缺值=UNKNOWN",
              o2.stopped == STOP_GAP_CLOSED
              and set(failed) <= set(o2.fixed)
              and o2.unresolved == ()
              and _dir_sha256(draft) == draft_hash0
              and o2.cost["tokens"] is None)

        # 3) 來源改動＝不可接受（P000-20261105-02）：fake agent 弄壞工作區的來源
        #    expenses.csv（舊語義下重驗讀工作區來源→UNKNOWN）。新語義：重驗讀權威
        #    快照（來源未動→仍 FAIL）、改動記錄在 source_tampered、候選不可接受（20）。
        o3 = repair_slice(task_dir, rs, draft, out_root=tmp / "s3",
                          build=fake,
                          run=_selftest_fake_agent({"expenses.csv": "corrupted,not,a,valid\ngarbage"}),
                          feedback_mode="localized", max_rounds=1, synthetic=True)
        check("來源改動＝不可接受（重驗讀快照仍 FAIL、改動記錄、退出碼 20）",
              o3.stopped != STOP_GAP_CLOSED
              and o3.final_status[failed[0]] == "FAIL"
              and o3.source_tampered is True
              and "expenses.csv" in o3.source_tampered_files
              and all(cid not in o3.fixed for cid in failed)
              and _exit_code(o3) == 20)

        # 4) 原有 PASS 退步（PASS→FAIL）必須記錄在 regressed，不能淨改善掩蓋
        o4 = repair_slice(task_dir, rs, draft, out_root=tmp / "s4",
                          build=fake,
                          run=_selftest_fake_agent({"summary.md": good_summary,
                                                    "expense_summary.csv": broken_csv}),
                          feedback_mode="localized", max_rounds=1, synthetic=True)
        check("PASS→FAIL 記錄在 regressed",
              "req_csv_structure" in o4.regressed and o4.stopped != STOP_GAP_CLOSED)

        # 5) 連續兩次無進展 ⇒ 停止（2 輪，不是 4）；停因＋未解決項都回傳
        o5 = repair_slice(task_dir, rs, draft, out_root=tmp / "s5",
                          build=fake, run=_selftest_fake_agent(None),
                          feedback_mode="generic", max_rounds=4, synthetic=True)
        check("停滯停因＋未解決項（2 輪即停、不燒盡預算）",
              o5.stopped == STOP_STALLED and len(o5.rounds) == 2
              and all(cid in o5.unresolved for cid in failed))

        # 6) 無缺口：localized 零呼叫（缺口驅動）；generic 至少重驗 1 輪
        o6a = repair_slice(task_dir, rs, task_dir / "good", out_root=tmp / "s6a",
                           build=fake, run=_selftest_fake_agent(None),
                           feedback_mode="localized", max_rounds=2, synthetic=True)
        o6b = repair_slice(task_dir, rs, task_dir / "good", out_root=tmp / "s6b",
                           build=fake, run=_selftest_fake_agent(None),
                           feedback_mode="generic", max_rounds=2, min_rounds=1,
                           synthetic=True)
        check("無缺口：localized 0 呼叫／generic 1 呼叫",
              o6a.stopped == STOP_NO_GAP and o6a.cost["calls"] == 0
              and o6a.cost["wall_ms_total"] is None
              and o6b.cost["calls"] == 1)

        # 7) CLI 退出碼 0/20＋成本缺值顯示 UNKNOWN（不填 0）
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc_ok = main(["--task", str(task_dir), "--draft", str(draft),
                          "--out", str(tmp / "rc_ok"), "--rounds", "1", "--synthetic",
                          "--feedback-mode", "localized"],
                         build=fake, run=_selftest_fake_agent({"summary.md": good_summary}))
            rc_unverified = main(["--task", str(task_dir), "--draft", str(draft),
                                 "--out", str(tmp / "rc_unverified"), "--rounds", "1",
                                 "--synthetic", "--feedback-mode", "localized"],
                                build=fake,
                                run=_selftest_fake_agent({"expenses.csv": "corrupted,not,a,valid\ngarbage"}))
        text = buf.getvalue()
        check("退出碼 0（缺口關閉）/20（未驗證、拒收）＋tokens 顯示 UNKNOWN",
              rc_ok == 0 and rc_unverified == 20
              and "tokens=UNKNOWN" in text)

        # 8) 累積修復（P000-20261105-01）：bad_round_each_row 有兩個獨立必需 FAIL（
        #    分組重算＋報表總額）。fake agent 每輪只修一個缺口：若第 2 輪重抽原草稿，
        #    第 1 輪修好的 summary 會被覆蓋回去，兩個缺口永遠關不掉；只有第 2 輪
        #    承接第 1 輪候選，兩輪後才全部 PASS。
        draft2 = task_dir / "bad_round_each_row"
        draft2_hash0 = _dir_sha256(draft2)
        before2 = run_requirement_checks(task_dir, rs, draft2)
        f2 = [c.claim_id for c in before2 if c.required and c.status == "FAIL"]
        good_csv = (task_dir / "good" / "expense_summary.csv").read_text(encoding="utf-8")
        if len(f2) == 2:
            def run_one_per_round(launch: Any, *, workspace: pathlib.Path,
                                  timeout_s: float, log_dir: pathlib.Path) -> dict[str, Any]:
                ws = pathlib.Path(workspace)
                if (ws / "summary.md").read_text(encoding="utf-8") != good_summary:
                    (ws / "summary.md").write_text(good_summary, encoding="utf-8")  # 缺口①：只修 summary
                else:
                    (ws / "expense_summary.csv").write_text(good_csv, encoding="utf-8")  # 缺口②：只修 CSV
                log_dir.mkdir(parents=True, exist_ok=True)
                (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
                (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
                return {"rc": 0, "timed_out": False, "wall_ms": 100, "spawn_error": None,
                        "stdout_log": str(log_dir / "agent_stdout.log"),
                        "stderr_log": str(log_dir / "agent_stderr.log")}
            o8 = repair_slice(task_dir, rs, draft2, out_root=tmp / "s8",
                              build=fake, run=run_one_per_round,
                              feedback_mode="localized", max_rounds=2, synthetic=True)
            check("累積修復：兩個獨立缺口每輪修一個 ⇒ 兩輪後全 PASS（第 2 輪承接第 1 輪候選）",
                  o8.stopped == STOP_GAP_CLOSED
                  and set(f2) <= set(o8.fixed)
                  and o8.unresolved == ()
                  and len(o8.rounds) == 2
                  and o8.rounds[0].diff.closed_any_gap
                  and o8.rounds[1].diff.closed_any_gap
                  and _dir_sha256(draft2) == draft2_hash0,
                  f"stopped={o8.stopped} fixed={o8.fixed} unresolved={o8.unresolved}")
        else:
            check("累積修復：兩個獨立缺口每輪修一個 ⇒ 兩輪後全 PASS",
                  False,
                  f"G1 案例 bad_round_each_row 應有 2 條必需 FAIL，實際 {len(f2)}（案例已變？需重凍結案例）")

        # 9) 來源改動不得翻 FAIL→PASS（P000-20261105-02 驗收核心）：fake agent
        #    只改來源 CSV（把加總改成 bad 摘要的錯誤值）⇒ 缺口不得關閉、退出碼 20；
        #    對照：同一份改寫來源在舊語義（工作區當來源）下會翻 PASS——攻擊真實存在。
        import csv as _csv
        import io as _io
        import re as _re
        bad_md = (draft / "summary.md").read_text(encoding="utf-8")
        m = _re.search(r"報銷總金額：([\d,\.]+)", bad_md)
        target = float(m.group(1).replace(",", ""))
        src_text = (task_dir / "expenses.csv").read_text(encoding="utf-8")
        src_rows = list(_csv.DictReader(_io.StringIO(src_text)))
        src_sum = sum(float(r["amount"]) for r in src_rows)
        if abs(src_sum - target) > 0.005:
            src_rows[-1]["amount"] = f"{float(src_rows[-1]['amount']) + (target - src_sum):.4f}"
            cols = list(src_rows[0].keys())
            buf = _io.StringIO()
            w = _csv.DictWriter(buf, fieldnames=cols)
            w.writeheader()
            w.writerows(src_rows)
            tampered_src = buf.getvalue()
            # 攻擊真實性：舊語義（工作區同時當來源）下改來源能翻 PASS
            ws_probe = tmp / "probe_ws"
            ws_probe.mkdir(exist_ok=True)
            for f in ("summary.md", "expense_summary.csv"):
                shutil.copy(draft / f, ws_probe / f)
            (ws_probe / "expenses.csv").write_text(tampered_src, encoding="utf-8")
            old_sem = {c.claim_id: c.status for c in run_requirement_checks(ws_probe, rs, ws_probe)}
            new_sem = {c.claim_id: c.status for c in run_requirement_checks(task_dir, rs, ws_probe)}

            def run_tamper(launch: Any, *, workspace: pathlib.Path,
                           timeout_s: float, log_dir: pathlib.Path) -> dict[str, Any]:
                (pathlib.Path(workspace) / "expenses.csv").write_text(tampered_src, encoding="utf-8")
                log_dir.mkdir(parents=True, exist_ok=True)
                (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
                (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
                return {"rc": 0, "timed_out": False, "wall_ms": 50, "spawn_error": None,
                        "stdout_log": str(log_dir / "agent_stdout.log"),
                        "stderr_log": str(log_dir / "agent_stderr.log")}
            o9 = repair_slice(task_dir, rs, draft, out_root=tmp / "s9",
                              build=fake, run=run_tamper,
                              feedback_mode="localized", max_rounds=2, synthetic=True)
            check("改來源迎合交付不得翻 PASS（舊語義會 PASS、新語義仍 FAIL、改動記錄、拒收）",
                  old_sem[failed[0]] == "PASS" and new_sem[failed[0]] == "FAIL"
                  and o9.stopped != STOP_GAP_CLOSED
                  and failed[0] not in o9.fixed
                  and o9.source_tampered is True
                  and "expenses.csv" in o9.source_tampered_files
                  and _exit_code(o9) == 20,
                  f"old={old_sem[failed[0]]} new={new_sem[failed[0]]} stopped={o9.stopped}")
        else:
            check("改來源迎合交付不得翻 PASS", False,
                  f"G1 案例加總 {src_sum} 與 bad 摘要值 {target} 太接近，無法造真實攻擊（案例已變？需重凍結案例）")

        # 10) 驗證器程式不可由候選覆寫（P000-20261105-02）：候選寫同名 checks.py
        #     （恆 PASS）不改變裁決；新檔不計來源改動。
        shadow = (
            "def run_requirement_checks(*a, **k):\n"
            "    class _C:\n"
            "        claim_id = 'req_summary_numbers'\n"
            "        status = 'PASS'\n"
            "        detail = 'shadow'\n"
            "        evidence = {}\n"
            "    return [_C()]\n"
        )
        o10 = repair_slice(task_dir, rs, draft, out_root=tmp / "s10",
                           build=fake, run=_selftest_fake_agent({"checks.py": shadow}),
                           feedback_mode="localized", max_rounds=1, synthetic=True)
        check("候選覆寫驗證器無效（裁決不變、新檔不計來源改動、仍拒收）",
              o10.final_status[failed[0]] == "FAIL"
              and o10.stopped != STOP_GAP_CLOSED
              and o10.source_tampered is False
              and _exit_code(o10) == 20)

        # 11) 成本誠實（P001-20261105-03）：model_calls＝實際模型 API 呼叫數
        #     （各輪原始 stdout 的 usage 事件數），不是修復 session 數；任一輪 usage 缺值
        #     ⇒ 總成本（model_calls/tokens）＝UNKNOWN，不得把已知部分當完整總和。
        #     對照組：每輪都有 usage ⇒ 總和＝各輪 API 呼叫數的精確總和（3≠2 sessions）。
        usage_r1 = ('{"type": "message_update", "usage": {"input": 100, "output": 50}}\n'
                    '{"type": "message_update", "usage": {"input": 10, "output": 5}}\n')
        usage_r2 = '{"type": "message_update", "usage": {"input": 100, "output": 50}}\n'
        if len(f2) == 2:
            def make_usage_agent(usage: dict[int, str]) -> RunFn:
                def run(launch: Any, *, workspace: pathlib.Path,
                        timeout_s: float, log_dir: pathlib.Path) -> dict[str, Any]:
                    ws = pathlib.Path(workspace)
                    if (ws / "summary.md").read_text(encoding="utf-8") != good_summary:
                        (ws / "summary.md").write_text(good_summary, encoding="utf-8")
                    else:
                        (ws / "expense_summary.csv").write_text(good_csv, encoding="utf-8")
                    log_dir.mkdir(parents=True, exist_ok=True)
                    n = int(pathlib.Path(log_dir).name.rsplit("_", 1)[-1])
                    (log_dir / "agent_stdout.log").write_text(usage.get(n, "{}"), encoding="utf-8")
                    (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
                    return {"rc": 0, "timed_out": False, "wall_ms": 100, "spawn_error": None,
                            "stdout_log": str(log_dir / "agent_stdout.log"),
                            "stderr_log": str(log_dir / "agent_stderr.log")}
                return run
            o11a = repair_slice(task_dir, rs, draft2, out_root=tmp / "s11a",
                                build=fake, run=make_usage_agent({1: usage_r1}),
                                feedback_mode="localized", max_rounds=2, synthetic=True)
            o11b = repair_slice(task_dir, rs, draft2, out_root=tmp / "s11b",
                                build=fake,
                                run=make_usage_agent({1: usage_r1, 2: usage_r2}),
                                feedback_mode="localized", max_rounds=2, synthetic=True)
            check("成本誠實：任一輪 usage 缺⇒總成本 UNKNOWN（已知部分不當完整總和）；"
                  "每輪齊全⇒總和＝實際 API 呼叫數精確總和（非 session 數）",
                  o11a.stopped == STOP_GAP_CLOSED and len(o11a.rounds) == 2
                  and o11a.cost["calls"] == 2
                  and o11a.cost["model_calls"] is None
                  and o11a.cost["tokens"] is None
                  and o11a.cost["token_source"] == "partial"
                  and o11a.rounds[0].usage == {"input": 110, "output": 55, "total": 165, "calls": 2}
                  and o11a.rounds[1].usage is None
                  and o11b.cost["model_calls"] == 3
                  and o11b.cost["tokens"] == 315
                  and o11b.cost["token_source"] == "agent_stdout",
                  f"partial={o11a.cost} full={o11b.cost}")
        else:
            check("成本誠實：任一輪 usage 缺⇒總成本 UNKNOWN", False,
                  "G1 案例 bad_round_each_row 應有 2 條必需 FAIL（案例已變？需重凍結案例）")

        passed = sum(1 for _, err in results if err is None)
        print("G2 repair-slice SELFTEST（synthetic G1、離線、0 模型呼叫；只驗管線，不宣稱效果）")
        for i, (name, err) in enumerate(results, 1):
            print(f"  [{i}/{len(results)}] {'ok' if err is None else 'FAIL'} — {name}"
                  + ("" if err is None else f"（{err}）"))
        print(f"SELFTEST: {passed}/{len(results)} PASS")
        return 0 if passed == len(results) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)



def main(argv: list[str] | None = None, *,
         build: BuildFn | None = None,
         run: RunFn | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and "--selftest" in argv:
        return _selftest()
    ap = argparse.ArgumentParser(
        prog="python -m vacant_network.reqloop.repair",
        description="G2 局部修復切片：原生 pi 接收草稿與可見反例 → 修正 → 重驗 → 前後差異及成本。"
                    "原型 opt-in；不呼叫時系統行為不變。")
    ap.add_argument("--task", required=True, help="任務目錄（request.md＋requirements.json＋源資料）")
    ap.add_argument("--draft", required=True, help="待修草稿交付物目錄（保留、不改動）")
    ap.add_argument("--out", default=None, help="輸出根目錄（預設 /tmp 下新建）")
    ap.add_argument("--feedback-mode", choices=FEEDBACK_MODES, default="localized")
    ap.add_argument("--rounds", type=int, default=2, help="修復輪數上限（預設 2）")
    ap.add_argument("--min-rounds", type=int, default=None,
                    help="無已確認缺口時至少執行的輪數（預設：generic 臂為 1，localized 臂為 0）")
    ap.add_argument("--timeout", type=float, default=300.0, help="單輪 agent wall timeout（秒）")
    ap.add_argument("--provider", default=os.environ.get("VACANT_PI_PROVIDER"),
                    help="pi provider（預設讀 VACANT_PI_PROVIDER；不給＝pi 預設）")
    ap.add_argument("--model", default=os.environ.get("VACANT_PI_MODEL"),
                    help="pi model（預設讀 VACANT_PI_MODEL；不給＝provider 預設）")
    ap.add_argument("--include-dirs", nargs="*", default=["data"],
                    help="進工作區的子目錄白名單（預設 ['data']）")
    ap.add_argument("--no-hooks", action="store_true", help="pi 不載 Vacant 掛鉢")
    ap.add_argument("--synthetic", action="store_true",
                    help="此草稿為自造案例（G1）：本次只是離線接線測試，不作 G2 效果")
    ap.add_argument("--json", action="store_true", help="輸出 JSON（machine-readable）")
    args = ap.parse_args(argv)

    task_dir = pathlib.Path(args.task)
    draft_dir = pathlib.Path(args.draft)
    if not (task_dir / "requirements.json").is_file():
        print(f"error: {task_dir / 'requirements.json'} 不存在", flush=True)
        return 2
    req_set = RequirementSet.load(task_dir / "requirements.json")

    if build is None:
        build = _default_build(args.provider, args.model, hooks=not args.no_hooks)
    if run is None:
        from vacant_network.adapters.run import run_agent
        run = run_agent
    out_root = pathlib.Path(args.out) if args.out else \
        pathlib.Path(tempfile.mkdtemp(prefix="vacant-repair-"))

    min_rounds = args.min_rounds
    if min_rounds is None:
        min_rounds = 1 if args.feedback_mode == "generic" else 0

    include_dirs = tuple(args.include_dirs) if args.include_dirs else ()

    outcome = repair_slice(
        task_dir, req_set, draft_dir,
        out_root=out_root, build=build, run=run,
        feedback_mode=args.feedback_mode, max_rounds=args.rounds,
        timeout_s=args.timeout, synthetic=args.synthetic,
        min_rounds=min_rounds,
        include_dirs=include_dirs,
    )

    if args.json:
        print(json.dumps(outcome.to_dict(), ensure_ascii=False, indent=1, default=str))
    else:
        print(f"task      : {outcome.task_dir}")
        print(f"draft     : {outcome.original_draft_dir} (sha256 {outcome.draft_sha256[:16]}…, 保留未改)")
        print(f"mode      : {outcome.feedback_mode}  rounds={len(outcome.rounds)}/{outcome.max_rounds}  "
              f"synthetic={outcome.synthetic}")
        for r in outcome.rounds:
            b = {c.claim_id: c.status for c in r.before}
            a = {c.claim_id: c.status for c in r.after}
            changed = [f"{k}: {b[k]}→{a[k]}" for k in b if b.get(k) != a.get(k)]
            agent = r.agent
            agent_s = (f"rc={agent.get('rc')}" + (f" spawn_error={agent.get('spawn_error')}"
                                                   if agent.get("spawn_error") else "") +
                       (f" wall_ms={agent.get('wall_ms')}" if agent.get("wall_ms") is not None else ""))
            print(f"round {r.n}: {'；'.join(changed) if changed else '無狀態變化'}  [{agent_s}]")
        fs = outcome.final_status
        print("final   : " + "  ".join(f"{k}={v}" for k, v in fs.items()))
        if outcome.fixed:
            print(f"fixed   : {', '.join(outcome.fixed)}")
        if outcome.regressed:
            print(f"REGRESSED: {', '.join(outcome.regressed)}  ← 原有 PASS 退步，已記錄")
        if outcome.source_tampered:
            print(f"SOURCE_TAMPERED: {', '.join(outcome.source_tampered_files)}"
                  f"  ← 來源資料被改寫，不可接受（P000-20261105-02）")
        if outcome.unresolved:
            print(f"unresolved: {', '.join(outcome.unresolved)}")
        c = outcome.cost
        tokens_s = str(c["tokens"]) if c["tokens"] is not None else "UNKNOWN（缺值不填 0）"
        wall_s = str(c["wall_ms_total"]) if c["wall_ms_total"] is not None else "UNKNOWN"
        mc_s = str(c["model_calls"]) if c["model_calls"] is not None else "UNKNOWN（無原始 usage，不填 0）"
        print(f"cost    : sessions={c['calls']}  model_calls={mc_s}  wall_ms={wall_s}  tokens={tokens_s} "
              f"(source: {c['token_source']})")
        print(f"stopped : {outcome.stopped}")
    return _exit_code(outcome)


def _exit_code(outcome: RepairOutcome) -> int:
    # P000-20261105-02：來源改動＝不可接受，即使表面全 PASS 也拒收
    if outcome.source_tampered:
        return 20
    if outcome.stopped in (STOP_NO_GAP, STOP_GAP_CLOSED) and not outcome.unresolved:
        return 0
    if not outcome.rounds:
        # no_gap 但仍有未驗證項（UNKNOWN/缺項）：0 模型呼叫是**設計**（缺口驅動、
        # min_rounds=0），不是基建故障——22 保留給「agent 應該跑但沒跑起來」。把
        # 『未驗證』誤報成 infra 會誤導呼叫方重試/查基建；裁決是 20（未驗證、拒收）。
        return 20
    agent_ok = any(not r.agent.get("spawn_error") and r.agent.get("rc") is not None
                   for r in outcome.rounds)
    return 20 if agent_ok else 22


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
