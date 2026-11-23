"""每筆測資以子行程執行候選解，不接收預期答案；承接 PROTOCOL.md 的 Ordering。"""
import json
import subprocess
import sys

CANDIDATE = """
import json
import sys
sys.path.insert(0, '/work')
from solution import solve
print(json.dumps(solve(json.load(sys.stdin)), allow_nan=False))
"""


def run_case(example):
    try:
        proc = subprocess.run([sys.executable, "-I", "-B", "-c", CANDIDATE],
                              input=json.dumps(example), capture_output=True, text=True, timeout=4,
                              errors="replace")
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}
    if proc.returncode != 0:
        return {"status": "nonzero", "rc": proc.returncode, "stderr_tail": proc.stderr[-500:]}
    try:
        value = json.loads(proc.stdout, parse_constant=lambda word: (_ for _ in ()).throw(ValueError(word)))
    except ValueError:
        return {"status": "invalid_json", "stdout_tail": proc.stdout[-500:]}
    return {"status": "ok", "value": value}


if __name__ == "__main__":
    print(json.dumps([run_case(case) for case in json.load(sys.stdin)], allow_nan=False))
