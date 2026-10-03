#!/usr/bin/env python3
"""把 DABstep 正式 79 題轉成 cell.sh 的題目目錄（Colab 沒有 Docker）。
    stage_dabstep.py --harbor450 <harbor-datasets@e25eec6e 的 datasets/dabstep> --dev <adapter --split dev 的輸出>
                     --data <7 個資料檔> --manifest <FORMAL_MANIFEST.json> --out <staged 根>
每題：instruction.txt＝instruction.md 原文（Harbor 把它整段當 pi 的提示）；workspace/data/＝7 個資料檔（＝映像的 /app/data）；
hidden/tests/＝題目的 tests/（逐檔不動，tree sha256 必須等於 FORMAL_MANIFEST）；scorer.py＝dabstep_score.py。
資料檔 sha256 必須等於 FORMAL_MANIFEST 的 pin。任何一項對不上就停。印 plan 的 tasks 陣列。"""
import argparse, hashlib, json, pathlib, shutil
HERE = pathlib.Path(__file__).resolve().parent
def tree_sha(d):
    h = hashlib.sha256()
    for f in sorted(p for p in d.rglob("*") if p.is_file()):
        h.update(str(f.relative_to(d)).encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()
ap = argparse.ArgumentParser()
for k in ("harbor450", "dev", "data", "manifest", "out"):
    ap.add_argument("--" + k, required=True, type=pathlib.Path)
a = ap.parse_args()
man = json.loads(a.manifest.read_text())
for n, want in man["pin"]["data_sha256"].items():
    got = hashlib.sha256((a.data / n).read_bytes()).hexdigest()
    if got != want:
        raise SystemExit(f"data {n}: {got} != {want}")
tasks = []
for t in man["tasks"]:
    src = (a.dev if t["source"] == "dev" else a.harbor450) / f"dabstep-{t['task']}"
    if tree_sha(src / "tests") != t["tests_sha256"]:
        raise SystemExit(f"tests mismatch {t['task']}")
    d = a.out / "dabstep" / t["task"]
    if d.exists():
        shutil.rmtree(d)
    (d / "workspace" / "data").mkdir(parents=True)
    for n in man["pin"]["data_sha256"]:
        shutil.copy2(a.data / n, d / "workspace" / "data" / n)
    shutil.copytree(src / "tests", d / "hidden" / "tests")
    shutil.copy2(HERE / "dabstep_score.py", d / "scorer.py")
    (d / "instruction.txt").write_text((src / "instruction.md").read_text())
    tasks.append({"bank": "dabstep", "id": t["task"], "dir": f"/srv/eval/staged/dabstep/{t['task']}", "source": t["source"]})
print(json.dumps(tasks))
