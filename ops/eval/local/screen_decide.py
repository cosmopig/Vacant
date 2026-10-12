"""一小時篩選題組的判定（S36 本機／S26-api 付費；2026-09-26）：只讀篩選自己那幾跑的評分，套跑之前寫死的規則。

規則（`decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md` §三、§十；原型 `review_effect/scripts/screen1h__screen_decide.py`）：
- `net_U＝#(C 對、A 錯) − #(A 對、C 錯)`，只算 U（會被切斷的題）；
- K（沒裝時一直對的題）的淨損＝`#(A 對、C 錯) − #(C 對、A 錯)`；
- **多出來的錯答案**＝C 的「有答案檔、答錯」跑數 − A 的；
- **GO**：net_U ≥ 4、K 淨損 ≤ 2、多出來的錯答案 ≤ U＋K 的淨增對；**STOP**：net_U ≤ 1；其餘＝這一輪不判定（檢定力不夠）。

    python3 ops/eval/local/screen_decide.py --suite local --jobs <s36 jobs> --a A --c C35
    python3 ops/eval/local/screen_decide.py --suite api --jobs <api jobs> --a A --c C
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
from typing import Any

SUITES = {
    "local": {"U": "1 3 6 7 11 16 18 19 23 26 30 35 36 44 49 50 51 53 58 59 61 62 71 72".split(),
              "K": "8 9 15 21 22 24 25 29 48 54 57 64".split()},
    "api": {"U": "3 7 10 15 16 17 18 19 39 43 47 48 58 62 65 69 71 72".split(),
            "K": "8 12 25 30 35 42 56 63".split()},
}


def cells(jobs: pathlib.Path, arm: str, sample: int = 1) -> dict[str, dict[str, Any]]:
    """task → {reward, answer, exception}（本機的 g12-off-<組>-s<次>、付費的 g4-on-<組> 兩種擺法都讀；本機只讀第 `sample` 次）。"""
    out: dict[str, dict[str, Any]] = {}
    for trial in sorted(jobs.glob(f"*-{arm}*/*/dabstep-*__*")):
        m_arm = re.search(rf"(?:^|-){re.escape(arm)}(?:-s(\d+))?$", trial.parent.parent.name)
        if not m_arm or (m_arm.group(1) is not None and int(m_arm.group(1)) != sample):
            continue
        m = re.match(r"dabstep-(\d+)__", trial.name)
        if not m or not (trial / "result.json").is_file():
            continue
        try:
            reward = float((trial / "verifier" / "reward.txt").read_text().strip())
        except (OSError, ValueError):
            reward = None
        vt = (trial / "verifier" / "test-stdout.txt")
        missing = vt.is_file() and "answer.txt not found" in vt.read_text(errors="replace")
        exc = (json.loads((trial / "result.json").read_text()).get("exception_info") or {}).get("exception_type")
        out[m.group(1)] = {"reward": reward, "answer": not missing, "exception": exc}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--suite", choices=SUITES, required=True)
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--a", default="A")
    ap.add_argument("--c", required=True)
    ap.add_argument("--sample", type=int, default=1, help="本機擺法的第幾次（g12-off-<組>-s<次>）")
    ap.add_argument("--out", type=pathlib.Path)
    a = ap.parse_args(argv)
    A, C = cells(a.jobs, a.a, a.sample), cells(a.jobs, a.c, a.sample)
    res: dict[str, Any] = {"suite": a.suite, "a": a.a, "c": a.c, "sample": a.sample}
    net_right = 0
    for name, tasks in SUITES[a.suite].items():
        c_only = a_only = n = 0
        missing = []
        for t in tasks:
            x, y = A.get(t), C.get(t)
            if not x or not y or x["reward"] is None or y["reward"] is None:
                missing.append(t)
                continue
            n += 1
            c_only += y["reward"] == 1.0 and x["reward"] != 1.0
            a_only += x["reward"] == 1.0 and y["reward"] != 1.0
        res[name] = {"pairs": n, "C_only": c_only, "A_only": a_only, "net": c_only - a_only, "missing": missing}
        net_right += c_only - a_only
    wrong = {arm: sum(1 for t in SUITES[a.suite]["U"] + SUITES[a.suite]["K"] if d.get(t) and d[t]["answer"]
                      and d[t]["reward"] == 0.0) for arm, d in (("A", A), ("C", C))}
    extra_wrong = wrong["C"] - wrong["A"]
    res.update(wrong_answers=wrong, extra_wrong=extra_wrong, net_right=net_right)
    net_u, k_loss = res["U"]["net"], -res["K"]["net"]
    if res["U"]["missing"] or res["K"]["missing"]:
        decision = "INCOMPLETE"
    elif net_u >= 4 and k_loss <= 2 and extra_wrong <= net_right:
        decision = "GO"
    elif net_u <= 1:
        decision = "STOP"
    else:
        decision = "NOT DECIDED (underpowered)"
    res["decision"] = decision
    print(json.dumps(res, indent=1))
    if a.out:
        a.out.write_text(json.dumps(res, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
