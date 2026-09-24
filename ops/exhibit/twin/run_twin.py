"""twin/run_twin — 把一位居民的一天真跑出來：一格 ＝ **兩次** `vacant run`（ON／OFF）。

## 這支在架構裡承重什麼

展件的主張是「分身做的每一件事都留下可驗的收據」。那句話只有在**每一格都真的
被 `vacant run` 包過**時才成立。本支就是產生那些格的驅動器：

  一位居民 × N 題（`ops/gain/r535/bank/`，現成的，不造新題）
    → 每題兩個工作區、**一個** run-dir（兩臂的落點靠 `ARM` 後綴分開）
    → `vacant_network.vrun.launcher.run(...)` 跑兩次（**沒有第二把尺**，就是那一支）
    → ON：`receipts_RUN-ON.ndjson` ＋ `run_RUN-ON.json` ＋ `visible_RUN-ON*.json`
    → OFF：`run_RUN-OFF.json` ＋ `wire_RUN-OFF/`（**沒有收據、沒有驗收**）

它**不改** `vacant_network/vrun/` 一個字；它只是那支的呼叫端。

## 為什麼 OFF 臂非跑不可（2026-09-19）

展場的主視覺是一組反事實對照：**同一題、關掉這一層會怎樣**。
在此之前展件只有 ON 臂，電視卻照樣印「同題關掉這層：也擋下」——
**替一個沒跑過的反事實作證**（`decisions/DECISION_20260919_TWIN_V2_FIDELITY.md` A4）。
把模擬講成證明是鐵律 5 的展場版本，所以那句話只有兩種下場：
不准說，或者**把它真的跑出來**。本支選後者。

OFF ＝ `vacant_on=False`：proxy 只做 tee（wire 照樣逐字落盤，`requests_seen`
照樣算），**不驗收、不簽收據、不拒交**，`stop_reason` 恆為 `ungated`、
`accepted` 恆為 `None`。那正是「沒有這一層」的字面意思：
東西就這樣交出去了，沒有人量過。

## 事後稽核（`postaudit_RUN-OFF.json`）：**是誰、在什麼時候量的**要寫在資料上

OFF 那一份交付到底過不過，`vacant run --vacant 0` **答不出來**——它當場沒量。
但展場需要這個數字，否則觀眾只看到兩份長得差不多的程式碼。
⇒ 跑完之後，用**同一把尺**（同一份 `tests_visible`）在 OFF 的凍結快照上再跑一次，
落成 `postaudit_RUN-OFF.json`，欄位 `when="after_the_run"`、
`is_verdict=false`、`signed=false`。

⚠ **這不是裁決**。它沒有進收據鏈、沒有簽章、agent 當時也不知道它會發生。
把它畫成 OFF 臂的裁決，就是把「沒有這一層」演成「這一層在另一邊也跑了」——
那會把 OFF 臂的意義整個弄反。資料上分得開，頁面才有機會說對。

給了 `--events L.jsonl` 時，量完的當下另外在 `L.sidecar.jsonl` 追加一筆旁註
（`twin.sidecar/1`，`sidecar.py`），綁那一跑的 `run_id`＋`ws_end_sha256`——電視的
`postaudit` 只從這裡來。**不寫進 lifecycle**：那一份只放 Vacant 當場觀察到的事
（2026-09-24 人類裁決「分身側自己記一份補回」）。

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
   （`vacant_network/suitegauge.py` 的同一條）：擋得住已知壞解 ≠ 涵蓋真需求。
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
from vacant_network.vrun import launcher  # noqa: E402

BANK = REPO / "ops" / "gain" / "r535" / "bank"

#: 一格要跑哪一題、用哪一份題面。`explicit=True` ⇒ 介面寫明（PC 臂）＝交付格候選。
CellPlan = tuple[str, bool]

#: 每位居民 6 格，其中 3 格扣住介面（拒交候選）、3 格寫明（交付候選）。
#: 題目取自 S1，因為 S1 的「扣住介面」正是展場要讓觀眾看見的那件事。
#:
#: 2026-09-19 換過兩次，判準都是**展場判準**（觀眾走到展場前面時有沒有差別），
#: 不是題目難度。兩條規則：
#:
#: 1. **需求一句話講得完**（加起來和乘起來／秒數變時鐘／分變成 $3.05／姓名縮寫／
#:    是不是回文／第幾名的英文字尾／百分比／某年某月幾天／色碼拆成 r,g,b）。
#:    `s1_02_span`／`s1_03_nwords` 要先解釋什麼叫 span、什麼算一個 word 才聽得懂，
#:    換掉了。
#: 2. **全部取自 S1**，因為 S1 的坑是「客戶要的那個函式名字沒寫在需求裡」，
#:    而那正是展場要演的那件事。S2 的坑是**行為**被扣住（`TASK.md` 裡已經有
#:    函式名），那是另一個故事，混進來會讓「扣住／寫明」這一組對照失焦。
#:
#: 為什麼是 9 題而不是 3 題：手機當導播（觀眾自己點要看哪一格）是已拍板的方向，
#: 那條路吃的是**反事實對照的題目多樣性**，不是格數。3 題 × 3 居民＝18 格，
#: 但觀眾按三下就把不同的題目看完了，剩下的只是換一個代號在演同一題。
DEFAULT_TASKS = ("s1_01_addmul", "s1_12_hms", "s1_31_money",
                 "s1_05_initials", "s1_24_is_pal", "s1_30_ord_suffix",
                 "s1_32_pct", "s1_34_days_in", "s1_49_rgb")


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


#: 兩臂。**兩臂都真的跑**——OFF 不是推算出來的，見模組 docstring。
ARMS = ("ON", "OFF")


def _arm_workspace(out_root: pathlib.Path, cid: str, arm: str) -> pathlib.Path:
    """兩臂各自一個工作區，內容逐位元組相同（`ws_start_sha256` 會相等，那是可驗的）。

    不共用同一個目錄的理由很笨但很硬：ON 跑完工作區裡會多一個
    `VACANT_FEEDBACK.md`（`revise` 每次判定之後寫的）。共用 ⇒ OFF 的起點就不是
    起點了，而且它會**讀到 ON 的失敗原文**——那樣 OFF 就不是「沒有 Vacant」，
    是「有 Vacant，只是沒簽收據」。整個對照會反過來。
    """
    return out_root / "ws" / (cid if arm == "ON" else f"{cid}__off")


def run_arm(*, arm, resident, task_id, explicit, out_root, run_dir, argv,
            retry_arm, max_attempts, sandbox, timeout_s, test_timeout_s,
            events_path=None, declared_evidence="") -> dict:
    """跑一臂，回 `launcher.run` 的 summary。兩臂共用同一個 run-dir。

    共用 run-dir 是安全的：落盤檔名全部帶 `ARM`（`run_RUN-ON.json` ／
    `run_RUN-OFF.json`、`_frozen_RUN-ON*` ／ `_frozen_RUN-OFF`、
    `wire_RUN-ON` ／ `wire_RUN-OFF`），`rows.jsonl` 一臂一列。
    """
    cid = cell_id(resident, task_id, explicit)
    ws = _arm_workspace(out_root, cid, arm)
    build_workspace(ws, task_id, explicit=explicit)
    suite = BANK / task_id / "tests_visible"
    task_text = (ws / "TASK.md").read_text(encoding="utf-8")
    real_argv = [a.replace("{TASK}", task_text) for a in argv]
    return launcher.run(
        real_argv, workspace=ws, run_dir=run_dir, suite_dir=suite,
        # ⚠ 這一行就是實驗處理本身。OFF ＝ 純 tee：不驗收、不簽收據、不拒交。
        vacant_on=(arm == "ON"),
        task_id=f"{task_id}:{'pc' if explicit else 'held'}",
        sandbox_name=sandbox,
        # OFF 臂**不能**有重試臂：沒有裁決可以拿來決定要不要再跑一次
        # （launcher 會直接 SystemExit）。那不是我們讓它少跑，是那一臂
        # 定義上就沒有那個東西——「沒有 Vacant」本來就沒有閘門可以觸發重試。
        retry_arm=retry_arm if arm == "ON" else "none",
        max_attempts=max_attempts if arm == "ON" else None,
        timeout_s=timeout_s, test_timeout_s=test_timeout_s,
        # ── 活模式：跑的當下就把事件寫出去（`live_events.py` 把它轉成電視的格式）──
        #   `caller` 是**我們**的標籤（哪一格、哪位居民、題面），Vacant 不驗它；
        #   證據等級照樣要等 `run_ended.requests_seen` 才推得出來（宣告蓋不過資料）。
        events_path=events_path,
        events_caller={"cell_id": cid, "resident": resident.codename,
                       "task_id": task_id,
                       "stratum": "pc" if explicit else "held",
                       "prompt": task_text,
                       "declared_evidence": declared_evidence or ""},
    )


def postaudit_off(run_dir: pathlib.Path, task_id: str, *, sandbox: str,
                  test_timeout_s: float) -> dict | None:
    """**事後**用同一把尺量 OFF 交出來的那一份。回 `None` ＝ 沒有東西可以量。

    ⚠ **這不是裁決。** `vacant run --vacant 0` 當場沒量，而且 agent 當時不知道
      這件事會發生。所以結果帶三個旗標：`when="after_the_run"`、
      `is_verdict=false`、`signed=false`。少了它們，這份資料與 ON 臂的裁決
      在形狀上就分不開，頁面遲早會把它畫成「OFF 也被擋下」——
      而那正是這一輪要修掉的那句話（忠實度對照表 A4）。

    ⚠ 只跑 `tests_visible`。隱藏測資一個 byte 都不碰（V/GT 紅線）。
    """
    from vacant_network.vrun import acceptance
    from vacant_network.vrun.sandbox import make_sandbox
    frozen = run_dir / "_frozen_RUN-OFF"
    if not frozen.is_dir():
        return None
    suite = BANK / task_id / "tests_visible"
    sb, backend = make_sandbox(sandbox, workdir=run_dir)
    result = acceptance.run_suite(
        sb, frozen, suite, suite="visible", task_id=f"{task_id}:postaudit-off",
        verify_root=run_dir / "_postaudit_verify", timeout_s=test_timeout_s)
    out = {
        "when": "after_the_run",
        "is_verdict": False,
        "signed": False,
        "ruler": "vacant_network/vrun/acceptance.py::run_suite(suite='visible')"
                 "——與 ON 臂同一把尺、同一份 tests_visible",
        "note": "OFF 臂當場沒有量過任何東西。這個判定是事後補的，"
                "沒有進收據鏈，也沒有影響那一跑的任何一個位元。",
        "sandbox": backend.get("backend"),
        **result,
    }
    (run_dir / "postaudit_RUN-OFF.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def write_postaudit_sidecar(events_path, pa: dict, *, cell_id: str,
                            summary: dict) -> dict:
    """事後稽核**完成的當下**寫一筆旁註（`twin.sidecar/1`），給電視的 `postaudit` 用。

    ⚠ 寫進 `sidecar.sidecar_path(events_path)`（`X.jsonl` 旁邊的 `X.sidecar.jsonl`），
      **不寫進** lifecycle 那一個檔：那一份是 Vacant 當場觀察到的，這一份是分身事後
      補量的——人類裁決（2026-09-24）「分身側自己記一份補回」，不准進 lifecycle 契約。
      為什麼分檔寫在 `sidecar.py` 的 docstring。

    綁定：`run_id`＝OFF 那一跑的 lifecycle `run_id`（`summary["lifecycle"]`）、
    `ws_end_sha256`＝那一跑的凍結樹。**寫不進去不改變任何結果**，只回報在
    `twin_cell.json` 的 `arms.OFF.sidecar` 上（不可以安靜）。
    """
    from ops.exhibit.twin import sidecar as sidecarlib
    run_id = (summary.get("lifecycle") or {}).get("run_id")
    path = sidecarlib.sidecar_path(events_path)
    if not run_id:
        return {"written": False, "error": "這一跑沒有 lifecycle run_id，旁註綁不上任何一跑"}
    row = sidecarlib.postaudit_row(pa, cell_id=cell_id, run_id=run_id,
                                   ws_end_sha256=summary.get("ws_end_sha256"))
    err = sidecarlib.append(path, row)
    if err:
        print(f"⚠ 旁註寫不進 {path.name}：{err}（那一跑的結果不受影響）",
              file=sys.stderr)
    return {"written": err is None, "error": err, "file": path.name}


def run_cell(*, resident, task_id, explicit, out_root, argv, upstream, model,
             retry_arm, max_attempts, sandbox, timeout_s, test_timeout_s,
             fixture, evidence, arms=ARMS, events_path=None) -> dict:
    cid = cell_id(resident, task_id, explicit)
    run_dir = out_root / "runs" / cid
    run_dir.mkdir(parents=True, exist_ok=True)

    env_before = dict(os.environ)
    if upstream:
        os.environ["VACANT_RUN_UPSTREAM_OPENAI"] = upstream
    if model:
        os.environ["VACANT_AGENT_MODEL"] = model
    if fixture:
        os.environ["TWIN_FIXTURE_SOURCE"] = str(
            fixture_source(task_id, explicit=explicit))
    per_arm: dict[str, dict] = {}
    try:
        for arm in arms:
            summary = run_arm(
                arm=arm, resident=resident, task_id=task_id, explicit=explicit,
                out_root=out_root, run_dir=run_dir, argv=argv,
                retry_arm=retry_arm, max_attempts=max_attempts,
                sandbox=sandbox, timeout_s=timeout_s,
                test_timeout_s=test_timeout_s,
                events_path=events_path, declared_evidence=evidence)
            per_arm[arm] = {
                "exit_code": launcher.exit_code(summary),
                "requests_seen": summary.get("requests_seen"),
                "stop_reason": summary.get("stop_reason"),
                # 鐵律 3：「沒量到」≠「量到 0」。跑掛的格子要標記，不可當成失敗格。
                "infra_void": summary.get("infra_void"),
                "attempts_used": summary.get("attempts_used"),
            }
            if arm == "OFF" and not summary.get("infra_void"):
                pa = postaudit_off(run_dir, task_id, sandbox=sandbox,
                                   test_timeout_s=test_timeout_s)
                per_arm[arm]["postaudit_all_pass"] = (
                    None if pa is None else bool(pa.get("all_pass")))
                if pa is not None and events_path:
                    per_arm[arm]["sidecar"] = write_postaudit_sidecar(
                        events_path, pa, cell_id=cid, summary=summary)
    finally:
        os.environ.clear()
        os.environ.update(env_before)

    meta = {
        "v": 2,
        "cell_id": cid,
        "resident": resident.codename,
        "task_id": task_id,
        "explicit": explicit,
        "run_dir": str(run_dir.relative_to(REPO)) if run_dir.is_relative_to(REPO)
                   else str(run_dir),
        # 頂層 `exit_code` 仍然是 **ON 臂**的（V0 起的欄位形狀，`pack.py` 讀它）。
        # OFF 臂沒有裁決，它的退出碼是 agent 自己的，兩者不可比。
        "exit_code": per_arm.get("ON", {}).get("exit_code"),
        "arms": per_arm,
        # 宣告的上游。**它證明不了任何事**——證據是 run summary 的 requests_seen
        # 與 wire bytes 裡的 model 欄位。這裡記下來只是為了事後對帳。
        "declared_upstream": upstream or "",
        "declared_model": model or "",
        "declared_evidence": evidence or "",
        # 後端是哪一台哪一版：1003（LM Studio 0.4.24）把同一份 gguf 跑成 thinking
        # 模式、1004（0.4.17）不是 ⇒ 兩台的數字**不可混講**。落盤才講得清楚。
        "declared_backend": os.environ.get("TWIN_BACKEND_NOTE", ""),
        "argv": list(argv),
        "built_ms": int(time.time() * 1000),
    }
    (run_dir / "twin_cell.json").write_text(
        json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    return meta


def merge_index(out_root: pathlib.Path) -> dict:
    """把每一格自己落下的 `twin_cell.json` 收成 `twin_index.json`。

    為什麼不是「driver 跑完自己寫名單」：四條流並行時誰都不知道全部跑完了沒，
    而一條流中途掛掉也不該讓整批索引消失。索引是**掃當下的樹**掃出來的，
    不是某一條流記得的清單。
    """
    cells = [json.loads(p.read_text(encoding="utf-8"))
             for p in sorted(out_root.glob("runs/*/twin_cell.json"))]
    idx = {"v": 2, "cells": cells}
    (out_root / "twin_index.json").write_text(
        json.dumps(idx, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    return idx


def main(argv_in=None) -> int:
    ap = argparse.ArgumentParser(description="跑一位／多位居民的一天，一格兩個 vacant run")
    ap.add_argument("--out", required=True, help="落點根目錄（會長出 ws/ 與 runs/）")
    ap.add_argument("--fixture", action="store_true",
                    help="用內建的零模型假 agent（證據等級只會是 L-none）")
    ap.add_argument("--residents", type=int, default=3, help="跑幾位居民（預設 3）")
    ap.add_argument("--tasks", default=",".join(DEFAULT_TASKS),
                    help="逗號分隔的 bank task_id")
    ap.add_argument("--arms", default=",".join(ARMS),
                    help="要跑哪幾臂（預設 ON,OFF）。**兩臂都跑才有反事實對照**")
    ap.add_argument("--shard", default=None, metavar="K:N",
                    help="只跑 `位置 %% N == K` 的格（並行用；位置是固定格序裡的位置）")
    ap.add_argument("--upstream", default=None, help="真模型端點（寫進 twin_cell.json 對帳用）")
    ap.add_argument("--model", default=None, help="模型 id")
    ap.add_argument("--evidence", choices=["L-real", "L-fake"], default=None,
                    help="這一批的上游是真模型（L-real）還是假上游（L-fake）。"
                         "宣告蓋不過資料：requests_seen==0 一律落成 L-none")
    ap.add_argument("--retry", default="none", help="launcher 的 --retry（只作用在 ON 臂）")
    ap.add_argument("--max-attempts", type=int, default=None)
    ap.add_argument("--sandbox", default="auto")
    ap.add_argument("--timeout", type=float, default=None, help="單次 agent 的牆鐘上限")
    ap.add_argument("--test-timeout", type=float, default=30.0)
    ap.add_argument("--events", default=None,
                    help="跑的當下把 vacant.lifecycle 事件逐行寫到這個 JSONL；"
                         "`live_events.py --follow` 把它轉成電視吃的格式")
    ap.add_argument("--merge-only", action="store_true",
                    help="不跑任何東西，只把已落盤的 twin_cell.json 收成索引")
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="`--` 之後的整條 agent 命令；`{TASK}` 會被題面取代")
    a = ap.parse_args(argv_in)

    out_root = pathlib.Path(a.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    if a.merge_only:
        idx = merge_index(out_root)
        print("索引：%d 格 → %s" % (len(idx["cells"]),
                                    out_root / "twin_index.json"))
        return 0

    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
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
    arms = tuple(x.strip().upper() for x in a.arms.split(",") if x.strip())
    unknown = [x for x in arms if x not in ARMS]
    if unknown:
        raise SystemExit(f"不認得的臂：{unknown}（只有 {ARMS}）")

    residents = rosterlib.default_roster()[:a.residents]
    #: 整批的格序是**固定**的（居民 × 題 × 兩份題面）。分片用的是這個序的位置
    #: ⇒ N 條流合起來剛好是全集，而且每條流拿到的題目與題面分佈都一樣。
    plan = [(r, t, e) for r in residents for (t, e) in plan_for(r, tasks)]
    if a.shard:
        k, n = (int(x) for x in a.shard.split(":"))
        plan = [c for i, c in enumerate(plan) if i % n == k]

    metas = []
    for resident, task_id, explicit in plan:
        m = run_cell(resident=resident, task_id=task_id, explicit=explicit,
                     out_root=out_root, argv=cmd, upstream=a.upstream,
                     model=a.model, retry_arm=a.retry,
                     max_attempts=a.max_attempts, sandbox=a.sandbox,
                     timeout_s=a.timeout, test_timeout_s=a.test_timeout,
                     fixture=a.fixture, evidence=a.evidence, arms=arms,
                     events_path=a.events)
        metas.append(m)
        on, off = m["arms"].get("ON", {}), m["arms"].get("OFF", {})
        print("%-34s ON exit=%-4s %-4s | OFF 通數=%-4s 事後稽核=%s%s"
              % (m["cell_id"], on.get("exit_code"),
                 "拒交" if on.get("exit_code") == 20 else
                 "交付" if on.get("exit_code") == 0 else "作廢",
                 off.get("requests_seen"),
                 {True: "過", False: "沒過", None: "—"}.get(
                     off.get("postaudit_all_pass"), "—"),
                 "  ⚠infra_void" if (on.get("infra_void") or off.get("infra_void"))
                 else ""), flush=True)
    idx = merge_index(out_root)
    delivered = sum(1 for m in idx["cells"] if m.get("exit_code") == 0)
    refused = sum(1 for m in idx["cells"] if m.get("exit_code") == 20)
    void = len(idx["cells"]) - delivered - refused
    print("\n本流 %d 格；索引共 %d 格：交付 %d、拒交 %d、作廢 %d → %s"
          % (len(metas), len(idx["cells"]), delivered, refused, void,
             out_root / "twin_index.json"))
    if not delivered or not refused:
        print("⚠ 展件需要兩種格都有。缺一種就只證明了閘門的一半。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
