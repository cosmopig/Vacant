#!/usr/bin/env python3
"""把幾份 realrev 輸出依序合併成一份教材（組號重編 s01、s02…；內容與真值一個位元組都不動）。機械式。
用法：merge_sets.py <out> <dir1> [<dir2> …]"""
import hashlib
import json
import pathlib
import shutil
import sys

out = pathlib.Path(sys.argv[1])
srcs = [pathlib.Path(x) for x in sys.argv[2:]]
if out.exists():
    raise SystemExit(f"refusing: {out} exists")
(out / "sets").mkdir(parents=True)
sets, meta, n = [], [], 0
for d in srcs:
    m = json.loads((d / "manifest.json").read_text())
    meta.append({"from": d.name, "generator": m.get("generator"), "seed": m.get("seed"), "n_sets": len(m["sets"]),
                 "window": m.get("window")})
    for s in m["sets"]:
        n += 1
        new = f"s{n:02d}"
        shutil.copytree(d / "sets" / s["set"], out / "sets" / new)
        sets.append({**s, "set": new, "orig_set": s["set"], "orig_dir": d.name})
man = {"schema": "vacant.d2.manifest/1", "generator": "realrev-wikipedia/1 (merged)", "n_sets": len(sets), "parts": meta, "sets": sets}
raw = json.dumps(man, ensure_ascii=False, indent=1).encode()
(out / "manifest.json").write_bytes(raw)
(out / "manifest.sha256").write_text(hashlib.sha256(raw).hexdigest() + "\n")
for d in srcs:
    if (d / "SOURCES.md").exists():
        with open(out / "SOURCES.md", "a") as fh:
            fh.write(f"\n## {d.name}\n\n" + (d / "SOURCES.md").read_text())
print(len(sets), hashlib.sha256(raw).hexdigest())
