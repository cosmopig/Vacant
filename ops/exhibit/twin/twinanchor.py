"""twin/twinanchor — 把鏈頭錨定出去，讓「**整條重算**」被偵測得到。

## 這支在架構裡承重什麼（補 `twinstore.py` 誠實邊界 1）

`twinstore.py` 自己寫得很清楚：

> 雜湊鏈證明的是「竄改看得出來」，不是「竄改不可能」。拿得到這個檔案的人
> 可以把整條鏈從某一列開始**全部重算**，`verify()` 就會通過。……要擋後者需要
> 把鏈頭**外部錨定**——這一支**沒有做**，不要讀成做了。

這一支就是那個「沒有做」的東西。原理只有一句話：

> **重算改得了鏈，改不了「鏈頭曾經是什麼」這件已經離開這台機器的事。**

所以錨定＝**定期把鏈頭簽起來、送到這個檔案之外的地方**。之後任何一次
「整條重算」都會讓現在的鏈算不出當初那個承諾，於是紅。

## 為什麼是 `vacant_network/checkpoint.py` 的複用，不是另造一套

`checkpoint.py`（18 §2 V1 存檔點）**已經把這件事做完了**，而且做的是同一件事：

| 存檔點要的 | twinstore 給得出的 |
|---|---|
| `logbook.entries`（每個有 `.seq`、`.hash()`） | `twin_event` 每列的 `seq`、`row_sha256` |
| `logbook.stream_id()` | `store.genesis()`（含 `store_id`，兩個庫不可能同鏈） |
| `logbook.head()` | 最後一列的 `row_sha256` |

於是這一支只寫了一個**唯讀視圖** `TwinChainView`，把 SQLite 的列偽裝成
`Logbook`；`issue_checkpoint()` / `verify_checkpoint()` / `verify_checkpoint_chain()`
**一行都沒有改**。跟著免費拿到的還有：簽章覆蓋整個 claim、`vacant_id` 必須由
`pub` 重算（擋換 pub 冒名）、`entries_hash` 窗口承諾、`chain_head` 一致性、
以及**存檔點自身成鏈**（`prev_checkpoint_sig`，抽掉中間一枚會紅）。

沒有複用到的只有 `retro_audit_window()`——那支是拿 `checks.py` 沙箱重跑
交付答案的，分身卡沒有「答案對不對」這回事。它留下來的兩個欄位倒是照用：
`retro_audits` 記「簽這一枚的當下量到什麼」，`retro_missing` 記「什麼量不到」
（第一枚沒有前一枚可比 ⇒ `prev_anchor_holds` 進 missing，**不寫 false**）。

## 一、錨定到哪？（展場離線是紅線，所以沒有一個選項可以依賴外部服務）

四個出口，**每一個在斷網之下退化成什麼都寫在這裡**。預設全部離線可跑。

| 出口 | 指令 | 斷網之下退化成 | 擋得住「整條重算」嗎 |
|---|---|---|---|
| **① 本機錨鏈**（一定會做） | `emit` | **不退化**（本來就不用網路） | ❌ 單獨不行。錨鏈跟 store 同一顆磁碟，改得了一個就改得了兩個。它擋的是「只改 store、忘了改錨鏈」——**偷懶與意外，不是有決心的人**。 |
| **② 另一台機器** | `mirror --scp w401@100.119.113.56:C:/...` | **停**。`ok=false` ＋ stderr 原樣回報，**不寫 0、不安靜跳過**。已經送出去的副本照常有效，只是不再更新 ⇒ 偵測解析度停在最後一次成功的那一枚。 | ✅ 只要那台沒被同時攻下。 |
| **③ 可攜媒體 / 掛載點** | `mirror --dest /Volumes/USB/twinanchor` | **不退化**（USB 不需要網路）。退化的是**人**：沒人去插隨身碟就沒有新副本。 | ✅ 同上，且展場最實際——開館前插一次、閉館後插一次。 |
| **④ 簽章後印出來的紙 / QR** | `slip`、`slip --qr out.png` | **不退化**（紙不需要電）。代價：紙上只放**錨定摘要的前 128 bit**，不是完整簽章 ⇒ 紙能做的是**比對**，不是獨立驗簽。 | ✅ 這是唯一一個連「磁碟整個被換掉」都還在的出口。 |

`vacant_network/logbook.py` 的既有鏈**沒有列進來**，這是刻意的：它跟 store
同一顆磁碟，安全性上等於①，卻要多養一條鏈與一把金鑰。真要多一層就走②③④。

> ⚠ ②③④ 三個出口共同的前提：**送出去的不只是錨鏈，還有公鑰**
> （`anchor_pub.txt`）。沒有離機的公鑰副本，`verify` 只能驗「這條錨鏈自洽」，
> 攻擊者用**自己的金鑰**重簽一整條就驗得過。見下面誠實邊界 1。

## 二、誰簽？金鑰放哪？

- 一把**專用的 Ed25519**，`Identity.generate()` 產、`Identity.save()` 存成
  `identity.key`（0600，目錄 0700）。預設在
  `ops/exhibit/twin/store/anchor_key/`——`store/` **已經在 `.gitignore` 第 25 行**，
  而 `identity.key` 這個檔名本身就是 `record.py` RECORD_SPEC §7 排除私鑰的對象。
  兩道不相干的紀律同時蓋住它。
- 🔴 **不碰任何既有憑證**。不讀 `auth.json`、不讀 repo 裡任何既有 `identity.key`、
  不共用 G 實驗或收據那幾條鏈的身份。錨定鏈是獨立的一條，弄丟了就重開一條
  （代價是舊的錨全部失去可比性，所以**要備份公鑰**）。
- `init` **不覆寫**既有金鑰（覆寫＝把所有舊錨變成無主的字串）。
- 其他子命令**永遠不會偷偷產金鑰**：沒有金鑰就叫你去跑 `init`，fail-closed。

## 三、誠實邊界（🔴 改碼時逐字保留）

1. **錨定擋不住「拿到金鑰的人重新簽一條」。** 他重算 store、重簽整條錨鏈，
   本機看起來完全乾淨。唯一的反制是**離機的公鑰或紙條**：
   `verify --pub <hex>` / `--pin-file` / `--slip`。沒給任何一個，報告裡
   `pubkey_pinned` 寫 **`null`**（不是 `false`——那會被讀成「比對過、不符」），
   而 `--require-pin` 會把這個 `null` 變成紅。**展場那條線要開 `--require-pin`。**
2. **錨定的偵測解析度＝錨的間隔。** 最後一枚錨之後追加的列，錨一句話都沒說。
   閉館後補一枚，那一天才算被蓋住。
3. **錨定不取代 `twinstore.verify()`，兩個要一起跑。** 錨的 `entries_hash` 串的是
   每列的 `row_sha256`，不重算 `payload_json` 的雜湊。單改 `payload_json`
   而不動 `payload_sha256` ⇒ 錨看不到、`twinstore.verify()` 會抓到。
   所以 `verify` 子命令兩個都跑，少一個就不完整。
4. **「錨鏈完整」不等於「沒漏收」。** `twinstore.py` 誠實邊界 3 原封不動：
   `seq` 連續只保證寫進來的沒被抽掉，不保證雲端發生過的都寫進來了。
5. **紙條驗的是摘要不是簽章。** `VTA1 …` 上的 32 個十六進位字＝錨定記錄
   canonical bytes 的 sha256 前 128 bit。它證明「這枚錨跟印那天是同一枚」，
   不證明「這枚錨簽得對」（那要完整記錄 ＋ 公鑰）。
6. **可用性不在守備範圍。** `rm -rf store/` 之後這一支什麼都說不出來。
   錨定管的是**竄改看得出來**，備份管的是**東西還在**，兩件事。

用法：
    python3 ops/exhibit/twin/twinanchor.py init
    python3 ops/exhibit/twin/twinanchor.py emit --note "開館前"
    python3 ops/exhibit/twin/twinanchor.py verify --require-pin --pin-file /Volumes/USB/anchor_pub.txt
    python3 ops/exhibit/twin/twinanchor.py slip --qr /tmp/anchor.png
    python3 ops/exhibit/twin/twinanchor.py mirror --dest /Volumes/USB/twinanchor
    python3 ops/exhibit/twin/twinanchor.py mirror --scp w401@100.119.113.56:C:/Users/w401/twinanchor/
    python3 ops/exhibit/twin/twinanchor.py selftest      # 離線；含負控制
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

HERE = pathlib.Path(__file__).resolve()
TWIN = HERE.parent
ROOT = TWIN.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.exhibit.twin.twinstore import (  # noqa: E402
    DEFAULT_DB, GENESIS_PREFIX, KIND_NOTE, SCHEMA, TwinStore, row_digest,
)
from vacant_network import crypto  # noqa: E402
from vacant_network.canonical import canonical_bytes  # noqa: E402
from vacant_network.checkpoint import (  # noqa: E402
    issue_checkpoint, verify_checkpoint, verify_checkpoint_chain,
)
from vacant_network.identity import Identity  # noqa: E402

#: 錨鏈落盤位置。跟 store 放一起（`store/` 已在 .gitignore），
#: 但**真正承重的是離機副本**，不是這個檔。
DEFAULT_ANCHORS = pathlib.Path(
    os.environ.get("VACANT_TWIN_ANCHORS") or (TWIN / "store" / "anchors.jsonl")
)
#: 錨定金鑰目錄。`Identity.save()` 會在裡面寫 `identity.key`（0600）。
DEFAULT_KEYDIR = pathlib.Path(
    os.environ.get("VACANT_TWIN_ANCHOR_KEY") or (TWIN / "store" / "anchor_key")
)
#: 離機副本裡公鑰的檔名。**這個檔要跟錨鏈一起送出去**，否則邊界 1 那條洞是開的。
PUB_PIN_NAME = "anchor_pub.txt"
#: 紙條前綴＋版本。換格式要換版本號，不要就地改語意。
SLIP_MAGIC = "VTA1"
#: 紙條上摘要的長度（十六進位字元數）。32 ＝ 128 bit，人抄得動、碰撞不用擔心。
SLIP_DIGEST_HEX = 32


# ---------------------------------------------------------------------------
# 把 twinstore 偽裝成 Logbook（唯讀視圖）
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _RowRef:
    """`checkpoint.py` 對一筆 entry 只用到 `.seq` 與 `.hash()`，所以只給這兩樣。"""

    seq: int
    row_sha256: str

    def hash(self) -> str:
        return self.row_sha256


class TwinChainView:
    """twinstore 的**唯讀** Logbook 視圖。

    ⚠ **刻意沒有 `append()`。** twinstore 的寫入只有 `TwinStore.append()` 一條路
    （trigger 擋住其他路），這裡如果補一個 `append()`，就等於在 append-only
    的牆上自己開一扇後門。存檔點模組本來也不寫鏈，它只讀。
    """

    def __init__(self, store: TwinStore) -> None:
        self._genesis = store.genesis()
        self.entries: list[_RowRef] = [
            _RowRef(r["seq"], r["row_sha256"])
            for r in store.conn.execute(
                "SELECT seq, row_sha256 FROM twin_event ORDER BY seq ASC")
        ]

    def stream_id(self) -> str:
        """存檔點的 `stream_id` 欄位＝ store 的創世串（含 `store_id`）。

        ⇒ 一枚錨天生綁死在一個 store 上，把別台的錨鏈接過來會被
        `verify_all()` 的 `stream_bound` 抓到。"""
        return self._genesis

    def branch_id(self) -> str:
        return "twinstore"

    def head(self) -> str:
        return self.entries[-1].hash() if self.entries else self._genesis

    def head_seq(self) -> int:
        return self.entries[-1].seq if self.entries else 0

    def __len__(self) -> int:
        return len(self.entries)


# ---------------------------------------------------------------------------
# 金鑰
# ---------------------------------------------------------------------------

def key_exists(keydir: pathlib.Path | str) -> bool:
    return (pathlib.Path(keydir) / "identity.key").exists()


def init_key(keydir: pathlib.Path | str) -> dict[str, Any]:
    """產一把專用錨定金鑰。**已存在就不動它**（覆寫＝舊錨全部變無主）。"""
    keydir = pathlib.Path(keydir)
    if key_exists(keydir):
        ident = Identity.load(keydir)
        return {"created": False, "keydir": str(keydir),
                "vacant_id": ident.vacant_id,
                "pub": crypto.pub_to_hex(ident.pub),
                "note": "已存在，未覆寫（覆寫會讓所有舊錨變成無主的字串）"}
    ident = Identity.generate()
    ident.save(keydir)
    return {"created": True, "keydir": str(keydir),
            "vacant_id": ident.vacant_id,
            "pub": crypto.pub_to_hex(ident.pub),
            "note": "私鑰 identity.key 已 0600；store/ 在 .gitignore、"
                    "檔名也在 RECORD_SPEC §7 排除清單"}


def load_key(keydir: pathlib.Path | str) -> Identity:
    """載入錨定金鑰。**不存在就炸，不偷偷產**（偷偷產＝悄悄換簽名的人）。"""
    keydir = pathlib.Path(keydir)
    if not key_exists(keydir):
        raise FileNotFoundError(
            f"錨定金鑰不存在：{keydir / 'identity.key'}。"
            f"先跑 `twinanchor.py init`——這一支不會替你偷偷產一把，"
            f"因為那等於悄悄換掉簽名的人。")
    return Identity.load(keydir)


def pub_hex_of(keydir: pathlib.Path | str) -> str | None:
    p = pathlib.Path(keydir) / "identity.pub"
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# 錨鏈的讀寫
# ---------------------------------------------------------------------------

def load_anchors(path: pathlib.Path | str) -> list[dict[str, Any]]:
    path = pathlib.Path(path)
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{n} 不是合法 JSON：{e}") from e
    return out


def _append_anchor(path: pathlib.Path, anchor: dict[str, Any]) -> None:
    """追加一枚。`fsync` 是因為展場會直接拔電源（跟 twinstore 的 synchronous=FULL 同理）。"""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(canonical_bytes(anchor).decode("utf-8") + "\n")
        f.flush()
        os.fsync(f.fileno())


def anchor_digest(anchor: dict[str, Any]) -> str:
    """一枚錨的摘要＝它 canonical bytes 的 sha256（含簽章）。紙條與離機比對都用這個。"""
    return hashlib.sha256(canonical_bytes(anchor)).hexdigest()


def slip_of(anchor: dict[str, Any]) -> str:
    """印得出來、抄得動的紙條：`VTA1 <創世前8> <窗口尾 seq> <摘要前32>`。

    ⚠ 誠實邊界 5：這是**摘要**不是簽章。紙條能說「這枚錨跟印那天是同一枚」，
    不能獨立證明「這枚錨簽得對」。"""
    return " ".join([
        SLIP_MAGIC,
        str(anchor["stream_id"])[:8],
        str(anchor["window"][1]),
        anchor_digest(anchor)[:SLIP_DIGEST_HEX],
    ])


def parse_slip(text: str) -> dict[str, Any]:
    parts = text.strip().split()
    if len(parts) != 4 or parts[0] != SLIP_MAGIC:
        raise ValueError(
            f"紙條格式不對，要 `{SLIP_MAGIC} <創世前8> <seq> <摘要{SLIP_DIGEST_HEX}>`，"
            f"拿到 {text!r}")
    try:
        seq = int(parts[2])
    except ValueError as e:
        raise ValueError(f"紙條的 seq 不是整數：{parts[2]!r}") from e
    return {"magic": parts[0], "stream8": parts[1], "seq": seq, "digest": parts[3]}


# ---------------------------------------------------------------------------
# 簽發
# ---------------------------------------------------------------------------

class AnchorRefused(RuntimeError):
    """fail-closed：鏈已經紅了還簽，等於替竄改背書。"""


def emit_anchor(
    store: TwinStore,
    identity: Identity,
    anchors_path: pathlib.Path | str,
    *,
    force: bool = False,
    ts_ms: int | None = None,
) -> dict[str, Any]:
    """簽一枚錨並追加到錨鏈。窗口**永遠是 `[1, 鏈頭]`（累積式）**。

    為什麼累積不是增量：增量窗口下，抽掉中間一枚錨就等於讓那一段歷史沒有人
    承諾過；累積窗口下，**最新那一枚自己就蓋住全部歷史**，錨鏈少幾枚也還在守。
    代價是 O(N) 雜湊，展場的 N 是幾百到幾千，不是問題。

    `force=True` ＝ 明知道鏈是紅的還簽（鑑識用：把「什麼時候發現斷的」釘下來）。
    這時 `retro_audits` 裡會誠實寫 false，**不會把紅的洗成綠的**。
    """
    view = TwinChainView(store)
    if not view.entries:
        raise AnchorRefused("空的 store 沒有鏈頭可錨（`verify_checkpoint` 也會拒收空窗口）")

    chain = store.verify()
    prev_list = load_anchors(anchors_path)
    prev = prev_list[-1] if prev_list else None

    retro: dict[str, bool] = {"twinstore_verify": bool(chain["ok"])}
    missing: list[str] = []
    if prev is None:
        # 🔴 三態：第一枚沒有前一枚可比 ⇒ 「量不到」進 missing，不是 false。
        missing.append("prev_anchor_holds")
        prev_ok: bool | None = None
    else:
        prev_ok, _reason = verify_checkpoint(prev, view)
        retro["prev_anchor_holds"] = bool(prev_ok)

    if not force:
        if not chain["ok"]:
            raise AnchorRefused(
                f"拒簽：twinstore 自己的鏈就已經紅了（{chain['reason']}，"
                f"broken_at={chain['broken_at']}）。簽下去等於替竄改背書。"
                f"真要釘鑑識時間點用 --force。")
        if prev_ok is False:
            raise AnchorRefused(
                "拒簽：前一枚錨對不上現在的 store（歷史被改過或被截斷）。"
                "先查清楚再說；真要釘鑑識時間點用 --force。")

    if ts_ms is None:
        ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    anchor = issue_checkpoint(
        view, identity,
        window=(1, view.head_seq()),
        retro_audits=retro,
        retro_missing=missing,
        prev_checkpoint=prev,
        ts_ms=ts_ms,
    )
    _append_anchor(pathlib.Path(anchors_path), anchor)
    return anchor


# ---------------------------------------------------------------------------
# 驗證
# ---------------------------------------------------------------------------

def verify_all(
    store: TwinStore,
    anchors: list[dict[str, Any]],
    *,
    pinned_pub: str | None = None,
    slip: str | None = None,
    require_pin: bool = False,
) -> dict[str, Any]:
    """七道關。回一份逐條報告；`ok` 是全部的 AND。

    1. `store_verify`  — twinstore 自己的鏈（**錨不取代它**，誠實邊界 3）
    2. `anchor_chain`  — 錨自身成鏈（`verify_checkpoint_chain`，抽掉中間一枚會紅）
    3. `per_anchor`    — 每一枚對現在的 store 重驗（簽章＋`entries_hash`＋`chain_head`）
    4. `stream_bound`  — 每一枚的 `stream_id` 必須等於這個 store 的創世串
    5. `no_rollback`   — 現在的鏈頭 seq 不得低於任何一枚錨的窗口尾（截斷）
    6. `single_signer` — 所有錨同一把公鑰（半路換人簽）
    7. `pubkey_pinned` — 跟**離機**的公鑰比對。沒有可比的東西 ⇒ `null`
    """
    report: dict[str, Any] = {
        "anchors": len(anchors),
        "failures": [],
        "warnings": [],
    }

    # 1
    sv = store.verify()
    report["store_verify"] = sv
    if not sv["ok"]:
        report["failures"].append(
            f"twinstore 鏈紅：{sv['reason']}（seq {sv['broken_at']}）")

    view = TwinChainView(store)
    report["store_head_seq"] = view.head_seq()
    report["store_genesis"] = view.stream_id()

    if not anchors:
        # 沒有錨＝沒有被錨定過。這是「量不到」，不是「乾淨」。
        report["anchor_chain"] = None
        report["per_anchor"] = []
        report["stream_bound"] = None
        report["no_rollback"] = None
        report["single_signer"] = None
        report["pubkey_pinned"] = None
        report["slip"] = None
        report["warnings"].append(
            "錨鏈是空的：這條 store 從來沒有被錨定過 ⇒ 整條重算偵測不到。先跑 `emit`。")
        if require_pin:
            report["failures"].append("--require-pin：沒有任何錨可比對")
        report["ok"] = not report["failures"]
        return report

    # 2
    ok2, why2 = verify_checkpoint_chain(anchors)
    report["anchor_chain"] = {"ok": ok2, "reason": why2}
    if not ok2:
        report["failures"].append(f"錨鏈本身斷了：{why2}")

    # 3
    per: list[dict[str, Any]] = []
    for i, a in enumerate(anchors):
        ok, why = verify_checkpoint(a, view)
        per.append({"i": i, "window_end": a.get("window", [None, None])[1],
                    "ts_ms": a.get("ts_ms"), "ok": ok, "reason": why,
                    "digest": anchor_digest(a)})
        if not ok:
            report["failures"].append(
                f"錨 #{i}（窗口尾 {per[-1]['window_end']}）驗不過：{why}")
    report["per_anchor"] = per

    # 4
    bad_stream = [i for i, a in enumerate(anchors)
                  if a.get("stream_id") != view.stream_id()]
    report["stream_bound"] = {
        "ok": not bad_stream,
        "reason": "ok" if not bad_stream
        else f"錨 {bad_stream} 的 stream_id 不是這個 store 的創世串（別台的錨被接過來）"}
    if bad_stream:
        report["failures"].append(report["stream_bound"]["reason"])

    # 5
    max_end = max(int(a["window"][1]) for a in anchors)
    rolled = view.head_seq() < max_end
    report["no_rollback"] = {
        "ok": not rolled, "anchored_max_seq": max_end,
        "store_head_seq": view.head_seq(),
        "reason": "ok" if not rolled
        else f"鏈頭退回去了：錨過 seq {max_end}，現在只到 {view.head_seq()}（尾巴被截掉）"}
    if rolled:
        report["failures"].append(report["no_rollback"]["reason"])

    # 6
    pubs = {a.get("pub") for a in anchors}
    report["single_signer"] = {
        "ok": len(pubs) == 1, "distinct": len(pubs),
        "reason": "ok" if len(pubs) == 1 else f"錨鏈上有 {len(pubs)} 把不同的公鑰"}
    if len(pubs) != 1:
        report["failures"].append(report["single_signer"]["reason"])

    # 7 🔴 三態：沒有離機的公鑰可比 ⇒ null，不是 false
    if pinned_pub is None:
        report["pubkey_pinned"] = None
        report["warnings"].append(
            "pubkey_pinned=null：沒有給離機公鑰 ⇒ **拿到金鑰的人重簽一整條偵測不到**"
            "（誠實邊界 1）。展場請用 --require-pin --pin-file <離機副本>。")
        if require_pin:
            report["failures"].append(
                "--require-pin：沒有給離機公鑰（--pub / --pin-file）")
    else:
        pinned = pinned_pub.strip().lower()
        match = all((a.get("pub") or "").strip().lower() == pinned for a in anchors)
        report["pubkey_pinned"] = bool(match)
        if not match:
            report["failures"].append(
                "錨鏈的公鑰跟離機釘的那把不符 ⇒ 有人用自己的金鑰重簽了整條")

    # 紙條（可選，但它是唯一連「磁碟整個被換掉」都還在的比對點）
    if slip is None:
        report["slip"] = None
    else:
        report["slip"] = check_slip(slip, anchors)
        if not report["slip"]["ok"]:
            report["failures"].append(f"紙條對不上：{report['slip']['reason']}")

    report["ok"] = not report["failures"]
    return report


def check_slip(slip: str, anchors: list[dict[str, Any]]) -> dict[str, Any]:
    """拿紙條（或 QR 掃出來的字串）比對本機錨鏈。"""
    try:
        s = parse_slip(slip)
    except ValueError as e:
        return {"ok": False, "reason": str(e), "slip": slip}
    cand = [a for a in anchors if int(a["window"][1]) == s["seq"]]
    if not cand:
        return {"ok": False, "slip": slip,
                "reason": f"本機錨鏈裡找不到窗口尾 = {s['seq']} 的錨"
                          f"（紙條記的那一枚被拿掉了，或整條被重簽成別的窗口）"}
    for a in cand:
        if (str(a["stream_id"])[:8] == s["stream8"]
                and anchor_digest(a)[:SLIP_DIGEST_HEX] == s["digest"]):
            return {"ok": True, "slip": slip, "reason": "ok",
                    "matched_digest": anchor_digest(a)}
    got = anchor_digest(cand[0])[:SLIP_DIGEST_HEX]
    return {"ok": False, "slip": slip,
            "reason": f"窗口尾 {s['seq']} 的那一枚摘要是 {got}，紙條上寫 {s['digest']}"
                      f" ⇒ 那一枚被換過（整條重算＋重簽的特徵）"}


# ---------------------------------------------------------------------------
# 出口②③：離機副本
# ---------------------------------------------------------------------------

_MIRROR_README = """\
Vacant twinanchor 離機副本
==========================
產生時間（UTC）：{ts}
來源 store 創世串：{genesis}
錨數：{n}    最新窗口尾 seq：{end}
最新一枚摘要：{digest}
紙條（可手抄／可做 QR）：{slip}

這份副本要做什麼：
  回到那台機器上跑
      python3 ops/exhibit/twin/twinanchor.py verify --require-pin \\
              --pin-file <這個目錄>/{pin}
  如果 store 被整條重算過，上面那行會紅。

⚠ 這裡面**沒有私鑰，也不該有**。只有公鑰（{pin}）與錨鏈（anchors.jsonl）。
⚠ 公鑰一旦跟錨鏈放在同一個地方被一起改掉，這份副本就退化成「本機錨鏈」
   （擋意外，不擋有決心的人）。所以副本要放在**攻擊者改不到的地方**，
   而不是只是「另一個資料夾」。
"""


def mirror_to_dir(anchors_path: pathlib.Path | str, keydir: pathlib.Path | str,
                  dest: pathlib.Path | str) -> dict[str, Any]:
    """出口③：複製到可攜媒體／掛載點。**離線可跑。**"""
    anchors_path = pathlib.Path(anchors_path)
    dest = pathlib.Path(dest)
    anchors = load_anchors(anchors_path)
    if not anchors:
        return {"ok": False, "reason": "錨鏈是空的，沒東西可送", "dest": str(dest)}
    pub = pub_hex_of(keydir)
    if pub is None:
        return {"ok": False, "reason": f"{keydir}/identity.pub 不存在（先 init）",
                "dest": str(dest)}
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(anchors_path, dest / "anchors.jsonl")
    (dest / PUB_PIN_NAME).write_text(pub + "\n", encoding="utf-8")
    last = anchors[-1]
    (dest / "MIRROR.txt").write_text(_MIRROR_README.format(
        ts=datetime.now(timezone.utc).isoformat(),
        genesis=last["stream_id"], n=len(anchors), end=last["window"][1],
        digest=anchor_digest(last), slip=slip_of(last), pin=PUB_PIN_NAME,
    ), encoding="utf-8")
    return {"ok": True, "dest": str(dest), "anchors": len(anchors),
            "files": ["anchors.jsonl", PUB_PIN_NAME, "MIRROR.txt"],
            "slip": slip_of(last)}


def mirror_scp(anchors_path: pathlib.Path | str, keydir: pathlib.Path | str,
               target: str, *, timeout: float = 60.0) -> dict[str, Any]:
    """出口②：送到另一台機器。

    ⚠ **1003 的路徑方言**：`scp` 那一側要寫 `C:/Users/w401/...`，
    不是 `ssh` 用的 `/c/Users/...`（MSYS 只轉換裸參數）。寫錯會靜靜落在
    奇怪的地方，所以這裡**回報 scp 的 stderr 原文，不吞**。

    斷網 ⇒ `ok=false` ＋ rc ＋ stderr。**不寫 0、不當作成功。**
    `scp` 這支程式根本不存在 ⇒ `ok=null`（沒量到，不是量到失敗）。
    """
    if shutil.which("scp") is None:
        return {"ok": None, "reason": "這台沒有 scp ⇒ 這個出口沒量到（不是失敗）",
                "target": target}
    anchors_path = pathlib.Path(anchors_path)
    if not anchors_path.exists():
        return {"ok": False, "reason": f"{anchors_path} 不存在", "target": target}
    pub = pub_hex_of(keydir)
    if pub is None:
        return {"ok": False, "reason": f"{keydir}/identity.pub 不存在（先 init）",
                "target": target}
    with tempfile.TemporaryDirectory() as td:
        staged = pathlib.Path(td)
        shutil.copyfile(anchors_path, staged / "anchors.jsonl")
        (staged / PUB_PIN_NAME).write_text(pub + "\n", encoding="utf-8")
        cmd = ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
               str(staged / "anchors.jsonl"), str(staged / PUB_PIN_NAME), target]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"ok": False, "reason": f"scp 逾時（{timeout}s）",
                    "target": target, "cmd": cmd}
        return {"ok": p.returncode == 0, "rc": p.returncode, "target": target,
                "cmd": cmd, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}


# ---------------------------------------------------------------------------
# 負控制：這兩支就是我們宣稱擋得住的那個攻擊
# ---------------------------------------------------------------------------
#
# 🔴 它們留在正式模組裡是刻意的：**沒有負控制的綠燈不算數**。
# 招式毫無機密可言（trigger 只擋 SQL 的 UPDATE/DELETE，攻擊者把 trigger
# 拔掉重建表就好），寫出來的價值遠大於藏起來。
# `selftest` 與 `tests/test_twinanchor.py` 都靠這兩支產生紅燈。

def _drop_triggers(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TRIGGER IF EXISTS twin_event_no_update")
    conn.execute("DROP TRIGGER IF EXISTS twin_event_no_delete")


def simulate_full_rewrite(db_path: pathlib.Path | str,
                          drop_seqs: Iterable[int] = ()) -> dict[str, Any]:
    """**負控制 A**：整條重算。拿得到檔案的人做得到的事。

    拔掉 trigger → 讀出全部列 → 抽掉 `drop_seqs` → **重新編號、重算
    `prev_sha256` 與 `row_sha256`** → 寫回去 → 把 trigger 補回來。
    做完之後 `twinstore.verify()` 是**綠的**——這正是 twinstore 誠實邊界 1
    講的那件事。錨定要抓的就是這個。
    """
    drop = {int(s) for s in drop_seqs}
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None
    try:
        sid = conn.execute("SELECT v FROM twin_meta WHERE k='store_id'").fetchone()["v"]
        genesis = hashlib.sha256(
            f"{GENESIS_PREFIX}\n{sid}".encode("utf-8")).hexdigest()
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM twin_event ORDER BY seq ASC")]
        keep = [r for r in rows if r["seq"] not in drop]
        _drop_triggers(conn)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM twin_event")
        prev = genesis
        for i, r in enumerate(keep, 1):
            payload_sha = hashlib.sha256(
                r["payload_json"].encode("utf-8")).hexdigest()
            dg = row_digest(i, r["ts_unix_ms"], r["sub_id"], r["kind"],
                            r["source"], payload_sha, prev)
            conn.execute(
                "INSERT INTO twin_event(seq, ts_unix_ms, ts_utc, sub_id, kind, source,"
                " payload_json, payload_sha256, prev_sha256, row_sha256)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (i, r["ts_unix_ms"], r["ts_utc"], r["sub_id"], r["kind"], r["source"],
                 r["payload_json"], payload_sha, prev, dg))
            prev = dg
        conn.execute("COMMIT")
        conn.executescript(SCHEMA)  # trigger 補回去，讓現場看起來一切正常
        return {"before": len(rows), "after": len(keep), "dropped": sorted(drop)}
    finally:
        conn.close()


def simulate_truncate(db_path: pathlib.Path | str, n: int) -> dict[str, Any]:
    """**負控制 B**：截掉鏈尾 n 列。

    截斷之後剩下的是一段**合法前綴**，`twinstore.verify()` 照樣綠——
    因為它只往前走，不知道原本該走到哪裡。知道的是錨。
    """
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.isolation_level = None
    try:
        before = conn.execute("SELECT COUNT(*) FROM twin_event").fetchone()[0]
        _drop_triggers(conn)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "DELETE FROM twin_event WHERE seq > (SELECT MAX(seq)-? FROM twin_event)",
            (int(n),))
        conn.execute("COMMIT")
        conn.executescript(SCHEMA)
        after = conn.execute("SELECT COUNT(*) FROM twin_event").fetchone()[0]
        return {"before": before, "after": after, "removed": before - after}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# selftest（離線、零機時、含負控制＋對照組）
# ---------------------------------------------------------------------------

def selftest() -> int:
    """展場開機前跑得完的自檢。判準全部要有負控制，綠燈才算數。"""
    results: list[tuple[str, bool, str]] = []

    def chk(name: str, cond: bool, extra: str = "") -> None:
        results.append((name, bool(cond), extra))

    with tempfile.TemporaryDirectory() as td:
        base = pathlib.Path(td)
        keydir = base / "key"
        init_key(keydir)
        ident = load_key(keydir)
        pub = pub_hex_of(keydir)

        def fresh(tag: str) -> tuple[pathlib.Path, pathlib.Path]:
            db = base / f"{tag}.sqlite3"
            an = base / f"{tag}.anchors.jsonl"
            st = TwinStore(db)
            for i in range(8):
                st.append(KIND_NOTE, f"v{i:02d}", {"i": i, "t": f"卡 {i}"},
                          source="selftest", ts_unix_ms=1_700_000_000_000 + i)
            st.close()
            return db, an

        # --- 對照組：沒被動過的鏈是綠的 -----------------------------------
        db, an = fresh("clean")
        st = TwinStore(db)
        a1 = emit_anchor(st, ident, an, ts_ms=1_700_000_100_000)
        slip = slip_of(a1)
        st.append(KIND_NOTE, "v08", {"i": 8}, source="selftest",
                  ts_unix_ms=1_700_000_000_100)
        a2 = emit_anchor(st, ident, an, ts_ms=1_700_000_200_000)
        rep = verify_all(st, load_anchors(an), pinned_pub=pub, slip=slip,
                         require_pin=True)
        st.close()
        chk("對照組：沒動過的鏈＋釘公鑰＋紙條 ⇒ 綠", rep["ok"],
            json.dumps(rep["failures"], ensure_ascii=False))
        chk("對照組：錨自身成鏈（第二枚接得上第一枚）",
            a2.get("prev_checkpoint_sig") == a1.get("sig"))
        chk("對照組：第一枚的 prev_anchor_holds 進 missing 不是 false",
            a1["retro_missing"] == ["prev_anchor_holds"]
            and "prev_anchor_holds" not in a1["retro_audits"],
            json.dumps({"missing": a1["retro_missing"],
                        "audits": a1["retro_audits"]}, ensure_ascii=False))

        # --- 負控制 A：整條重算 -------------------------------------------
        db, an = fresh("rewrite")
        st = TwinStore(db)
        emit_anchor(st, ident, an, ts_ms=1_700_000_300_000)
        st.close()
        info = simulate_full_rewrite(db, drop_seqs=[4])
        st = TwinStore(db)
        sv = st.verify()
        rep = verify_all(st, load_anchors(an), pinned_pub=pub)
        st.close()
        chk("負控制 A 前提：整條重算之後 twinstore 自己還是綠的（弱點屬實）",
            sv["ok"], sv["reason"])
        chk("負控制 A：整條重算被錨抓到 ⇒ 紅", not rep["ok"],
            json.dumps(rep["failures"], ensure_ascii=False))
        chk("負控制 A：資料真的少了一列", info["after"] == info["before"] - 1,
            json.dumps(info))

        # --- 負控制 B：截掉鏈尾 -------------------------------------------
        db, an = fresh("truncate")
        st = TwinStore(db)
        emit_anchor(st, ident, an, ts_ms=1_700_000_400_000)
        st.close()
        simulate_truncate(db, 3)
        st = TwinStore(db)
        sv = st.verify()
        rep = verify_all(st, load_anchors(an), pinned_pub=pub)
        st.close()
        chk("負控制 B 前提：截斷之後 twinstore 自己還是綠的（合法前綴）",
            sv["ok"], sv["reason"])
        chk("負控制 B：截斷被錨抓到 ⇒ 紅", not rep["ok"],
            json.dumps(rep["failures"], ensure_ascii=False))
        chk("負控制 B：紅的理由指名鏈頭退回去",
            (rep["no_rollback"] or {}).get("ok") is False,
            json.dumps(rep.get("no_rollback"), ensure_ascii=False))

        # --- 負控制 C：拿到金鑰的人重簽一整條（這是我們**擋不住**的那個） ---
        db, an = fresh("resign")
        st = TwinStore(db)
        emit_anchor(st, ident, an, ts_ms=1_700_000_500_000)
        st.close()
        simulate_full_rewrite(db, drop_seqs=[2])
        attacker = Identity.generate()
        an.unlink()
        st = TwinStore(db)
        emit_anchor(st, attacker, an, ts_ms=1_700_000_600_000)
        rep_nopin = verify_all(st, load_anchors(an))                # 沒釘公鑰
        rep_pin = verify_all(st, load_anchors(an), pinned_pub=pub)  # 釘了
        rep_req = verify_all(st, load_anchors(an), require_pin=True)
        st.close()
        chk("負控制 C（誠實邊界 1 的可執行標本）：沒釘公鑰 ⇒ 重簽偵測不到，會綠",
            rep_nopin["ok"], json.dumps(rep_nopin["failures"], ensure_ascii=False))
        chk("負控制 C：沒釘公鑰時 pubkey_pinned 是 null 不是 false",
            rep_nopin["pubkey_pinned"] is None, repr(rep_nopin["pubkey_pinned"]))
        chk("負控制 C：釘了離機公鑰 ⇒ 重簽被抓到，紅",
            not rep_pin["ok"], json.dumps(rep_pin["failures"], ensure_ascii=False))
        chk("負控制 C：--require-pin 把 null 變紅", not rep_req["ok"],
            json.dumps(rep_req["failures"], ensure_ascii=False))

        # --- 負控制 D：紙條 -----------------------------------------------
        db, an = fresh("slip")
        st = TwinStore(db)
        a = emit_anchor(st, ident, an, ts_ms=1_700_000_700_000)
        good = slip_of(a)
        st.close()
        simulate_full_rewrite(db, drop_seqs=[3])
        an.unlink()
        st = TwinStore(db)
        emit_anchor(st, ident, an, ts_ms=1_700_000_800_000)  # 用同一把重簽
        rep = verify_all(st, load_anchors(an), pinned_pub=pub, slip=good)
        st.close()
        chk("負控制 D：同一把金鑰重簽，公鑰釘不住，但**紙條**抓得到",
            (not rep["ok"]) and rep["slip"]["ok"] is False,
            json.dumps(rep["failures"], ensure_ascii=False))
        chk("負控制 D 對照：釘公鑰這一關在這個情境下是綠的（所以紙條不是多餘的）",
            rep["pubkey_pinned"] is True, repr(rep["pubkey_pinned"]))

        # --- 負控制 E：別台的錨接過來 --------------------------------------
        db_a, an_a = fresh("bindA")
        db_b, _an_b = fresh("bindB")
        st = TwinStore(db_a)
        emit_anchor(st, ident, an_a, ts_ms=1_700_000_900_000)
        st.close()
        st = TwinStore(db_b)
        rep = verify_all(st, load_anchors(an_a), pinned_pub=pub)
        st.close()
        chk("負控制 E：A 的錨鏈接到 B 的 store ⇒ 紅（創世串綁死）",
            (not rep["ok"]) and rep["stream_bound"]["ok"] is False,
            json.dumps(rep["failures"], ensure_ascii=False))

        # --- 負控制 F：fail-closed，鏈紅的時候拒簽 ---------------------------
        db, an = fresh("refuse")
        conn = sqlite3.connect(str(db))
        conn.isolation_level = None
        _drop_triggers(conn)
        conn.execute("UPDATE twin_event SET payload_json='{\"x\":1}' WHERE seq=3")
        conn.executescript(SCHEMA)
        conn.close()
        st = TwinStore(db)
        refused = False
        try:
            emit_anchor(st, ident, an, ts_ms=1_700_001_000_000)
        except AnchorRefused:
            refused = True
        forced = emit_anchor(st, ident, an, force=True, ts_ms=1_700_001_000_000)
        st.close()
        chk("負控制 F：store 已經紅了 ⇒ 預設拒簽（不替竄改背書）", refused)
        chk("負控制 F：--force 簽得下去，但 retro_audits 誠實寫 false",
            forced["retro_audits"]["twinstore_verify"] is False,
            json.dumps(forced["retro_audits"], ensure_ascii=False))

        # --- 出口③：離機副本 ------------------------------------------------
        db, an = fresh("mirror")
        st = TwinStore(db)
        emit_anchor(st, ident, an, ts_ms=1_700_001_100_000)
        st.close()
        m = mirror_to_dir(an, keydir, base / "usb")
        pin_txt = (base / "usb" / PUB_PIN_NAME).read_text(encoding="utf-8").strip()
        chk("出口③：離機副本三個檔都在，且公鑰對得上", m["ok"] and pin_txt == pub,
            json.dumps(m, ensure_ascii=False))
        chk("出口③：副本裡**沒有**私鑰",
            not any(p.name == "identity.key" for p in (base / "usb").iterdir()))

    bad = [r for r in results if not r[1]]
    for name, ok, extra in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}"
              + (f"  {extra}" if extra and not ok else ""))
    print(f"\n{len(results) - len(bad)}/{len(results)} 通過")
    return 0 if not bad else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _p(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="twinanchor — 把 twinstore 的鏈頭錨定出去（複用 V1 存檔點）")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--anchors", default=str(DEFAULT_ANCHORS))
    ap.add_argument("--keydir", default=str(DEFAULT_KEYDIR))
    s = ap.add_subparsers(dest="cmd", required=True)

    s.add_parser("init", help="產一把專用錨定金鑰（已存在不覆寫）")
    e = s.add_parser("emit", help="簽一枚錨並追加到錨鏈")
    e.add_argument("--note", default=None,
                   help="先往 twinstore 追加一列 note（於是它也被這枚錨蓋住）")
    e.add_argument("--force", action="store_true",
                   help="鏈已經紅了還簽（鑑識用；retro_audits 會誠實寫 false）")
    s.add_parser("list", help="列出錨鏈")
    v = s.add_parser("verify", help="七道關；退出碼 0 綠 / 1 紅")
    v.add_argument("--pub", default=None, help="離機公鑰（hex）")
    v.add_argument("--pin-file", default=None,
                   help="離機公鑰檔（mirror 出去的 anchor_pub.txt）")
    v.add_argument("--slip", default=None, help="紙條字串 `VTA1 ...`")
    v.add_argument("--require-pin", action="store_true",
                   help="沒有離機公鑰就算紅（展場那條線要開）")
    sl = s.add_parser("slip", help="印得出來的紙條（可選 QR）")
    sl.add_argument("--qr", default=None, help="同時輸出 QR PNG 到這個路徑")
    m = s.add_parser("mirror",
                     help="離機副本（出口②③）；退出碼 0 送到了 / 1 送失敗 / 3 沒量到")
    m.add_argument("--dest", default=None, help="可攜媒體／掛載點目錄")
    m.add_argument("--scp", default=None,
                   help="另一台機器，例如 w401@100.119.113.56:C:/Users/w401/twinanchor/"
                        "（⚠ scp 用 C:/ 方言，不是 ssh 的 /c/）")
    s.add_parser("selftest", help="離線自檢，含負控制")

    a = ap.parse_args(list(argv) if argv is not None else None)

    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "init":
        _p(init_key(pathlib.Path(a.keydir)))
        return 0

    anchors_path = pathlib.Path(a.anchors)

    if a.cmd == "list":
        ans = load_anchors(anchors_path)
        _p([{"i": i, "window": x["window"], "ts_ms": x["ts_ms"],
             "chain_head": x["chain_head"], "retro_audits": x["retro_audits"],
             "retro_missing": x["retro_missing"], "digest": anchor_digest(x),
             "slip": slip_of(x)} for i, x in enumerate(ans)])
        return 0

    if a.cmd == "mirror":
        if not a.dest and not a.scp:
            print("要 --dest 或 --scp 至少一個", file=sys.stderr)
            return 2
        out: dict[str, Any] = {}
        if a.dest:
            out["dir"] = mirror_to_dir(anchors_path, pathlib.Path(a.keydir),
                                       pathlib.Path(a.dest))
        if a.scp:
            out["scp"] = mirror_scp(anchors_path, pathlib.Path(a.keydir), a.scp)
        _p(out)
        # 🔴 三態的退出碼：0 送到了 / 1 送失敗 / 3 沒量到（例如這台沒有 scp）。
        # 「沒量到」**不可以走 0**——那會讓排程腳本以為副本更新過了。
        if any(x.get("ok") is False for x in out.values()):
            return 1
        if any(x.get("ok") is None for x in out.values()):
            return 3
        return 0

    if a.cmd == "slip":
        ans = load_anchors(anchors_path)
        if not ans:
            print("錨鏈是空的，先跑 emit", file=sys.stderr)
            return 1
        text = slip_of(ans[-1])
        res: dict[str, Any] = {"slip": text, "window_end": ans[-1]["window"][1],
                               "qr": None}
        if a.qr:
            from ops.exhibit.twin import qr as qrmod
            pathlib.Path(a.qr).write_bytes(qrmod.to_png(text, scale=8))
            res["qr"] = a.qr
        _p(res)
        print(text)
        return 0

    # verify 走 SQLite 層唯讀（mode=ro）——稽核這件事不該對真相來源寫東西。
    st = TwinStore(a.db, read_only=(a.cmd == "verify"))
    try:
        if a.cmd == "emit":
            ident = load_key(pathlib.Path(a.keydir))
            if a.note:
                st.append(KIND_NOTE, "_anchor", {"text": a.note}, source="twinanchor")
            try:
                anchor = emit_anchor(st, ident, anchors_path, force=a.force)
            except AnchorRefused as ex:
                print(str(ex), file=sys.stderr)
                return 1
            _p({"window": anchor["window"], "chain_head": anchor["chain_head"],
                "retro_audits": anchor["retro_audits"],
                "retro_missing": anchor["retro_missing"],
                "digest": anchor_digest(anchor), "slip": slip_of(anchor),
                "anchors_file": str(anchors_path)})
            return 0
        if a.cmd == "verify":
            pinned = a.pub
            if a.pin_file:
                pinned = pathlib.Path(a.pin_file).read_text(encoding="utf-8").strip()
            rep = verify_all(st, load_anchors(anchors_path), pinned_pub=pinned,
                             slip=a.slip, require_pin=a.require_pin)
            _p(rep)
            return 0 if rep["ok"] else 1
    finally:
        st.close()
    return 2


if __name__ == "__main__":
    sys.exit(main())
