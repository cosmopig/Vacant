#!/usr/bin/env python3
"""R472：`r447_gauge_capability.py` 三道 run 目錄擋門的植入缺陷測試。
判準 `DECISION_20260904_R472_GAUGE_CAPABILITY_RUNDIR_GATES_PREREG.md`（本檔之前 commit）。

⚠ **源碼級突變，不是 env 旗標**：本檔既有的 `_mut()` 只服務 M1–M6，而且 selftest 的
`run()` 會把 `R450_MUTANT` 設完就 pop ⇒ 從外面設環境變數對新條 I/J/K/L 永遠不生效
（那個症狀跟「偵測條沒牙齒」長得一模一樣，r706）。

判準（memory 鐵律）：
  * 只寫 `rc≠0` 不算抓到——突變體害 import 失敗也是 rc≠0。每個突變體要**指名**哪一條該紅。
  * crash 收場記 `BROKEN`，不記 `caught`。
  * 承重牆測試（r695）：把指名的那一條**整段刪掉**再跑同一個突變體 ⇒ 必須退回 MISSED，
    否則那一條是搭順風車，不是它在承重。

用法：python3 ops/gain/mutation_test_r472_gauge_capability.py --worktree ~/vacant/wt_r472 [--json out]
"""
from __future__ import annotations
import argparse, json, pathlib, re, subprocess, sys

REL = "ops/gain/r447_gauge_capability.py"

# --- D3 的期望值：R472 §三 P5 在**修前**的 HEAD 上量到的 14 個鍵（不是本輪產生的基線）---
D3_RUN = "runs/g_r447_conform_lcb2"
D3_EXPECT = {
    "verdict": "OK", "n_tasks_complete": 120, "n_tasks_partial_excluded": 0,
    "n_demonstrated": 94, "n_undemonstrated": 26, "pct_undemonstrated": 21.667,
    "pz1_raw_NOT_ARBITER": 49.167, "pz1_demonstrated_only_NOT_ARBITER": 35.106,
    "window_doubt_triggered": False, "rows_file_lines": 360,
    "deliv_contract_drift": None, "NOT_ARBITER": True,
}

G1_OLD = '    if not ev["run_terminal"]:\n'
G0_OLD = ('    if summary is None:\n'
          '        return "BROKEN_NO_SUMMARY", {"summary_error": summary_err}\n')
G0_NEW = ('    if summary is None:\n'
          '        summary = {}\n')
G2_OLD = ('    if bad:\n'
          '        ev["row_accounting_mismatch"] = bad\n'
          '        return "BROKEN_ROW_ACCOUNTING", ev\n')
G2_NEW = ('    if False:\n'
          '        ev["row_accounting_mismatch"] = bad\n'
          '        return "BROKEN_ROW_ACCOUNTING", ev\n')
WIRE_OLD = '    gate, ev = run_dir_gates(rows, summary, summary_err)\n'
WIRE_NEW = '    gate, ev = None, {}\n'
N1_OLD = 'def run_dir_gates(rows: list[dict], summary: dict | None,\n'
N1_NEW = 'def run_dir_gates(rows: list[dict], summary: dict | None,  this is not python\n'

# (名字, 逐字舊字串, 新字串, 指名該紅的條, 說明)
MUTANTS = [
    ("M7_ignore_terminal", G1_OLD, '    if False:\n', ["I"],
     "G1 拿掉：期中資料被當收官資料"),
    ("M8_missing_summary_ok", G0_OLD, G0_NEW, ["J"],
     "G0 拿掉：讀不到 summary 當成空的往下走（把『讀不到』報成『沒落盤』）"),
    ("M9_ignore_row_accounting", G2_OLD, G2_NEW, ["K"],
     "G2 拿掉：rows 被截斷但 summary 說 terminal ⇒ 分母安靜掉下來"),
    ("M10_unwire_gates", WIRE_OLD, WIRE_NEW, ["I", "J", "K", "L"],
     "接線整條拔掉：三道擋門都在、但 main() 那條路不呼叫它們"),
    # M11：事後追加（不在 §三 P3 的計數裡）。第一次跑是 MISSED——夾具總是把
    # terminal 與 complete 一起設 ⇒ 換讀哪個旗標看不見。條 M 是為了讓它看得見才加的。
    ("M11_terminal_to_complete", G1_OLD, '    if not ev["run_complete"]:\n', ["M"],
     "G1 改讀 run_complete：有 void 的 run 永遠拒絕收官（R516 §8 的坑）"),
    ("N1_syntax", N1_OLD, N1_NEW, [], "負對照：語法壞掉 ⇒ 必須記 BROKEN，不准記 caught"),
]

# 承重牆測試：(突變體, 要刪掉的條)
LOADBEARING = [("M7_ignore_terminal", "I"), ("M8_missing_summary_ok", "J"),
               ("M9_ignore_row_accounting", "K"), ("M11_terminal_to_complete", "M")]

BROKEN_MARKS = ("SyntaxError", "Traceback (most recent call last)",
                "ImportError", "IndentationError")


def run_cmd(cmd, cwd, timeout=600):
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr)


def failed_labels(out: str) -> list[str]:
    """從 selftest 輸出取出紅掉的條的標籤（不靠 SELFTEST_FAIL 那行的逗號切法）。"""
    return [m.group(1).strip() for m in re.finditer(r"^  FAIL  (.+)$", out, re.M)]


def d1(wt):
    rc, out = run_cmd(["python3", REL, "--selftest"], wt)
    return {"rc": rc, "red": rc != 0, "broken": any(m in out for m in BROKEN_MARKS),
            "failed": failed_labels(out)}


def d2(wt):
    rc, out = run_cmd(["python3", "ops/gain/prereg_falsifiability_census.py", "--selftest"], wt)
    return {"rc": rc, "red": rc != 0, "broken": any(m in out for m in BROKEN_MARKS)}


def d3(wt):
    """真資料回歸見證：修前 HEAD 量到的 14 個鍵必須逐值重現。"""
    jp = pathlib.Path("/dev/shm/r472_mut/d3.json")
    jp.parent.mkdir(parents=True, exist_ok=True)
    if jp.exists():
        jp.unlink()
    rc, out = run_cmd(["python3", REL, D3_RUN, "--json", str(jp)], wt)
    broken = any(m in out for m in BROKEN_MARKS)
    if not jp.exists():
        return {"rc": rc, "red": True, "broken": broken, "diff": ["no_output"]}
    got = json.loads(jp.read_text())
    diff = [f"{k}:{got.get(k)!r}!={v!r}" for k, v in D3_EXPECT.items() if got.get(k) != v]
    return {"rc": rc, "red": bool(diff) or rc != 0, "broken": broken, "diff": diff}


def strip_check(src: str, tag: str) -> str:
    pat = re.compile(r"[ \t]*# <R472-%s>\n.*?[ \t]*# </R472-%s>\n" % (tag, tag), re.S)
    new, n = pat.subn("", src)
    if n != 1:
        raise SystemExit(f"ABORT: 條 {tag} 的標記在檔裡出現 {n} 次，不是 1 次")
    return new


def apply_mut(path: pathlib.Path, base: str, old: str, new: str, name: str) -> None:
    if base.count(old) != 1:
        raise SystemExit(f"ABORT: {name} 的舊字串在檔裡出現 {base.count(old)} 次，不是 1 次")
    path.write_text(base.replace(old, new))


def classify(name, named, st1, st2, st3):
    if st1["broken"] or st3["broken"]:
        return "BROKEN"
    if not named:                      # 負對照
        return "BROKEN" if st1["broken"] else ("RED_NO_LABEL" if st1["red"] else "MISSED")
    hit = [t for t in named if any(l.startswith(t + " ") for l in st1["failed"])]
    if not st1["red"]:
        return "MISSED"
    return "DETECTED" if len(hit) == len(named) else f"RED_WRONG_LABEL:{hit}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()
    wt = pathlib.Path(a.worktree).expanduser()
    tgt = wt / REL
    base = subprocess.run(["git", "show", "HEAD:" + REL], cwd=str(wt),
                          capture_output=True, text=True).stdout
    if not base:
        raise SystemExit("ABORT: 取不到 worktree 的 HEAD 版原始碼")

    res = {"clean": {}, "mutants": {}, "loadbearing": {}}
    tgt.write_text(base)
    res["clean"] = {"D1": d1(wt), "D2": d2(wt), "D3": d3(wt)}
    print(f"[乾淨基線] D1 red={res['clean']['D1']['red']} "
          f"D2 red={res['clean']['D2']['red']} D3 red={res['clean']['D3']['red']} "
          f"diff={res['clean']['D3']['diff']}")

    for name, old, new, named, why in MUTANTS:
        apply_mut(tgt, base, old, new, name)
        s1, s2, s3 = d1(wt), d2(wt), d3(wt)
        v = classify(name, named, s1, s2, s3)
        res["mutants"][name] = {"verdict": v, "named": named, "why": why,
                                "D1": s1, "D2": s2, "D3": s3}
        print(f"  {name}: {v}  指名={named}  紅的條={[l.split()[0] for l in s1['failed']]}"
              f"  D3red={s3['red']}")
        tgt.write_text(base)

    for name, tag in LOADBEARING:
        old, new = next((o, n) for nm, o, n, _, _ in MUTANTS if nm == name)
        stripped = strip_check(base, tag)
        apply_mut(tgt, stripped, old, new, name + "/strip")
        s1 = d1(wt)
        v = classify(name, [tag], s1, s1, {"broken": False, "red": False, "diff": []})
        res["loadbearing"][f"X-{tag}"] = {"mutant": name, "verdict": v, "D1": s1}
        print(f"  X-{tag}（刪掉條 {tag} 再跑 {name}）: {v}")
        tgt.write_text(base)

    ok = (not res["clean"]["D1"]["red"] and not res["clean"]["D3"]["red"]
          and all(m["verdict"] == "DETECTED" for n, m in res["mutants"].items()
                  if n != "N1_syntax")
          and res["mutants"]["N1_syntax"]["verdict"] == "BROKEN"
          and all(x["verdict"] == "MISSED" for x in res["loadbearing"].values()))
    res["all_predictions_hit"] = ok
    print("\n" + ("ALL_HIT" if ok else "NOT_ALL_HIT"))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
