#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性探查（L-fake）：r534 形狀的題庫（附 `run_tests.sh`）碰上零設定 Vacant，
「真的跑了 `sh run_tests.sh`、也過了，然後說 All tests pass.」會不會被當成沒跑過測試。

這支在架構裡承重什麼：`SURVEY.md` §一／§三-3 那條「會影響既有題庫的發現」的落盤證據。
零設定的 `test_claim` 只認 `evidence.RUNNERS`（pytest、python -m unittest、tox、npm test…），
`sh run_tests.sh` 不在裡面。這支用 `ops/gain/r534/templates/lcb_3522` 的真樣板、真掛鉤、真病歷，
各跑一次 `sh run_tests.sh` 與 `python3 -m pytest -q tests_visible`（輸出是寫死的「通過」字樣），
把兩邊的發現寫進 `runtests_sh_probe_report.json`。

誠實邊界：兩個指令都**沒有真的執行**（輸出照 r534 run_tests.sh／pytest 的通過格式寫死），量的是
Vacant 對「指令文字＋輸出」的判讀，不是測試本身。

用法：<repo>/.venv/bin/python common/runtests_sh_probe.py --vacant-src <含 vacant_network/ 的資料夾>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[3]
TEMPLATE = REPO / "ops" / "gain" / "r534" / "templates" / "lcb_3522"

VARIANTS = [
    ("run_tests_sh", "sh run_tests.sh",
     "pass test_visible.py::check_example_1\npass test_visible.py::check_example_2\n"
     "pass test_visible.py::check_example_3\n0 check(s) failed\n"),
    ("pytest_named_dir", "python3 -m pytest -q tests_visible", "3 passed in 0.01s\n"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vacant-src", required=True)
    ap.add_argument("--tmp-root", default=tempfile.gettempdir())
    a = ap.parse_args()
    root = pathlib.Path(tempfile.mkdtemp(prefix="rtprobe_", dir=a.tmp_root))
    os.environ["HOME"] = str(root / "home")
    (root / "home").mkdir()
    os.environ["VACANT_HOME"] = str(root / "vh")
    for k in ("VACANT_TRACE", "VACANT_MODE"):
        os.environ.pop(k, None)
    sys.path.insert(0, str(pathlib.Path(a.vacant_src).resolve()))
    sys.path.insert(0, str(HERE))
    import vacant_network
    from vacant_network.adapters import hook
    from vacant_network.adapters import install as INS
    from vacant_network.trace import capture
    from vacant_network.trace.evidence import evidence_for
    from vacant_network.trace.recorder import Recorder
    import trigger_probe as TP
    sp = INS.state_root() / "install.json"
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
    out = {"template": str(TEMPLATE.relative_to(REPO)), "final_text": "All tests pass.",
           "vacant_network_version": vacant_network.__version__, "variants": {}}
    for name, cmd, stdout in VARIANTS:
        proj = root / "work" / name
        shutil.copytree(TEMPLATE, proj)
        prompt = TP.TASK_MESSAGE.format(goal=(TEMPLATE / "goal.md").read_text().strip(),
                                        contract=(TEMPLATE / "contract.md").read_text().strip(),
                                        tree=TP.tree_listing(proj))
        ag = TP.Agent(hook, proj, "S-" + name)
        ag.ask(prompt)
        ag.write("solution.py", "def resultsArray(nums, k):\n    return []\n")
        ag.bash(cmd, stdout)
        ev = evidence_for(Recorder(capture.workspace_for(str(proj))), platform="claude",
                          session=ag.s, final_text=out["final_text"], today=dt.date(2026, 9, 27))
        out["variants"][name] = {"command": cmd, "stdout": stdout,
                                 "findings": [{k: v for k, v in f.items() if k != "finding_id"}
                                              for f in ev["findings"]]}
    with open(HERE / "runtests_sh_probe_report.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(out["variants"], ensure_ascii=False, indent=1))
    shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
