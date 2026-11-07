#!/usr/bin/env python3
"""從 glm 原始輸出（~/dev/ops/logs/vibe）離線重建 G1 擷取結果——0 次模型呼叫。

argon 20261107_1248：out/<task>.<model>.json 曾被擷取器裡「替模型補條件」的程式改寫過
（9b91a0f5，兄弟條目複製 exclude/dedup_by/compute、orders.csv 硬塞 CANCELLED/net_sales），
也曾被手動換成前一輪的形狀（r1184 orders_monthly）。這支腳本讓每個 out 檔都能追回
「哪一次呼叫的原始輸出」＋「目前擷取規則」，不再有無法重現的需求檔。

規則：每題取 vibe_calls.jsonl 中該 model、rc=0、purpose 以 "<task> " 開頭的**最後一次**呼叫
（不挑結果較好的那次）。寫入 raw_output 與 provenance.log；run_eval 讀到 raw_output 時
一律以目前的 build_requirement_set 重建。

用法：python3 ops/reqloop/extract/rebuild_from_logs.py --model glm53 [--ops ~/dev/ops]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from vacant_network.reqloop.extract import build_requirement_set, parse_model_output  # noqa: E402


def latest_call(calls: list[dict], model: str, task: str) -> dict | None:
    hit = None
    for c in calls:
        if c.get("model") == model and c.get("rc") == 0 and str(c.get("purpose", "")).startswith(task + " "):
            hit = c
    return hit


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="glm53")
    ap.add_argument("--ops", default="~/dev/ops")
    ap.add_argument("--g1", default=str(REPO_ROOT / "ops" / "reqloop" / "g1" / "tasks"))
    ap.add_argument("--out-dir", default=str(REPO_ROOT / "ops" / "reqloop" / "extract" / "out"))
    a = ap.parse_args(argv)
    ops = pathlib.Path(a.ops).expanduser()
    calls = [json.loads(l) for l in (ops / "state" / "vibe_calls.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rc = 0
    for t_dir in sorted(p for p in pathlib.Path(a.g1).iterdir() if (p / "requirements.json").is_file()):
        c = latest_call(calls, a.model, t_dir.name)
        if c is None:
            print(f"{t_dir.name}: 無呼叫紀錄（fail-closed，不寫）")
            rc = 2
            continue
        log = ops / "logs" / "vibe"
        raw = (log / f"{c['log']}.output.md").read_text(encoding="utf-8")
        prompt = (log / f"{c['log']}.prompt.md").read_text(encoding="utf-8")
        user_text = (t_dir / "request.md").read_text(encoding="utf-8")
        req, report = build_requirement_set(t_dir.name, parse_model_output(raw), user_text)
        doc = req.to_dict()
        doc.update({
            "model": a.model,
            "report": report.to_dict(),
            "raw_output": raw,
            "provenance": {
                "log": c["log"], "ts": c.get("ts"),
                "total_tokens": c.get("total_tokens"),
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "rule": "latest rc=0 call for this task/model; rebuilt offline by rebuild_from_logs.py",
            },
        })
        out = pathlib.Path(a.out_dir) / f"{t_dir.name}.{a.model}.json"
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{t_dir.name}: log={c['log']} 條目 {len(req.items)}、丟棄 {len(report.discarded)}、"
              f"unverified {len(report.unverified)}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
