#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""這支在架構裡承重什麼：**零模型呼叫**的事後計分＋收官表。可離線重跑。

⚠⚠ **非預註冊。** 這支印的每一個數字都是**描述性**的：
「在這 20 題上，X 是 a/b」。**不准**做統計檢定、**不准**與 R535／R530 原始結果
合併、**不准**寫「複製」「效果消失」「等價」。判讀紀律全文見 `README.md`。

它做三件事
----------
1. **隱藏驗收計分**（`ops/gain/r530/hidden/<task_id>/test_hidden.py`）。
   跑在**最後一次嘗試的凍結快照**上——那是閘門判決時看到的那一份逐位元組，
   不是事後還可能被動過的 live 工作區。**隱藏驗收只計分不回饋**：它在整個
   發射過程中一個位元組都沒有進過工作區，也沒有進過 `--suite`。
2. **40 格的表**：`accepted`／`stop_reason`／`attempts_used`／`requests_seen`／
   `M7_*`／`upstreams_defaulted`／`agent_timed_out`／牆鐘。
3. **M7 三層**（`M7_file` → `M7_ws` → `M7_ws_solution`）與**牆鐘分佈**
   （min／p25／median／p75／p90／max，**刻意不印均值**——均值會把一個 900 秒的
   逾時格與二十個 40 秒的格子攪成一個沒有人見過的數字）。

兩個隱藏分數都落盤，**都不是主指標**
------------------------------------
`hidden_frac`＝最終工作區有多好（不管有沒有出貨）；
`hidden_frac_delivered`＝拒交 ⇒ 0.0。`TASK_FORMAT.md` §九-1 要求 analyzer
**在看到資料之前**指名一個——本輪沒有預註冊，所以**這支不指名**，
兩個都印、都標成描述性。想指名就要先寫預註冊，那是另一件事。

誠實邊界
--------
`passed/total` 是「過了我們自己寫的幾條」，不是「做對了幾成」
（`vacant/suitegauge.py` 的單邊保證逐字適用）。

用法
----
    python3 ops/gain/r530vrun/score_r530vrun.py --out /var/tmp/vacant_r530vrun
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from vacant.vrun import acceptance                        # noqa: E402
from vacant.vrun.sandbox import make_sandbox              # noqa: E402

R530 = REPO / "ops" / "gain" / "r530"
HIDDEN = R530 / "hidden"

ARM_ORDER = ("RF", "RP")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_cells(out: pathlib.Path) -> list[dict]:
    cells = []
    d = out / "cells"
    if not d.is_dir():
        raise SystemExit(f"沒有 {d}。停。")
    for p in sorted(d.iterdir()):
        f = p / "cell.json"
        if f.is_file():
            cells.append(json.loads(f.read_text(encoding="utf-8")))
    return cells


def graded_dir(out: pathlib.Path, cell: dict) -> tuple[pathlib.Path | None, str]:
    """閘門判決時看到的那一份工作區。

    優先用**最後一次嘗試的凍結快照**（`frozen_path`）；沒有就退到 live `ws`，
    並把退了這一步記下來——「用哪一份計分」不可以是看不見的決定。
    """
    atts = cell.get("attempts") or []
    if atts:
        fp = atts[-1].get("frozen_path")
        if fp and pathlib.Path(fp).is_dir():
            return pathlib.Path(fp), "frozen_last_attempt"
    ws = out / "cells" / cell["cell"] / "ws"
    if ws.is_dir():
        return ws, "live_ws_fallback"
    return None, "missing"


def score_hidden(out: pathlib.Path, cell: dict, *, timeout_s: float,
                 sandbox_name: str, scratch: pathlib.Path) -> dict:
    task_id = cell["task_id"]
    src, how = graded_dir(out, cell)
    if src is None:
        return {"hidden_scored": False, "hidden_reason": "no_workspace",
                "hidden_source": how}
    work = pathlib.Path(tempfile.mkdtemp(prefix=f"h_{cell['cell']}_",
                                         dir=str(scratch)))
    sb, meta = make_sandbox(sandbox_name, workdir=str(work / "sb"))
    res = acceptance.run_suite(sb, src, HIDDEN / task_id, suite="hidden",
                               task_id=task_id, verify_root=work / "verify",
                               timeout_s=timeout_s)
    files = [{"file": f["file"], "wall_ms": f["wall_ms"],
              "timed_out": f["timed_out"], "passed": f["passed"],
              "total": f["total"]} for f in res.get("files", [])]
    import shutil
    shutil.rmtree(work, ignore_errors=True)
    total = res.get("total") or 0
    passed = res.get("passed") or 0
    accepted = cell.get("accepted")
    frac = (passed / total) if total else None
    return {
        "hidden_scored": True, "hidden_source": how,
        "hidden_backend": meta.get("backend"),
        "hidden_passed": passed, "hidden_total": total,
        "hidden_all_pass": res.get("all_pass"),
        "hidden_timed_out": any(f["timed_out"] for f in files),
        "hidden_files": files,
        "hidden_result_sha256": res.get("result_sha256"),
        # 兩個都是**描述性**的，都不是主指標（docstring）。
        "hidden_frac": frac,
        "hidden_frac_delivered": (frac if accepted else
                                  (0.0 if accepted is False else None)),
    }


def dist(vals: list[float]) -> dict | None:
    """**印分佈不印均值**（人類指令）。"""
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    def q(p: float) -> float:
        if len(v) == 1:
            return v[0]
        i = p * (len(v) - 1)
        lo, hi = int(i), min(int(i) + 1, len(v) - 1)
        return v[lo] + (v[hi] - v[lo]) * (i - lo)
    return {"n": len(v), "min": round(v[0], 1), "p25": round(q(0.25), 1),
            "median": round(statistics.median(v), 1), "p75": round(q(0.75), 1),
            "p90": round(q(0.90), 1), "max": round(v[-1], 1)}


def frac_str(num: int, den: int) -> str:
    return f"{num}/{den}" + (f" ({num / den:.0%})" if den else "")


def m7_layer(cells: list[dict], key: str) -> dict:
    """一層 M7 的三分：`true` ／ `false` ／ `null`（**null 不併進 false**）。"""
    t = sum(1 for c in cells if c.get(key) is True)
    f = sum(1 for c in cells if c.get(key) is False)
    n = sum(1 for c in cells if c.get(key) is None)
    reasons: dict[str, int] = {}
    rk = key + "_reason"
    for c in cells:
        if c.get(key) is None:
            r = c.get(rk) or "(no reason recorded)"
            reasons[r] = reasons.get(r, 0) + 1
    return {"true": t, "false": f, "null": n, "null_reasons": reasons}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="r530vrun 計分（零模型呼叫）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--test-timeout", type=float, default=None,
                    help="隱藏驗收的每檔逾時；預設沿用 manifest 裡發射時用的那個值")
    ap.add_argument("--sandbox", default="auto")
    ap.add_argument("--no-hidden", action="store_true",
                    help="只印表，不跑隱藏驗收")
    args = ap.parse_args(argv)

    out = pathlib.Path(args.out).resolve()
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    timeout_s = args.test_timeout or manifest.get("test_timeout_s") or 30.0
    cells = load_cells(out)
    scratch = out / "_score_scratch"
    scratch.mkdir(exist_ok=True)

    if not args.no_hidden:
        print(f"# 隱藏驗收計分（timeout={timeout_s}s，**只計分不回饋**）",
              flush=True)
        for c in cells:
            if c.get("cell_status") == "infra_void":
                c.update({"hidden_scored": False,
                          "hidden_reason": "infra_void"})
                continue
            c.update(score_hidden(out, c, timeout_s=timeout_s,
                                  sandbox_name=args.sandbox, scratch=scratch))
            print(f"  {c['cell']:<28} hidden "
                  f"{c.get('hidden_passed')}/{c.get('hidden_total')}  "
                  f"({c.get('hidden_source')})", flush=True)
        import shutil
        shutil.rmtree(scratch, ignore_errors=True)

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    (out / f"scores_{stamp}.json").write_text(
        json.dumps({"generated": now_iso(), "not_preregistered": True,
                    "reading_discipline": manifest.get("reading_discipline"),
                    "test_timeout_s": timeout_s, "cells": cells},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 收官表 ────────────────────────────────────────────────────────────
    lines: list[str] = []
    add = lines.append
    add("⚠ 非預註冊：下面每一個數字都是描述性的。不准做統計檢定、"
        "不准與 R535／R530 原始結果合併、不准寫「複製」「效果消失」「等價」。")
    add("")
    add(f"# r530vrun 收官表　{now_iso()}　"
        f"cells={len(cells)}　test_timeout={timeout_s}s")
    add("")
    add("| cell | arm | 層 | accepted | stop_reason | att | req | "
        "vis | hidden | M7_file | M7_ws | M7_ws_sol | to | wall_s |")
    add("|---|---|---|---|---|---:|---:|---|---|---|---|---|---:|---:|")
    for c in sorted(cells, key=lambda x: (x["task_id"], x["arm"])):
        vis = (f"{c.get('visible_passed')}/{c.get('visible_total')}"
               if c.get("visible_total") is not None else "—")
        hid = (f"{c.get('hidden_passed')}/{c.get('hidden_total')}"
               if c.get("hidden_scored") else "—")
        add(f"| `{c['task_id']}` | {c['arm']} | {c.get('stratum')} | "
            f"{c.get('accepted')} | {c.get('stop_reason')} | "
            f"{c.get('attempts_used')} | {c.get('requests_seen')} | {vis} | "
            f"{hid} | {c.get('m7_file')} | {c.get('m7_ws')} | "
            f"{c.get('m7_ws_solution')} | {c.get('agent_timed_out_n')} | "
            f"{c.get('wall_s')} |")
    add("")

    measured = [c for c in cells if c.get("cell_status") == "measured"]
    void = [c for c in cells if c.get("cell_status") == "infra_void"]
    add(f"## 逐臂（measured {len(measured)} 格、infra_void {len(void)} 格）")
    add("")
    add("| 臂 | n | accepted | 單發過（att1） | stop_reason 分佈 | "
        "hidden 全過 | 逾時嘗試 |")
    add("|---|---:|---|---|---|---|---|")
    for arm in ARM_ORDER:
        sub = [c for c in measured if c["arm"] == arm]
        if not sub:
            continue
        acc = sum(1 for c in sub if c.get("accepted"))
        a1 = sum(1 for c in sub
                 if (c.get("attempts") or [{}])[0].get("accepted"))
        sr: dict[str, int] = {}
        for c in sub:
            sr[c.get("stop_reason") or "?"] = sr.get(
                c.get("stop_reason") or "?", 0) + 1
        hp = sum(1 for c in sub if c.get("hidden_all_pass"))
        hn = sum(1 for c in sub if c.get("hidden_scored"))
        to = sum(int(c.get("agent_timed_out_n") or 0) for c in sub)
        att = sum(int(c.get("attempts_used") or 0) for c in sub)
        add(f"| {arm} | {len(sub)} | {frac_str(acc, len(sub))} | "
            f"{frac_str(a1, len(sub))} | "
            + ", ".join(f"`{k}`×{v}" for k, v in sorted(sr.items()))
            + f" | {frac_str(hp, hn)} | {to}/{att} |")
    add("")

    add("## M7 三層（**`null` 不併進 `false`**：沒量到 ≠ 量到 0）")
    add("")
    add("| 層 | 臂 | true | false | null | null 的理由 |")
    add("|---|---|---:|---:|---:|---|")
    for key, label in (("m7_file", "M7_file（回饋文字進 wire）"),
                       ("m7_name", "M7_name（回饋檔名進 wire）"),
                       ("m7_ws", "M7_ws（讀了工作區）"),
                       ("m7_ws_solution", "M7_ws_solution（讀了自己上一份錯碼）")):
        for arm in ARM_ORDER:
            sub = [c for c in measured if c["arm"] == arm]
            if not sub:
                continue
            L = m7_layer(sub, key)
            add(f"| {label} | {arm} | {L['true']} | {L['false']} | "
                f"{L['null']} | "
                + ("；".join(f"`{k}`×{v}"
                             for k, v in sorted(L["null_reasons"].items()))
                   or "—") + " |")
    add("")

    add("## 牆鐘分佈（**不印均值**）")
    add("")
    add("| 量 | 臂 | n | min | p25 | median | p75 | p90 | max |")
    add("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for label, pick in (
            ("整格牆鐘 wall_s", lambda c: c.get("wall_s")),
            ("agent 牆鐘 agent_wall_s", lambda c: c.get("agent_wall_s"))):
        for arm in ARM_ORDER:
            sub = [c for c in measured if c["arm"] == arm]
            d = dist([pick(c) for c in sub])
            if not d:
                continue
            add(f"| {label} | {arm} | {d['n']} | {d['min']} | {d['p25']} | "
                f"{d['median']} | {d['p75']} | {d['p90']} | {d['max']} |")
    add("")
    per_att = [a.get("agent_wall_s") for c in measured
               for a in (c.get("attempts") or [])]
    d = dist([x for x in per_att if x is not None])
    if d:
        add(f"逐次嘗試的 agent 牆鐘（n={d['n']}）："
            f"min {d['min']} / p25 {d['p25']} / median {d['median']} / "
            f"p75 {d['p75']} / p90 {d['p90']} / max {d['max']} 秒。")
    add("")

    add("## 紀律欄位")
    add("")
    nm = [c["cell"] for c in cells if c.get("not_mediated")]
    add(f"* `requests_seen == 0`（infra_void 不是 0 分）："
        f"{len(nm)} 格{'：' + ', '.join(nm) if nm else ''}")
    ud = sorted({u for c in cells for u in (c.get("upstreams_defaulted") or [])})
    add(f"* `upstreams_defaulted`（沒指定而走預設上游的 wire）："
        f"{ud or '（無）'}")
    ws_moved = [c["cell"] for c in cells
                if c.get("ws_suite_sha256")
                and c.get("suite_sha256")
                and c["ws_suite_sha256"] != c["suite_sha256"]]
    add(f"* 工作區裡那一份可見驗收被動過的格子：{len(ws_moved)} 格"
        f"{'：' + ', '.join(ws_moved) if ws_moved else ''}"
        "（計分用的是工作區外那一份，所以動了也騙不到閘門——這是觀測不是錯誤）")
    f3 = {}
    for c in measured:
        k = c.get("f3_verdict") or "?"
        f3[k] = f3.get(k, 0) + 1
    add(f"* F3（送出去的推論模式）：" + ", ".join(f"`{k}`×{v}"
                                             for k, v in sorted(f3.items())))
    st = [c["cell"] for c in measured if c.get("suspect_timeout")]
    add(f"* `suspect_timeout`：{len(st)} 格{'：' + ', '.join(st) if st else ''}")
    add("")
    add("## 誠實邊界")
    add("")
    add("* `passed/total` 是「過了我們自己寫的幾條」，不是「做對了幾成」"
        "（`vacant/suitegauge.py` 的單邊保證）。")
    add("* `hidden_frac` 與 `hidden_frac_delivered` **都不是主指標**——"
        "本輪沒有預註冊，這支不指名。")

    text = "\n".join(lines) + "\n"
    (out / f"report_{stamp}.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {out / f'report_{stamp}.md'}")
    print(f"wrote {out / f'scores_{stamp}.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
