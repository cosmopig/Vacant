#!/usr/bin/env python3
"""P13 第五輪：第 3 行優先選與第 2 行共用關鍵名詞的完整句。用 round3 的 24 跑＋round4 的 6 份真跑紀錄離線重組：
前＝第四輪的選法（rank_tried 退回原順序），後＝第五輪。只列第 3 行有改變的卡。輸出 cards_r5.json / changes_r5.txt。"""
from __future__ import annotations
import json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
R3 = HERE.parent / "round3"; R4 = HERE.parent / "round4"
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(R3))
from ops.exhibit.twin import fortune as fz  # noqa: E402
from ops.exhibit.twin import twinagent  # noqa: E402
import recompute_cards as rc  # noqa: E402


def compose(r, which):
    name = r["name"].replace("dv_", "")
    card, text = rc.persona(name, which)
    traits = twinagent.render_traits(card, text)
    files = {**(r.get("made_things") or {}), fz.RECORD_FILE: r.get("record_full") or ""}
    return fz.compose_card_v3(r.get("fortune_final") or {}, plan_text=r.get("plan_full") or "", record_text=r.get("record_full") or "", rows=[],
                              files=files, retries=0, traits=traits, letter_text=r.get("letter_full") or "", look=r.get("look") or {},
                              seed=twinagent.slug_for(f"p13-a-{name}"))


def main():
    srcs = []
    for which, d in (("a", R3 / "out_a"), ("v", R3 / "out_v")):
        for p in sorted(d.glob(f"{which}[0-9]*.json"), key=lambda x: int(x.stem[1:])):
            srcs.append((f"r3_{p.stem}", which, p))
    for p in sorted((R4 / "live").glob("a[0-9]*.json"), key=lambda x: int(x.stem[1:])):
        if ".lifecycle" not in p.name:
            srcs.append((f"r4live_{p.stem}", "a", p))
    orig = fz.rank_tried
    rows = []
    for rid, which, p in srcs:
        r = json.loads(p.read_text(encoding="utf-8"))
        fz.rank_tried = lambda change, body, wish: change
        before = compose(r, which)
        fz.rank_tried = orig
        after = compose(r, which)
        rows.append({"id": rid, "wish": before["want_line"], "before": before["tried_line"], "after": after["tried_line"],
                     "changed": before["tried_line"] != after["tried_line"],
                     "other_lines_same": [before["want_line"], before["said_line"]] == [after["want_line"], after["said_line"]]})
    (HERE / "cards_r5.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ch = [x for x in rows if x["changed"]]
    out = [f"總共 {len(rows)} 張，第 3 行有改變 {len(ch)} 張；其他行不變：{all(x['other_lines_same'] for x in rows)}", ""]
    for x in ch:
        out += [f"## {x['id']}", f"  第2行  {x['wish']}", f"  前     {x['before']}", f"  後     {x['after']}", ""]
    (HERE / "changes_r5.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))

main()
