#!/usr/bin/env python3
"""這支在架構裡承重什麼：R534 的**凍結常數**——四格共用的那一份。

R534 問的是一句話：**把 Vacant 的驗收閘門裝進「別人的」agent harness（pi）
之後，宣告完成那一刻有沒有人擋一下，會不會改變交出去的東西。**
四格 ＝ 2（有／沒有閘門）× 2（有／沒有思考）：

    A1 ＝ pi ＋ Vacant 閘門 ＋ 12B 有思考      B1 ＝ 純 pi ＋ 12B 有思考
    A2 ＝ pi ＋ Vacant 閘門 ＋ 12B 沒思考      B2 ＝ 純 pi ＋ 12B 沒思考

四格**同 prompt、同工具、同預算上限**。唯一的兩個差異寫死在這一支裡，
別的地方不准再造第三個差異：

  1. `arm`：`vacant` ⇒ `agent_settled` 之後跑可見驗收、沒過就回饋重改、
     用完就拒交；`plain` ⇒ 宣告完成就收（`accepted` 結構性恆真，
     **包含「宣告完成但什麼都沒寫」那一格**，引用時必須跟著講這一句）。
  2. `reasoning_effort`：不送 ⇒ 1003 會思考；送 `"none"` ⇒ 不思考。
     這個欄位只存在於 wire 上 ⇒ 它的真相來源是 `wire_tap.py` 的 JSONL，
     不是 harness 的自述（12 §4.3：自述不算證據，收據才算）。

⚠ **R534 的數字只准在 R534 內部配對。** pi 的 system prompt 組裝方式、
  工具是 native tool-calling 而不是 R530 的 bash 圍欄文字協定、訊息序列化
  都與 `ops/gain/r530/openwork_arms.py` 不同 ⇒ 不得與 `runs/g_r530_*`、
  `runs/g_r460_*`、`runs/g_r532_*` 跨 run 併算。這一句同時寫在收官檔裡。

⚠ **誠實邊界（改碼請保留）**：閘門 records and gates，不 proves。
  它證明「宣告完成之後，可見驗收先跑了一次，沒過就沒出貨」，
  **不**證明交出去的東西是對的——可見驗收是客戶給的那幾條，不是真需求
  （`vacant/suitegauge.py` 的單邊保證，逐字沿用）。

隱藏測資的紅線：本檔案、擴充、sidecar 的任何一條路徑都不碰 `hidden/`。
它只在 driver 於工作區凍結＋打包之後、在另一個目錄裡用來事後算分。
"""
from __future__ import annotations

import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from ops.gain.r530.openwork_arms import PERSONAS, persona_for  # noqa: E402,F401
from ops.gain.r530.sandbox import DEFAULT_TEST_TIMEOUT_S  # noqa: E402
from vacant.memory import assert_ks1_clean  # noqa: E402

# ══ 四格 ═════════════════════════════════════════════════════════════════
#: `arm`＝有沒有閘門；`think`＝送不送 `reasoning_effort:"none"`。
#: **兩台後端都載著同一個 gguf，但 LM Studio 版本不同**（1003＝0.4.24 會思考、
#: 1004＝0.4.17 不會）⇒ 預設四格全部走 **1003**，讓「思考／不思考」這一刀
#: 只由旗標切開。把不思考那兩格搬到 1004 會讓那一刀同時混進「換了一台機器」，
#: 要那樣做必須是**明示**的（`--upstream-nothink`），而且收官要單獨講。
CELLS: dict[str, dict] = {
    "A1": {"arm": "vacant", "think": True},
    "A2": {"arm": "vacant", "think": False},
    "B1": {"arm": "plain", "think": True},
    "B2": {"arm": "plain", "think": False},
}
CELL_ORDER = ("A1", "A2", "B1", "B2")
ARMS = ("vacant", "plain")

#: 端點（既有事實，不要再驗一次）。
UPSTREAM = {
    "1003": "http://100.119.113.56:1234",
    "1004": "http://100.86.226.21:1234",
}
MODEL_ID = "gemma-4-12b-it-qat"

#: 每格一個 tap 埠——**wire log 本身就是歸屬**，不必只靠 header。
#: header（`x-r534-*`）另外再蓋一層，兩邊對不起來就是 harness 有問題。
TAP_PORTS = {"A1": 8541, "A2": 8542, "B1": 8543, "B2": 8544}

# ══ 預算（四格共用；**寫死成模組常數，不做成 CLI 旋鈕**）═══════════════════
#
# 數值形狀沿用 `openwork_arms.OPENWORK_BUDGET`，好讓兩個 run 的「撞線」意思
# 一樣；**但數字本身不可跨 run 併算**（見模組 docstring）。
#
# ⚠ `max_wall_s` **不是每題牆鐘的上界**：它在呼叫之間檢查，單次請求可以
#   燒掉遠多於這個數字。收官報 `wall_s` 的分佈，不准講成硬上界。
# ⚠ 「同預算上限」的操作定義 ＝ **四格的這一份 dict 逐位元相同**，
#   不是「四格實際用掉的呼叫數相同」。`plain` 兩格宣告完成就收，
#   結構上用不到上限——上限相同、用量各自落盤（R460 的同一條口徑）。
R534_BUDGET = {
    "max_model_calls": 72,          # 每格總上限（跨閘門輪累計）
    "max_calls_per_attempt": 24,    # 只管 `resample` 政策的每一份
    "max_gate_rounds": 5,           # `revise`：閘門輪數用完＝拒交
    "max_conf_attempts": 3,         # `resample`：最多三份
    "max_completion_tokens": 120_000,   # 累計 completion（**不是** total 的和）
    # 單通 prompt 的硬上界 ⇒ `budget_context`。**48k 不是 200k，理由是機器**：
    # 這兩台 LM Studio 的 ctx 是 262,144 但 parallel 4 ⇒ **每槽 65,536**，
    # 而 `models.json` 給的 `maxTokens` 是 16,384 ⇒ prompt 能用的上界是
    # 65,536 − 16,384 ＝ 49,152。寫 200k（甚至 60k）這一條都永遠咬不到——
    # 先炸的是槽的 context，而那會以「provider 回錯 → pi 自己重試三次 →
    # 空訊息」的樣子出現，也就是把「脈絡用光」這個**真實行為**變成一個
    # 看起來像基建故障的東西。48,000 留 1,152 的餘裕給 template 的開銷。
    # ⚠ 改 `models.json` 的 `maxTokens` 或後端的 parallel 就要一起改這一格。
    "max_context_tokens": 48_000,
    "max_tool_calls": 120,
    "max_wall_s": 7_200,
    "tool_timeout_s": 120,
    "tool_timeout_max_s": 300,
    "gate_test_timeout_s": DEFAULT_TEST_TIMEOUT_S,
    "nudge_budget": 2,
}

#: 為什麼 token 上限只算 completion：多輪迴圈每一通都把整段對話當 prompt 重送
#: ⇒ `total_tokens` 的和隨輪數二次成長，綁住的是「對話多長」不是「模型寫了多少」。
#: **兩種 token 逐格都要落盤**——換了分子就更要讓分母看得見。
TOKEN_ACCOUNTING_NOTE = "completion-only; prompt logged separately"

#: 停止理由的**封閉集合**。多一個就是規格變更——不准在別處臨時造字串。
STOP_REASONS = frozenset({
    "visible_pass",          # 過了可見驗收（vacant）
    "declared_done",         # 宣告完成就收（plain）
    "gate_exhausted",        # vacant/revise：閘門輪用完仍不過 ⇒ 拒交
    "attempts_exhausted",    # vacant/resample：每一份都不過 ⇒ 拒交
    "budget_calls", "budget_tokens", "budget_wall", "budget_tool_calls",
    "budget_context",        # 單通 prompt 超過上限 ⇒ 拒交
    "nudge_exhausted",       # 宣告完成但工作區沒動，逼問額度用完
    "pi_exit_unsettled",     # pi 行程結束時 harness 還沒收到任何裁決（基建）
    "harness_void",          # 不變量破了（system prompt／wire 旗標／起點樹雜湊）
})

#: 哪幾種算**拒交**。`budget_calls`／`budget_wall` 不算——它們是「沒跑完」
#: 不是「不交」，混在一起會讓 `plain` 的結構性 0 變成會跳動的數字。
#: ⚠ `plain` 兩格一格都拿不到：它沒有拒交語意（accepted 恆為 True）。
REFUSAL_REASONS = ("gate_exhausted", "attempts_exhausted", "budget_context")

#: 回給模型的工具輸出截斷長度。**落盤的是全文**（`calls.jsonl`）。
TOOL_OUTPUT_CLIP = 6000

# ══ 凍結的 prompt／回饋常數 ══════════════════════════════════════════════
#
# ⚠ 這幾段**不是** `openwork_arms` 那幾段的複製品，也不准改成一樣：
#   R530 的工具是「回一個 ```bash 圍欄」的文字協定，R534 的工具是 pi 的
#   native tool-calling（`run_bash`）。把 R530 的字照抄過來會教模型寫圍欄，
#   而圍欄在這裡不會被執行 ⇒ 量到的是「模型會不會用錯協定」。
#   **協定不同正是 R534 不可與 R530 併表的原因之一。**
RULES = """Rules:
- You have exactly one tool: run_bash. It runs a single shell command in your
  working directory and returns its exit code, its stdout and its stderr.
- Use run_bash for everything: reading files (cat, sed -n), searching (grep,
  find), writing files (a heredoc or python3), and running commands.
- You are offline and your working directory is the whole world you have. There
  is no network, no package installation, and nothing outside this directory.
- Some commands are stopped by a hard guard and come back as BLOCKED with a
  reason. Do not look for a way around a block.
- Work in small verified steps: run a command, read its real output, then
  decide. Do not say something worked without having seen the output that shows
  it.
- When you consider the work finished, reply with a short plain-text summary and
  do not call any tool."""

TASK_MESSAGE = """{goal}

{contract}

Your working directory already contains these files:

{tree}

Write your solution in that directory."""

#: 宣告完成但工作區與樣板逐位元相同 ⇒ 逼問一次（額度 `nudge_budget`）。
#: **四格都有這一則**：它擋的是「模型自認完成 ≠ 真的完成」，不是閘門。
#: 只給 `vacant` 會變成四格之間的第二個差異，那樣就切不出閘門的效果了。
NUDGE_NO_WORK = """You have not changed any file in the working directory yet.
Stop analyzing and write the actual files now, using run_bash."""

#: `vacant` 專用的回饋。**逐字凍結**；`{block}` 由
#: `ops/gain/r530/acceptance.render_failures()` 渲染（只給**可見**驗收的結果）。
#: 隱藏驗收的存在、條數、內容一律不進這一段（紅線）。
FEEDBACK_TEMPLATE = """The checks that ship with this task were run against your
working directory. They did not all pass.

{block}

Fix the working directory. When you consider it finished, reply with a short
plain-text summary and do not call any tool."""

#: 工具結果的**凍結表頭**：模型看得出來這一段是機器輸出不是人在說話。
TOOL_RESULT_HEADER = "TOOL RESULT (run_bash). This is machine output, not a person."
TOOL_RESULT_TEMPLATE = """{header}

$ {command}
exit={rc}
--- stdout ---
{stdout}
--- stderr ---
{stderr}"""

BLOCKED_TEMPLATE = """{header}

$ {command}
BLOCKED: {why}
This command was stopped by a hard guard. Do not look for a way around it."""

#: `run_bash` 的工具描述——**四格逐字相同**，而且它會進 payload 的 `tools`
#: 欄位 ⇒ 它的 sha256 是一個跨格不變量（`before_provider_request` 會斷言）。
RUN_BASH_DESCRIPTION = (
    "Run one shell command in the working directory and return its exit code, "
    "stdout and stderr. The command runs offline in an isolated sandbox; "
    "nothing outside the working directory exists."
)

# ── KS-1 可執行防呆：四段模板一段都不准有責任修辭 ────────────────────────
for _t in (RULES, TASK_MESSAGE, NUDGE_NO_WORK, FEEDBACK_TEMPLATE,
           TOOL_RESULT_TEMPLATE, BLOCKED_TEMPLATE, RUN_BASH_DESCRIPTION):
    assert_ks1_clean(_t)


def system_prompt(persona_text: str) -> str:
    """system ＝ persona ＋ 凍結的 Rules。四格**逐字相同**（同一題同一 attempt）。

    ⚠ 這個字串會被擴充在 `before_agent_start` 裡**整段取代**回去，
      而不是「檢查 pi 組出來的那一份等不等於它」。理由：pi 會把
      `AGENTS.md`／`~/.pi/agent/SYSTEM.md`／skills／tool snippets 串進去，
      那些東西會隨機器狀態改變 ⇒ 用檢查的，四格會在不同時間以不同方式紅；
      用取代的，四格在 wire 上就是同一段位元組。工具說明不會因此消失——
      pi 走的是 native tool-calling，schema 在 payload 的 `tools` 欄位。
    """
    return persona_text + "\n\n" + RULES


def system_prompt_sha256(persona_text: str) -> str:
    return hashlib.sha256(system_prompt(persona_text).encode("utf-8")).hexdigest()


def task_message(goal: str, contract: str, tree: str) -> str:
    return TASK_MESSAGE.format(goal=goal.strip(), contract=contract.strip(),
                               tree=tree)


def clip(s: str, n: int = TOOL_OUTPUT_CLIP) -> str:
    """回給模型的截斷。**落盤的是全文**（`calls.jsonl`）。

    頭尾都留而不是純 tail：指令輸出的資訊常常在開頭（錯誤訊息）也在結尾
    （traceback 最後一行）。形狀沿用 `openwork_arms.clip`。
    """
    s = s or ""
    if len(s) <= n:
        return s
    head = n // 2
    tail = n - head
    return s[:head] + f"\n…[{len(s) - n} characters omitted]…\n" + s[-tail:]


def budget_stop(calls_used: int, completion_tokens: int, tool_calls: int,
                elapsed_s: float, last_prompt_tokens: int = 0) -> str | None:
    """呼叫數／completion tokens／工具次數／牆鐘／脈絡任一超過就停。

    撞線是一個**獨立的 outcome**，不可以混進失敗率——每個 stop_reason 分開記。
    """
    b = R534_BUDGET
    if calls_used >= int(b["max_model_calls"]):
        return "budget_calls"
    if completion_tokens >= int(b["max_completion_tokens"]):
        return "budget_tokens"
    if last_prompt_tokens >= int(b["max_context_tokens"]):
        return "budget_context"
    if tool_calls >= int(b["max_tool_calls"]):
        return "budget_tool_calls"
    if elapsed_s >= float(b["max_wall_s"]):
        return "budget_wall"
    return None


def assert_cells_differ_only_as_declared() -> None:
    """可執行防呆：四格除了 `arm` 與 `think` 之外沒有第三個欄位。

    這一條看起來瑣碎，但它擋的正是最容易發生的那種汙染——有人為了跑快一點
    給某一格多開一個旋鈕，然後那個旋鈕變成量到的東西的一部分。
    """
    keys = {frozenset(v.keys()) for v in CELLS.values()}
    if keys != {frozenset({"arm", "think"})}:
        raise SystemExit(f"CELLS 多了宣告以外的欄位：{keys}。停。")
    if {c["arm"] for c in CELLS.values()} != set(ARMS):
        raise SystemExit("CELLS 的 arm 集合與 ARMS 不符。停。")
    if len({(c["arm"], c["think"]) for c in CELLS.values()}) != 4:
        raise SystemExit("四格不是 2×2 的完整叉乘。停。")


assert_cells_differ_only_as_declared()


def main() -> int:
    import json

    print(json.dumps({
        "cells": CELLS,
        "budget": R534_BUDGET,
        "stop_reasons": sorted(STOP_REASONS),
        "refusal_reasons": list(REFUSAL_REASONS),
        "rules_sha256": hashlib.sha256(RULES.encode()).hexdigest(),
        "feedback_sha256": hashlib.sha256(FEEDBACK_TEMPLATE.encode()).hexdigest(),
        "run_bash_description_sha256":
            hashlib.sha256(RUN_BASH_DESCRIPTION.encode()).hexdigest(),
        "personas": [p[0] for p in PERSONAS],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
