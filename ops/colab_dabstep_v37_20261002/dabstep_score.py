#!/usr/bin/env python3
"""DABstep 計分（計分使用者、圍牆裡跑）。用法：dabstep_score.py <hidden> <app>
照 Harbor 題目自己的 tests/test.sh 逐字跑：只把 /tests/ 換成 <hidden>/tests/、/logs/verifier 換成暫存目錄、/app/answer.txt 換成 <app>/answer.txt
（格子裡計分時 <app> 就是 /app ⇒ 沒有差別；量具在暫存目錄跑時才用得到）。
印一行 JSON：{"pass": reward==1, "reward": …, "answer_exists": …}。test.sh 本身沒寫 reward ⇒ "pass": null（infra）。"""
import json, os, pathlib, subprocess, sys, tempfile
hidden, app = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
src = (hidden / "tests" / "test.sh").read_text()
with tempfile.TemporaryDirectory() as td:
    sh = (src.replace("/tests/", str(hidden / "tests") + "/").replace("/logs/verifier", td)
          .replace("/app/answer.txt", str(app / "answer.txt")))
    p = pathlib.Path(td) / "test.sh"; p.write_text(sh)
    r = subprocess.run(["bash", str(p)], capture_output=True, text=True, timeout=600)
    rw = pathlib.Path(td) / "reward.txt"
    reward = rw.read_text().strip() if rw.exists() else None
print(r.stdout[-2000:], file=sys.stderr)
print(json.dumps({"pass": None if reward is None else reward == "1", "reward": reward,
                  "answer_exists": (app / "answer.txt").is_file(), "rc": r.returncode}))
