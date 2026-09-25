"""組出 DABstep 的正式 79 題（評測計畫 §3.2）：72 題簡單（Harbor 的 450 題裡）＋ 7 題困難 dev。
和 dev 重複的 6 題（5、49、70、1305、1681、1753）用 dev 版——那是官方的真答案（Harbor 那一份是從排行榜擷取的，
例：70 題 Harbor 是 `Not`、dev 是 `Not Applicable`；49 題 `BE` 對 `B. BE`）。

    python3 ops/eval/dabstep_formal.py --pinned <dabstep_pin.py 的輸出> --dev <adapter 產生的 dev 題目目錄> \
        --tasks ops/eval/pilot/tasks.json --out <輸出目錄>

dev 題目的 Dockerfile 一樣換成釘死的映像（讀 `PIN_MANIFEST.json`）。寫 `FORMAL_MANIFEST.json`：每一題的來源、
`tests/` 的 sha256（評分程式＋答案都在那裡；預註冊釘這個）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil


def tree_sha(d: pathlib.Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in d.rglob("*") if p.is_file()):
        h.update(str(f.relative_to(d)).encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pinned", required=True)
    ap.add_argument("--dev", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pinned, dev, out = pathlib.Path(a.pinned), pathlib.Path(a.dev), pathlib.Path(a.out)
    pin = json.loads((pinned / "PIN_MANIFEST.json").read_text())
    formal = json.loads(pathlib.Path(a.tasks).read_text())["formal_79"]
    dev_ids = {p.name.removeprefix("dabstep-") for p in dev.glob("dabstep-*")}
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    rows = []
    for t in formal:
        name = f"dabstep-{t}"
        src = dev / name if t in dev_ids else pinned / name
        if not src.is_dir():
            raise SystemExit(f"missing task {name}")
        shutil.copytree(src, out / name)
        (out / name / "environment").mkdir(exist_ok=True)
        for extra in (out / name / "environment").iterdir():
            if extra.name != "Dockerfile":
                extra.unlink()
        (out / name / "environment" / "Dockerfile").write_text(
            f"# Vacant eval: pinned DABstep environment (ops/eval/dabstep_pin.py)\n"
            f"FROM {pin['image']}\nWORKDIR /app\n")
        rows.append({"task": t, "source": "dev" if t in dev_ids else "harbor-450",
                     "tests_sha256": tree_sha(out / name / "tests")})
    man = {"pin": pin, "count": len(rows), "tasks": rows}
    (out / "FORMAL_MANIFEST.json").write_text(json.dumps(man, indent=1))
    print(json.dumps({"count": len(rows),
                      "from_dev": [r["task"] for r in rows if r["source"] == "dev"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
