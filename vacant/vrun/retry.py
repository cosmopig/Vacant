#!/usr/bin/env python3
"""這支在架構裡承重什麼：`vacant run` V1 的**重試迴圈政策**（兩條臂的差別本身）。

V0 只能「跑一次 → 驗收 → 過或拒交」。**那只是收件口，不是 Vacant 的機制。**
R530／R532 量到增益的那個東西是**閘門＋重抽／重改**（CONFORM 對單發
+14～+19 pp、五次複製都過 Holm）。沒有迴圈，`vacant run` 交付不出那個增益。

## 為什麼 V1 這麼便宜：觸發點不在 wire 上

「把回饋注入回對話」之所以是一整塊研究，是因為它假設要在 **wire 層偽造
tool_call 或訊息**——那會在 agent 的歷史裡留下模型從沒說過的話，
**直接傷害 Vacant「紀錄忠實」的立論根基**（`docs/VACANT_RUN.md` §1）。

但 V0 的觸發點是 **agent 行程結束**，所以重試根本不用碰協定：
把失敗原文寫進工作區的一個檔，**再 spawn 一次 agent 就好**。
零協定破解、零偽造發言、跨所有框架、連走文字協定的也涵蓋。
`wireproxy.WireProxy.on_wire()` 在 V1 仍然**恆回 `None`（永不改寫）**。

## 兩條臂（命名對齊既有實驗，但**不得與 R530／R534 併表**）

| 臂 | 沒過之後 | 對應 |
|---|---|---|
| `resample` | **全新工作區**（重置回起點）、全新 agent 行程，不給失敗原文 | R530 A-CONF／R532 CONFORM |
| `revise`   | **保留工作區**、把失敗原文寫進 `VACANT_FEEDBACK.md`、再跑一次 | R530 A-GATE／R532 HMIX |
| `none`     | 不重試（＝V0 的行為，預設）                                    | — |

⚠ **本輪的數字不得與 R530／R532／R534 併表**：prompt 不是我們寫的
（agent 命令由使用者給）、工具面由框架自己決定、預算形狀是「整個行程重跑」
而不是「同一段對話多說一輪」。三個變因都不同，併表就是把三件事講成一件事。

## `resample` 的重置為什麼連 `.git` 一起清

`wshash.EXCLUDED_DIRS` 把 `.git/` 排除在樹雜湊之外——**但它排除不了 agent 的眼睛**。
上一次嘗試如果 commit 過，留著 `.git` 就等於偷偷把失敗原文留在現場，
那樣 `resample`（不給原文）與 `revise`（給原文）的差別會消失，而消失的方式
**在樹雜湊上完全看不出來**。所以重置是整個目錄逐位元還原，不是「還原被雜湊的那部分」。
還原完會**再量一次**樹雜湊，對不回起點 ⇒ 判 `infra_void`，不判拒交也不判通過。

## 回饋檔的兩條紅線

1. **只准寫可見驗收的失敗原文**（`acceptance.render_failures()` 吃的是
   `run_suite(suite="visible")` 的結果）。隱藏驗收的存在、條數、內容一律不進這一段。
   可執行防呆：`tests/test_vacant_run_retry.py::test_feedback_file_never_contains_hidden_testdata`
   （canary 種在 hidden 側，掃 feedback 檔要零命中），形狀照抄
   `tests/test_gain_vgt_canary.py`。
2. **KS-1（鐵律 1）**：回饋文字禁止「你有責任／會被懲罰」類措辭。
   `vacant/memory.py::assert_ks1_clean` 在本模組 import 時就跑，繞不過去。

## V2 ＝ 同一份回饋也放進 **argv**（`--feedback-into prompt|both`）

V1 的回饋是寫一個檔（`VACANT_FEEDBACK.md`）到工作區，而上面 `FEEDBACK_FILENAME`
的註解自己就承認了那條路的洞：**「我們沒有辦法在它的 prompt 裡講『去讀某某檔』」**
⇒ 模型可以不讀它。人類的要求是「Vacant 在開啟的狀態下不要被 LLM 忽略，
它基本上就是 harness 的一環才行」。

### 為什麼是 argv 而不是 wire

proxy **擁有一次 HTTP 往返的讀寫權，不擁有 agent 的迴圈狀態，也不擁有工具執行器**。
三條 wire 上的路各自撞死在那個邊界上：

  · 改 `tools` ⇒ **L0**：proxy 宣告得了工具、**執行不了**——`tool_result`
    只能由 agent 自己的執行器產生，我們生不出來。
  · 改 `system` ⇒ wire 上的紀錄會與框架自己的 transcript 講不同的話
    （**直接傷害「紀錄忠實」的立論根基**）。
  · 插一則 user 訊息 ⇒ 它**只存在於那一通 request**，agent 的歷史裡沒有，
    下一通就不一致。

**launcher 擁有 argv，而 argv 就是那一則 user 訊息。** 零協定破解、零偽造發言。
`wireproxy.WireProxy.on_wire()` 在 V2 仍然**恆回 `None`（永不改寫）**——
V2 一個位元都沒有碰 wire。

### 三條規則，每一條都有理由

  1. **placeholder 必須是該 argv 元素的結尾**，否則 `SystemExit`。
     尾端 append 才保得住 provider 的**前綴快取**；插在中間會讓整段快取失效，
     而那個成本不會出現在任何一個我們落盤的欄位裡。
  2. **第 1 次嘗試把 placeholder 換成空字串** ⇒ 第一次的 prompt 與
     「沒有 Vacant」時**逐位元相同**。這是兩臂可比性的基礎，
     形狀與 wire 那條「兩臂 body 逐位元相同」同一個用意。
  3. 之後才換成 `"\n\n" + 回饋`，並對**接上去的那一段**再跑一次
     `assert_ks1_clean`（鐵律 1 不因為換了管道就放鬆）。
     ⚠ **範圍是「我們寫的字」，不是整條命令。** KS-1 的立法意旨是
     「我們的 prompt 模板不准用責任措辭」——那會污染實驗條件（三臂模板逐字
     相同，唯一差異是記憶區塊）——**不是內容審查**。使用者自己的 prompt
     是他的業務：`-p "You are responsible for the migration"` 完全正常，
     掃它等於用一個誤判殺掉整跑。（2026-09-18 人類裁決。）

### V2 的誠實邊界（**不准淡化**）

  1. **不能說「不可忽略」。** 能說的是「**回饋一定出現在模型的輸入裡**」。
     **看得到 ≠ 照做**——能強制的只有「沒過就不出貨」（閘門本身）。
  2. **不能說 V2 提高了通過率。** V1 實跑三次都沒改對，但 wire 顯示
     那份回饋**從未進過 context**（18 通請求零命中，§7.8）⇒ 那一跑
     **沒有測到重改**，不能拿來當 V2 的對照基線；
     R534 真模型上「沒過→重改」與拒交出現 **0 次**。
     **V2 改的是機制性質（回饋一定在輸入裡），不是效果量測。**
  3. **不得與 R530／R532／R534 併表**：prompt 不是我們寫的、工具面由框架決定、
     預算形狀不同。三個變因都不一樣。
  4. **預設仍是 `"file"`** ＝ V1 的行為逐字不變；要 argv 就要明講
     `--feedback-into prompt|both`，而且 argv 裡沒有 placeholder 就**死在畫面上**，
     **不安靜退回檔案模式**——「我以為在 prompt 模式」的錯不准在資料裡活著。

## 誠實邊界（改碼請保留；完整版在 `docs/VACANT_RUN.md` §7）

1. **重試不是免費的。** 每一次嘗試都燒一整個 agent 行程的 token 與時間，
   `--max-attempts` 是**成本上限**不是目標值。實際用量逐次落盤
   （`attempts[i].requests_seen`／`wall_s`／`ws_*_sha256`），
   等預算的定義是「上限相同、實際用量落盤」，不是強制用滿（R530 的裁決）。
2. **`revise` 會讓 agent 看到自己的失敗，那是設計**；但它看不到隱藏測資，
   這條由上面的 V/GT 測試守，不是由「我們很小心」守。
3. **R534 實測：真模型上「沒過→重改」與拒交出現 0 次**（6 格次裡 2 次宣告完成
   都第一輪過、2 次燒光 token、2 次撞脈絡上限）⇒ **V1 讓這條路存在，
   不代表它在你的工作負載上會被觸發。** 沒被觸發的迴圈不產生增益。
4. 迴圈**不改變**驗收是單邊保證這件事（`vacant/suitegauge.py`）：
   重試到過，只代表「客戶給的那幾條過了」，不代表做對了。
"""
from __future__ import annotations

import hashlib
import pathlib
import shutil

from ..memory import assert_ks1_clean

#: 三條臂。**封閉集合**——多一個就是規格變更，不准在別處臨時造字串。
RETRY_ARMS = ("none", "resample", "revise")

#: 預設嘗試上限。
#:
#: 為什麼是 3 而不是 R530 A-GATE 的 5：那個 5 是給「同一段對話裡多說一輪」
#: 訂的，單位成本是幾則訊息；V1 的一次嘗試是**整個 agent 行程重跑**
#: （重讀任務、重建脈絡、重跑工具），成本高一個量級。3 同時是 R530 A-CONF
#: 「最多 3 份」那條的下限，兩條臂都涵蓋得住。
#: 展場與無人值守（CLAUDE.md「離線可跑、可無人值守循環」）要的是一個**小**的
#: 成本上限，不是一個大的。要更多就明講 `--max-attempts`。
DEFAULT_MAX_ATTEMPTS = 3

#: 失敗原文寫在工作區的哪個檔。**固定檔名**：agent 命令是使用者給的，
#: 我們沒有辦法在它的 prompt 裡講「去讀某某檔」，所以這個名字必須是
#: 文件上的一個約定（`docs/VACANT_RUN.md` §7），而不是每次跑都不同的臨時名。
FEEDBACK_FILENAME = "VACANT_FEEDBACK.md"

#: 回饋正文。**沿用 `ops/gain/r534/piarms.py::FEEDBACK_TEMPLATE` 的形狀**，
#: 不是自己發明的措辭——連硬折行的位置都逐字照抄，理由是那一段已經在 R534
#: 的真模型上跑過，換字就等於在這裡引入一個沒有被量過的變因。
#:
#: **唯一的改寫是最後一句**（R534 是 `When you consider it finished, reply with
#: a short plain-text summary and do not call any tool.`）：那句話講的是 pi
#: 在**同一段對話裡**怎麼宣告完成，而 V1 的觸發點是**行程結束**，照抄會是
#: 對 agent 說一句在這裡不成立的話。改寫之後說的是 V1 真正的機制。
#: `{block}` 由 `ops/gain/r530/acceptance.render_failures()` 渲染
#: （**只吃可見驗收的結果**，紅線見模組 docstring）。
FEEDBACK_BODY = """The checks that ship with this task were run against your
working directory. They did not all pass.

{block}

Fix the working directory. The checks run again when this process exits."""

#: 檔案表頭。**訊息可以靠位置說明自己是什麼，檔案不行**——工作區裡多一個檔，
#: agent 第一眼要能分辨它是「別人塞進來的機器輸出」還是「交付的一部分」。
#: 形狀取自 `piarms.TOOL_RESULT_HEADER`（"This is machine output, not a person."）
#: 的同一個用意：讓模型看得出這一段不是人在說話。
FEEDBACK_HEADER = """<!-- Written by `vacant run` between attempts.
     This is machine output, not a person. It is not part of the deliverable. -->

# Acceptance feedback (attempt {attempt} of {max_attempts})
"""

FEEDBACK_TEMPLATE = FEEDBACK_HEADER + "\n" + FEEDBACK_BODY + "\n"

# ── KS-1 可執行防呆（鐵律 1）：import 時就跑，繞不過去 ─────────────────────
for _t in (FEEDBACK_HEADER, FEEDBACK_BODY, FEEDBACK_TEMPLATE):
    assert_ks1_clean(_t)


def render_feedback(block: str, *, attempt: int, max_attempts: int) -> str:
    """組出要寫進 `VACANT_FEEDBACK.md` 的整份文字。

    `block` 一定要是 `acceptance.render_failures(<visible 的結果>)` 的輸出。
    呼叫端負責只餵可見驗收——這支不會、也沒辦法替它檢查資料從哪來。
    """
    text = FEEDBACK_TEMPLATE.format(block=block, attempt=attempt,
                                    max_attempts=max_attempts)
    return assert_ks1_clean(text)


def write_feedback(workspace: pathlib.Path, text: str) -> dict:
    """把回饋寫進工作區，回一份可落盤的中繼資料（路徑、位元組數、sha256）。

    **落盤 sha256 而不是只落盤「寫了」**：收據要說得出那一次 agent 讀到的是
    哪一份文字，而全文已經在 `run_<ARM>.json` 的 `attempts[i].feedback_text`
    裡；鏈上放雜湊、全文放檔案，形狀沿用 `r530/receipts.py`。
    """
    p = pathlib.Path(workspace) / FEEDBACK_FILENAME
    data = text.encode("utf-8")
    p.write_text(text, encoding="utf-8")
    return {"path": str(p), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def snapshot_origin(workspace: pathlib.Path, dest: pathlib.Path) -> None:
    """把起點工作區整個複製到 `dest`（**含 `.git` 等一切**）。

    不用 `wshash.EXCLUDED_DIRS` 過濾，理由見模組 docstring：
    排除清單是**樹雜湊**的清單，不是**重置**的清單。
    """
    dest = pathlib.Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(workspace, dest, symlinks=True)


def restore_origin(origin: pathlib.Path, workspace: pathlib.Path) -> None:
    """把工作區**整個**還原成 `origin`：先清空，再複製回去。

    清空是逐項刪，不是 `rmtree(workspace)` 再建——工作區有可能是別人給的掛載點
    或 agent 的 cwd，整個拿掉再造出來會換掉 inode，有些行程會因此看到
    `ENOENT`。刪內容不刪殼，外面拿著這個路徑的東西不受影響。
    """
    workspace = pathlib.Path(workspace)
    for child in workspace.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        else:
            shutil.rmtree(child)
    shutil.copytree(origin, workspace, symlinks=True, dirs_exist_ok=True)


# ══ V2：把同一份回饋放進 argv（＝那一則 user 訊息）════════════════════════

#: argv 裡的佔位符。**固定字面值**：它是使用者寫在自己那條 agent 命令裡的東西，
#: 所以必須是文件上的一個約定（`docs/VACANT_RUN.md` §8），不是每次跑都不同的臨時名。
#: 與 `FEEDBACK_FILENAME` 的差別在於**誰擁有它**：檔名是我們寫進工作區的東西，
#: agent 可以不去讀；placeholder 在 argv 裡，而 argv 就是模型的輸入本身。
FEEDBACK_PLACEHOLDER = "{VACANT_FEEDBACK}"

#: 回饋的投遞管道。**封閉集合**——多一個就是規格變更，不准在別處臨時造字串。
#: `"file"` ＝ V1 逐字不變（預設）；`"prompt"` ＝ 只進 argv；`"both"` ＝ 兩邊都給。
DELIVERY_MODES = ("file", "prompt", "both")

#: 哪些 mode 會把回饋放進 argv／哪些會寫檔。**兩個集合是上面那個封閉集合的
#: 唯一解讀方式**——不要在別處用 `mode == "prompt"` 之類的字串比對，
#: `"both"` 會被那種寫法安靜漏掉。
_PROMPT_MODES = frozenset({"prompt", "both"})
_FILE_MODES = frozenset({"file", "both"})


def delivers_to_prompt(mode: str) -> bool:
    """這個 mode 會不會把回饋放進 argv。"""
    return mode in _PROMPT_MODES


def delivers_to_file(mode: str) -> bool:
    """這個 mode 會不會把回饋寫成工作區裡的檔。"""
    return mode in _FILE_MODES


def argv_sha256(argv: list[str]) -> str:
    """argv 的指紋。**用 NUL 分隔**：空白分隔的話 `["a b"]` 與 `["a", "b"]`
    會雜湊成同一個值，而那兩條命令不是同一條。
    """
    return hashlib.sha256("\0".join(argv).encode("utf-8")).hexdigest()


def check_argv_has_placeholder(argv: list[str], mode: str) -> None:
    """`--feedback-into` ＋ argv → 壞組合一律 **fail-visible**。

    口氣與 `launcher.resolve_max_attempts` 同一條：
    `--feedback-into prompt` 而 argv 裡沒有 `{VACANT_FEEDBACK}`，不是
    「保守的預設」，是**使用者以為回饋會進 prompt 但它不會**。

    ⚠ **不准安靜退回檔案模式。** 安靜退回會讓「我以為在 prompt 模式」的錯
    在資料裡活著：那一跑的收據會寫 `feedback_delivery="prompt"`，
    而模型的輸入裡一個字都沒有。那種錯要死在畫面上。

    反向也擋（argv 有 placeholder 但 mode 是 `"file"`）：那一格我們**不會**替換它，
    literal `{VACANT_FEEDBACK}` 會原樣送給 agent 看——同一個「我以為開了」的錯，
    只是方向相反。
    """
    if mode not in DELIVERY_MODES:
        raise SystemExit(f"--feedback-into 只認 {list(DELIVERY_MODES)}，"
                         f"拿到 {mode!r}。停。")
    hits = [a for a in argv if FEEDBACK_PLACEHOLDER in a]
    if delivers_to_prompt(mode) and not hits:
        raise SystemExit(
            f"--feedback-into {mode} 要把回饋放進 agent 命令，但那條命令裡沒有 "
            f"{FEEDBACK_PLACEHOLDER}。把它接在提示詞的**結尾**，例如：\n"
            f"    -- pi -p \"把 solution.py 寫完{FEEDBACK_PLACEHOLDER}\"\n"
            "（不安靜退回檔案模式：那會讓收據說 prompt、模型的輸入裡卻什麼都沒有。）停。")
    if hits and not delivers_to_prompt(mode):
        raise SystemExit(
            f"agent 命令裡有 {FEEDBACK_PLACEHOLDER}，但 --feedback-into {mode} "
            "不會替換它——那串字會原樣送給 agent 看。"
            "要回饋進 prompt 就給 --feedback-into prompt（或 both）。停。")


def render_argv(argv: list[str], feedback_text: str, *,
                mode: str) -> tuple[list[str], str, int]:
    """把回饋接到 argv 的 placeholder 上。回 `(new_argv, argv_sha256, 替換次數)`。

    · `mode` 不投遞到 prompt ⇒ **argv 一個位元都不動**（V1 逐字不變）。
    · `feedback_text` 為空（＝**第 1 次嘗試**）⇒ placeholder 換成 **空字串**，
      所以第一次的命令與「沒有 Vacant」時**逐位元相同**。
      這是兩臂可比性的基礎：第一次就不一樣的話，後面量到的差別有一半是
      「第一次的 prompt 本來就不同」。
    · 之後 ⇒ 換成 `"\n\n" + feedback_text`。

    ⚠ **placeholder 必須是該元素的結尾**，否則 `SystemExit`：
      尾端 append 才保得住 provider 的前綴快取，插在中間會讓整段失效。
      同一個元素裡出現兩次也擋（前面那一次就不在結尾）。

    ⚠ **KS-1 只掃我們接上去的那一段（`tail`），不掃使用者自己的 prompt。**
      鐵律 1 的立法意旨是「**我們的** prompt 模板不准用責任措辭」——理由是那會
      污染實驗條件（三臂模板必須逐字相同，唯一差異是記憶區塊），
      **不是內容審查**。使用者那條命令是他自己的業務：
      `-p "You are responsible for the migration"` 是一句完全正常的話，
      掃它等於用一個誤判殺掉整跑，代價與 KS-1 要防的東西不成比例。
      回饋文字本身仍然逐字受管——那是我們產生的，該管。
      兩個方向各有一條測試（`test_v2_ks1_scope_is_our_text_not_the_users`／
      `test_v2_ks1_still_voids_when_our_own_feedback_is_dirty`）：
      **只證明「收得住」不夠，還要證明「沒收掉」**。
    """
    # ⚠ **擋門在 early-return 之前**，不在之後：放在後面的話，
    #   `--feedback-into prmopt`（打錯一個字）會走 `delivers_to_prompt()` 為 False
    #   那條路，argv 原樣回去、零錯誤——**那正是本模組禁止的「安靜退回檔案模式」**，
    #   而且收據還會照樣寫使用者以為的那個 mode。壞 mode 要死在這裡。
    check_argv_has_placeholder(argv, mode)
    out = list(argv)
    if not delivers_to_prompt(mode):
        return out, argv_sha256(out), 0
    tail = "" if not feedback_text else "\n\n" + feedback_text
    # 鐵律 1 不因為換了管道就放鬆——**但它管的是我們寫的字**（上面那條 ⚠）。
    # 掃 `tail` 不掃 `"\n".join(new)`：後者含使用者自己的 prompt。
    assert_ks1_clean(tail)
    new: list[str] = []
    n_sub = 0
    for a in out:
        cnt = a.count(FEEDBACK_PLACEHOLDER)
        if cnt == 0:
            new.append(a)
            continue
        if cnt > 1 or not a.endswith(FEEDBACK_PLACEHOLDER):
            raise SystemExit(
                f"{FEEDBACK_PLACEHOLDER} 必須是該參數的**結尾**（拿到 {a!r}）："
                "回饋是往尾端 append 的，插在中間會讓 provider 的前綴快取整段失效。停。")
        new.append(a[: -len(FEEDBACK_PLACEHOLDER)] + tail)
        n_sub += 1
    return new, argv_sha256(new), n_sub


def constants_manifest() -> dict:
    """凍結常數的指紋。落進 `run_<ARM>.json`，改了文字在資料上看得見。

    形狀沿用 `piarms.frozen_manifest()` 的 `feedback_sha256`。
    """
    return {
        "retry_arms": list(RETRY_ARMS),
        "default_max_attempts": DEFAULT_MAX_ATTEMPTS,
        "feedback_filename": FEEDBACK_FILENAME,
        "feedback_template_sha256":
            hashlib.sha256(FEEDBACK_TEMPLATE.encode("utf-8")).hexdigest(),
        "feedback_body_sha256":
            hashlib.sha256(FEEDBACK_BODY.encode("utf-8")).hexdigest(),
        # ── V2：投遞管道（改了字面值在資料上看得見）──────────────────
        "feedback_placeholder": FEEDBACK_PLACEHOLDER,
        "delivery_modes": list(DELIVERY_MODES),
    }
