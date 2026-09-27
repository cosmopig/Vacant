#!/usr/bin/env python3
"""把 tui.raw 依驅動器的 marks 切段、剝 ANSI、每段印最後幾行不重複的字。"""
import json, re, sys, pathlib
L = pathlib.Path(sys.argv[1])
b = (L / "tui.raw").read_bytes()
marks = json.load(open(L / "marks.json"))
ansi = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*(\x07|\x1b\\)|\x1b[()][A-Z0-9]|\x1b[=>]")
offs = [0] + [m["offset"] for m in marks] + [len(b)]
labels = ["(startup)"] + [m["label"] for m in marks]
for lab, a, z in zip(labels, offs, offs[1:]):
    seg = ansi.sub("", b[a:z].decode("utf-8", "replace"))
    uniq = []
    for l in (x.strip() for x in seg.splitlines()):
        if l and l not in uniq:
            uniq.append(l)
    print(f"===== {lab}  bytes={z - a}")
    for l in uniq[-int(sys.argv[2] if len(sys.argv) > 2 else 12):]:
        print("   ", l[:160])
