"""twin/world/build_facts — 生成世界作者側的 `materials/_facts.json`（窗 3「兩個出處對得上嗎」的事實表）。

這支在架構裡承重什麼：`grounding_gate.check_agree` 要知道「每件材料對哪些實體說了什麼值」，
並且要有一個**權威**（規矩 3「收據誰都能自己對」：帳本鏈的檔是這個世界的權威）。
事實表**不是手寫的**——它由材料本身依實體定義抽出來（同一支 `extract_values`，成品那一側也用它），
所以「材料說了什麼」可以逐檔重算、`--check` 驗得出表有沒有漂。

實體（`ENTITIES`）：
  - `chain.<418..447>.mark`：帳本鏈每一片的印紋。權威＝`帳本鏈/尾段_418到447片.txt`。
  - `cards.row4.count`：紙卡地第四列有幾張。權威＝`紙卡地/格狀圖.txt`（數第四列的 ○）。
  - `seals.mound.count`：土堆石頭上的小陶印有幾枚。權威＝`長桌廣場/土堆/小陶印.txt`（「兩枚…沒有第三枚」）。

誠實邊界：只登記這幾個；沒登記的實體窗 3 一律不判。`claims` 只收「同一行裡主詞後面緊接著說的值」，
一個檔一個實體記第一個值；抽不到就是這個檔沒對這個實體說話（不是它沒意見）。

用法：python3 ops/exhibit/twin/world/build_facts.py [--check]
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from ops.exhibit.twin import grounding_gate as gg  # noqa: E402

MATERIALS = HERE / "materials"
OUT = MATERIALS / "_facts.json"
CHAIN_FILE = "帳本鏈/尾段_418到447片.txt"
CHAIN_RANGE = range(418, 448)


def _pool() -> list[str]:
    out = []
    for p in sorted(MATERIALS.rglob("*")):
        rel = p.relative_to(MATERIALS)
        if p.is_file() and not any(part.startswith("_") for part in rel.parts):
            out.append(rel.as_posix())
    return out


def _first_value(text: str, ent: dict) -> str | None:
    for line in text.splitlines():
        v = gg.extract_values(line, ent)
        if v:
            return v[0]
    return None


def _grid_row4_count(text: str) -> str:
    for line in text.splitlines():
        if re.match(r"\s*第四列", line):
            return str(line.count("○"))
    raise ValueError("格狀圖裡找不到第四列")


def _mound_seal_count(text: str) -> str:
    m = re.search(r"[（(]\s*([兩二\d])\s*枚", text)
    if not m:
        raise ValueError("小陶印.txt 裡找不到「（兩枚」")
    return gg._ZH_DIGIT.get(m.group(1), m.group(1))


def build() -> dict:
    texts = {rel: (MATERIALS / rel).read_text(encoding="utf-8") for rel in _pool()}
    ents: dict[str, dict] = {}
    for n in CHAIN_RANGE:
        ent = {"label": f"片 {n} 的印紋", "kind": "mark",
               "subject": rf"(?<![0-9]){n}(?![0-9])", "authority_file": CHAIN_FILE}
        v = _first_value(texts[CHAIN_FILE], ent)
        if v is None:
            raise ValueError(f"帳本鏈尾段抽不到片 {n} 的印紋")
        ent["authority_value"] = v
        ents[f"chain.{n}.mark"] = ent
    ents["cards.row4.count"] = {
        "label": "第四列的張數", "kind": "count", "unit": "張", "subject": r"第\s?[四4]\s?列",
        "authority_file": "紙卡地/格狀圖.txt",
        "authority_value": _grid_row4_count(texts["紙卡地/格狀圖.txt"])}
    ents["seals.mound.count"] = {
        "label": "土堆小陶印的枚數", "kind": "count", "unit": "枚", "subject": "小陶印",
        "authority_file": "長桌廣場/土堆/小陶印.txt",
        "authority_value": _mound_seal_count(texts["長桌廣場/土堆/小陶印.txt"])}
    claims: dict[str, dict[str, str]] = {}
    for rel, text in texts.items():
        row = {}
        for key, ent in ents.items():
            if rel == ent["authority_file"] and ent["kind"] == "count":
                row[key] = ent["authority_value"]      # 權威檔對數量的說法是數出來的，不是一行字
                continue
            v = _first_value(text, ent)
            if v is not None:
                row[key] = v
        if row:
            claims[rel] = row
    return {"schema": "twin.facts/1",
            "note": ("作者側的事實表：每件材料對哪些實體說了什麼值（由 build_facts.py 從材料抽出，"
                     "不手寫）；authority_file 是這個世界對該實體的權威（帳本鏈與數出來的實物）。"
                     "不進分身的工作區；窗 3 的 prepare 把它抄進每一跑的 _ledger.py。"),
            "entities": ents, "claims": claims}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    data = build()
    text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if "--check" in argv:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if cur != text:
            print("_facts.json 與材料對不上（重跑 build_facts.py）", file=sys.stderr)
            return 1
        print("ok")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"寫了 {OUT}（{len(data['entities'])} 個實體、{len(data['claims'])} 件材料有說話）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
