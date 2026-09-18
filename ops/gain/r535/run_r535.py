#!/usr/bin/env python3
"""這支在架構裡承重什麼：R535 的**發射驅動**（四臂 × 90 題 ＝ 360 格）。

它**不出題**（題庫＝`ops/gain/r535/bank/`，量具＝`gauge_bank.py`，兩者都不在本檔
的職責裡，本檔一個位元都不碰），**不寫預註冊**，也**不計分**（事後計分是
`ops/gain/r535/score_r535.py`，分開的一支，零模型呼叫、可離線重跑）。
本檔只做一件事：把 360 格逐格交給 `vacant/vrun/launcher.py` 的 CLI，
把每一格發生了什麼逐格落盤。

## 四臂（唯一差異是旗標與工作區樣板；prompt 逐字相同）

| 臂 | 旗標 | 工作區樣板 | 它承重什麼 |
|---|---|---|---|
| `RS` | `--retry resample --max-attempts 3` | `TASK.md` | **不給回饋的重抽**＝負控制 |
| `RF` | `--retry revise --max-attempts 3 --feedback-into file` | `TASK.md` | 回饋走檔案 |
| `RP` | `--retry revise --max-attempts 3 --feedback-into prompt` | `TASK.md` | 回饋走 argv |
| `PC` | `--retry none` | `TASK_explicit.md`→`TASK.md` | RP 的**天花板**（正控制） |

⚠ **RS 不是 `--retry none`**（2026-09-19 更正）：那會讓 RS 只有 1 次 draw 而
RF／RP 有 3 次 ⇒「RF > RS」變成設計的可預期後果，負控制就分不開它要分的東西。
改成 `resample` 之後兩臂都是 3 次 draw，剩下的差異只有兩個：
(i) 工作區裡多一個回饋檔、(ii) `revise` **保留**工作區／`resample` **重置**工作區。

**單發基線不另開臂**：三條重試臂的**第 1 次嘗試**與 `--retry none` 逐位元同構
（同 argv——V2 的 placeholder 第 1 次換成空字串，§8.2-2；同 TASK.md；
launcher 第 1 次不注入任何東西）⇒ S1 有 n=150 個單發觀測，零額外機時。
所以本檔**逐次嘗試**落盤（`attempts[]` 每一筆都帶可見判定），
不是只落最後一次——那個免費的基線就是靠這個拿到的。

## 推論模式：**送 `reasoning_effort: "none"`**（NOTHINK，2026-09-19 裁決）

**「不送」不是選擇一個模式，是把模式交給後端版本決定。** 1003（0.4.24）預設思考、
1004（0.4.17）預設不思考，**同一份 gguf**——所謂「真實 pi 使用者拿到的預設」在這裡
不是 pi 的性質，是那台 LM Studio 的性質，而那正是 **R529 的混淆形狀**。
送旗標是唯一讓模式成為「我們送出的輸入」而不是「機器的狀態」的做法。
另外 THINK 在 pi 上有已知病態（R534 A1/B1 四格全部 `nudge_exhausted`，每通 400+ s、
宣告完成但工作區沒動），在 `--timeout` 底下會變成「被砍→可見失敗→重試」，
**把「思考燒掉時間」混進管道比較**。

走 **R534 驗過的那條**：`models.json` 的
`samplingParams: {"reasoning_effort": "none"}`（形狀照 `ops/gain/r534/models.json`
的 `lms1003nothink`）。**不用 pi 的 `--thinking off`**——compat 標
`supportsReasoningEffort: false`，那條路沒驗過。

**F3 是兩半，兩半都要**（`measure_f3`）：
① 每通 request body 含 `"reasoning_effort":"none"`；② 每通 response
`reasoning_tokens == 0`。任一違反 ⇒ 該格 `INVALID`；累計 > 0 格 ⇒
**driver 暫停等人**，不自己續跑。第三種狀態是 **`unmeasured`**（那一通沒報 usage）
——它與「量到 0」不可以同形，所以分開記、不當成通過。

## 模型端點怎麼接（照 `docs/VACANT_RUN.md` §7.8 那兩跑重現）

pi 0.85.1 ＋ 1003 的 `gemma-4-12b-it-qat`。**pi 不吃環境變數**（§4.5／
`docs/AGENT_COMPAT.md` §3 有否定證據），所以走 `--port` 固定埠 ＋
`PI_CODING_AGENT_DIR` 底下一份 `models.json` 把 provider `baseUrl` 指向 proxy。

⚠ **端點環境變數是 `VACANT_GAIN_API`**（完整的
`http://<host>:1234/v1/chat/completions`），**不是 `VACANT_ENDPOINT`**——
R532 為此誤發兩次打到雲端（產物留在 `runs/_falsestart_20260917_*`）。
本檔把它拆成 proxy 的上游（`VACANT_RUN_UPSTREAM_OPENAI`＝去掉
`/chat/completions` 的 base），沒設或形狀不對就**拒絕啟動**。

⚠ 但「我設了設定」不是證據。真正要驗的是 **`requests_seen > 0`**
（§4.5 現場版本：`--port` 給 8878 而 `models.json` 寫 8877 ⇒ agent 完全沒被
中介到，畫面上只有 pi 自己的 `Connection error.`）。本檔逐格落盤
`requests_seen`，並在 `--preflight` 之外不替它找藉口。

## 兩個新量測（裁決要的，現有程式沒有）

* **`M7_file`** ——回饋文字有沒有出現在**第 ≥2 次嘗試**的任一通 wire。
  這是 **RF 臂的承重證據**，不是附帶指標。`true`／`false`／`null`，
  `null`＝不適用（沒有第 2 次嘗試，或這一臂根本不產生回饋＝RS）
  ——**不可以記成 `false`**（鐵律 3 的 `infra_void` 同一條：沒量到 ≠ 量到 0）。
  另外附一個**負向控制**：同一組特徵字串如果在**第 1 次**的 wire 裡就出現，
  那它不具鑑別力，會被剔除並記進 `m7_file_leaky_needles`；全部被剔除 ⇒ `null`。
* **`M7_ws`** ——RF 臂第 ≥2 次嘗試裡，wire 出現 `read TASK.md`／
  `write solution.py` **以外**任何工具呼叫的比例。它承重上面的 (ii)：
  RF 比 RS 高但 `M7_file = 0` 時，用它分辨「保留工作區被讀到了」
  還是「我們的機制模型解釋不了」。**分類器的原始清單一起落盤**
  （`m7_ws_calls`），所以事後可以離線重新分類，不必重跑。
* **`F6`** ——RP 臂的每個第 ≥2 次嘗試 `feedback_in_prompt_bytes > 0`。

## 發射順序：**題塊 × 四臂交錯**，不是「先發一臂」（2026-09-19 裁決）

「先只發 RS 90 格」**被否決**：RS 全部在 T₁ 跑、其餘在 T₂ 跑 ⇒ 後端任何漂移
（重載、TTL、負載）都變成 **RS 與別臂之間的時間混淆**，而 H2 的預測正是「可交換」
——最怕的就是這種混淆（R534 §九「同一題四格同時發」就是為此）。

所以 `plan.jsonl` 把**同一題的四格排在相鄰四列**，臂序按 `task_index mod 4` 輪轉。
配上 `--shard k:4`（分片用的是**計畫裡的列號**不是過濾後的位置）⇒
第 k 條流拿到每一題的第 k 個位置 ⇒ **四條流同時在跑同一題的四個臂**，
而且每條流四個臂的量都一樣。

### 唯一一次期中看（格數、量、方向全部寫死，只能停不能改）

| 層 | 量 | 期中 n | 期中停止線 | 終判線（不變） |
|---|---|---:|---|---|
| S1 | RS/RF/RP 合併 attempt-1 可見失敗率 | 45 | < 0.45 ⇒ 停 S1，`NOT_TRIGGERED` | < 0.6，n=150 |
| S1 | PC attempt-1 通過率 | 15 | < 0.30 ⇒ 停 S1，`CEILING_TOO_LOW` | < 0.5，n=50 |
| S2 | 同上合併失敗率 | 36 | < 0.15 ⇒ 停 S2 | < 0.3，n=120 |
| S2 | PC 通過率 | 12 | < 0.30 ⇒ 停 S2 | < 0.5，n=40 |

觸發點：S1 **前 15 題 × 4 臂 = 60 格**跑完、S2 **前 12 題 × 4 臂 = 48 格**跑完。
停止線比終判線寬是**刻意的 futility boundary**：真值 0.6 時 n=45 的觀測 SD ≈ 0.073，
0.45 在 2 SD 之外，誤停約 2%；設計意圖 0.8 時誤停 ≈ 0。
**落在停止線與終判線之間 ⇒ 續發**，由終判在 n=150 裁。

⚠ **期中看只有一次。**
⚠ **格數固定。**
⚠ **量固定。**
⚠ **方向固定（只能停，不能改任何門檻或臂）。**

判定寫成 `interim_<層>.json`，**`O_EXCL` 寫一次就不再重算**——「只看一次」不是
自律，是檔案系統的語意。資料不齊（有 void 格）時**不寫**，因為寫了就定案了。

### 塊邊界探針

每 15 題（S2 每 12 題）driver 對上游打一通 1-token 探針，落盤 model id 與
`reasoning_tokens`。model id 變了或 `reasoning_tokens > 0` ⇒ 寫 `HALT.json`、
**driver 暫停**，之後的格標 `probe_invalid` 直到人 `--ack-halt` 確認。
這把「載的是哪份 gguf」那條人的義務縮到只剩**載入參數與檔案內容**（見誠實邊界 5）。

## 落盤與斷點續跑

```
<out>/plan.jsonl              360 格的計畫（**只 append 安全，永不覆寫**）
<out>/plan_receipt.ndjson     第一筆收據簽的就是 plan.jsonl 的 sha256
<out>/plan_receipt.pub.json   公鑰（私鑰不落盤，RECORD_SPEC §7）
<out>/driver_<stream>.jsonl   driver 事件（含每 15 分鐘一筆 uptime）
<out>/cells.jsonl             每格收完 append 一列（對帳用）
<out>/probes.jsonl            塊邊界探針（model id ＋ reasoning_tokens）
<out>/probe_baseline.json     第一次探針看到的 model id（O_EXCL，之後拿它比）
<out>/interim_<層>.json       期中判定。**O_EXCL 寫一次就定案**
<out>/HALT.json               探針或 F3 舉的旗；在就不派工，只有人 --ack-halt 解得開
<out>/reconcile.json          收官對帳（`--reconcile`）
<out>/cells/<task>__<ARM>/
    ws/                       agent 的工作區（只有 TASK.md）
    run/                      `--run-dir`：收據、wire、`_frozen_*`、run_RUN-ON.json
    piconf/                   `PI_CODING_AGENT_DIR`（models.json）
    io.jsonl                  這一格的 driver I/O（逐事件）
    cell.json                 **邊跑邊寫**；`run_complete` 最後才翻 true
```

⚠ **完成判定用 `run_complete` 旗標，不是「檔案存在」**（2026-09-17 踩過：
等待迴圈用檔案存在判定，冒煙塊才第 4/20 題就被當成收完）。
⚠ **目錄存在就跳過**：多串並行安全、斷點續跑。要重跑一格＝人自己把那個目錄搬走。

## 誠實邊界（改碼請保留）

1. 本檔**不判斷題目做對了沒有**。它記的是「可見驗收過了沒有」，而可見驗收是
   **單邊保證**（`vacant/suitegauge.py` 的 docstring）：擋得住已知壞解 ≠ 涵蓋真需求。
   隱藏驗收只在 `score_r535.py` 跑，**只計分不回饋**（V/GT 紅線）。
2. `suspect_timeout` 是**標記不是剔除**。剔除是收官時依預註冊規則做的事，
   當場剔除會讓「基建壞了」與「模型答錯了」在資料上同形。
3. `infra_void` 的格子 `accepted` 落 `null` 不落 `False`。
4. 本檔量的是**這一份 harness 上的**通過率。`vacant run` 的 prompt 不是我們寫的、
   工具面由 pi 決定、預算形狀是「整個行程重跑」——**不得與 R530／R532／R534 併表**
   （`docs/VACANT_RUN.md` §7.7-4、§8.5-3）。
5. 驅動證明得了 wire 去了哪台機器（`wire_upstreams`），**證明不了那台載的是哪一份
   gguf、用什麼載入參數**。塊邊界探針接住了「model id 變了」與「開始思考了」，
   **接不住「同一個 model id、同一個推論模式，但檔案內容或載入參數換了」**
   ——那一條仍然是人的義務。
6. **牆鐘方差大（實測同一臂相鄰兩題 10 s 對 314 s）⇒ 逐格牆鐘印分佈不印均值。**
   「等預算」的意思仍然是**上限相同、實際用量落盤**，不是用滿。
7. **`agent_timed_out=true` 是正常的嘗試結果，不 void**：那是 agent 自己在預算內
   沒做完，四臂一視同仁。逐臂逐層印比例；任一臂-層 > 20% ⇒ 收官必須寫
   「該比較受預算約束」。把它當 `infra_void` 剔掉會**系統性地偏袒慢的那一臂**。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from vacant.identity import Identity            # noqa: E402
from vacant.logbook import Logbook              # noqa: E402
from vacant.crypto import pub_to_hex            # noqa: E402

# ── 凍結常數（改這裡就是改實驗，不要在別處臨時寫字串）─────────────────────

#: 題庫 manifest 的 sha256。**釘死值**，不相等就拒絕啟動（裁決 2026-09-19）。
#: 展開器讀的是 `bank_manifest.json`，**不讀預註冊文件**——預註冊是給人看的，
#: 兩份真相會漂。
EXPECTED_MANIFEST_SHA256 = (
    "5e727b2ee884d80b197ec42f63af2bf73ce939bdd53c48fc8fc29e46e49c0794")

#: 四臂的旗標。**逐字凍結**：唯一差異是這裡與工作區樣板，prompt 一個字都不動。
ARMS: dict[str, dict] = {
    "RS": {"flags": ["--retry", "resample", "--max-attempts", "3"],
           "template": "workspace_template", "placeholder": False,
           "why": "不給回饋的重抽＝負控制（與 RF 同為 3 次 draw）"},
    "RF": {"flags": ["--retry", "revise", "--max-attempts", "3",
                     "--feedback-into", "file"],
           "template": "workspace_template", "placeholder": False,
           "why": "回饋走工作區的 VACANT_FEEDBACK.md（agent 可以不讀它）"},
    "RP": {"flags": ["--retry", "revise", "--max-attempts", "3",
                     "--feedback-into", "prompt"],
           "template": "workspace_template", "placeholder": True,
           "why": "回饋走 argv 尾端（一定出現在模型輸入裡，但看得到 ≠ 照做）"},
    "PC": {"flags": ["--retry", "none"],
           "template": "workspace_template_pc", "placeholder": False,
           "why": "正控制＝RP 的天花板（講明白了它寫不寫得出來）"},
}
ARM_ORDER = ("RS", "RF", "RP", "PC")

#: pi 的 user 訊息。**逐字照 `docs/VACANT_RUN.md` §7.8**，四臂共用。
#: KS-1（鐵律 1）：沒有「你有責任／會被懲罰」類措辭。
PI_PROMPT = "Read TASK.md and do what it says. Use your tools to write the file."

#: V2 的 placeholder。**必須是那個參數的結尾**（§8.2-1），否則 launcher `SystemExit`。
FEEDBACK_PLACEHOLDER = "{VACANT_FEEDBACK}"

#: launcher 的退出碼（`docs/VACANT_RUN.md` §2）。
EXIT_ACCEPTED, EXIT_REFUSED, EXIT_INFRA_VOID = 0, 20, 22

#: 基建失敗重試次數（鐵律 3：retry×4）。
INFRA_RETRIES = 4

#: **推論模式的釘值**（2026-09-19 裁決：NOTHINK）。`"backend-default"` ＝不送旗標
#: ＝把模式交給後端版本決定，那是 R529 的混淆形狀，所以它不是預設而是要明講的偏離。
DEFAULT_REASONING_EFFORT = "none"
REASONING_CHOICES = ("none", "low", "medium", "high", "backend-default")

#: 期中看：**只有一次、格數固定、量固定、方向固定（只能停）**。
#: `tasks` ＝觸發點（那一層的前幾題，每題四格都要跑完）。
INTERIM: dict[str, dict] = {
    "S1": {"tasks": 15, "fail_n": 45, "fail_floor": 0.45,
           "pc_n": 15, "pc_floor": 0.30},
    "S2": {"tasks": 12, "fail_n": 36, "fail_floor": 0.15,
           "pc_n": 12, "pc_floor": 0.30},
}
#: 終判線（**不變**，收官時用；本檔不執行終判，只把它印在期中判定旁邊，
#: 免得有人把期中的寬線當成終判的線）。
FINAL_LINES: dict[str, dict] = {
    "S1": {"fail_n": 150, "fail_floor": 0.60, "pc_n": 50, "pc_floor": 0.50},
    "S2": {"fail_n": 120, "fail_floor": 0.30, "pc_n": 40, "pc_floor": 0.50},
}
#: 塊邊界探針的間隔（題數）。
PROBE_EVERY: dict[str, int] = {"S1": 15, "S2": 12}

#: 1 分鐘 load 超過這個值就**暫停派工**（不是砍 run）。
DEFAULT_LOAD_PAUSE = 80.0

#: uptime 落盤的間隔（秒）。
UPTIME_EVERY_S = 900.0

#: 回饋正文的固定夾子，用來把 `{block}` 切出來當特徵字串
#: （`vacant/vrun/retry.py::FEEDBACK_BODY` 逐字，那一段是凍結碼）。
_BLOCK_PREFIX = "working directory. They did not all pass.\n\n"
_BLOCK_SUFFIX = "\n\nFix the working directory."

#: 不靠 `{block}` 也一定在的兩條特徵字串（模板本身）。
_TEMPLATE_NEEDLES = (
    ("header", "Acceptance feedback (attempt"),
    ("body", "The checks that ship with this task were run against your"),
)

#: M7_ws 的分類關鍵字。**分類結果與原始清單都落盤**，事後可離線重分類。
_READ_VERBS = ("read", "view", "cat", "open", "get_file", "fetch_file",
               "show_file")
_WRITE_VERBS = ("write", "edit", "create", "replace", "patch", "apply",
                "insert", "append")


# ── 小工具 ────────────────────────────────────────────────────────────────

def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def effort_or_none(effort: str | None) -> str | None:
    """`"backend-default"` ＝**不送旗標**；其餘照送。

    ⚠ 「不送」不是選擇一個模式，是把模式交給後端版本決定——
    1003（0.4.24）預設思考、1004（0.4.17）預設不思考，**同一份 gguf**。
    這個轉換只有這一個地方做，免得別處把 `"backend-default"` 當成一個
    真的可以送出去的值（那會讓 LM Studio 收到一個它不認得的字串）。
    """
    return None if effort in (None, "backend-default") else effort


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def jsonl_append(path: pathlib.Path, rec: dict) -> None:
    """**單次 write 的 append**：多串並行時整列不會被切開（O_APPEND ＋ 一次寫完）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False, sort_keys=False) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()


def load1() -> float | None:
    """1 分鐘 load。拿不到就回 `None`（**不回 0**——沒量到 ≠ 量到 0）。"""
    try:
        return os.getloadavg()[0]
    except (OSError, AttributeError):       # pragma: no cover - 非 POSIX
        return None


def uptime_line() -> str:
    try:
        return subprocess.run(["uptime"], capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except Exception as exc:                # noqa: BLE001
        return f"<uptime 拿不到：{exc!r}>"


# ── manifest 與計畫 ──────────────────────────────────────────────────────

def load_manifest(path: pathlib.Path, *, expect_sha: str) -> tuple[dict, str]:
    """讀 `bank_manifest.json`，**逐位元比對釘死的 sha256**，不相等就拒絕啟動。"""
    got = sha256_file(path)
    if expect_sha and got != expect_sha:
        raise SystemExit(
            f"bank_manifest.json 的 sha256 不是釘死的值。停。\n"
            f"  釘死 {expect_sha}\n  實際 {got}\n"
            f"  （題庫漂了，或你指到別的 manifest。發射前這一條不准繞過。）")
    return json.loads(path.read_text(encoding="utf-8")), got


def bank_dir(manifest_path: pathlib.Path, manifest: dict) -> pathlib.Path:
    """manifest 的 `bank_dir` 是 repo 相對路徑；以 repo 根解析。"""
    return (REPO / manifest["bank_dir"]).resolve()


def plan_rows(manifest: dict) -> list[dict]:
    """360 格的計畫。**確定性**：題照 manifest 的 `task_ids`、臂照輪轉。

    **題塊 × 四臂交錯**（2026-09-19 裁決）：同一題的四格**相鄰**，臂序按
    `task_index mod 4` 輪轉。配上 `--shard k:4`（分片用計畫裡的列號）⇒
    四條流同時在跑同一題的四個臂，而且每條流四臂的量一樣。

    ⚠ 這不是排版偏好。「先發一臂」會讓後端漂移（重載、TTL、負載）變成
    **臂與臂之間的時間混淆**，而 H2 的預測正是「可交換」。
    """
    rows: list[dict] = []
    idx = 0
    for stratum in ("S1", "S2"):
        for pos_in_stratum, tid in enumerate(
                manifest["strata"][stratum]["task_ids"]):
            r = idx % len(ARM_ORDER)
            order = ARM_ORDER[r:] + ARM_ORDER[:r]
            for arm_pos, arm in enumerate(order):
                rows.append({"cell": f"{tid}__{arm}", "task_id": tid,
                             "arm": arm, "stratum": stratum,
                             "task_index": idx, "task_pos": pos_in_stratum,
                             "arm_pos": arm_pos})
            idx += 1
    return rows


def plan_bytes(rows: list[dict]) -> bytes:
    return ("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                    for r in rows)).encode("utf-8")


def write_plan(out: pathlib.Path, manifest: dict, manifest_sha: str,
               *, force: bool = False) -> dict:
    """把計畫寫成 `plan.jsonl`，並把它的 sha256 **簽進第一筆收據**。

    ⚠ **永不覆寫**（`--force` 也只在內容逐位元相同時放行）：驅動與 bash 都可能
    正在按位元組偏移續讀這個檔，覆寫會讓讀的人跳過整塊。**只 append 是安全的。**
    """
    out.mkdir(parents=True, exist_ok=True)
    rows = plan_rows(manifest)
    blob = plan_bytes(rows)
    sha = sha256_bytes(blob)
    p = out / "plan.jsonl"
    if p.exists():
        cur = p.read_bytes()
        if cur != blob and not force:
            raise SystemExit(
                f"{p} 已存在且內容不同。**不覆寫**（有人可能正在按偏移續讀它）。\n"
                f"  現有 sha256 {sha256_bytes(cur)}\n  要寫的  {sha}")
        if cur == blob:
            return {"plan_path": str(p), "plan_sha256": sha,
                    "n_cells": len(rows), "receipt": "既有，未重寫"}
    p.write_bytes(blob)
    ident, book = Identity.generate(), Logbook()
    entry = book.append("r535_plan", {
        "run": "R535", "created": now_iso(),
        "plan_sha256": sha, "plan_bytes": len(blob), "n_cells": len(rows),
        "arms": list(ARM_ORDER),
        "n_by_stratum": {s: manifest["strata"][s]["n"] for s in ("S1", "S2")},
        "bank_manifest_sha256": manifest_sha,
        "bank_dir": manifest["bank_dir"],
        "driver": "ops/gain/r535/run_r535.py",
        "note": ("收官對帳：360 格每格都必須「有一列」或「明寫 void 原因」，"
                 "少一格或多一格都判 INVALID。"),
    }, ident, ts_ms=int(time.time() * 1000))
    book.save(out / "plan_receipt.ndjson")
    (out / "plan_receipt.pub.json").write_text(json.dumps(
        {"vacant_id": ident.vacant_id, "pub_hex": pub_to_hex(ident.pub)},
        ensure_ascii=False), encoding="utf-8")
    return {"plan_path": str(p), "plan_sha256": sha, "n_cells": len(rows),
            "receipt_hash": entry.hash(),
            "receipt": str(out / "plan_receipt.ndjson")}


def read_plan(out: pathlib.Path) -> tuple[list[dict], str, int]:
    """**一次讀完**（不按偏移續讀），並把當下的 sha256 與長度一起回傳。

    後來有人 append 了 ⇒ 我們驅的是哪一段前綴，driver 日誌說得出來。
    """
    p = out / "plan.jsonl"
    if not p.exists():
        raise SystemExit(f"找不到 {p}。先跑一次 `--write-plan`。")
    blob = p.read_bytes()
    rows = []
    for k, line in enumerate(blob.decode("utf-8").splitlines()):
        if line.strip():
            # `plan_index` ＝**計畫裡的列號**。`--shard` 分的是它，不是過濾後的
            # 位置——同一題的四格相鄰 ⇒ `plan_index % 4` 就是 `arm_pos` ⇒
            # `--shard k:4` 拿到的是每一題的第 k 個臂。用過濾後的位置分片，
            # 只要有人加了 `--tasks` 就會把四流跑成四個不同的題集。
            rows.append({**json.loads(line), "plan_index": k})
    return rows, sha256_bytes(blob), len(blob)


def check_plan_receipt(out: pathlib.Path, plan_sha: str) -> dict:
    """驗「plan.jsonl 的 sha256 真的被簽進第一筆收據」。驗不過就停。"""
    rp, pp = out / "plan_receipt.ndjson", out / "plan_receipt.pub.json"
    if not rp.exists() or not pp.exists():
        raise SystemExit(f"找不到計畫收據（{rp}）。先跑一次 `--write-plan`。")
    from vacant.identity import PublicIdentity
    book = Logbook.load(rp)
    pub = json.loads(pp.read_text(encoding="utf-8"))
    who = PublicIdentity.from_hex(pub["vacant_id"], pub["pub_hex"])
    if not book.verify_chain(who):
        raise SystemExit(f"計畫收據驗鏈失敗：{rp}")
    signed = book.entries[0].payload.get("plan_sha256")
    if signed != plan_sha:
        raise SystemExit(
            "plan.jsonl 與第一筆收據對不上（計畫被改過，或你讀到的是別份）。停。\n"
            f"  收據簽的 {signed}\n  現在的檔 {plan_sha}\n"
            "  （只 append 是安全的；append 過就要重簽一份新的計畫收據。）")
    return {"chain_ok": True, "entries": len(book),
            "plan_sha256_signed": signed}


# ── 工作區與 pi 設定 ─────────────────────────────────────────────────────

def materialise_ws(ws: pathlib.Path, task_dir: pathlib.Path, arm: str,
                   manifest: dict) -> list[str]:
    """把樣板檔複製進工作區。

    PC 臂把 `TASK_explicit.md` **改名成 `TASK.md`** 落地，其餘位元組相同——
    否則 PC 不是同一題的天花板（manifest 的 `workspace_template_pc_note`）。
    ⚠ `tests_visible/` 與 `hidden/` **都不進工作區**：`--suite` 一定在工作區外，
    agent 改得到的驗收不是驗收（R534 就是踩這個）。
    """
    ws.mkdir(parents=True, exist_ok=True)
    key = ARMS[arm]["template"]
    names = list(manifest[key])
    landed: list[str] = []
    for name in names:
        src = task_dir / name
        dst = ws / ("TASK.md" if name.startswith("TASK") else name)
        shutil.copy2(src, dst)
        landed.append(f"{name} -> {dst.name}")
    return landed


def write_pi_config(conf_dir: pathlib.Path, *, port: int, model_id: str,
                    reasoning_effort: str | None) -> dict:
    """`PI_CODING_AGENT_DIR` 底下那一份 `models.json`（§7.8 ＋ AGENT_COMPAT §2.4）。

    ⚠ **pi 不吃 `OPENAI_BASE_URL`**，所以這裡是唯一把它指向 proxy 的地方；
    而「我寫了這個檔」不是證據，`requests_seen` 才是。
    """
    conf_dir.mkdir(parents=True, exist_ok=True)
    model: dict = {"id": model_id, "name": "m",
                   "contextWindow": 262144, "maxTokens": 16384}
    if reasoning_effort:
        # 形狀逐字沿用 R534 的 `tap1004nothink`。
        model["samplingParams"] = {"reasoning_effort": reasoning_effort}
    cfg = {"providers": {"vacantproxy": {
        "baseUrl": f"http://127.0.0.1:{port}/v1",
        "api": "openai-completions",
        "apiKey": "sk-whatever",
        "compat": {"supportsDeveloperRole": False,
                   "supportsReasoningEffort": False},
        "models": [model]}}}
    (conf_dir / "models.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


def upstream_base(endpoint: str) -> str:
    """`http://h:1234/v1/chat/completions` → `http://h:1234/v1`。形狀不對就停。"""
    e = endpoint.strip()
    if not e.endswith("/v1/chat/completions"):
        raise SystemExit(
            "端點必須是**完整的** `http://<host>:1234/v1/chat/completions`"
            f"（與 R529／R533 逐字相同），收到：{endpoint!r}。停。\n"
            "  ⚠ 環境變數是 `VACANT_GAIN_API`，不是 `VACANT_ENDPOINT`"
            "（R532 為此誤發兩次打到雲端）。")
    return e[: -len("/chat/completions")]


# ── M7 / F6：從 wire 讀出來的量測 ────────────────────────────────────────

def _needle_variants(text: str) -> list[bytes]:
    """同一條字串在 wire 上的三種長相：原文、`ensure_ascii` 轉義、不轉義。

    少了第二種就會漏掉最常見的一類 client（`json.dumps` 預設把 `—` 寫成
    `\\u2014`），而漏掉的方式是**安靜地回 False**——那正是本檔不准出現的形狀。
    """
    out = [text.encode("utf-8"),
           json.dumps(text)[1:-1].encode("utf-8"),
           json.dumps(text, ensure_ascii=False)[1:-1].encode("utf-8")]
    seen, uniq = set(), []
    for b in out:
        if b not in seen:
            seen.add(b)
            uniq.append(b)
    return uniq


def build_needles(feedback_text: str) -> list[tuple[str, str]]:
    """從回饋全文切出特徵字串。回 `[(kind, text), …]`。"""
    needles: list[tuple[str, str]] = list(_TEMPLATE_NEEDLES)
    if _BLOCK_PREFIX in feedback_text and _BLOCK_SUFFIX in feedback_text:
        block = feedback_text.split(_BLOCK_PREFIX, 1)[1].split(
            _BLOCK_SUFFIX, 1)[0]
        if block.strip():
            needles.append(("block", block.strip()))
            for line in block.splitlines():
                s = line.strip()
                if len(s) >= 16:
                    needles.append(("block_line", s))
    return needles


def _hit(blobs: list[bytes], text: str) -> bool:
    for v in _needle_variants(text):
        for b in blobs:
            if v in b:
                return True
    return False


def wire_slices(run_dir: pathlib.Path, arm: str,
                attempts: list[dict]) -> tuple[dict[int, list[str]], dict]:
    """把 `wire_<ARM>/index.jsonl` 按「每一次嘗試用掉幾通」切成逐次的 call_id。

    對得起來的理由：`requests_seen` 與索引那一列是同一個計數器前後腳寫的
    （`wireproxy._handle`：先 `_index(rec)` 再 `requests_seen += 1`），
    而嘗試的邊界上 agent 行程已經結束、proxy 已經閒置 ⇒ 兩邊相等。
    對不起來就**回 `None` 的理由**，不硬切——沒量到 ≠ 量到 0。
    """
    idx = run_dir / f"wire_{arm}" / "index.jsonl"
    meta: dict = {"index_path": str(idx), "ok": False, "reason": None}
    if not idx.exists():
        meta["reason"] = "wire index 不存在"
        return {}, meta
    lines = [json.loads(s) for s in idx.read_text(
        encoding="utf-8").splitlines() if s.strip()]
    cum_last = 0
    for rec in attempts:
        c = rec.get("requests_seen_cumulative")
        if c is not None:
            cum_last = c
    if cum_last != len(lines):
        meta["reason"] = (f"index 有 {len(lines)} 列，"
                          f"attempts 累計說 {cum_last} 通——對不起來")
        return {}, meta
    out: dict[int, list[str]] = {}
    prev = 0
    for rec in attempts:
        c = rec.get("requests_seen_cumulative")
        if c is None:
            out[rec["attempt"]] = []
            continue
        out[rec["attempt"]] = [r["call_id"] for r in lines[prev:c]]
        prev = c
    meta["ok"] = True
    meta["n_calls"] = len(lines)
    return out, meta


def _req_blobs(run_dir: pathlib.Path, arm: str,
               call_ids: list[str]) -> list[bytes]:
    out = []
    for cid in call_ids:
        p = run_dir / f"wire_{arm}" / f"{cid}.req.bin"
        if p.exists():
            out.append(p.read_bytes())
    return out


def measure_m7_file(run_dir: pathlib.Path, arm_name: str, summary: dict,
                    slices: dict[int, list[str]], slice_meta: dict) -> dict:
    """`M7_file`：回饋文字有沒有進到第 ≥2 次嘗試的任一通 wire。

    `null` 的三種理由分開記，**不合併成 False**：
    沒有第 2 次嘗試／這一臂不產生回饋／wire 對不起來或特徵字串不具鑑別力。
    """
    arm = summary["arm"]
    attempts = summary.get("attempts") or []
    res: dict = {"m7_file": None, "m7_file_reason": None,
                 "m7_file_by_attempt": [], "m7_file_leaky_needles": []}
    if len(attempts) < 2:
        res["m7_file_reason"] = "no_second_attempt"
        return res
    if arm_name == "RS":
        res["m7_file_reason"] = "arm_has_no_feedback_by_policy"
        return res
    if not slice_meta.get("ok"):
        res["m7_file_reason"] = f"wire_unmappable: {slice_meta.get('reason')}"
        return res
    first_blobs = _req_blobs(run_dir, arm, slices.get(1, []))
    any_true, any_checked = False, False
    for rec in attempts:
        n = rec["attempt"]
        if n < 2:
            continue
        prev = attempts[n - 2]
        fb = (prev.get("feedback") or {}).get("text")
        per: dict = {"attempt": n, "found": None, "matched": [],
                     "n_req": len(slices.get(n, []))}
        if not fb:
            per["reason"] = "上一次沒有產生回饋"
            res["m7_file_by_attempt"].append(per)
            continue
        needles = build_needles(fb)
        good = []
        for kind, text in needles:
            if _hit(first_blobs, text):
                res["m7_file_leaky_needles"].append(
                    {"attempt": n, "kind": kind, "text": text[:160]})
            else:
                good.append((kind, text))
        if not good:
            per["reason"] = "needles_not_discriminative"
            res["m7_file_by_attempt"].append(per)
            continue
        blobs = _req_blobs(run_dir, arm, slices.get(n, []))
        found = False
        for kind, text in good:
            if _hit(blobs, text):
                found = True
                per["matched"].append({"kind": kind, "text": text[:160]})
        per["found"] = found
        any_checked = True
        any_true = any_true or found
        res["m7_file_by_attempt"].append(per)
    if not any_checked:
        res["m7_file_reason"] = "no_usable_attempt"
        return res
    res["m7_file"] = bool(any_true)
    return res


def _tool_calls_from_body(blob: bytes) -> list[dict] | None:
    """從一通 request body 裡撈出**這一段對話目前為止的所有工具呼叫**。

    每一通請求都把完整上文重放一次（`docs/AGENT_COMPAT.md` §4.1 對 pi／Codex
    都實測過），所以一次嘗試的最後一通就帶著那一次的全部工具呼叫。
    parse 不動就回 `None`（**不回空陣列**——那會和「真的沒有工具呼叫」同形）。
    """
    try:
        body = json.loads(blob.decode("utf-8"))
    except Exception:                        # noqa: BLE001
        return None
    if not isinstance(body, dict):
        return None
    calls: list[dict] = []
    for m in body.get("messages") or []:
        if not isinstance(m, dict):
            continue
        for tc in m.get("tool_calls") or []:
            fn = (tc.get("function") or {}) if isinstance(tc, dict) else {}
            calls.append({"name": fn.get("name"),
                          "args": str(fn.get("arguments") or "")[:400]})
    return calls


def classify_call(name: str | None, args: str) -> str:
    low = (name or "").lower()
    if "VACANT_FEEDBACK" in args:
        return "read_feedback"
    if "TASK.md" in args and any(v in low for v in _READ_VERBS):
        return "read_task"
    if "solution.py" in args and any(v in low for v in _WRITE_VERBS):
        return "write_solution"
    return "other"


def measure_m7_ws(run_dir: pathlib.Path, summary: dict,
                  slices: dict[int, list[str]], slice_meta: dict) -> dict:
    """`M7_ws`：第 ≥2 次嘗試裡「`read TASK.md`／`write solution.py` 以外」的比例。

    **原始清單一起落盤**（`m7_ws_calls`）：分類器是我們猜的，證據不是。
    事後要換分類規則，用那份清單離線重算即可，不必重跑任何一格。
    """
    arm = summary["arm"]
    attempts = summary.get("attempts") or []
    res: dict = {"m7_ws": None, "m7_ws_reason": None, "m7_ws_ratio": None,
                 "m7_ws_counts": {}, "m7_ws_calls": []}
    if len(attempts) < 2:
        res["m7_ws_reason"] = "no_second_attempt"
        return res
    if not slice_meta.get("ok"):
        res["m7_ws_reason"] = f"wire_unmappable: {slice_meta.get('reason')}"
        return res
    counts: dict[str, int] = {}
    total, parsed_any = 0, False
    for rec in attempts:
        n = rec["attempt"]
        if n < 2:
            continue
        ids = slices.get(n, [])
        if not ids:
            continue
        blob = _req_blobs(run_dir, arm, ids[-1:])
        if not blob:
            continue
        calls = _tool_calls_from_body(blob[0])
        if calls is None:
            continue
        parsed_any = True
        for c in calls:
            kind = classify_call(c["name"], c["args"])
            counts[kind] = counts.get(kind, 0) + 1
            total += 1
            res["m7_ws_calls"].append(
                {"attempt": n, "name": c["name"], "kind": kind,
                 "args": c["args"][:200]})
    if not parsed_any:
        res["m7_ws_reason"] = "no_parsable_request_body"
        return res
    other = total - counts.get("read_task", 0) - counts.get(
        "write_solution", 0)
    res["m7_ws_counts"] = {**counts, "total": total, "other_total": other}
    res["m7_ws_ratio"] = (other / total) if total else None
    if total == 0:
        res["m7_ws_reason"] = "no_tool_calls_in_attempt_ge2"
        return res
    res["m7_ws"] = bool(other > 0)
    #: 取樣方式要落盤：我們讀的是**每一次嘗試的最後一通**（那一通帶著該次的
    #: 完整上文）。框架如果做了脈絡壓縮，早期的工具呼叫會不在裡面——
    #: 那是這個量測的已知上界，不是 bug，但看數字的人要知道。
    res["m7_ws_source"] = "last_request_per_attempt"
    return res


def measure_f6(arm_name: str, summary: dict) -> dict:
    """`F6`：RP 臂的每個第 ≥2 次嘗試 `feedback_in_prompt_bytes > 0`。"""
    attempts = summary.get("attempts") or []
    res: dict = {"f6": None, "f6_reason": None, "f6_bytes_by_attempt": []}
    later = [a for a in attempts if a["attempt"] >= 2]
    for a in attempts:
        res["f6_bytes_by_attempt"].append(
            {"attempt": a["attempt"],
             "feedback_in_prompt_bytes": a.get("feedback_in_prompt_bytes")})
    if arm_name != "RP":
        res["f6_reason"] = "arm_is_not_RP"
        return res
    if not later:
        res["f6_reason"] = "no_second_attempt"
        return res
    vals = [a.get("feedback_in_prompt_bytes") for a in later]
    if any(v is None for v in vals):
        res["f6_reason"] = "field_missing"
        return res
    res["f6"] = all(v > 0 for v in vals)
    return res


def sse_usage(blob: bytes) -> dict | None:
    """從 SSE 回應裡撈 `usage`。撈不到回 `None`（**不是 `{}`**，不是 0）。

    pi 送的是 `stream:true` ＋ `stream_options:{include_usage:true}`，所以最後
    一個 `data:` chunk 帶 `usage`（實測 vacant-dev 2026-09-18）。但這裡**不假設
    它一定在**：撈不到就是撈不到，回 `None` 讓上層記成 `unmeasured`。
    「沒量到」與「量到 0」在本輪是兩件不同的事——F3 的整個用處就是分開它們。
    """
    found = None
    for line in blob.split(b"\n"):
        s = line.strip()
        if not s.startswith(b"data:"):
            continue
        payload = s[5:].strip()
        if payload == b"[DONE]":
            continue
        try:
            d = json.loads(payload.decode("utf-8"))
        except Exception:                    # noqa: BLE001
            continue
        if isinstance(d, dict) and d.get("usage"):
            found = d["usage"]
    if found is None:
        try:                                 # 非串流的情況（body 就是一包 JSON）
            d = json.loads(blob.decode("utf-8"))
            if isinstance(d, dict) and d.get("usage"):
                found = d["usage"]
        except Exception:                    # noqa: BLE001
            return None
    return found


def reasoning_tokens_of(usage: dict | None) -> int | None:
    if not usage:
        return None
    det = usage.get("completion_tokens_details") or {}
    v = det.get("reasoning_tokens", usage.get("reasoning_tokens"))
    return v if isinstance(v, int) else None


def measure_f3(run_dir: pathlib.Path, arm: str, *, expect: str) -> dict:
    """**F3 兩半，兩半都要**（2026-09-19 裁決）。

    ① 每通 request body 含 `"reasoning_effort": "<expect>"`；
    ② 每通 response `reasoning_tokens == 0`。

    任一違反 ⇒ 該格 `INVALID`。第三種狀態是 `unmeasured`（那一通沒報 usage，
    或 request 根本不該有那個欄位）——**不當成通過**，分開記。

    ⚠ 這一支**逐通掃**，不是只看第一通。R529 的混淆就是「設定對了 ⇒ 全程都對」
    這個推論——中途換模型／換設定的那一通不會自己舉手。
    """
    idx = run_dir / f"wire_{arm}" / "index.jsonl"
    res: dict = {"f3_verdict": None, "f3_expect": expect,
                 "f3_calls": 0, "f3_req_ok": 0, "f3_req_bad": 0,
                 "f3_resp_zero": 0, "f3_resp_nonzero": 0,
                 "f3_resp_unmeasured": 0, "f3_violations": []}
    if not idx.exists():
        res["f3_verdict"] = "unmeasured"
        res["f3_reason"] = "wire index 不存在"
        return res
    lines = [json.loads(s) for s in idx.read_text(
        encoding="utf-8").splitlines() if s.strip()]
    wdir = run_dir / f"wire_{arm}"
    for rec in lines:
        cid = rec.get("call_id")
        req, resp = wdir / f"{cid}.req.bin", wdir / f"{cid}.resp.bin"
        if not req.exists():
            res["f3_resp_unmeasured"] += 1
            continue
        res["f3_calls"] += 1
        got = None
        try:
            body = json.loads(req.read_bytes().decode("utf-8"))
            got = body.get("reasoning_effort")
        except Exception:                    # noqa: BLE001
            got = "<req 不是 JSON>"
        want = None if expect == "backend-default" else expect
        if got == want:
            res["f3_req_ok"] += 1
        else:
            res["f3_req_bad"] += 1
            if len(res["f3_violations"]) < 8:
                res["f3_violations"].append(
                    {"call_id": cid, "half": "request",
                     "want": want, "got": got})
        rt = reasoning_tokens_of(sse_usage(resp.read_bytes())
                                 if resp.exists() else None)
        if rt is None:
            res["f3_resp_unmeasured"] += 1
        elif rt == 0:
            res["f3_resp_zero"] += 1
        else:
            res["f3_resp_nonzero"] += 1
            if len(res["f3_violations"]) < 8:
                res["f3_violations"].append(
                    {"call_id": cid, "half": "response",
                     "reasoning_tokens": rt})
    if res["f3_calls"] == 0:
        res["f3_verdict"] = "unmeasured"
    elif res["f3_req_bad"] or res["f3_resp_nonzero"]:
        res["f3_verdict"] = "violated"
    elif res["f3_resp_unmeasured"]:
        # 有通過的、也有沒量到的 ⇒ **不報 ok**。
        res["f3_verdict"] = "unmeasured"
    else:
        res["f3_verdict"] = "ok"
    return res


def measure_suspect_timeout(run_dir: pathlib.Path, arm: str) -> dict:
    """任一嘗試的可見結果含 `kind == "timeout"` ⇒ 標記，**不當場剔除**。"""
    hits = []
    for p in sorted(run_dir.glob(f"visible_{arm}*.json")):
        try:
            res = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                    # noqa: BLE001
            continue
        for f in res.get("files") or []:
            for c in f.get("cases") or []:
                if c.get("kind") == "timeout":
                    hits.append({"file": p.name, "case": c.get("case")})
    return {"suspect_timeout": bool(hits), "suspect_timeout_hits": hits}


# ── 一格 ──────────────────────────────────────────────────────────────────

class Driver:
    def __init__(self, args, manifest: dict, manifest_sha: str):
        self.a = args
        self.manifest = manifest
        self.manifest_sha = manifest_sha
        self.out = pathlib.Path(args.out).resolve()
        self.bank = bank_dir(pathlib.Path(args.bank_manifest), manifest)
        self.cells_dir = self.out / "cells"
        self.log = self.out / f"driver_{args.stream}.jsonl"
        self.upstream = upstream_base(args.endpoint)
        self._stop = threading.Event()

    # -- 日誌 -------------------------------------------------------------
    def ev(self, kind: str, **kw) -> None:
        jsonl_append(self.log, {"ts": now_iso(), "stream": self.a.stream,
                                "event": kind, **kw})

    def _uptime_thread(self) -> None:
        """**每 15 分鐘記一次 `uptime`**（裁決；load 是派工決策的證據）。"""
        while not self._stop.wait(UPTIME_EVERY_S):
            self.ev("uptime", load1=load1(), uptime=uptime_line())

    # -- load 閘門 --------------------------------------------------------
    def wait_for_load(self) -> None:
        """1 分鐘 load > 門檻就**暫停派工**——不是砍 run（在跑的那一格不動它）。"""
        while True:
            l1 = load1()
            if l1 is None or l1 <= self.a.load_pause:
                return
            self.ev("load_pause", load1=l1, threshold=self.a.load_pause,
                    uptime=uptime_line(), sleep_s=self.a.load_poll_s)
            if self.a.dry_run:
                return
            time.sleep(self.a.load_poll_s)

    # -- 一格 -------------------------------------------------------------
    def cell_argv(self, cell: pathlib.Path, task_id: str, arm: str) -> list[str]:
        spec = ARMS[arm]
        suite = self.bank / task_id / "tests_visible"
        prompt = PI_PROMPT + (FEEDBACK_PLACEHOLDER if spec["placeholder"] else "")
        return [sys.executable, "-m", "vacant.vrun.launcher",
                "--workspace", str(cell / "ws"),
                "--run-dir", str(cell / "run"),
                "--suite", str(suite),
                "--task-id", f"r535_{task_id}_{arm}",
                "--vacant", "1",
                "--sandbox", self.a.sandbox,
                "--test-timeout", str(self.a.test_timeout),
                "--port", str(self.a.pi_port),
                "--timeout", str(self.a.agent_timeout),
                "--json", *spec["flags"],
                "--", self.a.pi_bin, "-p",
                "--provider", "vacantproxy", "--model", "m", prompt]

    def cell_env(self, cell: pathlib.Path) -> dict:
        env = dict(os.environ)
        env["VACANT"] = "1"
        # proxy 的真上游。**這是 `VACANT_GAIN_API` 唯一該去的地方。**
        env["VACANT_RUN_UPSTREAM_OPENAI"] = self.upstream
        # **寫死，不 setdefault**：父行程如果有一把真的雲端金鑰，setdefault 會把它
        # 原封不動轉給本機端點。沒有人會因此收到帳單，但那把鑰匙就留在別人的 log 裡了。
        env["OPENAI_API_KEY"] = "lmstudio"
        env["PI_CODING_AGENT_DIR"] = str(cell / "piconf")
        env["PI_OFFLINE"] = "1"
        env["PI_SKIP_VERSION_CHECK"] = "1"
        env["PYTHONPATH"] = (str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
                             ).rstrip(os.pathsep)
        pib = pathlib.Path(self.a.pi_bin)
        if pib.parent.name and pib.exists():
            env["PATH"] = str(pib.parent) + os.pathsep + env.get("PATH", "")
        return env

    def run_cell(self, row: dict) -> dict | None:
        task_id, arm = row["task_id"], row["arm"]
        cell = self.cells_dir / row["cell"]
        # ── 目錄存在就跳過（多串並行安全、斷點續跑）───────────────────
        try:
            cell.mkdir(parents=True)
        except FileExistsError:
            done = self.cell_done(cell)
            self.ev("skip", cell=row["cell"],
                    reason="run_complete" if done else "dir_exists_not_complete")
            return None
        io = cell / "io.jsonl"
        started = time.time()
        jsonl_append(io, {"ts": now_iso(), "event": "cell_start", **row,
                          "bank_manifest_sha256": self.manifest_sha,
                          "arm_flags": ARMS[arm]["flags"],
                          "upstream": self.upstream,
                          "endpoint_var": "VACANT_GAIN_API"})
        state: dict = {
            "cell": row["cell"], "task_id": task_id, "arm": arm,
            "stratum": row["stratum"], "run_complete": False,
            "cell_status": None, "started": now_iso(),
            "bank_manifest_sha256": self.manifest_sha,
            "arm_flags": ARMS[arm]["flags"], "prompt": PI_PROMPT,
            "prompt_has_placeholder": ARMS[arm]["placeholder"],
            "stream": self.a.stream, "pi_port": self.a.pi_port,
            # **逐格落盤推論模式**，不是只在啟動時檢查一次：
            # `--reconcile` 會拿它跟釘值逐位元比（同 `arm_flags` 的形狀）。
            "reasoning_effort": self.a.reasoning_effort,
            "agent_timeout_s": self.a.agent_timeout,
            "task_index": row.get("task_index"), "task_pos": row.get("task_pos"),
            "arm_pos": row.get("arm_pos"), "plan_index": row.get("plan_index"),
            # HALT 期間跑出來的格子要看得出來（探針說後端換了之後的觀測）。
            "probe_invalid": bool(self.halted()),
        }
        self.write_cell(cell, state)

        landed = materialise_ws(cell / "ws", self.bank / task_id, arm,
                                self.manifest)
        write_pi_config(cell / "piconf", port=self.a.pi_port,
                        model_id=self.a.model,
                        reasoning_effort=effort_or_none(
                            self.a.reasoning_effort))
        state["workspace_files"] = landed
        argv = self.cell_argv(cell, task_id, arm)
        state["launcher_argv"] = argv
        jsonl_append(io, {"ts": now_iso(), "event": "materialised",
                          "files": landed, "argv": argv})
        if self.a.dry_run:
            state.update({"cell_status": "dry_run", "run_complete": False})
            self.write_cell(cell, state)
            return state

        rc, tries, void_reason = None, [], None
        for i in range(1, INFRA_RETRIES + 1):
            if i > 1:
                # 上一次是基建壞掉：把那一次的產物搬開，工作區重鋪，
                # **不要混進正式那一份**（混了就分不出哪一列是量到的）。
                for name in ("run", "ws"):
                    src = cell / name
                    if src.exists():
                        src.rename(cell / f"{name}_void_{i - 1}")
                materialise_ws(cell / "ws", self.bank / task_id, arm,
                               self.manifest)
            t0 = time.time()
            proc = subprocess.run(argv, cwd=str(REPO), env=self.cell_env(cell),
                                  capture_output=True, text=True)
            rc = proc.returncode
            (cell / f"launcher_stdout_{i}.json").write_text(
                proc.stdout or "", encoding="utf-8")
            (cell / f"launcher_stderr_{i}.log").write_text(
                proc.stderr or "", encoding="utf-8")
            tries.append({"try": i, "rc": rc,
                          "wall_s": round(time.time() - t0, 3)})
            jsonl_append(io, {"ts": now_iso(), "event": "launcher_done",
                              "try": i, "rc": rc,
                              "wall_s": round(time.time() - t0, 3),
                              "stderr_tail": (proc.stderr or "")[-600:]})
            if rc in (EXIT_ACCEPTED, EXIT_REFUSED):
                # ── `requests_seen == 0` ＝ **agent 根本沒被中介到**，不是量測 ──
                #  §4.5 的現場版本：`--port` 給 8878 而 `models.json` 寫 8877 ⇒
                #  畫面上只有 pi 自己的 `Connection error.`，而那一格看起來像
                #  「模型答錯了」。判 `infra_void` 並重試，接線壞掉才不會偽裝成 0 分。
                sp = cell / "run" / "run_RUN-ON.json"
                seen = None
                if sp.exists():
                    try:
                        seen = json.loads(sp.read_text(encoding="utf-8")
                                          ).get("requests_seen")
                    except Exception:        # noqa: BLE001
                        seen = None
                if seen:
                    break
                void_reason = (f"requests_seen={seen!r}：agent 沒被中介到"
                               f"（pi 的 models.json 指的埠與 --port "
                               f"{self.a.pi_port} 對不上？），第 {i} 次")
                jsonl_append(io, {"ts": now_iso(), "event": "not_mediated",
                                  "try": i, "requests_seen": seen})
                rc = None
                continue
            if rc == 2:
                # 參數壞了＝驅動的 bug，每一格都會一樣。**停整條流**，不要刷屏。
                void_reason = f"launcher 拒收參數（rc=2）：{(proc.stderr or '')[-400:]}"
                state.update({"cell_status": "driver_bug",
                              "infra_void": void_reason, "run_complete": True,
                              "launcher_tries": tries})
                self.write_cell(cell, state)
                raise SystemExit(void_reason)
            void_reason = f"rc={rc}（infra_void 或未知），第 {i} 次"
        state["launcher_tries"] = tries
        state["launcher_rc"] = rc

        summary_path = cell / "run" / "run_RUN-ON.json"
        if rc not in (EXIT_ACCEPTED, EXIT_REFUSED) or not summary_path.exists():
            # **沒量到 ≠ 量到 0**：accepted 落 null，不落 False。
            state.update({
                "cell_status": "infra_void", "accepted": None,
                "infra_void": void_reason or "run_RUN-ON.json 不存在",
                "m7_file": None, "m7_file_reason": "infra_void",
                "m7_ws": None, "m7_ws_reason": "infra_void",
                "f6": None, "f6_reason": "infra_void",
                "wall_s": round(time.time() - started, 3),
                "run_complete": True, "finished": now_iso()})
            self.write_cell(cell, state)
            jsonl_append(self.out / "cells.jsonl", self.row_of(state))
            self.ev("cell_void", cell=row["cell"], reason=state["infra_void"])
            return state

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        state.update(self.harvest(cell, summary, arm))
        # 這一格跑的期間有人（可能是別條流）舉了 HALT ⇒ 它是「後端換了之後」的觀測。
        state["probe_invalid"] = bool(state.get("probe_invalid")
                                      or self.halted())
        status = "measured"
        if state.get("f3_verdict") == "violated":
            # **F3 任一違反 ⇒ 該格 INVALID**，而且 driver 暫停等人（累計 > 0 格）。
            status = "invalid_f3"
            self.raise_halt("F3 違反（推論模式不是我們送的那個）", {
                "cell": row["cell"], "f3": {k: state.get(k) for k in
                                            ("f3_verdict", "f3_expect",
                                             "f3_calls", "f3_req_bad",
                                             "f3_resp_nonzero",
                                             "f3_resp_unmeasured",
                                             "f3_violations")}})
        state.update({"wall_s": round(time.time() - started, 3),
                      "cell_status": status, "finished": now_iso(),
                      "run_complete": True})
        self.write_cell(cell, state)
        jsonl_append(self.out / "cells.jsonl", self.row_of(state))
        self.ev("cell_done", cell=row["cell"], accepted=state.get("accepted"),
                stop_reason=state.get("stop_reason"),
                attempts=state.get("attempts_used"),
                requests_seen=state.get("requests_seen"),
                m7_file=state.get("m7_file"), m7_ws=state.get("m7_ws"),
                f6=state.get("f6"), wall_s=state["wall_s"])
        return state

    def harvest(self, cell: pathlib.Path, summary: dict, arm_name: str) -> dict:
        """從 launcher 的 summary ＋ wire 把這一格的量測整理出來。"""
        run_dir, arm = cell / "run", summary["arm"]
        attempts = summary.get("attempts") or []
        slices, slice_meta = wire_slices(run_dir, arm, attempts)
        out: dict = {
            "accepted": summary.get("accepted"),
            "refused": summary.get("refused"),
            "stop_reason": summary.get("stop_reason"),
            "infra_void": summary.get("infra_void"),
            "attempts_used": summary.get("attempts_used"),
            "max_attempts": summary.get("max_attempts"),
            "requests_seen": summary.get("requests_seen"),
            "agent_wall_s": summary.get("agent_wall_s"),
            "visible_passed": summary.get("visible_passed"),
            "visible_total": summary.get("visible_total"),
            "ws_start_sha256": summary.get("ws_start_sha256"),
            "ws_end_sha256": summary.get("ws_end_sha256"),
            "verdict_sha256": summary.get("verdict_sha256"),
            "verdict_hash": summary.get("verdict_hash"),
            "wire_digest": summary.get("wire_digest"),
            "wire_slice_meta": slice_meta,
            # **逐次嘗試**都落：三臂的第 1 次就是免費的單發基線。
            "attempts": [{
                "attempt": a["attempt"],
                "accepted": a.get("accepted"),
                "stop_reason": a.get("stop_reason"),
                "visible_passed": a.get("visible_passed"),
                "visible_total": a.get("visible_total"),
                "requests_seen": a.get("requests_seen"),
                "agent_rc": a.get("agent_rc"),
                "agent_timed_out": a.get("agent_timed_out"),
                "agent_wall_s": a.get("agent_wall_s"),
                "argv_sha256": a.get("argv_sha256"),
                "feedback_delivery": a.get("feedback_delivery"),
                "feedback_in_prompt_bytes": a.get("feedback_in_prompt_bytes"),
                "feedback_sha256": (a.get("feedback") or {}).get("sha256"),
                "frozen_path": a.get("frozen_path"),
                "ws_end_sha256": a.get("ws_end_sha256"),
                "reset": a.get("reset"),
            } for a in attempts],
        }
        # **wire 真的去了哪**：`requests_seen > 0` 只證明「有被中介」，
        # 不證明「中介到了對的機器」。端點設錯（R532 的雲端誤發）在
        # `requests_seen` 上完全看不出來，在這一欄看得出來。
        out["wire_upstreams"] = sorted({
            json.loads(s)["upstream"].rsplit("/v1", 1)[0]
            for s in (run_dir / f"wire_{arm}" / "index.jsonl").read_text(
                encoding="utf-8").splitlines() if s.strip()
        }) if (run_dir / f"wire_{arm}" / "index.jsonl").exists() else []
        out["upstream_expected"] = self.upstream
        out["upstream_matches"] = all(
            self.upstream.startswith(u) for u in out["wire_upstreams"]
        ) if out["wire_upstreams"] else None
        out.update(measure_m7_file(run_dir, arm_name, summary, slices,
                                   slice_meta))
        out.update(measure_m7_ws(run_dir, summary, slices, slice_meta))
        out.update(measure_f6(arm_name, summary))
        out.update(measure_f3(run_dir, arm, expect=self.a.reasoning_effort))
        out.update(measure_suspect_timeout(run_dir, arm))
        # `agent_timed_out` 是**正常的嘗試結果不 void**（誠實邊界 7）：
        # 逐次落盤、逐格彙總，收官逐臂逐層印比例。
        out["agent_timed_out_any"] = any(
            bool(a.get("agent_timed_out")) for a in attempts)
        out["agent_timed_out_n"] = sum(
            1 for a in attempts if a.get("agent_timed_out"))
        # `requests_seen == 0` ＝ **agent 根本沒被中介到**（§4.5）。
        # 那不是「模型不想講話」，是接線壞了——當場標出來。
        if not out.get("requests_seen"):
            out["not_mediated"] = True
        return out

    @staticmethod
    def row_of(state: dict) -> dict:
        keys = ("cell", "task_id", "arm", "stratum", "cell_status", "accepted",
                "stop_reason", "attempts_used", "requests_seen", "m7_file",
                "m7_file_reason", "m7_ws", "m7_ws_ratio", "f6",
                "f3_verdict", "reasoning_effort", "probe_invalid",
                "agent_timed_out_n", "suspect_timeout", "infra_void",
                "wall_s", "run_complete")
        return {"ts": now_iso(), **{k: state.get(k) for k in keys}}

    @staticmethod
    def write_cell(cell: pathlib.Path, state: dict) -> None:
        """**邊跑邊寫**（所以讀的人要看 `run_complete`，不要看檔案存在）。"""
        tmp = cell / "cell.json.tmp"
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(cell / "cell.json")

    @staticmethod
    def cell_done(cell: pathlib.Path) -> bool:
        p = cell / "cell.json"
        if not p.exists():
            return False
        try:
            return bool(json.loads(p.read_text(encoding="utf-8")
                                   ).get("run_complete"))
        except Exception:                    # noqa: BLE001
            return False

    # -- 塊邊界探針 ＋ HALT ------------------------------------------------
    def halt_path(self) -> pathlib.Path:
        return self.out / "HALT.json"

    def halted(self) -> dict | None:
        p = self.halt_path()
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:                    # noqa: BLE001
            return {"reason": "HALT.json 讀不動，保守當成 HALT"}

    def raise_halt(self, reason: str, detail: dict) -> None:
        """**暫停等人**，不是自己續跑。之後的格標 `probe_invalid` 直到人確認。"""
        doc = {"ts": now_iso(), "stream": self.a.stream, "reason": reason,
               "detail": detail,
               "how_to_resume": ("人確認過後端沒換之後跑 "
                                 "`run_r535.py --ack-halt '<理由>' --out <OUT>`；"
                                 "HALT 期間跑出來的格子在 --reconcile 會落在 "
                                 "probe_invalid 桶，非空即 INVALID。")}
        try:
            fd = os.open(self.halt_path(), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False, indent=2)
        except FileExistsError:
            pass                              # 別條流先寫了，內容一樣重要
        self.ev("halt", **doc)

    def probe(self, stratum: str, task_pos: int) -> dict:
        """1-token 探針：落盤 model id 與 `reasoning_tokens`。

        ⚠ 這把「那台機器上載的是什麼」從**人的義務**縮成一個落盤欄位——
        但它接不住「同一個 model id、同一個推論模式，檔案內容或載入參數換了」。
        那一條仍然在誠實邊界 5 裡。
        """
        eff = effort_or_none(self.a.reasoning_effort)
        ok, lines, info = probe_endpoint(self.a.endpoint, self.a.model,
                                         reasoning_effort=eff)
        rec = {"ts": now_iso(), "stream": self.a.stream, "stratum": stratum,
               "task_pos": task_pos, "ok": ok, **info}
        jsonl_append(self.out / "probes.jsonl", rec)
        base_p = self.out / "probe_baseline.json"
        if not ok:
            self.raise_halt("探針打不通", rec)
            return rec
        try:
            fd = os.open(base_p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"model": info.get("model"),
                           "reasoning_effort_sent": eff,
                           "first_seen": rec["ts"]}, fh, ensure_ascii=False)
        except FileExistsError:
            pass
        base = json.loads(base_p.read_text(encoding="utf-8"))
        if info.get("model") != base.get("model"):
            self.raise_halt("model id 變了", {**rec, "baseline": base})
        elif eff is not None and (info.get("reasoning_tokens") or 0) > 0:
            self.raise_halt("reasoning_tokens > 0（後端開始思考了）", rec)
        return rec

    # -- 期中看（只有一次）------------------------------------------------
    def interim_gate(self, stratum: str) -> dict | None:
        """觸發點到了就算一次，**`O_EXCL` 寫一次就定案**；回判定或 `None`。"""
        p = self.out / f"interim_{stratum}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        doc = compute_interim(self.out, self.manifest, stratum)
        if doc is None or doc["verdict"] == "NOT_YET":
            return None
        if doc["verdict"] == "UNEVALUABLE":
            # **不寫檔**：寫了就定案了，而資料還沒齊（有 void 格）。
            self.ev("interim_unevaluable", stratum=stratum, **doc["counts"])
            return None
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False, indent=2)
            self.ev("interim_written", stratum=stratum,
                    verdict=doc["verdict"], reasons=doc["reasons"])
        except FileExistsError:
            doc = json.loads(p.read_text(encoding="utf-8"))
        return doc

    # -- 埠獨佔鎖 ---------------------------------------------------------
    def lock_port(self):
        """一個 `--pi-port` 同時只准有一條流。

        pi 吃的是 `models.json` 裡寫死的埠。兩條流共用同一個埠 ⇒ 第二個 proxy
        綁不上，或者更糟——**綁上了，於是 A 流的 agent 打到 B 流的 proxy**，
        兩格的 wire 混在一起而畫面上什麼都看不出來。所以這裡拿一把檔案鎖，
        拿不到就**當場停**，不是警告。
        """
        import fcntl
        p = pathlib.Path(f"/tmp/r535_port_{self.a.pi_port}.lock")
        fh = open(p, "w", encoding="utf-8")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SystemExit(
                f"--pi-port {self.a.pi_port} 已經被另一條流佔著（{p}）。\n"
                "  每條並行流要一個自己的埠——共用會讓兩格的 wire 混在一起，"
                "而那件事在資料上看不出來。停。")
        fh.write(f"{os.getpid()} {self.a.stream} {now_iso()}\n")
        fh.flush()
        return fh

    # -- 主迴圈 -----------------------------------------------------------
    def drive(self, rows: list[dict]) -> int:
        self._portlock = self.lock_port()
        th = threading.Thread(target=self._uptime_thread, daemon=True)
        th.start()
        self.ev("driver_start", n_rows=len(rows), out=str(self.out),
                bank=str(self.bank), upstream=self.upstream,
                pi_bin=self.a.pi_bin, pi_port=self.a.pi_port,
                model=self.a.model, sandbox=self.a.sandbox,
                test_timeout=self.a.test_timeout,
                agent_timeout=self.a.agent_timeout,
                reasoning_effort=self.a.reasoning_effort,
                load1=load1(), uptime=uptime_line())
        n_done = 0
        probed: set[tuple[str, int]] = set()
        try:
            for row in rows:
                if self.a.limit and n_done >= self.a.limit:
                    self.ev("limit_reached", limit=self.a.limit)
                    break
                # ── HALT：探針說後端換了 ⇒ **暫停等人**，不是自己續跑 ──
                h = self.halted()
                if h:
                    self.ev("halted_stop", reason=h.get("reason"),
                            cell=row["cell"])
                    print(f"[r535] HALT：{h.get('reason')}。"
                          f"人確認後跑 --ack-halt。停。", file=sys.stderr)
                    break
                # ── 期中看：觸發點到了就算一次，STOP 就不再派這一層 ──
                iv = self.interim_gate(row["stratum"])
                if iv and iv.get("verdict") == "STOP":
                    self.ev("interim_stop", stratum=row["stratum"],
                            reasons=iv.get("reasons"), cell=row["cell"])
                    print(f"[r535] 期中判定：停 {row['stratum']}"
                          f"（{[r['code'] for r in iv['reasons']]}）。跳過這一層。",
                          file=sys.stderr)
                    continue
                # ── 塊邊界探針（S1 每 15 題、S2 每 12 題）──────────────
                key = (row["stratum"],
                       row.get("task_pos", 0) // PROBE_EVERY[row["stratum"]])
                if row.get("task_pos", 0) % PROBE_EVERY[row["stratum"]] == 0 \
                        and key not in probed:
                    probed.add(key)
                    self.probe(row["stratum"], row.get("task_pos", 0))
                    if self.halted():
                        continue
                self.wait_for_load()
                st = self.run_cell(row)
                if st is not None:
                    n_done += 1
        finally:
            self._stop.set()
        self.ev("driver_end", n_done=n_done, load1=load1(),
                uptime=uptime_line())
        print(f"[r535] stream={self.a.stream} 收了 {n_done} 格 → {self.out}",
              file=sys.stderr)
        return 0


# ── 發射前擋門（`--preflight`）────────────────────────────────────────────

def gate_manifest(manifest_path: pathlib.Path, manifest: dict,
                  manifest_sha: str) -> tuple[bool, list[str]]:
    """④ manifest 的 sha256 ＋ **逐檔** sha256 重驗（題庫沒漂）。"""
    lines = [f"manifest sha256 = {manifest_sha}",
             f"釘死值         = {EXPECTED_MANIFEST_SHA256}",
             f"逐位元相等      = {manifest_sha == EXPECTED_MANIFEST_SHA256}"]
    bank = bank_dir(manifest_path, manifest)
    bad, n = [], 0
    for rel, want in sorted(manifest["files_sha256"].items()):
        p = bank / rel
        n += 1
        if not p.exists():
            bad.append(f"缺檔 {rel}")
            continue
        got = sha256_file(p)
        if got != want:
            bad.append(f"漂了 {rel}: {got} != {want}")
    extra = []
    for p in sorted(bank.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(bank))
            if rel not in manifest["files_sha256"]:
                extra.append(rel)
    lines.append(f"逐檔重驗 {n} 個檔，壞 {len(bad)} 個，manifest 沒列到的 "
                 f"{len(extra)} 個")
    lines += [f"  ✗ {b}" for b in bad[:10]]
    lines += [f"  ? 多出來 {e}" for e in extra[:10]]
    ok = (manifest_sha == EXPECTED_MANIFEST_SHA256 and not bad and not extra)
    return ok, lines


def gate_timing(manifest_path: pathlib.Path, manifest: dict, *,
                sandbox_name: str, limit_s: float,
                scratch: pathlib.Path) -> tuple[bool, list[str]]:
    """① F8 時序門：**用參考解跑同一支驗收 runner**，可見＋隱藏各 ≤ limit_s。

    同一支＝`vacant/vrun/acceptance.py::run_suite`（manifest 寫死「不准另寫第
    二把尺」）。零模型呼叫。
    """
    from vacant.vrun import acceptance
    from vacant.vrun.sandbox import make_sandbox
    bank = bank_dir(manifest_path, manifest)
    scratch.mkdir(parents=True, exist_ok=True)
    sb, _meta = make_sandbox(sandbox_name, workdir=str(scratch))
    rows: list[dict] = []
    for stratum in ("S1", "S2"):
        for tid in manifest["strata"][stratum]["task_ids"]:
            tdir = bank / tid
            ws = scratch / f"ws_{tid}"
            if ws.exists():
                shutil.rmtree(ws)
            ws.mkdir(parents=True)
            shutil.copy2(tdir / "TASK.md", ws / "TASK.md")
            shutil.copy2(tdir / "reference" / "solution.py", ws / "solution.py")
            row = {"task_id": tid, "stratum": stratum}
            for suite in ("visible", "hidden"):
                sdir = tdir / ("tests_visible" if suite == "visible"
                               else "hidden")
                t0 = time.time()
                res = acceptance.run_suite(
                    sb, ws, sdir, suite=suite, task_id=tid,
                    verify_root=scratch / "_verify", timeout_s=30.0)
                row[f"{suite}_s"] = round(time.time() - t0, 3)
                row[f"{suite}_pass"] = bool(res.get("all_pass"))
                row[f"{suite}_n"] = res.get("total")
            row["worst_s"] = max(row["visible_s"], row["hidden_s"])
            rows.append(row)
            shutil.rmtree(ws, ignore_errors=True)
    slow = sorted(rows, key=lambda r: -r["worst_s"])[:5]
    over = [r for r in rows if r["worst_s"] > limit_s]
    refbad = [r for r in rows
              if not (r["visible_pass"] and r["hidden_pass"])]
    lines = [f"{len(rows)} 題，門檻每題可見／隱藏各 ≤ {limit_s} s（牆鐘）",
             f"超過門檻 {len(over)} 題；參考解沒全過 {len(refbad)} 題",
             "最慢 5 題："]
    lines += [f"  {r['task_id']}  visible {r['visible_s']:.2f}s"
              f"  hidden {r['hidden_s']:.2f}s" for r in slow]
    lines += [f"  ✗ 超時 {r['task_id']} {r['worst_s']:.2f}s" for r in over[:10]]
    lines += [f"  ✗ 參考解沒過 {r['task_id']}" for r in refbad[:10]]
    return (not over and not refbad), lines


def probe_endpoint(endpoint: str, model: str, *,
                   reasoning_effort: str | None, max_tokens: int = 32,
                   timeout_s: float = 120.0) -> tuple[bool, list[str], dict]:
    """打一通 trivial 呼叫，回 `(ok, 給人看的幾行, 可落盤的 info)`。

    ⚠ 1003（0.4.24）是 thinking 模式、1004（0.4.17）不是，**同一份 gguf 也會不同**
    ——跨機之前要比的就是這個數字，不是「我載了同一個模型」。
    同一支同時給 `--preflight` 的第 ② 門與**塊邊界探針**用（一份判準，不是兩份）。
    """
    import urllib.request
    payload: dict = {"model": model,
                     "messages": [{"role": "user", "content": "Say OK."}],
                     "max_tokens": max_tokens, "stream": False}
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    req = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer lmstudio"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:                 # noqa: BLE001
        return (False, [f"端點打不通：{endpoint}", f"  {exc!r}"],
                {"endpoint": endpoint, "error": repr(exc),
                 "reasoning_effort_sent": reasoning_effort})
    usage = body.get("usage") or {}
    rt = reasoning_tokens_of(usage)
    txt = ((body.get("choices") or [{}])[0].get("message") or {}).get(
        "content") or ""
    info = {"endpoint": endpoint, "model": body.get("model"),
            "model_wanted": model, "reasoning_tokens": rt,
            "reasoning_effort_sent": reasoning_effort, "usage": usage,
            "elapsed_s": round(time.time() - t0, 2)}
    lines = [
        f"端點 {endpoint}",
        f"  回話 {info['elapsed_s']} s",
        f"  實際 model id      = {body.get('model')!r}（要的是 {model!r}）",
        f"  reasoning_tokens   = {rt!r}"
        f"（None＝這個後端沒報；0＝真的沒思考）",
        f"  reasoning_effort 送出去的值 = {reasoning_effort!r}",
        f"  usage = {json.dumps(usage, ensure_ascii=False)}",
        f"  content[:60] = {txt[:60]!r}",
    ]
    return True, lines, info


def gate_endpoint(endpoint: str, model: str, *,
                  reasoning_effort: str | None) -> tuple[bool, list[str]]:
    """② 端點活著＋model id＋`reasoning_tokens`。

    **NOTHINK 那一輪這一門要求 `reasoning_tokens == 0`**：送了旗標而後端照樣
    思考，代表旗標沒被吃——那件事要死在發射前，不是死在 360 格的資料裡。
    """
    ok, lines, info = probe_endpoint(endpoint, model,
                                     reasoning_effort=reasoning_effort)
    if not ok:
        return False, lines
    if reasoning_effort is not None:
        rt = info.get("reasoning_tokens")
        if rt is None:
            lines.append("  ✗ 後端沒報 reasoning_tokens ⇒ F3 的第二半量不到。"
                         "**沒量到不是通過。**")
            return False, lines
        if rt > 0:
            lines.append(f"  ✗ 送了 reasoning_effort={reasoning_effort!r} "
                         f"但 reasoning_tokens={rt} > 0 ⇒ 旗標沒被吃。停。")
            return False, lines
        lines.append(f"  ✓ 送了 {reasoning_effort!r} 且 reasoning_tokens=0")
    else:
        lines.append("  ⚠ `--reasoning-effort backend-default`＝**不送旗標**＝"
                     "把模式交給後端版本決定。那是 R529 的混淆形狀，"
                     "2026-09-19 裁決是送 `none`。這一門因此判 FAIL。")
        return False, lines
    return True, lines


def gate_pi(pi_bin: str) -> tuple[bool, list[str]]:
    """③ pi 版本**逐字印出來**。"""
    try:
        p = subprocess.run([pi_bin, "--version"], capture_output=True,
                           text=True, timeout=60)
    except Exception as exc:                 # noqa: BLE001
        return False, [f"跑不動 {pi_bin} --version：{exc!r}"]
    out = (p.stdout or "").strip()
    return (p.returncode == 0 and bool(out)), [
        f"{pi_bin} --version → rc={p.returncode}",
        f"  stdout 逐字：{out!r}",
        f"  stderr 逐字：{(p.stderr or '').strip()[:200]!r}"]


def gate_workspace_clean(manifest_path: pathlib.Path,
                         manifest: dict) -> tuple[bool, list[str]]:
    """⑤ 工作區樣板裡 `grep -ril hidden` **零命中**。"""
    bank = bank_dir(manifest_path, manifest)
    names = sorted(set(manifest["workspace_template"]
                       + manifest["workspace_template_pc"]))
    pat = re.compile("hidden", re.IGNORECASE)
    hits, n = [], 0
    for stratum in ("S1", "S2"):
        for tid in manifest["strata"][stratum]["task_ids"]:
            for name in names:
                p = bank / tid / name
                if not p.exists():
                    hits.append(f"缺 {tid}/{name}")
                    continue
                n += 1
                if pat.search(p.read_text(encoding="utf-8")):
                    hits.append(f"{tid}/{name} 出現 'hidden'")
    return (not hits), [f"掃了 {n} 個樣板檔（{', '.join(names)}）",
                        f"命中 {len(hits)} 個"] + [f"  ✗ {h}" for h in hits[:10]]


def gate_suite_outside(out: pathlib.Path, manifest_path: pathlib.Path,
                       manifest: dict) -> tuple[bool, list[str]]:
    """⑥ `--suite` 確實在工作區外——**`resolve()` 之後比**，字串前綴不算數。"""
    bank = bank_dir(manifest_path, manifest)
    cells = (out / "cells").resolve()
    bad, n = [], 0
    for stratum in ("S1", "S2"):
        for tid in manifest["strata"][stratum]["task_ids"]:
            suite = (bank / tid / "tests_visible").resolve()
            hidden = (bank / tid / "hidden").resolve()
            for arm in ARM_ORDER:
                ws = (cells / f"{tid}__{arm}" / "ws").resolve()
                rd = (cells / f"{tid}__{arm}" / "run").resolve()
                n += 1
                for label, p in (("suite", suite), ("hidden", hidden),
                                 ("run-dir", rd)):
                    if p == ws or ws in p.parents:
                        bad.append(f"{tid}__{arm}: {label} 在工作區底下 {p}")
                if ws == rd or rd in ws.parents:
                    bad.append(f"{tid}__{arm}: 工作區在 run-dir 底下")
    return (not bad), [
        f"檢查 {n} 格（resolve() 之後比，不是字串前綴）",
        f"  工作區根 = {cells}", f"  題庫根   = {bank}",
        f"  壞 {len(bad)} 格"] + [f"  ✗ {b}" for b in bad[:10]]


def preflight(args, manifest_path: pathlib.Path, manifest: dict,
              manifest_sha: str) -> int:
    out = pathlib.Path(args.out).resolve()
    scratch = pathlib.Path(args.scratch or (out / "_preflight")).resolve()
    gates: list[tuple[str, bool, list[str]]] = []

    ok, lines = gate_manifest(manifest_path, manifest, manifest_sha)
    gates.append(("④ 題庫沒漂（manifest sha256 ＋ 逐檔 sha256）", ok, lines))

    ok, lines = gate_workspace_clean(manifest_path, manifest)
    gates.append(("⑤ 工作區樣板 grep -ril hidden 零命中", ok, lines))

    ok, lines = gate_suite_outside(out, manifest_path, manifest)
    gates.append(("⑥ --suite 在工作區外（resolve 之後比）", ok, lines))

    ok, lines = gate_pi(args.pi_bin)
    gates.append(("③ pi 版本逐字", ok, lines))

    if args.no_endpoint_probe:
        gates.append(("② 端點活著＋model id＋reasoning_tokens", False,
                      ["--no-endpoint-probe：**沒量**。",
                       "  沒量不是通過（鐵律 3 的 infra_void 同一條）。"]))
    else:
        ok, lines = gate_endpoint(args.endpoint, args.model,
                                  reasoning_effort=effort_or_none(
                                      args.reasoning_effort))
        gates.append(("② 端點活著＋model id＋reasoning_tokens", ok, lines))

    if args.skip_timing:
        gates.append(("① F8 時序門（參考解每題 ≤ 2 s）", False,
                      ["--skip-timing：**沒量**。沒量不是通過。"]))
    else:
        ok, lines = gate_timing(manifest_path, manifest,
                                sandbox_name=args.sandbox,
                                limit_s=args.timing_limit_s, scratch=scratch)
        gates.append((f"① F8 時序門（參考解每題 ≤ {args.timing_limit_s} s）",
                      ok, lines))

    print("=" * 72)
    print(f"R535 發射前擋門　{now_iso()}　out={out}")
    print(f"  load1={load1()}　{uptime_line()}")
    print("=" * 72)
    all_ok = True
    for name, ok, lines in gates:
        all_ok = all_ok and ok
        print(f"\n[{'PASS' if ok else 'FAIL'}] {name}")
        for ln in lines:
            print(f"    {ln}")
    print("\n" + "=" * 72)
    print(f"結論：{'全過 ⇒ 准發' if all_ok else '有 FAIL ⇒ 不准發'}")
    print("=" * 72)
    rec = {"ts": now_iso(), "event": "preflight", "all_ok": all_ok,
           "gates": [{"name": n, "ok": o} for n, o, _ in gates],
           "bank_manifest_sha256": manifest_sha}
    out.mkdir(parents=True, exist_ok=True)
    jsonl_append(out / "preflight.jsonl", rec)
    return 0 if all_ok else 1


# ── CLI ───────────────────────────────────────────────────────────────────

def compute_interim(out: pathlib.Path, manifest: dict,
                    stratum: str) -> dict | None:
    """算那一層的期中判定。**只算，不決定要不要寫檔**（寫檔＝定案）。

    回 `verdict` ∈ {`NOT_YET`（觸發點還沒到）、`UNEVALUABLE`（跑完了但有 void 格，
    分母不是釘死的那個數）、`STOP`、`CONTINUE`}。

    ⚠ 四句話，一句都不准改：
      **期中看只有一次。格數固定。量固定。方向固定（只能停，不能改門檻或臂）。**
    """
    cfg = INTERIM[stratum]
    tasks = manifest["strata"][stratum]["task_ids"][: cfg["tasks"]]
    cells_dir = out / "cells"
    fail_hits, fail_n, pc_hits, pc_n = 0, 0, 0, 0
    not_complete, unmeasured = [], []
    for tid in tasks:
        for arm in ARM_ORDER:
            cj = cells_dir / f"{tid}__{arm}" / "cell.json"
            if not cj.exists():
                not_complete.append(f"{tid}__{arm}")
                continue
            st = json.loads(cj.read_text(encoding="utf-8"))
            if not st.get("run_complete"):
                not_complete.append(f"{tid}__{arm}")
                continue
            atts = st.get("attempts") or []
            a1 = atts[0] if atts else None
            if st.get("cell_status") != "measured" or a1 is None \
                    or a1.get("accepted") is None:
                unmeasured.append(f"{tid}__{arm}")
                continue
            if arm == "PC":
                pc_n += 1
                pc_hits += 1 if a1["accepted"] else 0
            else:
                fail_n += 1
                fail_hits += 1 if not a1["accepted"] else 0
    if not_complete:
        return {"verdict": "NOT_YET", "stratum": stratum,
                "counts": {"missing": len(not_complete)}}
    counts = {"fail_n": fail_n, "fail_expected": cfg["fail_n"],
              "pc_n": pc_n, "pc_expected": cfg["pc_n"],
              "unmeasured": len(unmeasured)}
    if fail_n != cfg["fail_n"] or pc_n != cfg["pc_n"]:
        return {"verdict": "UNEVALUABLE", "stratum": stratum,
                "counts": counts, "unmeasured": unmeasured,
                "why": ("格數固定＝分母釘死。有 void 格就不是那個分母，"
                        "**這時候不准寫判定**——寫了就定案了。"
                        "把 void 的格子重跑齊再說。")}
    fail_rate = fail_hits / fail_n
    pc_rate = pc_hits / pc_n
    reasons = []
    if fail_rate < cfg["fail_floor"]:
        reasons.append({"code": "NOT_TRIGGERED",
                        "metric": "RS/RF/RP 合併 attempt-1 可見失敗率",
                        "value": round(fail_rate, 4), "n": fail_n,
                        "floor": cfg["fail_floor"],
                        "say": (f"停 {stratum}，記 NOT_TRIGGERED"
                                f"（期中，n={fail_n}）")})
    if pc_rate < cfg["pc_floor"]:
        reasons.append({"code": "CEILING_TOO_LOW",
                        "metric": "PC attempt-1 通過率",
                        "value": round(pc_rate, 4), "n": pc_n,
                        "floor": cfg["pc_floor"],
                        "say": (f"停 {stratum}，記 CEILING_TOO_LOW"
                                f"（期中，n={pc_n}）")})
    return {
        "verdict": "STOP" if reasons else "CONTINUE",
        "stratum": stratum, "ts": now_iso(),
        "fail_rate": round(fail_rate, 4), "fail_hits": fail_hits,
        "pc_rate": round(pc_rate, 4), "pc_hits": pc_hits,
        "counts": counts, "reasons": reasons,
        "interim_lines": cfg, "final_lines": FINAL_LINES[stratum],
        "rule": ("期中看只有一次。格數固定。量固定。方向固定（只能停，"
                 "不能改任何門檻或臂）。落在停止線與終判線之間 ⇒ 續發，"
                 "由終判裁。停止線比終判線寬是刻意的 futility boundary："
                 "真值 0.6 時 n=45 的觀測 SD ≈ 0.073，0.45 在 2 SD 之外，"
                 "誤停約 2%；設計意圖 0.8 時誤停 ≈ 0。"),
    }


def reconcile(out: pathlib.Path, manifest: dict, msha: str,
              expect_effort: str = DEFAULT_REASONING_EFFORT) -> int:
    """收官對帳：**360 格每格都必須「有一列」或「明寫 void 原因」**。

    少一格或多一格都判 `INVALID`（裁決 2026-09-19）。零模型呼叫。
    這一支刻意不看分數——分數是 `score_r535.py` 的事，這裡只問「跑過了沒有、
    沒跑的話說不說得出為什麼」。
    """
    rows, plan_sha, _ = read_plan(out)
    chain = check_plan_receipt(out, plan_sha)
    want = {r["cell"] for r in rows}
    cells_dir = out / "cells"
    have = {p.name for p in cells_dir.iterdir() if p.is_dir()} \
        if cells_dir.is_dir() else set()
    buckets: dict[str, list[str]] = {
        "measured": [], "infra_void": [], "claimed_not_complete": [],
        "never_started": [], "not_in_plan": sorted(have - want),
        # ⚠ 下面兩桶查的是「**跑的時候到底是不是這一臂／這一份題庫**」。
        #   `plan.jsonl` 只釘住「跑哪 360 格」，釘不住「怎麼跑」——一格被標成
        #   `RS` 卻用 RF 的旗標跑（中途改 `ARMS`、某條流用了舊 checkout、
        #   手動補跑時打錯旗標），舊版對帳照樣說 OK。整個實驗的立論是
        #   「除了旗標以外全部相同」，所以這一條不是形式檢查。
        "flags_mismatch": [], "bank_mismatch": [],
        # ⚠ 同一個形狀再用三次（2026-09-19 裁決：「不要只在啟動時檢查一次」）：
        #   資料本來就逐格落在 `cell.json`，這裡負責**比對**。
        #   `effort_mismatch`＝這一格跑的推論模式不是釘死的那個；
        #   `f3_violation`＝那一格的 wire 逐通掃出來「送的／回的」對不上；
        #   `probe_invalid`＝塊邊界探針舉了 HALT 之後才跑出來的觀測。
        "effort_mismatch": [], "f3_violation": [], "f3_unmeasured": [],
        "probe_invalid": []}
    detail: list[dict] = []
    for r in rows:
        cell = cells_dir / r["cell"]
        if not cell.is_dir():
            buckets["never_started"].append(r["cell"])
            detail.append({**r, "state": "never_started"})
            continue
        cj = cell / "cell.json"
        if not cj.exists():
            buckets["claimed_not_complete"].append(r["cell"])
            detail.append({**r, "state": "claimed_no_cell_json"})
            continue
        st = json.loads(cj.read_text(encoding="utf-8"))
        if not st.get("run_complete"):
            buckets["claimed_not_complete"].append(r["cell"])
            detail.append({**r, "state": "not_complete",
                           "cell_status": st.get("cell_status")})
            continue
        want_flags = list(ARMS[r["arm"]]["flags"])
        got_flags = list(st.get("arm_flags") or [])
        if got_flags != want_flags:
            buckets["flags_mismatch"].append(r["cell"])
            detail.append({**r, "state": "flags_mismatch",
                           "want_flags": want_flags, "got_flags": got_flags})
            continue
        got_bank = st.get("bank_manifest_sha256")
        if got_bank != msha:
            buckets["bank_mismatch"].append(r["cell"])
            detail.append({**r, "state": "bank_mismatch",
                           "want_bank": msha,
                           "got_bank": got_bank})
            continue
        got_eff = st.get("reasoning_effort")
        if got_eff != expect_effort:
            buckets["effort_mismatch"].append(r["cell"])
            detail.append({**r, "state": "effort_mismatch",
                           "want_effort": expect_effort, "got_effort": got_eff})
            continue
        if st.get("probe_invalid"):
            buckets["probe_invalid"].append(r["cell"])
            detail.append({**r, "state": "probe_invalid",
                           "note": "塊邊界探針舉了 HALT 之後才跑出來的觀測"})
            continue
        f3v = st.get("f3_verdict")
        if f3v == "violated":
            buckets["f3_violation"].append(r["cell"])
            detail.append({**r, "state": "f3_violation",
                           "f3": {k: st.get(k) for k in
                                  ("f3_calls", "f3_req_bad", "f3_resp_nonzero",
                                   "f3_violations")}})
            continue
        if f3v == "unmeasured" and st.get("cell_status") == "measured":
            # **沒量到不是通過**，但也不是違反——分開一桶，不判紅、要人看見。
            buckets["f3_unmeasured"].append(r["cell"])
        kind = ("measured" if st.get("cell_status") == "measured"
                else "infra_void")
        buckets[kind].append(r["cell"])
        detail.append({**r, "state": kind, "accepted": st.get("accepted"),
                       "stop_reason": st.get("stop_reason"),
                       "infra_void": st.get("infra_void"),
                       "requests_seen": st.get("requests_seen"),
                       "arm_flags": got_flags})
    ok = (len(rows) == len(plan_rows(manifest))
          and not buckets["not_in_plan"]
          and not buckets["never_started"]
          and not buckets["claimed_not_complete"]
          and not buckets["flags_mismatch"]
          and not buckets["bank_mismatch"]
          and not buckets["effort_mismatch"]
          and not buckets["f3_violation"]
          and not buckets["probe_invalid"])
    doc = {"run": "R535", "ts": now_iso(), "out": str(out),
           "plan_sha256": plan_sha, "plan_chain": chain,
           "n_plan": len(rows), "n_expected": len(plan_rows(manifest)),
           "counts": {k: len(v) for k, v in buckets.items()},
           "verdict": "OK" if ok else "INVALID",
           "rule": ("360 格每格都必須「有一列」或「明寫 void 原因」，"
                    "少一格或多一格都判 INVALID；"
                    "另外每一格落盤的 arm_flags 與 bank_manifest_sha256 "
                    "都必須與本檔的釘值逐位元相同——plan 釘住「跑哪些格」，"
                    "這兩桶釘住「怎麼跑的、用哪份題庫」；"
                    "effort_mismatch／f3_violation／probe_invalid 三桶釘住"
                    "「跑的時候後端是不是同一個推論模式、同一台機器」。"
                    "f3_unmeasured 不判紅但要人看見——沒量到不是通過。"),
           "expect_reasoning_effort": expect_effort,
           "interim": {s: (json.loads((out / f"interim_{s}.json").read_text(
               encoding="utf-8")) if (out / f"interim_{s}.json").exists()
               else None) for s in ("S1", "S2")},
           "halt": (json.loads((out / "HALT.json").read_text(encoding="utf-8"))
                    if (out / "HALT.json").exists() else None),
           "buckets": buckets, "cells": detail}
    (out / "reconcile.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: doc[k] for k in
                      ("n_plan", "n_expected", "counts", "verdict")},
                     ensure_ascii=False, indent=2))
    for k in ("never_started", "claimed_not_complete", "not_in_plan",
              "flags_mismatch", "bank_mismatch", "effort_mismatch",
              "f3_violation", "f3_unmeasured", "probe_invalid"):
        if buckets[k]:
            print(f"  {k}（{len(buckets[k])}）：{buckets[k][:12]}")
    print(f"→ {out / 'reconcile.json'}")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="run_r535.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "R535 發射驅動：四臂（RS／RF／RP／PC）× 90 題（S1 50／S2 40）＝ 360 格，"
            "每格跑一次 `vacant run`（vacant/vrun/launcher.py）。\n"
            "不出題、不寫預註冊、不計分（計分＝ops/gain/r535/score_r535.py）。"),
        epilog=(
            "順序：\n"
            "  1) --preflight        六道門全過才准發（零模型呼叫，除了端點那一次 trivial 呼叫）\n"
            "  2) --write-plan       產 plan.jsonl（360 列）＋把它的 sha256 簽進第一筆收據\n"
            "  3) （多串並行）每條流一個 --stream 名字與一個 --pi-port\n\n"
            "端點：`VACANT_GAIN_API=http://<host>:1234/v1/chat/completions`"
            "（**不是** VACANT_ENDPOINT）。\n"
            "「我設了設定」不是證據——要看逐格的 `requests_seen`。"))
    ap.add_argument("--out", required=True, help="run 目錄（plan／cells／日誌都在這）")
    ap.add_argument("--bank-manifest", default=str(HERE / "bank_manifest.json"),
                    help="題庫 manifest（預設 ops/gain/r535/bank_manifest.json）")
    ap.add_argument("--expect-manifest-sha256", default=EXPECTED_MANIFEST_SHA256,
                    help="釘死的 manifest sha256；不相等就拒絕啟動")
    ap.add_argument("--endpoint", default=os.environ.get("VACANT_GAIN_API", ""),
                    help="完整的 http://<host>:1234/v1/chat/completions"
                         "（預設讀 $VACANT_GAIN_API）")
    ap.add_argument("--model", default="gemma-4-12b-it-qat")
    ap.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT,
                    choices=list(REASONING_CHOICES),
                    help="送進 models.json 的 samplingParams。"
                         f"**預設 {DEFAULT_REASONING_EFFORT!r}**（2026-09-19 裁決："
                         "NOTHINK）。`backend-default`＝不送旗標＝把模式交給後端"
                         "版本決定（1003 預設思考、1004 預設不思考，同一份 gguf）"
                         "——那是 R529 的混淆形狀，preflight 會判 FAIL")
    ap.add_argument("--pi-bin", default="pi", help="pi 執行檔（0.85.1）")
    ap.add_argument("--pi-port", type=int, default=8877,
                    help="proxy 固定埠（§7.8 用 8877）。**每條並行流要不同的埠**"
                         "——pi 吃設定檔不吃環境變數，埠對不上 ⇒ requests_seen=0")
    ap.add_argument("--sandbox", default="none",
                    help="驗收沙箱後端（裁決：R535 用 none，不降權 ⇒ 不再造跨 uid 孤兒）")
    ap.add_argument("--test-timeout", type=float, default=30.0)
    ap.add_argument("--agent-timeout", type=float, default=600.0,
                    help="單次嘗試的 agent 逾時（秒，**預設 600**＝裁決值）。"
                         "300 會砍掉冒煙量到的 314 s 那一格（THINK 下的 ls -R）；"
                         "900 的最壞情況是 360×900/4 約 22 小時。600 ＝ 2x 最壞觀測。"
                         "⚠ 不對稱：太小 ⇒ **假逾時汙染量測**（把「超時」記成「答錯」，"
                         "那正是本輪白跑風險第一名）；太大 ⇒ 一格卡住占一條流 10 分鐘。"
                         "`agent_timed_out=true` 是**正常的嘗試結果不 void**"
                         "（四臂一視同仁）；逐臂逐層的比例任一格超過兩成 ⇒ "
                         "收官必須寫「該比較受預算約束」")
    ap.add_argument("--stream", default="s1", help="這條流的名字（日誌檔名用）")
    ap.add_argument("--shard", default=None,
                    help="把計畫切給多條流：`i:n`（例 0:4）。與『目錄存在就跳過』"
                         "併用，兩層保險")
    ap.add_argument("--arms", default=",".join(ARM_ORDER),
                    help="只跑這些臂（逗號分隔）")
    ap.add_argument("--stratum", default=None, choices=["S1", "S2"])
    ap.add_argument("--tasks", default=None, help="只跑這些 task_id（逗號分隔）")
    ap.add_argument("--limit", type=int, default=0, help="這條流最多收幾格（0＝不限）")
    ap.add_argument("--load-pause", type=float, default=DEFAULT_LOAD_PAUSE,
                    help="1 分鐘 load 超過就**暫停派工**（不是砍 run）")
    ap.add_argument("--load-poll-s", type=float, default=60.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="鋪工作區、印出要跑的命令，但不 spawn agent")
    ap.add_argument("--preflight", action="store_true", help="只跑發射前擋門")
    ap.add_argument("--write-plan", action="store_true",
                    help="產 plan.jsonl ＋ 簽第一筆收據（**不覆寫**既有的）")
    ap.add_argument("--reconcile", action="store_true",
                    help="收官對帳：360 格每格都要「有一列」或「明寫 void 原因」，"
                         "少一格或多一格都判 INVALID（零模型呼叫）")
    ap.add_argument("--interim", default=None, choices=["S1", "S2"],
                    help="印那一層的期中判定（**只讀不寫**，不會定案；"
                         "定案是 driver 在觸發點自己 O_EXCL 寫一次）")
    ap.add_argument("--ack-halt", default=None, metavar="理由",
                    help="人確認過後端沒換 ⇒ 解除 HALT（把 HALT.json 改名存證，"
                         "理由寫進去）。**只有人能下這個，driver 不會自己解**")
    ap.add_argument("--force-plan", action="store_true")
    ap.add_argument("--timing-limit-s", type=float, default=2.0)
    ap.add_argument("--skip-timing", action="store_true",
                    help="跳過 F8 時序門。**跳過＝沒量，preflight 會判 FAIL**")
    ap.add_argument("--no-endpoint-probe", action="store_true",
                    help="不打端點。**不打＝沒量，preflight 會判 FAIL**")
    ap.add_argument("--scratch", default=None, help="F8 時序門的暫存目錄")
    return ap


def select(rows: list[dict], args) -> list[dict]:
    arms = {a.strip() for a in args.arms.split(",") if a.strip()}
    bad = arms - set(ARM_ORDER)
    if bad:
        raise SystemExit(f"不認識的臂 {sorted(bad)}，只有 {list(ARM_ORDER)}")
    tasks = ({t.strip() for t in args.tasks.split(",") if t.strip()}
             if args.tasks else None)
    out = [r for r in rows
           if r["arm"] in arms
           and (args.stratum is None or r["stratum"] == args.stratum)
           and (tasks is None or r["task_id"] in tasks)]
    if args.shard:
        i, n = (int(x) for x in args.shard.split(":"))
        if not (0 <= i < n):
            raise SystemExit(f"--shard {args.shard} 不合法（要 0 <= i < n）")
        # **用計畫裡的列號分**（見 `read_plan`）：`--shard k:4` ⇒ 每一題的第 k 個臂。
        out = [r for r in out if r.get("plan_index", 0) % n == i]
    return out


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    mpath = pathlib.Path(args.bank_manifest).resolve()
    manifest, msha = load_manifest(mpath, expect_sha=args.expect_manifest_sha256)

    if args.preflight:
        return preflight(args, mpath, manifest, msha)

    out = pathlib.Path(args.out).resolve()
    if args.reconcile:
        return reconcile(out, manifest, msha,
                         expect_effort=args.reasoning_effort)
    if args.interim:
        doc = compute_interim(out, manifest, args.interim)
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        p = out / f"interim_{args.interim}.json"
        print(f"（**只讀不寫**。已定案的判定："
              f"{p if p.exists() else '還沒有'}）", file=sys.stderr)
        return 0 if (doc or {}).get("verdict") in ("CONTINUE", "NOT_YET") else 1
    if args.ack_halt:
        p = out / "HALT.json"
        if not p.exists():
            print("沒有 HALT.json，不用解。", file=sys.stderr)
            return 0
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["acked"] = {"ts": now_iso(), "by": "human", "why": args.ack_halt}
        dst = out / f"HALT_acked_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
        dst.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        p.unlink()
        # ⚠ **HALT 期間跑出來的格子不會因此變乾淨**：它們的 `probe_invalid`
        #   已經落盤，`--reconcile` 照樣把它們算進那一桶。解除的是「能不能繼續派工」。
        print(f"HALT 已解除，存證 → {dst}\n"
              f"⚠ HALT 期間已經跑出來的格子仍然標著 probe_invalid，"
              f"--reconcile 照樣判 INVALID。那是設計。")
        return 0
    if args.write_plan:
        info = write_plan(out, manifest, msha, force=args.force_plan)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0

    if not args.endpoint:
        raise SystemExit(
            "沒有端點。設 `VACANT_GAIN_API=http://<host>:1234/v1/chat/completions`"
            " 或給 `--endpoint`。\n"
            "  ⚠ **不是** `VACANT_ENDPOINT`（那個只管 substrate.py）——"
            "R532 為此誤發兩次打到雲端。")
    rows, plan_sha, plan_len = read_plan(out)
    chain = check_plan_receipt(out, plan_sha)
    todo = select(rows, args)
    d = Driver(args, manifest, msha)
    d.ev("plan_read", plan_sha256=plan_sha, plan_bytes=plan_len,
         n_rows=len(rows), n_selected=len(todo), **chain)
    if len(rows) != len(plan_rows(manifest)):
        d.ev("plan_size_mismatch", got=len(rows),
             want=len(plan_rows(manifest)),
             note="收官對帳：少一格或多一格都判 INVALID")
    return d.drive(todo)


if __name__ == "__main__":
    raise SystemExit(main())
