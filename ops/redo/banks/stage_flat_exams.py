#!/usr/bin/env python3
"""把 vacant-cloud 的扁平考卷目錄（<task>/xm_test.py、xmv_test.py、pb_test.py、ex_test.py）
轉成 import_exams.py 要的 <task>/<KIND>/<file> 版面（只複製、不改內容；MANIFEST 照抄）。
用法：stage_flat_exams.py <flat_exam_dir> <staging_dir> [--kinds XM,XMV,PB,EX]"""
import argparse, pathlib, shutil, sys
MAP = {"XM": "xm_test.py", "XMV": "xmv_test.py", "PB": "pb_test.py", "EX": "ex_test.py"}
ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--kinds", default="XM,XMV,PB,EX")
a = ap.parse_args(); src, dst = pathlib.Path(a.src), pathlib.Path(a.dst)
if dst.exists(): sys.exit(f"refuse: {dst} exists")
kinds = [k for k in a.kinds.split(",") if k]; missing = []
for t in sorted(p for p in src.iterdir() if p.is_dir() and p.name.startswith("ex_")):
    for k in kinds:
        f = t / MAP[k]
        if not f.is_file(): missing.append(f"{t.name}/{MAP[k]}"); continue
        (dst / t.name / k).mkdir(parents=True, exist_ok=True); shutil.copy2(f, dst / t.name / k / MAP[k])
for extra in ("MANIFEST.json",):
    if (src / extra).is_file(): dst.mkdir(parents=True, exist_ok=True); shutil.copy2(src / extra, dst / extra)
if missing: print(f"MISSING {len(missing)}: {missing[:10]}"); sys.exit(2)
print("STAGED", dst)
