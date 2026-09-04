"""R738：`tests/test_equal_budget_rules_r446.py` 的突變測試（這支測試有沒有牙齒）。

判準：`DECISION_20260904_R738_R446_TEST_TEETH_PREREG.md`（commit 238051d，**量測之前** commit）。

為什麼要有這支
--------------
r737 把這支測試從「收集 0」修成「12/12 PASS」。**全綠只證明它會跑，不證明它會叫**——
這個 repo 有過「乾淨 PASS、植入缺陷仍 PASS」的假測試。本支對被測模組做 14 次
精確字串替換（11 個正對照 ＋ 1 個負對照 ＋ 2 個事前點名的預期漏網），
逐個問「事前指名的那條測試有沒有叫」。

三條硬規則（違反就會量出「有牙齒」的假象）
- 突變**在被測函式內部生效**（直接改原始碼，不用 env 旗標——模組層讀 env 的突變體永遠不生效）。
- 突變體與測試在**同一個 import 環境**。
- 判決**不准只寫 rc≠0**：收集數掉下來／harness crash 一律記 `BROKEN`，不算偵測到。

用法
    python3 ops/gain/mutation_test_r446_rules.py --root <repo 或 worktree 的根>

⚠ **`--root` 指到有 gain_run 活著的工作區時會拒跑**：本支會短暫改寫產品碼原始檔
（跑完 `finally` 還原並驗 sha256）。要在活著的 run 旁邊做，就開 worktree：
    git worktree add --detach ~/vacant/wt_xxx HEAD
    ln -s <repo>/.vacant-private ~/vacant/wt_xxx/.vacant-private
"""
import argparse, hashlib, json, os, re, subprocess, sys, pathlib

_ap = argparse.ArgumentParser()
_ap.add_argument("--root", required=True, help="要施工的 repo／worktree 根目錄")
_ap.add_argument("--allow-live", action="store_true",
                 help="明知有 gain_run 活著仍要在該工作區施工（不建議）")
_A = _ap.parse_args()
ROOT = pathlib.Path(_A.root).resolve()

# 活著的 run 就在這個工作區 ⇒ 拒跑（它的落盤檔在這裡，產品碼也在這裡）
_live = subprocess.run(["bash", "-c",
                        'ps -eo pid,cmd | grep "^ *[0-9]* python3 ops/gain/gain_run\\.py" || true'],
                       capture_output=True, text=True).stdout.strip()
if _live and not _A.allow_live:
    for _pid in [l.split()[0] for l in _live.splitlines()]:
        try:
            if pathlib.Path(f"/proc/{_pid}/cwd").resolve() == ROOT:
                sys.exit(f"拒跑：gain_run PID {_pid} 的 cwd 就是 {ROOT}。開 worktree，或 --allow-live。")
        except (OSError, PermissionError):
            pass

SRC = ROOT / "ops/gain/replay/equal_budget_rules.py"
TEST = "tests/test_equal_budget_rules_r446.py"
CLEAN = SRC.read_text()
CLEAN_SHA = hashlib.sha256(CLEAN.encode()).hexdigest()

M = [
 # (id, 舊字串, 新字串, 事前指名該叫的測試, 事前預測)
 ("M1", '        return (passers[0], False) if passers else (None, True)',
        '        return (passers[-1], False) if passers else (None, True)',
        ["test_filter_first_takes_earliest_visible_passer"], "DETECTED"),
 ("M2", '        key = sig if sig is not None else f"__SIG_UNKNOWN_{i}"   # 未知不併桶',
        '        key = sig if sig is not None else "__SIG_UNKNOWN"   # MUTANT 併桶',
        ["test_unknown_signature_does_not_merge_buckets"], "DETECTED"),
 ("M3", '    return min(min(x) for x in tied)',
        '    return max(max(x) for x in tied)',
        ["test_filter_vote_prefers_the_majority_behaviour_among_passers"], "DETECTED"),
 ("M4", '    tied = [x for x in buckets if len(x) == top]\n    out = []',
        '    tied = list(buckets)   # MUTANT 不限平手桶\n    out = []',
        ["test_vote_dist_matches_arm_off5_two_stage_uniform"], "DETECTED"),
 ("M5", '    if refused or idx is None:\n        return False',
        '    if refused or idx is None:\n        return True   # MUTANT 拒交算通過',
        ["test_score_counts_refusal_as_failure"], "DETECTED"),
 ("M6", '        return (_vote_first(view, passers) if passers\n                else _vote_first(view, allidx)), False',
        '        return ((_vote_first(view, passers), False) if passers\n                else (None, True))   # MUTANT 退化成 FILTER_VOTE',
        ["test_filter_vote_fallback_never_refuses"], "DETECTED"),
 ("M7", '        return next(i for i in allidx if key(i) == best), False',
        '        return [i for i in allidx if key(i) == best][-1], False',
        ["test_depth_best_picks_deepest_prefix_and_never_refuses"], "DETECTED"),
 ("M8", '        return _vote_first(view, allidx), False',
        '        return _vote_first(view, passers or allidx), False   # MUTANT 偷看 visible',
        ["test_off5_replay_is_plain_majority_ignoring_visible"], "DETECTED"),
 ("M9", '    passers = [i for i in allidx if view[i]["vis"] is True]',
        '    passers = [i for i in allidx if view[i]["vis"] is True]\n    _leak = [view[i]["hid"] for i in allidx]   # MUTANT V/GT 洩漏',
        ["test_pick_never_sees_hidden"], "DETECTED"),
 ("M10",'    return len(pairs), b, c, min(1.0, 2 * tail / 2 ** nd)',
        '    return len(pairs), b, c, min(1.0, tail / 2 ** nd)   # MUTANT 單尾',
        ["test_mcnemar_exact_two_sided"], "DETECTED"),
 ("M11",'    rng = random.Random(seed)\n    reps = [100.0 * sum(rng.choices(d, k=n)) / n for _ in range(b)]',
        '    rng = random.Random()   # MUTANT 無 seed\n    reps = [100.0 * sum(rng.choices(d, k=n)) / n for _ in range(b)]',
        ["test_boot_ci_is_deterministic_and_brackets_the_point_estimate"], "DETECTED"),
 # 負對照：語意等價，必須不被抓到
 ("N1", '    passers = [i for i in allidx if view[i]["vis"] is True]',
        '    passers = list(filter(lambda i: view[i]["vis"] is True, allidx))',
        [], "MISSED"),
 # 事前點名的預期漏網
 ("M12",'    return [b[k] for k in order]',
        '    return [b[k] for k in sorted(b)]   # MUTANT 桶序改成字典序',
        [], "MISSED"),
 ("M13",'            return -(10 ** 9) if d is None else d',
        '            return (10 ** 9) if d is None else d   # MUTANT None 變最好',
        [], "MISSED"),
 # 壞掉對照（R739）：語法錯 ⇒ 收集數掉到 0 ⇒ 必須判 BROKEN，不准判 DETECTED。
 # 沒有它，「期望收集數改成從乾淨基線衍生」有沒有在擋東西是看不出來的。
 ("B1", 'def _buckets(view: list[dict], idxs: list[int]) -> list[list[int]]:',
        'def _buckets(view: list[dict], idxs: list[int]) -> list[list[int]]:\n    ((( # MUTANT 語法錯',
        [], "BROKEN"),
]

def run():
    p = subprocess.run([sys.executable, "ops/run_tests_nopytest.py", TEST],
                       cwd=ROOT, capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT),
                            "HOME": os.environ.get("HOME", "/root")})
    out = p.stdout + p.stderr
    res = {}
    for line in out.splitlines():
        m = re.match(r"^(PASS|FAIL|ERROR|SKIP)\s+(test_\S+?)(:|$|\s)", line)
        if m:
            res[m.group(2)] = m.group(1)
    summ = re.search(r"(\d+)/(\d+) pass, (\d+) fail, (\d+) error, (\d+) skip => (\w+)", out)
    return p.returncode, res, (summ.groups() if summ else None), out

# 期望收集數來自**乾淨基線的實測**，不是寫死的常數：測試檔增減一條時，
# 寫死的 12 會讓 15 個對照全部安靜變成 BROKEN（＝「安靜量不到」）。
_rc0, _res0, _summ0, _out0 = run()
if _summ0 is None or int(_summ0[1]) == 0:
    sys.exit("乾淨基線收集不到測試，中止：\n" + _out0[-2000:])
EXPECT_COLLECTED = int(_summ0[1])
BASELINE_OK = _summ0[5] == "PASS" and int(_summ0[0]) == EXPECT_COLLECTED
print(f"乾淨基線: collected={EXPECT_COLLECTED} {' '.join(_summ0)} "
      f"=> {'OK' if BASELINE_OK else '⚠ 基線就沒全過'}")

rows = []
for mid, old, new, named, pred in M:
    n_occ = CLEAN.count(old)
    if n_occ != 1:
        rows.append(dict(id=mid, verdict="BROKEN", why=f"舊字串出現 {n_occ} 次（要求恰好 1）"))
        continue
    try:
        SRC.write_text(CLEAN.replace(old, new))
        rc, res, summ, out = run()
    finally:                                   # 任何例外都要還原產品碼
        SRC.write_text(CLEAN)
    back = hashlib.sha256(SRC.read_text().encode()).hexdigest()
    assert back == CLEAN_SHA, f"{mid} 還原失敗 {back}"
    collected = int(summ[1]) if summ else 0
    red = sorted(k for k, v in res.items() if v in ("FAIL", "ERROR"))
    if summ is None or collected != EXPECT_COLLECTED:
        v = "BROKEN"
    elif named and all(t in red for t in named):
        v = "DETECTED"
    elif red:
        v = "DETECTED_OFF_TARGET" if named else "DETECTED"
    else:
        v = "MISSED"
    rows.append(dict(id=mid, verdict=v, pred=pred, collected=collected, rc=rc,
                     red=red, named=named, summary=summ and " ".join(summ)))
    print(f"{mid:4} pred={pred:8} => {v:20} collected={collected} rc={rc} red={red}")

print()
_agree = sum(1 for r in rows if r.get("verdict") == r.get("pred"))
print(f"事前預測相符 {_agree}/{len(rows)}；基線 collected={EXPECT_COLLECTED} "
      f"baseline_ok={BASELINE_OK}")
print(json.dumps(rows, ensure_ascii=False, indent=1))
final = hashlib.sha256(SRC.read_text().encode()).hexdigest()
print("\n還原後 sha256 ==", final, "相同" if final == CLEAN_SHA else "⚠ 不同")
