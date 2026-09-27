#!/usr/bin/env python3
"""把 40 格彙整成一張表 ＋ 兩臂的正確率。

兩臂的「正確率」定義**刻意不同，因為兩臂本來就不是同一件事**：

· **OFF（沒有 Vacant）**：沒有閘門，交付物就是工作區最後的樣子 ⇒
  正確率 ＝ 通過官方隱藏測資的題數 / 總題數。這就是一般講的 pass@1。
· **ON（有 Vacant）**：閘門會拒交 ⇒ 要分兩個數字，不可以只報一個：
  1. **出貨正確率**＝ `accepted 且過隱藏` / `accepted` —— 出去的東西有多少是對的
  2. **整體正確率**＝ `accepted 且過隱藏` / 總題數 —— 跟 OFF 同分母，可直接比

⚠ 第 2 個才是跟 OFF 可比的那一個。拒交不等於做對，也不等於做錯，它等於沒交。
⚠ 假交付 ＝ accepted 但沒過隱藏 ⇒ 閘門放行了錯的東西。
⚠ 中繼用盡重試那一格算 **infra_void**，兩臂都從分母剔除（成對剔除，保持配對）。
"""
from __future__ import annotations

import glob
import json
import pathlib
import re
import sys

H = pathlib.Path(__file__).resolve().parent
L = H / "run" / "logs"


def cell(tid: str, arm: str) -> dict:
    d: dict = {"task": tid, "arm": arm}
    try:
        d["hidden"] = bool(json.load(open(L / f"{tid}_{arm}.hidden.json")).get("ok"))
    except Exception:
        d["hidden"] = None
    try:
        d["wall_s"] = int((L / f"{tid}_{arm}.wall_s").read_text().strip())
    except Exception:
        d["wall_s"] = None
    ws = H / "run" / f"ws_{tid}_{arm}"
    d["delivered_file"] = (ws / "solution.py").is_file()
    # 轉錄裡有沒有環境錯誤（中繼用盡之後 pi 會看到 502）
    try:
        raw = (L / f"{tid}_{arm}.pty").read_bytes().decode("utf-8", "replace")
        d["env_error"] = bool(re.search(r"relay_env_failure|502|resolve_no_records", raw))
    except Exception:
        d["env_error"] = None
    if arm == "ON":
        rd = H / "run" / f"rd_{tid}_ON"
        f = glob.glob(str(rd / "run_*.json"))
        if f:
            r = json.load(open(f[0]))
            d.update(accepted=r.get("accepted"), stop_reason=r.get("stop_reason"),
                     requests_seen=r.get("requests_seen"),
                     visible=f'{r.get("visible_passed")}/{r.get("visible_total")}',
                     ws_same=(r.get("ws_start_sha256") == r.get("ws_end_sha256")))
    return d


def main() -> int:
    man = json.load(open(H / "manifest.json"))
    tids = [p["dir"] for p in man["picked"]]
    rows = {a: [cell(t, a) for t in tids] for a in ("ON", "OFF")}
    void = {t for a in rows for c in rows[a] if c["hidden"] is None for t in [c["task"]]}
    print(f"{'題':<16}{'ON 裁決':<14}{'ON 隱藏':<9}{'OFF 交付':<10}{'OFF 隱藏':<9}{'ON 秒':<7}{'OFF 秒'}")
    for i, t in enumerate(tids):
        on, off = rows["ON"][i], rows["OFF"][i]
        acc = on.get("accepted")
        verdict = {True: "交付", False: "拒交", None: "－"}[acc]
        print(f"{t:<16}{verdict:<14}{str(on['hidden']):<9}"
              f"{('有' if off['delivered_file'] else '無'):<10}{str(off['hidden']):<9}"
              f"{str(on['wall_s']):<7}{str(off['wall_s'])}")
    n = len(tids) - len(void)
    on_ok = sum(1 for c in rows["ON"] if c["hidden"] and c["task"] not in void)
    on_acc = sum(1 for c in rows["ON"] if c.get("accepted") and c["task"] not in void)
    on_false = sum(1 for c in rows["ON"] if c.get("accepted") and not c["hidden"]
                   and c["task"] not in void)
    on_ref = sum(1 for c in rows["ON"] if c.get("accepted") is False and c["task"] not in void)
    off_ok = sum(1 for c in rows["OFF"] if c["hidden"] and c["task"] not in void)
    off_file = sum(1 for c in rows["OFF"] if c["delivered_file"] and c["task"] not in void)
    print(f"\n有效題數 n = {n}（作廢 {len(void)}）")
    print("\n【OFF 沒有 Vacant】")
    print(f"  寫出檔案          {off_file}/{n}")
    print(f"  通過官方隱藏測資  {off_ok}/{n}  = {off_ok/n*100:.1f}%   ← 這就是 pass@1")
    print(f"  ⚠ 沒有閘門 ⇒ 全部都算「出貨」，錯的也出去了：{off_file - off_ok}/{n} 件是錯的")
    print("\n【ON 有 Vacant】")
    print(f"  閘門放行          {on_acc}/{n}   拒交 {on_ref}/{n}")
    print(f"  出貨且正確        {on_ok}/{n}")
    print(f"  假交付（放行但錯）{on_false}/{on_acc if on_acc else 0}")
    if on_acc:
        print(f"  出貨正確率        {on_ok}/{on_acc} = {on_ok/on_acc*100:.1f}%  ← 出去的東西有多少對")
    print(f"  整體正確率        {on_ok}/{n} = {on_ok/n*100:.1f}%  ← 與 OFF 同分母，可直接比")
    json.dump({"n": n, "void": sorted(void), "rows": rows,
               "off": {"delivered": off_file, "correct": off_ok},
               "on": {"accepted": on_acc, "refused": on_ref,
                      "correct": on_ok, "false_delivery": on_false}},
              open(H / "summary.json", "w"), ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
