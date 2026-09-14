#!/usr/bin/env python3
r"""R530 三條臂：`A-SOLO`／`A-CONF`／`A-GATE`——差別**只在宣告完成之後**。

規格：`DECISION_20260913_R530_OPEN_GOAL_WITH_WITHOUT_VACANT_PREREG.md` §二，
＋ Fable 2026-09-13 的建置裁決（三臂定義、預算、工具面、工作區生命週期）。

## 三條臂

| 臂 | 宣告完成之後 | 工作區 | persona |
|---|---|---|---|
| `A-SOLO` | **收。** 那一刻的工作區就是最終交付。無閘門、無回饋、**不存在拒交** | 一個 | 一位 |
| `A-CONF` | 跑可見驗收。過⇒出貨。不過⇒**工作區重置回樣板**、**換一位 persona**、**全新對話**（不告訴它哪裡錯），最多 5 份；全不過⇒**拒交** | 每次嘗試一個全新的 | 每次換 |
| `A-GATE` | 跑可見驗收。過⇒出貨。不過⇒**失敗原文貼回同一段對話**、同一個工作區、同一位 persona，最多 5 個閘門輪；用完⇒**拒交** | 一個，全程累積 | 一位 |

## KS-1（鐵律 1）在這裡是什麼意思

R460 的 H 臂三條 prompt **本來就不同**（那裡量的是 prompt 本身）。
**R530 不是那樣**：Fable 裁決「三臂 prompt 逐字相同，唯一差別是宣告完成之後
發生什麼」。所以這裡有**兩道** import 時的斷言，繞不過去：

  1. `assert_ks1_clean`（`vacant/memory.py`）對每一個凍結字串跑一遍
     ——寫出「你有責任／會被懲罰／有人在看」類措辭，這支就 import 不進來。
  2. `assert_arm_prompts_identical()`：對同一個 fixture 題目，三條臂算出來的
     **system ＋ 第一則 user 訊息**必須**逐位元相同**。
     ⚠ 這條斷言的意義在於 `initial_messages()` **收** `arm` 參數：
     它現在沒有用到那個參數，而斷言保證的是**以後也不准用**——
     有人哪天加一個 `if arm == "A-GATE"` 的分支，import 就會炸。

第一則訊息之後的差別**只有兩件**（§二-2 逐字）：
(a) 宣告完成之後會不會有一則新的 user 訊息進來；
(b) 那則訊息的內容是可見驗收的失敗原文（`A-GATE`），還是根本不存在
    （`A-SOLO`），或是整段對話重開（`A-CONF`）。
**worker 事前不知道自己在哪一條臂。**

## 工具面：一個 `run_bash`，**原生 `tools`**

工具只有一個，理由逐字沿用 `ops/localagent.py` 的 docstring：12B 級模型工具
越多越容易選錯，而讀檔、寫檔、跑指令、跑測試全都能經過 shell；附帶好處是
每個動作都以**可重跑的指令**落盤。

⚠ **協定的預設值在 2026-09-13 被冒煙推翻過一次，這一段要留著。**
預註冊 §二-4 寫的是「預設走文字協定（```bash 圍欄），原生 `tools` 本檔沒有量過」。
冒煙 `runs/_smoke/g_r530_real_1`（2 題 × 3 臂 × 1 seed，真後端）量到的是相反的：

| 協定 | 實測 |
|---|---|
| 文字（```bash 圍欄） | **不通**：6 格裡 4 格零工具呼叫、工作區逐位元沒動 ⇒ `nudge_exhausted`。模型要嘛回 ```python 區塊（單通 18,023 completion tokens），要嘛吐它自己的 `<|tool_call>call:bash{…}` 內部格式。 |
| 原生 `tools` | **通**：`finish_reason="tool_calls"`、`tool_calls` 陣列乾淨、22 completion tokens。 |

⇒ 預設改成 `native`（`ops/gain/r530/brain_native.py`），文字協定留著當備援。
R460 那個「圍欄遵循 925/925」**不能拿來支持文字協定在這裡可行**：
那是一問一答的「寫一個 ```python 區塊」，不是多輪工具迴圈。
模式逐格落盤在 `summary.tool_protocol` 與每一列 `rows.jsonl`，
**兩種模式的資料不得混算**（SPEC_GAIN §7 的同一條）。

`DENY`（`ops/localagent.py:51-65`）**原樣沿用**，再加 R530 專用的三條擋門
（跳出工作區、觸網、讀 `hidden`／`rubric` 路徑）。擋下來的指令**照樣落盤**
（`blocked: true`）——「模型試圖做什麼」比「模型做成了什麼」更值得留著看。

⚠ **擋門不是隔離。** 真正的隔離由 `ops/gain/r530/sandbox.py` 的 `bwrap` 後端
提供（最小 rootfs ＋ net namespace）；`DENY` 是第二層，而且是比較弱的那一層。
退到 `none` 後端時，只剩這一層——那件事寫在 `backend_meta.honest_bound`。
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pathlib
import random
import re
import shutil
import subprocess
import sys
import tarfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from ops.gain.brain_cline import InfraVoid  # noqa: E402
from ops.gain.r530 import acceptance, receipts, wshash  # noqa: E402
from ops.gain.r530.sandbox import (DEFAULT_TEST_TIMEOUT_S,  # noqa: E402
                                   Sandbox, SandboxInfraError)
from vacant.memory import assert_ks1_clean  # noqa: E402

ARMS = ("A-SOLO", "A-CONF", "A-GATE")

# ══ 預算（三臂共用同一份，**寫死成模組常數，不做成 CLI 旋鈕**）══════════
#
# Fable 2026-09-13 裁決：`max_model_calls=24`、`max_tokens`、`max_wall` 共用。
# ⚠ `A-GATE` vs `A-SOLO` **不是等預算比較，而且故意不是**（§八-4）：
#   人類問的就是「收第一份」對「有閘門」。等預算那一刀由
#   `A-GATE` vs `A-CONF` 負責（同樣 24 通、同樣 5 輪上限）。
# ⚠ `max_wall_s` **不是每題牆鐘的上界**（§二-3 的誠實邊界逐字沿用）：
#   它在呼叫之間檢查；單次請求在 `--request-timeout-s` × `retries` 之下
#   最壞可以燒掉遠多於這個數字。收官報 `wall_s` 的分佈，不准講成硬上界。
OPENWORK_BUDGET = {
    "max_model_calls": 24,
    # ⚠ **token 上限只算 completion**（Fable 2026-09-14 裁決）。
    #   原本算的是逐通 `total_tokens` 的和，而多輪迴圈每一通都把整段對話當
    #   prompt 重送 ⇒ 那個和隨輪數**二次成長**。冒煙實測單格
    #   prompt 207,591／completion 14,542：用總和當上限，實際綁住的是
    #   「對話多長」而不是「模型寫了多少」，5–8 通就撞滿 120k。
    #   改成只算 completion 之後，40,000 綁的是生成量本身。
    #   ⚠ **兩種 token 逐格都要印**（`rows.jsonl` 的 `prompt_tokens`／
    #     `completion_tokens`）——換了分子就更要讓分母看得見。
    "max_completion_tokens": 40_000,
    # 脈絡本身的硬上界：單通的 prompt 超過它 ⇒ `budget_context` 拒交。
    # 它擋的是另一種失控：對話長到端點開始截斷或變慢，而那在
    # `max_completion_tokens` 上完全看不出來。
    "max_context_tokens": 200_000,
    "max_wall_s": 2_400,
    "max_gate_rounds": 5,
    "max_tool_calls": 40,
    "tool_timeout_s": 120,
    "tool_timeout_max_s": 300,
    "gate_test_timeout_s": DEFAULT_TEST_TIMEOUT_S,
    "nudge_budget": 2,
    "max_commands_per_turn": 3,
}

#: 停止理由的**封閉集合**。多一個就是規格變更——不准在別處臨時造字串。
STOP_REASONS = frozenset({
    "visible_pass",            # 過了可見驗收（GATE／CONF）
    "declared_done",           # 宣告完成就收（SOLO）
    "gate_exhausted",          # GATE：閘門輪用完仍不過 ⇒ 拒交
    "attempts_exhausted",      # CONF：五份都不過 ⇒ 拒交
    "budget_calls", "budget_tokens", "budget_wall", "budget_tool_calls",
    "budget_context",          # 單通 prompt 超過 max_context_tokens ⇒ 拒交
    "nudge_exhausted",         # 宣告完成但工作區沒動，逼問額度用完
})

#: 哪幾種停止理由算**拒交**。`budget_calls`／`budget_wall` 不算——
#: 它們是「沒跑完」不是「不交」，混在一起會讓 P-W3 的結構性 0 變成會跳動的數字。
#: ⚠ `A-SOLO` 一格都拿不到：它沒有拒交語意（accepted 恆為 True，見 `run_cell`）。
REFUSAL_REASONS = ("gate_exhausted", "attempts_exhausted", "budget_context")

#: 回給模型的工具輸出截斷長度（**落盤的是全文**，沿用 localagent 的形狀）。
TOOL_OUTPUT_CLIP = 6000

# ══ DENY：`ops/localagent.py` 那一份 ＋ R530 專用三條 ════════════════════
#
# 前 13 條逐字沿用（`tests/test_r530_arms.py` 用原始碼比對釘死「沒有被改寬」）。
_LOCALAGENT_DENY = [
    (r"\brm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*[rf]", "rm -rf：run 目錄是證據，刪掉就沒有了"),
    (r"\bgit\s+push\b.*(--force|-f)\b", "force push：會改寫別人也在用的歷史"),
    (r"\bgit\s+reset\s+--hard\b", "reset --hard：會丟掉未提交的實驗產物"),
    (r"\bgit\s+clean\b", "git clean：會刪掉 untracked 的 run 目錄"),
    (r"\bgit\s+checkout\s+\.", "checkout .：同上，會丟掉未提交的改動"),
    (r"\bsudo\b", "sudo：需要人類決定"),
    (r"\bshutdown\b|\breboot\b|\bpoweroff\b", "關機／重開"),
    (r"\bmkfs\b|\bdd\s+if=", "磁碟層級操作"),
    (r">\s*/dev/sd", "直接寫磁碟裝置"),
    (r"\btouch\s+.*\bSTOP\b", "touch STOP：迴圈要一直迭代，停止只有人類能決定"),
    (r"\bkill\b.*\bloop\.sh\b|\bpkill\b.*loop", "殺掉迴圈本身"),
    (r"\.cline-keys|\.hf-token|identity\.key|\.git-credentials",
     "秘密憑證：不要讀、不要印、不要複製"),
]

#: R530 專用的三條。第三條命中要單獨計數（`vgt.deny_hidden_read_n`，§五-3 第 4 項），
#: 因為它不只是「被擋下來」，它是一次**試圖讀 GT** 的紀錄。
DENY_ESCAPE = "r530_escape"
DENY_NETWORK = "r530_network"
DENY_HIDDEN = "r530_hidden_read"

_R530_DENY = [
    # ⚠ 這三條**刻意寫得很窄**。寬的版本（「任何絕對路徑一律擋」）在第一次
    #   冒煙就會把 `cat > solution.py <<'EOF' … #!/usr/bin/env python3 … EOF`
    #   擋掉——那不是攔截逃逸，那是把三條臂一起變笨，而且笨的程度取決於
    #   模型多常寫 shebang，於是量到的東西一半是「模型會不會踩到我們的正則」。
    #   真正的隔離由 `sandbox.py` 的 `bwrap` 後端提供（最小 rootfs：
    #   工作區以外的東西在沙箱裡**不存在**）；這三條是第二層。
    (r"(?m)^\s*cd\s+(/|\.\.)|(?<![\w.])\.\./|>\s*/(?!dev/null)",
     "跳出工作區：這一格的工作區就是全部，外面的東西不在題目裡", DENY_ESCAPE),
    (r"\b(curl|wget|nc|ncat|telnet|ssh|scp|rsync|pip|pip3|apt|apt-get)\b"
     r"|\bgit\s+(clone|fetch|pull|push|remote)\b",
     "觸網：這一格離線，網路上的東西不在題目裡", DENY_NETWORK),
    (r"\bhidden\b|\brubric\b",
     "隱藏驗收與評分表不在工作區裡，也不准去找", DENY_HIDDEN),
]

#: `(pattern, why, tag)` 的完整清單。前 13 條的 tag 是 `localagent`。
DENY = ([(p, w, "localagent") for p, w in _LOCALAGENT_DENY] + _R530_DENY)

#: heredoc 的開頭：`<<EOF`／`<<-'EOF'`／`<< "EOF"`。
_HEREDOC_START = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def strip_heredoc_bodies(command: str) -> str:
    """把 heredoc 的**內容**從指令文字裡拿掉，只留下 shell 本身。

    為什麼這件事承重：`DENY` 是對「模型寫了什麼 shell」的擋門，不是對
    「模型寫進檔案的內容」的擋門。不拿掉 heredoc 的話——

      · 寫一個含 shebang 的檔案會撞 `DENY_ESCAPE`（`/usr/bin/env`）；
      · 寫一段註解裡有 "hidden" 的程式會撞 `DENY_HIDDEN`；
      · 寫一個測試檔裡有 `../` 的相對路徑字串會撞 `DENY_ESCAPE`。

    三種都是偽陽性，而且它們會**系統性地**打到「寫比較多程式碼」的那一條臂。
    ⚠ 代價要照實講：把 `rm -rf /` 藏進 heredoc 內容就不會被這一份擋門看到。
      擋不住那一格的是擋門，擋得住的是沙箱——這正是為什麼隔離不能只靠 DENY。
    """
    lines = (command or "").splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = _HEREDOC_START.search(line)
        i += 1
        if not m:
            continue
        word = m.group(2)
        while i < len(lines) and lines[i].strip() != word:
            i += 1
        if i < len(lines):
            out.append(lines[i])          # 終止符留著（它是 shell 的一部分）
            i += 1
    return "\n".join(out)


def deny_reason(command: str) -> tuple[str, str] | None:
    """回 `(why, tag)`；沒有命中回 None。**第一條命中的就是理由**。

    比對的對象是 `strip_heredoc_bodies(command)`，理由見那一支的 docstring。
    """
    shell = strip_heredoc_bodies(command)
    for pattern, why, tag in DENY:
        if re.search(pattern, shell):
            return why, tag
    return None


# ══ persona（三臂共用同一份；`A-CONF` 重抽時往後取一位）═══════════════════
#
# ⚠ 不沿用 `brain_cline.POOL`：那六段是中文，而 R530 的題目與 prompt 全英文
#   （§一-2：換語言會多一個與機制無關的差異）。這六段是它的英文對應物，
#   語氣分佈刻意保持一樣（careful ×2／plain ×2／hasty ×2）。
PERSONAS = (
    ("careful-1", "You are a senior engineer. Before writing code, think through "
                  "the edge cases: empty input, a single element, duplicates, "
                  "negative numbers, mixed types. Check your own work when you "
                  "are done."),
    ("careful-2", "You are an engineer who cares about correctness. List the "
                  "conditions the task states, confirm each one is handled, then "
                  "write the code."),
    ("plain-1",   "You are a programmer."),
    ("plain-2",   "You are a programmer. Complete what the user asks for."),
    ("hasty-1",   "You are a programmer who works fast. Write the shortest "
                  "solution that works and do not overthink it."),
    ("hasty-2",   "You are a programmer. Answer quickly; handling the common "
                  "case is enough."),
)


def persona_for(seed: str, task_id: str, attempt: int) -> tuple[str, str]:
    """第 `attempt` 次嘗試用哪一位 persona（attempt 從 1 起算）。

    ⚠ **鍵裡刻意沒有 `arm`**，這與預註冊 §三-5 的 `Random(f"{seed}:{arm}")`
      是一處**明示偏離**，理由是 Fable 的裁決壓過它：「三臂 prompt 逐字相同」。
      把 arm 放進鍵裡 ⇒ 三條臂第一則訊息的 system 就不同 ⇒ 那條裁決在第一通
      呼叫就破了。所以 persona 由 `(seed, task_id)` 決定，
      `A-CONF` 的第 k 次嘗試往後取第 k−1 位（繞回）。
    """
    rng = random.Random(f"{seed}:{task_id}")
    base = rng.randrange(len(PERSONAS))
    return PERSONAS[(base + attempt - 1) % len(PERSONAS)]


# ══ 凍結的 prompt／回饋常數 ══════════════════════════════════════════════
RULES = """Rules:
- You have exactly one tool: bash. To run a command, reply with a fenced block
  whose language tag is `bash`. You may include up to {max_cmd} such blocks in
  one reply; they run in order.
- Use bash for everything: reading files (cat, sed -n), searching (grep, find),
  writing files (heredoc or python3), and running commands.
- You are offline and your working directory is the whole world you have. There
  is no network, no package installation, and nothing outside this directory.
- Some commands are stopped by a hard guard and come back as BLOCKED with a
  reason. Do not look for a way around a block.
- Work in small verified steps: run a command, read its real output, then decide.
  Do not say something worked without having seen the output that shows it.
- When you consider the work finished, reply with a short plain-text summary and
  no bash block."""

TASK_MESSAGE = """{goal}

{contract}

Your working directory already contains these files:

{tree}

Write your solution in that directory."""

#: 宣告完成但工作區與樣板逐位元相同 ⇒ 逼問一次（額度 `nudge_budget`）。
#: 形狀沿用 `ops/localagent.py` 的 nudge（那裡量到的是「模型自認完成 ≠ 真的完成」）。
NUDGE_NO_WORK = """You have not changed any file in the working directory yet.
Stop analyzing and write the actual files now, using bash."""

#: `A-GATE` 專用的回饋（`A-CONF` 一個字都不給，`A-SOLO` 根本沒有這一則）。
#: **逐字凍結**；`{block}` 由 `acceptance.render_failures()` 渲染。
FEEDBACK_TEMPLATE = """The checks that ship with this task were run against your
working directory. They did not all pass.

{block}

Fix the working directory and reply again. When you consider it finished, reply
with a short plain-text summary and no bash block."""

#: 工具結果貼回去的那一則訊息的**凍結表頭**。
#: 它有兩個用途，兩個都承重：
#:   1. 模型看得出來這一段是機器輸出不是人在說話；
#:   2. `ops/gain/harness_vgt_audit.py --scope r530` 靠它把這一則 user 訊息
#:      認回 `role="tool"`（端點的 chat API 只收 user／assistant，
#:      工具結果只能以 user 訊息回灌——見 `brain_cline.chat` 的參數檢查）。
TOOL_RESULT_HEADER = "TOOL RESULT (bash). This is machine output, not a person."
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

#: 一條指令都沒有、但也還沒宣告完成時不會出現這一則——沒有這種狀態：
#: 沒有 bash 區塊就是宣告完成（`ops/localagent.py` 的同一條判準）。


def rules_text() -> str:
    return RULES.format(max_cmd=OPENWORK_BUDGET["max_commands_per_turn"])


def system_prompt(persona_text: str) -> str:
    """system ＝ persona ＋ 凍結的 Rules。三臂**逐字相同**（同一位 persona 時）。"""
    return persona_text + "\n\n" + rules_text()


def workspace_tree_listing(workspace: pathlib.Path) -> str:
    """給 worker 看的檔案清單——**按路徑排序**，所以三臂拿到的字串相同。"""
    leaves = wshash.tree_leaves(workspace)
    return "\n".join(f"  {leaf['path']}" for leaf in leaves) or "  (empty)"


def initial_messages(task: dict, workspace: pathlib.Path, *, arm: str,
                     persona_text: str) -> tuple[str, list[dict]]:
    """第一則訊息。**`arm` 收了但不准用**——`assert_arm_prompts_identical` 釘死。"""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    system = system_prompt(persona_text)
    user = TASK_MESSAGE.format(
        goal=task["goal"].strip(),
        contract=task["contract"].strip(),
        tree=workspace_tree_listing(workspace),
    )
    return system, [{"role": "user", "content": user}]


# ══ 工具協定（文字協定）═══════════════════════════════════════════════════
_FENCE_RE = re.compile(r"```[ \t]*(bash|sh|shell)[ \t]*\r?\n(.*?)```",
                       re.DOTALL | re.IGNORECASE)


def parse_commands(text: str, limit: int | None = None) -> list[str]:
    """從回覆裡抽出 bash 圍欄區塊。空區塊不算指令。"""
    if limit is None:
        limit = OPENWORK_BUDGET["max_commands_per_turn"]
    out = [m.group(2).strip() for m in _FENCE_RE.finditer(text or "")]
    return [c for c in out if c][:limit]


def clip(s: str, n: int = TOOL_OUTPUT_CLIP) -> str:
    """回給模型的截斷。**落盤的是全文**（`calls.jsonl`）。

    形狀沿用 `harness_arms.truncate_message` 的「頭尾都留」而不是純 tail：
    指令輸出的資訊常常在開頭（錯誤訊息）也在結尾（traceback 最後一行）。
    """
    s = s or ""
    if len(s) <= n:
        return s
    head = n // 2
    tail = n - head
    return (s[:head] + f"\n…[{len(s) - n} characters omitted]…\n" + s[-tail:])


# ══ 工作區生命週期 ═══════════════════════════════════════════════════════
GIT_IDENTITY = ("-c", "user.name=r530", "-c", "user.email=r530@vacant.local")


def prepare_workspace(template_dir: str | pathlib.Path,
                      cell_dir: str | pathlib.Path, *,
                      git_init: bool = True,
                      world_writable: bool = False) -> dict:
    """`cp -a <template>/. <cell>/` ＋ 空 git 起點，回起始樹 manifest。

    ⚠ 已存在的 `cell_dir` 會被**整個刪掉重建**。`A-CONF` 的「重置回樣板」
      走的就是這一條，所以它必須是冪等的：重置之後的樹雜湊必須等於樣板的
      樹雜湊（`tests/test_r530_workspace.py` 有對這一條）。
    ⚠ `.git/` 不進樹雜湊（`wshash.EXCLUDED_DIRS`）——commit 帶時間戳，
      算進去會讓 108 格得到 108 個不同的起始雜湊。
    """
    tpl = pathlib.Path(template_dir)
    cell = pathlib.Path(cell_dir)
    if not tpl.is_dir():
        raise FileNotFoundError(f"樣板不存在：{tpl}")
    if cell.exists():
        shutil.rmtree(cell)
    cell.parent.mkdir(parents=True, exist_ok=True)
    # `cp -a` 而不是 `shutil.copytree`：保留 mode／mtime／符號連結，
    # 與預註冊 §三-1 寫的那一行逐字相同（樹雜湊不取 mtime，見 wshash）。
    subprocess.run(["cp", "-a", f"{tpl}/.", str(cell)], check=True)
    if git_init:
        subprocess.run(["git", "init", "-q", str(cell)], check=True)
        subprocess.run(["git", "-C", str(cell), *GIT_IDENTITY, "add", "-A"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(cell), *GIT_IDENTITY,
                        "commit", "-q", "-m", "template"],
                       check=True, capture_output=True)
    if world_writable:
        # 沙箱降權到別的 uid（`--sandbox-uid`，例如 `nobody`）時，
        # 那個 uid 必須寫得進這一格的工作區。**只有這一格**：工作區根
        # 本身留 0755／擁有者是我們，所以「寫出界」在 unix 權限上就是擋的
        # （`sandbox.probe` 的 `write_confined` 量的正是這一條）。
        subprocess.run(["chmod", "-R", "a+rwX", str(cell)], check=True)
    return wshash.tree_manifest(cell)


def archive_workspace(cell_dir: str | pathlib.Path,
                      out_path: str | pathlib.Path) -> str:
    """把一個工作區打包成 tar.gz，回檔案的 sha256。

    `.git/` **打進去**（與樹雜湊相反）：樹雜湊要跨格相同所以排除它，
    而封存要留住「worker 到底動了什麼」的 `git diff` 證據所以留著它。
    兩個用途不同，不是矛盾——這一句寫在這裡免得以後有人「統一」掉。
    """
    cell = pathlib.Path(cell_dir)
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz") as tf:
        tf.add(cell, arcname=cell.name)
    return hashlib.sha256(out.read_bytes()).hexdigest()


# ══ 一格的執行 ═══════════════════════════════════════════════════════════
@dataclasses.dataclass
class CellPaths:
    """一格要用到的路徑，一次算好，免得散落在函式裡各算一份。"""

    template_dir: pathlib.Path
    visible_dir: pathlib.Path
    hidden_dir: pathlib.Path
    cell_dir: pathlib.Path
    verify_root: pathlib.Path
    ws_archive_dir: pathlib.Path
    #: 沙箱降權到別的 uid 時要把工作區開成 a+rwX（見 `prepare_workspace`）。
    world_writable: bool = False


def _budget_stop(calls_used: int, completion_tokens: int, tool_calls: int,
                 t0: float, last_prompt_tokens: int = 0) -> str | None:
    """呼叫數／completion tokens／工具次數／牆鐘／脈絡任一超過就停。

    撞線是一個**獨立的 outcome**，不可以混進失敗率——五個 stop_reason 分開記
    （`harness_arms._budget_stop` 的同一條）。

    ⚠ 第二個參數是 **completion tokens**，不是 `total_tokens` 的和
      （Fable 2026-09-14）。理由見 `OPENWORK_BUDGET` 的註解。
    """
    b = OPENWORK_BUDGET
    if calls_used >= int(b["max_model_calls"]):
        return "budget_calls"
    if completion_tokens >= int(b["max_completion_tokens"]):
        return "budget_tokens"
    if last_prompt_tokens >= int(b["max_context_tokens"]):
        return "budget_context"
    if tool_calls >= int(b["max_tool_calls"]):
        return "budget_tool_calls"
    if (time.time() - t0) >= float(b["max_wall_s"]):
        return "budget_wall"
    return None


def _log(calls_path: pathlib.Path, rec: dict) -> None:
    calls_path.parent.mkdir(parents=True, exist_ok=True)
    rec.setdefault("ts_ms", int(time.time() * 1000))
    with calls_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())        # 中途被砍也要留得住（鐵律 3）


#: 「worker 自己跑過可見驗收沒有」——**P-W7 的仲裁量原料**（§四-1）。
#: 操作型定義逐字沿用預註冊 §四-1 P-W7：「該格的工具呼叫紀錄裡出現**至少
#: 一次成功執行**可見驗收的指令（`blocked: true` 的不算）」。四個凍結字串
#: 同時涵蓋本 repo 的 `tests_visible/`／`run_tests.sh` 與預註冊行文裡的
#: `examples/`／`run_examples.sh` 兩套命名——**兩套都認**，免得命名差異
#: 被讀成「它沒跑過」。
#: 這一格若高而 `A-SOLO` 仍然輸 ⇒ 增益來自迴圈；若低 ⇒ 增益主要來自
#: 「被強迫看一眼」。**兩種結論都成立，事前不挑。**
SELF_RAN_MARKERS = ("tests_visible", "run_tests.sh", "examples/",
                    "run_examples.sh")


def _looks_like_self_ran_visible(command: str) -> bool:
    shell = strip_heredoc_bodies(command)
    return any(m in shell for m in SELF_RAN_MARKERS)


def run_cell(task: dict, brain, *, arm: str, seed: str, paths: CellPaths,
             sandbox: Sandbox, calls_path: pathlib.Path,
             book=None, ident=None) -> dict:
    """跑一格（一題一臂），回一列 `rows.jsonl`。

    `InfraVoid` **不接**：由 `brain.chat` 往上拋，呼叫端（`run_r530.py`）
    照 `gain_run` 的同一條規則記成 `infra_void` 並 `continue`——
    **作廢的格子不寫 row**（`gain_run.py:1922-1932` 的同一條，
    所以 `len(rows) == processed − infra_void`）。
    """
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    b = OPENWORK_BUDGET
    task_id = task["task_id"]
    t0 = time.time()
    calls_used = tokens_total = tool_calls = blocked_n = 0
    deny_tags: dict[str, int] = {}
    attempts: list[dict] = []
    receipt_hashes: list[str] = []
    ws_start_sha: str | None = None
    stop_reason: str | None = None
    accepted = False
    final_visible: dict | None = None
    ws_archives: list[dict] = []
    self_ran_visible = False
    prompt_tokens_total = completion_tokens_total = 0
    last_prompt_tokens = 0
    messages: list[dict] = []

    max_attempts = b["max_gate_rounds"] if arm == "A-CONF" else 1
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        persona_id, persona_text = persona_for(seed, task_id, attempt)
        start_manifest = prepare_workspace(
            paths.template_dir, paths.cell_dir,
            world_writable=paths.world_writable)
        if ws_start_sha is None:
            ws_start_sha = start_manifest["ws_sha256"]
        elif start_manifest["ws_sha256"] != ws_start_sha:
            # 重置回樣板必須回到**同一個**起點，否則 `A-CONF` 的第 k 份與
            # 第 1 份不是同一個實驗。這裡是 fail-fast，不是警告。
            raise RuntimeError(
                f"工作區重置後的樹雜湊變了：{start_manifest['ws_sha256']} "
                f"≠ {ws_start_sha}（task={task_id} arm={arm} attempt={attempt}）")
        system, messages = initial_messages(
            task, paths.cell_dir, arm=arm, persona_text=persona_text)
        nudges_left = b["nudge_budget"]
        gate_round = 0
        att_rec = {"attempt": attempt, "persona": persona_id,
                   "gate_rounds": [], "declared_done_turn": None,
                   "stop_reason": None}

        while True:
            stop_reason = _budget_stop(calls_used, completion_tokens_total,
                                       tool_calls, t0, last_prompt_tokens)
            if stop_reason:
                break
            proto = getattr(brain, "tool_protocol", "text")
            out = brain.propose(
                messages, system=system, role="r530",
                meta={"run_arm": arm, "arm": arm, "task_id": task_id,
                      "attempt": attempt, "gate_round": gate_round,
                      "seed": seed, "persona": persona_id,
                      "tool_protocol": proto})
            calls_used += 1
            usage = out.get("usage") or {}
            tokens_total += _usage_tokens(usage)
            prompt_tokens_total += int(usage.get("prompt_tokens") or 0)
            completion_tokens_total += int(usage.get("completion_tokens") or 0)
            last_prompt_tokens = int(usage.get("prompt_tokens") or 0)
            text = out.get("text") or ""
            # 每輪指令數上限**兩種協定都套**（文字協定在 `parse_commands`
            # 裡夾，原生協定在這裡夾）。不對稱的話，換協定就等於換預算。
            calls_out = (out.get("tool_calls")
                         or [])[:b["max_commands_per_turn"]]
            raw_calls = (out.get("raw") or {}).get("tool_calls")
            assistant_msg = {"role": "assistant", "content": text}
            if proto == "native" and raw_calls:
                assistant_msg["tool_calls"] = raw_calls
            messages.append(assistant_msg)

            if calls_out:
                for call in calls_out:
                    if call.get("error"):
                        # 叫了不存在的工具／參數壞掉：回一則錯誤訊息，
                        # **照樣落盤**（模型試圖做什麼比做成了什麼更值得看）。
                        _log(calls_path, {"kind": "tool", "blocked": False,
                                          "deny_tag": None, "command": None,
                                          "tool_error": call["error"],
                                          "task_id": task_id, "arm": arm,
                                          "attempt": attempt,
                                          "gate_round": gate_round})
                        messages.append(_tool_reply(
                            proto, call, f"ERROR: {call['error']}. "
                            f"The only tool is run_bash(command)."))
                        continue
                    cmd = call["command"]
                    result_msg, rec = _run_one_command(
                        cmd, sandbox, paths.cell_dir, calls_path,
                        timeout_s=call.get("timeout_s"),
                        task_id=task_id, arm=arm, attempt=attempt,
                        gate_round=gate_round)
                    if rec["blocked"]:
                        blocked_n += 1
                        deny_tags[rec["deny_tag"]] = (
                            deny_tags.get(rec["deny_tag"], 0) + 1)
                    else:
                        tool_calls += 1
                        if _looks_like_self_ran_visible(cmd):
                            self_ran_visible = True
                    messages.append(_tool_reply(proto, call, result_msg))
                continue

            # ── 宣告完成 ────────────────────────────────────────────────
            now = wshash.tree_manifest(paths.cell_dir)
            if now["ws_sha256"] == start_manifest["ws_sha256"] and nudges_left > 0:
                nudges_left -= 1
                messages.append({"role": "user", "content": NUDGE_NO_WORK})
                continue
            if now["ws_sha256"] == start_manifest["ws_sha256"]:
                att_rec["declared_done_turn"] = calls_used
                stop_reason = "nudge_exhausted"
                break
            att_rec["declared_done_turn"] = calls_used

            if arm == "A-SOLO":
                # **收。** 沒有閘門、沒有回饋、不存在拒交。
                #
                # ⚠ 但**可見驗收照樣跑一次**（預註冊 §三-6 C3 逐字：
                #   「`A-SOLO` 那格也要跑（只記分、不當閘門、不回饋）」）。
                #   沒有它，P-W7／W7a／W7b 的歸因量就少掉對照的那一半。
                #   跑的結果**不進 messages、不改 accepted、不改 stop_reason**
                #   ——它只落盤。三條臂的 prompt 逐字相同這件事因此不受影響。
                final_visible = acceptance.run_suite(
                    sandbox, paths.cell_dir, paths.visible_dir, suite="visible",
                    task_id=task_id, verify_root=paths.verify_root,
                    timeout_s=b["gate_test_timeout_s"])
                att_rec["gate_rounds"].append({
                    "gate_round": 0, "scoring_only": True,
                    "passed": final_visible["passed"],
                    "total": final_visible["total"],
                    "all_pass": final_visible["all_pass"],
                    "result_sha256": final_visible["result_sha256"]})
                _log(calls_path, {"kind": "gate", "arm": arm,
                                  "task_id": task_id, "attempt": attempt,
                                  "gate_round": 0, "scoring_only": True,
                                  "visible": final_visible})
                # ⚠ 照樣簽一筆 `ws_attempt`（`verdict_sha256=None` ＝
                #   **這一輪沒有跑驗收**）。不簽的話 `A-SOLO` 的鏈上只有
                #   verdict 沒有 attempt，而 `verify_run_receipts` 的對帳
                #   （attempt 數 ≥ verdict 數）會把「這條臂本來就沒有閘門」
                #   讀成「漏寫」。收據要能表達「沒有跑」，不是省略它。
                if book is not None:
                    entry = receipts.append_attempt(
                        book, ident, task_id=task_id, arm=arm, attempt=attempt,
                        gate_round=0, ws_sha256=now["ws_sha256"],
                        # `A-SOLO` 的可見驗收是**只記分**的：雜湊照樣簽進鏈
                        # （它是一份真的量測），但它沒有當過閘門。
                        verdict_sha256=final_visible["result_sha256"],
                        conversation_sha256=receipts.conversation_digest(messages),
                        visible_passed=final_visible["passed"],
                        visible_total=final_visible["total"],
                        scoring_only=True)
                    receipt_hashes.append(entry.hash())
                stop_reason = "declared_done"
                accepted = True
                break

            visible = acceptance.run_suite(
                sandbox, paths.cell_dir, paths.visible_dir, suite="visible",
                task_id=task_id, verify_root=paths.verify_root,
                timeout_s=b["gate_test_timeout_s"])
            final_visible = visible
            gate_round += 1
            att_rec["gate_rounds"].append({
                "gate_round": gate_round,
                "passed": visible["passed"], "total": visible["total"],
                "all_pass": visible["all_pass"],
                "result_sha256": visible["result_sha256"]})
            _log(calls_path, {"kind": "gate", "arm": arm, "task_id": task_id,
                              "attempt": attempt, "gate_round": gate_round,
                              "visible": visible})
            if book is not None:
                entry = receipts.append_attempt(
                    book, ident, task_id=task_id, arm=arm, attempt=attempt,
                    gate_round=gate_round, ws_sha256=now["ws_sha256"],
                    verdict_sha256=visible["result_sha256"],
                    conversation_sha256=receipts.conversation_digest(messages),
                    visible_passed=visible["passed"],
                    visible_total=visible["total"])
                receipt_hashes.append(entry.hash())

            if visible["all_pass"]:
                stop_reason = "visible_pass"
                accepted = True
                break
            if arm == "A-GATE":
                if gate_round >= b["max_gate_rounds"]:
                    stop_reason = "gate_exhausted"
                    accepted = False
                    break
                messages.append({
                    "role": "user",
                    "content": FEEDBACK_TEMPLATE.format(
                        block=acceptance.render_failures(visible))})
                continue
            # A-CONF：這一份不過 ⇒ 跳出內圈，外圈重置工作區＋換 persona＋重開對話
            break

        att_rec["stop_reason"] = stop_reason
        arc = paths.ws_archive_dir / f"{task_id}__{arm}__a{attempt}.tar.gz"
        att_rec["ws_archive"] = str(arc.name)
        att_rec["ws_archive_sha256"] = archive_workspace(paths.cell_dir, arc)
        att_rec["ws_end_sha256"] = wshash.tree_hash(paths.cell_dir)
        attempts.append(att_rec)
        ws_archives.append({"attempt": attempt, "file": arc.name,
                            "sha256": att_rec["ws_archive_sha256"]})
        if accepted or (stop_reason or "").startswith("budget") \
                or stop_reason in ("gate_exhausted", "nudge_exhausted"):
            break
    else:
        # while-else：`A-CONF` 把 5 份都跑完而沒有 break ⇒ 全不過 ⇒ 拒交
        stop_reason = "attempts_exhausted"
        accepted = False

    if arm == "A-CONF" and not accepted and stop_reason not in (
            "budget_calls", "budget_tokens", "budget_wall",
            "budget_tool_calls", "nudge_exhausted"):
        stop_reason = "attempts_exhausted"

    # ⚠ **`A-SOLO` 的 `accepted` 恆為 True。這是定義不是發現**
    #   （§六-0、§八-4；P-W3 逐字：「`A-SOLO` 的拒交件數 ＝ 0」是結構上必然）。
    #   它沒有拒交語意 ⇒ 宣告完成就是交付，連「宣告完成但什麼都沒寫」
    #   （`nudge_exhausted`）都是一份交付——一份空的。把那一格記成
    #   `accepted=False` 會讓 `A-SOLO` 憑空長出拒交語意，而那正是
    #   §八-4 要求「每次引用 deliv 都要跟著講」的那條結構差。
    #   撞預算的格子也一樣：`stop_reason` 分開記，`accepted` 不動。
    if arm == "A-SOLO":
        accepted = True

    ws_end = wshash.tree_manifest(paths.cell_dir)
    hidden = acceptance.run_suite(
        sandbox, paths.cell_dir, paths.hidden_dir, suite="hidden",
        task_id=task_id, verify_root=paths.verify_root,
        timeout_s=b["gate_test_timeout_s"])
    # 驗收跑完工作區必須逐位元沒動——隱藏驗收永遠不進工作區（§五-3 第 1 條）。
    ws_after_hidden = wshash.tree_hash(paths.cell_dir)
    if ws_after_hidden != ws_end["ws_sha256"]:
        raise RuntimeError(
            f"跑隱藏驗收改動了工作區（{ws_end['ws_sha256']} → {ws_after_hidden}）"
            f"——V/GT 紅線，task={task_id} arm={arm}。停。")

    row = {
        "task_id": task_id, "arm": arm, "seed": seed,
        "accepted": bool(accepted),
        "stop_reason": stop_reason,
        "attempts_n": len(attempts),
        "attempts": attempts,
        # §三-6 C2：宣告完成的輪次（第一次宣告的那一通）。
        "declared_done_turn": next(
            (a["declared_done_turn"] for a in attempts
             if a.get("declared_done_turn")), None),
        # §四-1 P-W3：拒交件數的原料（`A-SOLO` 恆為 0，那是定義不是發現）。
        # 拒交**只有兩種**：閘門輪用完（GATE）與五份都不過（CONF）。
        # `nudge_exhausted`／`budget_*` 不是拒交，它們是「沒跑完」——
        # 把它們算成拒交會讓 P-W3 的結構性 0 變成一個會跳動的數字。
        # ⚠ `A-SOLO` 一格都拿不到（它沒有拒交語意）——這是定義不是量測。
        "refusal": (arm != "A-SOLO" and stop_reason in REFUSAL_REASONS),
        # E-10（Fable 2026-09-14）：工作區逐位元沒動**而且**零工具呼叫
        # ⇒ 這一格什麼都沒發生。它在資料上長得跟「模型很笨」一模一樣，
        # 分得出來只因為樹雜湊是一個**獨立於模型輸出**的訊號。
        # 同一臂 noop 比例 > 20% ⇒ 量具故障不是結果（`gates.e10_noop_gate`）。
        "noop_cell": bool(ws_start_sha == ws_end["ws_sha256"]
                          and tool_calls == 0),
        "calls": calls_used, "tokens": tokens_total,
        # ⚠ `tokens` ＝ 逐通 `total_tokens` 的和，而多輪迴圈每一通都會把
        #   整段對話當 prompt 重送 ⇒ 它**隨輪數呈二次成長**。冒煙實測
        #   5–8 通就撞滿 120k（`runs/_smoke/g_r530_real_1`）。兩個分量
        #   分開落盤，好讓 analyzer 看得出「是生成太多還是脈絡太長」。
        "prompt_tokens": prompt_tokens_total,
        "completion_tokens": completion_tokens_total,
        "tool_protocol": getattr(brain, "tool_protocol", "text"),
        "tool_calls": tool_calls, "blocked": blocked_n,
        "deny_tags": deny_tags,
        "wall_s": round(time.time() - t0, 3),
        "persona_first": persona_for(seed, task_id, 1)[0],
        "ws_start_sha256": ws_start_sha,
        "ws_end_sha256": ws_end["ws_sha256"],
        # 預註冊 §三-1／§三-6 C5 用的是 `workspace_*` 這組名字。
        # **兩個名字都落盤**：欄位名對不上會讓檢核表判「量不到」，
        # 而那與「量到了但不合格」是兩件事。
        "workspace_start_sha256": ws_start_sha,
        "workspace_end_sha256": ws_end["ws_sha256"],
        "ws_files_n": ws_end["files_n"],
        "ws_archives": ws_archives,
        "visible_passed": (final_visible or {}).get("passed"),
        "visible_total": (final_visible or {}).get("total"),
        "visible_all_pass": (final_visible or {}).get("all_pass"),
        "self_ran_visible": self_ran_visible,
        # 預註冊 §四-1 P-W7 指名的欄位名。
        "solo_self_ran_visible": self_ran_visible,
        "hidden_passed": hidden["passed"],
        "hidden_total": hidden["total"],
        # `frac` ＝ 隱藏驗收通過條數 ÷ 總條數（§六-0 的主指標原料）。
        # **量的是最終工作區**，不管有沒有出貨。
        "hidden_frac": (hidden["passed"] / hidden["total"]
                        if hidden["total"] else None),
        # ⚠ **拒交的格子「交出去的東西」是零**，而上面那一格量的是「最後那份
        #   工作區有多好」。兩者在 `A-GATE`／`A-CONF` 上不同，在 `A-SOLO` 上
        #   恆等（它沒有拒交語意）。**主指標 M1 該讀哪一個，本檔不挑**——
        #   兩個都落盤，由 analyzer 在看到資料之前的那份預註冊指名一個。
        #   （這是 §九 該問 Fable 的第一件事，見 `TASK_FORMAT.md` 末節。）
        "hidden_frac_delivered": ((hidden["passed"] / hidden["total"])
                                  if (accepted and hidden["total"]) else 0.0),
        # `deliv` ＝ accepted ∧ 全過（R667 凍結口徑的 R530 版）。
        # ⚠ `A-SOLO` 的 accepted 恆為 True——這是定義不是發現（§八-4）。
        "deliv": bool(accepted and hidden["total"] and
                      hidden["passed"] == hidden["total"]),
        "hidden_result_sha256": hidden["result_sha256"],
        "visible_result_sha256": (final_visible or {}).get("result_sha256"),
        "receipt_attempt_hashes": receipt_hashes,
    }
    _log(calls_path, {"kind": "hidden", "arm": arm, "task_id": task_id,
                      "hidden": hidden})
    if book is not None:
        entry = receipts.append_verdict(
            book, ident, task_id=task_id, arm=arm, accepted=accepted,
            ws_start_sha256=ws_start_sha or "", ws_end_sha256=ws_end["ws_sha256"],
            verdict_sha256=(final_visible or {}).get("result_sha256"),
            conversation_sha256=receipts.conversation_digest(messages),
            stop_reason=stop_reason,
            attempts_n=len(attempts), calls=calls_used)
        row["receipt_verdict_hash"] = entry.hash()
    return row


def _tool_reply(proto: str, call: dict, body: str) -> dict:
    """工具結果貼回去的那一則訊息。**兩種協定的角色不同**。

    · `native`：`{"role": "tool", "tool_call_id": …}`——端點要求的形狀。
    · `text` ：`{"role": "user", …}`——`ClineBrain.chat` 只收 user／assistant，
      所以工具結果只能以 user 訊息回灌，靠凍結的 `TOOL_RESULT_HEADER`
      讓 V/GT 稽核把它認回 `tool`（見 `harness_vgt_audit.R530_TOOL_HEADER`）。
    """
    if proto == "native":
        return {"role": "tool", "tool_call_id": call.get("id") or "",
                "content": body}
    return {"role": "user", "content": body}


def _run_one_command(command: str, sandbox: Sandbox, cell_dir: pathlib.Path,
                     calls_path: pathlib.Path, *, timeout_s: int | None = None,
                     **meta) -> tuple[str, dict]:
    """跑一條指令（或擋下來），回 `(貼回模型的訊息, 落盤紀錄)`。"""
    hit = deny_reason(command)
    if hit:
        why, tag = hit
        rec = {"kind": "tool", "blocked": True, "deny_tag": tag,
               "command": command, "reason": why, **meta}
        _log(calls_path, rec)
        return BLOCKED_TEMPLATE.format(header=TOOL_RESULT_HEADER,
                                       command=command, why=why), rec
    timeout = OPENWORK_BUDGET["tool_timeout_s"]
    if timeout_s:
        timeout = max(1, min(int(timeout_s),
                             OPENWORK_BUDGET["tool_timeout_max_s"]))
    try:
        res = sandbox.run(command, workspace=cell_dir, timeout_s=timeout)
    except SandboxInfraError as e:
        # 沙箱起不來＝基建故障，翻成 InfraVoid 讓呼叫端走 `infra_void` 規則
        # （鐵律 3；`checks.CheckInfraError` 的同一條紀律）。
        raise InfraVoid(f"沙箱起不來：{e}") from e
    rec = {"kind": "tool", "blocked": False, "deny_tag": None,
           "command": command, "timeout_s": timeout,
           "rc": res.rc, "timed_out": res.timed_out, "wall_ms": res.wall_ms,
           "stdout": res.stdout, "stderr": res.stderr, **meta}
    _log(calls_path, rec)
    rc_text = "timeout" if res.timed_out else str(res.rc)
    msg = TOOL_RESULT_TEMPLATE.format(
        header=TOOL_RESULT_HEADER, command=command, rc=rc_text,
        stdout=clip(res.stdout), stderr=clip(res.stderr))
    return msg, rec


def _usage_tokens(usage: dict) -> int:
    try:
        return int(usage.get("total_tokens")
                   or (int(usage.get("prompt_tokens") or 0)
                       + int(usage.get("completion_tokens") or 0)))
    except Exception:                                        # noqa: BLE001
        return 0


# ══ import 時的兩道防呆（繞不過去）════════════════════════════════════════
_FROZEN_TEXTS = (
    RULES, rules_text(), TASK_MESSAGE, NUDGE_NO_WORK, FEEDBACK_TEMPLATE,
    TOOL_RESULT_HEADER, TOOL_RESULT_TEMPLATE, BLOCKED_TEMPLATE,
    acceptance.CASE_LINE, acceptance.CASE_OUTPUT_LINE, acceptance.NO_FAILURE_LINE,
    *[t for _i, t in PERSONAS],
)
for _txt in _FROZEN_TEXTS:
    assert_ks1_clean(_txt)
del _txt

#: `assert_arm_prompts_identical` 用的 fixture。刻意**不讀磁碟**：
#: 這條斷言要在 import 時就跑完，不能依賴任何題庫檔存在。
_FIXTURE_TASK = {
    "task_id": "_fixture",
    "goal": "Goal. A client wants a thing that does something useful.",
    "contract": "Contract\n- solution.f(x: int) -> int",
}


def assert_arm_prompts_identical() -> None:
    """三條臂的 system ＋ 第一則 user 訊息**逐位元相同**。

    這不是一個「應該相同」的註解，是一個 import 時就會炸的斷言：
    有人哪天在 `initial_messages` 裡加 `if arm == …`，這支就 import 不進來、
    run 起不來（`vacant.memory.assert_ks1_clean` 的同一個性質）。
    """
    import tempfile

    with tempfile.TemporaryDirectory(prefix="r530fixture.") as td:
        ws = pathlib.Path(td)
        (ws / "goal.md").write_text("x", encoding="utf-8")
        rendered = []
        for arm in ARMS:
            persona_id, persona_text = persona_for("s", _FIXTURE_TASK["task_id"], 1)
            del persona_id
            system, msgs = initial_messages(
                _FIXTURE_TASK, ws, arm=arm, persona_text=persona_text)
            rendered.append(json.dumps([system, msgs], ensure_ascii=False,
                                       sort_keys=True))
    if len(set(rendered)) != 1:
        raise AssertionError(
            "三條臂的第一則訊息不逐字相同——Fable 2026-09-13 裁決的唯一差別是"
            "「宣告完成之後發生什麼」，prompt 有分支就不是那個實驗了。")


assert_arm_prompts_identical()
