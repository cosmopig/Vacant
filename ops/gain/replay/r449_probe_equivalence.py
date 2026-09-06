#!/usr/bin/env python3
"""R449 §四-3 的等價性證明：`probe_instrument` 抽出共用量具之後，行為逐鍵不變。

round451 用它證明過的一句話：`--base HEAD --bank evalplus --seed g-r212-route-20260828
--n 179 --sample 0` ⇒ EQUIVALENT，新舊兩版 `probe_instrument` 的 8 個回傳鍵（含
`detail`／`visible_detail` 的逐題欄位）完全相同，兩版都是 179/179 ＋ 179/179。

做法（零 API、零模型呼叫，只跑本機沙箱）：
  1. `git show <base>:ops/gain/gain_run.py` 取出改動前的版本，落在 `ops/gain/` 底下
     （放同一層才讓那支自己的 `parents[2]` sys.path 插入指到對的 repo 根），另名載入。
     本檔自己住在 `ops/gain/replay/`，所以 `GAIN` 與 `ROOT` 是分開算的兩個路徑。
  2. 兩個版本對**同一批題目**跑 `probe_instrument(sample=N, bank=...)`。
  3. 回傳的 dict 逐鍵比對；不一致就印出差在哪一題、哪一個欄位。

為什麼需要：repo 裡沒有任何 pytest 直接呼叫 `probe_instrument`（round749 查證：
`grep -rl probe_instrument tests/` 空），所以「跑了測試都綠」證明不了這一段沒被改壞。

⚠ 空洞通過的防呆（`--base` 指到已經含有改動的 commit 時）：舊版原始碼裡若已經出現
  `suitegauge`，這支會直接 `SystemExit`。沒有這一條的話，改動一旦被 commit，
  「EQUIVALENT」就會變成「新版跟新版一樣」——一句永遠為真的話。

用法：
    .venv/bin/python ops/gain/replay/r449_probe_equivalence.py --base HEAD \
        --bank evalplus --seed g-r212-route-20260828 --n 179 --sample 0
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent      # ops/gain/replay
ROOT = HERE.parents[2]                              # repo 根
GAIN = HERE.parent                                  # ops/gain：舊版副本必須落在這裡
sys.path.insert(0, str(ROOT))

#: 舊版**不得**含有的字串。改動的入口就是這個 import，所以它同時是「這確實是舊版」
#: 的判準與「這支沒有在比較自己跟自己」的防呆。
NEW_MARKER = "suitegauge"


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--n", type=int, default=0,
                    help="載入幾題；0＝用 --sample*3（舊行為）")
    ap.add_argument("--sample", type=int, default=4,
                    help="量具驗證幾題；0＝全部載入的題目（＝CLI 的 --probe-sample 0）")
    ap.add_argument("--bank", default="evalplus")
    ap.add_argument("--seed", default="r449-equiv")
    a = ap.parse_args()

    old_src = subprocess.run(
        ["git", "show", f"{a.base}:ops/gain/gain_run.py"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout
    new_src = (GAIN / "gain_run.py").read_text(encoding="utf-8")
    if NEW_MARKER in old_src:
        raise SystemExit(
            f"拒絕比較：{a.base} 的 gain_run.py 已經含有「{NEW_MARKER}」——"
            "那是改動後的版本，這樣比等於拿新版跟新版比，永遠 EQUIVALENT。"
            "請把 --base 指到改動之前的 commit。")
    if NEW_MARKER not in new_src:
        raise SystemExit(
            f"拒絕比較：工作區的 gain_run.py 沒有「{NEW_MARKER}」——改動不在場，"
            "這支沒有東西可以證明。")
    print(f"old({a.base}) sha256={hashlib.sha256(old_src.encode()).hexdigest()[:16]} "
          f"new(worktree) sha256={hashlib.sha256(new_src.encode()).hexdigest()[:16]}")

    old_path = GAIN / "_r449_head_gain_run.py"
    old_path.write_text(old_src)
    try:
        new = _load(GAIN / "gain_run.py", "_r449_new_gain_run")
        old = _load(old_path, "_r449_old_gain_run")
        n_tasks = a.n or max(1, a.sample * 3)
        tasks = new.load_tasks(a.bank, a.seed, n_tasks)
        sample = len(tasks) if a.sample == 0 else a.sample
        r_new = new.probe_instrument(tasks, lambda d: None, sample=sample, bank=a.bank)
        r_old = old.probe_instrument(tasks, lambda d: None, sample=sample, bank=a.bank)
    finally:
        old_path.unlink(missing_ok=True)

    same = json.dumps(r_old, sort_keys=True) == json.dumps(r_new, sort_keys=True)
    print(f"base={a.base} bank={a.bank} seed={a.seed} tasks={len(tasks)} "
          f"sample={sample} n={r_new['n']} visible_n={r_new['visible_n']}")
    for tag, r in (("old", r_old), ("new", r_new)):
        print(f"  {tag}: 參考解通過 {r['ref_pass']}/{r['n']}　"
              f"壞解被擋 {r['broken_rejected']}/{r['n']}　"
              f"可見參考解通過 {r['visible_ref_pass']}/{r['visible_n']}　"
              f"可見樁被擋 {r['visible_stub_rejected']}/{r['visible_n']}")
    if same:
        print(f"EQUIVALENT (逐鍵相同；比對了 {len(set(r_old) | set(r_new))} 個鍵，"
              f"含 detail/visible_detail 逐題欄位)")
        return 0
    for k in sorted(set(r_old) | set(r_new)):
        if json.dumps(r_old.get(k), sort_keys=True) != json.dumps(r_new.get(k), sort_keys=True):
            print(f"  DIFF {k}:\n    old={r_old.get(k)}\n    new={r_new.get(k)}")
    print("NOT EQUIVALENT")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
