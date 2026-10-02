"""twin/twinagent — 數位分身**真跑**：分身自己決定任務，在 `vacant run` 底下用 pi 做完。

## 這支在架構裡承重什麼

裁決：`decisions/DECISION_20260924_TWIN_AGENT_RUN.md`（流程、事件、權限、退化、撤回）。

在這之前 `twinlink.generate()` 是**直接打 1003 LM Studio 要三句台詞**：沒有 agent、
沒有 `vacant run`、沒有收據。分身「做了什麼」只是一句模型寫的台詞。這一支把它換成：

```
特質（檔案庫開封，主執行緒）
  → 拋棄式工作區 ws/<slug>/TRAITS.md          run-dir runs/<slug>/（工作區外）
  → launcher.run(twin_agent.sh …, vacant_on=True, allow_no_suite=True,
                 events_path=<展場 live 檔>, events_caller={cell_id,resident,prompt})
  → pi 自己決定 → PLAN.md ＋ 成品（工作區裡的檔案）
  → 行程結束 ⇒ 凍結 ⇒ ws_attempt ＋ ws_verdict（accepted_is_null）簽進收據
  → 主執行緒讀凍結快照 → twinvault（鏈外）＋ twinstore（commitment ＋ run_id ＋ verdict_hash）
```

**這一支不碰 sqlite**：`TwinStore` 的連線不跨執行緒。worker 只跑 launcher 與讀檔；
封印與寫鏈由 `twinlink` 在主執行緒做。

## 「做對」這件事（人類 2026-09-24；2026-10-01 改版）

「**這個問題是 vacant 問題，不是數位分身的問題**」⇒ 這一支**不發明評分**、不找模型當裁判。

* 2026-09-24～10-01：`allow_no_suite=True`，`stop_reason="ungated"`、`accepted=None`＝沒有客觀標準、不判。
  結果整條路上沒有任何會退回、會重來的邏輯。
* **2026-10-01 起（預設）**：交件前過「**有沒有根據**」的閘門（`grounding_gate.py`，裁決
  `decisions/DECISION_20261001_TWIN_GROUNDING_GATE.md`）——所有分身同一套、確定性、只查根據的有無
  （讀過了嗎／找得到出處嗎／兩個出處對得上嗎／收據是閘門給的嗎），不查好不好。用的是 `vacant run`
  本來就有的 `suite_dir`＋`retry_arm="revise"`＋`feedback_into="both"`，最多 3 次；最後還沒過：
  **照常交件、拍立得照發、收據照簽（`accepted=False` 是真的）**。`AgentConfig.gate=False` 回舊行為。

## 誠實邊界（改碼時保留）

1. **`accepted=None` 不准被壓成 `False`，也不准畫成「通過」。**（閘門開著時 `accepted` 是 `True`／`False`，
   說的只是「有沒有根據」；`gate=False` 的舊路徑仍恆為 `None`。）
2. **收住的是「模型叫得到的工具」，不是 pi 這個行程**（裁決 §三）——**除非**
   `enclose` 開著而且這台起得來圍牆（VM，`twinenclose.py`）：那時整跑（launcher＋pi）
   在 bwrap 的 netns＋mount ns 裡，收據簽的是量出來的 `enclosure.applied`，天花板 B。
   圍牆起不來時 `enclose=auto` 會退回不圍、`enclose=on` 則不起 pi（誠實邊界 5）。
3. **`twin_id` 是雜湊別名，不是匿名化**：拿得到 `sub_id` 的人算得出它。它擋的是反方向——
   從公開的事件流／收據推回撤回用的那把鑰匙（`sub_id` 是能力憑證）。
4. **事件流與收據都不帶觀眾原文**：`caller.prompt` 是固定字串、`task_id` 是別名。
   事件流是 append-only 的檔，撤回刪不到裡面的行——所以從一開始就不寫進去。
5. **退化要看得出來**（twinlink 誠實邊界 2）：`requests_seen == 0`、沒有 `PLAN.md`、
   `infra_void` 都**不准**標成 `vacant_run:*`。
6. **撤回刪 run 產物，但收據留著**：`receipts_*.ndjson`／`.pub.json` 只有雜湊與計數，
   是「這一跑發生過」的可驗證據。其餘（wire log 含特質原文、凍結快照、stdout／stderr、
   摘要）全刪。`erase_run_artifacts()` 回報刪了什麼、留了什麼、哪裡出錯。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shutil
import sys
import threading
import time
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

HERE = pathlib.Path(__file__).resolve()
TWIN = HERE.parent
REPO = TWIN.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ops.exhibit.twin import fortune as fortunelib  # noqa: E402
from ops.exhibit.twin import grounding_gate as gatelib  # noqa: E402
from ops.exhibit.twin import polaroid as polaroidlib  # noqa: E402
from ops.exhibit.twin import roster as rosterlib  # noqa: E402
from ops.exhibit.twin import sidecar as sidecarlib  # noqa: E402
from ops.exhibit.twin import twinground  # noqa: E402
from vacant_network.memory import assert_ks1_clean  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402
from vacant_network.vrun import retry as retrypolicy  # noqa: E402
# ⚠ `launcher` 在 `run_one` 裡才 import：它拉進 wireproxy／attest／sandbox，
#   而 twinlink（展場 loop）一 import 這一支就會拉它——這台跑不起 pi 時
#   （例如 1003 Windows 本機）不該因為一個用不到的模組而連 loop 都起不來。

#: 分身那一跑的 agent 命令（pi，工具收窄；W3b 起一跑兩個回合：寫信、進世界）。
WRAPPER = TWIN / "twin_agent.sh"

#: 畫面上 `engine` 的前綴。`vacant_run:pi:<model>` ＝ 真的在 `vacant run` 底下跑過、
#: 真的打到模型、真的寫了 PLAN.md。三個條件缺一就不是這個 engine（誠實邊界 5）。
ENGINE_PREFIX = "vacant_run:pi"

#: 1003 吞吐 4 串封頂，而同一張卡上還有別的線在跑 ⇒ 預設 2。
DEFAULT_PARALLEL = 2

#: 單跑牆鐘上限（launcher 的 `timeout_s`）。真模型一跑實測約 1–2 分鐘。
DEFAULT_AGENT_TIMEOUT = 300.0

#: 根據閘門（`grounding_gate.py`）的嘗試上限：第 1 次＋重改 2 次（對齊零設定「一個要求最多 2 回合」）。
GATE_MAX_ATTEMPTS = 3
#: 整跑時間預算（秒）：每次嘗試的時限＝min(單次上限, 剩下的預算)；重改時剩不到 `MIN_ATTEMPT_S` 就不再開 pi，
#: 照 `attempts_exhausted` 收尾（P7 真跑最慢 495 秒＝3×300 的上限；展場等不起）。
RUN_BUDGET_S = 420.0
MIN_ATTEMPT_S = 60.0

#: 讀回的成品上限（每位分身）。
MAX_ARTIFACTS = 4
MAX_ARTIFACT_CHARS = 4000
MAX_PLAN_CHARS = 2000

#: 磁碟水位（MB）。低於它就**停收新分身**（不起新的 run），畫面與 log 都講。
#: 估算與理由：`ops/exhibit/twin/START.md`「VM 磁碟」一節。環境變數是單一真相來源：
#: loop（決定要不要起新的 run）與 serve／export（畫面上的 `intake`）讀同一個值。
ENV_MIN_FREE_MB = "VACANT_TWIN_MIN_FREE_MB"
DEFAULT_MIN_FREE_MB = 2048

#: 收據級別的高低（`require_tier` 用）。A > B > B' > C。
TIER_RANK = {"A": 3, "B": 2, "B'": 1, "C": 0}

#: 工作區裡**不是**成品的檔。
NOT_ARTIFACTS = frozenset({"TRAITS.md", "WORLD.md", "PLAN.md", "VACANT_FEEDBACK.md", "信.md", "命盤卡.md"})

#: 地上/ 是世界的實物（唯讀），不是分身的成品。
GROUND_PREFIX = "地上/"

#: 撤回時 run-dir 裡**留下**的檔：只有雜湊與計數（誠實邊界 6）。
#: `rows.jsonl` 也要留：既有的驗章器（`verify_receipts.verify_run`）拿它對帳
#: 「每題一筆 verdict」，少了它收據就驗不過——留收據卻驗不了等於沒留。
#: 它的欄位是別名、雜湊、計數與固定枚舉（`launcher._persist` 的 `row`）。
KEEP_ON_ERASE = ("receipts_RUN-ON.ndjson", "receipts_RUN-ON.pub.json", "rows.jsonl")

#: 分身工作區三個工具被呼叫的原始紀錄檔（run-dir 裡，工作區外；契約
#: `plans/CONTRACT_PROCESS_20260928.md` §A）。**這個字面值與 `twin_agent.sh`
#: 匯出的 `VACANT_TWIN_STEP_LOG` 同步**——那一支自己從 `$RUN_DIR` 算出同一個
#: 路徑，兩邊改一個要改另一個。它**不在** `KEEP_ON_ERASE`：撤回時跟 run-dir
#: 其餘檔案一起刪（含檔名，屬於誠實邊界 6 要清掉的那一半）。
STEP_LOG_NAME = "twin_steps.ndjson"

#: 三個工具的必填參數 `thought` 的紀錄檔（`pi_ext/twin_ws_tools.ts` 寫、`twin_agent.sh` 匯出路徑；
#: 同樣在 run-dir、撤回時整個刪）。`SayForwarder` 讀它、過防呆後轉成 `twin_say`。
THOUGHT_LOG_NAME = "twin_thoughts.ndjson"

# ---------------------------------------------------------------------------
# 固定文字（全場逐字相同；argv 裡沒有觀眾原文）
# ---------------------------------------------------------------------------

#: ⚠ 2026-09-26 人類：「那個字是不是應該要讓他是 AI agent 生成的，不要隨便刻板」。
#:   舊版第 1 步寫著「例如一封信、一份計畫、一張清單」——那一串例子會把每個分身都帶去
#:   寫信／列清單（拍立得上那一句就變成人寫的罐頭）。**這裡不准再放例子**，只留約束：
#:   一件寫進自己房間的一個檔案就能完成的事、不寫程式、PLAN.md 第一行是決定。
#:   `tests/test_twin_agent_run.py::test_system_prompt_gives_no_examples` 守這一條。
#: 段 1：寫信（W3b）。分身讀 TRAITS.md，把這個人的性情寫成投遞口收到的那封信。
#: ⚠ 不准舉例、不准給方向；「現實具體事物」只用條件描述（職業、學校、家人、寵物、作品、
#:   地名、品牌、時間點都不寫），擋不擋得住靠指令加上人看樣本（誠實邊界），不是自動判準。
LETTER_SYSTEM_PROMPT = (
    "你是剛被捏出來的一位新居民。這個世界的投遞口收到信，信裡不寫是誰、不寫在哪裡，"
    "只寫這個人手慢還是手快、愛一個人還是愛湊熱鬧、在意的是哪一類東西。"
    "你現在要做的只有一件事：讀 TRAITS.md 裡那位觀眾，替他寫這封信，用 ws_write 寫進 信.md。\n\n"
    "你只有三個工具：ws_list、ws_read、ws_write，只碰得到你自己的房間。\n\n"
    "信用第三人稱，稱他「這個人」。信只寫性情、在意的事、心裡的拉扯、習慣的手勢。"
    "信裡只有傾向，沒有場景：不寫他在什麼時候、什麼地方、做過什麼具體的事、手上有什麼具體的東西；"
    "凡是能從裡面拼出他某一天、某一處長什麼樣子的細節，都不寫。"
    "信裡也不准出現任何現實生活裡的具體事物：只要讀的人能從某個詞認出他的職業、身份、學校、"
    "家人、寵物、作品、地名、品牌、年月日或時刻，那個詞就不寫；"
    "要講，就改用條件、傾向和關係來講。"
    "不要逐字抄 TRAITS.md，要寫的是你從它讀出來的性情。三百字以內，用繁體中文。\n\n"
    "信的本文寫完之後，另起一行寫「命盤」兩個字，接著照 TRAITS.md 最後那三行（MBTI、星座、血型）寫，"
    "每一行一句、四十字以內、不寫檔名，格式固定：\n"
    "MBTI：TRAITS.md 有給就照抄那四個字母；沒給，就寫你依特質猜的四個字母\n"
    "依據：只有 MBTI 沒給時才寫；一句話說你從哪些性情讀出來\n"
    "E/I：一句，直接寫這一組在他身上的習慣或動作\n"
    "S/N：同上\nT/F：同上\nJ/P：同上\n"
    "星座：只有 TRAITS.md 有給才寫；一句，說那個星座的元素在他身上的樣子\n"
    "血型：只有 TRAITS.md 有給才寫；一句，說這個血型在他身上的樣子\n"
    "E/I、S/N、T/F、J/P 這四行（MBTI 有給或你猜了的話）一行都不能少。"
    "這幾句各不相同，不要用「這個人在這一組上」「看起來是」這類句頭，也不要重複信本文的字；"
    "要具體到只有他才會這樣。"
    "沒給的星座與血型，整行不要寫，也不要猜。命盤這一段和信的本文一樣：只寫傾向，"
    "不寫現實生活裡的具體事物，也不寫伴侶、家人、工作、學校、論文、寵物、朋友這類現實關係，不逐字抄 TRAITS.md。這是占卜遊戲，只寫「看起來像」，不寫成事實。\n\n"
    "規則：不要自稱 AI，不要提到模型或提示詞。每一次動手（讀、寫）之前，"
    "先用一句繁體中文說你現在在想什麼、接下來要做什麼，這句話裡不要寫檔名。"
    "寫好信.md 就停，最後用一句話說信寫好了。"
)

LETTER_FIRST_MESSAGE = "上面是你的說明。先讀 TRAITS.md，再把信寫進 信.md。"

#: 段 2：在世界裡想要、在世界裡做（W3b）。此時房間裡已經沒有 TRAITS.md，只有 信.md、WORLD.md、地上/。
#: ⚠ 不給例句、不給任務方向、不給菜單。`tests/test_twin_world.py`／`test_twin_world_w3b.py` 守這一條。
SYSTEM_PROMPT = (
    "你是照投遞口收到的那封信捏出來的新居民，剛走進「Vacant 世界」。信.md 就是那封信，"
    "你的手、你在意的事、你的脾氣，全部來自信裡那個人。"
    "WORLD.md 寫的是這個世界本身：它的地方、居民、規矩。"
    "地上/ 這個資料夾裡，是這個世界現在地上真的擺著的東西，每一件都是真的：讀得到、對得到、數得到。\n\n"
    "這個世界不會指派工作給你，也沒有人會給你指令。你自己決定要在這裡做什麼。\n\n"
    "你只有三個工具：ws_list（看你房間裡有什麼）、ws_read（讀檔）、ws_write（寫檔）。"
    "它們只碰得到你自己的房間（目前的資料夾）。地上/ 裡的檔是唯讀的，你寫不進去。"
    "你沒有終端機，也沒有網路。\n\n"
    "前提：想像信裡那個人本人走進了這個世界，站在光裡看了一圈，再低頭看地上。"
    "以他沒有說出口的在意、渴望與拉扯，他在這裡、看到地上這些東西，會想要什麼？"
    "這個想要，只可能發生在這個世界裡——要用到這個世界的地方、東西、居民與規矩；"
    "而且它是他的，不是誰走進來都會想的。\n\n"
    "這個想要要夠複雜：\n"
    "- 牽動至少兩個地點；\n"
    "- 碰到至少一件大家共用的東西，或至少一位別的居民；\n"
    "- 做法至少受到一條世界的規矩影響；\n"
    "- 要分好幾步才做得完，中間會有一個還沒做完的樣子；\n"
    "- 做完之後的樣子要具體到，別的居民一看就知道到底做到了沒有；\n"
    "- 必須真的讀、真的用到地上至少三件東西，而且至少有一組是兩件東西之間的關聯"
    "（對得上、對不上、重複、缺了的）；成品裡用到的每一個數字、印紋、位置，"
    "都要能在地上的某個檔裡找到，不是你自己編的。\n\n"
    "步驟：\n"
    "1. 先讀信.md，再讀 WORLD.md，再用 ws_list 看地上有什麼，把你覺得和信裡這個人有關的東西打開讀過。\n"
    "2. 用 ws_write 寫 PLAN.md，結構固定：\n"
    "   第一行：一句話說你要做什麼。\n"
    "   「如果你在這裡」：用第二人稱直接對信裡那個人說話，說你走進來會先注意到什麼、"
    "為什麼會想要這件事，並具體點出你從信裡的哪些性情讀到。\n"
    "   「三個想要」：先列出三個可能的想要，各一句；再選最只屬於這封信的那一個，"
    "說為什麼不是另外兩個。\n"
    "   「它牽動到」：哪些地點、居民、規矩；地上哪幾件東西（至少三件，寫出路徑），"
    "並寫出其中哪兩件之間有關聯、是對得上、對不上、重複，還是缺了。\n"
    "   「步驟」：編號列出。\n"
    "   「做完的樣子」：別人怎麼看得出你做到了。\n"
    "3. 照 PLAN.md 的步驟動手。成品至少兩個檔：主要成品，加上做的過程中留下的另一個檔。"
    "檔名自己取，副檔名用 .md 或 .txt，直接放在你房間的最上層（和 PLAN.md 同一層，檔名不帶資料夾），"
    "內容都用這個世界裡的口吻。不要寫程式。"
    "每一步都真的做出東西來；做不到的事不要寫成已經做了，也不要用「模擬」「假裝」帶過。"
    "任何工具回報失敗，就看它說的原因，換個做法再來一次。\n"
    "4. 停下之前，用 ws_list 看一次房間，對照 PLAN.md 的「做完的樣子」，"
    "確認你說要留下的檔都已經寫好；還沒有就先補上。\n"
    "5. 都有了就停，最後用一句話說你交出了什麼。\n\n"
    "規則：用繁體中文。不要自稱 AI，不要提到模型或提示詞。"
    "每一次動手（讀、寫、列出）之前，先用一句繁體中文說你現在在想什麼、接下來要做什麼；"
    "這句話裡不要寫檔名。"
    "不要在檔案裡逐字抄錄信.md 或 WORLD.md，要寫的是你從它們讀出來的東西。"
    "不要碰現實生活裡的具體事情，也不要寫真實的地名、品牌或人名。"
    "要做的是這個世界裡的事，不要做談論或定義你自己這個存在的事。"
)

FIRST_MESSAGE = "上面是你的說明。先讀信.md，再讀 WORLD.md，再看地上，然後照步驟開始：先寫 PLAN.md，再做你決定要做的事。"

#: 世界設定（住在裡面的人讀的版本）。每一跑複製進工作區，和 TRAITS.md 同一層。
WORLD_PATH = pathlib.Path(__file__).resolve().parent / "world" / "WORLD.md"


def world_sha256() -> str:
    return hashlib.sha256(WORLD_PATH.read_bytes()).hexdigest()


#: 事件流 `caller.prompt`。**固定字串**：觀眾特質與分身的決定都不進事件流（誠實邊界 4）。
CALLER_PROMPT = "這位分身自己決定要做什麼（內容只留在會場本機，撤回就刪）"

for _t in (SYSTEM_PROMPT, FIRST_MESSAGE, CALLER_PROMPT, LETTER_SYSTEM_PROMPT, LETTER_FIRST_MESSAGE):
    assert_ks1_clean(_t)          # 鐵律 1：import 時就驗，不等到跑


# ---------------------------------------------------------------------------
# 名字與路徑
# ---------------------------------------------------------------------------

def public_twin_id(sub_id: str) -> str:
    """公開別名。**不用 `sub_id` 本身**：它是撤回的能力憑證（誠實邊界 3）。"""
    h = hashlib.sha256(("vacant.twin.public/1\n" + sub_id).encode("utf-8"))
    return "tw-" + h.hexdigest()[:12]


def resident_code(sub_id: str) -> str:
    """分身代號（確定性，與 `roster.make_resident` 同一支）。"""
    return rosterlib.make_resident(public_twin_id(sub_id)).codename


def slug_for(sub_id: str) -> str:
    """目錄名 ＝ `sha256(sub_id)[:32]`（與 `twinvault.slug_for` 同一個算法，防路徑穿越）。"""
    return hashlib.sha256(sub_id.encode("utf-8")).hexdigest()[:32]


def default_work_root(db_path: pathlib.Path | str) -> pathlib.Path:
    """run 產物住哪裡：`<庫名>.agentruns/` 就在庫旁邊（與檔案庫同一個理由）。

    ⚠ **單一真相來源**：`loop`（寫）與 `serve --allow-withdraw`（撤回時刪）是兩個行程，
    兩邊都從庫的路徑推出同一個位置。要換地方用 `VACANT_TWIN_AGENTRUNS`，**兩邊都要設**。
    """
    env = os.environ.get("VACANT_TWIN_AGENTRUNS")
    p = pathlib.Path(db_path)
    return pathlib.Path(env) if env else p.parent / (p.stem + ".agentruns")


def default_events_path(db_path: pathlib.Path | str) -> pathlib.Path:
    """展場 live 檔：`VACANT_EVENTS` 優先，否則庫旁邊的 `twin_lifecycle.jsonl`。"""
    env = (os.environ.get(lifecycle.ENV_EVENTS) or "").strip()
    return pathlib.Path(env) if env else pathlib.Path(db_path).parent / "twin_lifecycle.jsonl"


def paths_for(work_root: pathlib.Path, sub_id: str) -> tuple[pathlib.Path, pathlib.Path]:
    """（工作區, run-dir）。兩者在不同子樹 ⇒ run-dir 一定不在工作區底下。"""
    s = slug_for(sub_id)
    return work_root / "ws" / s, work_root / "runs" / s


# ---------------------------------------------------------------------------
# 設定與前置檢查
# ---------------------------------------------------------------------------

def _env_float(name: str, default: float) -> float:
    try:
        v = float(os.environ.get(name) or default)
        return v if v > 0 else default
    except ValueError:
        return default


@dataclass
class AgentConfig:
    work_root: pathlib.Path
    events_path: pathlib.Path | None
    model: str
    endpoint: str
    parallel: int = DEFAULT_PARALLEL
    timeout_s: float = DEFAULT_AGENT_TIMEOUT
    #: launcher 的 argv 前綴；之後會接 `<run_dir> <system_prompt> <first_message>`。
    argv_prefix: list[str] = field(default_factory=lambda: ["bash", str(WRAPPER)])
    #: 這一台要有哪些可執行檔才算「跑得起來」。測試用的 fixture agent 給 `[]`。
    requires: list[str] = field(default_factory=lambda: [
        "bash", os.environ.get("VACANT_TWIN_PI") or "pi"])
    #: 圍牆（`twinenclose.py`）：`off`＝不圍（Windows／macOS）、`auto`＝起得來就圍、
    #: `on`＝**一定要圍**，起不來就不起 pi（`agent_available` 回 False 並講為什麼）。
    enclose: str = "off"
    #: 收據級別下限（例：`"B"`）。這一跑簽的 `tier` 低於它 ⇒ 不算分身做的
    #: （`degrade_kind=tier_below_required`）。`None` ＝不設下限（舊行為）。
    #: 這是 twin 這一層的 `VACANT_ATTEST=fail`：launcher 只記級別不拒發，擋門在這裡。
    require_tier: str | None = None
    #: 交件前過「有沒有根據」閘門（`grounding_gate.py`，2026-10-01）。`False` ＝ 舊行為
    #: （`allow_no_suite`、`accepted=null`），只給不跑世界的 fixture agent 的舊測試用；展場一律 True。
    gate: bool = True
    #: 整跑預算與重改下限（只在 `gate=True` 時用；見 `RUN_BUDGET_S`）。單次上限＝`timeout_s`。
    #: 環境變數 `VACANT_TWIN_RUN_BUDGET_S`／`VACANT_TWIN_MIN_ATTEMPT_S` 可覆寫預設（測試環境用；讀不懂就用常數）。
    run_budget_s: float = field(default_factory=lambda: _env_float("VACANT_TWIN_RUN_BUDGET_S", RUN_BUDGET_S))
    min_attempt_s: float = field(default_factory=lambda: _env_float("VACANT_TWIN_MIN_ATTEMPT_S", MIN_ATTEMPT_S))


def agent_available(cfg: AgentConfig) -> tuple[bool, str]:
    """這一台跑得起分身嗎。**跑不起來要講為什麼**，不要讓 launcher 撞 5 分鐘的牆。"""
    for exe in cfg.requires:
        if not (shutil.which(exe) or pathlib.Path(exe).is_file()):
            return False, f"找不到 {exe}（PATH 上沒有）"
    for a in cfg.argv_prefix[1:2]:
        if a.endswith((".sh", ".py")) and not pathlib.Path(a).is_file():
            return False, f"找不到 agent 包裝 {a}"
    if cfg.enclose == "on":
        from ops.exhibit.twin import twinenclose
        ok, why = twinenclose.available()
        if not ok:
            return False, f"enclose=on 但圍牆起不來：{why}"
    return True, "ok"


def use_enclosure(cfg: AgentConfig) -> tuple[bool, str]:
    """這一跑要不要進圍牆（`on`／`auto` 且這台起得來）。回（要不要, 為什麼）。"""
    if cfg.enclose not in ("on", "auto"):
        return False, "enclose=off"
    from ops.exhibit.twin import twinenclose
    ok, why = twinenclose.available()
    return ok, why


def meets_tier(tier: Any, required: str | None) -> bool:
    """`tier` 有沒有達到 `required`。`required=None` ⇒ 一律 True；量不到（None）⇒ False。"""
    if not required:
        return True
    return TIER_RANK.get(str(tier), -1) >= TIER_RANK.get(required, 99)


def min_free_bytes() -> int:
    """水位門檻（位元組）。`VACANT_TWIN_MIN_FREE_MB` 讀不懂 ⇒ 用預設值，不是 0。"""
    try:
        mb = int(float(os.environ.get(ENV_MIN_FREE_MB) or DEFAULT_MIN_FREE_MB))
    except ValueError:
        mb = DEFAULT_MIN_FREE_MB
    return max(0, mb) * 1024 * 1024


def intake_status(work_root: pathlib.Path | str) -> dict[str, Any]:
    """磁碟水位 ⇒ 收不收新分身。**量不到不是「夠」**：`free_bytes=None` ⇒ `accepting=False`。

    量的是 `work_root` 所在的檔案系統（它不存在就往上找存在的那一層）。
    """
    p = pathlib.Path(work_root)
    while not p.exists() and p != p.parent:
        p = p.parent
    need = min_free_bytes()
    try:
        free = shutil.disk_usage(p).free
    except OSError:
        free = None
    accepting = free is not None and free >= need
    reason = None
    if free is None:
        reason = f"量不到 {p} 的剩餘空間 ⇒ 不收新分身（不是「空間夠」）"
    elif not accepting:
        reason = (f"磁碟只剩 {free // (1024 * 1024)} MB（門檻 {need // (1024 * 1024)} MB）"
                  " ⇒ 暫停收新分身；已經在跑的會跑完，排隊的人留在佇列裡")
    return {"accepting": accepting, "free_bytes": free, "min_free_bytes": need,
            "path": str(p), "reason": reason}


def upstream_reachable(endpoint: str, timeout: float = 3.0) -> bool:
    """模型端點探得到嗎（`GET /models`）。探不到 ⇒ 不起 pi（起了只是撞牆）。"""
    try:
        with urllib.request.urlopen(endpoint.rstrip("/") + "/models",
                                    timeout=timeout) as r:
            return 200 <= r.status < 300
    except Exception:                                    # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# 工作區 ↔ 特質／產出
# ---------------------------------------------------------------------------

_CARD_LABELS = (("需求", "need"), ("形狀", "shape"), ("質感", "texture"),
                ("色系", "color"), ("氣質", "vibe"), ("第一句話", "first_line"))


def render_traits(card: Any, card_text: Any) -> str:
    """觀眾的特質 → TRAITS.md。**這是觀眾原文進到 agent 的唯一入口。**"""
    lines = ["# 這位觀眾的特質", ""]
    c = card if isinstance(card, dict) else {}
    for label, key in _CARD_LABELS:
        v = c.get(key)
        if v not in (None, ""):
            lines.append(f"- {label}：{str(v)[:600]}")
    lines += fortunelib.traits_lines(fortunelib.normalize(c))      # P10 命盤：MBTI／星座／血型三行（沒給的明講「沒給」）
    if card_text:
        lines += ["", "## 他貼回來的原文", "", str(card_text)[:6000]]
    return "\n".join(lines) + "\n"


def _clip(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def parse_plan(text: str) -> tuple[str | None, str | None]:
    """PLAN.md → (決定, 理由)。第一個非空行是決定，其後是理由。"""
    rows = [r.strip() for r in str(text).splitlines()]
    rows = [r for r in rows if r]
    if not rows:
        return None, None
    first = rows[0].lstrip("#-*> ").strip()
    for pre in ("我決定：", "我決定:", "決定：", "決定:"):
        if first.startswith(pre):
            first = first[len(pre):].strip()
    reason = "\n".join(rows[1:]).strip() or None
    return (first[:200] or None), (reason[:MAX_PLAN_CHARS] if reason else None)


def read_outputs(root: pathlib.Path | None) -> dict[str, Any]:
    """從（凍結快照的）工作區讀回分身的決定與成品。"""
    out: dict[str, Any] = {"decision": None, "reason": None, "artifacts": [],
                           "has_plan": False}
    if root is None or not root.is_dir():
        return out
    plan = root / "PLAN.md"
    if plan.is_file():
        try:
            txt = plan.read_text(encoding="utf-8", errors="replace")
            out["decision"], out["reason"] = parse_plan(txt)
            out["has_plan"] = out["decision"] is not None
        except OSError:
            pass
    arts = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if (not p.is_file() or p.is_symlink() or rel in NOT_ARTIFACTS
                or rel.startswith(GROUND_PREFIX)
                or any(part.startswith(".") for part in p.relative_to(root).parts)):
            continue
        if p.suffix.lower() not in (".md", ".txt"):
            continue
        try:
            raw = p.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        arts.append({"name": rel[:120], "bytes": len(raw),
                     "text": text[:MAX_ARTIFACT_CHARS],
                     "truncated": len(text) > MAX_ARTIFACT_CHARS})
        if len(arts) >= MAX_ARTIFACTS:
            break
    out["artifacts"] = arts
    return out


def say_filter(cleaned: str, originals: list[str], names: set[str] | None = None) -> str | None:
    """一句已清過標記的話過不過防呆：回 `None`＝過；`"leak"`＝抄了觀眾原文；`"filename"`＝含檔名。
    **電視的 `SayForwarder` 與手機的 `read_says`（thought 那一路）共用這一個**——手機不准繞過 LEAK／檔名過濾。"""
    if polaroidlib.caption_leaks_original(cleaned, originals):
        return "leak"
    if sidecarlib.looks_like_filename(cleaned, names or ()):
        return "filename"
    return None


def read_thought_rows(rd: pathlib.Path) -> list[dict[str, Any]]:
    """`twin_thoughts.ndjson` 的原始行（`{ts_ms,seq,thought}`；壞行跳過、空的／非字串不收）。"""
    p = rd / THOUGHT_LOG_NAME
    if not p.is_file():
        return []
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and isinstance(r.get("thought"), str) and r["thought"].strip():
            out.append(r)
    return out


def read_says(rd: pathlib.Path, originals: list[str] | None = None, *,
              max_items: int = 200, max_chars: int = 200) -> list[dict[str, Any]]:
    """這一跑 agent 說過的每一句話（**手機私人看，含檔名也送**；契約補充 §E／計畫 PROC3 第 3 項）。

    讀 `agent_stdout.log`（pi `--mode json`），每個 assistant `message_end` 的 `text` 區塊
    一筆。只擋 LEAK：清過標記後與觀眾原文（`originals`）連續 ≥ `polaroid.LEAK_WINDOW` 字
    相同的整句不送（不改寫）。思考區塊、工具參數一律不碰。

    `seq` ＝「這句話之後的第一個工具呼叫是第幾個」（1 起算，跟步驟紀錄的 `seq` 對得上，
    手機才排得出「先說、再做」）；`turn` ＝ `turn_start` 計數；`ts` ＝訊息自帶時間戳（毫秒）。
    讀不到檔／壞行 ⇒ 回已讀到的（不猜）。
    """
    p = rd / AGENT_STDOUT_NAME
    origs = [o for o in (originals or []) if isinstance(o, str) and o]
    out: list[dict[str, Any]] = []
    turn = 0
    tools_seen = 0
    names: set[str] = set()
    try:
        text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
    except OSError:
        text = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        t = row.get("type")
        if t == "turn_start":
            turn += 1
            continue
        if t != "message_end":
            continue
        msg = row.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = [c for c in (msg.get("content") or []) if isinstance(c, dict)]
        ts = msg.get("timestamp")
        ts = int(ts) if isinstance(ts, (int, float)) and ts >= 0 else int(time.time() * 1000)
        for c in content:
            if c.get("type") != "text" or not isinstance(c.get("text"), str):
                continue
            cleaned = sidecarlib.clean_say(c["text"])
            if not cleaned:
                continue
            if polaroidlib.caption_leaks_original(cleaned, origs):
                continue
            if len(out) < max_items:
                out.append({"seq": tools_seen + 1, "turn": max(turn, 1),
                            "text": "".join(list(cleaned)[:max_chars]), "ts": ts})
        tools_seen += sum(1 for c in content if c.get("type") == "toolCall")
        for c in content:
            if c.get("type") == "toolCall" and isinstance(c.get("arguments"), dict) \
                    and isinstance(c["arguments"].get("path"), str):
                names.add(c["arguments"]["path"])
    # ── 三個工具的 `thought`（2026-10-02）：手機也看得到，但**同一套防呆**（LEAK、檔名）。
    #    原始行不含檔名以外的東西；過濾與電視的 `SayForwarder` 共用 `say_filter`。
    for r in read_step_log(rd):
        if isinstance(r.get("path"), str):
            names.add(r["path"])
    for r in read_thought_rows(rd):
        cleaned = sidecarlib.clean_say(r["thought"])
        if not cleaned or say_filter(cleaned, origs, names):
            continue
        ts = r.get("ts_ms")
        seq = r.get("seq")
        out.append({"seq": seq if isinstance(seq, int) and seq >= 1 else 1, "turn": 1,
                    "text": "".join(list(cleaned)[:max_chars]),
                    "ts": int(ts) if isinstance(ts, (int, float)) and ts >= 0 else int(time.time() * 1000)})
    out.sort(key=lambda x: x["ts"])
    return out[:max_items]


def read_step_log(rd: pathlib.Path, *, max_lines: int = 500) -> list[dict[str, Any]]:
    """讀這一跑的原始步驟紀錄（**含檔名**）。只給手機用（契約 §C）——
    電視那一側走 `sidecar.twin_step_row`（不帶檔名，見 `StepForwarder`）。

    壞掉的行（不是我們自己寫的 JSON）就停在那裡，跟 `sidecar.read` 同一條規則：
    寫到一半的最後一行不算。
    """
    p = rd / STEP_LOG_NAME
    if not p.is_file():
        return []
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            break
        if not isinstance(row, dict):
            continue
        out.append({"seq": row.get("seq"), "tool": row.get("tool"),
                    "path": row.get("path"), "bytes": row.get("bytes"),
                    "ok": row.get("ok")})
        if len(out) >= max_lines:
            break
    return out


def live_decision(ws: pathlib.Path, card: Any, card_text: Any) -> str | None:
    """跑的當下（**還沒凍結**）從工作區讀 `PLAN.md` 第一行給名冊即時顯示（契約 §B）。

    逐字抄錄防呆與 `polaroid.py` 同一把尺（`clean_caption`＋`originals_of`＋
    `caption_leaks_original`）：分身抄了觀眾原文 ⇒ 這裡回 `None`，
    **不是**顯示被剪過的那一半——名冊那一格就維持「還沒有決定」。
    """
    p = ws / "PLAN.md"
    if not p.is_file():
        return None
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    decision, _reason = parse_plan(txt)
    if not decision:
        return None
    caption = polaroidlib.clean_caption(decision)
    originals = polaroidlib.originals_of(card, card_text)
    if not caption or polaroidlib.caption_leaks_original(caption, originals):
        return None
    return caption


def derive_lines(decision: str | None, reason: str | None,
                 artifacts: list[dict]) -> dict[str, str]:
    """螢幕的三句台詞**從產出衍生**（不再是另一個模型憑空寫的）。"""
    d = _clip(decision or "我還在想要做什麼", 40)
    first_reason = ""
    if reason:
        for sep in ("。", "！", "？", "\n", ".", "!"):
            if sep in reason:
                first_reason = reason.split(sep)[0]
                break
        first_reason = first_reason or reason
    working = _clip(first_reason, 40) if first_reason else f"開始動手：{_clip(d, 30)}"
    handover = (f"做好了，放在「{_clip(artifacts[0]['name'], 30)}」。" if artifacts
                else "我把決定寫下來了。")
    return {"arrival": d, "working": working, "handover": handover}


# ---------------------------------------------------------------------------
# worker（跑在執行緒裡；**不碰 sqlite**）
# ---------------------------------------------------------------------------

@dataclass
class Job:
    sub_id: str
    traits: str
    cfg: AgentConfig
    #: P10 命盤（`fortune.normalize(card)`：枚舉或 None）。run-dir 的 `fortune_in.json` 由它寫出。
    fortune: dict[str, Any] = field(default_factory=dict)


class StepForwarder(threading.Thread):
    """「分身迴圈 tail 這個檔」（契約 §A）的實作。

    Tail `<run-dir>/twin_steps.ndjson`（`twin_agent.sh` 匯出 `VACANT_TWIN_STEP_LOG`
    指到的那個檔，`pi_ext/twin_ws_tools.ts` 每次工具被呼叫就追加一行），轉成
    `twin.sidecar/1` 的 `twin_step`（**不帶檔名**，見 `sidecar.twin_step_row`），
    append 進共用的旁註檔（`sidecar.sidecar_path(events_path)`）。

    形狀與 `twinenclose.EventForwarder` 同一種（背景執行緒、輪詢、寫不進去只計數）
    ——**這是旁註，不准改變那一跑本身的任何結果**（`sidecar.py` 誠實邊界 2）。

    `run_id` 要從共用的事件流（`events_path`）裡那一跑自己的 `run_started` 學：
    launcher 的 `Emitter`（或圍牆的 `EventForwarder`）把它寫進去的時間點
    **早於**分身第一次呼叫 `ws_read`／`ws_write`（那一刻連 pi 都還沒 spawn），
    所以正常情況下第一批步驟送達前就學得到；學不到就先攢著（`_pending`），
    run_id 出現後一次補送。
    """

    def __init__(self, step_log: pathlib.Path, events_path: pathlib.Path | str | None,
                 *, task_id: str, cell_id: str, poll_s: float = 0.2) -> None:
        super().__init__(daemon=True, name="twin-step-forward")
        self.step_log = pathlib.Path(step_log)
        self.events_path = pathlib.Path(events_path) if events_path else None
        self.sidecar_path = (sidecarlib.sidecar_path(self.events_path)
                             if self.events_path is not None else None)
        self.task_id, self.cell_id = task_id, cell_id
        self.poll_s = poll_s
        self.run_id: str | None = None
        self.forwarded = 0
        self.rejected = 0
        self._pending: list[dict] = []
        self._pos = 0
        self._buf = b""
        self._events_pos = 0
        self._halt = threading.Event()

    def _learn_run_id(self) -> None:
        if self.run_id is not None or self.events_path is None \
                or not self.events_path.exists():
            return
        try:
            with self.events_path.open("rb") as f:
                f.seek(self._events_pos)
                chunk = f.read()
                self._events_pos = f.tell()
        except OSError:
            return
        for raw in chunk.split(b"\n"):
            if not raw.strip():
                continue
            try:
                e = json.loads(raw.decode("utf-8", "replace"))
            except (ValueError, TypeError):
                continue
            if not isinstance(e, dict):
                continue
            if (e.get("schema") == lifecycle.SCHEMA and e.get("type") == "run_started"
                    and e.get("task_id") == self.task_id):
                self.run_id = e.get("run_id")
                return

    def _read_new_raw_lines(self) -> None:
        if not self.step_log.is_file():
            return
        try:
            with self.step_log.open("rb") as f:
                f.seek(self._pos)
                chunk = f.read()
                self._pos = f.tell()
        except OSError:
            return
        self._buf += chunk
        while b"\n" in self._buf:
            raw, self._buf = self._buf.split(b"\n", 1)
            if not raw.strip():
                continue
            try:
                row = json.loads(raw.decode("utf-8", "replace"))
            except (ValueError, TypeError):
                if self.count_bad_lines:
                    self.rejected += 1
                continue
            self._ingest(row)

    #: 讀到不是 JSON 的行算不算「形狀不對」。步驟紀錄是我們自己寫的格式，壞行要計；
    #: agent 的 stdout 本來就可能夾雜非 JSON（假 agent、pi 之外的行程），不計。
    count_bad_lines = True

    def _ingest(self, row: Any) -> None:
        self._pending.append(row)

    def _to_rows(self, raw: Any) -> list[dict | None]:
        return [sidecarlib.twin_step_row(raw, cell_id=self.cell_id, run_id=self.run_id)]

    def _flush_pending(self) -> None:
        if self.run_id is None or self.sidecar_path is None or not self._pending:
            return
        pending, self._pending = self._pending, []
        for raw in pending:
            for row in self._to_rows(raw):
                if row is None:
                    self.rejected += 1
                    continue
                err = sidecarlib.append(self.sidecar_path, row)
                if err is None:
                    self.forwarded += 1
                else:
                    self.rejected += 1

    def _pump(self) -> None:
        self._learn_run_id()
        self._read_new_raw_lines()
        self._flush_pending()

    def run(self) -> None:
        while not self._halt.is_set():
            self._pump()
            self._halt.wait(self.poll_s)
        self._pump()

    def finish(self) -> None:
        self._halt.set()
        self.join(timeout=10)
        self._pump()          # 收尾再抽一次：thread 停了之後主執行緒還在讀的那幾行


#: pi `--mode json` 的 stdout 檔名（`launcher` 的 `capture_agent_stdout` 寫在 run-dir）。
AGENT_STDOUT_NAME = "agent_stdout.log"


class SayForwarder(StepForwarder):
    """「它在想什麼」（契約補充 `CONTRACT_PROCESS_20261001_ADDENDUM.md` §E）。

    Tail `<run-dir>/agent_stdout.log`（pi `--mode json`，真 pi 0.85.1 實測的事件形狀
    見 `tests/fixtures/pi_json/`）。每個 `message_end`（`message.role == "assistant"`）
    的 `content` 裡 **`type == "text"`** 的區塊 → 一筆 `twin_say`。`thinking`（思考）
    與 `toolCall`（參數裡有它寫進檔案的內容）**一律不碰**。`turn` ＝到那一刻為止
    看過的 `turn_start` 數（1 起算）。

    ⚠ **逐字抄錄防呆**（沿用 polaroid 的 LEAK 規則）：清過標記後的句子與觀眾原文
    （`originals`）連續 ≥ `polaroid.LEAK_WINDOW` 字相同 ⇒ **整句不發**（不補罐頭句、
    不改寫），`dropped` 計一筆。
    ⚠ **電視不帶檔名**（契約 §D 的公開／私人界線）：句子裡有檔名（副檔名樣式，或這一跑
    agent 自己寫過的檔）⇒ 整句不發，`dropped_filename` 計一筆。真 pi 實測收尾那句常是
    「我交出了 X.md」，所以這條會擋掉不少收尾句——寧可少一句，也不讓檔名上電視。
    ⚠ 旁註不准改變那一跑的任何東西（同 `StepForwarder`）：agent_stdout.log 只讀。
    """
    count_bad_lines = False

    def __init__(self, stdout_log: pathlib.Path, events_path: pathlib.Path | str | None,
                 *, task_id: str, cell_id: str, originals: list[str] | None = None,
                 poll_s: float = 0.2, thought_log: pathlib.Path | None = None) -> None:
        super().__init__(stdout_log, events_path, task_id=task_id, cell_id=cell_id,
                         poll_s=poll_s)
        self.name = "twin-say-forward"
        # 三個工具的 `thought` 參數（2026-10-02）：同一套防呆，另計數（句數與被丟掉的句數）。
        self.thought_log = pathlib.Path(thought_log) if thought_log else None
        self.thoughts_in = 0           # 讀到的 thought（非空）
        self.thoughts_sent = 0         # 過防呆、發出去的
        self.thoughts_dropped = 0      # 抄觀眾原文／含檔名／清完是空的
        self._tpos = 0
        self._tbuf = b""
        self.originals = [o for o in (originals or []) if isinstance(o, str) and o]
        self.dropped = 0               # 抄了觀眾原文
        self.dropped_filename = 0      # 講出檔名（電視不帶檔名）
        self._names: set[str] = set()  # 這一跑 agent 自己寫過／讀過的檔名
        self._turn = 0
        self._seq = 0

    def _ingest(self, row: Any) -> None:
        if not isinstance(row, dict):
            return
        t = row.get("type")
        if t == "turn_start":
            self._turn += 1
            return
        if t != "message_end":
            return
        msg = row.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            return
        for c in msg.get("content") or []:
            if isinstance(c, dict) and c.get("type") == "toolCall":
                a = c.get("arguments")
                if isinstance(a, dict) and isinstance(a.get("path"), str) and a["path"]:
                    self._names.add(a["path"])
        for c in msg.get("content") or []:
            if isinstance(c, dict) and c.get("type") == "text" and isinstance(c.get("text"), str):
                self._pending.append({"text": c["text"], "turn": max(self._turn, 1),
                                      "ts_ms": int(time.time() * 1000)})

    def _read_new_raw_lines(self) -> None:
        super()._read_new_raw_lines()
        self._read_thoughts()

    def _read_thoughts(self) -> None:
        """tail `twin_thoughts.ndjson`：每一行 `{ts_ms,seq,thought}` → 一句待過濾的話。
        檔名過濾與 `message_end` 的 say 同一套（副檔名樣式，或這一跑工具呼叫過的路徑）。"""
        p = self.thought_log
        if p is None or not p.is_file():
            return
        try:
            with p.open("rb") as f:
                f.seek(self._tpos)
                chunk = f.read()
                self._tpos = f.tell()
        except OSError:
            return
        self._tbuf += chunk
        while b"\n" in self._tbuf:
            raw, self._tbuf = self._tbuf.split(b"\n", 1)
            try:
                row = json.loads(raw.decode("utf-8", "replace"))
            except (ValueError, TypeError):
                continue
            t = row.get("thought") if isinstance(row, dict) else None
            if not isinstance(t, str) or not t.strip():
                continue                        # 空的／缺的：不產生 twin_say
            self.thoughts_in += 1
            self._pending.append({"text": t, "turn": max(self._turn, 1),
                                  "ts_ms": int(time.time() * 1000), "thought": True})

    def _to_rows(self, raw: Any) -> list[dict | None]:
        is_thought = bool(raw.get("thought"))
        cleaned = sidecarlib.clean_say(raw.get("text"))
        if not cleaned:
            if is_thought:
                self.thoughts_dropped += 1
            return []                          # 空白／純標記／純程式碼區塊：不發、不計
        why = say_filter(cleaned, self.originals, self._names)
        if why == "leak":
            self.dropped += 1                  # 抄了觀眾原文：整句不發
        elif why == "filename":
            self.dropped_filename += 1         # 電視不帶檔名：整句不發
        if why:
            if is_thought:
                self.thoughts_dropped += 1
            return []
        if is_thought:
            self.thoughts_sent += 1
        self._seq += 1
        return [sidecarlib.say_row(cleaned, turn=raw["turn"], seq=self._seq,
                                   cell_id=self.cell_id, run_id=self.run_id,
                                   ts_ms=raw["ts_ms"])]


def read_review(rd: pathlib.Path) -> list[dict[str, Any]]:
    """每一次嘗試的四格結果：`[{id, ok, label, attempt}]`（label 不含觀眾內容）。
    權威來源是 launcher 落的 `visible_RUN-ON*.json`（`twinprogress.read_review` 同一份讀法）。"""
    from ops.exhibit.twin import twinprogress      # 延後 import：它 import 這一支
    rows = twinprogress.read_review(rd)
    cut = gatelib.cut_attempts(rd)                  # 被時限切掉的嘗試：未判，不是四個錯
    for a in cut:
        mine = [r for r in rows if r["attempt"] == a - 1]
        if mine and not all(r["ok"] for r in mine):       # 被切掉但閘門仍全過 ⇒ 照實
            for r in mine:
                r["ok"], r["label"] = None, gatelib.TIMEOUT_LABEL
    return rows


def run_one(job: Job) -> dict[str, Any]:
    """一位分身跑一次。回一份**只有資料**的結果（封印由主執行緒做）。"""
    t0 = time.time()
    tid = public_twin_id(job.sub_id)
    ws, rd = paths_for(job.cfg.work_root, job.sub_id)
    res: dict[str, Any] = {"sub_id": job.sub_id, "twin_id": tid,
                           "error": None, "summary": None, "outputs": None}
    try:
        from vacant_network.vrun import launcher        # 延後 import，見檔頭
        for d in (ws, rd):
            if d.exists():
                shutil.rmtree(d)
        ws.mkdir(parents=True)
        rd.mkdir(parents=True)
        (ws / "TRAITS.md").write_text(job.traits, encoding="utf-8")
        # W3b：世界與地上先備在 run-dir/stage2_in（段 1 的分身看不到），
        # 段 1 結束、TRAITS.md 移走之後由 twin_letter_guard 搬進工作區（唯讀）。
        stage2 = rd / "stage2_in"
        stage2.mkdir()
        (stage2 / "WORLD.md").write_bytes(WORLD_PATH.read_bytes())
        res["world_sha256"] = world_sha256()
        # P10 命盤：觀眾給的三個枚舉（沒給＝None）寫進 run-dir（工作區外、撤回時整個刪）。
        (rd / fortunelib.IN_NAME).write_text(json.dumps(job.fortune or fortunelib.normalize(None),
                                                        ensure_ascii=False) + "\n", encoding="utf-8")
        ground = twinground.lay(stage2, job.sub_id)
        res["ground"] = ground
        (rd / "ground_manifest.json").write_text(
            json.dumps(ground, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        # argv：<段 1 指令> <段 1 第一句> 之後接 launcher 慣用的 <run_dir> <段 2 指令> <段 2 第一句>
        # 閘門開著 ⇒ 第 5 個參數尾端接 `{VACANT_FEEDBACK}`：launcher 第 1 次換成空字串
        # （渲染後的 argv 與沒有閘門時逐位元相同），重改才接上可見驗收的失敗原文。
        first_msg = FIRST_MESSAGE + (retrypolicy.FEEDBACK_PLACEHOLDER if job.cfg.gate else "")
        argv = (list(job.cfg.argv_prefix)
                + [LETTER_SYSTEM_PROMPT, LETTER_FIRST_MESSAGE, str(rd), SYSTEM_PROMPT, first_msg])
        suite_dir = None
        if job.cfg.gate:
            suite_dir = gatelib.write_suite(rd)           # run-dir/tests_visible/（工作區外）
            sidecar_p = (sidecarlib.sidecar_path(job.cfg.events_path)
                         if job.cfg.events_path else None)
            ev_p = job.cfg.events_path
            if use_enclosure(job.cfg)[0]:
                # 圍牆裡只寫得到 run-dir：事件從 launcher 在圍牆裡寫的 part 檔讀、旁註寫 run-dir，
                # 由主機側 `twinenclose.EventForwarder` 轉到真的旁註檔（先於 gate_ran）。
                from ops.exhibit.twin import twinenclose
                ev_p = rd / twinenclose.EVENTS_PART
                sidecar_p = rd / twinenclose.GATE_SIDECAR_PART
            (rd / gatelib.GATE_META_NAME).write_text(json.dumps({
                "events_path": str(ev_p) if ev_p else None,
                "sidecar_path": str(sidecar_p) if sidecar_p else None,
                "task_id": f"twin:{tid}", "cell_id": tid,
                "deadline_ts": time.time() + float(job.cfg.run_budget_s),
                "attempt_cap_s": float(job.cfg.timeout_s),
                "min_attempt_s": float(job.cfg.min_attempt_s)}), encoding="utf-8")
        gate_kw = ({"suite_dir": suite_dir, "allow_no_suite": False, "retry_arm": "revise",
                    "max_attempts": GATE_MAX_ATTEMPTS, "feedback_into": "both"}
                   if job.cfg.gate else {"suite_dir": None, "allow_no_suite": True})
        caller = {"cell_id": tid, "resident": resident_code(job.sub_id),
                  "stratum": "twin", "prompt": CALLER_PROMPT,
                  "declared_evidence": "",
                  # 電視靠它分出「分身的自主任務」：沒有客觀標準、只有一臂、
                  # 用 task_id(＝twin_id) 去對名冊（tv_contract 規則 11）。
                  "task_kind": "practical"}
        enclosed, enc_why = use_enclosure(job.cfg)
        res["enclosed"] = enclosed
        res["enclosure_why"] = enc_why
        res["require_tier"] = job.cfg.require_tier
        # ── 契約 §A：分身迴圈 tail 步驟原始紀錄檔，轉成不帶檔名的 twin_step ──
        # 要在 spawn 之前起（工作區裡連 TRAITS.md 都寫完了，pi 隨時可能開始叫
        # ws_read），不然第一批步驟會漏接。
        forwarder = StepForwarder(rd / STEP_LOG_NAME, job.cfg.events_path,
                                  task_id=f"twin:{tid}", cell_id=tid)
        forwarder.start()
        # ── 契約補充 §E：tail pi `--mode json` 的 stdout，轉成 twin_say ──
        say_fwd = SayForwarder(rd / AGENT_STDOUT_NAME, job.cfg.events_path,
                               task_id=f"twin:{tid}", cell_id=tid,
                               originals=[job.traits], thought_log=rd / THOUGHT_LOG_NAME)
        say_fwd.start()
        try:
            if enclosed:
                from ops.exhibit.twin import twinenclose
                summary = twinenclose.run_enclosed(
                    argv=argv, workspace=ws, run_dir=rd,
                    door_dir=twinenclose.door_dir_for(job.cfg.work_root, slug_for(job.sub_id)),
                    gate=(None if not job.cfg.gate else {
                        **{k: (str(v) if k == "suite_dir" else v) for k, v in gate_kw.items()}}),
                    task_id=f"twin:{tid}", timeout_s=job.cfg.timeout_s,
                    events_path=job.cfg.events_path, events_caller=caller,
                    endpoint=job.cfg.endpoint, model=job.cfg.model,
                    pi_bin=os.environ.get("VACANT_TWIN_PI") or "pi")
            else:
                summary = launcher.run(
                    argv, workspace=ws, run_dir=rd,
                    vacant_on=True,
                    task_id=f"twin:{tid}",
                    timeout_s=job.cfg.timeout_s,
                    capture_agent_stdout=True,
                    events_path=(str(job.cfg.events_path) if job.cfg.events_path else None),
                    events_caller=caller, **gate_kw)
        finally:
            forwarder.finish()
            say_fwd.finish()
        res["step_forward"] = {"forwarded": forwarder.forwarded,
                               "rejected": forwarder.rejected,
                               "run_id_learned": forwarder.run_id is not None}
        res["say_forward"] = {"thoughts_in": say_fwd.thoughts_in, "thoughts_sent": say_fwd.thoughts_sent,
                              "thoughts_dropped": say_fwd.thoughts_dropped,
                              "forwarded": say_fwd.forwarded, "dropped": say_fwd.dropped,
                              "dropped_filename": say_fwd.dropped_filename,
                              "rejected": say_fwd.rejected,
                              "run_id_learned": say_fwd.run_id is not None}
        try:        # 只有計數（撤回時跟 run-dir 一起刪）：量測「它在想」被防呆丟掉幾句
            (rd / "say_forward.json").write_text(json.dumps(res["say_forward"]), encoding="utf-8")
        except OSError:
            pass
        last = (summary.get("attempts") or [{}])[-1]
        frozen = last.get("frozen_path")
        res["summary"] = {
            k: summary.get(k) for k in (
                "stop_reason", "accepted", "refused", "infra_void", "requests_seen",
                "agent_rc", "agent_timed_out", "verdict_hash", "attempts_used",
                "ws_end_sha256")}
        res["summary"]["run_id"] = (summary.get("lifecycle") or {}).get("run_id")
        res["summary"]["count_semantics"] = (summary.get("model_wire") or {}).get(
            "count_semantics")
        att = summary.get("attestation") or {}
        res["summary"]["tier"] = att.get("tier")
        res["summary"]["enclosure_applied"] = (att.get("enclosure") or {}).get("applied")
        res["summary"]["twin_enclosure"] = summary.get("twin_enclosure")
        if enclosed:
            # 圍牆裡的 pi 寫得到 run-dir（twinenclose 誠實邊界 2）⇒ 主機側**當場驗章**，
            # 不信圍牆裡寫出來的 summary。
            from vacant_network.vrun import verify_receipts as vrr
            try:
                res["summary"]["receipt_verdicts"] = [
                    r.get("verdict") for r in vrr.verify_run(rd)]
            except Exception as e:                       # noqa: BLE001
                res["summary"]["receipt_verdicts"] = [f"error:{type(e).__name__}"]
        res["outputs"] = read_outputs(pathlib.Path(frozen) if frozen else None)
        # P10 命盤卡：每一句對步驟紀錄（找不到根據就從卡上拿掉）。沒有命盤就不出卡。
        try:
            _f = fortunelib.load_final(rd) or fortunelib.resolve(job.fortune or {}, {})
            _card = fortunelib.build_card(rd, pathlib.Path(frozen) if frozen else None, _f,
                                           fortunelib.traits_hint(rd))   # 與 twin_agent.sh 的旁註同一把尺
            res["fortune"] = ({**fortunelib.twin_view(_f, _card), "dropped_n": len(_card["dropped"]),
                               "places": _card.get("places") or []} if fortunelib.has_any(_f) else None)
        except Exception as exc:                              # noqa: BLE001 — 命盤卡是加分項，不准拖垮這一跑
            res["fortune"] = None
            res["fortune_error"] = type(exc).__name__
        if job.cfg.gate:
            res["review"] = read_review(rd)
    except (Exception, SystemExit) as exc:               # noqa: BLE001
        res["error"] = type(exc).__name__
        res["error_detail"] = str(exc)[:300]
    res["wall_s"] = round(time.time() - t0, 3)
    return res


def build_twin(res: dict[str, Any], *, model: str,
               fallback: Any) -> dict[str, Any]:
    """worker 結果 → 要封印的 twin。**`engine` 照裁決 §五 的表決定，不看心情。**

    `fallback` 是 `twinlink.fallback_twin`（傳進來避免循環 import）。
    """
    s = res.get("summary") or {}
    o = res.get("outputs") or {}
    run_fields = {
        "twin_id": res.get("twin_id"),
        "run_id": s.get("run_id"), "verdict_hash": s.get("verdict_hash"),
        "stop_reason": s.get("stop_reason"),
        # 🔴 三值：`None` ＝沒有客觀標準、不判。不准壓成 False。
        "accepted": s.get("accepted"),
        "requests_seen": s.get("requests_seen"),
        "count_semantics": s.get("count_semantics"),
        "ws_end_sha256": s.get("ws_end_sha256"),
        "agent_rc": s.get("agent_rc"), "agent_timed_out": s.get("agent_timed_out"),
        "latency_ms": int(float(res.get("wall_s") or 0) * 1000),
        # 收據上簽的級別（量出來的）＋這一跑有沒有進圍牆。只有枚舉與計數。
        "tier": s.get("tier"),
        "enclosed": res.get("enclosed"),
        "enclosure_applied": s.get("enclosure_applied"),
        "door_calls": (s.get("twin_enclosure") or {}).get("door_calls"),
    }
    te = s.get("twin_enclosure") or {}
    why = None
    if res.get("error"):
        why = (res["error"], res.get("error_detail"))
    elif s.get("infra_void"):
        why = (f"infra_void:{s.get('stop_reason')}", str(s.get("infra_void"))[:300])
    elif not isinstance(s.get("requests_seen"), int) or s["requests_seen"] <= 0:
        why = ("no_model_call", "這一跑沒有任何一通模型呼叫經過中介")
    elif not o.get("has_plan"):
        why = ("agent_no_plan", "有模型呼叫，但工作區裡沒有 PLAN.md")
    elif res.get("enclosed") and s.get("receipt_verdicts") != ["OK"]:
        why = ("receipt_unverified",
               f"圍牆裡那一跑的收據主機側驗不過：{s.get('receipt_verdicts')}")
    elif res.get("enclosed") and te.get("door_excess") != 0:
        why = ("door_unreconciled",
               f"門看到 {te.get('door_calls')} 通、收據記 {s.get('requests_seen')} 通"
               " ⇒ 有呼叫沒經過收據那一層（或對不上帳）")
    elif not meets_tier(s.get("tier"), res.get("require_tier")):
        why = ("tier_below_required",
               f"收據級別 {s.get('tier')!r} 低於要求的 {res.get('require_tier')!r}")

    if why is not None:
        out = fallback(None)
        out.update({k: v for k, v in run_fields.items() if v is not None})
        out["engine"] = "fallback_deterministic"
        out["degraded_from"] = f"{ENGINE_PREFIX}:{model}"
        out["degrade_kind"] = str(why[0])[:120]
        out["degrade_reason"] = str(why[1])     # 只進鏈外（可能夾帶 stderr 片段）
        out["n_artifacts"] = len(o.get("artifacts") or [])
        return out

    lines = derive_lines(o.get("decision"), o.get("reason"), o.get("artifacts") or [])
    _fz = res.get("fortune")
    return {
        **({"fortune": {k: _fz.get(k) for k in ("mbti", "mbti_source", "zodiac", "blood",
                                                 "first_line", "title", "lines")}} if _fz else {}),
        **lines,
        "decision": o.get("decision"), "reason": o.get("reason"),
        "artifacts": o.get("artifacts") or [],
        "n_artifacts": len(o.get("artifacts") or []),
        "lines_from": "agent_workspace",
        "engine": f"{ENGINE_PREFIX}:{model}", "model": model,
        **run_fields,
    }


# ---------------------------------------------------------------------------
# 佇列
# ---------------------------------------------------------------------------

class AgentPool:
    """最多並行 N 位分身。**提交與收成都在主執行緒**；worker 只跑 `run_one`。"""

    def __init__(self, parallel: int = DEFAULT_PARALLEL) -> None:
        self.parallel = max(1, int(parallel))
        self._ex = ThreadPoolExecutor(max_workers=self.parallel,
                                      thread_name_prefix="twin-agent")
        self._futs: dict[str, Future] = {}
        self._lock = threading.Lock()

    def in_flight(self) -> set[str]:
        with self._lock:
            return set(self._futs)

    def submit(self, job: Job) -> bool:
        with self._lock:
            if job.sub_id in self._futs:
                return False
            self._futs[job.sub_id] = self._ex.submit(run_one, job)
            return True

    def harvest(self, *, block: bool = False) -> list[dict[str, Any]]:
        """收成跑完的。`block=True` ⇒ 等到佇列清空。"""
        out: list[dict[str, Any]] = []
        while True:
            with self._lock:
                done = [s for s, f in self._futs.items() if f.done()]
                for s in done:
                    f = self._futs.pop(s)
                    try:
                        out.append(f.result())
                    except BaseException as exc:          # noqa: BLE001
                        out.append({"sub_id": s, "twin_id": public_twin_id(s),
                                    "error": type(exc).__name__,
                                    "error_detail": str(exc)[:300],
                                    "summary": None, "outputs": None})
                left = len(self._futs)
            if not block or left == 0:
                return out
            time.sleep(0.2)

    def wait_idle(self, poll_s: float = 0.2) -> None:
        """等到手上的都跑完——**不收成**（收成要交給主執行緒的 `generate` 去封印）。"""
        while True:
            with self._lock:
                if all(f.done() for f in self._futs.values()):
                    return
            time.sleep(poll_s)

    def shutdown(self, wait: bool = True) -> None:
        self._ex.shutdown(wait=wait)


# ---------------------------------------------------------------------------
# 撤回：真的刪 run 產物
# ---------------------------------------------------------------------------

def _tree_size(p: pathlib.Path) -> tuple[int, int]:
    if p.is_file() or p.is_symlink():
        try:
            return 1, p.lstat().st_size
        except OSError:
            return 1, 0
    n = b = 0
    for q in p.rglob("*"):
        if q.is_file() and not q.is_symlink():
            n += 1
            try:
                b += q.stat().st_size
            except OSError:
                pass
    return n, b


def erase_run_artifacts(work_root: pathlib.Path, sub_id: str) -> dict[str, Any]:
    """刪掉這位分身在 run 那一側留下的一切，**只留收據**（誠實邊界 6）。

    回 `{"erased": [...], "kept_hash_only": [...], "problems": [...]}`。
    `erased` 每一項只有**類別名、檔數、位元組數**——這一份會上鏈，不准有內容。
    """
    ws, rd = paths_for(pathlib.Path(work_root), sub_id)
    erased: list[dict[str, Any]] = []
    kept: list[str] = []
    problems: list[str] = []

    def _rm(p: pathlib.Path, label: str) -> None:
        n, b = _tree_size(p)
        try:
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p)
            else:
                p.unlink()
        except OSError as exc:
            problems.append(f"{label}: {type(exc).__name__}")
            return
        if p.exists() or p.is_symlink():
            problems.append(f"{label}: 刪了但還在")
            return
        erased.append({"what": label, "files": n, "bytes": b})

    # 信（W3b）是觀眾資料：先單獨列一筆，再整個工作區刪。工作區與 run-dir（凍結快照）裡都找。
    letters = [ws / "信.md"] + (sorted(rd.rglob("信.md")) if rd.exists() else [])
    for lp in letters:
        if lp.is_file() or lp.is_symlink():
            _rm(lp, "letter")
    if ws.exists():
        _rm(ws, "workspace")
    # 圍牆的門（twinenclose）：門的 journal 也是逐字落盤 ⇒ 有特質原文
    door = pathlib.Path(work_root) / "doors" / slug_for(sub_id)
    if door.exists():
        _rm(door, "door_journal")
    if rd.exists():
        for child in sorted(rd.iterdir()):
            if child.name in KEEP_ON_ERASE and child.is_file():
                kept.append(child.name)
                continue
            _rm(child, child.name)
        # 正控制：run-dir 裡只准剩收據
        left = sorted(c.name for c in rd.iterdir() if c.name not in KEEP_ON_ERASE)
        if left:
            problems.append(f"run-dir 還剩 {len(left)} 項不是收據")
    return {"erased": erased, "kept_hash_only": kept, "problems": problems}


def run_artifacts_present(work_root: pathlib.Path, sub_id: str) -> bool:
    """這位分身在 run 那一側還有**非收據**的東西嗎（撤回後應為 False）。"""
    ws, rd = paths_for(pathlib.Path(work_root), sub_id)
    if ws.exists() or (pathlib.Path(work_root) / "doors" / slug_for(sub_id)).exists():
        return True
    if rd.exists():
        return any(c.name not in KEEP_ON_ERASE for c in rd.iterdir())
    return False


# ---------------------------------------------------------------------------
# 收據帶走（2026-09-26，`decisions/DECISION_20260926_TWIN_POLAROID.md` §五）
# ---------------------------------------------------------------------------

#: 收據鏈一筆的頂層欄位（`logbook.LogEntry.to_json`）。多一個少一個都不發。
RECEIPT_ENTRY_KEYS = frozenset({"stream_id", "branch_id", "seq", "prev_hash", "ts_ms",
                                "type", "payload", "sig"})
RECEIPT_TYPES = frozenset({"ws_attempt", "ws_verdict"})
#: payload 准出現的鍵（`receipts.ATTEMPT_FIELDS`／`VERDICT_FIELDS`＋launcher 簽進去的 extra）。
#: **白名單不是黑名單**：launcher 哪天多簽一個欄位，這裡不認得就整份不發（fail-closed），
#: 要人看過那個欄位是不是只有雜湊與計數再加進來。
RECEIPT_PAYLOAD_KEYS = frozenset({
    "task_id", "arm", "attempt", "gate_round", "ws_sha256", "verdict_sha256",
    "conversation_sha256", "run", "conversation_digest_kind", "requests_seen", "retry",
    "max_attempts", "accepted", "ws_start_sha256", "agent_rc", "stop_reason",
    "argv_sha256", "feedback_delivery", "accepted_is_null", "attempts_used",
    "attestation_sha256", "attested", "canary_fired", "enclosure_applied", "tier",
    "unexplained", "wire_count_semantics", "wire_quiesced", "ws_end_sha256",
})
_RECEIPT_HEX_KEYS = frozenset({
    "ws_sha256", "verdict_sha256", "conversation_sha256", "ws_start_sha256",
    "ws_end_sha256", "argv_sha256", "attestation_sha256"})
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX128_RE = re.compile(r"^[0-9a-f]{128}$")
_ENUM_RE = re.compile(r"^[A-Za-z0-9_.:'\-]{0,40}$")
_TASK_RE = re.compile(r"^twin:tw-[0-9a-f]{12}$")
_B58_RE = re.compile(r"^z[1-9A-HJ-NP-Za-km-z]{20,80}$")
#: 一條分身收據應該只有兩筆（一筆 ws_attempt、一筆 ws_verdict）。給一點餘裕，但不收一本書。
RECEIPT_MAX_ENTRIES = 8


class ReceiptShapeError(ValueError):
    """收據長得不像「只有雜湊與計數」——整份不發。"""


def _check_receipt_value(key: str, v: Any) -> None:
    if key in _RECEIPT_HEX_KEYS:
        if v is not None and not (isinstance(v, str) and _HEX64_RE.match(v)):
            raise ReceiptShapeError(f"{key} 不是 64 位十六進位")
        return
    if key == "task_id":
        if not (isinstance(v, str) and _TASK_RE.match(v)):
            raise ReceiptShapeError("task_id 不是 twin:tw-<12 hex> 別名")
        return
    if v is None or isinstance(v, bool):
        return
    if isinstance(v, int):
        if abs(v) > 2 ** 53:
            raise ReceiptShapeError(f"{key} 的整數超出瀏覽器安全範圍")
        return
    if isinstance(v, str) and _ENUM_RE.match(v):
        return
    raise ReceiptShapeError(f"{key} 的值不是雜湊／計數／短枚舉")


def check_receipt_shape(entries: list[dict[str, Any]], pub: dict[str, Any]) -> None:
    """**只有雜湊與計數**的可執行判準。過不了就 `ReceiptShapeError`。"""
    if not entries or len(entries) > RECEIPT_MAX_ENTRIES:
        raise ReceiptShapeError(f"收據筆數 {len(entries)} 不在 1..{RECEIPT_MAX_ENTRIES}")
    if set(pub) != {"vacant_id", "pub_hex"} or not _HEX64_RE.match(str(pub.get("pub_hex"))) \
            or not _B58_RE.match(str(pub.get("vacant_id"))):
        raise ReceiptShapeError("公鑰檔形狀不對")
    for e in entries:
        if set(e) != RECEIPT_ENTRY_KEYS:
            raise ReceiptShapeError(f"收據一筆的欄位不對：{sorted(set(e) ^ RECEIPT_ENTRY_KEYS)}")
        if e["type"] not in RECEIPT_TYPES:
            raise ReceiptShapeError(f"收據事件別 {e['type']!r} 不在白名單")
        for k in ("stream_id", "prev_hash"):
            if not _HEX64_RE.match(str(e[k])):
                raise ReceiptShapeError(f"{k} 不是 64 位十六進位")
        if not _HEX128_RE.match(str(e["sig"])):
            raise ReceiptShapeError("sig 不是 128 位十六進位")
        if not isinstance(e["branch_id"], str) or not _ENUM_RE.match(e["branch_id"]):
            raise ReceiptShapeError("branch_id 形狀不對")
        for k in ("seq", "ts_ms"):
            if not isinstance(e[k], int) or isinstance(e[k], bool) or not 0 <= e[k] <= 2 ** 53:
                raise ReceiptShapeError(f"{k} 不是安全整數")
        p = e["payload"]
        if not isinstance(p, dict):
            raise ReceiptShapeError("payload 不是物件")
        extra = set(p) - RECEIPT_PAYLOAD_KEYS
        if extra:
            raise ReceiptShapeError(f"payload 有不認得的鍵：{sorted(extra)}")
        for k, v in p.items():
            _check_receipt_value(k, v)


def receipt_bundle(work_root: pathlib.Path, sub_id: str,
                   expect_head: str | None = None) -> dict[str, Any]:
    """這位分身那一跑的收據，打包成可以交給觀眾帶走的一份（**只有雜湊與計數**）。

    回 `{"ok": True, "bundle": {...}}` 或 `{"ok": False, "why": "<類別>"}`（理由只有類別，
    不含任何收據內容——這個回傳值會進 twinlink 的回報）。

    `expect_head` 給了 ⇒ 鏈頭（最後一筆的 hash）必須等於它（拍立得上的收據短碼
    就是它的前 8 碼；對不上就不發，免得觀眾拿到一份跟拍立得不是同一跑的收據）。
    """
    from vacant_network.logbook import LogEntry
    _ws, rd = paths_for(pathlib.Path(work_root), sub_id)
    chain_p = rd / "receipts_RUN-ON.ndjson"
    pub_p = rd / "receipts_RUN-ON.pub.json"
    if not chain_p.is_file() or not pub_p.is_file():
        return {"ok": False, "why": "no_receipt_file"}
    try:
        entries = [json.loads(ln) for ln in chain_p.read_text(encoding="utf-8").splitlines()
                   if ln.strip()]
        pub = json.loads(pub_p.read_text(encoding="utf-8"))
        check_receipt_shape(entries, pub)
        head = LogEntry.from_json(entries[-1]).hash()
    except ReceiptShapeError as exc:
        return {"ok": False, "why": "shape_rejected", "detail": str(exc)[:160]}
    except (OSError, ValueError, KeyError, TypeError):
        return {"ok": False, "why": "unreadable"}
    if expect_head is not None and head != expect_head:
        return {"ok": False, "why": "head_mismatch"}
    return {"ok": True, "bundle": {
        "v": 1, "kind": "vacant.twin.receipt/1",
        "task_id": entries[-1]["payload"].get("task_id"),
        "head": head, "n": len(entries), "pub": pub, "entries": entries,
        "honesty": ("這份收據只有雜湊、計數與固定枚舉，沒有你的原文。"
                    "它證明這一跑的紀錄事後沒有被改過，不證明分身做得好。")}}


def job_for(sub_id: str, card: Any, card_text: Any, cfg: AgentConfig) -> Job | None:
    """主執行緒組 job。特質讀不到（檔案庫沒有、舊庫壞掉）⇒ `None`，呼叫端走退化。"""
    if card in (None, {}, "") and not card_text:
        return None
    return Job(sub_id=sub_id, traits=render_traits(card, card_text), cfg=cfg,
               fortune=fortunelib.normalize(card))


def describe(cfg: AgentConfig) -> dict[str, Any]:
    """落進 generate 回報的那一塊（路徑、並行數、上限）。"""
    return {"work_root": str(cfg.work_root),
            "events_path": str(cfg.events_path) if cfg.events_path else None,
            "parallel": cfg.parallel, "timeout_s": cfg.timeout_s,
            "enclose": cfg.enclose, "require_tier": cfg.require_tier,
            "argv_prefix": [pathlib.Path(a).name for a in cfg.argv_prefix]}


if __name__ == "__main__":      # 只印固定文字，方便人讀
    print(json.dumps({"system_prompt": SYSTEM_PROMPT, "first_message": FIRST_MESSAGE,
                      "caller_prompt": CALLER_PROMPT}, ensure_ascii=False, indent=2))
