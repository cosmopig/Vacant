#!/usr/bin/env python3
"""P13 第四輪：用第四輪的組句器（殘句不上卡、前綴一致、現實詞擴充）對 round3 已存下的 24 跑文字離線重組卡片，
與 round3 最終版（card_md_final）逐行對照。不改 round3 的任何檔；輸出 round4/cards_offline.json 與 cards_offline.txt。"""
from __future__ import annotations
import json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent          # .../round4
R3 = HERE.parent / "round3"
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(R3))
from ops.exhibit.twin import fortune as fz  # noqa: E402
from ops.exhibit.twin import twinagent  # noqa: E402
import recompute_cards as rc  # noqa: E402


def cards(which: str, outdir: pathlib.Path) -> list[dict]:
    rows = []
    for p in sorted(outdir.glob(f"{which}[0-9]*.json"), key=lambda x: int(x.stem[1:])):
        r = json.loads(p.read_text(encoding="utf-8"))
        name = r["name"].replace("dv_", "")
        card, text = rc.persona(name, which)
        traits = twinagent.render_traits(card, text)
        f = r.get("fortune_final") or {}
        files = {**(r.get("made_things") or {}), fz.RECORD_FILE: r.get("record_full") or ""}
        res = fz.compose_card_v3(f, plan_text=r.get("plan_full") or "", record_text=r.get("record_full") or "", rows=[], files=files,
                                 retries=0, traits=traits, letter_text=r.get("letter_full") or "", look=r.get("look") or {},
                                 seed=twinagent.slug_for(f"p13-a-{name}"))
        rows.append({"id": p.stem, "old": r.get("card_md_final", ""), "new": fz.card_md(res), "lines": res["lines"],
                     "dropped": res["dropped"]})
    return rows


def main() -> int:
    allrows = cards("a", R3 / "out_a") + cards("v", R3 / "out_v")
    (HERE / "cards_offline.json").write_text(json.dumps(allrows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    out = []
    for r in allrows:
        o, n = r["old"].splitlines()[1:], r["new"].splitlines()[1:]
        out.append(f"## {r['id']}")
        for i in range(max(len(o), len(n), 3)):
            ov = o[i] if i < len(o) else "(無)"
            nv = n[i] if i < len(n) else "(無)"
            if ov == nv:
                out.append(f"   {nv}")
            else:
                out.append(f" - {ov}\n + {nv}")
    (HERE / "cards_offline.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
