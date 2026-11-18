"""產品臂（`vacant do pi`，usage=none）的模型呼叫數：從每格 vacant-work 底下的 pi JSON 日誌補算。

harness 對 P 臂記 usage=none（外層只看到一個 `vacant do` 行程），預註冊的 known_limits 要求結案時補這個數字。
一次模型呼叫＝pi 日誌裡一個 role=assistant 的 message_end。用法：
    python3 ops/redo/analysis/p_model_calls.py ~/dev/ops/redo_runs/confirm1 [--arm P]
"""
import glob, json, statistics, sys

def calls(log):
    n = 0
    for line in open(log, errors="replace"):
        if '"message_end"' not in line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "message_end" and e.get("message", {}).get("role") == "assistant":
            n += 1
    return n

def main(root, arm="P"):
    per_cell, attempts = [], []
    for cell in sorted(glob.glob(f"{root}/cells/*/r*/{arm}/cell.json")):
        d = cell.rsplit("/", 1)[0]
        logs = sorted(glob.glob(f"{d}/attempt_*/logs/vacant-work/restart-*/attempt_*/logs/agent_stdout.log"))
        per_cell.append(sum(calls(l) for l in logs))
        attempts.append(len(logs))
    if not per_cell:
        print("沒有找到格子"); return
    print(f"{root} 臂 {arm}：{len(per_cell)} 格；平均模型呼叫 {statistics.mean(per_cell):.1f}"
          f"（中位數 {statistics.median(per_cell)}）；平均內層嘗試 {statistics.mean(attempts):.2f}")

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0], sys.argv[sys.argv.index("--arm") + 1] if "--arm" in sys.argv else "P")
