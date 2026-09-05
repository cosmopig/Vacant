#!/usr/bin/env python3
"""R503：R495 普查**五道擋門**的承重牆刪除測試。
判準先行：DECISION_20260905_R503_R495_WALL_DELETION_PREREG.md（commit 3c156cc）。

跟 R500（做 R496 的同型測試）的差別，見判準 §一的對照表：
非 1:1 的歸屬、M3 走 selftest 不走 census、兩面牆事前就懷疑沒有主人。
所以每面牆量三件事（判準 §三）：突變表、乾淨 census、乾淨 selftest。

用法：
  python3 ops/gain/r495_wall_deletion.py --selftest
  python3 ops/gain/r495_wall_deletion.py --worktree /dev/shm/r503wt [--json <path>]
"""
from __future__ import annotations
import argparse, json, os, pathlib, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
REL = "ops/gain/r495_empirical_census.py"
CHECK = "ops/gain/r495_mutation_check.py"
LIVE = "g_r461_lcb3_three_arm"          # 判準 §四：本尺不得碰主 run

ALL_MUTS = ["M1_NO_SUBWINDOWS", "M2_FORCE_SAME", "M3_NO_GLIVE", "M4_NO_DEGENERATE"]

# 判準 §一：逐字錨點，各須恰好出現 1 次
WALLS = {
    "W1_G_N": ('    if out["n_windows"] != N_WINDOWS_EXPECTED:\n'
               '        out["blockers"].append("BROKEN_WINDOWS")\n'),
    "W2_G_CAL": ('    if out["calibration"]["C_POS"] != "EMPIRICAL_DEGENERATE" \\\n'
                 '            or out["calibration"]["C_NEG"] != "EMPIRICAL_MOVABLE":\n'
                 '        out["blockers"].append("BROKEN_CALIBRATION")\n'),
    "W3_G_LIVE": ('    if LIVE in str(file) and os.environ.get("R495_MUTANT", "") != "M3_NO_GLIVE":\n'
                  '        _live_reads += 1\n'
                  '        raise RuntimeError(f"G-LIVE: 拒絕碰主 run 的路徑：{file}")\n'),
    "W4_G_LIVE_BLOCKER": ('    if out["live_reads"] != 0:\n'
                          '        out["blockers"].append("BROKEN_LIVE_READ")\n'),
    "W5_G_REPRO": ('    if not out["repro_ok"]:\n'
                   '        out["blockers"].append("BROKEN_NO_REPRO")\n'),
}
# 判準 §二：非 1:1。W4／W5 事前就寫成「沒有主人」，不是漏填。
MUT_OF_WALL = {
    "W1_G_N": ["M1_NO_SUBWINDOWS"],
    "W2_G_CAL": ["M2_FORCE_SAME", "M4_NO_DEGENERATE"],
    "W3_G_LIVE": ["M3_NO_GLIVE"],
    "W4_G_LIVE_BLOCKER": [],
    "W5_G_REPRO": [],
}


def cut(src: str, block: str) -> str:
    """判準 §一：錨點必須恰好 1 次，否則不准動刀。"""
    n = src.count(block)
    if n != 1:
        raise ValueError(f"anchor count = {n}, expected 1")
    i = src.index(block)
    return src[:i] + src[i + len(block):]


# ─────────────────────────────────────────────────────────── 量測（不純，夾具不碰）
def _live_reads_seen() -> int:
    """判準 §四的繼承擋門：突變表把 census JSON 落在 /tmp/r495_mut_*.json。"""
    worst = 0
    for m in ALL_MUTS:
        p = pathlib.Path(f"/tmp/r495_mut_{m}.json")
        try:
            worst = max(worst, int(json.loads(p.read_text()).get("live_reads", 0)))
        except Exception:
            pass
    return worst


def run_mutcheck(wt: pathlib.Path) -> dict:
    for m in ALL_MUTS:                                   # 先清掉上一刀留下的 JSON
        pathlib.Path(f"/tmp/r495_mut_{m}.json").unlink(missing_ok=True)
    env = dict(os.environ)
    env.pop("R495_MUTANT", None)
    p = subprocess.run([sys.executable, CHECK], cwd=str(wt), env=env,
                       capture_output=True, text=True, timeout=3600)
    out = p.stdout + p.stderr
    broken = ("Traceback (most recent call last)" in out) or ("SyntaxError" in out)
    det = {}
    try:
        body = json.loads(out[out.index("{"):out.rindex("}") + 1])
        det = {k: bool(v.get("detected")) for k, v in body.items()}
        if sorted(det) != sorted(ALL_MUTS):
            broken = True                                 # 突變體增減 ⇒ BROKEN 不是安靜跳過
    except Exception:
        broken = True
    return {"rc": p.returncode, "broken": broken, "detected": det,
            "live_reads": _live_reads_seen(), "raw_tail": out[-400:]}


def run_clean(wt: pathlib.Path) -> dict:
    """判準 §三.2／3：乾淨 census ＋ 乾淨 selftest（無突變旗標）。"""
    env = dict(os.environ)
    env.pop("R495_MUTANT", None)
    jp = pathlib.Path("/tmp/r503_clean_census.json")
    jp.unlink(missing_ok=True)
    c = subprocess.run([sys.executable, REL, "--json", str(jp)], cwd=str(wt), env=env,
                       capture_output=True, text=True, timeout=1800)
    verdict, live = None, 0
    try:
        body = json.loads(jp.read_text())
        verdict, live = body.get("verdict"), int(body.get("live_reads", 0))
    except Exception:
        verdict = "BROKEN_NO_JSON"
    s = subprocess.run([sys.executable, REL, "--selftest"], cwd=str(wt), env=env,
                       capture_output=True, text=True, timeout=600)
    return {"census_verdict": verdict, "census_ok": verdict == "CENSUS_OK",
            "selftest_ok": s.returncode == 0 and "FAIL" not in s.stdout,
            "selftest_fails": [l.strip() for l in s.stdout.splitlines() if "FAIL" in l],
            "live_reads": live,
            "census_tail": (c.stdout + c.stderr)[-200:]}


# ─────────────────────────────────────────────────────────── 判決（純函式，夾具可餵）
def analyse(baseline: dict, cuts: dict) -> dict:
    res = {"walls": {}, "detail": {}, "specificity": {}, "n_broken_cut": 0}
    # 判準 §四：基線擋門
    if baseline.get("broken") or not all(baseline.get("detected", {}).get(m) for m in ALL_MUTS):
        res["verdict"] = "BASELINE_BROKEN"
        res["baseline_detected"] = baseline.get("detected")
        return res
    live_bad = int(baseline.get("live_reads") or 0) != 0
    for wall in sorted(WALLS):
        r = cuts.get(wall, {})
        own = MUT_OF_WALL[wall]
        if int(r.get("live_reads") or 0) != 0 or int((r.get("clean") or {}).get("live_reads") or 0) != 0:
            live_bad = True
        if r.get("broken"):
            res["walls"][wall] = "BROKEN_CUT"
            res["n_broken_cut"] += 1
            res["detail"][wall] = {"raw_tail": r.get("raw_tail")}
            continue
        det = r.get("detected", {})
        clean = r.get("clean") or {}
        notices = not (clean.get("census_ok") and clean.get("selftest_ok"))
        still = [m for m in own if det.get(m)]
        if own and not still:
            label = "LOAD_BEARING"
        elif notices:
            label = "CLEAN_NOTICES_ONLY"
        elif own:
            label = "STILL_RED_ELSEWHERE"
        else:
            label = "UNCOVERED_NO_MUTANT"
        res["walls"][wall] = label
        res["detail"][wall] = {"own": own, "still_red": still, "clean_notices": notices,
                               "clean": clean, "detected": det}
        for m in ALL_MUTS:                                # 判準 §四：專一性負對照
            if m not in own:
                res["specificity"][f"cut_{wall}_keeps_{m}"] = bool(det.get(m))
    res["baseline_detected"] = baseline.get("detected")
    if live_bad:
        res["verdict"] = "BROKEN_LIVE_READ_INHERITED"
    elif res["n_broken_cut"]:
        res["verdict"] = "BROKEN_CUT_PRESENT"
    elif all(v in ("LOAD_BEARING", "CLEAN_NOTICES_ONLY") for v in res["walls"].values()) \
            and all(res["specificity"].values()):
        res["verdict"] = "ALL_WALLS_COVERED"
    else:
        res["verdict"] = "SOME_WALL_UNCOVERED"
    return res


def main_run(wt: pathlib.Path) -> dict:
    if LIVE in str(wt) or wt == ROOT:
        return {"verdict": "REFUSED_BAD_WORKTREE", "walls": {}}
    tgt = wt / REL
    clean_src = tgt.read_text(encoding="utf-8")
    t0 = time.time()
    baseline = run_mutcheck(wt)
    cuts = {}
    for wall, block in WALLS.items():
        try:
            tgt.write_text(cut(clean_src, block), encoding="utf-8")
            r = run_mutcheck(wt)
            r["clean"] = run_clean(wt)
            cuts[wall] = r
        except ValueError as e:
            cuts[wall] = {"broken": True, "detected": {}, "raw_tail": f"anchor: {e}"}
        finally:
            tgt.write_text(clean_src, encoding="utf-8")          # 一律還原
        print(f"  [{time.time()-t0:6.0f}s] {wall}: "
              f"det={cuts[wall].get('detected')} clean={cuts[wall].get('clean', {}).get('census_verdict')}",
              flush=True)
    out = analyse(baseline, cuts)
    out["baseline_raw_tail"] = baseline.get("raw_tail")
    out["elapsed_s"] = round(time.time() - t0, 1)
    return out


# ───────────────────────────────────────────────────────────────────── selftest
def _c(det, clean_ok=True, self_ok=True, broken=False, live=0):
    return {"broken": broken, "detected": det, "live_reads": live,
            "clean": {"census_ok": clean_ok, "selftest_ok": self_ok,
                      "census_verdict": "CENSUS_OK" if clean_ok else "BROKEN_X", "live_reads": 0}}


def selftest() -> int:
    fails = []

    def chk(n, c):
        print(f"  {'ok  ' if c else 'FAIL'} {n}")
        if not c:
            fails.append(n)

    # cut：錨點必須恰好 1 次
    chk("cut_ok", cut("a\nXX\nb\n", "XX\n") == "a\nb\n")
    for bad, name in (("ZZ\n", "cut_missing_should_raise"), (None, None)):
        if bad is None:
            continue
        try:
            cut("a\nXX\nb\n", bad)
            fails.append(name)
        except ValueError:
            pass
    try:
        cut("XX\nXX\n", "XX\n")
        fails.append("cut_dup_should_raise")
    except ValueError:
        pass

    # 前置尺：真檔上的五個錨點各恰好 1 次（過期要 BROKEN，不准安靜跳過）
    real = (ROOT / REL).read_text(encoding="utf-8")
    for w, b in WALLS.items():
        chk(f"anchor_{w}", real.count(b) == 1)
    # 前置尺：突變表的四個名字確實在真檔裡（歸屬表過期也要 BROKEN）
    mreal = (ROOT / CHECK).read_text(encoding="utf-8")
    chk("muts_exist", all(f'"{m}"' in mreal for m in ALL_MUTS))
    chk("mut_of_wall_covers", sorted(MUT_OF_WALL) == sorted(WALLS)
        and sorted(m for v in MUT_OF_WALL.values() for m in v) == sorted(ALL_MUTS))

    allred = {m: True for m in ALL_MUTS}
    base = {"broken": False, "detected": allred, "live_reads": 0}

    def cuts_all(**over):
        d = {w: _c(dict(allred)) for w in WALLS}
        d.update(over)
        return d

    # 主人沉默 ⇒ LOAD_BEARING（W1 只有一個主人）
    g = analyse(base, cuts_all(W1_G_N=_c({**allred, "M1_NO_SUBWINDOWS": False})))
    chk("load_bearing", g["walls"]["W1_G_N"] == "LOAD_BEARING")
    # W2 有兩個主人：只沉默一個 ⇒ 不准算 LOAD_BEARING，且要具名
    p = analyse(base, cuts_all(W2_G_CAL=_c({**allred, "M2_FORCE_SAME": False})))
    chk("partial_owner_not_load_bearing", p["walls"]["W2_G_CAL"] == "STILL_RED_ELSEWHERE"
        and p["detail"]["W2_G_CAL"]["still_red"] == ["M4_NO_DEGENERATE"])
    both = analyse(base, cuts_all(W2_G_CAL=_c({**allred, "M2_FORCE_SAME": False,
                                               "M4_NO_DEGENERATE": False})))
    chk("both_owners_silent", both["walls"]["W2_G_CAL"] == "LOAD_BEARING")
    # 主人仍紅但乾淨跑會叫 ⇒ CLEAN_NOTICES_ONLY（W3 的預期形狀）
    cn = analyse(base, cuts_all(W3_G_LIVE=_c(dict(allred), self_ok=False)))
    chk("clean_notices_only", cn["walls"]["W3_G_LIVE"] == "CLEAN_NOTICES_ONLY")
    # 沒主人、乾淨跑也不叫 ⇒ UNCOVERED_NO_MUTANT
    chk("uncovered", g["walls"]["W4_G_LIVE_BLOCKER"] == "UNCOVERED_NO_MUTANT"
        and g["walls"]["W5_G_REPRO"] == "UNCOVERED_NO_MUTANT")
    # 沒主人但乾淨 census 倒了 ⇒ CLEAN_NOTICES_ONLY（不是 UNCOVERED）
    u2 = analyse(base, cuts_all(W4_G_LIVE_BLOCKER=_c(dict(allred), clean_ok=False)))
    chk("uncovered_but_clean_notices", u2["walls"]["W4_G_LIVE_BLOCKER"] == "CLEAN_NOTICES_ONLY")
    # 總判決：五面牆全 LOAD_BEARING/CLEAN_NOTICES 且專一性全過 ⇒ ALL_WALLS_COVERED
    ok_all = analyse(base, {
        "W1_G_N": _c({**allred, "M1_NO_SUBWINDOWS": False}),
        "W2_G_CAL": _c({**allred, "M2_FORCE_SAME": False, "M4_NO_DEGENERATE": False}),
        "W3_G_LIVE": _c({**allred, "M3_NO_GLIVE": False}),
        "W4_G_LIVE_BLOCKER": _c(dict(allred), clean_ok=False),
        "W5_G_REPRO": _c(dict(allred), self_ok=False)})
    chk("all_covered", ok_all["verdict"] == "ALL_WALLS_COVERED")
    chk("some_uncovered", g["verdict"] == "SOME_WALL_UNCOVERED")
    # 專一性倒了 ⇒ 不准判 ALL（刪 W1 連 M2 也不紅了）
    sp = analyse(base, {
        "W1_G_N": _c({**allred, "M1_NO_SUBWINDOWS": False, "M2_FORCE_SAME": False}),
        "W2_G_CAL": _c({**allred, "M2_FORCE_SAME": False, "M4_NO_DEGENERATE": False}),
        "W3_G_LIVE": _c({**allred, "M3_NO_GLIVE": False}),
        "W4_G_LIVE_BLOCKER": _c(dict(allred), clean_ok=False),
        "W5_G_REPRO": _c(dict(allred), self_ok=False)})
    chk("specificity_fails", sp["verdict"] == "SOME_WALL_UNCOVERED"
        and sp["specificity"]["cut_W1_G_N_keeps_M2_FORCE_SAME"] is False)
    # crash ⇒ BROKEN_CUT，不是 MISSED 也不是 DETECTED
    br = analyse(base, cuts_all(W5_G_REPRO={"broken": True, "detected": {}}))
    chk("broken_cut", br["walls"]["W5_G_REPRO"] == "BROKEN_CUT"
        and br["verdict"] == "BROKEN_CUT_PRESENT" and br["n_broken_cut"] == 1)
    # 基線不是 4/4 ⇒ BASELINE_BROKEN 且不准往下判
    bb = analyse({"broken": False, "detected": {**allred, "M3_NO_GLIVE": False}}, cuts_all())
    chk("baseline_broken", bb["verdict"] == "BASELINE_BROKEN" and bb["walls"] == {})
    chk("baseline_crash", analyse({"broken": True, "detected": {}}, cuts_all())["verdict"]
        == "BASELINE_BROKEN")
    # G-LIVE 繼承擋門：任一 census 讀到主 run ⇒ 蓋過一切
    lv = analyse(base, cuts_all(W1_G_N=_c({**allred, "M1_NO_SUBWINDOWS": False}, live=3)))
    chk("live_inherited", lv["verdict"] == "BROKEN_LIVE_READ_INHERITED")
    # 拒絕在工作目錄動刀
    chk("refuse_root", main_run(ROOT)["verdict"] == "REFUSED_BAD_WORKTREE")

    n = 22
    print(f"selftest {n - len(fails)}/{n}" + (f"  FAILS={fails}" if fails else ""))
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--worktree")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.worktree:
        print("need --worktree (不准在工作目錄上動刀)")
        return 2
    out = main_run(pathlib.Path(a.worktree).expanduser().resolve())
    if a.json:
        p = ROOT / a.json
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"verdict={out['verdict']}  elapsed_s={out.get('elapsed_s')}")
    print(f"walls={json.dumps(out.get('walls'), ensure_ascii=False)}")
    print(f"baseline={out.get('baseline_detected')}  n_broken_cut={out.get('n_broken_cut')}")
    print(f"specificity={json.dumps(out.get('specificity'), ensure_ascii=False)}")
    for w, d in (out.get("detail") or {}).items():
        print(f"  {w}: own={d.get('own')} still_red={d.get('still_red')} "
              f"clean_notices={d.get('clean_notices')} clean={json.dumps(d.get('clean'), ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
