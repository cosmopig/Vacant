"""twin/fortune_recompute — 用已歸檔的真跑紀錄（`evidence_fortune_*/final/`）**離線重算**命盤卡（不用重跑模型）。

這支在架構裡承重什麼：命盤卡第二版（確定性生成）的離線驗證。步驟紀錄從旁註 `fNN.lifecycle.sidecar.jsonl` 的 `twin_step` 還原
（地點代號 → 地點名；plan／artifact／ground），信取 `fNN.json` 的 `letter_full`，標題取最後一次嘗試的成品，退回次數＝嘗試數 − 1。
⚠ 誠實邊界：旁註的 `twin_step` 不帶檔名，所以標題用 `fNN.json` 裡記下的成品全文；觀眾原文（TRAITS）已撤回，LEAK 比對這裡略過。
用法：python3 ops/exhibit/twin/fortune_recompute.py <evidence final 目錄>
"""
from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ops.exhibit.twin import fortune as fz  # noqa: E402
from ops.exhibit.twin import sidecar as sc  # noqa: E402


def rows_from_sidecar(rows: list[dict]) -> list[dict]:
    inv = {code: place for place, code in sc.GROUND_PLACES.items()}
    out = []
    for r in rows:
        if r.get("type") != "twin_step":
            continue
        kind, tool = r.get("path_kind"), {"read": "ws_read", "write": "ws_write", "list": "ws_list"}[r["step"]]
        if kind and kind.startswith("ground:"):
            path = f"地上/{inv[kind.split(':', 1)[1]]}/x"
        elif kind == "plan":
            path = "PLAN.md"
        elif kind == "traits":
            path = "TRAITS.md"
        elif kind == "artifact":
            path = "成品.md"
        else:
            path = "."
        out.append({"ts_ms": r["ts_ms"], "seq": r["seq"], "tool": tool, "path": path, "ok": r.get("ok")})
    # 段 2 的起點＝第一次讀 信.md：旁註把 信.md 歸 other，所以在「讀 TRAITS 之後第一個非 TRAITS 的 other 讀」處補一個
    return out


def recompute(d: pathlib.Path) -> list[dict]:
    cards = []
    for n in range(1, 9):
        rec = json.loads((d / f"f{n}.json").read_text(encoding="utf-8"))
        f = rec["fortune_final"]
        rows = rows_from_sidecar(sc.read(d / f"f{n}.lifecycle.sidecar.jsonl"))
        # 旁註的 other 讀（信.md、WORLD.md）被歸 other：還原成 信.md 讓 stage2_rows 找得到段 2 的起點
        for r in rows:
            if r["path"] == "." and r["tool"] == "ws_read":
                r["path"] = "信.md"
                break
        arts = {a["name"]: a["text"] for a in rec["attempts"][-1]["artifacts"]}
        card = fz.compose_card(f, letter_text=rec["letter_full"], rows=rows, files=arts,
                               retries=max(0, rec["attempts_used"] - 1))
        cards.append({"name": rec["name"], "card": card, "md": fz.card_md(card)})
    return cards


if __name__ == "__main__":
    for c in recompute(pathlib.Path(sys.argv[1])):
        print(f"【{c['name']}】\n{c['md']}")
