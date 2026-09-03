"""替身自檢——**跑「replay 那一行本身」，不是只跑它的零件**（round646）。

`ops/run_tests_nopytest.py` 是量具。量具自己得先被驗，而且要**雙向**驗：
  - `tests/shim_selfcheck/good.py`  每個能力的正確用法 → 必須全 PASS
  - `tests/shim_selfcheck/bad.py`   每個能力植入一個缺陷 → **必須全被抓成 FAIL**
  - `tests/shim_selfcheck/empty.py` 一個測試都沒有       → 必須是 NOT_VERIFIED 且 exit 1

第二項是重點：round646 實測過，光有第一項驗不出「量具有沒有牙齒」——
`tests/test_gain_runner.py::test_off5_votes_on_behavior_not_source_text` 就是
「乾淨時 PASS、植入缺陷後**仍然** PASS」的活例子。

用法：python3 ops/run_tests_selfcheck.py     （exit 0 = 量具可信）
"""
import subprocess, sys, re

RUN = [sys.executable, "ops/run_tests_nopytest.py"]


def run(path):
    p = subprocess.run(RUN + [path], capture_output=True, text=True, timeout=300)
    m = re.search(r": (\d+)/(\d+) pass, (\d+) fail, (\d+) error, (\d+) skip => (\S+)",
                  p.stdout)
    if not m:
        print(f"BROKEN 讀不到 {path} 的總結行（量具輸出格式變了？）\n{p.stdout[-800:]}")
        sys.exit(2)
    ok, n, fail, err, skip, verdict = (*map(int, m.groups()[:5]), m.group(6))
    return dict(ok=ok, n=n, fail=fail, err=err, skip=skip, verdict=verdict, rc=p.returncode)


def check(label, got, want):
    bad = [k for k, v in want.items() if got[k] != v]
    print(f"{'OK  ' if not bad else 'BAD '} {label}: {got}")
    if bad:
        print(f"     期望 {[(k, want[k]) for k in bad]}")
    return not bad


good = run("tests/shim_selfcheck/good.py")
bad = run("tests/shim_selfcheck/bad.py")
empty = run("tests/shim_selfcheck/empty.py")

allok = True
# 正向：全過，而且收集數不准掉（掉了＝有能力被安靜漏收）
allok &= check("good  每個能力的正確用法", good,
               {"fail": 0, "err": 0, "verdict": "PASS", "rc": 0, "n": 16, "ok": 16})
# 反向：植入的 9 個缺陷一個都不准漏；parametrize 那兩個該過的仍要過
allok &= check("bad   植入缺陷必須被抓到", bad,
               {"fail": 9, "err": 0, "ok": 2, "n": 11, "verdict": "FAIL", "rc": 1})
# 安靜綠燈：收集到 0 個不准 exit 0
allok &= check("empty 零收集不准印成綠的", empty, {"n": 0, "rc": 1})
if not empty["verdict"].startswith("NOT_VERIFIED"):
    print(f"BAD  empty 的 verdict 應為 NOT_VERIFIED，實際 {empty['verdict']}")
    allok = False

print("\n量具自檢：" + ("通過，可以信它的綠燈" if allok else "**沒過**，先修量具再看任何測試結果"))
sys.exit(0 if allok else 1)
