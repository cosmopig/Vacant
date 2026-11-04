"""
G2 局部修復切片（工單 P000-20261104-01-repair-slice，2026-11-04）。

垂直切片（RLOOP_PLAN.md G2，11/04 方向）：
    原生 pi 接收草稿與可見反例 → 修正產物 → 重驗所有必要條目 → 輸出前後差異及成本。

重用既有元件（不重造契約／重試／收據）：
- `reqloop.requirements.RequirementSet` — 需求條目
- `reqloop.checks.run_requirement_checks` — G1 程式重算檢查器
- `intake.verifiers.ClaimResult` — 四態結果
- `adapters.agents.pi_build` + `adapters.run.run_agent` — 原生 pi 執行（CLI 預設）

規則（RD_FOCUS_20261104；本模組的每個行為都在此約束下）：
- **保留原候選**：原草稿目錄永遠不被改動；每一輪複製到新的工作目錄才讓 agent 動。
- **FAIL→UNKNOWN 不算修好**；缺項／UNKNOWN／CONFLICT 不得宣告完成（unresolved 裡列明）。
- **任何原有 PASS 退步**（PASS→FAIL／PASS→UNKNOWN）都要記錄在 `regressed`，
  不能用淨改善掩蓋。
- **連續兩次修復沒有消除已確認缺口**（必需條目 FAIL 數沒減少）⇒ 停止，
  回傳停因（`stopped`）及未解決項（`unresolved`）。預算由本控制器管（輪數上限），
  不靠提示詞。
  停滯判據＝原 FAIL 的**必需**項本輪新確認轉 PASS；非必需項 FAIL→PASS、
  FAIL→UNKNOWN、振蕩（修→退→再修同一項）都不算進度、不重置停滯計數。
- **成本**：wall_ms／呼叫數由執行器（`run_agent`）實際攔截；token 從 agent 原始
  stdout 的 usage 讀，缺值＝UNKNOWN（None），**絕不填 0**。
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
) -> str:
    """組修復請求。只帶：相關原文、目前交付物、失敗證據（可見反例）、
    允許改的範圍、必須保持成立的條件。不帶任何隱藏答案／hidden／scorer。

    兩臂（G2 對照）：
    - `localized`：逐條 FAIL 的驗證結果＋可見反例＋已 PASS 條目（必須保持）。
    - `generic`：只有原始需求＋「再檢查修正一次」（對照臂，不帶失敗證據）。
    """
    if feedback_mode not in FEEDBACK_MODES:
        raise ValueError(f"feedback_mode must be one of {FEEDBACK_MODES}")
    t = pathlib.Path(task_dir)
    d = pathlib.Path(draft_dir)
    request_p = t / "request.md"
    request = request_p.read_text(encoding="utf-8").strip() if request_p.is_file() else ""

    draft_files = sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file()) \
        if d.is_dir() else []
    # 工作區裡的「參考檔」＝task 目錄的顶层檔案（源資料、需求檔）；交付物檔不在此列
    ref_files = sorted(p.name for p in t.iterdir() if p.is_file()) if t.is_dir() else []
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
                lines.append(f"  驗證結果：{c.detail}")
                if c.evidence:
                    lines.append(f"  可見反例：{json.dumps(c.evidence, ensure_ascii=False, default=str)}")
        lines.append("")
        lines.append("【必須保持成立的條件】")
        keep = [i.id for i in req_set.items
                if by_id.get(i.id) is not None and by_id[i.id].status == "PASS"]
        lines.append(
            ("以下條目已 PASS，修正後必須仍然 PASS：" + "、".join(keep))
            if keep else "（沒有已 PASS 的條目）")
        lines.append("只修上面的缺口，不要重寫不相關的部分；改完後所有必需條目都要能通過重驗。")
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

    讀到真實 token 數才回傳 {"input","output","total"}；沒有／解析不出／全為 0＝None
    （呼叫端標 UNKNOWN）。**缺值不填 0。**
    """
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
    tin = tout = 0
    seen = False
    for obj in parsed:
        u = obj.get("usage")
        if not isinstance(u, dict):
            continue
        i = _usage_int(u, _USAGE_INPUT_KEYS)
        o = _usage_int(u, _USAGE_OUTPUT_KEYS)
        if i is None and o is None:
            continue
        seen = True
        tin += i or 0
        tout += o or 0
    if not seen or (tin == 0 and tout == 0):
        return None
    return {"input": tin, "output": tout, "total": tin + tout}


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

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["before"] = [c.to_json() for c in self.before]
        d["after"] = [c.to_json() for c in self.after]
        return d


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
) -> RepairRound:
    """一輪修復：新工作區 → 原生 pi → 重驗 → 差異。原草稿不被改動。"""
    ws = prepare_workspace(task_dir, draft_dir, out_root,
                           round_n=n, include_dirs=include_dirs)
    prompt = build_repair_prompt(task_dir, req_set, draft_dir, before,
                                 feedback_mode=feedback_mode, include_dirs=include_dirs)
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
    # 重驗：工作區同時是 task_dir（源資料在）和 deliverable_dir（交付物在）
    after = run_requirement_checks(ws, req_set, ws)
    diff = diff_results(before, after)
    usage = parse_usage_from_log(log_dir / "agent_stdout.log")
    return RepairRound(
        n=n, feedback_mode=feedback_mode, workspace=str(ws),
        before=before, after=after, diff=diff, agent=agent,
        prompt_sha256=prompt_sha, usage=usage, error=error,
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
    cost: dict[str, Any]
    draft_sha256: str                     # 原草稿目錄內容指紋（保留證據）

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

    每輪從**原草稿**起新工作區（保留原候選）；連續兩輪沒有消除已確認缺口
    （必需條目 FAIL 數沒減少）即停；無缺口則零呼叫。

    min_rounds（真草稿冒煙，2026-11-04）：無已確認缺口時也至少跑幾輪。
    - localized（預設 0）：無缺口 ⇒ 0 模型呼叫（缺口驅動）。
    - generic（傳 1）：無缺口也重驗一次（看對的草稿會不會被改壞）。
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

    before = run_requirement_checks(t_dir, req_set, d_dir)
    req_fail = [c.claim_id for c in before if c.required and c.status == "FAIL"]
    initial_req_fail = set(req_fail)
    confirmed: set[str] = set()   # 原 FAIL 的必需項中，已確認轉 PASS 的高水位
    rounds: list[RepairRound] = []
    stalled = 0
    stopped = STOP_MAX_ROUNDS
    if not req_fail and min_rounds == 0:
        # 沒有已確認缺口（必需條目沒有 FAIL）：不呼叫模型。
        # 注意：若有必需條目是 UNKNOWN／缺項，unresolved 仍會列出、退出碼非 0——不得宣告完成。
        stopped = STOP_NO_GAP
    else:
        for n in range(1, max_rounds + 1):
            r = run_repair_round(
                n, t_dir, req_set, d_dir, before,
                out_root=o_root, build=build, run=run,
                feedback_mode=feedback_mode, timeout_s=timeout_s,
                include_dirs=include_dirs,
            )
            rounds.append(r)
            if _required_all_pass(req_set, r.after):
                stopped = STOP_GAP_CLOSED
                break
            # 停滯決策（規則原文：「連續兩次修復沒有消除已確認缺口⇒停止」）：
            # 進度＝原 FAIL 的必需項本輪新確認轉 PASS。以下**不**算進度：
            # - 非必需項 FAIL→PASS：不是已確認缺口。若算進度，一次非必需修復會
            #   每輪都重置停滯預算（每輪 diff 對照原草稿，fixed 一直非空），迴圈燒盡
            #   max_rounds——預算紀律失效。
            # - FAIL→UNKNOWN：紅線明列不算修好（若用「必需 FAIL 數下降」計數式判據，
            #   弄壞資料檔把 FAIL 變 UNKNOWN 也能偽裝成『進度』）。
            # - 振蕩（修→退→再修同一項）：非新確認的修復，同樣不重置。
            newly = {c.claim_id for c in r.after
                     if c.required and c.status == "PASS"} & initial_req_fail
            if newly - confirmed:
                confirmed |= newly
                stalled = 0
            else:
                stalled += 1
                if stalled >= _STALL_LIMIT:
                    stopped = STOP_STALLED
                    break

    last_after = rounds[-1].after if rounds else before
    final_status = _status_map(last_after)
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

    calls = len(rounds)
    wall = [r.agent.get("wall_ms") for r in rounds]
    wall_total = sum(w for w in wall if isinstance(w, (int, float)))
    token_parts = [r.usage for r in rounds if r.usage is not None]
    if token_parts:
        tokens = sum(u.get("total", sum(v for v in u.values())) for u in token_parts)
        token_source = "agent_stdout"
    else:
        tokens = None          # UNKNOWN：缺值不填 0
        token_source = "unavailable"
    cost: dict[str, Any] = {
        "calls": calls,
        "model_calls": calls,   # 同一數量的明確名稱（G2 冒煙契約用 model_calls）
        "wall_ms_total": int(wall_total) if wall_total else None,  # 無呼叫＝無 wall time
        "tokens": tokens,
        "token_source": token_source,
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
        cost=cost,
        draft_sha256=_dir_sha256(d_dir),
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


def main(argv: list[str] | None = None, *,
         build: BuildFn | None = None,
         run: RunFn | None = None) -> int:
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
        if outcome.unresolved:
            print(f"unresolved: {', '.join(outcome.unresolved)}")
        c = outcome.cost
        tokens_s = str(c["tokens"]) if c["tokens"] is not None else "UNKNOWN（缺值不填 0）"
        wall_s = str(c["wall_ms_total"]) if c["wall_ms_total"] is not None else "UNKNOWN"
        print(f"cost    : calls={c['calls']}  wall_ms={wall_s}  tokens={tokens_s} "
              f"(source: {c['token_source']})")
        print(f"stopped : {outcome.stopped}")
    return _exit_code(outcome)


def _exit_code(outcome: RepairOutcome) -> int:
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
