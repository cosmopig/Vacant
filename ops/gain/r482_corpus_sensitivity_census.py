#!/usr/bin/env python3
"""R482：語料增長擾動 census——找 R481 §3 那一類「夾具寫死語料事實 ⇒ 安靜衰減」。

判準見 DECISION_20260905_R482_CORPUS_SENSITIVITY_PREREG.md（量測之前 commit）。
判別量不是字面 grep，是擾動：往量具會掃的語料裡加一個「不帶訊號」的新成員，
selftest 的 rc 若因此翻掉 ⇒ 它的綠燈本來就靠語料當下的形狀撐著。

用法：
  python3 ops/gain/r482_corpus_sensitivity_census.py --selftest
  python3 ops/gain/r482_corpus_sensitivity_census.py --json ops/gain/data/r482_census.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF_NAME = Path(__file__).name
TIMEOUT_S = 90
OK_RCS = {0, 1, 2, 3}

# 具名排除（判準 §七）：不是安靜跳過。
EXCLUDED = {
    SELF_NAME: "本工具自己（會遞迴）",
}

PERTURBATIONS = {
    "P_MD": (
        "DECISION_R482_BENIGN_PROBE_DO_NOT_COMMIT.md",
        "# R482 benign probe\n\n這是一份只有散文的暫時檔案，沒有認證標題、沒有 run 名、沒有預測行。\n",
    ),
    "P_TEST": (
        "tests/test_r482_benign_probe_DO_NOT_COMMIT.py",
        "def test_r482_benign_probe():\n    assert True\n",
    ),
    "P_TOOL": (
        "ops/gain/r482_benign_probe_DO_NOT_COMMIT.py",
        'print("r482 benign probe")\n',
    ),
}


def discover_tools(gain_dir: Path) -> list[str]:
    """ops/gain 底下所有帶 --selftest 的 .py，排除具名清單。"""
    out = []
    for p in sorted(gain_dir.glob("*.py")):
        if p.name in EXCLUDED:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "--selftest" in txt:
            out.append(p.name)
    return out


def run_selftest(script: Path, cwd: Path) -> int:
    """回傳 rc；timeout 回傳 -9 當成 BROKEN 的訊號。"""
    try:
        r = subprocess.run(
            [sys.executable, str(script), "--selftest"],
            cwd=str(cwd), capture_output=True, timeout=TIMEOUT_S,
        )
        return r.returncode
    except subprocess.TimeoutExpired:
        return -9


def classify(clean_a: int, clean_b: int, pert: dict[str, int]) -> tuple[str, list[str]]:
    """判準 §三，逐字實作。回傳 (verdict, 觸發的擾動代號)。"""
    mutant = os.environ.get("R482_MUTANT", "")
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


def _write_perturbations(root: Path) -> list[Path]:
    made = []
    for rel, body in PERTURBATIONS.values():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        made.append(p)
    return made


def _clear_perturbations(root: Path) -> None:
    for rel, _ in PERTURBATIONS.values():
        p = root / rel
        if p.exists():
            p.unlink()


def census(root: Path, tools: list[str], gain_rel: str = "ops/gain",
           progress: bool = False) -> dict:
    """每支工具：clean×2 ＋ 每個擾動×1。擾動檔一律在 finally 清掉。"""
    gain_dir = root / gain_rel
    records = {}
    try:
        _clear_perturbations(root)
        for name in tools:
            script = gain_dir / name
            rec = {"clean_a": run_selftest(script, root), "clean_b": run_selftest(script, root),
                   "pert": {}}
            records[name] = rec
        for key, (rel, body) in PERTURBATIONS.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
            try:
                for name in tools:
                    records[name]["pert"][key] = run_selftest(gain_dir / name, root)
                    if progress:
                        print(f"  {key} {name} rc={records[name]['pert'][key]}", flush=True)
            finally:
                if p.exists():
                    p.unlink()
    finally:
        _clear_perturbations(root)

    for name, rec in records.items():
        v, trig = classify(rec["clean_a"], rec["clean_b"], rec["pert"])
        rec["verdict"] = v
        rec["triggered_by"] = trig

    counts = {}
    for rec in records.values():
        counts[rec["verdict"]] = counts.get(rec["verdict"], 0) + 1
    return {
        "tools_scanned": len(tools),
        "excluded": EXCLUDED,
        "perturbations": list(PERTURBATIONS),
        "records": records,
        "counts": counts,
        "clean_red": sorted(n for n, r in records.items()
                            if r["clean_a"] == r["clean_b"] and r["clean_a"] not in (0, -9)),
        "decay_prone": sorted(n for n, r in records.items() if r["verdict"] == "DECAY_PRONE"),
        "masking": sorted(n for n, r in records.items() if r["verdict"] == "MASKING"),
        "nondeterministic": sorted(n for n, r in records.items()
                                   if r["verdict"] == "NONDETERMINISTIC"),
        "broken": sorted(n for n, r in records.items() if r["verdict"] == "BROKEN"),
    }


# ---------------------------------------------------------------- 合成對照

POS_CONTROL = '''\
import sys
from pathlib import Path
ROOT = Path({root!r})
if "--selftest" in sys.argv:
    n = len(list(ROOT.glob("DECISION_*.md")))
    ok = (n == {baseline})
    print("pos control", n, ok)
    sys.exit(0 if ok else 1)
'''

NEG_CONTROL = '''\
import sys
from pathlib import Path
ROOT = Path({root!r})
if "--selftest" in sys.argv:
    docs = sorted(p.name for p in ROOT.glob("DECISION_*.md"))
    out = {{d: len(d) for d in docs}}
    ok = all(d in out for d in docs) and len(out) == len(docs)
    print("neg control", len(docs), ok)
    sys.exit(0 if ok else 1)
'''


def build_controls(root: Path, dest: Path) -> list[str]:
    """正對照＝寫死語料基數（R481 缺陷的合成複製）；負對照＝關係式，同樣讀真語料。"""
    dest.mkdir(parents=True, exist_ok=True)
    baseline = len(list(root.glob("DECISION_*.md")))
    (dest / "_r482_pos_control.py").write_text(
        POS_CONTROL.format(root=str(root), baseline=baseline), encoding="utf-8")
    (dest / "_r482_neg_control.py").write_text(
        NEG_CONTROL.format(root=str(root)), encoding="utf-8")
    return ["_r482_pos_control.py", "_r482_neg_control.py"]


# ---------------------------------------------------------------- selftest

def _fake_tool(d: Path, name: str, rcs: list[int]) -> None:
    """每次被呼叫就吐 rcs 裡的下一個 rc（用計數檔記狀態）。"""
    (d / name).write_text(
        "import sys\n"
        f"from pathlib import Path\n"
        f"c = Path(__file__).with_suffix('.count')\n"
        "n = int(c.read_text()) if c.exists() else 0\n"
        "c.write_text(str(n + 1))\n"
        f"rcs = {rcs!r}\n"
        "if '--selftest' in sys.argv:\n"
        "    sys.exit(rcs[min(n, len(rcs) - 1)])\n",
        encoding="utf-8")


def selftest() -> int:
    fails = []
    n = 0

    def ck(label, cond, extra=""):
        nonlocal n
        n += 1
        status = "PASS" if cond else "FAIL"
        if not cond:
            fails.append(label)
        print(f"  {label:44s} {status}  {extra}")

    mutant = os.environ.get("R482_MUTANT", "")

    # --- A 群：classify 的判準逐條（單元）
    ck("A1_insensitive", classify(0, 0, {"P_MD": 0, "P_TEST": 0})[0] == "INSENSITIVE")
    ck("A2_decay_prone", classify(0, 0, {"P_MD": 0, "P_TEST": 1})[0] == "DECAY_PRONE")
    ck("A2b_decay_names_trigger",
       classify(0, 0, {"P_MD": 0, "P_TEST": 1})[1] == ["P_TEST"])
    ck("A3_masking", classify(1, 1, {"P_MD": 0})[0] == "MASKING")
    ck("A4_nondet_wins_over_decay",
       classify(0, 1, {"P_MD": 1})[0] == "NONDETERMINISTIC",
       "不決定性優先，判準 §六-4")
    ck("A5_broken_timeout", classify(0, 0, {"P_MD": -9})[0] == "BROKEN")
    ck("A6_sensitive_other", classify(1, 1, {"P_MD": 2})[0] == "SENSITIVE_OTHER")
    ck("A7_broken_beats_nondet", classify(0, 1, {"P_MD": -9})[0] == "BROKEN")

    with tempfile.TemporaryDirectory(dir="/dev/shm") as td:
        d = Path(td)
        gd = d / "ops" / "gain"
        gd.mkdir(parents=True)
        (d / "tests").mkdir()

        # --- B 群：census() 端到端（真的起子行程、真的建擾動檔）
        _fake_tool(gd, "t_flat.py", [0])
        _fake_tool(gd, "t_nondet.py", [0, 1, 0])
        (gd / "t_decay.py").write_text(
            "import sys\nfrom pathlib import Path\n"
            f"R = Path({str(d)!r})\n"
            "if '--selftest' in sys.argv:\n"
            "    sys.exit(0 if not (R / 'tests' / 'test_r482_benign_probe_DO_NOT_COMMIT.py').exists() else 1)\n",
            encoding="utf-8")
        res = census(d, ["t_flat.py", "t_nondet.py", "t_decay.py"])
        ck("B1_flat_insensitive", res["records"]["t_flat.py"]["verdict"] == "INSENSITIVE")
        ck("B2_nondet_detected", res["records"]["t_nondet.py"]["verdict"] == "NONDETERMINISTIC")
        ck("B3_decay_detected", res["records"]["t_decay.py"]["verdict"] == "DECAY_PRONE",
           str(res["records"]["t_decay.py"]["triggered_by"]))
        ck("B3b_decay_trigger_is_P_TEST",
           res["records"]["t_decay.py"]["triggered_by"] == ["P_TEST"])
        ck("B4_tools_scanned", res["tools_scanned"] == 3)

        # --- C 群：擾動檔一定被清掉（含 census 拋例外時）
        left = [rel for rel, _ in PERTURBATIONS.values() if (d / rel).exists()]
        ck("C1_perturbations_cleaned", left == [], str(left))

        # --- D 群：discover_tools 的排除與第三型「掃到 0 個目標」
        (gd / "no_selftest.py").write_text("print(1)\n", encoding="utf-8")
        found = discover_tools(gd)
        ck("D1_discover_skips_non_selftest", "no_selftest.py" not in found, str(found))
        ck("D2_discover_finds_selftest_tools",
           {"t_flat.py", "t_decay.py"} <= set(found), str(found))
        empty = d / "empty_gain"
        empty.mkdir()
        ck("D3_empty_dir_is_zero", discover_tools(empty) == [])

    # --- E 群：真語料上的合成雙向對照（判準 §四）——這一段用真的 ROOT
    with tempfile.TemporaryDirectory(dir="/dev/shm") as td2:
        cdir = Path(td2)
        names = build_controls(ROOT, cdir)
        cres = _census_with_dir(ROOT, cdir, names)
        pv = cres["records"]["_r482_pos_control.py"]["verdict"]
        nv = cres["records"]["_r482_neg_control.py"]["verdict"]
        ck("E1_pos_control_is_decay_prone", pv == "DECAY_PRONE",
           f"{pv} trig={cres['records']['_r482_pos_control.py']['triggered_by']}")
        ck("E2_neg_control_is_insensitive", nv == "INSENSITIVE", nv)
        ck("E3_pos_trigger_is_P_MD",
           cres["records"]["_r482_pos_control.py"]["triggered_by"] == ["P_MD"],
           "只有 root .md 才改得動 DECISION_*.md 的基數")

    ok = not fails
    print(f"selftest {'SELFTEST_PASS' if ok else 'SELFTEST_FAIL'} {n - len(fails)}/{n}"
          + (f"  MUTANT={mutant}" if mutant else "")
          + ("" if ok else f"  failed={fails}"))
    return 0 if ok else 3


def _census_with_dir(root: Path, gain_dir: Path, tools: list[str]) -> dict:
    """對照腳本放在 root 之外的暫存目錄，但擾動仍加在真的 root 上。"""
    # census() 用 root / gain_rel 定位腳本；對照放在 root 之外，用相對路徑接過去。
    rel = os.path.relpath(gain_dir, root)
    return census(root, tools, gain_rel=rel)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--only", help="逗號分隔的工具名（除錯用）")
    ap.add_argument("--progress", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    gain_dir = ROOT / "ops" / "gain"
    tools = discover_tools(gain_dir)
    if a.only:
        want = set(a.only.split(","))
        tools = [t for t in tools if t in want]
    if not tools:
        print("verdict UNSCANNED  rc=2  掃到 0 個目標（第三型安靜量不到）")
        return 2

    res = census(ROOT, tools, progress=a.progress)

    # 合成雙向對照，跟真資料同一次跑
    with tempfile.TemporaryDirectory(dir="/dev/shm") as td:
        cdir = Path(td)
        names = build_controls(ROOT, cdir)
        cres = _census_with_dir(ROOT, cdir, names)
    res["controls"] = {k: cres["records"][k] for k in cres["records"]}
    pos_ok = cres["records"]["_r482_pos_control.py"]["verdict"] == "DECAY_PRONE"
    neg_ok = cres["records"]["_r482_neg_control.py"]["verdict"] == "INSENSITIVE"
    res["controls_ok"] = bool(pos_ok and neg_ok)

    if not res["controls_ok"]:
        res["verdict"] = "BASELINE_BROKEN"
        rc = 2
    elif res["decay_prone"] or res["masking"]:
        res["verdict"] = "DECAY_CLASS_PRESENT"
        rc = 1
    else:
        res["verdict"] = "NO_DECAY_FOUND_TODAY"
        rc = 0
    res["rc"] = rc

    print(f"verdict {res['verdict']}  rc={rc}  tools_scanned={res['tools_scanned']}")
    print(f"  counts={res['counts']}")
    print(f"  controls_ok={res['controls_ok']} (pos={pos_ok} neg={neg_ok})")
    for key in ("decay_prone", "masking", "nondeterministic", "broken", "clean_red"):
        print(f"  {key}={res[key]}")
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  wrote {a.json}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
