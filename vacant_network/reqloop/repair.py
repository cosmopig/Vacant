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
    run(launch, *, workspace: Path, timeout_s: float, log_dir: Path,
        max_tool_calls: int | None = None, max_tokens: int | None = None) -> dict
    （與 `adapters.agents.pi_build`／`adapters.run.run_agent` 同簽名；
    兩支硬上限 opt-in：None＝不量不殺；未設定時本層不帶新 kwarg，舊簽名實現照跑）

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

def _partition_deliverables(
    req_set: RequirementSet, before: list[ClaimResult]
) -> tuple[set[str], set[str]]:
    """按關聯必需項的驗證狀態分流宣告交付物（只 localized 臂用）。

    回傳 (satisfied, unsatisfied)：
    - 某交付物的所有關聯必需項皆 PASS ⇒ satisfied（成果已驗證，提示要求完整保留）；
    - 任一關聯必需項非 PASS（FAIL/UNKNOWN/CONFLICT 或缺項）⇒ unsatisfied（缺口所在，請修正）；
    - 沒有關聯必需項（無從判定已驗證）⇒ 保守歸 unsatisfied（可修改）。
    未知狀態不得當已驗證：看不到＝UNKNOWN，不是 PASS。
    """
    by_id = {c.claim_id: c for c in before}
    satisfied: set[str] = set()
    unsatisfied: set[str] = set()
    for d in {it.deliverable for it in req_set.items if it.deliverable}:
        all_items = [i for i in req_set.items if i.deliverable == d]
        req_items = [i for i in all_items if i.required]
        if (
            req_items
            and all(i.id in by_id and by_id[i.id].status == "PASS" for i in req_items)
            and all(by_id[i.id].status == "PASS" for i in all_items if i.id in by_id)
        ):
            satisfied.add(d)
        else:
            unsatisfied.add(d)
    return satisfied, unsatisfied


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
    ×117 迴圈，具體證據才讓模型知道該避免哪一條；若其 `crash_giveup_suspected` 非空，
    提示點名「禁止裸 except: pass / except: return False 靜默吞掉解析錯誤」
    （effects_20261105 dabstep-1753：手寫匹配函式的解包例外被裸 except 吞掉、
    最終答案為放棄詞，兩階段 6 輪全敗）；若其 `empty_result_giveup_suspected` 非空，
    提示點名「腳本成功執行但沒有輸出任何結果、最終答案為放棄詞——通常是過濾/匹配
    條件把所有資料都排除了，不是腳本崩潰」（contrast1753_20261105 dabstep-1753
    localized r1：跑一次、零匹配、答案 None，既有兩個偵測器均按設計未觸發）。
    generic 對照臂不使用（定義不變）。

    計數規則形狀提示（localized 臂、只對 FAIL 的 unique_count／count_if 型規則）：
    effects_20261105 兩敗因（vq-5nz.15 / vq-5nz.20）：
    - dabstep-10-localized 兩輪皆敗（草稿 30→6，重算值 5，兩值皆恰為 +1）——
      cut|sort|uniq|wc 型管線計數、把 CSV 表頭行當成一個值；
    - dab_507-localized（值解析口徑）——policy30 r1 用 `grep ",5.0,"` 計數
      得 48（正則 `.` 通配、未錨定打到別欄）並把它當「草稿正確」的確認；
      fb20 r1 用 `awk -F','` 裸逗號切分、被名稱欄引號內含逗號錯列得 40。
    規則本身（col eq）已在證據中，但這類規則的常見錯誤形狀不在；
    `_count_rule_hint_line` 補形狀提示（表頭行／空行／正則通配／引號欄錯列），
    不給重算值或任何答案（leak guard 不變），不改重驗／停滯／退出碼。
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
    # P20261106_0632-1（2026-11-06 指示 4）：localized 臂在同時存在已滿足與未滿足的
    # 宣告交付物時分流顯示——只修未滿足、完整保留已滿足，防止模型重寫已通過的成果；
    # generic 對照臂定義不變（單一可修改列表）；全部未滿足或單一交付物也維持原列表。
    satisfied, unsatisfied = _partition_deliverables(req_set, before)
    declared = {it.deliverable for it in req_set.items if it.deliverable}
    partition = (
        feedback_mode == "localized"
        and len(declared) >= 2
        and bool(satisfied)
        and bool(unsatisfied)
    )
    lines: list[str] = []
    lines.append("【原始需求（使用者原文）】")
    lines.append(request if request else "（缺 request.md）")
    lines.append("")
    if partition:
        fix_files = [f for f in draft_files if f not in satisfied]
        # 宣告了但尚不存在於工作區的交付物＝未滿足（請依需求建立它）
        fix_files += sorted(declared - satisfied - set(draft_files))
        keep_files = [f for f in draft_files if f in satisfied]
        lines.append("【未滿足交付物（請修正此檔案以滿足缺口）】")
        lines.append("\n".join(f"- {f}" for f in fix_files) if fix_files else "- （無）")
        lines.append("")
        lines.append("【已滿足交付物（成果已驗證通過，請完整保留勿修改）】")
        lines.append("\n".join(f"- {f}" for f in keep_files) if keep_files else "- （無）")
        if declared - satisfied - set(draft_files):
            lines.append("若原始需求要求的交付物不存在，請依需求建立它。")
    else:
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
            # 標明所屬交付物（多交付物任務中缺口對應哪個檔案；空＝沿用舊格式）
            tag = f"（交付物：{item.deliverable}）" if item.deliverable else ""
            lines.append(f"- [{c.status}] {item.id}{tag}：{item.quote}")
            if c.status != "PASS":
                lines.append(f"  驗證結果：{_cap_prompt_text(c.detail)}")
                if c.evidence:
                    ev = json.dumps(c.evidence, ensure_ascii=False, default=str)
                    lines.append(f"  可見反例：{_cap_prompt_text(ev)}")
                hint = _count_rule_hint_line(c.evidence) or _cond_rate_hint_line(c.evidence)
                if hint:
                    lines.append(f"  {hint}")
        lines.append("")
        lines.append("【必須保持成立的條件】")
        keep = [i.id for i in req_set.items
                if by_id.get(i.id) is not None and by_id[i.id].status == "PASS"]
        lines.append(
            ("以下條目已 PASS，修正後必須仍然 PASS：" + "、".join(keep))
            if keep else "（沒有已 PASS 的條目）")
        lines.append("只修上面的缺口，不要重寫不相關的部分；改完後所有必需條目都要能通過重驗。")
        non_pass_claims = [
            by_id[i.id] for i in req_set.items
            if by_id.get(i.id) is not None and by_id[i.id].status != "PASS"
        ]
        format_only_failure = bool(non_pass_claims) and all(
            _is_format_only_claim(c) for c in non_pass_claims
        )
        if format_only_failure:
            lines.append(
                "不要重複同一命令：一旦依原始需求與驗證結果修好格式／取整／缺漏問題並確認結果無誤，"
                "請**立即先把修正後的結果寫入交付物檔案（如 answer.txt）**；"
                "嚴禁遲遲不寫交付物或反覆重跑單行驗證命令。"
            )
        else:
            lines.append(
                "不要重複同一命令：一旦腳本依原始需求的過濾條件與公式算出了與失敗草稿（deliverable_value）"
                "不同的新結果（或獨立驗算一次確認無誤），請**立即先把新結果寫入交付物檔案（如 answer.txt）**；"
                "嚴禁因反例未顯示隱藏期望值（expected_in_evidence=false）而遲遲不寫交付物或反覆重跑單行驗證命令。"
            )
        # 第 1 輪即可見的兩條紅線（不等上一輪觀察）：
        # contrast23_20261105 dabstep-23-pi-C localized r1（@26f23af5，vq-5nz.25）：
        # 7 條 `python3 -c "...; if cond: print(...)"` 一行式全部 SyntaxError（串流日誌 35×）——
        # -c 單行編譯下 `;` 後接 if/for/def 複合陳述即語法錯，重試永不成功；另
        # effects_20261105 feedback_once20 dab_055-pi-C localized r1 連續 27 次在 `python -c`
        # 單行內寫 `# comment` 把同行後續 `;` 語句與 print 全部註解掉而產生空輸出；同期
        # `python3 calculate_fraud.py` → 0.0 成功 7 次卻從未寫入 answer.txt（r2 才以
        # `python3 calculate_fraud.py > answer.txt` 關閉缺口）。_loop_warning_line 的
        # 「寫 .py、不要一行式」逃路只從第 2 輪生效；第 1 輪必須自己帶這兩條。
        # 只 localized 臂（generic 對照臂不帶執行觀察行）；不帶重算值、不影響裁決。
        # 注意：這兩行不得含任何數字——leak guard 測試（如重算值 "3" 不得進提示）
        # 以子串判斷，`python3` 的 "3" 會被誤判為重算值（故用 `python -c` 措辭）。
        lines.append(
            "【python 一行式紅線】`python -c` 只能執行小陳述；`;` 之後不得接 "
            "if / for / def / with 等複合陳述（例如 `data = read(); if data: print(len(data))` "
            "會直接 SyntaxError，重試多少次都不會成功），且單行內不得放 `#` 註解"
            "（`#` 會把同行後續所有 `;` 語句與 `print` 全部註解掉而產生空輸出）。"
            "需要多分支驗證或加註解時，把程式碼寫成 .py 檔案後執行；"
            "工作區裡已有能算出結果的腳本時，直接執行該腳本。"
        )
        if format_only_failure:
            lines.append(
                "計算或格式化腳本一旦成功印出符合原始需求格式的結果，下一個動作必須是把結果寫入交付物檔案："
                "腳本輸出即結果本身時，直接重定向寫入（例如 `python <計算腳本> > answer.txt`）；"
                "寫入交付物之前不要再執行任何驗證命令。"
            )
        else:
            lines.append(
                "計算腳本一旦成功印出與失敗草稿不同的新結果，下一個動作必須是把結果寫入交付物檔案："
                "腳本輸出即結果本身時，直接重定向寫入（例如 `python <計算腳本> > answer.txt`）；"
                "寫入交付物之前不要再執行任何驗證命令。"
            )
        # 上一輪工具死迴圈觀察 → 本輪針對性指令（點名工具＋次數＋命令例）。
        # 只 localized 臂：generic 對照臂定義＝不帶任何逐輪觀察（保持兩臂差異乾淨）。
        # 只帶執行觀察，不帶需求失敗證據或重算值；不影響重驗／停滯判定。
        loop = (prev_round_agent or {}).get("tool_loop_suspected")
        if isinstance(loop, dict) and loop:
            lines.append(_loop_warning_line(loop))
        # 上一輪 crash→放棄觀察 → 本輪針對性指令（禁止裸 except 靜默吞解析錯）。
        # 同樣只 localized 臂、只帶執行觀察（崩潰發生＋放棄詞），不帶重算值；
        # 不影響重驗／停滯判定／退出碼。
        crash = (prev_round_agent or {}).get("crash_giveup_suspected")
        empty = (prev_round_agent or {}).get("empty_result_giveup_suspected")
        if isinstance(crash, dict) and crash:
            lines.append(_crash_giveup_hint_line())
        elif isinstance(empty, dict) and empty:
            # 上一輪静默空结果 → 放弃观察 → 本輪針對性指令（空结果＝条件把资料都滤掉、非崩溃）。
            # 若已有 crash 提示則不重複追加互斥的空結果提示（避免同時稱「崩潰吞錯」又稱「未崩潰空結果」產生矛盾失焦）
            lines.append(_empty_result_giveup_hint_line())
    else:
        lines.append("")
        lines.append("請對照原始需求，重新檢查並修正工作區裡的交付物檔案一次。")
        lines.append("若原始需求要求的交付物（例如 answer.txt）不存在，請依原始需求把它建立出來。")
    return "\n".join(lines)


# ── 工作區（原草稿保留）──────────────────────────────────────────────

_WS_REQ_ITEM_KEYS = ("id", "quote", "deliverable", "required")


def _workspace_requirements_bytes(raw_bytes: bytes) -> bytes:
    """移除控制器內部驗證規格（verifier、params、recompute、note），只把需求識別與原文放入工作區。"""
    try:
        obj = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return raw_bytes
    if not isinstance(obj, dict) or not isinstance(obj.get("items"), list):
        return raw_bytes
    out: dict[str, Any] = {}
    if "task_id" in obj:
        out["task_id"] = obj["task_id"]
    out["items"] = [
        {k: it[k] for k in _WS_REQ_ITEM_KEYS if k in it}
        if isinstance(it, dict) else it
        for it in obj["items"]
    ]
    return (json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _copy_into_workspace(src: str | pathlib.Path, dst: str | pathlib.Path) -> None:
    """複製單檔進工作區，並保證目標可寫。

    來源可能是唯讀共享檔（data/ symlink 指向 0444 的 _data 檔；草稿目錄本身
    「只讀」是設計前提）——唯讀目標會讓 open(dst,'wb') 直接 EACCES，第 2+ 輪
    「同名檔以草稿為準」的覆寫與後續「權威來源重拷」就崩掉。先解唯讀再複製、
    複製後維持可寫；內容不變（sha256 不受影響）。
    （copytree 的 copy_function 傳 str，這裡統一轉 Path。）
    """
    src = pathlib.Path(src)
    dst = pathlib.Path(dst)
    if dst.exists() or dst.is_symlink():
        try:
            os.chmod(dst, 0o644)
        except OSError:
            dst.unlink()
    shutil.copy2(src, dst)
    try:
        os.chmod(dst, 0o644)
    except OSError:
        pass


def _copy_task_top_files_to_workspace(t: pathlib.Path, ws: pathlib.Path) -> None:
    for p in sorted(t.iterdir()) if t.is_dir() else []:
        if not p.is_file():
            continue
        if p.name == "requirements.json":
            (ws / p.name).write_bytes(_workspace_requirements_bytes(p.read_bytes()))
        else:
            _copy_into_workspace(p, ws / p.name)


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
    控制器內部的 requirements.json 寫入工作區時會剝離 verifier/params/recompute 等內部重算規格，
    防止模型在工作區偷讀重算答案或被歷史備註誤導。
    工作區副本一律可寫（來源唯讀不影響覆寫；內容 sha256 不變）。
    """
    t = pathlib.Path(task_dir)
    d = pathlib.Path(draft_dir)
    ws = pathlib.Path(out_root) / f"round_{round_n}"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    _copy_task_top_files_to_workspace(t, ws)
    for dd in include_dirs:
        src = t / dd
        if src.is_dir():
            shutil.copytree(src, ws / dd, dirs_exist_ok=True,
                            copy_function=_copy_into_workspace)
    for p in sorted(d.rglob("*")) if d.is_dir() else []:
        if p.is_file():
            dest = ws / p.relative_to(d)
            dest.parent.mkdir(parents=True, exist_ok=True)
            _copy_into_workspace(p, dest)
    if round_n >= 2:
        # 累積修復第 2+ 輪（d 為上一輪工作區）：確保權威來源檔案不被上一輪可能污染的副本覆寫
        _copy_task_top_files_to_workspace(t, ws)
        for dd in include_dirs:
            src = t / dd
            if src.is_dir():
                shutil.copytree(src, ws / dd, dirs_exist_ok=True,
                                copy_function=_copy_into_workspace)
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


_FORMAT_ONLY_PROBLEMS = frozenset({
    "not_a_number",
    "not_an_integer",
    "not_nonneg_int",
    "out_of_01",
    "missing",
    "missing_key",
    "missing_file",
    "invalid_json",
    "ambiguous",
    "empty_value",
    "not_a_fee_id",
})


def _is_format_only_claim(c: ClaimResult) -> bool:
    """判定一條非 PASS 的 ClaimResult 是否純屬格式／型別／取整／缺漏問題（而非重算數值不符）。"""
    ev = c.evidence
    if not isinstance(ev, dict):
        return False
    if "missing_file" in ev:
        return True
    prob = ev.get("problem")
    if isinstance(prob, str) and (prob in _FORMAT_ONLY_PROBLEMS or prob.startswith("missing_file:")):
        return True
    cex = ev.get("counterexamples")
    if isinstance(cex, list) and cex:
        return all(
            isinstance(it, dict)
            and isinstance(it.get("problem"), str)
            and (it["problem"] in _FORMAT_ONLY_PROBLEMS or it["problem"].startswith("missing_file:"))
            for it in cex
        )
    return False


def _cap_prompt_text(s: str) -> str:
    """截斷修復請求裡的單段詳情／反例；截斷必須可見（不得靜默丟棄資訊）。"""
    s = (s or "").strip()
    if len(s) <= _PROMPT_TEXT_CAP:
        return s
    return s[:_PROMPT_TEXT_CAP].rstrip() + f"…（已截斷，共 {len(s)} 字）"


def _count_rule_hint_line(evidence: Any) -> str | None:
    """計數與條件比率型重算規則（unique_count / count_if / cond_rate）FAIL 反例的形狀提示行——localized 臂專用。

    unique_count（effects_20261105 dabstep-10-localized 兩輪皆敗，vq-5nz.15）：
    草稿 30→6，重算值 5，兩值皆恰為 +1：模型用 cut|sort|uniq|wc 型 shell 管線
    計數，把 CSV 表頭行 "merchant" 當成一個值。
    count_if（effects_20261105 dab_507-localized，值解析口徑，vq-5nz.20）：
    - policy30 r1：`grep ",5.0," | wc -l` → 48——正則 `.` 是通配（也命中 ",520,"）、
      未錨定模式打到另一欄；模型把多算結果當「草稿正確」的確認、原樣保留 48；
    - fb20 r1：`awk -F',' '$4=="5.0"'` → 40——裸逗號切分被引號欄（飯店名稱）內含
      逗號錯列，漏掉名稱含逗號的 6 行 5 星飯店。成功修復（policy30 r2）＝
      pandas 依欄位名過濾 → 46。
    cond_rate（contrast23_20261105 dabstep-23-localized，argon 20261105_1407）：
    - payments.csv 有 42 筆 2023 年 Ecommerce 交易的 base64 雜湊欄（ip_address／email_address／
      card_number）碰巧含子字串 `POS`，其中 19 筆為 has_fraudulent_dispute=True，導致未錨定欄位名的
      `grep "POS" data/payments.csv | grep "2023" | cut -d',' -f18` 算出 19 / 12439 = 0.00152745
      （恰等於失敗草稿錯值！），而 `grep "True"` 則命中 is_credit=True 算出 8978，使模型在 r1 與 r2
      反覆懷疑 pandas 算出的 0.0。
    規則本身已在證據中、但這類規則的常見錯誤形狀不在；本行只補形狀
    提示，不給重算值、不給任何答案（leak guard 不變，且提示文字不含任何阿拉伯數字）。
    紅線：不給重算值、不給任何答案（leak guard 不變）；只 localized 臂、只 FAIL
    條目；不改重驗／停滯／退出碼。evidence 非 dict、無 rule、非 unique_count／
    count_if／cond_rate → None。
    """
    if not isinstance(evidence, dict):
        return None
    rule = evidence.get("rule")
    if not isinstance(rule, str):
        return None
    if rule.startswith("unique_count"):
        return (
            "【計數規則常見錯誤形狀（逐項檢查，兩種獨立計數方法一致才產出交付物）】"
            "其一：CSV 表頭行是否被當成一個值計入"
            "（cut|sort|uniq|wc 這類 shell 管線會把表頭行算進結果）；"
            "其二：行尾空行、空白值是否被計入；"
            "其三：僅大小寫或前後空白不同的值是否被當成多個；"
            "其四：CSV 雙引號欄位內若含逗號（如名稱含 `,`），cut/awk 以逗號切欄會導致欄位錯位。"
            "請改用逐行解析檔案的方法（如 python csv 模組）重數一次再比對。"
        )
    if rule.startswith("count_if"):
        return (
            "【計數規則常見錯誤形狀（逐項檢查，兩種獨立計數方法一致才產出交付物）】"
            "其一：若用文字匹配計數（grep/awk/cut），模式是否錨定在目標欄位與目標值上——"
            "正則 `.` 是通配（\",5.0,\" 這種模式也會命中 \",520,\"），未錨定的模式可能打到"
            "恰好含同值的另一欄；多算或漏算都可能，且錯誤結果可能恰好「確認」了草稿的錯值。"
            "其二：CSV 中有逗號的引號欄（如名稱欄）會讓裸逗號切分（awk -F',' / cut -d',' /"
            "按欄位序數取欄）錯列——改用逐行解析檔案的方法（python csv 模組或 pandas"
            "依欄位名）過濾目標欄位重數一次再比對。"
        )
    return None


def _cond_rate_hint_line(evidence: Any) -> str | None:
    """條件比率重算規則（cond_rate）FAIL 反例的欄位錨定提示行——localized 臂專用。

    來源（contrast23_20261105 dabstep-23-localized，argon 20261105_1407）：
    payments.csv 有 42 筆 2023 年 Ecommerce 交易的 base64 雜湊欄（ip_address／email_address／
    card_number）碰巧含子字串 `POS`，其中 19 筆為 has_fraudulent_dispute=True，導致未錨定欄位名的
    `grep "POS" data/payments.csv | grep "2023" | cut -d',' -f18` 算出 19 / 12439 = 0.00152745
    （恰等於失敗草稿錯值！），而 `grep "True"` 則命中 is_credit=True 算出 8978，使模型在 r1 與 r2
    反覆懷疑 pandas 算出的 0.0。
    紅線：不給重算值、不給任何答案、不含任何阿拉伯數字（防 leak guard 子串誤判）；
    與 _count_rule_hint_line 分離，保持 _count_rule_hint_line 對非計數規則回傳 None。
    """
    if not isinstance(evidence, dict):
        return None
    rule = evidence.get("rule")
    if not isinstance(rule, str) or not rule.startswith("cond_rate"):
        return None
    return (
        "【條件比率規則常見錯誤形狀（逐項檢查，請用按欄位名解析的程式計算）】"
        "其一：嚴禁用未錨定欄位的文字匹配（如 grep 子字串或 cut 按逗號切欄）"
        "直接數分子／分母行數——CSV 其他欄位（如雜湊編碼欄、電郵欄、另一布林欄）"
        "可能碰巧含目標子字串（如 POS、True 或年份字串），導致跨欄誤中而多算，"
        "甚至碰巧湊出與失敗草稿完全相同的錯誤比率。"
        "其二：CSV 引號欄若含逗號會讓裸逗號切欄錯位。"
        "請一律用 pandas 或 python csv 模組依精確欄位名過濾分母與分子後計算比率。"
    )


_PYTHON_SYNTAX_ERRORS = frozenset({"SyntaxError", "IndentationError", "TabError"})


def _loop_remediation_tail(loop: dict[str, Any]) -> str:
    """「先修掉錯誤的根因再執行」之後的針對性處方（r1063/argon）。

    - 「把程式碼寫成 .py 檔案後執行（不要用一行式拼接多條語句）」專屬於 Python 一行式
      語法/編譯錯誤（SyntaxError/IndentationError/TabError，如 dabstep-23 SyntaxError×34
      或 dabstep-1273 SyntaxError×7）：在一行式 -c 中使用複合陳述直接被語法限制擋住。
      若命令本身已是執行 .py 檔案（如 python3 script.py），或錯誤是執行期例外
      （NameError、KeyError、ZeroDivisionError、ValueError、TypeError 等），
      或是非 Python 工具（jq 過濾器錯、edit 驗證錯），開「寫成 .py 檔案、不要一行式」
      屬於失焦診斷，會誤導模型懷疑執行方式而非修正程式或資料邏輯。
    - 其餘情況（非語法錯、執行期例外、非 Python 工具、已是 .py 腳本）一律走通用根因處方：
      先查明失敗原因（參數、語法、未定義變數或資料內容不符）再修正執行。
    """
    cls = str(loop.get("error_class") or "").strip()
    args = loop.get("args")
    cmd = ""
    if isinstance(args, dict):
        cmd = str(args.get("command") or "")
    elif isinstance(args, str):
        cmd = args

    is_syntax_err = cls in _PYTHON_SYNTAX_ERRORS
    is_already_script = bool(cmd and (".py " in cmd or cmd.strip().endswith(".py")))
    if is_syntax_err and not is_already_script:
        return (
            "先修掉錯誤的根因再執行：把程式碼寫成 .py 檔案後執行（不要用一行式拼接多條語句），"
            "確認執行成功、結果正確後，直接把結果寫入交付物檔案。"
        )
    return (
        "先修掉錯誤的根因再執行：先查明這類命令失敗的原因（參數、語法、變數定義或資料內容不符），修正後再執行；"
        "確認結果正確後，直接把結果寫入交付物檔案。"
    )


def _empty_result_giveup_hint_line() -> str:
    """上一輪静默空结果 → 放弃观察（detect_empty_result_giveup 回傳）→ localized 提示的針對性行。

    来源（contrast1753_20261105，dabstep-1753-pi-C localized r1，r1068）：模型写
    solution.py 并跑一次，输出为空（零条匹配记录），最终答案为放弃词 None；日誌无
    Traceback、无重复命令——既有两个偵测器都按设计正确返回 None，但下一輪提示无
    針對性线索。空结果通常不是崩溃，而是過濾/匹配条件把所有记录都排除了
    （欄位型別、null 處理、字串 vs 数値、条件过严）。

    规则同 _crash_giveup_hint_line：只带执行观察（脚本跑过＋输出为空＋放弃词），不带
    需求失败证据或重算值；静态行（不含动态值、也不含数字——leak guard 是子串匹配，
    提示行任何数字都会被誤判）；不改变裁決。
    """
    return (
        "【上一輪執行觀察】上一輪偵測到：計算腳本成功執行但沒有輸出任何結果、最終答案為放棄詞（如 None）。"
        "空結果通常不是腳本崩潰，而是過濾／匹配條件把所有資料都排除掉了（欄位型別、null 處理、"
        "字串與數值比較、條件過嚴）。本輪先逐步印出過濾過程每步剩餘筆數、找出是哪一步把結果濾空，"
        "修正根因並確認腳本真的產出非空結果後，再寫入交付物。"
    )


def _loop_warning_line(loop: dict[str, Any]) -> str:
    """上一輪工具死迴圈觀察（detect_tool_loop 回傳值）→ localized 提示的針對性行。

    與提示裡既有的通用行（「不要重複同一命令」）不同：點名上一輪實際重複的
    工具、次數與命令例，讓模型知道該避免**哪一條**。effects_20261105 證據：
    通用行已在提示中，dabstep-23-localized 仍 ×117 重複至超時——通用警告不足
    以打破迴圈。只帶執行觀察（工具名／參數／次數），不帶需求失敗證據或重算值；
    參數例截斷必須可見。

    r1044（vq-5nz.21；contrast3_20261105 dabstep-23 localized r2 歸因）：重複命令
    **每次都失敗**（all_failed=True，如 SyntaxError ×34、從無結果）時，舊行
    「執行一次已得到結果後」的前提不成立、提示失焦——改點名錯誤類＋具體語法
    規則（寫 .py 檔案執行）＋「跑通即寫入交付物」，不帶該假前提。

    處方依錯誤類與執行方式分流（_loop_remediation_tail）：.py 逃逸處方只給
    Python 一行式語法錯誤；jq／edit 驗證／執行期例外等給通用根因處方。
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
        if len(args_text) > 360:
            args_text = args_text[:220].rstrip() + " … " + args_text[-120:].lstrip()
        example = f"（例：{args_text}）"
    tail = _loop_remediation_tail(loop)
    if loop.get("error_class_repeat") is True:
        # contrast055_1273_20261105 dabstep-1273 generic r1 形狀：同類錯誤多次失敗、
        # 成功探查交錯、每次錯誤文本微差。不帶「以相同參數」「每次都失敗」假前提。
        err = str(loop.get("error_class") or "執行錯誤").strip()
        sample = str(loop.get("error_sample") or "").strip()
        if sample.startswith(f"{err}:"):
            sample = sample[len(err) + 1:].strip()
        sample_part = f"（{sample}）" if (sample and sample != err) else ""
        n = loop.get("failure_count")
        n = f" {n}" if isinstance(n, int) else ""
        head = (
            f"【上一輪執行觀察】上一輪偵測到 {name} 合計失敗{n} 次、皆屬同一類錯誤（{err}{sample_part}）"
            f"（每次微調參數但未修根因，疑似工具死迴圈）{example}。"
        )
        if loop.get("all_failed") is True:
            return head + (
                f"本輪禁止重複該類命令——它上一輪每次都失敗（{err}{sample_part}）、從未得到結果。"
                + tail
            )
        return head + "本輪禁止重複該類失敗命令。" + tail
    if loop.get("same_error_streak") is True:
        head = (
            f"【上一輪執行觀察】上一輪偵測到 {name} 連續執行{reps} 次皆因同一錯誤失敗"
            f"（雖微調參數但未修根因，疑似工具死迴圈）{example}。"
        )
    else:
        head = (
            f"【上一輪執行觀察】上一輪偵測到 {name} 以相同參數連續執行{reps} 次、"
            f"中間沒有改動（疑似工具死迴圈）{example}。"
        )
    if loop.get("all_failed") is True:
        err = str(loop.get("error_class") or "執行錯誤").strip()
        sample = str(loop.get("error_sample") or "").strip()
        if sample.startswith(f"{err}:"):
            sample = sample[len(err) + 1:].strip()
        sample_part = f"（{sample}）" if (sample and sample != err) else ""
        return head + (
            f"本輪禁止重複該命令——它上一輪每次都失敗（{err}{sample_part}）、從未得到結果。"
            + tail
        )
    return head + (
        "本輪禁止重複該命令；同一計算執行一次已得到結果後，直接以該結果推導並產出交付物，"
        "不要再次執行同一命令。"
    )


def _crash_giveup_hint_line() -> str:
    """上一輪 crash→放棄觀察（detect_crash_giveup 回傳值）→ localized 提示的針對性行。

    來源（effects_20261105，dabstep-1753：兩階段 6 輪全敗）：模型手寫區間匹配函式
    （parse_range / match_volume / match_fraud）時反覆栽跟頭——split('..') 解包例外被
    裸 `except: return False` 靜默吞掉、cat << 'EOF' 內混用引號語法錯、最終答案是放棄詞，
    錯因永不浮現。審查指示 2026-11-05 P2：提示必須直接對準「禁止在資料過濾腳本中使用
    裸 except: pass / except: return False 靜默吞掉解析錯誤」。

    與 _loop_warning_line 同規則：只帶執行觀察（崩潰＋放棄詞），不帶需求失敗證據或
    重算值；hint 為靜態行（不含任何動態數值）；不改變裁決。
    """
    return (
        "【上一輪執行觀察】上一輪偵測到腳本崩潰、最終答案為放棄詞（如 None）。"
        "本輪寫資料過濾／匹配腳本時，禁止用裸 except: pass / except: return False "
        "靜默吞掉解析錯誤（解包例外、格式不符、引號轉義錯等）——解析錯誤應讓例外浮現"
        "（讓它丟出並修根因，或顯式計數並回報錯誤筆數），確認沒有靜默吞錯後再產出交付物。"
    )


def _extract_error_signature(text: str) -> tuple[str, str]:
    """從失敗工具輸出提取 (error_class, error_sample)。"""
    m = _CRASH_EXC_RE.search(text)
    if m:
        cls = m.group(1)
        for line in text.replace("\\n", "\n").splitlines():
            if cls in line:
                s = line.strip()
                if s:
                    return (cls, s[:80])
        return (cls, "")
    lines = [ln.strip() for ln in text.replace("\\n", "\n").splitlines() if ln.strip()]
    non_meta = [
        ln for ln in lines
        if not _CRASH_EXIT_RE.search(ln) and not _CRASH_TRACEBACK_RE.search(ln)
    ]
    pick = non_meta[0] if non_meta else (lines[0] if lines else "")
    return ("", pick[:80] if pick else "")


def _error_family(sample: str) -> str | None:
    """r1061（vq-5nz.30）：非例外工具錯誤（jq／edit 驗證等）沒有例外類；
    以錯誤文本第一個冒號前的穩定前綴（≤40 字元）作為錯誤類——
    jq parse/runtime 錯誤 → "jq"；edit 驗證 → 'Validation failed for tool "edit"'。
    前綴不合條件（無冒號／過長／空）回傳 None＝不歸組（維持原跳過行為，
    避免把無關錯誤併成一類）。effects_20261105 實據（r1062 逐 log 事件核對）：
    policy30/dabstep-1753-pi-C localized r1 4 次 jq parse error（column 微差）
    與 r2 4 次 jq 錯誤（parse×2＋index×2）、feedback_once20/dab_039-pi-C
    localized r1 5 次＋policy30/dab_039-pi-C generic r1 4 次 edit 驗證失敗，
    修正前 detect_tool_loop 皆回 None；feedback_once20/dab_039 generic r1
    僅 2 次（低於 threshold、不歸組屬設計）。
    """
    if not sample:
        return None
    i = sample.find(":")
    prefix = (sample[:i] if i > 0 else "").strip()
    if not prefix or len(prefix) > 40:
        return None
    return prefix


def _loop_outcome_fields(loop_keys: list[tuple[str, Any]],
                         outcomes: list[tuple[tuple[str, Any], bool, str]]) -> dict[str, Any]:
    """聚合迴圈 key（單 key 或 period-2/3 多 key）的執行結果（r1044／vq-5nz.21；argon 20261105_1047 修）。

    outcomes＝依 toolCallId 關聯自該連勝串 tool_execution_end 的 (key, isError, 輸出文字)。
    - 該 key 無 end 事件⇒{}（未知，不造假）；
    - 多步週期若任一步驟在迴圈串中每次皆失敗（如 write 成功但配對的 bash 每次都 SyntaxError），
      代表每一組交替迴圈皆失敗、從未跑出結果，以該失敗步驟計入全敗（all_failed=True）；
    - 至少一次完整成功⇒all_failed=False；
    - 全敗⇒all_failed=True，並自第一個失敗輸出提取 error_class＋error_sample
      （執行觀察：與提示中工具名／參數例同源，不含重算值／需求證據）。
    """
    rel = [o for o in outcomes if o[0] in loop_keys]
    if not rel:
        return {}
    if len(loop_keys) > 1:
        by_key = [[o for o in rel if o[0] == k] for k in loop_keys]
        failing_steps = [step_outs for step_outs in by_key if step_outs and all(o[1] for o in step_outs)]
        if failing_steps:
            rel = failing_steps[0]
    failed = [o for o in rel if o[1]]
    if not failed:
        return {"all_failed": False, "failure_count": 0, "success_count": len(rel)}
    all_failed = len(failed) == len(rel)
    out: dict[str, Any] = {
        "all_failed": all_failed,
        "failure_count": len(failed),
        "success_count": len(rel) - len(failed),
    }
    if all_failed:
        for _key, _err, text in failed:
            cls, sample = _extract_error_signature(text)
            if cls:
                out["error_class"] = cls
                if sample:
                    out["error_sample"] = sample
                break
        if "error_sample" not in out:
            for _key, _err, text in failed:
                _cls, sample = _extract_error_signature(text)
                if sample:
                    out["error_sample"] = sample
                    break
    return out


def detect_tool_loop(log_path: str | pathlib.Path, *, threshold: int = 4) -> dict[str, Any] | None:
    """偵測「工具死迴圈」：同一 (tool, args) 單步連續重複、雙步 (k1, k2)／三步 (k1, k2, k3) 交替連續重複，
    或同一工具連續多次微調參數但皆因同一錯誤失敗（same_error_streak）；
    同工具同錯誤類多次失敗但成功探查交錯／每次錯誤文本微差（error_class_repeat；
    contrast055_1273_20261105 dabstep-1273 generic r1：22 次 python3 -c 中 7 次
    SyntaxError、15 次成功——strict same_error_streak 要求「連續＋同錯誤文本」而漏）；
    r1061：無例外類的工具錯誤（jq／edit 驗證）以前綴類歸組（_error_family）。

    r1044（vq-5nz.21）：另自 tool_execution_end 依 toolCallId 關聯執行結果，
    區分「迴圈命令每次都失敗」（all_failed／error_class——contrast3 dabstep-23
    localized：同一行式 ×34 皆 SyntaxError、從無結果）與「成功後重複驗證」；
    無 end 事件＝未知（無該欄），不造假。只記錄，不改變裁決。

    來源：
    - effects_20261105 dabstep-23-pi-C localized：模型把同一條 python3 一行式重複執行
      10 次以上（period-1，同 args、同結果、中間沒有寫檔）直到 300s 預算耗盡；
    - effects_20261105 feedback_once20/dabstep-1753-pi-C localized r1：模型把完全相同的
      (write find_fees.py, bash cat << 'EOF' > find_fees.py ...) 雙步交替重複 9 組（18 次呼叫，
      period-2，參數零改動）直到 300s 超時；
    - contrast23_20261105 dabstep-23-pi-C generic r2：模型把 (write, bash python3, bash grep)
      三步週期（period-3）連續重複 5 組；
    - contrast23_20261105 dabstep-23-pi-C localized r1：模型連續 5 次執行 bash `python3 -c "...; if ..."`，
      每次微調中間 `fraud_count = ...` 但全部因尾部 `; if ...` 觸發相同 SyntaxError。
    這是觀察與標記，不是裁決：不改變任何 PASS/FAIL、停滯判定或退出碼；
    只記錄在該輪 agent 欄位（`tool_loop_suspected`），讓審計不必人讀 1MB 日誌。
    缺值＝None，不填假值。
    """
    p = pathlib.Path(log_path)
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    keys: list[tuple[str, Any]] = []
    starts: list[tuple[tuple[str, Any], str | None]] = []
    best: tuple[str, Any] | None = None
    best_streak = 0
    best_start_idx = 0
    cur_key: tuple[str, Any] | None = None
    cur_streak = 0
    cur_start_idx = 0
    call_key: dict[str, tuple[str, Any]] = {}
    end_by_cid: dict[str, tuple[tuple[str, Any], bool, str]] = {}
    end_outcomes: list[tuple[tuple[str, Any], bool, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        etype = obj.get("type")
        if etype == "tool_execution_start":
            key = (str(obj.get("toolName")), obj.get("args"))
            idx = len(keys)
            keys.append(key)
            cid = obj.get("toolCallId")
            cid_s = cid if (isinstance(cid, str) and cid) else None
            starts.append((key, cid_s))
            if cid_s is not None:
                call_key[cid_s] = key
            if key == cur_key:
                cur_streak += 1
            else:
                cur_key = key
                cur_streak = 1
                cur_start_idx = idx
            if cur_streak > best_streak:
                best_streak = cur_streak
                best = key
                best_start_idx = cur_start_idx
        elif etype == "tool_execution_end":
            cid = obj.get("toolCallId")
            if isinstance(cid, str) and cid in call_key:
                outcome_item = (
                    call_key[cid], bool(obj.get("isError")),
                    _extract_tool_end_text(obj),
                )
                end_by_cid[cid] = outcome_item
                end_outcomes.append(outcome_item)

    best_p2_pair: tuple[tuple[str, Any], tuple[str, Any]] | None = None
    best_p2_cycles = 0
    best_p2_start = 0
    n_keys = len(keys)
    for i in range(n_keys - 1):
        k1, k2 = keys[i], keys[i + 1]
        if k1 == k2:
            continue
        cycles = 1
        j = i + 2
        while j + 1 < n_keys and keys[j] == k1 and keys[j + 1] == k2:
            cycles += 1
            j += 2
        if cycles > best_p2_cycles:
            best_p2_cycles = cycles
            best_p2_pair = (k1, k2)
            best_p2_start = i

    best_p3_triple: tuple[tuple[str, Any], tuple[str, Any], tuple[str, Any]] | None = None
    best_p3_cycles = 0
    best_p3_start = 0
    for i in range(n_keys - 2):
        k1, k2, k3 = keys[i], keys[i + 1], keys[i + 2]
        if k1 == k2 == k3:
            continue
        cycles = 1
        j = i + 3
        while j + 2 < n_keys and keys[j] == k1 and keys[j + 1] == k2 and keys[j + 2] == k3:
            cycles += 1
            j += 3
        if cycles > best_p3_cycles:
            best_p3_cycles = cycles
            best_p3_triple = (k1, k2, k3)
            best_p3_start = i

    if best is not None and best_streak >= threshold and best_streak >= max(best_p2_cycles, best_p3_cycles):
        name, args = best
        out: dict[str, Any] = {"tool_name": name, "args": args,
                               "consecutive_repetitions": best_streak, "threshold": threshold}
        streak_starts = starts[best_start_idx:best_start_idx + best_streak]
        streak_outcomes = [
            end_by_cid[cid] for _k, cid in streak_starts
            if cid is not None and cid in end_by_cid
        ]
        out.update(_loop_outcome_fields([best], streak_outcomes if streak_outcomes else end_outcomes))
        return out
    if best_p2_pair is not None and best_p2_cycles >= threshold and best_p2_cycles >= best_p3_cycles:
        k1, k2 = best_p2_pair
        out = {
            "tool_name": f"{k1[0]}+{k2[0]}",
            "args": {"first": k1[1], "second": k2[1]},
            "consecutive_repetitions": best_p2_cycles,
            "threshold": threshold,
            "period": 2,
        }
        streak_starts = starts[best_p2_start:best_p2_start + 2 * best_p2_cycles]
        streak_outcomes = [
            end_by_cid[cid] for _k, cid in streak_starts
            if cid is not None and cid in end_by_cid
        ]
        out.update(_loop_outcome_fields([k1, k2], streak_outcomes if streak_outcomes else end_outcomes))
        return out
    if best_p3_triple is not None and best_p3_cycles >= threshold:
        k1, k2, k3 = best_p3_triple
        out = {
            "tool_name": f"{k1[0]}+{k2[0]}+{k3[0]}",
            "args": {"first": k1[1], "second": k2[1], "third": k3[1]},
            "consecutive_repetitions": best_p3_cycles,
            "threshold": threshold,
            "period": 3,
        }
        streak_starts = starts[best_p3_start:best_p3_start + 3 * best_p3_cycles]
        streak_outcomes = [
            end_by_cid[cid] for _k, cid in streak_starts
            if cid is not None and cid in end_by_cid
        ]
        out.update(_loop_outcome_fields([k1, k2, k3], streak_outcomes if streak_outcomes else end_outcomes))
        return out

    # 同工具連續多次微調參數但每次皆因同一錯誤簽名失敗（如 contrast23 dabstep-23 localized r1 calls 4-8）
    cur_err_sig: tuple[str, str, str] | None = None
    cur_err_streak = 0
    best_err_streak = 0
    best_err_sig: tuple[str, str, str] | None = None
    best_err_args: Any = None
    for (tname, targs), cid_s in starts:
        if cid_s is not None and cid_s in end_by_cid:
            _k, is_err, out_txt = end_by_cid[cid_s]
            if is_err:
                cls, sample = _extract_error_signature(out_txt)
                if cls or sample:
                    sig = (tname, cls, sample)
                    if sig == cur_err_sig:
                        cur_err_streak += 1
                    else:
                        cur_err_sig = sig
                        cur_err_streak = 1
                    if cur_err_streak > best_err_streak:
                        best_err_streak = cur_err_streak
                        best_err_sig = sig
                        best_err_args = targs
                    continue
        cur_err_sig = None
        cur_err_streak = 0

    if best_err_sig is not None and best_err_streak >= threshold:
        err_tool, err_cls, err_sample = best_err_sig
        out = {
            "tool_name": err_tool,
            "args": best_err_args,
            "consecutive_repetitions": best_err_streak,
            "threshold": threshold,
            "same_error_streak": True,
            "all_failed": True,
            "failure_count": best_err_streak,
            "success_count": 0,
        }
        if err_cls:
            out["error_class"] = err_cls
        if err_sample:
            out["error_sample"] = err_sample
        return out

    # 同一工具、同一錯誤類多次失敗——允許成功探查交錯其間、每次錯誤文本可微差
    # （contrast055_1273_20261105 dabstep-1273 generic r1：22 次 python3 -c 微調中 7 次皆
    # SyntaxError、15 次成功；上方 strict same_error_streak 要求「連續＋同錯誤文本」而漏
    # 掉這種形狀，該輪燒掉的模型呼叫在 g2_result 的 agent 欄位完全不可見）。
    # 最寬的 fallback 路徑：只記錄觀察（agent 欄位／localized 提示），不改變裁決；
    # 低於 threshold 的零星語法錯不誤報。
    class_fail: dict[tuple[str, str], dict[str, Any]] = {}
    for (tname, targs), cid_s in starts:
        if cid_s is None or cid_s not in end_by_cid:
            continue
        _k, is_err, out_txt = end_by_cid[cid_s]
        if not is_err:
            continue
        cls, sample = _extract_error_signature(out_txt)
        key_cls = cls or _error_family(sample)
        if not key_cls:
            continue
        rec = class_fail.setdefault((tname, key_cls),
                                    {"count": 0, "args": targs, "sample": sample})
        rec["count"] += 1
        if not rec["sample"] and sample:
            rec["sample"] = sample
    best_rec: tuple[tuple[str, str], dict[str, Any]] | None = None
    for key, rec in class_fail.items():
        if rec["count"] >= threshold and (
                best_rec is None or rec["count"] > best_rec[1]["count"]):
            best_rec = (key, rec)
    if best_rec is None:
        return None
    (repeat_tool, repeat_cls), rec = best_rec
    tool_success = 0
    for _k, cid_s in starts:
        if cid_s is None or cid_s not in end_by_cid:
            continue
        ek, is_err, _t = end_by_cid[cid_s]
        if not is_err and ek[0] == repeat_tool:
            tool_success += 1
    out: dict[str, Any] = {
        "tool_name": repeat_tool,
        "args": rec["args"],
        "error_class": repeat_cls,
        "error_class_repeat": True,
        "failure_count": rec["count"],
        "threshold": threshold,
        "all_failed": tool_success == 0,
        "success_count": tool_success,
    }
    if rec["sample"]:
        out["error_sample"] = rec["sample"]
    return out


#: crash→放棄 偵測的崩潰簽名（effects_20261105 dabstep-1753 generic：
#: `NameError ... Command exited with code 1`，模型隨後把答案寫成「None」放棄）。
_CRASH_EXIT_RE = re.compile(r"Command exited with code (\d+)")
_CRASH_TRACEBACK_RE = re.compile(r"Traceback \(most recent call last\)")
# 注意：不能加 `\b` 前綴錨——pi --mode json 的日誌把換行轉義為字面 `\n`，
# 例外名可能緊接在字元 `n` 之後，`\b` 會漏掉（dabstep-1753 真實日誌即此形狀）。
_CRASH_EXC_RE = re.compile(
    r"(NameError|TypeError|AttributeError|KeyError|ValueError|IndexError"
    r"|ZeroDivisionError|SyntaxError|IndentationError|TabError|UnboundLocalError"
    r"|ModuleNotFoundError|ImportError|FileNotFoundError|PermissionError|OSError"
    r"|JSONDecodeError|UnicodeDecodeError|RuntimeError)\s*:")
#: 最終答案＝放棄詞（strip+lower 比對）：空、None、N/A、Not Applicable、No answer。
_GIVEUP_ANSWERS = {"", "none", "n/a", "not applicable", "no answer"}
# 静默空结果 → 放棄偵测：bash 命令中 python 解释器直接执行 .py 文件（不匹配
# heredoc 重定向 `> solution.py`，也不匹配 `python3 -c "..."`）。
# 支援各種前綴路徑（如 /usr/bin/python3, ./.venv/bin/python）、版本後綴
# （如 python3.12, python3.11, /usr/local/bin/python3.12）與執行參數（如 -u, -B）。
# （r1078：5a2384fa 補了前綴路徑與參數，版本後綴是同一形狀家族的剩餘盲區。）
_PY_SCRIPT_RUN_RE = re.compile(
    r"(?:^|[\s;|&])(?:(?:\S+/)?python3?(?:\.\d+)*)(?:\s+-[a-zA-Z0-9]+)*\s+([^\s;|&<>]+\.py)"
)
# 偵測命令是否對 stdout 進行重導向或管道（> / >> / 1> / &> / |）
_STDOUT_REDIRECT_RE = re.compile(r"(?:(?<![2-9a-zA-Z])(?:>|>>)|1>|&>|\|)")


def _extract_tool_end_text(obj: dict[str, Any]) -> str:
    """從 tool_execution_end 事件抽出工具輸出文字（相容真實 pi --mode json 的 result 與測試的 output）。"""
    parts: list[str] = []
    out = obj.get("output")
    if isinstance(out, str):
        parts.append(out)
    res = obj.get("result")
    if isinstance(res, str):
        parts.append(res)
    elif isinstance(res, dict):
        content = res.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
        elif isinstance(res.get("text"), str):
            parts.append(res["text"])
    return "\n".join(parts)


def detect_crash_giveup(
    log_path: str | pathlib.Path,
    answer_path: str | pathlib.Path,
    *,
    max_signatures: int = 12,
    draft_answer_path: str | pathlib.Path | None = None,
) -> dict[str, Any] | None:
    """偵測「crash→放棄」：session 內腳本崩潰，最終答案卻是一句放棄詞。

    來源（effects_20261105，dabstep-1753-pi-C generic）：r1 腳本崩潰後答「Not Applicable」。
    防誤報與防膨脹（argon 20261105_0715）：
    - 若提供 `draft_answer_path` 且本輪結束時 `answer.txt` 與初始草稿完全相同（例如原草稿已是
      `"None"`），但日誌中 agent 從未對 `answer.txt` 發出寫入或修改工具呼叫（只是超時未寫檔），
      回傳 None，不得誤判為「crash 後寫 None 放棄」。
    - 若日誌為 `pi --mode json` JSONL 且含 `tool_execution_end` 事件，只掃描 `isError` 非 False
      的 `tool_execution_end` 輸出，避免同一錯誤在 6 種串流事件中被重複計數 6 倍，並避免誤抓
      `isError=False` 正常程式碼內的 `except ValueError:` 字串。
    """
    ans_p = pathlib.Path(answer_path)
    try:
        answer = ans_p.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if answer.lower() not in _GIVEUP_ANSWERS:
        return None
    try:
        text = pathlib.Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    parsed: list[dict[str, Any]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("{"):
            continue
        try:
            obj = json.loads(s)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            parsed.append(obj)

    if draft_answer_path is not None:
        try:
            draft_ans = pathlib.Path(draft_answer_path).read_text(
                encoding="utf-8", errors="replace"
            ).strip()
        except OSError:
            draft_ans = None
        if draft_ans is not None and draft_ans == answer and parsed:
            ans_name = ans_p.name
            touched = False
            for obj in parsed:
                if obj.get("type") != "tool_execution_start":
                    continue
                tname = str(obj.get("toolName") or "")
                args = obj.get("args") if isinstance(obj.get("args"), dict) else {}
                if tname in ("write", "edit") and ans_name in str(args.get("path") or ""):
                    touched = True
                    break
                if tname == "bash" and ans_name in str(args.get("command") or ""):
                    touched = True
                    break
            if not touched:
                return None

    tool_ends = [obj for obj in parsed if obj.get("type") == "tool_execution_end"]
    if tool_ends:
        scan_texts = [
            _extract_tool_end_text(obj)
            for obj in tool_ends
            if obj.get("isError") is not False
        ]
        scan_blob = "\n".join(t for t in scan_texts if t)
    else:
        scan_blob = text

    sigs: list[str] = []
    for m in _CRASH_EXIT_RE.finditer(scan_blob):
        if int(m.group(1)) != 0:
            sigs.append(m.group(0))
    sigs += _CRASH_TRACEBACK_RE.findall(scan_blob)
    sigs += _CRASH_EXC_RE.findall(scan_blob)
    if not sigs:
        return None
    uniq = sorted(set(sigs))
    return {
        "giveup_answer": answer,
        "crash_event_count": len(sigs),
        "crash_signatures": uniq[:max_signatures],
        "signatures_truncated": len(uniq) > max_signatures,
    }


def detect_empty_result_giveup(
    log_path: str | pathlib.Path,
    answer_path: str | pathlib.Path,
    *,
    max_examples: int = 8,
) -> dict[str, Any] | None:
    """偵测「静默空结果 → 放弃」：session 内有 python 脚本成功执行（isError False）但
    输出为空，且最终答案为放弃词。

    来源（contrast1753_20261105，dabstep-1753-pi-C localized r1，r1068）：模型写
    solution.py 并跑一次，输出为空（零条匹配记录），答案保持 None；日誌无 Traceback、
    无非零退出、无重复命令——detect_crash_giveup（无崩溃签名）与 detect_tool_loop
    （无重复）都按设计正确返回 None，但下一輪提示无針對性线索。空结果通常不是崩溃，
    而是過濾/匹配条件把所有记录都排除了（欄位型別、null 處理、字串 vs 数値、条件过严）。

    与 detect_crash_giveup 的区分：本形状是「agent 确实跑过一次计算脚本、什么都得到
    不到」（isError False＋输出欄位存在但為空）；detect_crash_giveup 的 draft 未变
    守卫在这里不适用——答案保持 draft 的「None」正是本形状本身。观察与標記、非裁決：
    不改变重驗、停滯判断、退出碼；缺失（无日誌／无答案／无 pi-jsonl 事件／isError
    未知）⇒ None，不捏造。
    """
    ans_p = pathlib.Path(answer_path)
    try:
        answer = ans_p.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if answer.lower() not in _GIVEUP_ANSWERS:
        return None
    try:
        text = pathlib.Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    starts: dict[str, dict[str, Any]] = {}
    ends: dict[str, dict[str, Any]] = {}
    have_events = False
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("{"):
            continue
        try:
            obj = json.loads(s)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        etype = obj.get("type")
        cid = obj.get("toolCallId")
        if not (isinstance(cid, str) and cid):
            continue
        if etype == "tool_execution_start":
            starts[cid] = obj
            have_events = True
        elif etype == "tool_execution_end":
            ends[cid] = obj
            have_events = True
    if not have_events:
        return None

    hits: list[str] = []
    for cid, start in starts.items():
        if str(start.get("toolName") or "") != "bash":
            continue
        args = start.get("args") if isinstance(start.get("args"), dict) else {}
        cmd = str(args.get("command") or "")
        m = _PY_SCRIPT_RUN_RE.search(cmd)
        if not m:
            continue
        # 若該命令對 stdout 進行了重導向或管道（> / >> / 1> / &> / |），
        # 則 bash 工具輸出為空屬重導向自然現象，不應誤判為「腳本無輸出」
        after_py = cmd[m.end():].split("\n")[0]
        if _STDOUT_REDIRECT_RE.search(after_py):
            continue
        end = ends.get(cid)
        if end is None or end.get("isError") is not False:
            continue  # 报错／未知 ⇒ crash 側形状或 UNKNOWN，不誤判
        # 输出欄位存在（非缺失）但為空 ⇒「跑过但没输出」（缺失＝UNKNOWN，不算）
        if not (isinstance(end.get("output"), str) or isinstance(end.get("result"), (str, dict))):
            continue
        if _extract_tool_end_text(end).strip():
            continue
        hits.append(m.group(1))
    if not hits:
        return None
    uniq = sorted(set(hits))
    return {
        "giveup_answer": answer,
        "empty_run_count": len(hits),
        "empty_run_scripts": uniq[:max_examples],
        "examples_truncated": len(uniq) > max_examples,
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
    對 requirements.json 比對工作區應有的去內部規格版本（_workspace_requirements_bytes）。
    """
    import hashlib as _hashlib
    bad: list[str] = []
    for rel, h in _load_manifest(authoritative).items():
        f = ws / rel
        if not f.is_file():
            bad.append(rel)
            continue
        expected_h = (
            _hashlib.sha256(
                _workspace_requirements_bytes((authoritative / rel).read_bytes())
            ).hexdigest()
            if rel == "requirements.json" and (authoritative / rel).is_file()
            else h
        )
        if _hashlib.sha256(f.read_bytes()).hexdigest() != expected_h:
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
    max_tool_calls: int | None = None,
    max_tokens: int | None = None,
    include_dirs: tuple[str, ...] = ("data",),
    authoritative: pathlib.Path | None = None,
    prev_round_agent: dict[str, Any] | None = None,
) -> RepairRound:
    """一輪修復：新工作區 → 原生 pi → 重驗 → 差異。來源目錄不被改動。

    `prev_round_agent`（第 2+ 輪）：上一輪 agent 欄位（第 1 輪＝None）。localized
    臂若其 tool_loop_suspected 非空，本輪提示點名上一輪重複的工具與次數（針對性
    反迴圈指令）；generic 臂不受影響。只進提示，不改重驗／停滯／退出碼。

    硬預算上限（opt-in，2026-11-06）：`max_tool_calls`／`max_tokens` 轉發給執行器
    run()；兩者皆 None＝原路徑逐位元組不變（不量不殺，舊簽名 RunFn 不受影響）。
    執行器殺掉的輪次其回傳 dict 帶 `budget_exceeded`，如實記錄在本輪 agent 欄位。

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
    # 硬預算上限（opt-in）：皆 None＝原路徑逐位元組不變（不帶新 kwarg，舊簽名 RunFn 照跑）
    run_kwargs: dict[str, Any] = {}
    if max_tool_calls is not None or max_tokens is not None:
        run_kwargs = {"max_tool_calls": max_tool_calls, "max_tokens": max_tokens}
    try:
        agent = run(launch, workspace=ws, timeout_s=timeout_s, log_dir=log_dir,
                    **run_kwargs)
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
    # 候選交付物路徑：優先納入 answer.txt 與需求集宣告的交付物（以存在者優先）
    candidate_delivs: list[str] = []
    if (ws / "answer.txt").exists():
        candidate_delivs.append("answer.txt")
    for it in req_set.items:
        if it.deliverable and it.deliverable not in candidate_delivs and (ws / it.deliverable).exists():
            candidate_delivs.append(it.deliverable)
    if not candidate_delivs:
        candidate_delivs = ["answer.txt"] + [it.deliverable for it in req_set.items if it.deliverable]

    crash_suspected = None
    empty_suspected = None
    for deliv_name in candidate_delivs:
        deliv_p = ws / deliv_name
        draft_deliv_p = pathlib.Path(draft_dir) / deliv_name
        if crash_suspected is None:
            crash_suspected = detect_crash_giveup(
                log_dir / "agent_stdout.log",
                deliv_p,
                draft_answer_path=draft_deliv_p,
            )
        if empty_suspected is None:
            empty_suspected = detect_empty_result_giveup(
                log_dir / "agent_stdout.log",
                deliv_p,
            )
        if crash_suspected is not None and empty_suspected is not None:
            break

    # 工具死迴圈觀察（effects_20261105 dabstep-23）：同一命令連續重複＝疑似迴圈。
    # 觀察與標記，不是裁決：不改變重驗結果與停滯判定（None＝未偵測到）。
    agent = {**agent, "tool_loop_suspected": detect_tool_loop(log_dir / "agent_stdout.log")}
    # crash→放棄觀察（effects_20261105 dabstep-1753 generic）：session 內崩潰＋
    # 最終答案是放棄詞（None/Not Applicable…）⇒ 標記。觀察與標記，不是裁決：
    # 不改變重驗結果與停滯判定（None＝未偵測到）。
    agent = {**agent, "crash_giveup_suspected": crash_suspected}
    # 静默空结果 → 放棄 觀察（contrast1753_20261105 dabstep-1753 localized r1：脚本
    # 成功跑过但输出为空＋最終答案為放棄詞 ⇒ 標記）。观察与標記、非裁決。
    agent = {**agent, "empty_result_giveup_suspected": empty_suspected}
    tampered = _source_tampered_files(authoritative, ws)
    if tampered:
        # P000-20261105-02：改來源迎合交付不得翻 PASS。來源改動之輪，原非 PASS 的條目一律不得標為 PASS。
        before_map = {c.claim_id: c.status for c in before}
        sanitized_after = []
        for c in after:
            if c.status == "PASS" and before_map.get(c.claim_id) != "PASS":
                orig_st = before_map.get(c.claim_id, "FAIL")
                st = orig_st if orig_st in ("FAIL", "UNKNOWN", "CONFLICT") else "FAIL"
                sanitized_after.append(
                    ClaimResult(
                        claim_id=c.claim_id,
                        status=st,
                        detail=f"來源改動（{', '.join(tampered)}）不可接受，依規則不得翻 PASS",
                        evidence={**c.evidence, "source_tampered": list(tampered)},
                        verifier=c.verifier,
                        verifier_version=c.verifier_version,
                        required=c.required,
                        authority=c.authority,
                    )
                )
            else:
                sanitized_after.append(c)
        after = sanitized_after
        diff = diff_results(before, after)
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
    #: 已滿足交付物的位元組級保留（P20261106_0834-2）：初始驗即已滿足的交付物中，
    #: 最終工作區檔案與原草稿 SHA256 逐檔核對相符＝preserved；
    #: 不符或缺失（被覆寫／竄改／刪除）＝mutated。「修復只改未滿足產物」由本欄直接判定，
    #: 不再只依賴條目級 regressed 間接推估。
    satisfied_preserved: tuple[str, ...]
    satisfied_mutated: tuple[str, ...]

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


def _file_sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


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
    max_tool_calls: int | None = None,
    max_tokens: int | None = None,
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

    硬預算上限（opt-in，2026-11-06）：`max_tool_calls`／`max_tokens` 逐輪轉發給執行器
    run()；皆 None＝不量不殺、呼叫形狀與以前逐位元組相同。設定的值如實記錄在
    cost["budget"]（None＝未設；不填 0）。
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
                max_tool_calls=max_tool_calls, max_tokens=max_tokens,
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

    # 來源改動（P000-20261105-02）：任一輪改寫權威來源即不可接受
    source_tampered = any(r.source_tampered for r in rounds)
    source_tampered_files = tuple(sorted({f for r in rounds for f in r.source_tampered}))
    if source_tampered:
        # P000-20261105-02：改來源迎合交付不得翻 PASS。若全段曾發生來源改動，原非 PASS 的條目一律不得標為 PASS。
        before_map = {c.claim_id: c.status for c in before}
        for cid in list(final_status.keys()):
            if final_status[cid] == "PASS" and before_map.get(cid) != "PASS":
                orig_st = before_map.get(cid, "FAIL")
                final_status[cid] = orig_st if orig_st in ("FAIL", "UNKNOWN", "CONFLICT") else "FAIL"

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

    # 已滿足交付物位元組級保留（P20261106_0834-2）：initial_satisfied（初始驗即已滿足）
    # 各交付物檔案，比對最終工作區與原草稿之 SHA256：相符⇒preserved；
    # 不符或缺失⇒mutated（覆寫／竄改／刪除皆不算保留）。
    # 零輪（無缺口）⇒無最終工作區，原草稿未動⇒以原草稿自比＝全部 preserved。
    initial_satisfied, _unsatisfied = _partition_deliverables(req_set, before)
    final_ws = pathlib.Path(rounds[-1].workspace) if rounds else d_dir
    satisfied_preserved: list[str] = []
    satisfied_mutated: list[str] = []
    for d in sorted(initial_satisfied):
        orig_f = d_dir / d
        if not orig_f.is_file():
            continue   # 交付物非檔案（無比對基準）⇒兩欄皆不計
        final_f = final_ws / d
        if final_f.is_file() and _file_sha256(final_f) == _file_sha256(orig_f):
            satisfied_preserved.append(d)
        else:
            satisfied_mutated.append(d)

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
                   "max_tool_calls": max_tool_calls,  # opt-in；None＝未設（不量不殺）
                   "max_tokens": max_tokens,          # opt-in；None＝未設（不量不殺）
                   "note": ("硬上限＝輪數×單輪 wall timeout＋輪數；tool 呼叫數／token "
                            "硬上限 opt-in：未設＝不量不殺；設了＝執行器超過即殺，"
                            "該輪 budget_exceeded 如實記錄")},
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
        satisfied_preserved=tuple(satisfied_preserved),
        satisfied_mutated=tuple(satisfied_mutated),
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
    if isinstance(provider, pathlib.Path) or isinstance(model, pathlib.Path):
        raise TypeError(
            "_default_build(provider, model) 是工廠函式，請先呼叫取得 BuildFn，"
            "勿直接作為 build(prompt, ws) 傳入"
        )
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

        # 12) 静默空结果 → 放棄（contrast1753_20261105 dabstep-1753 localized r1 形状）：
        #     脚本成功跑过但输出为空＋最終答案為放棄詞 ⇒ 偵测到、針對性提示只进
        #     localized 臂（generic 对照臂不带）；交出实质答案 ⇒ 不偵测（不捏造）。
        empty_log = tmp / "empty_run.log"
        empty_log.write_text("\n".join(json.dumps(o) for o in (
            {"type": "tool_execution_start", "toolCallId": "c1", "toolName": "bash",
             "args": {"command": "cat << 'EOF' > solution.py\n...\nEOF\npython3 solution.py"}},
            {"type": "tool_execution_end", "toolCallId": "c1", "toolName": "bash",
             "result": {"content": [{"type": "text", "text": "\n"}]}, "isError": False},
        )) + "\n", encoding="utf-8")
        ans12 = tmp / "empty_run_answer.txt"
        ans12.write_text("None", encoding="utf-8")
        hit12 = detect_empty_result_giveup(empty_log, ans12)
        ans12.write_text("47", encoding="utf-8")
        miss12 = detect_empty_result_giveup(empty_log, ans12)
        ans12.write_text("None", encoding="utf-8")
        hint12 = _empty_result_giveup_hint_line()
        obs12 = {"empty_result_giveup_suspected": hit12} if hit12 else {}
        loc12 = build_repair_prompt(task_dir, rs, draft, before,
                                    feedback_mode="localized", prev_round_agent=obs12)
        gen12 = build_repair_prompt(task_dir, rs, draft, before,
                                    feedback_mode="generic", prev_round_agent=obs12)
        check("静默空结果→放棄（脚本成功跑过＋输出为空＋放棄詞⇒偵测到且进 localized 提示；"
              "generic 不带；实质答案⇒不偵测；提示行不含数字）",
              hit12 is not None
              and hit12["empty_run_count"] >= 1
              and any("solution.py" in s for s in hit12["empty_run_scripts"])
              and not any(ch.isdigit() for ch in hint12)
              and hint12 in loc12
              and hint12 not in gen12
              and miss12 is None,
              f"hit={hit12} miss={miss12}")

        # 13) 版本後綴直譯器（r1078）：python3.12 / 前綴路徑＋版本 / 版本＋參數
        #     ＝同一静默空结果形状（5a2384fa 補前綴路徑與參數，版本後綴是剩餘盲區）；
        #     重定向排除對版本形狀同樣成立。
        ver_log = tmp / "versioned_py.log"
        ans13 = tmp / "versioned_py_answer.txt"
        ans13.write_text("None", encoding="utf-8")

        def _ver_hit(cmd: str) -> dict[str, Any] | None:
            ver_log.write_text("\n".join(json.dumps(o) for o in (
                {"type": "tool_execution_start", "toolCallId": "c1", "toolName": "bash",
                 "args": {"command": cmd}},
                {"type": "tool_execution_end", "toolCallId": "c1", "toolName": "bash",
                 "result": {"content": [{"type": "text", "text": "\n"}]}, "isError": False},
            )) + "\n", encoding="utf-8")
            return detect_empty_result_giveup(ver_log, ans13)

        h13a = _ver_hit("python3.12 solution.py")
        h13b = _ver_hit("/usr/local/bin/python3.12 -u calc.py")
        h13c = _ver_hit("python3.12 solution.py > out.txt")
        check("版本後綴直譯器空结果形状（python3.12／前綴路徑＋版本＋-u⇒偵测到；" "重定向⇒不偵测）",
              h13a is not None
              and "solution.py" in h13a["empty_run_scripts"]
              and h13b is not None
              and "calc.py" in h13b["empty_run_scripts"]
              and h13c is None,
              f"a={h13a} b={h13b} c={h13c}")

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
    ap.add_argument("--max-tool-calls", type=int, default=None,
                    help="單輪 agent 工具呼叫數硬上限（超過即殺；不給＝不量不殺）")
    ap.add_argument("--max-tokens", type=int, default=None,
                    help="單輪 agent token 用量硬上限（累計超過即殺；不給＝不量不殺）")
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
        timeout_s=args.timeout,
        max_tool_calls=args.max_tool_calls, max_tokens=args.max_tokens,
        synthetic=args.synthetic,
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
        if outcome.satisfied_mutated:
            print(f"SATISFIED_MUTATED: {', '.join(outcome.satisfied_mutated)}"
                  f"  ← 原已滿足交付物被改寫，未遵守保留約束（拒收）")
        if outcome.satisfied_preserved:
            print(f"satisfied_preserved: {', '.join(outcome.satisfied_preserved)}")
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
    # P20261106_1035-2：已滿足交付物被改寫＝未遵守「修復只改未滿足產物並保留其餘成果」，
    # 與 source_tampered 同等嚴格把關，即使表面全 PASS 也拒收
    if outcome.satisfied_mutated:
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
