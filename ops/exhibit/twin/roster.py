"""twin/roster — 展件居民名冊。**這裡面沒有任何真人資料，而且現在不准有。**

## 這支在架構裡承重什麼

`SPEC_v3 §七` 的施工順序把「persona 萃取與入場」列為第 4 項，依賴寫的是
**「待倫理定案」**；`HANDOFF.md §六-2` 把同一件事列進「待人類決定——不要自己
決定」，並指出它擋住動物園的兩項功能（人格抽取、退場上鏈）。

`vacant_hm/world/js/persona.js` 的檔頭已經先做了同一個決定：

  > 真的 persona 要等倫理定案（SPEC §4，施工順序第 4 項）。
  > 在那之前用假的餵世界——之後接真資料只是換這一個檔案的輸出來源。

本檔是那句話在 Vacant 這一側的對應物。**居民是程序生成的，不是任何人的分身。**
四類欄位（工作領域／興趣主題／風格特徵／需求類型）刻意與 `persona.js` 逐字對齊，
因為倫理定案之後要換的只有「這些值從哪來」，不是資料形狀。

## 形象規則（人類連續三次否決過的那一條）

居民一律**用人的形象**——`vacant_hm/demo/sprites/` 那批黏土人（體型：hunch／
lanky／plain／round／small／stout）。不准抽象發光生物。體型是**剪影辨識度**的
載體：展場是隔一段距離看螢幕，剪影是唯一還看得見的東西（`ops/exhibit/PLAN.md` §四）。

## 誠實邊界

1. 這份名冊裡的 persona 值**全部是假的**，由 seed 決定。它證明的是「資料形狀
   與同意機制接得起來」，不證明任何關於真人的事。
2. 倫理定案之前，不要把這份名冊接到任何觀眾輸入。接上去的那一刻，
   `vacant_network/consent.py` 的四條誠實邊界就從「示範」變成「義務」。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

#: 四類欄位的候選值，與 `vacant_hm/world/js/persona.js` 的四張清單逐字相同。
#: 逐字相同是為了讓兩邊的假 persona 看起來像同一個世界的人，不是為了共用程式碼。
DOMAIN = ["寫程式", "查資料", "寫文案", "翻譯", "規劃行程", "整理筆記",
          "看合約", "做簡報", "算數字", "改履歷", "寫信", "debug"]
TOPIC = ["機器學習", "城市規劃", "古典樂", "登山", "咖啡", "攝影", "賽車",
         "料理", "棋類", "建築", "海洋生物", "字體", "天文", "園藝", "單車"]
STYLE = ["話很短", "喜歡條列", "愛追問為什麼", "先給結論", "偏好例子",
         "一次問很多", "常改主意", "要求引用來源", "喜歡比喻", "很有耐心"]
NEED = ["要一個能跑的東西", "要有人幫忙檢查", "要看懂別人寫的",
        "要把長的變短", "要決定選哪個", "要找出哪裡錯了"]

#: 可用的體型。名字＝`vacant_hm/demo/sprites/<body>_<pose>.png` 的前綴。
BODIES = ("hunch", "lanky", "plain", "round", "small", "stout")

#: 每個體型有這幾張圖。展件目前只需要這四張。
POSES = ("portrait", "write", "wait", "submit")


def _h(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12], 16)


def _pick_n(seed: str, pool: list[str], n: int) -> list[str]:
    """確定性取 n 個不重複值。同一個 seed 永遠給同一份答案（可重放）。"""
    out: list[str] = []
    i = 0
    while len(out) < n and i < 64:
        v = pool[_h(seed, str(i)) % len(pool)]
        if v not in out:
            out.append(v)
        i += 1
    return out


@dataclass(frozen=True)
class Resident:
    """一位居民。`persona` 的四個 key 就是 `vacant_network/consent.py::ALLOWED_FIELDS`。"""

    codename: str
    body: str
    persona: dict[str, list[str]]
    #: 展場發給「捐贈者」的代號。目前是假的——沒有捐贈者（見檔頭誠實邊界 1）。
    subject_ref: str
    synthetic: bool = True
    cells: tuple[str, ...] = field(default=())

    def to_json(self) -> dict[str, Any]:
        return {
            "codename": self.codename,
            "body": self.body,
            "persona": {k: list(v) for k, v in sorted(self.persona.items())},
            "subject_ref": self.subject_ref,
            "synthetic": self.synthetic,
            "cells": list(self.cells),
        }


def make_resident(seed: str) -> Resident:
    """造一位程序生成的居民。內容由 seed 決定，體型也由 seed 決定。"""
    persona = {
        "domains": _pick_n(seed + "d", DOMAIN, 1 + _h(seed, "nd") % 3),
        "topics": _pick_n(seed + "t", TOPIC, 1 + _h(seed, "nt") % 3),
        "style": _pick_n(seed + "s", STYLE, 1 + _h(seed, "ns") % 2),
        "needs": _pick_n(seed + "n", NEED, 1 + _h(seed, "nn") % 2),
    }
    a, b = "KRVSTNLMDZ", "AEIOU"
    code = (a[_h(seed, "c0") % len(a)] + b[_h(seed, "c1") % len(b)]
            + a[_h(seed, "c2") % len(a)] + "-" + str(10 + _h(seed, "c3") % 90))
    return Resident(
        codename=code,
        body=BODIES[_h(seed, "body") % len(BODIES)],
        persona=persona,
        subject_ref="SYN-" + seed.upper(),
    )


#: v1 展位的三位居民。三位是算出來的，不是挑的——見 `DECISION_TWIN_2026-09-19.md` §三。
DEFAULT_SEEDS = ("t1", "t2", "t3")


def default_roster() -> list[Resident]:
    return [make_resident(s) for s in DEFAULT_SEEDS]


def specialty(r: Resident) -> str:
    """給畫面用的一行專長。取第一個工作領域——那個欄位本來就在允許萃取的四類裡。"""
    return r.persona["domains"][0] if r.persona.get("domains") else "—"
