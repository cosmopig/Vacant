#!/usr/bin/env python3
"""round680：`runner_git` 有沒有真的接進 `summary.json`。

為什麼要單獨驗接線（記憶鐵律）：「工具與判決分支驗過 ≠ 那一行的接線驗過」。
`runner_git_info()` 自己回傳對的東西，跟它**有沒有被寫進 summary 的那個 dict**，
是兩件事。而 `--arms probe` 在 `write_summary()` 之前就 return，
端到端探針**跑不到**那一行 ⇒ 只能用結構檢查，而結構檢查必須自己先被植入缺陷驗過。
"""
from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "ops/gain/gain_run.py"
results = []


def summary_dict_keys(src: str) -> list[str]:
    """找 `write_summary` 裡餵給 json.dumps 的那個 dict literal 的鍵。"""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == "write_summary"):
            continue
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "dumps"
                    and sub.args and isinstance(sub.args[0], ast.Dict)):
                return [k.value for k in sub.args[0].keys
                        if isinstance(k, ast.Constant)]
    raise AssertionError("找不到 write_summary 裡 json.dumps 的 dict literal"
                         "——接線檢查本身失效了，這不是通過")


def check(label, cond, detail):
    results.append(bool(cond))
    print(f"{'PASS' if cond else 'FAIL'} {label}　{detail}")


src = SRC.read_text(encoding="utf-8")
keys = summary_dict_keys(src)

check("W1 summary 的 dict literal 含 runner_git",
      "runner_git" in keys, f"鍵={keys}")

# 植入缺陷：把那一行拿掉，同一個檢查必須翻成 FAIL（證明 W1 有牙齒，
# 不是「不管怎樣都印 PASS」的裝飾品）。
mutated = src.replace('                "runner_git": RUNNER_GIT,\n', "", 1)
check("W2 拿掉那一行後 W1 會翻面 ⇒ W1 有牙齒是實測的",
      mutated != src and "runner_git" not in summary_dict_keys(mutated),
      "突變體的鍵少了 runner_git")

# 既有的鍵一個都不能少（不准為了加一個鍵而改掉別人引用過的輸出）
must = ["seed", "n", "offset", "n_tasks_loaded", "run_complete", "run_terminal",
        "request_policy", "pool", "instrument", "calibration", "arms",
        "equal_budget_comparison_valid"]
missing = [k for k in must if k not in keys]
check("W3 既有 12 個鍵一個都沒少（round672/677/678 引用過那些鍵）",
      not missing, f"缺={missing or '無'}")

# RUNNER_GIT 是模組級、只算一次（不是每次 write_summary 都 fork 一個 git）
tree = ast.parse(src)
mod_assign = [n for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "RUNNER_GIT" for t in n.targets)]
check("W4 RUNNER_GIT 是模組級常數、只算一次",
      len(mod_assign) == 1, f"模組級 assign 數={len(mod_assign)}")

# 匯入不得有副作用之外的破壞：語法 + 匯入都要過
p = subprocess.run([sys.executable, "-c",
                    "import importlib.util,pathlib;"
                    f"s=importlib.util.spec_from_file_location('gr',r'{SRC}');"
                    "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                    "print(m.RUNNER_GIT['sha'][:8], m.RUNNER_GIT['branch'])"],
                   capture_output=True, text=True, cwd=ROOT)
check("W5 匯入 gain_run.py 成功且 RUNNER_GIT 已求值",
      p.returncode == 0 and p.stdout.strip(), f"rc={p.returncode} out={p.stdout.strip()}")

real = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                      text=True, cwd=ROOT).stdout.strip()[:8]
check("W6 RUNNER_GIT.sha 與 git rev-parse HEAD 相符",
      p.stdout.strip().split()[0] == real if p.stdout.strip() else False,
      f"{p.stdout.strip().split()[0] if p.stdout.strip() else '?'} vs {real}")

ok = sum(results)
print(f"\n{ok}/{len(results)} PASS")
sys.exit(0 if ok == len(results) else 1)
