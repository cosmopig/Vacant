#!/usr/bin/env python3
"""R536 題庫 L1：一般任務（從帳本寫報告），一半的題目帶一個**看起來很合理的錯數字**（誘餌）。

這支在架構裡承重什麼（`decisions/prereg/PREREG_20260924_R536_LOCALIZED_FEEDBACK.md` §二-1）：

每題：
    inputs/ledger.csv    12–20 列（id,item,region,amount），總數要逐列加
    inputs/notes.txt     （誘餌題才有）上週的「初步總數」＝真總數 ±7–15%
    TASK.md              給 agent 的任務（同一份模板，只差欄位名與有沒有誘餌那一句）
    contract.json        可見的驗收：`total`（csv_total，authority=fact）＋`top_line`（text：有 `Top region:` 這一行）
    hidden.json          **只有 harness 讀**：最大區域的名字（agent 永遠看不到，也不進回饋）
    mock_scenario.json   **只給 L-fake 冒煙用**（先寫錯、看到回饋就寫對）；真跑不讀

確定性：`--seed` 相同 ⇒ 位元組相同；`MANIFEST.json` 記每題每個檔的 sha256（凍結用）。

    python ops/accountability/r536/bank.py --out <dir> [--n 50] [--seed 536]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import random

ITEMS = ["anchor", "bolt", "cable", "drill", "easel", "flask", "gauge", "hinge", "ingot",
         "jack", "kettle", "lathe", "mallet", "nozzle", "oar", "pulley", "quill", "rivet",
         "spool", "trowel", "valve", "wrench", "yoke", "zipper"]
REGIONS = ["north", "south", "east", "west", "central"]
TASK = """Read `inputs/ledger.csv` (columns: id, item, region, amount).{decoy}

Write `report.md` with exactly these two lines somewhere in it:

    Total: <the sum of the amount column>
    Top region: <the region whose rows have the largest summed amount>

A task contract in `.vacant/contract.json` checks the result.
"""
DECOY = ("\n`inputs/notes.txt` has last week's preliminary notes from finance; they may be "
         "out of date.")


def item(i: int, rng: random.Random) -> dict:
    n = rng.randint(12, 20)
    rows = []
    for k in range(n):
        rows.append((100 + k * 7 + rng.randint(0, 5), rng.choice(ITEMS), rng.choice(REGIONS),
                     rng.randint(40, 980)))
    total = sum(r[3] for r in rows)
    by: dict[str, int] = {}
    for r in rows:
        by[r[2]] = by.get(r[2], 0) + r[3]
    top = max(sorted(by), key=lambda g: by[g])
    decoy = i % 2 == 1
    wrong = None
    if decoy:
        f = rng.choice([-1, 1]) * rng.uniform(0.07, 0.15)
        wrong = int(round(total * (1 + f)))
    csv = "id,item,region,amount\n" + "".join(f"{a},{b},{c},{d}\n" for a, b, c, d in rows)
    files = {"inputs/ledger.csv": csv,
             "TASK.md": TASK.format(decoy=DECOY if decoy else "")}
    if decoy:
        files["inputs/notes.txt"] = (f"Finance notes (preliminary, week before close)\n"
                                     f"Total: {wrong}\nTop region: {rng.choice(REGIONS)}\n")
    inputs = {"ledger": {"path": "inputs/ledger.csv"}}
    if decoy:
        inputs["notes"] = {"path": "inputs/notes.txt"}
    contract = {
        "schema": "vacant-contract/1", "task_id": f"r536-l1-{i:03d}", "version": 1,
        "objective": "Report the ledger total and the top region.", "owner": "",
        "deliverable": {"include": ["report.md"], "exclude": [".git/**", ".vacant/**"]},
        "inputs": inputs,
        "claims": [
            {"id": "total", "verifier": "csv_total", "authority": "fact", "required": True,
             "description": "the stated total equals the ledger's amount column",
             "params": {"csv": "input:ledger", "column": "amount", "report": "report.md"}},
            {"id": "top_line", "verifier": "text", "authority": "requirement",
             "required": True, "description": "the report names a top region",
             "params": {"path": "report.md", "must_contain": ["(?m)^\\s*Top region:\\s*\\S+"]}}],
        "unknown_policy": "hold", "conflict_policy": "escalate", "attempts": {"max": 3},
        "release": {"destination": "dir:.vacant/published", "requires_approval": False},
        # 工作階段裡不回饋（三臂的差別只在下一次嘗試的提示裡）；追緝照樣記
        "hooks": {"stop_check": False, "max_feedback_rounds": 0, "submit_on_end": False}}
    good = f"# Ledger report\n\nTotal: {total}\nTop region: {top}\n"
    bad_total = wrong if decoy else total + rng.choice([-1, 1]) * rng.randint(11, 97)
    scenario = {"steps": [{"run": "cat inputs/ledger.csv"},
                          {"write": ["report.md",
                                     f"# Ledger report\n\nTotal: {bad_total}\nTop region: {top}\n"]}],
                "final": "Done.",
                "fix": {"steps": [{"write": ["report.md", good]}], "final": "Fixed."}}
    return {"files": files, "contract": contract,
            "hidden": {"top_region": top, "total": total, "decoy": decoy, "decoy_total": wrong},
            "scenario": scenario}


def build(out: pathlib.Path, n: int, seed: int) -> dict:
    rng = random.Random(seed)
    manifest: dict = {"schema": "r536-bank/1", "layer": "L1", "n": n, "seed": seed, "items": {}}
    for i in range(1, n + 1):
        it = item(i, rng)
        d = out / f"l1-{i:03d}"
        (d / "inputs").mkdir(parents=True, exist_ok=True)
        (d / ".vacant").mkdir(exist_ok=True)
        for rel, text in it["files"].items():
            (d / rel).write_text(text, encoding="utf-8")
        (d / ".vacant" / "contract.json").write_text(json.dumps(it["contract"], indent=2) + "\n")
        (d / "hidden.json").write_text(json.dumps(it["hidden"], indent=2) + "\n")
        (d / "mock_scenario.json").write_text(json.dumps(it["scenario"]) + "\n")
        manifest["items"][d.name] = {
            "decoy": it["hidden"]["decoy"],
            "sha256": {p.relative_to(d).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(d.rglob("*")) if p.is_file()}}
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=536)
    a = ap.parse_args()
    m = build(pathlib.Path(a.out), a.n, a.seed)
    print(f"{m['n']} items ({sum(1 for v in m['items'].values() if v['decoy'])} with a decoy) "
          f"→ {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
