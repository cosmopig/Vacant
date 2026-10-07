#!/usr/bin/env python3
"""P13 第三輪：用**最終版的命盤卡組合器**（fortune.compose_card_v3）對已存下來的真跑文字重算命盤卡。

為什麼有這一支：真跑期間發現組合器的幾個格式問題（句子在「、」被截成殘句、紙上的標記句「這是我自己做的」被抄上卡、
模型把路徑整串放進引號）。這些都是**確定性的後處理**，不影響模型寫出什麼——所以修好組合器後，用同一份真跑文字
（信、PLAN、試的紀錄、成品、外形、命盤）重算，不必再花一輪機時。真跑當下 VM 上組出來的卡原樣留在 `card_md`／`card`，
重算的放在 `card_final`／`card_md_final`；兩者不同的地方報告會逐條列出。

用法：python3 recompute_cards.py --set a|v <out_dir>
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO))
from ops.exhibit.twin import divine_samples as ds  # noqa: E402
from ops.exhibit.twin import fortune as fz  # noqa: E402
from ops.exhibit.twin import twinagent  # noqa: E402


def persona(name: str, which: str) -> tuple[dict, str]:
    if which == "a":
        rows = {r["name"]: r for r in json.loads((HERE / "inputs12_parsed.json").read_text(encoding="utf-8"))}
        return rows[name]["card"], rows[name]["text"]
    d = next(x for x in ds.DIVINERS if x["name"] == name)
    return d["card"], ds._text_of(d["card"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True, choices=["a", "v"])
    ap.add_argument("dir")
    a = ap.parse_args()
    changed = 0
    for p in sorted(pathlib.Path(a.dir).glob(f"{a.set}[0-9]*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        card, text = persona(r["name"].replace("dv_", ""), a.set)
        traits = twinagent.render_traits(card, text)
        f = r.get("fortune_final") or {}
        files = {**(r.get("made_things") or {}), fz.RECORD_FILE: r.get("record_full") or ""}
        res = fz.compose_card_v3(f, plan_text=r.get("plan_full") or "", record_text=r.get("record_full") or "", rows=[],
                                 files=files, retries=0, traits=traits, letter_text=r.get("letter_full") or "",
                                 look=r.get("look") or {}, seed=twinagent.slug_for(f"p13-a-{r['name'].replace('dv_', '')}"))
        new_md = fz.card_md(res)
        r["card_final"] = {k: res.get(k) for k in ("verdict", "want_line", "tried_line", "said_line", "lines", "tv_lines", "dropped")}
        r["card_md_final"] = new_md
        if new_md != r.get("card_md"):
            changed += 1
        p.write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("recomputed; cards that differ from the VM-time ones:", changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
