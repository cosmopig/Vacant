"""R460 C1/C2/C3：數 LCB 原始視窗檔能產出幾題可用題目——**用的是 build_lcb_bank 自己的
`_convert`**（不自寫近似過濾器：自寫一份等於在量另一把尺）。

從 stdin 串流讀（原始檔 0.6–1.3 GB，不落盤，見磁碟鐵律），逐行轉換，只留輕量欄位。
輸出 JSON：kept / stdin / easy / dropped / in、by_difficulty、日期分佈、task_id 清單。

用法：curl -sL <raw url> | python3 ops/gain/count_lcb_yield.py --src lcb_test3.jsonl --out x.json
"""
from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, "ops/gain")
from build_lcb_bank import _convert  # noqa: E402  同一支轉換器，C2 靠它才有意義


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="source_file 標籤，例如 lcb_test3.jsonl")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    stats = {"in": 0, "kept": 0, "stdin": 0, "easy": 0, "dropped": 0}
    kept: list[dict] = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        stats["in"] += 1
        if not (rec.get("starter_code") or "").strip():
            stats["stdin"] += 1
            continue
        if rec.get("difficulty") == "easy":
            stats["easy"] += 1
            continue
        t = _convert(rec, a.src)
        if t is None:
            stats["dropped"] += 1
            continue
        stats["kept"] += 1
        kept.append({"task_id": t["task_id"], "difficulty": t["difficulty"],
                     "contest_date": t["contest_date"], "platform": t["platform"],
                     "n_hidden_total": t["n_hidden_total"]})
    by_diff: dict[str, int] = {}
    for k in kept:
        by_diff[k["difficulty"]] = by_diff.get(k["difficulty"], 0) + 1
    dates = sorted(k["contest_date"] for k in kept)
    out = {
        "src": a.src, "stats": stats, "by_difficulty": by_diff,
        "date_min": dates[0] if dates else None, "date_max": dates[-1] if dates else None,
        "n_before_2024_08": sum(1 for d in dates if d < "2024-08"),
        "n_before_2024_01": sum(1 for d in dates if d < "2024-01"),
        "kept": kept,
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "kept"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
