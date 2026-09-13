#!/usr/bin/env python3
"""round675：`pooled_paired_ci.py --key` 的植入缺陷測試（判準 `CRITERION_20260903_R675_POOLED_DELIV.md` §三）。

零模型呼叫、零沙箱、唯讀 `runs/g_r444_conform_mbpp`。fixture 全建在 --work（預設 /dev/shm/r675）。
**不碰 runs/g_r445_conform_mbpp_ext**（它活著）。

接一個新旗標不算接好，除非它壞掉時會被抓到。含「安靜量不到」兩型：
  P4 欄位消失（缺 accepted ⇒ 被讀成拒交＝方向性偏誤）
  P5 整層量不到（n=0 的層被另一層蓋過去 ⇒ 偽裝成樣本數夠）
"""
from __future__ import annotations
import argparse, json, os, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOL = HERE / "pooled_paired_ci.py"
SRC = ROOT / "runs" / "g_r444_conform_mbpp"


def run(args, mutant=""):
    env = dict(os.environ)
    if mutant:
        env["POOLED_CI_MUTANT"] = mutant
    else:
        env.pop("POOLED_CI_MUTANT", None)
    r = subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True,
                       env=env, cwd=str(ROOT))
    try:
        return r.returncode, json.loads(r.stdout)
    except Exception:
        return r.returncode, {"_stdout": r.stdout, "_stderr": r.stderr}


def dump(d: pathlib.Path, rows, summary_bytes):
    d.mkdir(parents=True, exist_ok=True)
    (d / "rows.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                  encoding="utf-8")
    (d / "summary.json").write_bytes(summary_bytes)


def json_paths(o, pre=""):
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            out.update(json_paths(v, f"{pre}.{k}"))
        return out
    if isinstance(o, list):
        out = {}
        for i, v in enumerate(o):
            out.update(json_paths(v, f"{pre}[{i}]"))
        return out or {pre: "[]"}
    return {pre: o}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="/dev/shm/r675")
    ap.add_argument("--before", help="改動前版本輸出的 JSON（P1 用）")
    a = ap.parse_args()
    W = pathlib.Path(a.work)
    rows = [json.loads(l) for l in (SRC / "rows.jsonl").open(encoding="utf-8") if l.strip()]
    summ = (SRC / "summary.json").read_bytes()
    tids = sorted({r["task_id"] for r in rows})
    cut = len(tids) // 2
    A, B = set(tids[:cut]), set(tids[cut:])
    dump(W / "whole", rows, summ)
    dump(W / "half_a", [r for r in rows if r["task_id"] in A], summ)
    dump(W / "half_b", [r for r in rows if r["task_id"] in B], summ)
    dump(W / "empty", [], summ)

    # deliv != meets_demand 的 fixture：把 CONFORM 臂前 6 題改成「符合需求但被拒交」
    dd, n_flip = [], 0
    for r in json.loads(json.dumps(rows)):
        if r["arm"] == "CONFORM" and r.get("meets_demand") and r.get("accepted") and n_flip < 6:
            r["accepted"] = False; n_flip += 1
        dd.append(r)
    dump(W / "delivdiff", dd, summ)
    # 缺 accepted 欄位的 fixture（欄位整個不見，不是設成 False）
    dump(W / "noacc", [{k: v for k, v in r.items() if k != "accepted"} for r in rows], summ)

    ARMS = ["--a-arm", "CONFORM", "--b-arm", "OFF5"]
    HALVES = ["--stratum", f"A={W/'half_a'}", "--stratum", f"B={W/'half_b'}"]
    results = []

    def rec(name, ok, detail):
        results.append((name, ok, detail))

    # ---- P1：預設 key 的輸出，只准差「新增的 key 欄位」與那一個改名 ----
    rc, now = run([*ARMS, *HALVES])
    if a.before:
        before = json.loads(pathlib.Path(a.before).read_text(encoding="utf-8"))
        pb, pn = json_paths(before), json_paths(now)
        added = sorted(set(pn) - set(pb))
        removed = sorted(set(pb) - set(pn))
        changed = sorted(k for k in set(pb) & set(pn) if pb[k] != pn[k])
        # 改名在 diff 上會同時出現在「新增」與「消失」兩側；判準授權的就是這兩處。
        # 牙齒在 `changed == []`：**任何一個值變了都會露出來**，這條不准放寬。
        OLD, NEW = "third_category_missing_meets_demand", "third_category_missing_fields"
        # §六 addendum（本輪中途加的，已在判準補記並標明是偏離事前清單）：
        # 每層多一個 instrument_two_way 區塊。牙齒仍在 changed == []。
        ok_added = all(k.endswith(".key") or k.endswith("." + NEW)
                       or ".instrument_two_way." in k for k in added)
        ok_ren = bool(removed) and all(k.endswith("." + OLD) for k in removed)
        rec("P1 預設 key 逐位元不變（只差 key 欄位＋一個改名）",
            ok_added and ok_ren and not changed,
            f"新增={added} 消失={removed} 值變了={changed}")
    else:
        rec("P1 預設 key 逐位元不變", False, "沒給 --before，無法比對")

    # ---- P2：合併是加法恆等式（真資料）----
    rc_w, whole = run([*ARMS, "--stratum", f"W={W/'whole'}", "--stratum", f"Z={W/'empty'}"])
    keys = ("B", "C", "N", "n_discordant", "delta_pp", "ci95_lo_pp", "ci95_hi_pp")
    same = all(whole["pooled"][k] == now["pooled"][k] for k in keys)
    rec("P2 兩半併起來 == 單層跑全部（逐位元）", same,
        f"halves={ {k: now['pooled'][k] for k in keys} } whole={ {k: whole['pooled'][k] for k in keys} }")

    # ---- P3：--key 有牙齒（deliv != meets_demand 的資料上必須給出不同 b/c）----
    DD = ["--stratum", f"A={W/'delivdiff'}", "--stratum", f"B={W/'empty'}"]
    _, md = run([*ARMS, *DD, "--key", "meets_demand"])
    _, dv = run([*ARMS, *DD, "--key", "deliv"])
    diff = (md["pooled"]["B"], md["pooled"]["C"]) != (dv["pooled"]["B"], dv["pooled"]["C"])
    rec("P3 --key 有牙齒（造 6 格「符合需求但被拒交」）", diff,
        f"meets_demand b/c={md['pooled']['B']}/{md['pooled']['C']} "
        f"deliv b/c={dv['pooled']['B']}/{dv['pooled']['C']}")
    # M6：--key 被安靜忽略 ⇒ 上面那條必須翻成 False
    _, m6 = run([*ARMS, *DD, "--key", "deliv"], mutant="M6")
    m6_caught = (m6["pooled"]["B"], m6["pooled"]["C"]) == (md["pooled"]["B"], md["pooled"]["C"])
    rec("P3/M6 突變（--key 是裝飾品）被偵測器抓到", m6_caught,
        f"M6 deliv b/c={m6['pooled']['B']}/{m6['pooled']['C']}（== meets_demand ⇒ 該叫）")

    # ---- P4（安靜量不到・型一）：缺 accepted 欄位 ----
    NA = ["--stratum", f"A={W/'noacc'}", "--stratum", f"B={W/'empty'}"]
    rc4, r4 = run([*ARMS, *NA, "--key", "deliv"])
    hit = any("缺" in x and "accepted" in x for x in r4["broken_reasons"])
    rec("P4 缺 accepted 欄位 ⇒ BROKEN（不准當 False）", rc4 == 1 and hit,
        f"rc={rc4} broken={r4['broken_reasons']}")
    rc4m, r4m = run([*ARMS, *NA, "--key", "deliv"], mutant="M7")
    m7_caught = not any("accepted" in x for x in r4m["broken_reasons"])
    rec("P4/M7 突變（缺欄位靜靜當 False）被偵測器抓到", m7_caught,
        f"M7 rc={rc4m} broken={r4m['broken_reasons']}（缺欄位訊息消失 ⇒ 該叫）")

    # ---- P5（安靜量不到・型二）：n=0 的層 ----
    rc5, r5 = run([*ARMS, "--stratum", f"W={W/'whole'}", "--stratum", f"Z={W/'empty'}"])
    hit5 = any("n=0" in x for x in r5["broken_reasons"])
    rec("P5 n=0 的層 ⇒ BROKEN（不准被另一層蓋過去）", rc5 == 1 and hit5,
        f"rc={rc5} broken={r5['broken_reasons']}")
    rc5m, r5m = run([*ARMS, "--stratum", f"W={W/'whole'}", "--stratum", f"Z={W/'empty'}"], mutant="M8")
    m8_caught = not any("n=0" in x for x in r5m["broken_reasons"])
    rec("P5/M8 突變（空層放行）被偵測器抓到", m8_caught,
        f"M8 rc={rc5m} broken={r5m['broken_reasons']}")

    # ---- P6：真資料上 deliv == meets_demand（round670 §六 的構造，事前聲明的預期）----
    _, rmd = run([*ARMS, *HALVES, "--key", "meets_demand"])
    _, rdv = run([*ARMS, *HALVES, "--key", "deliv"])
    p6 = all(rmd["pooled"][k] == rdv["pooled"][k] for k in keys)
    rec("P6 r444 真資料上 deliv == meets_demand（預期，非發現）", p6,
        f"md={ {k: rmd['pooled'][k] for k in keys} } deliv={ {k: rdv['pooled'][k] for k in keys} }")

    # ---- P7（§六 addendum）：量具沒雙向滿分的層不准併進來 ----
    bad = json.loads((SRC / "summary.json").read_text(encoding="utf-8"))
    bad["instrument"]["ref_pass"] = bad["instrument"]["n"] - 1      # 一題參考解沒過
    dump(W / "badinst", rows, json.dumps(bad, ensure_ascii=False).encode("utf-8"))
    BI = ["--stratum", f"A={W/'badinst'}", "--stratum", f"B={W/'half_b'}"]
    rc7, r7 = run([*ARMS, *BI, "--key", "deliv"])
    hit7 = any("雙向滿分" in x for x in r7["broken_reasons"])
    rec("P7 量具沒雙向滿分的層 ⇒ BROKEN", rc7 == 1 and hit7, f"rc={rc7} broken={r7['broken_reasons']}")
    rc7m, r7m = run([*ARMS, *BI, "--key", "deliv"], mutant="M9")
    rec("P7/M9 突變（量具不滿分照樣放行）被偵測器抓到",
        not any("雙向滿分" in x for x in r7m["broken_reasons"]),
        f"M9 rc={rc7m} broken={r7m['broken_reasons']}")

    # ---- P8（§六 addendum・安靜量不到）：summary 沒有 instrument 區塊 ----
    noinst = json.loads((SRC / "summary.json").read_text(encoding="utf-8"))
    noinst.pop("instrument", None)
    dump(W / "noinst", rows, json.dumps(noinst, ensure_ascii=False).encode("utf-8"))
    rc8, r8 = run([*ARMS, "--stratum", f"A={W/'noinst'}", "--stratum", f"B={W/'half_b'}", "--key", "deliv"])
    rec("P8 summary 沒有 instrument 區塊 ⇒ BROKEN（不准當通過）",
        rc8 == 1 and any("沒有 instrument" in x for x in r8["broken_reasons"]),
        f"rc={rc8} broken={r8['broken_reasons']}")

    # ---- P9（§六）：真資料上 r444/r445 兩層都雙向滿分（conditions_sha 不等是題目清單不同，不是問題）----
    _, r9 = run([*ARMS, "--stratum", f"A={W/'half_a'}", "--stratum", f"B={W/'half_b'}", "--key", "deliv"])
    rec("P9 r444 真資料量具雙向滿分",
        all(s2["instrument_two_way"]["ok"] for s2 in r9["strata"]),
        str([(s2["label"], s2["instrument_two_way"]) for s2 in r9["strata"]]))

    # ---- 既有 selftest 不准回歸 ----
    r = subprocess.run([sys.executable, str(TOOL), "--selftest"], capture_output=True, text=True, cwd=str(ROOT))
    rec("既有 selftest（round658/660 的 P1–P7b）仍 PASS", r.returncode == 0, r.stdout.strip())

    bad = 0
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}\n      {detail}")
        bad += 0 if ok else 1
    print(f"\n{len(results) - bad}/{len(results)} PASS")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
