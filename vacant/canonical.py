"""Canonical JSON serialization — 跨機驗章一致的唯一序列化規則。

簽章覆蓋的永遠是 canonical bytes，不是 Python dict。規則（對應架構總規格 §5/§10）：
  - sort_keys（鍵排序）
  - 緊湊分隔（無多餘空白）
  - UTF-8、不轉義非 ASCII（ensure_ascii=False）→ 中文 niche 也能簽
  - embedding / 大二進位「不進簽章」：呼叫端負責在丟進來前剔除

任何持 pubkey 的人都能用同一規則重算 bytes → 驗章，無需信任送方的位元組。
"""

from __future__ import annotations

import json
from typing import Any

_SEPARATORS = (",", ":")


def canonical_bytes(obj: Any) -> bytes:
    """把 JSON-able 物件序列化成確定性的 canonical bytes。"""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=_SEPARATORS,
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_str(obj: Any) -> str:
    return canonical_bytes(obj).decode("utf-8")
