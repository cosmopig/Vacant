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

## 落盤與斷點續跑

```
<out>/plan.jsonl              360 格的計畫（**只 append 安全，永不覆寫**）
<out>/plan_receipt.ndjson     第一筆收據簽的就是 plan.jsonl 的 sha256
<out>/plan_receipt.pub.json   公鑰（私鑰不落盤，RECORD_SPEC §7）
<out>/driver_<stream>.jsonl   driver 事件（含每 15 分鐘一筆 uptime）
<out>/cells.jsonl             每格收完 append 一列（對帳用）
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
    """360 格的計畫。**確定性**：臂照 `ARM_ORDER`、題照 manifest 的 `task_ids`。"""
    rows: list[dict] = []
    for stratum in ("S1", "S2"):
        for tid in manifest["strata"][stratum]["task_ids"]:
            for arm in ARM_ORDER:
                rows.append({"cell": f"{tid}__{arm}", "task_id": tid,
                             "arm": arm, "stratum": stratum})
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
    rows = [json.loads(line) for line in blob.decode("utf-8").splitlines()
            if line.strip()]
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
        }
        self.write_cell(cell, state)

        landed = materialise_ws(cell / "ws", self.bank / task_id, arm,
                                self.manifest)
        write_pi_config(cell / "piconf", port=self.a.pi_port,
                        model_id=self.a.model,
                        reasoning_effort=self.a.reasoning_effort)
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
        state.update({"wall_s": round(time.time() - started, 3),
                      "cell_status": "measured", "finished": now_iso(),
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
        out.update(measure_m7_file(run_dir, arm_name, summary, slices,
                                   slice_meta))
        out.update(measure_m7_ws(run_dir, summary, slices, slice_meta))
        out.update(measure_f6(arm_name, summary))
        out.update(measure_suspect_timeout(run_dir, arm))
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
                "suspect_timeout", "infra_void", "wall_s", "run_complete")
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
        try:
            for row in rows:
                if self.a.limit and n_done >= self.a.limit:
                    self.ev("limit_reached", limit=self.a.limit)
                    break
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


def gate_endpoint(endpoint: str, model: str, *,
                  reasoning_effort: str | None,
                  timeout_s: float = 120.0) -> tuple[bool, list[str]]:
    """② 端點活著（**一次 trivial 呼叫**），印出實際 model id 與 `reasoning_tokens`。

    ⚠ 1003（0.4.24）是 thinking 模式、1004（0.4.17）不是，**同一份 gguf 也會不同**
    ——跨機之前要比的就是這個數字，不是「我載了同一個模型」。
    """
    import urllib.request
    payload: dict = {"model": model,
                     "messages": [{"role": "user", "content": "Say OK."}],
                     "max_tokens": 32, "stream": False}
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
        return False, [f"端點打不通：{endpoint}", f"  {exc!r}"]
    usage = body.get("usage") or {}
    det = usage.get("completion_tokens_details") or {}
    rt = det.get("reasoning_tokens", usage.get("reasoning_tokens"))
    txt = ((body.get("choices") or [{}])[0].get("message") or {}).get(
        "content") or ""
    return True, [
        f"端點 {endpoint}",
        f"  回話 {round(time.time() - t0, 2)} s",
        f"  實際 model id      = {body.get('model')!r}（要的是 {model!r}）",
        f"  reasoning_tokens   = {rt!r}"
        f"（None＝這個後端沒報；0＝真的沒思考）",
        f"  reasoning_effort 送出去的值 = {reasoning_effort!r}",
        f"  usage = {json.dumps(usage, ensure_ascii=False)}",
        f"  content[:60] = {txt[:60]!r}",
    ]


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
                                  reasoning_effort=args.reasoning_effort)
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

def reconcile(out: pathlib.Path, manifest: dict) -> int:
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
        "never_started": [], "not_in_plan": sorted(have - want)}
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
        kind = ("measured" if st.get("cell_status") == "measured"
                else "infra_void")
        buckets[kind].append(r["cell"])
        detail.append({**r, "state": kind, "accepted": st.get("accepted"),
                       "stop_reason": st.get("stop_reason"),
                       "infra_void": st.get("infra_void"),
                       "requests_seen": st.get("requests_seen")})
    ok = (len(rows) == len(plan_rows(manifest))
          and not buckets["not_in_plan"]
          and not buckets["never_started"]
          and not buckets["claimed_not_complete"])
    doc = {"run": "R535", "ts": now_iso(), "out": str(out),
           "plan_sha256": plan_sha, "plan_chain": chain,
           "n_plan": len(rows), "n_expected": len(plan_rows(manifest)),
           "counts": {k: len(v) for k, v in buckets.items()},
           "verdict": "OK" if ok else "INVALID",
           "rule": ("360 格每格都必須「有一列」或「明寫 void 原因」，"
                    "少一格或多一格都判 INVALID。"),
           "buckets": buckets, "cells": detail}
    (out / "reconcile.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: doc[k] for k in
                      ("n_plan", "n_expected", "counts", "verdict")},
                     ensure_ascii=False, indent=2))
    for k in ("never_started", "claimed_not_complete", "not_in_plan"):
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
    ap.add_argument("--reasoning-effort", default=None,
                    choices=["none", "low", "medium", "high"],
                    help="送進 models.json 的 samplingParams（不給＝照後端預設；"
                         "1003 預設是思考模式）")
    ap.add_argument("--pi-bin", default="pi", help="pi 執行檔（0.85.1）")
    ap.add_argument("--pi-port", type=int, default=8877,
                    help="proxy 固定埠（§7.8 用 8877）。**每條並行流要不同的埠**"
                         "——pi 吃設定檔不吃環境變數，埠對不上 ⇒ requests_seen=0")
    ap.add_argument("--sandbox", default="none",
                    help="驗收沙箱後端（裁決：R535 用 none，不降權 ⇒ 不再造跨 uid 孤兒）")
    ap.add_argument("--test-timeout", type=float, default=30.0)
    ap.add_argument("--agent-timeout", type=float, default=900.0,
                    help="單次嘗試的 agent 逾時（秒）")
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
        out = [r for k, r in enumerate(out) if k % n == i]
    return out


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    mpath = pathlib.Path(args.bank_manifest).resolve()
    manifest, msha = load_manifest(mpath, expect_sha=args.expect_manifest_sha256)

    if args.preflight:
        return preflight(args, mpath, manifest, msha)

    out = pathlib.Path(args.out).resolve()
    if args.reconcile:
        return reconcile(out, manifest)
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
