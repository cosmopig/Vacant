"""twin/run_twin — 把一位居民的一天真跑出來：一格 ＝ 一次 `vacant run`。

## 這支在架構裡承重什麼

展件的主張是「分身做的每一件事都留下可驗的收據」。那句話只有在**每一格都真的
被 `vacant run` 包過**時才成立。本支就是產生那些格的驅動器：

  一位居民 × N 題（`ops/gain/r535/bank/`，現成的，不造新題）
    → 每題一個工作區、一個 run-dir
    → `vacant.vrun.launcher.run(...)`（**沒有第二把尺**，就是那一支）
    → `receipts_RUN-ON.ndjson` ＋ `run_RUN-ON.json` ＋ `visible_RUN-ON.json`

它**不改** `vacant/vrun/` 一個字；它只是那支的呼叫端。

## 兩種模式，同一條程式路徑

| 模式 | argv | requests_seen | 證據等級 |
|---|---|---|---|
| `--fixture` | 內建的一支假 agent（寫檔就結束，不呼叫模型） | 0 | **L-none** |
| `-- <真 agent 命令>` | 你給什麼就跑什麼（例如 pi 的 wrapper） | >0 才算數 | L-real／L-fake，由上游決定 |

兩種模式跑的是**同一個** `launcher.run`。證據等級不是這支宣稱的，是
`twin/pack.py` 從落盤資料推出來的（`requests_seen == 0` 就只能是 L-none，
這條是 fail-closed，宣告蓋不過去）。

## 拒交格怎麼保證有

`ops/gain/r535/bank_manifest.json` 的 S1 分層寫著
`expected_first_attempt_visible_fail >= 0.8`——**拒交格是多數，交付格才是稀有的**。
所以：

  · 拒交格 ⇒ 用 S1 的 `TASK.md`（介面被扣住），預期大多數直接 `visible_fail`
  · 交付格 ⇒ 用同一題的 `TASK_explicit.md`（PC 臂，介面寫明）＋ `--retry revise`

兩者用**同一題**，所以展場那兩格的差別只有一個：它知不知道客戶要的介面長怎樣。
這比「換一題比較簡單的」誠實得多。

## 誠實邊界

1. 這支保證的是「每一格都被量過」，**不保證量得對**。驗收是單邊保證
   （`vacant/suitegauge.py` 的同一條）：擋得住已知壞解 ≠ 涵蓋真需求。
2. `--fixture` 的格子裡**沒有模型**。它驗的是閘門與收據，不是 agent 能力。
   把 fixture 格講成「分身做的事」就是把模擬講成證明（鐵律 5）。
3. 這支不決定展件上寫什麼字。標籤由 `pack.py` 從資料推、由頁面印出來。

用法：
    # 機制自檢（零模型、零網路）：三位居民各 2 格
    python3 ops/exhibit/twin/run_twin.py --fixture --out runs/twin_fixture

    # 真跑（等人類通知；1003 吞吐 4 串封頂）
    python3 ops/exhibit/twin/run_twin.py --out runs/twin_20260919 \\
        --upstream http://100.x.x.x:1234 --model gemma-4-12b-it-qat \\
        -- ops/vacantrun/wrap_agent.sh pi "{TASK}"
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sys
import time

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import roster as rosterlib  # noqa: E402
from vacant.vrun import launcher  # noqa: E402

BANK = REPO / "ops" / "gain" / "r535" / "bank"

#: 一格要跑哪一題、用哪一份題面。`explicit=True` ⇒ 介面寫明（PC 臂）＝交付格候選。
CellPlan = tuple[str, bool]

#: v1 的排程：每位居民 6 格，其中 3 格扣住介面（拒交候選）、3 格寫明（交付候選）。
#: 題目取自 S1，因為 S1 的「扣住介面」正是展場要讓觀眾看見的那件事。
DEFAULT_TASKS = ("s1_01_addmul", "s1_02_span", "s1_03_nwords")


def plan_for(resident: rosterlib.Resident, tasks: tuple[str, ...]) -> list[CellPlan]:
    """一位居民的一天：每題兩格——扣住介面一格、寫明介面一格。

    順序刻意是「先扣住、後寫明」：展場的敘事是「它先被擋下來，補上缺的資訊才過」，
    反過來排會變成「它本來就會，只是第二次故意做錯」。
    """
    out: list[CellPlan] = []
    for t in tasks:
        out.append((t, False))
        out.append((t, True))
    return out


def cell_id(resident: rosterlib.Resident, task_id: str, explicit: bool) -> str:
    return f"{resident.codename}__{task_id}__{'pc' if explicit else 'held'}"


FIXTURE_AGENT = '''\
"""twin fixture agent —— 零模型、零網路的**腳本化** agent。

它把 `TWIN_FIXTURE_SOURCE` 指到的那一份檔案寫成 `solution.py`，就結束。
那份檔案由 `run_twin.py` 事前從 bank 的 `reference/` 挑好：介面寫明的格挑
`solution.py`（會過），介面被扣住的格挑 `bad_c.py`（名字猜錯，會被擋）。

它存在的理由是**讓收據鏈與閘門在沒有機時的時候也被真的跑一次**。
它不是 agent 的模擬，也不代表任何模型的能力：`requests_seen` 會是 0，
所以 `pack.py` 只會把這種格標成 L-none，頁面上也只會這樣寫。
"""
import os
import pathlib

src = pathlib.Path(os.environ["TWIN_FIXTURE_SOURCE"])
pathlib.Path("solution.py").write_text(src.read_text(encoding="utf-8"),
                                       encoding="utf-8")
'''


def build_workspace(ws: pathlib.Path, task_id: str, *, explicit: bool) -> None:
    """工作區只放題面。驗收套件**留在 bank 裡**（工作區外）——那是 launcher 的硬擋門。"""
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    src = BANK / task_id / ("TASK_explicit.md" if explicit else "TASK.md")
    shutil.copyfile(src, ws / "TASK.md")


def fixture_source(task_id: str, *, explicit: bool) -> pathlib.Path:
    """腳本化 agent 這一格要交出來的東西（從 bank 的 reference/ 拿，不另外寫）。

    `explicit=True` ⇒ `reference/solution.py`（交付格）；
    `explicit=False` ⇒ `reference/bad_c.py`（wrong name ⇒ 驗收擋下來，拒交格）。
    用 bank 自己的樁而不是現寫，理由是 `gauge_bank.py` 已經證過這四份樁的
    通過／被擋行為——現寫一份等於再開一把沒被量過的尺。
    """
    return BANK / task_id / "reference" / ("solution.py" if explicit else "bad_c.py")


def run_cell(*, resident, task_id, explicit, out_root, argv, upstream, model,
             retry_arm, max_attempts, sandbox, timeout_s, fixture, evidence) -> dict:
    cid = cell_id(resident, task_id, explicit)
    ws = out_root / "ws" / cid
    run_dir = out_root / "runs" / cid
    build_workspace(ws, task_id, explicit=explicit)
    suite = BANK / task_id / "tests_visible"

    env_before = dict(os.environ)
    if upstream:
        os.environ["VACANT_RUN_UPSTREAM_OPENAI"] = upstream
    if model:
        os.environ["VACANT_AGENT_MODEL"] = model
    if fixture:
        os.environ["TWIN_FIXTURE_SOURCE"] = str(
            fixture_source(task_id, explicit=explicit))
    try:
        real_argv = [a.replace("{TASK}", (ws / "TASK.md").read_text(encoding="utf-8"))
                     for a in argv]
        summary = launcher.run(
            real_argv, workspace=ws, run_dir=run_dir, suite_dir=suite,
            vacant_on=True, task_id=f"{task_id}:{'pc' if explicit else 'held'}",
            sandbox_name=sandbox, retry_arm=retry_arm, max_attempts=max_attempts,
            timeout_s=timeout_s,
        )
    finally:
        os.environ.clear()
        os.environ.update(env_before)

    rc = launcher.exit_code(summary)
    meta = {
        "v": 1,
        "cell_id": cid,
        "resident": resident.codename,
        "task_id": task_id,
        "explicit": explicit,
        "run_dir": str(run_dir.relative_to(REPO)) if run_dir.is_relative_to(REPO)
                   else str(run_dir),
        "exit_code": rc,
        # 宣告的上游。**它證明不了任何事**——證據是 run summary 的 requests_seen
        # 與 wire bytes 裡的 model 欄位。這裡記下來只是為了事後對帳。
        "declared_upstream": upstream or "",
        "declared_model": model or "",
        "declared_evidence": evidence or "",
        "argv": list(argv),
        "built_ms": int(time.time() * 1000),
    }
    (run_dir / "twin_cell.json").write_text(
        json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    return meta


def main(argv_in=None) -> int:
    ap = argparse.ArgumentParser(description="跑一位／多位居民的一天，一格一個 vacant run")
    ap.add_argument("--out", required=True, help="落點根目錄（會長出 ws/ 與 runs/）")
    ap.add_argument("--fixture", action="store_true",
                    help="用內建的零模型假 agent（證據等級只會是 L-none）")
    ap.add_argument("--residents", type=int, default=3, help="跑幾位居民（預設 3）")
    ap.add_argument("--tasks", default=",".join(DEFAULT_TASKS),
                    help="逗號分隔的 bank task_id")
    ap.add_argument("--upstream", default=None, help="真模型端點（寫進 twin_cell.json 對帳用）")
    ap.add_argument("--model", default=None, help="模型 id")
    ap.add_argument("--evidence", choices=["L-real", "L-fake"], default=None,
                    help="這一批的上游是真模型（L-real）還是假上游（L-fake）。"
                         "宣告蓋不過資料：requests_seen==0 一律落成 L-none")
    ap.add_argument("--retry", default="none", help="launcher 的 --retry")
    ap.add_argument("--max-attempts", type=int, default=None)
    ap.add_argument("--sandbox", default="auto")
    ap.add_argument("--timeout", type=float, default=None)
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="`--` 之後的整條 agent 命令；`{TASK}` 會被題面取代")
    a = ap.parse_args(argv_in)

    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    out_root = pathlib.Path(a.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    if a.fixture:
        if cmd:
            raise SystemExit("--fixture 與自訂命令不能同時給：兩者會產生不同等級的證據")
        agent_py = out_root / "fixture_agent.py"
        agent_py.write_text(FIXTURE_AGENT, encoding="utf-8")
        cmd = [sys.executable, str(agent_py)]
    if not cmd:
        raise SystemExit("要嘛 --fixture，要嘛在 `--` 之後給一條真 agent 命令。停。")

    tasks = tuple(t.strip() for t in a.tasks.split(",") if t.strip())
    missing = [t for t in tasks if not (BANK / t / "tests_visible").is_dir()]
    if missing:
        raise SystemExit(f"bank 裡沒有這些題：{missing}")

    residents = rosterlib.default_roster()[:a.residents]
    metas = []
    for r in residents:
        for task_id, explicit in plan_for(r, tasks):
            m = run_cell(resident=r, task_id=task_id, explicit=explicit,
                         out_root=out_root, argv=cmd, upstream=a.upstream,
                         model=a.model, retry_arm=a.retry,
                         max_attempts=a.max_attempts, sandbox=a.sandbox,
                         timeout_s=a.timeout, fixture=a.fixture,
                         evidence=a.evidence)
            metas.append(m)
            print("%-34s exit=%-3d %s" % (m["cell_id"], m["exit_code"],
                                          "拒交" if m["exit_code"] == 20 else
                                          "交付" if m["exit_code"] == 0 else "作廢"))
    idx = out_root / "twin_index.json"
    idx.write_text(json.dumps({"v": 1, "cells": metas}, ensure_ascii=False,
                              sort_keys=True, indent=2) + "\n", encoding="utf-8")
    delivered = sum(1 for m in metas if m["exit_code"] == 0)
    refused = sum(1 for m in metas if m["exit_code"] == 20)
    print("\n%d 格：交付 %d、拒交 %d、作廢 %d → %s"
          % (len(metas), delivered, refused, len(metas) - delivered - refused, idx))
    if not delivered or not refused:
        print("⚠ 展件需要兩種格都有。缺一種就只證明了閘門的一半。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
