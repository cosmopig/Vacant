#!/usr/bin/env python3
"""R483：把那 8 支「只提及 --selftest」的突變量具接進語料增長擾動 census。

判準見 DECISION_20260905_R483_WORKTREE_MUTATION_CENSUS_PREREG.md（量測之前 commit 1bcdd91）。

核心設計（判準 §二／§三）：這 8 支的「語料在哪」不同，擾動就得加在不同地方。
  ROOT 域        eq5_analyze_mutation_check    → 擾動加 ROOT 才有解析度
  WT 域（6 支）  r470/r471/r472/r473/r474/r475 → 擾動加 worktree 才有解析度
  自建極小域     r476（只 copy2 兩個檔）       → 兩臂都沒有解析度＝構造強制綠燈
把擾動加在 ROOT 然後宣告 WT 域工具 INSENSITIVE，是強制綠燈，不是證據。

⚠ r476 的 build_worktree() 第一行是 shutil.rmtree(wt)：**絕不可以**餵它共用 worktree。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_S = 600
OK_RCS = {0, 1, 2, 3}
DEFAULT_BUDGET_S = 3600            # 判準 §六-4 的時間盒

# 判準 §三：三種擾動逐字沿用 R482，不改。
PERTURBATIONS = {
    "P_MD": ("DECISION_R483_BENIGN_PROBE_DO_NOT_COMMIT.md",
             "# R483 benign probe\n\n只有散文，沒有認證標題、沒有 run 名、沒有預測行。\n"),
    "P_TEST": ("tests/test_r483_benign_probe_DO_NOT_COMMIT.py",
               "def test_r483_benign_probe():\n    assert True\n"),
    "P_TOOL": ("ops/gain/r483_benign_probe_DO_NOT_COMMIT.py",
               'print("r483 benign probe")\n'),
}

# 判準 §二的 scoping 表。argv 裡的 {WT} / {R476WT} 由呼叫端填。
TOOLS = [
    {"name": "eq5_analyze_mutation_check.py", "scope": "ROOT",
     "argv": ["ops/gain/eq5_analyze_mutation_check.py"]},
    {"name": "mutation_test_r470_paired_ci.py", "scope": "WT",
     "argv": ["ops/gain/mutation_test_r470_paired_ci.py", "--worktree", "{WT}"]},
    {"name": "r471_specificity_and_deletion.py", "scope": "WT",
     "argv": ["ops/gain/r471_specificity_and_deletion.py", "--worktree", "{WT}"]},
    {"name": "mutation_test_r472_gauge_capability.py", "scope": "WT",
     "argv": ["ops/gain/mutation_test_r472_gauge_capability.py", "--worktree", "{WT}"]},
    {"name": "mutation_test_r473_r466_census.py", "scope": "WT",
     "argv": ["ops/gain/mutation_test_r473_r466_census.py", "--worktree", "{WT}"]},
    {"name": "mutation_test_r474_stub_sweep.py", "scope": "WT",
     "argv": ["ops/gain/mutation_test_r474_stub_sweep.py", "--worktree", "{WT}"]},
    {"name": "mutation_test_r475_oracle_sweep.py", "scope": "WT",
     "argv": ["ops/gain/mutation_test_r475_oracle_sweep.py", "--worktree", "{WT}"]},
    {"name": "mutation_test_r476_closing_arbiter_drift.py", "scope": "SELF_MINIMAL",
     "argv": ["ops/gain/mutation_test_r476_closing_arbiter_drift.py",
              "--worktree", "{R476WT}"]},
]

# 判準 §五 P-1／P-7：哪些工具的哪一臂是構造上的強制綠燈。
FORCED_GREEN = {
    ("WT", "A_ROOT"): "受測目標跑在 worktree 裡，ROOT 的新檔看不見",
    ("SELF_MINIMAL", "A_ROOT"): "自建 worktree 只 copy2 兩個檔，ROOT 的新檔看不見",
    ("SELF_MINIMAL", "A_WT"): "同上，共用 worktree 也碰不到它",
    ("ROOT", "A_WT"): "沒有 --worktree，不進 A_WT",
}


def arms_for(scope: str) -> list[str]:
    """判準 §三：哪支工具進哪個臂。"""
    if os.environ.get("R483_MUTANT") == "M3_ROOT_ARM_COUNTS":
        return ["A_ROOT"]                      # 退回「只用 ROOT 臂」＝把強制綠燈當證據
    return {"ROOT": ["A_ROOT"], "WT": ["A_ROOT", "A_WT"],
            "SELF_MINIMAL": ["A_ROOT"]}[scope]


def classify(clean_a: int, clean_b: int, pert: dict[str, int]) -> tuple[str, list[str]]:
    """判準 §三，逐條複製 R482 classify() 的語意。"""
    mutant = os.environ.get("R483_MUTANT", "")
    rcs = [clean_a, clean_b] + list(pert.values())
    if any(rc not in OK_RCS for rc in rcs):
        return "BROKEN", [k for k, v in pert.items() if v not in OK_RCS]
    if clean_a != clean_b and mutant != "M1_IGNORE_NONDET":
        return "NONDETERMINISTIC", []
    base = clean_a
    changed = [k for k, v in pert.items() if v != base]
    if not changed:
        return "INSENSITIVE", []
    if mutant == "M2_ANY_CHANGE_IS_FINE":
        return "INSENSITIVE", []
    if base == 0 and any(pert[k] != 0 for k in changed):
        return "DECAY_PRONE", [k for k in changed if pert[k] != 0]
    if base != 0 and any(pert[k] == 0 for k in changed):
        return "MASKING", [k for k in changed if pert[k] == 0]
    return "SENSITIVE_OTHER", changed


def run_tool(argv: list[str], cwd: Path) -> int:
    try:
        p = subprocess.run([sys.executable] + argv, cwd=str(cwd),
                           capture_output=True, timeout=TIMEOUT_S)
        return p.returncode
    except subprocess.TimeoutExpired:
        return -9


def write_pert(base: Path, key: str) -> Path:
    rel, body = PERTURBATIONS[key]
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def clear_perts(base: Path) -> None:
    for rel, _ in PERTURBATIONS.values():
        p = base / rel
        if p.exists() and os.environ.get("R483_MUTANT") != "M4_LEAK_PERTURBATION":
            p.unlink()


# ---------------------------------------------------------------- 合成對照（判準 §四）

POS_CONTROL = '''\
import sys
from pathlib import Path
WT = Path({wt!r})
if "--selftest" in sys.argv:
    n = len(list((WT / "tests").glob("test_*.py")))
    ok = (n == {baseline})
    print("pos control", n, ok)
    sys.exit(0 if ok else 1)
'''

NEG_CONTROL = '''\
import sys
from pathlib import Path
WT = Path({wt!r})
if "--selftest" in sys.argv:
    names = sorted(p.name for p in (WT / "tests").glob("test_*.py"))
    tbl = {{n: len(n) for n in names}}
    ok = all(n in tbl for n in names) and len(tbl) == len(names)
    print("neg control", len(names), ok)
    sys.exit(0 if ok else 1)
'''


def build_controls(wt: Path, dest: Path) -> list[dict]:
    """正對照＝寫死語料基數（memory 的「突變量具寫死期望收集數」合成複製）；
    負對照＝讀同一份語料但斷言關係式。兩者都在 A_WT 臂。"""
    dest.mkdir(parents=True, exist_ok=True)
    baseline = len(list((wt / "tests").glob("test_*.py")))
    (dest / "_r483_pos_control.py").write_text(
        POS_CONTROL.format(wt=str(wt), baseline=baseline), encoding="utf-8")
    (dest / "_r483_neg_control.py").write_text(
        NEG_CONTROL.format(wt=str(wt)), encoding="utf-8")
    return [
        {"name": "_r483_pos_control.py", "scope": "WT",
         "argv": [str(dest / "_r483_pos_control.py"), "--selftest"], "control": True},
        {"name": "_r483_neg_control.py", "scope": "WT",
         "argv": [str(dest / "_r483_neg_control.py"), "--selftest"], "control": True},
    ]


# ---------------------------------------------------------------- census

def census(root: Path, wt: Path, tools: list[dict], r476wt: Path,
           budget_s: float = DEFAULT_BUDGET_S, progress: bool = False,
           restore=None) -> dict:
    """先跑 A_WT（有解析度的臂），再跑 A_ROOT（強制綠燈的守門臂）——判準 §六-4：
    時間盒觸發時，寧可丟掉守門臂也不要丟掉證據臂。"""
    t0 = time.time()
    def argv_of(t):
        return [a.replace("{WT}", str(wt)).replace("{R476WT}", str(r476wt)) for a in t["argv"]]

    recs = {t["name"]: {"scope": t["scope"], "control": t.get("control", False),
                        "arms": {}, "clean_a": None, "clean_b": None} for t in tools}
    unscanned: list[str] = []

    def left():
        return budget_s - (time.time() - t0)

    clear_perts(root); clear_perts(wt)
    for t in tools:
        if left() <= 2 * TIMEOUT_S / 10 and left() < 60:
            unscanned.append(f"{t['name']}:clean"); continue
        if restore:
            restore()
        recs[t["name"]]["clean_a"] = run_tool(argv_of(t), root)
        if restore:
            restore()
        recs[t["name"]]["clean_b"] = run_tool(argv_of(t), root)
        if progress:
            print(f"  clean {t['name']} {recs[t['name']]['clean_a']}/"
                  f"{recs[t['name']]['clean_b']}  ({left():.0f}s left)", flush=True)

    for arm, base in (("A_WT", wt), ("A_ROOT", root)):
        members = [t for t in tools if arm in arms_for(t["scope"])]
        for key in PERTURBATIONS:
            p = write_pert(base, key)
            try:
                for t in members:
                    if recs[t["name"]]["clean_a"] is None:
                        continue
                    if left() < 60:
                        unscanned.append(f"{t['name']}:{arm}:{key}"); continue
                    if restore:
                        restore()
                    rc = run_tool(argv_of(t), root)
                    recs[t["name"]]["arms"].setdefault(arm, {})[key] = rc
                    if progress:
                        print(f"  {arm} {key} {t['name']} rc={rc}  ({left():.0f}s left)",
                              flush=True)
            finally:
                if p.exists() and os.environ.get("R483_MUTANT") != "M4_LEAK_PERTURBATION":
                    p.unlink()
        clear_perts(base)

    clear_perts(root); clear_perts(wt)

    for name, r in recs.items():
        r["verdicts"] = {}
        for arm in ("A_WT", "A_ROOT"):
            pert = r["arms"].get(arm)
            if r["clean_a"] is None or not pert or len(pert) != len(PERTURBATIONS):
                if arm in arms_for(r["scope"]):
                    r["verdicts"][arm] = {"verdict": "UNSCANNED", "triggered_by": []}
                continue
            v, trig = classify(r["clean_a"], r["clean_b"], pert)
            r["verdicts"][arm] = {"verdict": v, "triggered_by": trig}
            fg = FORCED_GREEN.get((r["scope"], arm))
            if fg and os.environ.get("R483_MUTANT") != "M5_DROP_FORCED_GREEN":
                r["verdicts"][arm]["forced_green"] = fg

    return {"records": recs, "unscanned": sorted(unscanned),
            "elapsed_s": round(time.time() - t0, 1)}


def summarize(res: dict) -> dict:
    recs = res["records"]
    real = {n: r for n, r in recs.items() if not r["control"]}
    ev = {}          # 有解析度的判決（不含強制綠燈）
    forced = {}
    for n, r in real.items():
        for arm, v in r["verdicts"].items():
            (forced if "forced_green" in v else ev)[f"{n}@{arm}"] = v["verdict"]
    counts = {}
    for v in ev.values():
        counts[v] = counts.get(v, 0) + 1
    # 自己的第二型「安靜量不到」：若 scoping 表說某格是構造強制綠燈，而它其實不綠，
    # 那個判決會被 ev 排除 ⇒ 從頂層完全消失。要具名吐出來，而且要否決整份判決。
    # 只有「語料敏感」那幾種判決才推翻 scoping 表的宣稱。
    # NONDETERMINISTIC／BROKEN／UNSCANNED 是 infra 狀態，對「這格看不看得見語料」沒有陳述
    # ⇒ 它們不算矛盾，但也**不准安靜丟掉**，另立具名清單。
    SENSITIVE = {"DECAY_PRONE", "MASKING", "SENSITIVE_OTHER"}
    contradictions = sorted(k for k, v in forced.items() if v in SENSITIVE)
    unevaluable = sorted(k for k, v in forced.items()
                         if v != "INSENSITIVE" and v not in SENSITIVE)
    if os.environ.get("R483_MUTANT") == "M6_HIDE_SCOPING_CONTRADICTION":
        contradictions = []
    return {"evidence_cells": ev, "forced_green_cells": forced,
            "forced_green_contradictions": contradictions,
            "forced_green_unevaluable": unevaluable,
            "evidence_counts": counts,
            "decay_prone": sorted(k for k, v in ev.items() if v == "DECAY_PRONE"),
            "masking": sorted(k for k, v in ev.items() if v == "MASKING"),
            "nondeterministic": sorted(k for k, v in ev.items() if v == "NONDETERMINISTIC"),
            "broken": sorted(k for k, v in ev.items() if v == "BROKEN"),
            "unscanned": res["unscanned"]}


def controls_ok(res: dict) -> tuple[bool, dict]:
    recs = res["records"]
    detail = {}
    ok = True
    pos = recs.get("_r483_pos_control.py", {}).get("verdicts", {}).get("A_WT")
    neg = recs.get("_r483_neg_control.py", {}).get("verdicts", {}).get("A_WT")
    detail["pos"] = pos
    detail["neg"] = neg
    if not pos or pos["verdict"] != "DECAY_PRONE" or pos["triggered_by"] != ["P_TEST"]:
        ok = False
    if not neg or neg["verdict"] != "INSENSITIVE":
        ok = False
    return ok, detail


# ---------------------------------------------------------------- selftest

def _fake(d: Path, name: str, body: str) -> None:
    (d / name).write_text(body, encoding="utf-8")


def selftest() -> int:
    fails, n = [], 0

    def ck(label, cond, extra=""):
        nonlocal n
        n += 1
        if not cond:
            fails.append(label)
        print(f"  {label:46s} {'PASS' if cond else 'FAIL'}  {extra}")

    mutant = os.environ.get("R483_MUTANT", "")

    # --- A 群：classify 逐條（單元）
    ck("A1_insensitive", classify(0, 0, {"P_MD": 0, "P_TEST": 0})[0] == "INSENSITIVE")
    ck("A2_decay_prone", classify(0, 0, {"P_MD": 0, "P_TEST": 1})[0] == "DECAY_PRONE")
    ck("A2b_decay_trigger_named",
       classify(0, 0, {"P_MD": 0, "P_TEST": 1})[1] == ["P_TEST"])
    ck("A3_masking", classify(1, 1, {"P_MD": 0})[0] == "MASKING")
    ck("A4_nondet_beats_decay", classify(0, 1, {"P_MD": 1})[0] == "NONDETERMINISTIC")
    ck("A5_broken_timeout", classify(0, 0, {"P_MD": -9})[0] == "BROKEN")
    ck("A6_broken_beats_nondet", classify(0, 1, {"P_MD": -9})[0] == "BROKEN")
    ck("A7_sensitive_other", classify(1, 1, {"P_MD": 2})[0] == "SENSITIVE_OTHER")

    # --- B 群：scoping 表（判準 §二／§三）
    ck("B1_wt_tool_has_two_arms", arms_for("WT") == ["A_ROOT", "A_WT"])
    ck("B2_root_tool_root_only", arms_for("ROOT") == ["A_ROOT"])
    ck("B3_self_minimal_root_only", arms_for("SELF_MINIMAL") == ["A_ROOT"])
    ck("B4_table_covers_all_tools",
       {t["scope"] for t in TOOLS} == {"ROOT", "WT", "SELF_MINIMAL"})
    ck("B5_r476_gets_its_own_worktree",
       all("{WT}" not in t["argv"] for t in TOOLS if t["scope"] == "SELF_MINIMAL"),
       "r476 的 build_worktree 會 rmtree 它拿到的路徑")
    ck("B6_eight_tools", len(TOOLS) == 8)

    with tempfile.TemporaryDirectory(dir="/dev/shm") as td:
        d = Path(td)
        rt, wt = d / "root", d / "wt"
        (rt / "ops" / "gain").mkdir(parents=True)
        (rt / "tests").mkdir()
        (wt / "ops" / "gain").mkdir(parents=True)
        (wt / "tests").mkdir()
        gd = rt / "ops" / "gain"

        # 兩個方向的假工具：一個只看 wt 的語料，一個只看 root 的語料。
        # 這對夾具正是「兩個臂各自有解析度」的證明——單一臂看不見其中一個。
        probe_test = PERTURBATIONS["P_TEST"][0]
        _fake(gd, "t_wt_decay.py",
              "import sys\nfrom pathlib import Path\n"
              f"sys.exit(1 if (Path({str(wt)!r}) / {probe_test!r}).exists() else 0)\n")
        _fake(gd, "t_root_decay.py",
              "import sys\nfrom pathlib import Path\n"
              f"sys.exit(1 if (Path({str(rt)!r}) / {probe_test!r}).exists() else 0)\n")
        _fake(gd, "t_flat.py", "import sys\nsys.exit(0)\n")
        cnt = gd / "t_nondet.count"
        _fake(gd, "t_nondet.py",
              "import sys\nfrom pathlib import Path\n"
              f"c = Path({str(cnt)!r})\n"
              "k = int(c.read_text()) if c.exists() else 0\n"
              "c.write_text(str(k + 1))\n"
              "sys.exit([0, 1, 0][min(k, 2)])\n")

        fixtures = [
            {"name": "t_wt_decay.py", "scope": "WT",
             "argv": ["ops/gain/t_wt_decay.py", "--worktree", "{WT}"]},
            {"name": "t_root_decay.py", "scope": "WT",
             "argv": ["ops/gain/t_root_decay.py", "--worktree", "{WT}"]},
            {"name": "t_flat.py", "scope": "WT", "argv": ["ops/gain/t_flat.py"]},
            {"name": "t_nondet.py", "scope": "WT", "argv": ["ops/gain/t_nondet.py"]},
        ]
        res = census(rt, wt, fixtures, r476wt=d / "r476wt")
        rv = {k: v["verdicts"] for k, v in res["records"].items()}
        def V(tool, arm, field="verdict"):
            return rv.get(tool, {}).get(arm, {}).get(field)

        ck("C1_wt_decay_seen_in_A_WT",
           V("t_wt_decay.py", "A_WT") == "DECAY_PRONE",
           str(V("t_wt_decay.py", "A_WT")))
        ck("C1b_wt_decay_trigger_is_P_TEST",
           V("t_wt_decay.py", "A_WT", "triggered_by") == ["P_TEST"])
        ck("C2_wt_decay_invisible_in_A_ROOT",
           V("t_wt_decay.py", "A_ROOT") == "INSENSITIVE",
           "＝R482 的做法看不見它，這條就是本輪存在的理由")
        ck("C3_root_decay_seen_in_A_ROOT",
           V("t_root_decay.py", "A_ROOT") == "DECAY_PRONE",
           str(V("t_root_decay.py", "A_ROOT")))
        ck("C4_root_decay_invisible_in_A_WT",
           V("t_root_decay.py", "A_WT") == "INSENSITIVE")
        ck("C5_flat_insensitive_both",
           V("t_flat.py", "A_WT") == "INSENSITIVE"
           and V("t_flat.py", "A_ROOT") == "INSENSITIVE")
        ck("C6_nondet_detected",
           V("t_nondet.py", "A_WT") == "NONDETERMINISTIC",
           str(V("t_nondet.py", "A_WT")))
        ck("C7_forced_green_labelled_in_A_ROOT",
           V("t_flat.py", "A_ROOT", "forced_green") is not None,
           "WT 域工具的 A_ROOT 格必須帶 forced_green 標籤")
        ck("C8_A_WT_not_labelled_forced",
           V("t_flat.py", "A_WT", "forced_green") is None)
        ck("C9_perturbations_cleaned",
           [r for base in (rt, wt) for r, _ in PERTURBATIONS.values() if (base / r).exists()] == [])

        s = summarize(res)
        ck("C10_forced_cells_excluded_from_evidence",
           all("@A_ROOT" not in k for k in s["evidence_cells"]),
           str(list(s["evidence_cells"])))
        ck("C11_decay_reported_from_evidence_arm",
           s["decay_prone"] == ["t_wt_decay.py@A_WT"], str(s["decay_prone"]))
        # t_root_decay 宣告為 WT 域卻真的對 ROOT 敏感 ⇒ scoping 表在這一格是錯的。
        # 沒有這條，那個 DECAY_PRONE 會被 forced_green 標籤吃掉、頂層完全看不見。
        ck("C12_scoping_contradiction_named",
           s["forced_green_contradictions"] == ["t_root_decay.py@A_ROOT"],
           str(s["forced_green_contradictions"]))
        ck("C12c_nondet_in_forced_cell_is_not_a_contradiction",
           "t_nondet.py@A_ROOT" not in s["forced_green_contradictions"],
           "infra 狀態不推翻 scoping 宣稱")
        ck("C12d_but_it_is_still_named",
           "t_nondet.py@A_ROOT" in s["forced_green_unevaluable"],
           str(s["forced_green_unevaluable"]))
        ck("C12b_contradiction_is_invisible_in_decay_prone",
           "t_root_decay.py@A_ROOT" not in s["decay_prone"],
           "＝沒有 C12 就是安靜量不到")

        # --- D 群：時間盒必須記 UNSCANNED，不准安靜記 INSENSITIVE
        _fake(gd, "t_slow.py", "import sys, time\ntime.sleep(3)\nsys.exit(0)\n")
        slow = [{"name": "t_slow.py", "scope": "WT", "argv": ["ops/gain/t_slow.py"]}]
        r2 = census(rt, wt, slow, r476wt=d / "r476wt", budget_s=7)
        vs = [v["verdict"] for v in r2["records"]["t_slow.py"]["verdicts"].values()]
        ck("D1_budget_gives_UNSCANNED", "UNSCANNED" in vs, str(vs))
        ck("D2_budget_never_silently_insensitive",
           "INSENSITIVE" not in vs or r2["unscanned"] == [], str(r2["unscanned"]))
        ck("D3_unscanned_named", any("t_slow.py" in u for u in r2["unscanned"]),
           str(r2["unscanned"]))

        # --- E 群：雙向對照（用假的 wt 語料，不碰真 repo）
        cdir = d / "ctl"
        ctls = build_controls(wt, cdir)
        rc3 = census(rt, wt, ctls, r476wt=d / "r476wt")
        ok, det = controls_ok(rc3)
        ck("E1_pos_control_decay_prone",
           det["pos"] and det["pos"]["verdict"] == "DECAY_PRONE", str(det["pos"]))
        ck("E2_neg_control_insensitive",
           det["neg"] and det["neg"]["verdict"] == "INSENSITIVE", str(det["neg"]))
        ck("E3_controls_ok_true", ok is True)
        ck("E4_controls_excluded_from_evidence",
           summarize(rc3)["evidence_cells"] == {},
           "對照不得混進真工具的計數")
        ck("E5_clean_run_has_no_contradiction",
           summarize(rc3)["forced_green_contradictions"] == []
           and summarize(rc3)["forced_green_unevaluable"] == [],
           "乾淨那一組不得誤報 scoping 矛盾")

    ok = not fails
    print(f"selftest {'SELFTEST_PASS' if ok else 'SELFTEST_FAIL'} {n - len(fails)}/{n}"
          + (f"  MUTANT={mutant}" if mutant else "")
          + ("" if ok else f"  failed={fails}"))
    return 0 if ok else 3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--worktree", default="/dev/shm/r483wt")
    ap.add_argument("--r476-worktree", default="/dev/shm/r476wt_r483")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--only")
    ap.add_argument("--progress", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    wt = Path(a.worktree).resolve()
    if not (wt / "ops" / "gain").is_dir():
        print(f"verdict BASELINE_BROKEN  rc=2  worktree 不存在或不像 repo：{wt}")
        return 2
    if wt.resolve() == Path(a.r476_worktree).resolve():
        print("verdict BASELINE_BROKEN  rc=2  r476 會 rmtree 它的 worktree，不可共用")
        return 2

    tools = list(TOOLS)
    if a.only:
        want = set(a.only.split(","))
        tools = [t for t in tools if t["name"] in want]
    if not tools:
        print("verdict UNSCANNED  rc=2  掃到 0 個目標（第三型安靜量不到）")
        return 2

    def restore():
        subprocess.run(["git", "-C", str(wt), "checkout", "--", "."],
                       capture_output=True)

    with tempfile.TemporaryDirectory(dir="/dev/shm") as td:
        ctls = build_controls(wt, Path(td))
        res = census(ROOT, wt, tools + ctls, Path(a.r476_worktree),
                     budget_s=a.budget_s, progress=a.progress, restore=restore)

    ok, det = controls_ok(res)
    out = {"prereg": "DECISION_20260905_R483_WORKTREE_MUTATION_CENSUS_PREREG.md",
           "worktree": str(wt), "perturbations": list(PERTURBATIONS),
           "scoping": {t["name"]: t["scope"] for t in TOOLS},
           "records": res["records"], "elapsed_s": res["elapsed_s"],
           "controls_ok": ok, "controls": det}
    out.update(summarize(res))

    if not ok:
        out["verdict"], out["rc"] = "BASELINE_BROKEN", 2
    elif out["forced_green_contradictions"]:
        out["verdict"], out["rc"] = "SCOPING_TABLE_REFUTED", 2
    elif out["decay_prone"] or out["masking"]:
        out["verdict"], out["rc"] = "DECAY_CLASS_PRESENT", 1
    elif out["unscanned"]:
        out["verdict"], out["rc"] = "PARTIAL_NO_DECAY_FOUND", 1
    else:
        out["verdict"], out["rc"] = "NO_DECAY_FOUND_TODAY", 0

    print(f"verdict {out['verdict']}  rc={out['rc']}  elapsed={out['elapsed_s']}s")
    print(f"  evidence cells={len(out['evidence_cells'])}  counts={out['evidence_counts']}")
    print(f"  forced_green cells={len(out['forced_green_cells'])}  (判準 §五 P-1／P-7，不得當證據)")
    print(f"  decay_prone={out['decay_prone']}  masking={out['masking']}")
    print(f"  nondeterministic={out['nondeterministic']}  broken={out['broken']}")
    print(f"  unscanned={out['unscanned']}")
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                encoding="utf-8")
    return out["rc"]


if __name__ == "__main__":
    sys.exit(main())
