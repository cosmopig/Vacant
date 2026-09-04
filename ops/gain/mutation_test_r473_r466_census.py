#!/usr/bin/env python3
"""R473：`r466_r461_sec2_sec6_census.py` 的**外部源碼級**植入缺陷測試。
判準 `DECISION_20260904_R473_R466_CENSUS_MUTATION_PREREG.md`（本檔之前 commit）。

⚠ **源碼級突變，不是檔內 `MUTANT` 旗標**：被測檔自己的 M1–M7 是寫在正式碼裡的
`if MUTANT == ...` 分支，與正式運算式**並存** ⇒ 「把正式那行整段刪掉會不會紅」
結構上答不了（r706）。本檔在 git worktree 裡做逐字替換，改的是正式碼本身。

判準（memory 鐵律）：
  * 只寫 `rc≠0` 不算抓到 ⇒ 每個突變體**指名**哪一條該紅（比對自檢輸出的條標籤首字）。
  * crash 收場記 `BROKEN`，不記 `caught`。
  * 承重牆（X-）測試（r695）：把指名的那一條**整段刪掉**再跑同一個突變體 ⇒ 必須退回 MISSED。

用法：python3 ops/gain/mutation_test_r473_r466_census.py --worktree ~/vacant/wt_r473 [--json out]
"""
from __future__ import annotations
import argparse, json, pathlib, re, subprocess, sys

REL = "ops/gain/r466_r461_sec2_sec6_census.py"
BASELINE_JSON = "ops/gain/data/r466_census.json"      # D3 的真資料對照（R466 收官落盤）

# ── 逐字舊字串 → 新字串。任何一條 old 在檔中不是恰好出現一次就是 BROKEN_PATCH。
SUPPRESS_OLD = (
    '        out["items"] = ({k: v for k, v in items.items()} if MUTANT == "M5_forced_under_contradiction"\n'
    '                        else {k: {**v, "class": ("SUPPRESSED" if v["class"] == "FORCED_GREEN"\n'
    '                                                 else v["class"])} for k, v in items.items()})\n')
SUPPRESS_NEW = '        out["items"] = {k: v for k, v in items.items()}\n'

PRED_OLD = 'PRED = {"S2-1": "EVALUABLE", "S2-2": "FORCED_GREEN", "S2-3": "EVALUABLE",\n'
PRED_NEW = 'PRED = {"S2-1": "FORCED_GREEN", "S2-2": "FORCED_GREEN", "S2-3": "EVALUABLE",\n'

INTENT_OLD = 'INTENT = {"S2-1": "evidence", "S2-2": "evidence", "S2-3": "evidence", "S2-4": "evidence",\n'
INTENT_NEW = 'INTENT = {"S2-1": "evidence", "S2-2": "guard", "S2-3": "evidence", "S2-4": "evidence",\n'

SRCPIN_OLD = '    if MUTANT == "M7_drop_source_pin":\n'
SRCPIN_NEW = '    if True:\n'

PINOK_OLD = '        ok = want in doc\n'
PINOK_NEW = '        ok = True\n'

B3_OLD = '    if MUTANT != "M1_drop_peek_gate" and FORBIDDEN_RUN in str(p):\n'
B3_NEW = '    if False:\n'

N1_OLD = 'def census() -> dict:\n'
N1_NEW = 'def census() -> dict:  this is not python\n'

# (名字, 舊, 新, 指名該紅的條（首字 token）, 說明)
MUTANTS = [
    ("X1_drop_suppression", SUPPRESS_OLD, SUPPRESS_NEW, ["J"],
     "B6 抑制式拿掉：CONTRADICTION 之下仍吐 FORCED_GREEN"),
    ("X2_pred_drift", PRED_OLD, PRED_NEW, ["I"],
     "事前預測被改寫：blind_hit_rate 安靜變成強制命中"),
    ("X3_intent_drift", INTENT_OLD, INTENT_NEW, ["I"],
     "intent 被改寫：evidence 級強制綠燈的警告安靜少一筆"),
    ("X4_drop_source_pin", SRCPIN_OLD, SRCPIN_NEW, ["K"],
     "來源釘退回讀 worktree：稽核的是今天的碼、不是被稽核的那個 commit"),
    ("P1_pin_noop", PINOK_OLD, PINOK_NEW, ["M4"],
     "正對照：判準字面比對變成恆真"),
    ("P2_b3_off", B3_OLD, B3_NEW, ["H"],
     "正對照：B3 主 run 擋門拿掉"),
    ("N1_syntax", N1_OLD, N1_NEW, [],
     "負對照：語法壞掉 ⇒ 必須記 BROKEN，不准記 caught"),
]

# 承重牆：(突變體, 要整段刪掉的新條)
LOADBEARING = [("X1_drop_suppression", "J"), ("X2_pred_drift", "I"),
               ("X3_intent_drift", "I"), ("X4_drop_source_pin", "K")]

BROKEN_MARKS = ("SyntaxError", "Traceback (most recent call last)",
                "ImportError", "IndentationError")


def run_cmd(cmd, cwd, timeout=600):
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr)


def failed_labels(out: str) -> list[str]:
    """被測檔印的是 `  [FAIL] <標籤>`（不是 r472 那支的 `  FAIL  <標籤>`）。"""
    return [m.group(1).strip() for m in re.finditer(r"^  \[FAIL\] (.+)$", out, re.M)]


def red_tokens(labels: list[str]) -> list[str]:
    return [l.split()[0] for l in labels if l.split()]


def d1(wt):
    rc, out = run_cmd(["python3", REL, "--selftest"], wt)
    return {"rc": rc, "red": rc != 0, "broken": any(m in out for m in BROKEN_MARKS),
            "failed": failed_labels(out)}


def d2(wt):
    rc, out = run_cmd(["python3", "ops/gain/prereg_falsifiability_census.py", "--selftest"], wt)
    return {"rc": rc, "red": rc != 0, "broken": any(m in out for m in BROKEN_MARKS)}


def _walk(new, old, p="", changed=None, added=None, removed=None):
    if isinstance(new, dict) and isinstance(old, dict):
        for k in sorted(set(new) | set(old)):
            if k not in old:
                added.append(p + "/" + k)
            elif k not in new:
                removed.append(p + "/" + k)
            else:
                _walk(new[k], old[k], p + "/" + k, changed, added, removed)
    elif new != old:
        changed.append(p)
    return changed, added, removed


def d3(wt):
    """真資料加法性見證：既有鍵逐值相同；新增鍵單獨列出（不算變紅）。"""
    outp = pathlib.Path(wt) / "_r473_d3.json"
    rc, out = run_cmd(["python3", REL, "--json", str(outp)], wt)
    if rc != 0 or not outp.exists():
        return {"rc": rc, "red": True, "broken": any(m in out for m in BROKEN_MARKS),
                "error": out.strip()[-300:]}
    new = json.loads(outp.read_text(encoding="utf-8"))
    old = json.loads((pathlib.Path(wt) / BASELINE_JSON).read_text(encoding="utf-8"))
    ch, ad, rm = _walk(new, old, "", [], [], [])
    return {"rc": rc, "red": bool(ch or rm), "broken": False,
            "changed": ch, "added": ad, "removed": rm,
            "blind_hit_rate": new.get("blind_hit_rate"),
            "forced_green_evidence_items": new.get("forced_green_evidence_items"),
            "class_counts": new.get("class_counts")}


def verdict_for(names, r1, r3):
    if r1["broken"] or r3.get("broken"):
        return "BROKEN"
    reds = red_tokens(r1["failed"])
    if names and all(n in reds for n in names):
        return "DETECTED"
    if r1["red"] or r3["red"]:
        return "RED_ELSEWHERE"          # 有東西紅，但不是指名的那一條 ⇒ 不算抓到
    return "MISSED"


COND_RE = "^    # --- COND {tok} ---$"


def strip_condition(src: str, tok: str) -> str:
    """把 `    # --- COND <tok> ---` 到下一個 COND 標記／`    print(` 之間整段刪掉。"""
    lines = src.splitlines(keepends=True)
    start = None
    for i, l in enumerate(lines):
        if re.match(COND_RE.format(tok=re.escape(tok)), l.rstrip("\n")):
            start = i
            break
    if start is None:
        raise SystemExit(f"承重牆測試找不到條 {tok} 的標記")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^    # --- COND ", lines[j]) or lines[j].startswith("    print("):
            end = j
            break
    return "".join(lines[:start] + lines[end:])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    root = pathlib.Path(__file__).resolve().parents[2]
    wt = pathlib.Path(a.worktree).expanduser()
    if not wt.exists():
        rc, out = run_cmd(["git", "worktree", "add", "--detach", str(wt), "HEAD"], root)
        if rc != 0:
            print(out); return 1
    else:
        run_cmd(["git", "-C", str(wt), "checkout", "--", "."], root)

    clean_src = subprocess.run(["git", "-C", str(root), "show", f"HEAD:{REL}"],
                               capture_output=True, text=True).stdout
    target = wt / REL

    def restore():
        target.write_text(clean_src, encoding="utf-8")

    res: dict = {"tool": "mutation_test_r473_r466_census",
                 "prereg": "DECISION_20260904_R473_R466_CENSUS_MUTATION_PREREG.md",
                 "rel": REL, "worktree": str(wt)}

    restore()
    b1, b2, b3 = d1(wt), d2(wt), d3(wt)
    res["baseline"] = {"d1": b1, "d2": b2, "d3": b3}
    print(f"[乾淨基線] D1 red={b1['red']} D2 red={b2['red']} D3 red={b3['red']} "
          f"D3 changed={b3.get('changed')} added={b3.get('added')}")

    rows = {}
    for name, old, new, names, why in MUTANTS:
        restore()
        src = target.read_text(encoding="utf-8")
        if src.count(old) != 1:
            rows[name] = {"verdict": "BROKEN_PATCH", "occurrences": src.count(old)}
            print(f"  {name:24s} BROKEN_PATCH（舊字串出現 {src.count(old)} 次）")
            continue
        target.write_text(src.replace(old, new), encoding="utf-8")
        r1, r2, r3 = d1(wt), d2(wt), d3(wt)
        v = verdict_for(names, r1, r3)
        rows[name] = {"verdict": v, "named": names, "red_tokens": red_tokens(r1["failed"]),
                      "d1_failed": r1["failed"], "d2_red": r2["red"],
                      "d3_changed": r3.get("changed"), "d3_blind_hit_rate": r3.get("blind_hit_rate"),
                      "d3_forced_green_evidence_items": r3.get("forced_green_evidence_items"),
                      "why": why}
        print(f"  {name:24s} {v:14s} 指名={names} 紅的條={red_tokens(r1['failed'])} "
              f"D3改值={r3.get('changed')}")
    res["mutants"] = rows

    lb = {}
    for name, tok in LOADBEARING:
        if rows.get(name, {}).get("verdict") != "DETECTED":
            lb[f"X-{tok}@{name}"] = {"skipped": "該突變體本來就不是 DETECTED"}
            continue
        restore()
        src = target.read_text(encoding="utf-8")
        old, new = next((o, n) for nm, o, n, _, _ in MUTANTS if nm == name)
        src = strip_condition(src, tok)
        target.write_text(src.replace(old, new), encoding="utf-8")
        r1, r3 = d1(wt), d3(wt)
        v = verdict_for([tok], r1, r3)
        lb[f"X-{tok}@{name}"] = {"verdict": v, "failed": r1["failed"]}
        print(f"  X-{tok}@{name}: {v}（刪掉條 {tok} 之後）")
    res["loadbearing"] = lb

    restore()
    ok = (not b1["red"] and not b2["red"] and not b3["red"]
          and all(r.get("verdict") not in ("BROKEN_PATCH",) for r in rows.values()))
    res["baseline_clean"] = ok
    print("ALL_DONE" if ok else "BASELINE_OR_PATCH_PROBLEM")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
