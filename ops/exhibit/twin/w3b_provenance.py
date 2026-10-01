"""twin/w3b_provenance — 確定性小腳本：樣本檔（w3b_samples 的輸出）每一跑的成品，
有幾個「數字／印紋」找得到出處、幾個找不到。字面比對（見 `twinground.provenance`）。

用法：python3 ops/exhibit/twin/w3b_provenance.py <samples.json> [--out table.json]
地上的檔從 `world/materials/` 依樣本裡記的 `ground_files` 讀回（和當時複製進房間的是同一份，sha256 在樣本的 run-dir 紀錄裡）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from ops.exhibit.twin import twinground  # noqa: E402

WORLD = pathlib.Path(twinground.__file__).parent / "world" / "WORLD.md"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("samples")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    runs = json.loads(pathlib.Path(a.samples).read_text(encoding="utf-8"))["runs"]
    world = WORLD.read_text(encoding="utf-8")
    table = []
    for r in runs:
        gt = [(twinground.MATERIALS / f.split("/", 1)[1]).read_text(encoding="utf-8")
              for f in r.get("ground_files", [])]
        arts = [x["text"] for x in r.get("artifacts_full", [])]
        art = twinground.provenance(arts, gt, [world])
        plan = twinground.provenance([r.get("plan_md") or ""], gt, [world])
        row = {"name": r["name"], "artifact_found": art["found"], "artifact_missing": art["missing"],
               "artifact_missing_tokens": art["missing_tokens"],
               "plan_found": plan["found"], "plan_missing": plan["missing"],
               "plan_missing_tokens": plan["missing_tokens"]}
        table.append(row)
        print(json.dumps(row, ensure_ascii=False))
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(table, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
