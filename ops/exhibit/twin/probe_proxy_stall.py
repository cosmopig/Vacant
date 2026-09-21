"""twin/probe_proxy_stall — 「連不上的位址」為什麼會卡住一分鐘以上。

## 這支在架構裡承重什麼

2026-09-21 補視窗測試時撞到的：`test_loop_cli_passes_the_window` 逾時（180 秒），
而它跑的是 `loop --cloud http://127.0.0.1:1`——**一個必定連不上的本機位址**。
直覺會判成「死位址不會快速拒絕」，那是**錯的結論**，而且會害人去改 timeout。

真因量出來是這個：**`urllib.request.getproxies()` 本身要跑很久。**
macOS 上它 ＝ `getproxies_environment() or getproxies_macosx_sysconf()`，
後者是 SystemConfiguration 那一次查詢。而 `urlopen` 的**每個新行程第一通**
都要付一次。連線本身（connection refused）是 **0.00 秒**。

判讀紀律（`instruments-lie-before-you-conclude-zero`）：
量到「慢」的時候先問**是被量的東西慢，還是量具慢**。這裡是量具那一邊——
換一個埠號、換一個主機都沒有用，因為付錢的不是連線。

## 🔴 它是**間歇**的，所以一次取樣會說謊

同一台機器、同一天實測到的 `getproxies()` 單次耗時橫跨三個數量級：

| 觀測 | 秒 |
|---|---|
| 2026-09-21 22:5x（三個 agent 同時在跑） | **206.33** |
| 同上，稍早 | **89.67** |
| 同上，更早（第一通 `urlopen` 的牆鐘） | 49.22 / 16.08 |
| 23:00 本探針**第一版（單次取樣）** | **1.48 ⇒ 判成「沒問題」** |
| 23:02 本探針 reps=6，同一台同一分鐘 | 1.38／3.44／4.66／11.24／17.64／**119.83** |

⇒ **一次取樣跑出 1.48 秒就結論「沒問題」是錯的**——隔兩分鐘同一組設定就量到
119.83 秒。那正是這份 repo 一直在抓的那個病。所以這一支**取多次、看最大值**，
判準寫在 `verdict.baseline_stalled_this_round`（`max` 超過 `STALL_S` 就算量到），
而且**「這一輪沒量到」寫 `stall_observed: false` 不寫「不存在」**
——間歇現象量不到只代表這一輪沒撞上。

落盤：`evidence_window_20260921/proxy_stall_mac_20260921.json`
（`baseline` max 119.83s ／ `no_proxy=*` max **0.0s**（6/6）／
負控制 `no_proxy_but_not` max 11.35s **沒有改善** ⇒ 改善確實來自
「變數名以 `_proxy` 結尾」這件事，不是「多設了一個環境變數」）。

## 誠實邊界

1. **這是本機（Mac）的數字，不是展場的。** 展場那台是 1003（Windows），
   Python 走的是 `getproxies_registry()`（讀登錄檔），**我們沒有在那台量過**。
   沒量到的欄位寫 `null` 不寫 0。
2. **`no_proxy=*` 不是「關掉 proxy 支援」。** `getproxies_environment()` 一旦回
   非空字典，CPython 就**整段跳過** OS 那次查詢（`proxy_bypass()` 也跟著走 env 分支）。
   `http_proxy`／`https_proxy` 照樣生效——需要 proxy 的場地設環境變數就好。
3. **這一支不改產品行為。** 它只是把「為什麼測試要帶 `no_proxy=*`」的證據留下來。
   `twinlink` 自己**沒有**設 `no_proxy`：要不要在展場的 unit 裡設，是另一條線的事
   （見報告「另一側需要配合什麼」）。

用法：
    python3 ops/exhibit/twin/probe_proxy_stall.py [--out 檔案.json] [--budget 秒] [--reps N]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import subprocess
import sys
import time

#: 子行程裡跑的那一段。**必須在新行程**——`getproxies()` 的成本在行程內只付一次，
#: 同一個行程量第二次一定是 0，量出來會自欺。
SNIPPET = (
    "import time,urllib.request;"
    "t=time.time();p=urllib.request.getproxies();"
    "print(round(time.time()-t,3),len(p))"
)


#: 超過這個秒數就算「量到停頓」。0.75～1.5 秒是本機安靜時的常態，
#: 而撞上的時候是幾十到兩百秒——中間空得很開，門檻放哪裡都一樣。
STALL_S = 5.0


def _once(env_extra: dict[str, str], budget: float) -> dict:
    """跑一次。回 `{"seconds": float|None, "timed_out": bool, ...}`。

    ⚠ 逾時的那一格 `seconds` 寫 **`null`**：我們只知道「≥ budget」，
      不知道實際多久。寫一個數字進去就是編的。
    """
    env = {**os.environ, **env_extra}
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, "-c", SNIPPET],
                           capture_output=True, text=True, timeout=budget, env=env)
    except subprocess.TimeoutExpired:
        return {"seconds": None, "timed_out": True, "at_least_s": budget,
                "n_proxies": None, "rc": None}
    wall = time.time() - t0
    secs, n = (None, None)
    if r.returncode == 0 and r.stdout.strip():
        parts = r.stdout.split()
        secs, n = float(parts[0]), int(parts[1])
    return {"seconds": secs, "timed_out": False, "wall_s": round(wall, 3),
            "n_proxies": n, "rc": r.returncode,
            "stderr": r.stderr[-300:] or None}


def _arm(env_extra: dict[str, str], budget: float, reps: int) -> dict:
    """同一個設定跑 `reps` 次，看**最大值**。

    ⚠ **不可以只跑一次。** 這個停頓是間歇的（見檔頭那張表），單次取樣
      跑出 1.48 秒就結論「沒問題」正是要防的那個錯。
    """
    runs = [_once(env_extra, budget) for _ in range(reps)]
    got = [r["seconds"] for r in runs if r["seconds"] is not None]
    timed_out = any(r["timed_out"] for r in runs)
    return {
        "reps": reps, "runs": runs,
        # 逾時過 ⇒ 最大值我們只知道「≥ budget」，寫 null 不寫 budget
        "max_s": None if timed_out else (max(got) if got else None),
        "min_s": min(got) if got else None,
        "any_timed_out": timed_out,
        # 「這一輪有沒有撞上停頓」——量不到只代表沒撞上，不代表不存在
        "stall_observed": bool(timed_out or (got and max(got) > STALL_S)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="量 getproxies() 的停頓（含負控制）")
    ap.add_argument("--out")
    ap.add_argument("--budget", type=float, default=150.0,
                    help="單次上限秒數（逾時就記 null，不編數字）")
    ap.add_argument("--reps", type=int, default=6,
                    help="每一組跑幾次（間歇現象，單次會說謊）")
    a = ap.parse_args()

    out = {
        "probe": "getproxies_stall",
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "budget_s": a.budget,
        "stall_threshold_s": STALL_S,
        # 正控制：什麼都不設 ⇒ 走 OS 那一條，這是測試原本在付的錢
        "baseline_no_env": _arm({}, a.budget, a.reps),
        # 治法：env 有東西 ⇒ CPython 整段跳過 OS 查詢
        "with_no_proxy_star": _arm({"no_proxy": "*"}, a.budget, a.reps),
        # 負控制：換一個**沒有**以 `_proxy` 結尾的變數，必須**量不到改善**
        #         （證明改善來自 `no_proxy` 這個名字，不是「多設了一個變數」）
        "negctl_irrelevant_env": _arm({"no_proxy_but_not": "*"}, a.budget, a.reps),
        "honesty": ("Mac 的數字。展場是 1003（Windows，getproxies_registry），"
                    "那台沒量過 ⇒ windows_measured=null。"
                    "停頓是間歇的：stall_observed=false 只代表這一輪沒撞上。"),
        "windows_measured": None,
        "previously_observed_stalls_s": [206.33, 89.67, 49.22, 16.08],
    }
    b, g, nc = (out["baseline_no_env"], out["with_no_proxy_star"],
                out["negctl_irrelevant_env"])
    out["verdict"] = {
        "baseline_stalled_this_round": b["stall_observed"],
        # ⚠ 用 `is None` 不用 `or`：`seconds` 合法值包含 **0.0**，
        #    而 `0.0 or 9e9` 會變成 9e9——第一版就是這樣把綠燈判成紅的。
        "fix_is_fast": (not g["any_timed_out"] and g["max_s"] is not None
                        and g["max_s"] < 1.0),
        "negctl_no_improvement": nc["max_s"] is None or nc["max_s"] >= (g["max_s"] or 0.0),
        # 這一輪的結論只有在**有撞上**的時候才成立；沒撞上 ⇒ 不下結論
        "conclusive_this_round": b["stall_observed"],
    }
    txt = json.dumps(out, ensure_ascii=False, indent=2)
    print(txt)
    if a.out:
        p = pathlib.Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
