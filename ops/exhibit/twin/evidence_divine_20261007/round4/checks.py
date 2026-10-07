#!/usr/bin/env python3
"""round4 檢查數字：殘句／前綴／現實詞／第 2 行出現率。輸入：離線重組的 cards_offline.json，或 VM 真跑的 out 目錄（--live DIR）。"""
import argparse, json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4]))
from ops.exhibit.twin import fortune as fz  # noqa: E402

PREF = (fz.WANT_PREFIX, fz.TRIED_PREFIX, fz.SAID_PREFIX)


def report(name, cards):
    n = len(cards)
    l2 = sum(any(x.startswith(fz.WANT_PREFIX) for x in c) for c in cards)
    l3 = sum(any(x.startswith(fz.TRIED_PREFIX) for x in c) for c in cards)
    l4 = sum(any(x.startswith(fz.SAID_PREFIX) for x in c) for c in cards)
    lines = [x for c in cards for x in c]
    badpre = [x for x in lines if not x.startswith(PREF)]
    frag = [x for x in lines if fz.frag_reason(x.split("：", 1)[-1], terminated=True) is not None]
    frag_strict = [x for x in lines if fz.frag_reason(x.split("：", 1)[-1], terminated=False, wish=x.startswith(fz.WANT_PREFIX)) is not None]
    real = [x for x in lines if fz.mentions_reality(x.split("：", 1)[-1])]
    tooLong = [x for x in lines if len(x) > 60]
    comma_pre = [x for x in lines if x.startswith("它試了，")]
    print(f"## {name}：{n} 張卡，第 2–4 行共 {len(lines)} 行\n"
          f"- 第 2 行（它心裡想：）出現 {l2}/{n}；第 3 行（它試了：）{l3}/{n}；第 4 行（試完它說：）{l4}/{n}\n"
          f"- 殘句（frag_reason 對上卡的每一行再驗一次）：{len(frag)} 行 {frag}\n"
          f"- 殘句（嚴格版：不信任句號，連結構規則一起上）：{len(frag_strict)} 行 {frag_strict}\n"
          f"- 前綴不在 {{它心裡想：、它試了：、試完它說：}} 的行：{len(badpre)} {badpre}；『它試了，』：{len(comma_pre)}\n"
          f"- 含現實詞的行：{len(real)} {real}\n- 超過 60 字的行：{len(tooLong)}")


ap = argparse.ArgumentParser()
ap.add_argument("--live")
a = ap.parse_args()
if a.live:
    cards = []
    for p in sorted(pathlib.Path(a.live).glob("a[0-9]*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        cards.append([x for x in (r.get("card_md") or "").splitlines()[1:] if x.strip()])
    report("VM 真跑", cards)
else:
    rows = json.loads((HERE / "cards_offline.json").read_text(encoding="utf-8"))
    report("離線重組 A 組 a1–a12", [r["lines"][1:] for r in rows if r["id"].startswith("a")])
    report("離線重組 B 組 v1–v12", [r["lines"][1:] for r in rows if r["id"].startswith("v")])
    # 對照：round3 最終版（card_md_final）同一套檢查
    old = []
    for r in rows:
        old.append([x for x in r["old"].splitlines()[1:] if x.strip()])
    report("對照：round3 最終版 24 張（同一套檢查）", old)
