"""沒用過的 DABstep 題清單（2026-09-27；裁決 BIGGER_EFFECT §十三）：450 題減掉正式 79 題、減掉付費校準的 1716、再減掉留出批次的 100 題。

留出批次（`PREREG_20260926_ZERO_CONFIG_V34_HELDOUT`）跑過、原始資料在容器回到舊快照時遺失、評分沒有人看（RUNLOG §13、§15），
但模型已經在那 100 題上跑過——所以也算用過。剩下的題全部列出、每一題的題目目錄 sha256 釘住（和留出清單同一種釘法；
先用留出清單的 100 個雜湊驗證釘死的題目目錄沒有變，對不上就不寫）。

    python3 ops/eval/local/make_unseen.py --dataset <釘死的 450 題目錄> --out <UNSEEN_MANIFEST.json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
FORMAL = REPO / "ops" / "eval" / "evidence_20260925" / "pilot" / "FORMAL_MANIFEST.json"
HELDOUT = REPO / "ops" / "eval" / "evidence_20260926_local" / "heldout" / "HELDOUT_MANIFEST.json"


def tsha(base: str) -> str:
    """留出清單用的那一種（逐字照抄）：os.walk 排序、相對路徑＋內容，跳過 __pycache__。"""
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(base)):
        dirs.sort()
        if "__pycache__" in root:
            continue
        for fn in sorted(files):
            p = os.path.join(root, fn)
            h.update(os.path.relpath(p, base).encode())
            h.update(open(p, "rb").read())
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dataset", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args(argv)
    formal = {x["task"] for x in json.loads(FORMAL.read_text())["tasks"]}
    held = json.loads(HELDOUT.read_text())
    bad = [x["task"] for x in held["tasks"] if tsha(str(a.dataset / f"dabstep-{x['task']}")) != x["task_dir_sha256"]]
    if bad:
        print(f"釘死的題目目錄和留出清單對不上：{bad[:10]}…（{len(bad)} 題）——不寫", file=sys.stderr)
        return 1
    allt = sorted(int(d.split("-")[1]) for d in os.listdir(a.dataset) if d.startswith("dabstep-"))
    pool = [t for t in allt if str(t) not in formal and t != 1716]
    assert len(pool) == held["pool_size"], (len(pool), held["pool_size"])
    used = {x["task"] for x in held["tasks"]}
    unseen = [t for t in pool if str(t) not in used]
    man = {"rule": "sorted(450 Harbor DABstep tasks − formal 79 − {1716} − heldout 100)",
           "pool_size": len(pool), "heldout_verified": len(held["tasks"]), "count": len(unseen),
           "tasks": [{"task": str(t), "task_dir_sha256": tsha(str(a.dataset / f"dabstep-{t}"))} for t in unseen]}
    a.out.write_text(json.dumps(man, indent=1) + "\n")
    print(json.dumps({k: man[k] for k in ("pool_size", "heldout_verified", "count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
