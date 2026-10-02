"""twin/twinground — 段 0：鋪地。把世界的材料池鋪成每一位分身的「地上的東西」。

## 這支在架構裡承重什麼

裁決：`decisions/DECISION_20261001_TWIN_WORLD.md` 的 W3b 一節。

W3 的分身房間裡什麼都沒有，「好幾步」只能是嘴上的。W3b 把世界裡的**實物**
（`world/materials/<地點>/…`：清單、帳本鏈尾段、托盤裡的信、紙團、卡片格狀圖……，
彼此有關聯）放進房間的 `地上/<地點>/…`。（W3b 當時是每一跑依 `sub_id` 雜湊抽樣；P10 起改成全部鋪，見下一節。）

⚠ 這些是地上的東西，**不是任務**：池子裡不准有任務句式或分身台詞
（`tests/test_twin_world_w3b.py` 掃禁詞與菜單句式）。

## 鋪法（P10，2026-10-02 起：全部鋪）

P10 把材料池從 41 件換成 24 件（八個地點各 3 件，每件都對某一種性情有吸引力，見 `world/materials/_lure.json`）。
**每一位分身看到同一片地**——命盤決定的是「先去哪、怎麼走」，不是「地上有什麼」；這樣八個人走同一片地，
走法不同，電視上的劇本才不一樣（以前每位觀眾抽 16–34 件，走法差異與抽樣差異混在一起，分不開）。
`sample(sub_id)` 的簽名不變（回 `{"files", "groups"}`），但回的是整個池子與全部關聯組。

⚠ 誠實邊界：唯讀是檔案權限，不是作業系統隔離；成品「用到的數字找得到出處」
是字面比對（`provenance`），不代表推理對。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
from typing import Any

MATERIALS = pathlib.Path(__file__).resolve().parent / "world" / "materials"
GROUND_DIRNAME = "地上"
N_GROUPS = 2          # 舊的抽樣參數（P10 起不用，留著讓舊測試的 import 不炸）
_SALT = "vacant.twin.ground/1\n"


def _h(sub_id: str, key: str) -> int:
    return int(hashlib.sha256((_SALT + sub_id + "\n" + key).encode("utf-8")).hexdigest(), 16)


def pool(materials: pathlib.Path = MATERIALS) -> list[str]:
    """池子裡所有材料（相對路徑，POSIX，排序）；底線開頭的檔是作者側的，不算。"""
    out = []
    for p in sorted(materials.rglob("*")):
        rel = p.relative_to(materials)
        if p.is_file() and not any(part.startswith("_") for part in rel.parts):
            out.append(rel.as_posix())
    return out


def groups(materials: pathlib.Path = MATERIALS) -> dict[str, list[str]]:
    p = materials / "_links.json"
    return json.loads(p.read_text(encoding="utf-8"))["groups"] if p.is_file() else {}


def place_of(rel: str) -> str:
    return rel.split("/", 1)[0]


def sample(sub_id: str, materials: pathlib.Path = MATERIALS) -> dict[str, Any]:
    """回 `{"files": [相對路徑…], "groups": [組名…]}`。P10 起＝整個池子＋全部關聯組（`sub_id` 不影響結果）。"""
    items = pool(materials)
    gs = groups(materials)
    return {"files": sorted(items), "groups": sorted(gs)}


def lay(ground_root: pathlib.Path, sub_id: str,
        materials: pathlib.Path = MATERIALS) -> dict[str, Any]:
    """把抽到的檔複製到 `ground_root/地上/…`（0444）。回 manifest（路徑＋sha256）。"""
    s = sample(sub_id, materials)
    base = ground_root / GROUND_DIRNAME
    if base.exists():
        shutil.rmtree(base)
    man = []
    for rel in s["files"]:
        src, dst = materials / rel, base / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        dst.write_bytes(data)
        dst.chmod(0o444)
        man.append({"path": f"{GROUND_DIRNAME}/{rel}", "sha256": hashlib.sha256(data).hexdigest()})
    return {"groups": s["groups"], "n_files": len(man), "files": man}


# ---------------------------------------------------------------------------
# 出處比對（確定性字面比對；不代表推理對）
# ---------------------------------------------------------------------------

#: 印紋用字（池子裡出現過的印紋名）。分身寫的成品裡出現它們，就要在地上找得到。
MARKS = ("魚骨", "水滴", "梯", "星", "半月", "波", "三點", "鎖扣", "雙環", "蕨葉", "螺旋", "十字")
_NUM = re.compile(r"(?<![\d.])\d{2,}(?![\d.])|(?<=[第片窗格列行張撮封枚截位共])\s?\d(?![\d])|(?<![\d.])\d(?=\s?[枚張片個截指撮格窗封行列位])")
_LINE_NO = re.compile(r"^\s*\d+[.、．)]", re.M)


def tokens(text: str) -> list[str]:
    """成品裡「要有出處」的字：≥2 位的阿拉伯數字、緊接在量詞後的個位數、印紋名。"""
    text = _LINE_NO.sub("", text)
    toks = [t.strip() for t in _NUM.findall(text)]
    toks += [m for m in MARKS if m in text for _ in range(1)]
    return toks


def provenance(artifact_texts: list[str], ground_texts: list[str],
               extra_known: list[str] | None = None) -> dict[str, Any]:
    """成品的每個「數字／印紋」token 有沒有出現在地上（或 WORLD.md 等 `extra_known`）的某個檔裡。

    數字要**整個數字**對得上（423 裡的 23 不算 23）；印紋名用子字串。
    ⚠ 字面比對：找得到出處不代表用得對（推理對不對沒有判）；自己算出來的數字（例如兩份清單相加）
    會被列成「找不到」——那是對的：它不在任何一個檔裡。
    """
    hay = "\n".join(ground_texts + list(extra_known or []))
    nums = set(re.findall(r"\d+", hay))
    found, missing = [], []
    for t in artifact_texts:
        for tok in tokens(t):
            ok = (tok in nums) if tok.isdigit() else (tok in hay)
            (found if ok else missing).append(tok)
    return {"found": len(found), "missing": len(missing),
            "missing_tokens": sorted(set(missing)), "found_tokens": sorted(set(found))}
