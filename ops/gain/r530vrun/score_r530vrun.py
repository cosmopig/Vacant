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


def load_cells(out: pathlib.Path) -> tuple[list[dict], list[str]]:
    """回 `(跑完的格子, 還在跑的格子名)`。

    ⚠ `cell.json` 是**邊跑邊寫**的，所以「檔案存在」不等於「這一格跑完了」。
    只收 `run_complete: true`；在跑的那些**另外列名**，不混進任何表。
    把它們混進去會讓分母說謊——而分母說謊比沒有分母更糟。
    """
    cells: list[dict] = []
    inflight: list[str] = []
    d = out / "cells"
    if not d.is_dir():
        raise SystemExit(f"沒有 {d}。停。")
    for p in sorted(d.iterdir()):
        f = p / "cell.json"
        if not f.is_file():
            inflight.append(p.name)
            continue
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except Exception:                                  # noqa: BLE001
            inflight.append(p.name)
            continue
        if rec.get("run_complete"):
            cells.append(rec)
        else:
            inflight.append(p.name)
    return cells, inflight


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


def visible_timing(out: pathlib.Path, cell: dict) -> dict:
    """從 launcher 逐次落盤的 `visible_RUN-ON*.json` 把**驗收自己的時間**讀回來。

    這是「`--test-timeout` 有沒有製造假逾時」的**直接證據**，而且它是離線的：
    跑完之後才算，所以發射時不必先想到要量。
    `kind == "timeout"` ＝ 那一檔沒在期限內跑完；`max_wall_ms` ＝ 實際用掉多少。
    """
    rd = out / "cells" / cell["cell"] / "run"
    files = sorted(rd.glob("visible_RUN-ON*.json")) if rd.is_dir() else []
    walls: list[float] = []
    n_timeout = 0
    per: list[dict] = []
    for p in files:
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                  # noqa: BLE001
            continue
        for f in r.get("files", []):
            walls.append((f.get("wall_ms") or 0) / 1000.0)
            if f.get("timed_out"):
                n_timeout += 1
            per.append({"json": p.name, "file": f.get("file"),
                        "wall_s": round((f.get("wall_ms") or 0) / 1000.0, 3),
                        "timed_out": bool(f.get("timed_out")),
                        "kinds": sorted({c.get("kind")
                                         for c in f.get("cases", [])})})
    return {"visible_suite_runs": len(per),
            "visible_suite_timeouts": n_timeout,
            "visible_suite_max_wall_s": round(max(walls), 3) if walls else None,
            "visible_suite_walls_s": [round(w, 3) for w in walls],
            "visible_suite_detail": per}


#: 工作區樣板一定有的四個檔（`ops/gain/r530/templates/<task>/`）。
TEMPLATE_FILES = frozenset({"goal.md", "contract.md", "run_tests.sh",
                            "tests_visible/test_visible.py"})


def ws_added(out: pathlib.Path, cell: dict) -> dict:
    """**worker 在工作區裡多放了什麼**——只有這個題庫問得出來的觀測。

    R530 的樣板附了 `tests_visible/` 與 `run_tests.sh`（`TASK_FORMAT.md` §八-5：
    worker 看得到、跑得到）。所以可以問一件 R535 問不出來的事：
    **他用我們給他的檢查，還是自己另外造一套？**

    `tests_visible/__pycache__` 存在 ⇒ 那組檢查被 import 過（跑過）。
    工作區裡多出 `test_*.py`／`*_test.py` ⇒ 他自己寫了一套。
    兩件事**可以同時發生**，也可以都不發生。**這是觀測不是判準。**
    """
    src, how = graded_dir(out, cell)
    if src is None:
        return {"ws_added_files": None, "ws_ran_shipped_checks": None,
                "ws_wrote_own_tests": None}
    names = sorted(str(p.relative_to(src)) for p in src.rglob("*")
                   if p.is_file()
                   and "__pycache__" not in p.relative_to(src).parts)
    added = [n for n in names if n not in TEMPLATE_FILES]
    return {
        "ws_added_files": added,
        "ws_snapshot": how,
        "ws_ran_shipped_checks": (src / "tests_visible" / "__pycache__").is_dir(),
        "ws_wrote_own_tests": [
            n for n in added
            if pathlib.PurePath(n).name.startswith("test_")
            or pathlib.PurePath(n).name.endswith(("_test.py", "_tests.py"))],
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
    cells, inflight = load_cells(out)
    planned = sum(1 for _ in (out / "plan.jsonl").read_text(
        encoding="utf-8").splitlines() if _.strip())
    scratch = out / "_score_scratch"
    scratch.mkdir(exist_ok=True)

    # 可見驗收的**時間**是離線讀回來的（launcher 已經逐次落盤），
    # 所以不管跑的時候有沒有想到要量，這一條都補得回來。
    for c in cells:
        c.update(visible_timing(out, c))
        c.update(ws_added(out, c))

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
        f"cells={len(cells)}/{planned}　test_timeout={timeout_s}s")
    add("")
    if inflight:
        add(f"⚠ **這是期中表，不是收官表**：計畫 {planned} 格，跑完 "
            f"{len(cells)} 格，**{len(inflight)} 格還在跑**"
            f"（{', '.join(sorted(inflight))}）。下面所有比例的分母都是**跑完的**"
            "那些，不是 40。發射順序是 `ow_01` → `ow_20`，而 `ow_18`–`ow_20` 是 "
            "`loose` 層 ⇒ **期中的子集偏向難的那一端**，不可以當成全題庫的樣子。")
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
    add("⚠⚠ **這一整張表是 `pi` 的性質，不是「agent 的性質」。**"
        "2026-09-19 Stage C 收官 40/40 量到：R535 的頭條數字"
        "（「只有 ~2% 讀回饋檔」）**不跨基質**——同一個量具下 OpenCode 與 "
        "Claude Code 都是 **50%**，pi 才是 ~2% 的那一個。本輪用的是 pi，"
        "所以下面的 `M7_file` 只能寫成「**在這 20 題上、用 pi**，M7_file 是 a/b」。"
        "**任何跨 agent 的宣稱都要連 agent 一起講**，不可以寫成通性。")
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

    add("## 回饋體積（重量級題庫才問得出來的那一條）")
    add("")
    add("R535 的微型題回饋只有幾百位元組；這個題庫的斷言訊息逐字帶 "
        "`args=… got=… want=…`，回饋可以大很多。`--feedback-into prompt` 把它接在 "
        "**argv** 尾端 ⇒ 夠大就會撞 `ARG_MAX`，那會長成 `agent_spawn_failed`／"
        "`infra_void`，**不是** 0 分。所以體積要印出來。")
    add("")
    add("| 量 | 臂 | n | min | p25 | median | p75 | p90 | max |")
    add("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for arm in ARM_ORDER:
        sub = [c for c in measured if c["arm"] == arm]
        fb = [a.get("feedback_in_prompt_bytes") for c in sub
              for a in (c.get("attempts") or [])
              if a.get("feedback_in_prompt_bytes")]
        d2 = dist(fb)
        if d2:
            add(f"| `feedback_in_prompt_bytes` | {arm} | {d2['n']} | "
                f"{d2['min']} | {d2['p25']} | {d2['median']} | {d2['p75']} | "
                f"{d2['p90']} | {d2['max']} |")
    spawn_fail = [c["cell"] for c in cells
                  if c.get("stop_reason") == "agent_spawn_failed"]
    add("")
    add(f"`agent_spawn_failed`：{len(spawn_fail)} 格"
        f"{'：' + ', '.join(spawn_fail) if spawn_fail else ''}")
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
    ran = [c for c in measured if c.get("ws_ran_shipped_checks")]
    own = [c for c in measured if c.get("ws_wrote_own_tests")]
    add(f"* worker 跑過題庫附給他的那組可見驗收"
        f"（`tests_visible/__pycache__` 存在）：{frac_str(len(ran), len(measured))}")
    add(f"* worker **自己另外寫了一套測試**："
        f"{frac_str(len(own), len(measured))}"
        + ("（例：" + ", ".join(
            f"`{c['cell']}`→{c['ws_wrote_own_tests']}" for c in own[:4]) + "）"
           if own else ""))
    add("  ⇒ 這兩條 **R535 都量不到**——它的工作區裡根本沒有驗收。"
        "兩件事可以同時發生也可以都不發生，**是觀測不是判準**。")
    f3 = {}
    for c in measured:
        k = c.get("f3_verdict") or "?"
        f3[k] = f3.get(k, 0) + 1
    add("* F3（送出去的推論模式）：" + ", ".join(f"`{k}`×{v}"
                                             for k, v in sorted(f3.items())))
    # **F3 的 `unmeasured` 與 agent 逾時是同一件事**（本輪量到的新失效模式）：
    # agent 被砍的那一刻有一通 request 還在飛，它的 usage 永遠不會回來 ⇒
    # 那一通算 `unmeasured`。逐格印出「逾時次數 vs unmeasured 通數」，
    # 相等就代表 F3 的降級**不是推論模式變了**，是 agent 預算咬到了。
    pairs = [(c["cell"], int(c.get("agent_timed_out_n") or 0),
              int(c.get("f3_resp_unmeasured") or 0)) for c in measured]
    eq = sum(1 for _, t, u in pairs if t == u)
    nz = [p for p in pairs if p[1] or p[2]]
    add(f"  * `agent_timed_out_n == f3_resp_unmeasured`："
        f"{frac_str(eq, len(pairs))}"
        f"（兩者都非零的格子 {len(nz)} 個）。**相等 ⇒ F3 降成 `unmeasured` 是"
        "「agent 被砍時有一通還在飛」，不是推論模式變了。** R535 的 driver "
        "把 F3 非 `ok` 當成暫停等人的條件——這個題庫會因此停一個與推論模式"
        "無關的原因。")
    if nz:
        add("  * 明細（cell / 逾時次數 / unmeasured 通數）："
            + "；".join(f"`{n}` {t}/{u}" for n, t, u in nz[:8])
            + ("…" if len(nz) > 8 else ""))
    st = [c["cell"] for c in measured if c.get("suspect_timeout")]
    add(f"* `suspect_timeout`：{len(st)} 格{'：' + ', '.join(st) if st else ''}")
    # **驗收逾時**（`--test-timeout` 有沒有製造假逾時）：本輪最實用的檢查。
    vt = [c["cell"] for c in cells if c.get("visible_suite_timeouts")]
    ht = [c["cell"] for c in cells
          if any(f.get("timed_out") for f in (c.get("hidden_files") or []))]
    vw = dist([c.get("visible_suite_max_wall_s") for c in cells])
    add(f"* **可見驗收逾時**（真跑，`--test-timeout` {timeout_s}s）："
        f"{len(vt)} 格{'：' + ', '.join(vt) if vt else ''}")
    add(f"* **隱藏驗收逾時**（事後計分，同一個值）："
        f"{len(ht)} 格{'：' + ', '.join(ht) if ht else ''}")
    if vw:
        add(f"* 可見驗收**實際用掉**的單檔牆鐘（n={vw['n']} 格的最大值）："
            f"min {vw['min']} / median {vw['median']} / p90 {vw['p90']} / "
            f"max {vw['max']} 秒 ⇒ 相對 {timeout_s}s 的餘裕 "
            f"{(timeout_s / vw['max']):.0f}×" if vw["max"] else "")
    orph = sum(1 for c in measured for a in (c.get("attempts") or [])
               if a.get("orphans_killed"))
    add(f"* `orphans_killed`（框架留孤兒行程的嘗試數）：{orph}")
    ws_moved_freeze = [c["cell"] for c in cells
                       if c.get("stop_reason") == "ws_moved_during_freeze"]
    add(f"* `ws_moved_during_freeze`（凍結期間工作區被動過，TOCTOU）："
        f"{len(ws_moved_freeze)} 格"
        f"{'：' + ', '.join(ws_moved_freeze) if ws_moved_freeze else ''}")
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
