#!/usr/bin/env python3
"""H 臂的 V/GT 洩漏動態稽核（跑在 run 的產物上，零模型呼叫）。

規格：`docs/HARNESS_STUDY_2026-09-07.md` §5.8。

**為什麼一定要跑在 rows／calls 上，不能只讀原始碼**：
「程式碼裡沒有 import 隱藏測資」不能證明「沒有 GT 進 prompt」——例如未來有人把
`conform_failure_detail` 的輸出擴充成帶期望值，靜態檢查照樣全綠。這支唯一的
輸入是**實際送出去的文字**（`calls.jsonl` 的 `messages`／`prompt` 全文）。

⚠ **D7：可見測資的內容（args／got／want）在 H 臂是刻意進 worker prompt 的**
  （HARNESS_STUDY §5.8；**本 repo 第一次**——既有的 OFF／CONFORM／OFF5 只送題目敘述）。
  合法性依據：`visible` 測資照設計就是給供應者看的驗收條件
  （LCB 的 assert 訊息三個欄位全部來自 `visible_tests`），
  **只有 `hidden \\ visible`（隱藏測資扣掉可見測資）那一段才是 GT**。
  所以這支稽核的對象逐字是 **`hidden \\ visible`**，不是「有沒有測資進 prompt」
  ——那個問題的答案是「有，而且是設計要的」，
  斷言「visible 沒出現」會**必然失敗**，因為它按設計就在裡面。

三條斷言（任何一條命中 ⇒ 整個 run 作廢，照 SPEC_GAIN §7 落盤並公開，
不得只修不報）：

  1. 送出的文字不含驗收碼專屬識別字（那幾個雙底線名字、`exec(`）
     ⇒ 驗收碼的**原始碼**從來沒有被送給模型，只有 `str(exc)` 被轉發。
     ⚠ 例外只有一個：`harness_arms._RULES` 那句給模型的禁令本身含 `exec(`
       （「Do not call … exec() …」）。掃描前把那個**凍結常數**整段扣掉；
       扣的是逐字相等的那一段，任何別處出現的 `exec(` 照樣會被抓到。
  2. 對該題「隱藏測資 \\ 可見測資」的每一個 case，`repr(args)` 與 `repr(expected)`
     都不出現在任何送出的文字裡。
  3. MBPP+ 的複製跑：另外斷言不含只在隱藏側出現的輸入運算式（同一條規則，
     只是那個題庫的驗收碼形狀不同）。

**誠實邊界**：`repr(expected)` 太短時（`0`、`[]`、`True`）子字串比對必然命中，
那不是洩漏而是量具沒有鑑別力。這支**不**把那種 needle 算成違規，但會**單獨列出
被跳過的數量**（`needles_skipped_trivial`）——跳過的東西要說出來，
不能讓「沒有違規」順手把「沒有檢查」蓋掉。

⚠ **round460e：量具修過一次，改的是量具不是判準**（2026-09-08）。
  R460 冒煙（n=3）跑出 **24 筆 `hidden_case_leak`，全部**的 needle 是 `True`／`False`
  ——來源是**模型自己**在回應裡寫的 `SELFTEST: […] -> True` 那幾行，
  而隱藏測資的 `expected` 剛好也是布林值。四個字的 needle 在自然語言裡必然命中：
  那是量具沒有鑑別力，不是 GT 洩漏。判準因此改成
  「`repr` 落在**凍結的瑣碎字面值集合** `TRIVIAL_NEEDLE_REPRS` 內、
  或長度 < `MIN_NEEDLE_CHARS`（6）⇒ 跳過並單獨計數」。
  ⚠ 這一格放寬了偵測面，所以它必須**同時**有反向牙齒：
  `tests/test_gain_harness_arms.py` 有一條負控——把一個**真的**隱藏 case 的 repr
  塞進送出的文字，仍然必須判 VIOLATION。放寬而沒有負控＝把稽核關掉。

⚠ **round460r：稽核範圍改成 v2——只查 harness 自己寫的文字**（2026-09-11，
  在任何 r460r 資料之前；Fable R5）。v1 把**整段送出文字**當掃描對象，
  於是 R460 六塊共報 90 筆 `hidden_case_leak`／`check_code_identifier`，
  逐筆分類之後**全部**是偽陽性（`DECISION_20260911_R460_FABLE_AUDIT_HARNESS.md` §一）：
  題目原文 54、模型自己的回覆 15（含一筆把 Rules 那行改寫、因此帶著 `exec(`）、
  harness 回饋引述模型自己 SELFTEST 的 12、可見測資失敗訊息的 `want=`／`got=` 回聲 9。
  **量具偽陽性會把真訊號淹掉**：90 筆噪音之下，第 91 筆真的洩漏沒有人看得出來。

  v2 的判準是**這段文字是誰寫的**，逐條：
    (a) **題目原文不查**——`task['prompt']` 逐字扣掉。它六臂共用、與 OFF 相同，
        題目自己提到某個陣列不是 harness 洩漏。
    (b) **assistant 訊息完全不查**——模型自己寫的東西不是 harness 寫進 prompt 的。
        （flattened 線路模式下整段對話被攤平成一則 user 訊息 ⇒ 先依
        `--- REPLY n ---` 標記切回角色再套這一條，見 `split_flattened`。）
    (c) **回饋訊息裡的回聲不算 harness 的話**，三條、各自很窄：
        · `visible_check_source`：needle 逐字在該題 `visible_check` 原始碼裡
          （D7：可見測資照設計就給 worker 看，它不是 `hidden \\ visible`）。
        · `model_own_selftest_same_request`：needle **等於**（不是包含）
          harness 用**自己那支解析器**從同一次請求的模型回覆裡讀出來的
          某個 `SELFTEST` 值——`SELFTEST_SUFFIX` 只是把它原封不動印回去。
        · `got=` 那一格是**沙箱回聲**：它逐字是
          `repr(候選函式(*可見測資的 args))`，harness 沒有任何管道能把隱藏 GT
          放進去；真要從隱藏側取值，變的會是 `args=`／`want=`／`you expected=`，
          **那三格照查**。needle 只出現在 `got=` 段落裡 ⇒ 記成
          `excused_as="got_sandbox_echo"` 並計入 `excused_by_rule`
          （**留證，不是靜音塗抹**——見下面 round460r-2）。
    (d) **凍結的 Rules 那行照舊扣掉**（v1 就有；`exec(` 唯一的合法出處）。
  其餘 harness 自己寫進 system／user 的文字**一律照查**；`system` 訊息
  **一格豁免都不給**（persona 文字沒有回聲的理由——**`got=` 也是一格豁免，
  所以 system 連它都不吃**），而且
  `CODE_NEEDLES`（`__tests`／`__aeq`／`__canon`）**不給 (c) 的豁免**——
  驗收碼原始碼被貼進 user 訊息永遠是紅的，**藏在 `got=` 後面也一樣**。

⚠ **round460r-2：Fable 稽核的三處 must-fix**（2026-09-11，仍在任何 r460r 資料
  之前）。v2 初版把 (c) 的 `got=` 做成「掃描前整段塗掉」，那一個實作細節同時
  踩到三件事，逐條：

  1. **`system` 也被塗了。** 「system 一格豁免都不給」那句在文件裡是對的，
     在程式碼裡不是——`redact_harness_text` 沒有分角色。
     ⇒ 現在 `system` 只吃 (a)＋(d)，`system` 裡的 `got=<隱藏 GT>` 是**紅的**。
  2. **`CODE_NEEDLES` 也被塗了。** `hint: got=x __tests = [...]` 之下整段
     `got=…` 被換成佔位字串，`__tests` 跟著消失 ⇒ 把驗收碼原始碼藏在 `got=`
     後面就能過稽核。`got=` 的合法性論證撐得住**值層級**的 repr
     （那一格逐字是某個函式的回傳值），撐不住 `__tests` 這種**識別字**。
     ⇒ `CODE_NEEDLES` 現在掃的是**只扣掉 (a)＋(d)** 的文字，
     `hidden_case_leak` 才掃扣掉 `got=` 之後的文字。
  3. **豁免被靜音了。** 塗掉之後那一筆連「被豁免過」都沒有紀錄，
     而 §五-3 那張對帳表卻寫著「`got=` 沙箱回聲 1」——那個 1 是**人工**數的，
     機器不吐。⇒ 現在它進 `excused`（帶 `excused_as="got_sandbox_echo"`）
     並計入 `excused_by_rule`，與另外兩條豁免同一個形狀。

  ⚠ **與 Fable 原文的一處明文偏離**：R5 寫的是「the immediately preceding
  assistant message」，那擋不住 HOC 的 14 筆——`SELFTEST` 的來源是**計畫輪**
  的回覆，不是緊鄰的前一則。因此範圍改成「同一次請求裡的任何一則 assistant
  訊息」，但**同時把判準收得比原文更緊**：不是子字串比對，而是「等於 harness
  自己解出來的那個 SELFTEST 值」（見 `model_selftest_reprs` 的 docstring：
  模型寫 `["NS", 1]`、harness 印 `['NS', 1]`，子字串比對本來就會漏）。
  淨效果是**豁免面比 R5 原文小**，理由與逐筆對帳在
  `DECISION_20260911_R460R_FIVE_REPLICATIONS_PREREG.md` §五。

  R460 六塊逐筆對帳（90 筆 v1 命中 → v2 的去向，`--scope v1`／`v2` 各跑一次可重算）：
  題目原文 (a) 54、assistant 訊息 (b) 17、SELFTEST 豁免 14、可見驗收碼豁免 4、
  `got=` 沙箱回聲 1 ⇒ **v2 六塊全 CLEAN、零違規**。
  （round460r-2 之後那個 1 由機器自己吐出來：b1 的
  `excused_by_rule.got_sandbox_echo == 1`。）
  （與 `DECISION_20260911_R460_FABLE_AUDIT_HARNESS.md` §一那份人工分類總數相同、
  分格不同：機械規則對每一筆只記**第一條**適用的排除理由。）

  ⚠ v1 **沒有被刪掉**：`--scope v1` 逐字重現 R460 那 90 筆，
  收官紀錄因此仍然可重跑（`tests/test_r460r_scheduler.py` 對釘兩個 scope 的數字）。

⚠⚠ **round534：v1／v2 從來只掃過 H 臂——那不是設計取捨，是一個洞**（2026-09-18）。
  `audit_run()` 開頭那句 `if arm not in VARIANTS: continue` 把 `OFF`／`OFF5`／
  `CONFORM`／`EQ5`／`ON`／`ONR`／`CALIBRATION` **安靜地**跳過。本模組的標題寫的是
  「H 臂的 V/GT 洩漏動態稽核」，所以那句 filter 在**寫的當下**是自洽的；
  不自洽的是後來拿它的輸出去講**整個 run** 的話。R532 每一塊的 `per_arm` 實測
  都只有 `{'HMIX': N}`，而對外的句子是「43/43 塊 V/GT 紅線 CLEAN」——
  **那句話把「HMIX 這一臂乾淨」講成了「這個 run 乾淨」**。
  方向上這不是中性的：Δ_C ＝ HMIX − CONFORM，沒驗過的是**被減數那一側**；
  CONFORM 若有洩漏會讓它分數偏高 ⇒ Δ_C 更負 ⇒ 與觀察到的方向同向，排除不掉。

  **為什麼會躲這麼久**：跳過是**靜音**的。`per_arm` 只記「掃到的」，
  不記「在檔案裡但沒掃的」，所以輸出裡沒有任何一格會因為少掃一臂而變紅。
  這與 round460e 那次是同一個形狀的錯（「沒有檢查」冒充「沒有違規」），
  只是換了一個維度：那次是 needle 被跳過，這次是**整條臂**被跳過。

  **不是形狀問題**（先查過才改）：古典臂的 `calls.jsonl` 記錄形狀是
  `system` ＋ `prompt`（沒有 `messages`），而 `classify_texts()` 本來就有
  `elif rec.get("prompt")` 那一條分支在接它 ⇒ 分類器**認得**古典臂，
  一格都不用補。實測 179 份 `calls.jsonl` 裡的七個古典臂全部走這個形狀。
  所以修法是「把 filter 放寬」，不是「為古典臂另寫一支解析器」。

  v3 ＝ v2 的判準（誰寫的）＋三件事：
    · **臂的範圍改成 `AUDITED_ARMS`**（七個古典臂＋三個 H 臂）。
    · **`arms_present` 逐臂落盤，並且 fail-closed**：某一臂在 `calls.jsonl` 裡
      有紀錄、卻有 0 筆進稽核 ⇒ verdict 是 `UNVERIFIABLE`**不是** `CLEAN`；
      一筆都沒稽核到（`records_audited == 0`）也是 `UNVERIFIABLE`
      （r530 那條路徑 2026-09-13 就有這一格，`audit_run` 當時漏掉）。
    · 多一條豁免 `model_own_output_quoted`，只為 `ON` 臂而存在：
      `arm_on` 的評審 prompt 逐字嵌入 `initial_code`、修訂 prompt 逐字嵌入
      三份評審全文（`gain_run.arm_on`）。那幾段是**模型自己寫的**，只是被
      harness 引號括起來搬進一則 user 訊息——與 v2 的 (b)「assistant 訊息不查」
      同一個作者歸屬論證，不是新的寬容。判準收得與 SELFTEST 那條一樣緊：
      needle 的**每一次出現**都必須落在某一段「與本 run 稍早某筆同臂同題的
      模型回覆（或其 `extract_code` 結果）逐字相等」的區間之內，才算豁免；
      有任何一次出現在區間之外就是違規。
      ⚠ 這條豁免**對 `CODE_NEEDLES` 也適用**，與 round460r-2 第 2 點的
        `got=` 不同——差別在論證的種類：`got=` 撐的是「值層級」，
        撐不住識別字；這一條撐的是**作者**，而作者論證對識別字一樣成立
        （模型自己寫 `exec(` 不是 harness 洩漏；R460 v1 那 90 筆裡就有一筆
        正是這個）。鏈是閉的：harness 若真的把驗收碼送進模型，**第一次送出**
        那一筆自己會紅，模型之後怎麼回聲都補不回來。
      ⚠ 已知弱點，照 R530 tool 回聲那條逐字沿用：「模型自己算出同一個值」
        與「模型看到了那個值」在字面比對下同形。所以豁免**逐筆留證**
        （`excused`），不是塗掉。
    · v3 對同一題的 needle 先去重再掃（v1／v2 不去重，因為 R460 那 90 筆的
      逐筆數字釘在重複計數上）。`needles_checked`／`needles_unique` 兩個數都印。

  **v1／v2 的臂範圍維持凍結**（只有 H 臂），因為 R460 收官的 90／0 對帳表與
  `tests/test_r460r_scheduler.py` 的 `V1_EXPECTED`／`V2_EXCUSED_BY_RULE` 釘在
  它們身上。兩個 scope 現在照樣吐 `arms_present_not_audited`——
  **舊判準可以凍結，但不准繼續靜音**。

用法（D9：**六塊各跑一次，六塊都要綠才算過**）：
    for b in a1 a2 a3 b1 b2 b3; do
      python3 ops/gain/harness_vgt_audit.py --run runs/g_r460_harness_lcb2_$b --bank lcb2
    done
（`--scope` 預設 **v3**；要重現 R460 收官那兩個數字才給 `--scope v1`／`v2`。）
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.harness_arms import (FLATTEN_HEADER,  # noqa: E402
                                   RULES_NO_CALL_LINE, VARIANTS, _RULES)

#: G 實驗的**古典臂**（`gain_run.KNOWN_ARMS` ＋ `calibrate_pool` 的 CALIBRATION）。
#: 這七個的 `calls.jsonl` 形狀都是 `system` ＋ `prompt`（沒有 `messages`），
#: `classify_texts()` 的 `elif rec.get("prompt")` 那條分支本來就接得住。
#: ⚠ `CALIBRATION` 一定要在裡面：`gain_run.calibrate_pool` 的 `run_one` 是一條
#:   **真的送 prompt 出去**的路徑（`role="calibration"`），它與六個臂共用同一份
#:   `task["prompt"]`，沒有理由不掃。漏掉它就是把同一個洞留一個小號。
CLASSIC_ARMS = ("OFF", "OFF5", "CONFORM", "EQ5", "ON", "ONR", "CALIBRATION")

#: v3 的稽核對象＝古典七臂＋H 三臂。**這份名單是 fail-closed 的分母**：
#: `calls.jsonl` 裡出現了不在這份名單上的臂（例如 R530 的 `A-SOLO`），
#: v3 會判 `UNVERIFIABLE` 而不是安靜跳過——那代表 scope 拿錯了，不是通過。
AUDITED_ARMS = CLASSIC_ARMS + tuple(VARIANTS)

# 驗收碼專屬的識別字。`exec(` 是最弱的一條（凍結常數會撞到，見上面的例外說明），
# 其餘三個只可能來自驗收碼本身。
CODE_NEEDLES = ("__canon", "exec(", "__aeq", "__tests")

# 短到子字串比對沒有鑑別力的 needle 不算違規，但要單獨計數。
# 6：`True`(4)／`False`(5) 是冒煙實測踩到的兩個——模型自己會在回應裡寫
# `SELFTEST: … -> True`，而隱藏 case 的 `expected` 剛好也是布林。
MIN_NEEDLE_CHARS = 6

#: **凍結**的瑣碎字面值集合：這些 repr 在任何一段自然語言／程式碼裡都會出現，
#: 命中它們證明不了任何事。逐字凍結（不是用型別判斷）是為了讓「跳過什麼」
#: 這件事可被逐字稽核——放寬偵測面的那一格必須自己說得出放寬了哪幾個字串。
TRIVIAL_NEEDLE_REPRS = frozenset({
    "True", "False", "None", "0", "1", "-1", "[]", "{}", "()", "''", '""',
})


def is_trivial_needle(needle: str) -> bool:
    """這個 needle 有沒有鑑別力。沒有 ⇒ 跳過並單獨計數，**不算成 CLEAN 的證據**。"""
    return needle in TRIVIAL_NEEDLE_REPRS or len(needle) < MIN_NEEDLE_CHARS


#: 送出文字裡**唯一**允許出現 `exec(` 的地方：給模型的那句禁令（`harness_arms`
#: 的 `RULES_NO_CALL_LINE`，逐字凍結）。掃描前只扣掉這一行與整段 Rules 模板，
#: 別處的 `exec(` 照樣算違規。
FROZEN_SENT_CONSTANTS = (RULES_NO_CALL_LINE, _RULES)


def strip_frozen_constants(text: str) -> str:
    """把 H 臂的凍結 prompt 常數逐字扣掉（相等才扣，不做模糊比對）。"""
    out = text or ""
    for frozen in FROZEN_SENT_CONSTANTS:
        out = out.replace(frozen, "")
    return out


def sent_texts(rec: dict) -> list[str]:
    """一筆 `calls.jsonl` 實際送出去的全部文字（system ＋ 每一則訊息）。

    v1 的掃描對象就是這個列表的每一格。v2 改用 `classify_texts()`
    ——同一批文字，但每一格帶著**角色**，好讓「誰寫的」成為判準。
    """
    return [t for _role, _i, t in classify_texts(rec)]


# ── v2：角色歸屬（誰寫的）────────────────────────────────────────────────
#
# round530（2026-09-13）：多一個 `r530`。它**不是 v2 的參數版本**，是另一種
# 實驗形狀的稽核（多輪工作區對話、needle 來源是 `hidden/` 目錄的字面值、
# 多一個 `tool` role、多一個工作區檔案掃描）——所以走 `audit_run_r530()`
# 這條獨立的路徑，`audit_run()` 的 v1／v2 行為**一個字都沒動**。
AUDIT_SCOPES = ("v1", "v2", "v3", "r530")


def scope_arms(scope: str) -> tuple[str, ...]:
    """這個 scope 掃哪幾條臂。**v1／v2 只掃 H 臂是凍結的歷史，不是完整稽核。**

    v1／v2 的臂範圍不准動：R460 收官那 90／0 的逐筆對帳表釘在它們身上
    （`tests/test_r460r_scheduler.py`）。要完整稽核就用 v3。
    """
    return AUDITED_ARMS if scope == "v3" else tuple(VARIANTS)

#: R530 的工具結果表頭。**這是 `ops/gain/r530/openwork_arms.TOOL_RESULT_HEADER`
#: 的副本**——這裡不 import 那支（它 import 時會跑 KS-1 與 prompt 同一性斷言，
#: 而稽核腳本不該為了認一個字串去載入整條發射路徑）。
#: 兩邊漂掉由 `tests/test_r530_vgt.py::test_tool_header_matches` 抓。
#:
#: 它承重什麼：端點的 chat API **只收 user／assistant**
#: （`brain_cline.chat` 的參數檢查），所以工具結果只能以 user 訊息回灌。
#: 不靠這個表頭把它認回 `tool`，Fable 裁決的「role=tool 的輸出也掃」
#: 就沒有可以掃的東西——它會被當成 harness 自己寫的 user 文字。
R530_TOOL_HEADER = "TOOL RESULT (bash). This is machine output, not a person."

#: flattened 線路模式的段落標記（`harness_arms.flatten_messages` 逐字產生）。
#: `REQUEST n`／`CURRENT REQUEST` ＝ user、`REPLY n` ＝ assistant。
_FLAT_SECTION_RE = re.compile(r"^--- (CURRENT REQUEST|REQUEST \d+|REPLY \d+) ---$",
                              re.MULTILINE)


def split_flattened(text: str) -> list[tuple[str, str]] | None:
    """攤平成一則 user 訊息的對話 → `[(role, text), …]`；不是攤平格式回 None。

    ⚠ 為什麼一定要做這件事：flattened 之下**整段對話**（含模型自己的回覆）
    被包進一則 `role="user"` 的訊息裡。不還原角色的話，v2 的 (b)
    「assistant 訊息不查」會整條失效——模型寫的東西會被當成 harness 寫的。
    R460 六塊全是 multiturn（G6），所以這段在 R460 上不改變任何數字；
    它擋的是**下一次**線路退回攤平模式時量具安靜地變回 v1。
    """
    if not (text or "").startswith(FLATTEN_HEADER):
        return None
    labels = _FLAT_SECTION_RE.findall(text)
    parts = _FLAT_SECTION_RE.split(text)
    if not labels:
        return None
    out: list[tuple[str, str]] = []
    # parts = [header, label1, body1, label2, body2, …]
    for i, label in enumerate(labels):
        body = parts[2 * i + 2] if 2 * i + 2 < len(parts) else ""
        out.append(("assistant" if label.startswith("REPLY") else "user", body))
    return out


def classify_texts(rec: dict) -> list[tuple[str, int, str]]:
    """一筆 `calls.jsonl` 送出的文字，逐格帶上角色。

    回 `[(role, message_index, text), …]`，`role ∈ {"system","user","assistant"}`。
    `message_index` 與 v1 的編號**逐格相同**（system 佔 0），
    好讓 v1／v2 的違規清單可以逐筆對照。
    攤平的那一則另外展開成多格，`message_index` 沿用那一則的編號。
    """
    out: list[tuple[str, int, str]] = []
    idx = 0
    if rec.get("system"):
        out.append(("system", idx, rec["system"]))
        idx += 1
    msgs = rec.get("messages")
    if isinstance(msgs, list) and msgs:
        for m in msgs:
            if not isinstance(m, dict):
                continue
            content = m.get("content", "")
            role = m.get("role") or "user"
            flat = split_flattened(content) if role == "user" else None
            if flat:
                out += [(r, idx, t) for r, t in flat if t]
            elif content:
                out.append((role, idx, content))
            idx += 1
    elif rec.get("prompt"):
        out.append(("user", idx, rec["prompt"]))
    return [(r, i, t) for r, i, t in out if t]


#: 沙箱回聲欄位：`got=` 之後、到下一個**凍結**欄位名（或行尾）之前的那一段。
#: 兩個來源逐字都是凍結模板：
#:   `vacant/codebench.py::_lcb_check_code` 的
#:     f"args={…!r} got={__got!r} want={…!r}"        ← 可見測資的 assert 訊息
#:   `harness_arms.SELFTEST_SUFFIX` 的
#:     "args={args!r} got={got} you expected={expected!r}"
#: `got` 逐字是 `repr(候選函式(*可見測資的 args))` ⇒ 它是**模型自己程式的輸出**，
#: harness 沒有任何管道把隱藏 GT 送進這一格；真要從隱藏側取值，
#: 變的會是 `args=`／`want=`／`you expected=`，而那三格**照查**。
_GOT_ECHO_RE = re.compile(r"got=.*?(?= want=| you expected=|\n|$)", re.DOTALL)
GOT_ECHO_PLACEHOLDER = "got=<sandbox-echo>"

#: `got=` 豁免的名字。它**不是**一種塗抹，是一筆**留證**的豁免：
#: needle 只出現在 `got=` 那一段裡 ⇒ 記成 `excused_as="got_sandbox_echo"`
#: 並計入 `excused_by_rule`。（round460r-2：v2 初版是「掃描前扣掉」，
#: 那等於把豁免做成靜音——「豁免了什麼」跟「違規了什麼」一樣是稽核證據。）
GOT_ECHO_EXCUSE = "got_sandbox_echo"

#: 三條豁免規則的名字，`excused_by_rule` 的鍵**逐字**是這個 tuple。
EXCUSE_RULES = ("visible_check_source", "model_own_selftest_same_request",
                GOT_ECHO_EXCUSE)

#: round534 的第四條豁免，**只在 v3 存在**（v1／v2 的 `excused_by_rule` 鍵不准多一個，
#: 否則 `ops/gain/replay/r460/vgt_v2_*.json` 那份落盤證據會對不上）。
MODEL_QUOTE_EXCUSE = "model_own_output_quoted"

#: v3 的豁免名單＝v2 三條＋作者歸屬那一條。
V3_EXCUSE_RULES = EXCUSE_RULES + (MODEL_QUOTE_EXCUSE,)


def quoted_spans(hay: str, quotes: tuple[str, ...]) -> list[tuple[int, int]]:
    """`hay` 裡每一段**與某則模型回覆逐字相等**的區間 `[start, end)`。

    這是 `MODEL_QUOTE_EXCUSE` 的機械判準。`gain_run.arm_on` 把
    `initial_code`（＝某次回覆的 `extract_code`）與三份評審全文原封不動嵌進
    自己寫的 user 訊息裡；那幾段的作者是模型不是 harness，與 v2 的 (b)
    「assistant 訊息不查」是同一條規則，只是文字搬了家。

    ⚠ 為什麼用**區間**不用「掃描前 replace 掉」：replace 會把區間邊界上的
      字接起來，可能憑空造出或抹掉一個 needle 命中
      （round460r-2 第 3 點的教訓是「豁免不准靜音」，這裡再加一條
      「豁免不准改動被掃的文字」）。區間包含關係是可逐筆覆核的。
    """
    spans: list[tuple[int, int]] = []
    for q in quotes:
        if not q:
            continue
        start = hay.find(q)
        while start != -1:
            spans.append((start, start + len(q)))
            start = hay.find(q, start + 1)
    return spans


def needle_only_inside_quotes(hay: str, needle: str,
                              spans: list[tuple[int, int]]) -> bool:
    """needle 的**每一次**出現都被某個引文區間完整包住 ⇒ 可以豁免。

    「每一次」是刻意的：只要有一次出現在引文之外，那一次就是 harness 自己寫的，
    整筆判違規。這與 `model_own_selftest_same_request` 用相等而不用子字串
    是同一個收緊方向——豁免面要小於它的論證所能撐住的範圍。
    """
    if not spans:
        return False
    pos = hay.find(needle)
    if pos == -1:
        return False
    while pos != -1:
        end = pos + len(needle)
        if not any(s <= pos and end <= e for s, e in spans):
            return False
        pos = hay.find(needle, pos + 1)
    return True


def model_quotes_of(rec: dict) -> list[str]:
    """一筆 `calls.jsonl` 紀錄裡**模型寫的**那些文字（回覆全文＋其中的程式碼）。

    供 `quoted_spans` 當引文來源。兩者都收：`arm_on` 的修訂 prompt 嵌的是
    評審**全文**，評審 prompt 嵌的是 `extract_code(回覆)`。
    `extract_code` 從 `gain_run` 現場 import（模組層 import 會循環）——
    **一定要是同一支**，自己重寫一個 fence 解析器就會與被稽核的那條路徑漂掉。
    """
    from ops.gain.gain_run import extract_code
    out: list[str] = []
    resp = rec.get("response")
    if isinstance(resp, str) and resp:
        out.append(resp)
        code = extract_code(resp)
        if code and code != resp:
            out.append(code)
    msgs = rec.get("messages")
    if isinstance(msgs, list):
        for m in msgs:
            if isinstance(m, dict) and m.get("role") == "assistant":
                c = m.get("content")
                if isinstance(c, str) and c:
                    out.append(c)
    return out


def strip_not_harness_written(text: str, task: dict | None) -> str:
    """(d) 凍結 Rules → (a) 題目原文。**沒有** `got=` 那一格。

    這是 `CODE_NEEDLES` 的掃描對象：(a)／(d) 扣的是**逐字相等**的整段，
    扣完剩下的每一個字都是 harness 自己寫的。`got=` 不在這裡，理由見
    `redact_harness_text` 的 ⚠。
    """
    out = strip_frozen_constants(text)                      # (d)
    prompt = (task or {}).get("prompt")
    if prompt:
        out = out.replace(prompt, " ")                      # (a)
    return out


def redact_got_echo(text: str) -> str:
    """把 `got=` 那一段換成佔位字串（＝沙箱回聲不算 harness 的話）。"""
    return _GOT_ECHO_RE.sub(GOT_ECHO_PLACEHOLDER, text)


def redact_harness_text(text: str, task: dict | None, *, role: str = "user") -> str:
    """v2：把**不是 harness 寫的**那幾段從一格 harness 文字裡扣掉再掃。

    順序固定：(d) 凍結 Rules → (a) 題目原文 → (c) `got=` 沙箱回聲。
    扣掉的都是**逐字相等**的段落，不做模糊比對。

    ⚠ **round460r-2 的兩處修正**（Fable 稽核的 must-fix，仍在任何 r460r 資料之前）：

    1. **`system` 訊息不吃 `got=` 那一格。** 只有 (a)＋(d) 適用。
       理由逐字是 §五-1 已經寫著的那句「`system` 訊息一格豁免都不給」——
       而 `got=` 是一格豁免。persona 文字沒有沙箱回聲的理由，
       所以 system 裡出現 `got=<隱藏 GT>` 必須是紅的，不是被塗掉。
    2. **`CODE_NEEDLES` 不吃 `got=` 那一格**（見 `strip_not_harness_written`）。
       否則 `hint: got=x __tests = [...]` 會被整段塗掉 ⇒ 把驗收碼原始碼藏在
       `got=` 後面就能過稽核。`got=` 的合法性論證是「那一格逐字是
       `repr(候選函式(*可見測資的 args))`」，那個論證撐得住
       **隱藏 case 的 repr**（值層級），撐不住**驗收碼識別字**
       （`__tests` 不是任何函式的回傳值）。
    """
    out = strip_not_harness_written(text, task)
    return out if role == "system" else redact_got_echo(out)


def model_selftest_reprs(assistant_texts: list[str]) -> set[str]:
    """同一次請求裡，模型自己那幾行 `SELFTEST:` 被 harness 解出來的 repr 集合。

    ⚠ 為什麼不是「needle 有沒有逐字出現在 assistant 訊息裡」：模型寫的是
    `SELFTEST: ["NS", 1] -> 2`（雙引號），而 `SELFTEST_SUFFIX` 印的是
    `args={args!r}` ＝ `['NS', 1]`（單引號）——**同一個值、不同寫法**，
    逐字子字串比對會漏掉它（R460 b2 實測 2 筆）。
    所以這裡走**與 harness 完全相同的那一支解析器**（`harness_arms.parse_selftests`）
    再 `repr()`：豁免的判準逐字是「這個值就是 harness 從模型自己的回覆裡讀出來、
    原封不動印回去的那一個」，不是「長得像」。
    範圍窄：只解 `SELFTEST:` 那個凍結格式，**同一次請求**之內；
    HPI／HMIX 沒有計畫輪 ⇒ 這個集合是空的 ⇒ 它們一格豁免都拿不到。
    """
    from ops.gain.harness_arms import parse_selftests
    out: set[str] = set()
    for text in assistant_texts:
        cases, _bad = parse_selftests(text)
        for args, expected in cases:
            out.add(repr(args))
            out.add(repr(expected))
            for a in (args if isinstance(args, list) else []):
                out.add(repr(a))
    return out


def needle_excuse(needle: str, task: dict, selftest_reprs: set[str]) -> str | None:
    """(c) 的兩條豁免；沒有豁免回 None（＝這一筆是真的違規）。

    1. `visible_check_source`：needle 逐字在該題可見驗收碼裡
       ⇒ D7 說可見測資本來就給 worker 看，它不是 `hidden \\ visible`。
       （會走到這裡是因為 needle 是**欄位層級**的 repr：某個隱藏 case 的
       `expected` 可以剛好等於某個可見 case 的 `expected`，而整個 case 不同。）
    2. `model_own_selftest_same_request`：needle 恰好等於 harness 從**同一次請求**
       的模型回覆裡解出來的某個 `SELFTEST` 值 ⇒ 那個值是模型自己算的，
       harness 只是原封不動印回去（`SELFTEST_SUFFIX`）。
       ⚠ 判準是**相等**不是子字串：`'[1, 2]' in '[1, 2, 3]'` 為真，
       用子字串會讓「模型寫過一個大陣列」順手豁免掉它的每一段。
    """
    if needle in (task.get("visible_check") or {}).get("code", ""):
        return "visible_check_source"
    if needle in selftest_reprs:
        return "model_own_selftest_same_request"
    return None


def lcb_cases(check_code: str) -> list[dict] | None:
    """LCB 形狀：`__tests = <list literal>`。認不出來回 None（**不猜**）。"""
    try:
        tree = ast.parse(check_code)
    except SyntaxError:
        return None
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "__tests"):
            try:
                tests = ast.literal_eval(node.value)
            except (ValueError, SyntaxError, TypeError):
                return None
            return tests if isinstance(tests, list) else None
    return None


def mbpp_inputs(check_code: str) -> list[str] | None:
    """MBPP+ 形狀：尾端一串 `assert __aeq(entry(*<expr>), …)`；回 `<expr>` 的原始碼。"""
    try:
        tree = ast.parse(check_code)
    except SyntaxError:
        return None
    exprs: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assert):
            continue
        for call in ast.walk(node.test):
            if isinstance(call, ast.Call):
                for arg in call.args:
                    if isinstance(arg, ast.Starred):
                        exprs.append(ast.unparse(arg.value))
    return exprs or None


def hidden_only_needles(task: dict) -> tuple[list[str], list[str]]:
    """回 `(needles, skipped)`：只在隱藏側出現的 case 的 repr。"""
    vis_code = task["visible_check"]["code"]
    hid_code = task["hidden_check"]["code"]
    needles: list[str] = []
    skipped: list[str] = []

    vis_cases, hid_cases = lcb_cases(vis_code), lcb_cases(hid_code)
    if vis_cases is not None and hid_cases is not None:
        vis_repr = {repr(c) for c in vis_cases}
        for case in hid_cases:
            if repr(case) in vis_repr:
                continue
            for key in ("args", "expected"):
                if key not in case:
                    continue
                needle = repr(case[key])
                (skipped if is_trivial_needle(needle) else needles).append(needle)
        return needles, skipped

    vis_in, hid_in = mbpp_inputs(vis_code), mbpp_inputs(hid_code)
    if vis_in is not None and hid_in is not None:
        seen = set(vis_in)
        for expr in hid_in:
            if expr in seen:
                continue
            seen.add(expr)
            for needle in {expr, _literal_repr(expr)} - {None}:
                (skipped if is_trivial_needle(needle) else needles).append(needle)
        return needles, skipped

    raise SystemExit(f"認不出驗收碼形狀：{task['task_id']}——認不出來不是通過，是沒接上。停。")


def _literal_repr(expr: str) -> str | None:
    try:
        return repr(ast.literal_eval(expr))
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None


# ══ round530：第三種 dialect ＋ 多輪工作區的稽核 ════════════════════════
#
# 既有的兩種 dialect（`lcb`／`mbpp`）認的是**驗收碼裡的一個資料結構**
# （`__tests = [...]`／尾端一串 `assert __aeq(entry(*<expr>), …)`）。
# R530 的隱藏驗收是**手寫的 Python 測試檔**，沒有那個資料結構，
# 所以 `hidden_only_needles()` 會撞它自己的 `SystemExit`（那是對的：
# 認不出形狀不是通過）。這裡加的是第三種讀法。

def python_literals(source: str) -> set[str]:
    """一份 Python 原始碼裡所有**字面值**的 repr 集合。

    收的是 `ast.literal_eval` 收得下的東西：常數、以及整個都由常數組成的
    list／tuple／dict／set。函式名、變數名、屬性名一概不收——那些是程式的
    骨架不是測資，把它們當 needle 會讓「模型寫了一個叫 `check_` 的函式」
    變成一筆洩漏。

    ⚠ **認不出來就丟 SyntaxError 給呼叫端**（fail-closed）。
      一個 parse 不動的隱藏驗收檔代表題庫壞了，不是「這一題沒有 needle」。
    """
    tree = ast.parse(source)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
            try:
                out.add(repr(ast.literal_eval(node)))
            except (ValueError, SyntaxError, TypeError,
                    MemoryError, RecursionError):
                pass
        elif isinstance(node, ast.Constant) and isinstance(
                node.value, (str, int, float, bool, bytes)):
            out.add(repr(node.value))
    return out


def r530_hidden_needles(task: dict) -> tuple[list[str], list[str]]:
    """R530：`hidden \\ visible` 的字面值。回 `(needles, skipped)`。

    ⚠ **扣掉 visible 是 D7 在 R530 的對應物**：可見驗收就在工作區裡，
      worker 讀得到、跑得到（§八-5），它不是 GT。GT 逐字是
      **只出現在隱藏側**的那些字面值。
    ⚠ 一併扣掉 `goal.md`／`contract.md` 裡出現過的字面值：契約裡寫著
      `line <N>: <reason>` 或 `float("inf")`，那是題目告訴 worker 的東西。
    """
    hid_dir = pathlib.Path(task["hidden_dir"])
    vis_dir = pathlib.Path(task["visible_dir"])
    hidden_lits: set[str] = set()
    visible_lits: set[str] = set()
    hid_files = sorted(hid_dir.glob("test_*.py"))
    vis_files = sorted(vis_dir.glob("test_*.py"))
    if not hid_files:
        raise SystemExit(
            f"認不出隱藏驗收形狀：{task['task_id']} 的 {hid_dir} 裡沒有 "
            "test_*.py——認不出來不是通過，是沒接上。停。")
    for p in hid_files:
        hidden_lits |= python_literals(p.read_text(encoding="utf-8"))
    for p in vis_files:
        visible_lits |= python_literals(p.read_text(encoding="utf-8"))
    prose = " ".join(
        (task.get("goal") or "", task.get("contract") or ""))
    needles: list[str] = []
    skipped: list[str] = []
    for lit in sorted(hidden_lits - visible_lits):
        if is_trivial_needle(lit):
            skipped.append(lit)
            continue
        # 題目自己寫過的字面值不是 GT——它是契約。
        if lit.strip("'\"") and lit.strip("'\"") in prose:
            skipped.append(lit)
            continue
        needles.append(lit)
    return needles, skipped


def classify_texts_r530(rec: dict) -> list[tuple[str, int, str]]:
    """R530 版的角色歸屬：多一個 `tool`。

    端點只收 user／assistant，工具結果以 user 訊息回灌，開頭是凍結的
    `R530_TOOL_HEADER`。看到那個表頭就歸成 `tool`——Fable 裁決的
    「role=tool 的輸出也掃」指的就是這一批文字。
    """
    out: list[tuple[str, int, str]] = []
    for role, idx, text in classify_texts(rec):
        if role == "user" and text.startswith(R530_TOOL_HEADER):
            out.append(("tool", idx, text))
        else:
            out.append((role, idx, text))
    return out


#: R530 專屬的豁免名字。三條，形狀與 v2 的 `EXCUSE_RULES` 相同
#: （留證不靜音：被豁免的命中逐筆進 `excused`，不是塗掉）。
R530_TOOL_ECHO = "tool_output_echo"
R530_TASK_PROSE = "task_prose"
R530_EXCUSE_RULES = (R530_TOOL_ECHO, R530_TASK_PROSE)


def audit_run_r530(run_dir: pathlib.Path, tasks: dict[str, dict]) -> dict:
    """R530 的 V/GT 動態稽核。`violations` 非空 ⇒ 整個 run 作廢。

    四件事，逐條對應預註冊 §五-3：

    1. **結構性保證**：`ws/*.tar.gz`（每一次嘗試的工作區封存）裡**不准**出現
       隱藏驗收的檔名。這一條是硬的——命中就是 `violation`，因為隱藏驗收
       進了工作區代表整個隔離設計失效，不是「可能是巧合」。
    2. **掃四種 role 的文字**（`system`／`user`／`assistant`／`tool`）找
       `hidden \\ visible` 的 needle。
       · `system`／`user` 命中 ⇒ **violation**（那是 harness 寫的字）。
       · `assistant` 命中 ⇒ 模型自己寫的，不查（v2 的 (b) 逐字沿用）。
       · `tool` 命中 ⇒ **記錄不判定**（`excused_as="tool_output_echo"`）。
         理由與 v2 的 `got=` 沙箱回聲同型但更強：工具輸出逐字是**模型自己
         寫的程式**在一個**結構上沒有隱藏驗收**的工作區裡跑出來的東西，
         harness 沒有任何管道把 GT 放進去。
         ⚠ **這是已知的量具弱點不是漏洞被補起來了**：「它自己想到同一個
           邊界情況」與「它看到了」在字面比對下同形。所以逐筆列出來讓人看。
    3. **掃工作區結束狀態的所有檔案內容**（`ws_needle_hits`）——同樣是
       **記錄不判定**，理由同上。
    4. **`DENY` 第三條的命中計數**（`deny_hidden_read_n`）。
       任一次命中 ⇒ 逐案人工看過才准結算（這支不自己判，只把數字吐出來）。
    """
    import tarfile

    calls_path = run_dir / "calls.jsonl"
    if not calls_path.exists():
        raise SystemExit(f"{calls_path} 不存在——沒有 calls 就沒有稽核對象。停。")
    r530_arms = ("A-SOLO", "A-CONF", "A-GATE")
    violations: list[dict] = []
    excused: list[dict] = []
    ws_hits: list[dict] = []
    per_arm: dict[str, int] = {}
    per_role: dict[str, int] = {}
    n_records = n_texts = n_checked = n_skipped = 0
    deny_hidden_read_n = 0
    deny_counts: dict[str, int] = {}
    cache: dict[str, tuple[list[str], list[str]]] = {}
    unknown_tasks: set[str] = set()

    with calls_path.open(encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            rec = json.loads(line)
            if rec.get("kind") == "tool":
                tag = rec.get("deny_tag")
                if rec.get("blocked") and tag:
                    deny_counts[tag] = deny_counts.get(tag, 0) + 1
                    if tag == "r530_hidden_read":
                        deny_hidden_read_n += 1
                continue
            meta = rec.get("meta") or {}
            arm = meta.get("arm")
            if arm not in r530_arms:
                continue
            n_records += 1
            per_arm[arm] = per_arm.get(arm, 0) + 1
            task_id = meta.get("task_id")
            task = tasks.get(task_id)
            classified = classify_texts_r530(rec)
            n_texts += len(classified)
            for role, _i, _t in classified:
                per_role[role] = per_role.get(role, 0) + 1
            if task is None:
                unknown_tasks.add(str(task_id))
                continue
            if task_id not in cache:
                cache[task_id] = r530_hidden_needles(task)
            needles, skipped = cache[task_id]
            n_checked += len(needles)
            n_skipped += len(skipped)
            for role, i, text in classified:
                if role == "assistant":
                    continue                    # (b) 模型自己寫的不查
                hay = strip_not_harness_written(text, task)
                for needle in needles:
                    if needle not in hay:
                        continue
                    hit = {"line": ln, "arm": arm, "rule": "hidden_literal_leak",
                           "needle": needle, "message_index": i, "role": role,
                           "task_id": task_id,
                           "excerpt": hay[max(0, hay.find(needle) - 80):
                                          hay.find(needle) + 80]}
                    if role == "tool":
                        hit["excused_as"] = R530_TOOL_ECHO
                        excused.append(hit)
                    else:
                        violations.append(hit)

    # ── 工作區封存：結構性保證 ＋ 檔案內容掃描 ──────────────────────────
    ws_dir = run_dir / "ws"
    archives = sorted(ws_dir.glob("*.tar.gz")) if ws_dir.is_dir() else []
    for arc in archives:
        try:
            with tarfile.open(arc, "r:gz") as tf:
                members = tf.getmembers()
                for m in members:
                    low = m.name.lower()
                    if "hidden" in low or "rubric" in low:
                        violations.append({
                            "rule": "hidden_file_in_workspace",
                            "archive": arc.name, "member": m.name})
                task_id = arc.name.split("__")[0]
                task = tasks.get(task_id)
                if task is None:
                    continue
                if task_id not in cache:
                    cache[task_id] = r530_hidden_needles(task)
                needles, _skipped = cache[task_id]
                for m in members:
                    if not m.isfile() or m.size > 512 * 1024:
                        continue
                    fh = tf.extractfile(m)
                    if fh is None:
                        continue
                    try:
                        body = fh.read().decode("utf-8", "replace")
                    except Exception:                        # noqa: BLE001
                        continue
                    for needle in needles:
                        if needle in body:
                            ws_hits.append({
                                "rule": "workspace_needle_hit",
                                "archive": arc.name, "member": m.name,
                                "needle": needle, "task_id": task_id})
        except tarfile.TarError as e:
            violations.append({"rule": "workspace_archive_unreadable",
                               "archive": arc.name, "error": repr(e)})

    # ⚠ **一筆都沒稽核到不是 CLEAN**。R460 的 round460e 已經踩過同一形狀的坑
    #   （放寬偵測面而沒有反向牙齒＝把稽核關掉）。這裡的版本是：
    #   `calls.jsonl` 裡一筆 R530 的模型呼叫都找不到，代表量具沒接上
    #   （後端沒落盤、arm 名字對不上、run 目錄拿錯），
    #   而那個狀態印出 "CLEAN" 會讓「沒有檢查」冒充「沒有違規」。
    structural = [v for v in violations
                  if v.get("rule") in ("hidden_file_in_workspace",
                                       "workspace_archive_unreadable")]
    if n_records == 0:
        verdict = "UNVERIFIABLE"
    elif violations or unknown_tasks:
        verdict = "VIOLATION"
    else:
        verdict = "CLEAN"
    return {
        "run": str(run_dir), "scope": "r530",
        "records_audited": n_records, "texts_audited": n_texts,
        "structural_violations_n": len(structural),
        "per_arm": per_arm, "per_role": per_role,
        "needles_checked": n_checked,
        "needles_skipped_trivial": n_skipped,
        "archives_scanned": len(archives),
        "excused_n": len(excused), "excused": excused,
        "excused_by_rule": {
            k: sum(1 for e in excused if e.get("excused_as") == k)
            for k in R530_EXCUSE_RULES},
        # 記錄不判定的那兩批，**逐筆留著**（§五-3 第 3 項）。
        "workspace_needle_hits_n": len(ws_hits),
        "workspace_needle_hits": ws_hits[:200],
        "deny_counts": deny_counts,
        "deny_hidden_read_n": deny_hidden_read_n,
        "unknown_task_ids": sorted(unknown_tasks),
        "violations": violations,
        "verdict": verdict,
        "honest_bounds": [
            "`records_audited == 0` ⇒ verdict 是 `UNVERIFIABLE` 不是 `CLEAN`："
            "一筆都沒稽核到代表量具沒接上，不代表沒有洩漏。",
            "`tool` role 與工作區檔案的命中是**記錄不判定**：「它自己想到同一個"
            "邊界情況」與「它看到了」在字面比對下同形。這是已知的量具弱點，"
            "不是漏洞被補起來了（§五-3 第 3 項）。",
            "`deny_hidden_read_n > 0` 時要逐案人工看過才准結算——這支只吐數字，"
            "不自己判（§五-3 第 4 項）。",
            "扣掉 visible 與題目原文之後剩下的才是 needle；扣掉的東西"
            "逐筆計進 `needles_skipped_trivial`，不能讓「沒有違規」順手把"
            "「沒有檢查」蓋掉。",
        ],
    }


def audit_run(run_dir: pathlib.Path, tasks: dict[str, dict], *,
              scope: str = "v3") -> dict:
    """回一份可落盤的稽核結果；`violations` 非空 ⇒ 整個 run 作廢。

    `scope="v1"` ＝ round460e 的讀法（整段送出文字都掃）——留著只為了讓
    R460 收官那 90 筆逐字可重跑。`scope="v2"` ＝ round460r 的判準
    （只掃 harness 自己寫的 system／user 文字），**臂的範圍凍結在 H 三臂**。
    `scope="v3"`（預設，round534）＝同一個判準擴到 `AUDITED_ARMS` 十條臂，
    加上逐臂 fail-closed 與 `model_own_output_quoted` 豁免；見模組 docstring。

    ⚠ **預設從 v2 改成 v3 是刻意的**：預設值必須是完整稽核。要凍結的舊數字
      得**明寫** `scope="v1"`／`"v2"`，不能靠「忘了給參數」拿到一份只掃一臂的
      綠燈——那正是 round534 這個洞能存在的條件。
    """
    if scope not in AUDIT_SCOPES:
        raise SystemExit(f"unknown audit scope: {scope}（可用 {list(AUDIT_SCOPES)}）")
    calls_path = run_dir / "calls.jsonl"
    if not calls_path.exists():
        raise SystemExit(f"{calls_path} 不存在——沒有 calls 就沒有稽核對象。停。")
    arms_in_scope = scope_arms(scope)
    violations: list[dict] = []
    excused: list[dict] = []
    n_records = n_texts = n_skipped = n_checked = n_texts_scanned = 0
    n_unique = 0
    cache: dict[str, tuple[list[str], list[str]]] = {}
    unknown_tasks: set[str] = set()
    per_arm: dict[str, int] = {}
    #: 檔案裡**出現過**的每一條臂（不管有沒有被掃）。fail-closed 的分母。
    arms_present: dict[str, int] = {}
    #: 逐 (arm, task_id) 累積、**只往前看**的模型回覆，供
    #: `MODEL_QUOTE_EXCUSE` 當引文來源。只收本筆之前已經落盤的回覆：
    #: 引用必然晚於被引用者，這一條讓豁免面比「整個 run 的回覆」更小。
    model_quotes: dict[tuple[str, str], list[str]] = {}
    with calls_path.open(encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            rec = json.loads(line)
            arm = (rec.get("meta") or {}).get("arm")
            if arm:
                arms_present[arm] = arms_present.get(arm, 0) + 1
            if arm not in arms_in_scope:
                continue
            n_records += 1
            per_arm[arm] = per_arm.get(arm, 0) + 1
            task_id = (rec.get("meta") or {}).get("task_id")
            task = tasks.get(task_id)
            classified = classify_texts(rec)
            n_texts += len(classified)
            # (b) assistant 訊息完全不查——但先留一份，(c) 的豁免要用它。
            assistant_texts = [t for role, _i, t in classified if role == "assistant"]
            selftest_reprs = (model_selftest_reprs(assistant_texts)
                              if scope in ("v2", "v3") else set())
            quotes = (tuple(model_quotes.get((arm, str(task_id)), ()))
                      if scope == "v3" else ())
            # 每一格帶三份文字：
            #   raw  ＝ 原文（v1 的掃描對象）
            #   base ＝ (a)＋(d) 扣掉、**沒有** got= 塗抹 ⇒ `CODE_NEEDLES` 掃這份
            #   full ＝ base 再扣掉 got=（`system` 除外）⇒ `hidden_case_leak` 掃這份
            # 兩份分開是 round460r-2 的修正之一：把驗收碼識別字藏在 `got=` 後面
            # 不准變成通過。
            if scope == "v1":
                targets = [(role, i, t, t, t) for role, i, t in classified]
            else:
                targets = []
                for role, i, t in classified:
                    if role == "assistant":
                        continue
                    base = strip_not_harness_written(t, task)
                    full = base if role == "system" else redact_got_echo(base)
                    targets.append((role, i, t, base, full))
            n_texts_scanned += len(targets)
            #: 每一格 haystack 的引文區間只算一次（needle 迴圈會重複用它）。
            #: 鍵用字串本身不用 `id()`：`id` 會在物件被回收後重用，
            #: 拿它當快取鍵是一個會隨 GC 時機改變結果的量具。
            span_cache: dict[str, list[tuple[int, int]]] = {}

            def spans_for(hay: str, _cache=span_cache, _q=quotes):
                if hay not in _cache:
                    _cache[hay] = quoted_spans(hay, _q) if _q else []
                return _cache[hay]

            for role, i, raw, base, _full in targets:
                scrubbed = strip_frozen_constants(raw) if scope == "v1" else base
                for needle in CODE_NEEDLES:
                    if needle not in scrubbed:
                        continue
                    hit = {
                        "line": ln, "arm": arm, "rule": "check_code_identifier",
                        "needle": needle, "message_index": i, "role": role,
                        "task_id": task_id,
                        "excerpt": scrubbed[max(0, scrubbed.find(needle) - 80):
                                            scrubbed.find(needle) + 80]}
                    # round534：識別字也吃作者歸屬豁免（模組 docstring 的 ⚠）。
                    # `system` 一格豁免都不給，這一條也不例外。
                    if (scope == "v3" and role != "system"
                            and needle_only_inside_quotes(
                                scrubbed, needle, spans_for(scrubbed))):
                        hit["excused_as"] = MODEL_QUOTE_EXCUSE
                        excused.append(hit)
                    else:
                        violations.append(hit)
            if task is None:
                unknown_tasks.add(str(task_id))
                if scope == "v3":
                    for q in model_quotes_of(rec):
                        model_quotes.setdefault((arm, str(task_id)), []).append(q)
                continue
            if task_id not in cache:
                cache[task_id] = hidden_only_needles(task)
            needles, skipped = cache[task_id]
            n_skipped += len(skipped)
            n_checked += len(needles)
            # v3 去重：同一個 repr 出現兩次不會多驗到任何東西，只會讓同一筆命中
            # 被記兩遍。v1／v2 **不准**去重——R460 那 90 筆的逐塊數字含重複計數。
            scan_needles = list(dict.fromkeys(needles)) if scope == "v3" else needles
            n_unique += len(scan_needles)
            for needle in scan_needles:
                for role, i, raw, base, full in targets:
                    if scope == "v1":
                        hay, why = raw, None
                        if needle not in hay:
                            continue
                    elif needle in full:
                        hay = full
                        why = (None if role == "system"
                               else needle_excuse(needle, task, selftest_reprs))
                    elif needle in base:
                        # needle **只**出現在 `got=` 那一段裡 ⇒ 沙箱回聲豁免。
                        # ⚠ 留證不靜音：v2 初版在掃描前就把 `got=` 塗掉，
                        #   於是這一筆連「被豁免過」都看不到。
                        # ⚠ `system` 走不到這一格：它的 full 逐字等於 base。
                        hay, why = base, GOT_ECHO_EXCUSE
                    else:
                        continue
                    if (why is None and scope == "v3" and role != "system"
                            and needle_only_inside_quotes(
                                hay, needle, spans_for(hay))):
                        why = MODEL_QUOTE_EXCUSE
                    hit = {"line": ln, "arm": arm, "rule": "hidden_case_leak",
                           "needle": needle, "message_index": i, "role": role,
                           "task_id": task_id,
                           "excerpt": hay[max(0, hay.find(needle) - 80):
                                          hay.find(needle) + 80]}
                    if why:
                        hit["excused_as"] = why
                        excused.append(hit)
                    else:
                        violations.append(hit)
            if scope == "v3":
                for q in model_quotes_of(rec):
                    model_quotes.setdefault((arm, str(task_id)), []).append(q)
    # ── 逐臂 fail-closed（round534）───────────────────────────────────────
    # 「在檔案裡但一筆都沒進稽核」的臂。v1／v2 之下這一格一定非空（它們只掃
    # H 臂），所以它**不是**那兩個 scope 的判準，只是把被跳過的東西說出來
    # ——舊判準可以凍結，但不准繼續靜音。
    arms_not_audited = sorted(a for a, n in arms_present.items()
                              if n and not per_arm.get(a))
    if scope == "v3" and n_records == 0:
        verdict = "UNVERIFIABLE"
    elif scope == "v3" and arms_not_audited:
        verdict = "UNVERIFIABLE"
    elif violations or unknown_tasks:
        verdict = "VIOLATION"
    else:
        verdict = "CLEAN"
    excuse_rules = V3_EXCUSE_RULES if scope == "v3" else EXCUSE_RULES
    out = {
        "run": str(run_dir), "scope": scope, "records_audited": n_records,
        "texts_audited": n_texts, "texts_scanned": n_texts_scanned,
        "arms_in_scope": list(arms_in_scope),
        # `arms_present` ＝ 檔案裡出現過的每一條臂（掃了幾筆見 `per_arm`）。
        # 兩份都要落盤：只印 `per_arm` 正是 round534 那個洞躲了這麼久的原因
        # ——被跳過的臂在輸出裡完全不留痕跡。
        "arms_present": arms_present,
        "per_arm": per_arm,
        "arms_present_not_audited": arms_not_audited,
        # 檢查了幾個 needle、跳過幾個——跳過的要說出來，
        # 不能讓「沒有違規」順手把「沒有檢查」蓋掉（見模組 docstring 的誠實邊界）。
        # `needles_skipped_trivial` ＝ 落在 TRIVIAL_NEEDLE_REPRS 或長度 < 6 的那些。
        "needles_checked": n_checked,
        "needles_unique_scanned": n_unique,
        "needles_skipped_trivial": n_skipped,
        # v2 專屬：被 (c) 豁免掉的命中要**逐筆留著**，不准只留一個總數——
        # 「豁免了什麼」跟「違規了什麼」一樣是稽核證據。
        "excused_n": len(excused),
        "excused": excused,
        "excused_by_rule": {
            k: sum(1 for e in excused if e.get("excused_as") == k)
            for k in excuse_rules},
        "unknown_task_ids": sorted(unknown_tasks),
        "violations": violations,
        "verdict": verdict,
        "honest_bounds": [
            "`records_audited == 0`、或有任何一條臂在 `calls.jsonl` 裡有紀錄卻"
            "0 筆進稽核 ⇒ verdict 是 `UNVERIFIABLE` 不是 `CLEAN`（v3）。"
            "沒掃過不等於掃過是乾淨的。",
            "`scope` 是 v1／v2 時 `arms_in_scope` 只有 H 三臂，"
            "`arms_present_not_audited` 列的就是**沒被稽核過**的臂——"
            "那兩個 scope 的 CLEAN 只能講那三條臂，不能講整個 run。",
            "`model_own_output_quoted` 是作者歸屬豁免，不是機制保證："
            "「模型自己算出同一個值」與「模型看到了那個值」在字面比對下同形。"
            "逐筆留在 `excused` 裡讓人看。",
            "擋得住已知的洩漏形狀 ≠ 涵蓋所有洩漏形狀：這支只比對"
            "`hidden \\\\ visible` 的字面 repr，語意等價的改寫它認不出來。",
        ],
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="V/GT 洩漏動態稽核（零模型呼叫）")
    ap.add_argument("--run", required=True)
    ap.add_argument("--bank", default="lcb2",
                    help="題庫名（summary.json 沒有記 bank，必須顯式給，不猜）")
    ap.add_argument("--seed", default=None, help="預設讀 summary.json 的 seed")
    ap.add_argument("--out", default=None, help="稽核結果 JSON 落盤路徑")
    ap.add_argument("--scope", default="v3", choices=list(AUDIT_SCOPES),
                    help="v3（預設，round534）＝v2 的判準擴到全部十條臂＋逐臂"
                         "fail-closed；v2 是 round460r 的判準但**只掃 H 三臂**；"
                         "v1 是 round460e 的讀法，兩個都留著讓 R460 收官的"
                         "90／0 逐塊可重跑")
    args = ap.parse_args()

    run_dir = pathlib.Path(args.run)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    seed = args.seed or summary["seed"]
    if args.scope == "r530":
        # R530 的題庫不在 `gain_run.load_tasks` 那條路徑上（它是目錄不是題目集）。
        from ops.gain.r530 import tasks as r530tasks
        ids = summary.get("tasks") or []
        if not ids:
            raise SystemExit(
                f"{run_dir}/summary.json 沒有 tasks 清單——"
                "不知道要對哪幾題稽核。停。")
        tasks = {t["task_id"]: t
                 for t in [r530tasks.load_task(i) for i in ids]}
        result = audit_run_r530(run_dir, tasks)
    else:
        from ops.gain.gain_run import load_tasks
        tasks = {t["task_id"]: t for t in load_tasks(args.bank, seed, 0)}
        result = audit_run(run_dir, tasks, scope=args.scope)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        pathlib.Path(args.out).write_text(text + "\n", encoding="utf-8")
    if result["verdict"] == "UNVERIFIABLE":
        missed = result.get("arms_present_not_audited") or []
        raise SystemExit(
            "V/GT 稽核**不可結算**："
            + (f"這些臂在 calls.jsonl 裡有紀錄卻 0 筆進稽核：{missed}"
               if missed else "一筆模型呼叫都沒稽核到")
            + f"（{run_dir}/calls.jsonl）。量具沒接上不是通過。停。")
    if result["verdict"] != "CLEAN":
        raise SystemExit(
            f"V/GT 稽核不通過：{len(result['violations'])} 筆違規／"
            f"{len(result['unknown_task_ids'])} 個對不到題目的 task_id"
            "——整個 run 作廢（SPEC_GAIN §7），不得只修不報。")


if __name__ == "__main__":
    main()
