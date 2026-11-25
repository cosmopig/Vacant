#!/usr/bin/env python3
"""邊界測試（bnd_d2_qwen9b_1004）的出處覆蓋率：按提示變體 × 初稿**實際的抓取指令**分層。

分類只看真的抓了來源網址（含 d2-sources.example）的指令：用 urllib／requests／urlopen ⇒ python；用 wget ⇒ wget；用 curl ⇒ curl。
2026-11-25 最終稽核更正：先前按「指令字串裡有沒有 python 字樣」分，`which wget python3` 這種偵測指令讓 s23、s27 被誤判成 python。
用法：bnd_coverage.py <run root> <manifest> <out json>
"""
import collections
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from score_d2 import parse_report, status  # noqa: E402


def classify(cmds: list[str]) -> str:
    j = " ".join(c for c in cmds if "d2-sources.example" in c)
    if re.search(r"urllib|requests\.get|urlopen", j):
        return "python urllib"
    if re.search(r"\bwget\b", j):
        return "wget"
    if re.search(r"\bcurl\b", j):
        return "curl"
    return "other"


def main() -> int:
    root, man_p, out_p = map(pathlib.Path, sys.argv[1:4])
    sets = {s["set"]: s for s in json.loads(man_p.read_text())["sets"]}
    agg: dict = collections.defaultdict(collections.Counter)
    rows = []
    for d in sorted(root.glob("cells/s*/c0")):
        sid = d.parent.name
        variant = (d / "write_variant.txt").read_text().strip()
        log = (d / "run" / "agent.log").read_text(errors="replace")
        cmds = [c.encode().decode("unicode_escape", "ignore") for c in re.findall(r'"command":"((?:[^"\\]|\\.)*)"', log)]
        fetch = classify(cmds)
        pj = (d / "provenance.json").read_text().strip()
        prov = {e["line"]: e for e in (json.loads(pj)["claims"] if pj else [])}
        rep = (d / "report.md").read_text()
        lines = rep.splitlines()
        s = sets[sid]
        vals = parse_report(rep, s["claims"])
        ok = correct = 0
        for cl in s["claims"]:
            correct += status(vals[cl["id"]], cl["id"], 0, s["truth"]) == "correct"
            ln = next((i + 1 for i, x in enumerate(lines) if x.strip().startswith(cl["template_line"].strip())), None)
            e = prov.get(ln)
            if e and e.get("source") and e["source"]["url"].endswith("/" + cl["source_page"]):
                ok += 1
        key = f"{variant}|{fetch}"
        agg[key]["sets"] += 1
        agg[key]["claims"] += len(s["claims"])
        agg[key]["correct_page"] += ok
        agg[key]["draft_correct"] += correct
        rows.append({"set": sid, "variant": variant, "fetch": fetch, "draft_correct": correct, "correct_page": ok})
    out = {"by_variant_and_fetch": {k: dict(v) for k, v in sorted(agg.items())}, "rows": rows,
           "note": "分類依實際抓取指令（2026-11-25 依最終稽核更正）"}
    out_p.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out["by_variant_and_fetch"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
