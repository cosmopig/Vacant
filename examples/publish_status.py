#!/usr/bin/env python3
"""把一個信任生態的現況輸出成 status.json，供文件網站即時顯示。

用途（12 §5 的延伸；回應「網站要一邊實驗一邊更新」）：
    python examples/publish_status.py --root ~/.vacant-mcp \\
        --out ../vacant-docs-web/data/status.json

網站是純靜態的，沒有後端可查詢；它每 30 秒輪詢這個檔案。實驗跑到哪裡、
證據到哪一階，就由這支腳本落盤，網站據此更新——**網站不自己推論任何東西**。

紀律：
  - 只輸出可被獨立重算的量（ledger 滾動雜湊、驗鏈結果、事件計數）。
  - 宣稱階梯的 met 由 vacant.dashboard.claim_ladder 決定，與觀測台同一份邏輯，
    不在這裡另寫一套（兩處判準不一致比沒有判準更糟）。
  - 不輸出任何交付內容、prompt、答案或私鑰——只有計數與雜湊。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vacant.dashboard import claim_ladder  # noqa: E402


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=10,
            cwd=Path(__file__).resolve().parent.parent,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _test_counts(run_tests: bool) -> dict[str, object]:
    """跑一次完整測試套件並回報數字。不跑就如實回 None，不沿用舊值。"""
    if not run_tests:
        return {"ran": False, "passed": None, "skipped": None, "failed": None}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
        capture_output=True, text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    out: dict[str, object] = {"ran": True, "summary": tail, "ok": proc.returncode == 0}
    for key, token in (("passed", "passed"), ("skipped", "skipped"), ("failed", "failed")):
        for part in tail.replace(",", " ").split():
            if part == token:
                idx = tail.replace(",", " ").split().index(part)
                words = tail.replace(",", " ").split()
                if idx > 0 and words[idx - 1].isdigit():
                    out[key] = int(words[idx - 1])
    return out


def build_status(root: Path, *, run_tests: bool = False) -> dict[str, object]:
    from vacant.cli import EchoLikeBrain
    from vacant.ecosystem import Ecosystem

    payload: dict[str, object] = {
        "generated_ms": time.time_ns() // 1_000_000,
        "commit": _git("rev-parse", "--short", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "tests": _test_counts(run_tests),
        "ecosystem": None,
    }

    if root.exists():
        eco = Ecosystem(root, EchoLikeBrain(), root_mode=None)
        integrity = eco.integrity()
        scoreboard = eco.scoreboard()
        payload["ecosystem"] = {
            "root": root.name,
            "identities": [
                {"name": i["name"], "credit": i["credit"], "n_obs": i["n_obs"],
                 "chain_ok": i["chain_ok"], "genesis_proven": i["genesis_proven"],
                 "deliveries": i["deliveries"], "episodes": i["episodes"],
                 "flags": i["flags"]}
                for i in eco.identities()
            ],
            "counters": eco.counters(),
            "cost": eco.cost(),
            "integrity": {"ledger_seq": integrity["ledger_seq"],
                          "ledger_head": integrity["ledger_head"],
                          "all_chains_ok": integrity["all_chains_ok"]},
            "scoreboard": scoreboard,
        }
        payload["claim_ladder"] = claim_ladder(
            integrity=integrity, scoreboard=scoreboard,
            b_layer_summary=root / "b_layer" / "summary.md")
    else:
        payload["claim_ladder"] = claim_ladder(integrity={}, scoreboard={})

    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path.home() / ".vacant-mcp",
                    help="信任生態的 root（沒有就只輸出 repo 層級狀態）")
    ap.add_argument("--out", type=Path, required=True, help="輸出的 status.json 路徑")
    ap.add_argument("--run-tests", action="store_true",
                    help="跑一次完整測試套件並把數字寫進去（較慢）")
    args = ap.parse_args()

    payload = build_status(args.root, run_tests=args.run_tests)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫出 {args.out}")
    print(f"  commit {payload['commit']} · 階梯 "
          f"{sum(1 for r in payload['claim_ladder'] if r['met'])}/{len(payload['claim_ladder'])} 已達")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
