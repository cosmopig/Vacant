#!/usr/bin/env python3
"""R532 發射前擋門 E-16：seed 授權集合掃描（DECISION_20260917_R532 §二-3／§五-4）。

這支在架構裡承重什麼
────────────────────
R532 的整個主張是「**只換了 worker 模型**，題組／題序／分塊／persona 指派
與 12B 那輪逐格相同」。題序與分塊由 `--seed` 決定（`gain_run.load_tasks`
的 `loader.iter_tasks(seed)` 前綴切片），所以「沿用 seed」不是行政手續，
而是**那句主張的前提**。DECISION §二-3 把四顆 seed 的授權重用集合
（`seed -> 用過它的 run 目錄`）逐字釘在檔案裡；本腳本掃 repo 內所有
`runs/*/summary.json`，把**實際**集合算出來，與那四行**逐字比對**。

不相等代表兩種情況之一，兩種都不准發射：
  1. 多出來的 run —— 有人在 DECISION 凍結之後又用了同一顆 seed，
     「與 12B 那輪逐格相同」的對照基準已經不是當初點名的那一組；
  2. 少掉的 run —— 授權行引用了不存在／已被搬走的 run，
     §五-5（E-14）要拿來逐格重放的對照物根本不在。
兩者都回報 `abort_seed_set_mismatch`（§五-4）。

⚠ 判定基準（§五-4 明文）：**本機（Mac）掃過不算數**，
vacant-dev 上的集合才是閘門讀的那一個。本腳本兩台都可跑，
回報時必須標明是哪一台。

零模型呼叫、唯讀；不修改任何既有程式碼。
用法：
    python3 ops/gain/r532/check_seed_authorization.py [--decision <path>] [--repo <path>]
退出碼：0 = E16 PASS，1 = E16 FAIL。
"""
from __future__ import annotations

import argparse
import glob
import json
import pathlib
import re
import socket
import sys

DEFAULT_DECISION = "DECISION_20260917_R532_STRONGER_MODEL_PREREG.md"
# §二-3 點名的四顆 seed；只有這四顆進判定，其餘 seed 只印出來當資訊。
JUDGED_SEEDS = ["g-r440-lcb2", "g-r529-lcb3", "g-r529-he", "g-r529-mbpp"]

_AUTH_RE = re.compile(r"^\s*SEED_AUTHORIZED_SET:\s*(\S+)\s*<-\s*(.+?)\s*$")


def parse_authorized(decision_path: pathlib.Path) -> dict[str, list[str]]:
    """從 DECISION §二-3 逐字讀出 `SEED_AUTHORIZED_SET:` 行。"""
    out: dict[str, list[str]] = {}
    for line in decision_path.read_text(encoding="utf-8").splitlines():
        m = _AUTH_RE.match(line)
        if not m:
            continue
        seed, rhs = m.group(1), m.group(2)
        runs = [x.strip() for x in rhs.split(",") if x.strip()]
        if seed in out:
            raise SystemExit(
                f"DECISION 裡 seed {seed} 有兩行 SEED_AUTHORIZED_SET —— "
                "授權集合不是單一真相，停。")
        out[seed] = runs
    return out


def scan_actual(repo: pathlib.Path) -> tuple[dict[str, set[str]], int, list[str]]:
    """掃 repo 內**所有** `runs/*/summary.json`，建出 seed -> run 目錄集合。"""
    actual: dict[str, set[str]] = {}
    paths = sorted(glob.glob(str(repo / "runs" / "*" / "summary.json")))
    broken: list[str] = []
    for p in paths:
        rel = pathlib.Path(p).relative_to(repo)
        run_dir = str(rel.parent)          # 例：runs/g_r529_mbpp_a1
        try:
            d = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        except Exception as e:             # 壞檔要報出來，不可安靜跳過
            broken.append(f"{run_dir}: {e}")
            continue
        seed = d.get("seed")
        if seed is None:
            broken.append(f"{run_dir}: summary.json 沒有 seed 欄位")
            continue
        actual.setdefault(str(seed), set()).add(run_dir)
    return actual, len(paths), broken


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decision", default=DEFAULT_DECISION)
    ap.add_argument("--repo", default=None,
                    help="repo 根目錄（預設＝本檔往上三層）")
    args = ap.parse_args()

    repo = (pathlib.Path(args.repo).resolve() if args.repo
            else pathlib.Path(__file__).resolve().parents[3])
    decision = pathlib.Path(args.decision)
    if not decision.is_absolute():
        decision = repo / decision
    if not decision.exists():
        raise SystemExit(f"找不到 DECISION：{decision}")

    print(f"── E-16 seed 授權集合掃描（DECISION §二-3／§五-4）")
    print(f"   主機　{socket.gethostname()}")
    print(f"   repo　{repo}")
    print(f"   決策　{decision}")

    authorized = parse_authorized(decision)
    actual, n_summaries, broken = scan_actual(repo)
    print(f"   掃到 {n_summaries} 個 runs/*/summary.json，"
          f"{len(actual)} 顆不同的 seed")
    for b in broken:
        print(f"   ⚠ 讀不動／缺欄位：{b}")

    missing_lines = [s for s in JUDGED_SEEDS if s not in authorized]
    if missing_lines:
        print("E16 FAIL: abort_seed_set_mismatch")
        for s in missing_lines:
            print(f"   DECISION 裡沒有 seed {s} 的 SEED_AUTHORIZED_SET 行")
        return 1

    ok = True
    for seed in JUDGED_SEEDS:
        auth = sorted(authorized[seed])
        act = sorted(actual.get(seed, set()))
        extra = [r for r in act if r not in set(auth)]      # 實際有、授權沒有
        absent = [r for r in auth if r not in set(act)]     # 授權有、實際沒有
        if not extra and not absent:
            print(f"   ✓ {seed}：{len(act)} 個 run，逐字相等")
            continue
        ok = False
        print(f"   ✗ {seed}：授權 {len(auth)} 個／實際 {len(act)} 個")
        for r in extra:
            print(f"       ＋多出來（實際有、DECISION 沒授權）：{r}")
        for r in absent:
            print(f"       －少掉了（DECISION 授權、實際掃不到）：{r}")

    others = sorted(set(actual) - set(JUDGED_SEEDS))
    if others:
        print("   （其餘 seed，僅供參考，不進判定）")
        for s in others:
            print(f"     · {s}：{len(actual[s])} 個 run")

    if ok:
        print("E16 PASS")
        return 0
    print("E16 FAIL: abort_seed_set_mismatch")
    return 1


if __name__ == "__main__":
    sys.exit(main())
