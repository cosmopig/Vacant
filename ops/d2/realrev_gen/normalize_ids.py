#!/usr/bin/env python3
"""把 realrev 輸出的組號 set_NN 改成 harness 用的 sNN（來源主機名 sNN.d2-sources.example 不能有底線）。
只改組號：manifest 的 "set" 欄位、sets/ 底下的目錄名；重算 manifest.sha256。內容與真值一個位元組都不動。用法：normalize_ids.py <dir>"""
import hashlib
import json
import pathlib
import re
import sys

d = pathlib.Path(sys.argv[1])
m = json.loads((d / "manifest.json").read_text())
for s in m["sets"]:
    mm = re.fullmatch(r"set_(\d+)", s["set"])
    if not mm:
        continue
    new = f"s{int(mm.group(1)):02d}"
    (d / "sets" / s["set"]).rename(d / "sets" / new)
    s["set"] = new
raw = json.dumps(m, ensure_ascii=False, indent=1).encode()
(d / "manifest.json").write_bytes(raw)
(d / "manifest.sha256").write_text(hashlib.sha256(raw).hexdigest() + "\n")
print([s["set"] for s in m["sets"]])
