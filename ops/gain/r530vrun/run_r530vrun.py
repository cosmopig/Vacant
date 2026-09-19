#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""這支在架構裡承重什麼：把 **R530 的開放目標題庫**第一次放到 `vacant run` 的
收件口底下跑，量的是**收件口撐不撐得住重量級題庫**，不是任何效果量。

⚠⚠ **這不是預註冊實驗。** 判讀紀律逐字見 `README.md` 最上面那一節；
這裡再說一次最重要的那三條，因為會有人只讀程式不讀 README：

1. **不准做統計檢定。** 沒有預註冊 ⇒ 這 40 格的數字不是假說檢定的輸入。
2. **不准與 R535／R530 原始結果合併**，也不准寫「複製」「效果消失」「等價」。
3. 能說的只有描述性的那一句：**「在這 20 題上，X 是 a/b」**。

它要回答的三件事（都是工程問題不是科學主張）
--------------------------------------------
1. `vacant run` 的收件口在**重量級題庫**上撐不撐得住。R535 全是秒級微型題，
   那是舒適區；這裡的題目參考解 16–200 行、隱藏驗收 6–16 條。
2. `M7_file`（回饋文字有沒有進到第 ≥2 次嘗試的 wire）在更長更難的任務上
   **還是 ~0 嗎**。
3. `--test-timeout` 要多少才不會製造**假逾時**——那個數字由
   `probe_timeout.py` 先量，本支只**吃**它、逐格落盤，不自己猜。

設計（20 × 2 ＝ 40 格）
----------------------
| 臂 | 旗標 | 它承重什麼 |
|---|---|---|
| `RF` | `--retry revise --max-attempts 3 --feedback-into file` | 回饋走工作區檔案 |
| `RP` | `--retry revise --max-attempts 3 --feedback-into prompt` | 回饋走 argv 尾端 |

**20 題全跑**（挑題是一個選擇點，這一輪不開那個選擇點）。
agent ＝ **pi**（三個 L-real 裡最便宜、最熟的那個），模型
`gemma-4-12b-it-qat`、`reasoning_effort: "none"`。

工作區與 `--suite`（V/GT 紅線）
------------------------------
R530 的題目結構**與 R535 不同**：`tests_visible/` 是**工作區的一部分**
（`TASK_FORMAT.md` §八-5：可見驗收的輸入與期望值 worker 看得到、跑得到，
還附一支 `run_tests.sh` 讓他自己跑）。所以：

* 工作區 ＝ `ops/gain/r530/templates/<task_id>/` 逐檔複製（含 `tests_visible/`）。
* `--suite` ＝ **另一份凍結副本**，落在 `<out>/suites/<task_id>/tests_visible/`，
  **在工作區外**。agent 改得到的驗收不是驗收；他改工作區裡那一份不影響計分，
  而那正是這個設計要的（他可以拿它自我檢查，但騙不到閘門）。
  兩份的 sha256 一起落盤（`suite_sha256`／`ws_suite_sha256`），**不相等是觀測**
  （代表 agent 動過工作區裡那一份），不是錯誤。
* `hidden/` **一個位元組都不進工作區、也不進 `--suite`**——它只在事後計分
  （`score_r530vrun.py`），**不回饋**。

紀律（逐條對應人類指令）
------------------------
* `requests_seen == 0` ⇒ **`infra_void` 不是 0 分**（accepted 落 `null`），重試 ×4。
* **load 監看**：每 15 分鐘記一次 `uptime`；1 分鐘 load > `--load-pause`（預設 8）
  就**暫停派工**——不是砍 run（在跑的那一格不動它）。那台機器剛從 load 71 救回來。
* 牆鐘**印分佈不印均值**（`score_r530vrun.py` 的收官表）。
* 口徑用「可究責性」不用「信任」。

量具沿用
--------
`M7_file`／`M7_name`／`M7_ws`／`M7_ws_solution`／`F6`／`F3`／`suspect_timeout`
**直接 import `ops/gain/r535/run_r535.py` 的那幾支**（以路徑載入，不改它一個位元組）。
用同一把尺是為了「量測本身可比」，**不是**為了讓結果可以合併——結果不可以合併。

用法
----
    # 0) 先量逾時（這一步的產出是本輪最實用的東西）
    python3 ops/gain/r530vrun/probe_timeout.py --out $OUT/probe
    # 1) 發射（兩條流，shard 用計畫裡的列號）
    for i in 0 1; do
      python3 ops/gain/r530vrun/run_r530vrun.py --out $OUT --shard $i:2 \
        --stream s$i --pi-port 889$i --pi-bin $PI --test-timeout <量到的值> &
    done; wait
    # 2) 計分（零模型呼叫、可離線重跑）
    python3 ops/gain/r530vrun/score_r530vrun.py --out $OUT
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from vacant_network.vrun import wshash                            # noqa: E402

R530 = REPO / "ops" / "gain" / "r530"
BANK = R530 / "bank"
TEMPLATES = R530 / "templates"

#: 量具借用：**以路徑載入 `ops/gain/r535/run_r535.py`**（`ops/gain` 沒有
#: `__init__.py`，不能一般 import）。載入它只會執行模組層的常數與三個
#: `vacant_network.*` import，沒有副作用（2026-09-19 逐行確認過）。
#: ⚠ 借的是**尺**不是**結果**：R535 的數字與本輪的數字不可以合併。
_R535_PATH = REPO / "ops" / "gain" / "r535" / "run_r535.py"
_spec = importlib.util.spec_from_file_location("_r535_gauge", _R535_PATH)
assert _spec is not None and _spec.loader is not None
r535 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r535)

# ── 凍結常數 ──────────────────────────────────────────────────────────────

#: 兩臂。**唯一差異是 `--feedback-into`**；prompt 與工作區樣板逐字相同。
ARMS: dict[str, dict] = {
    "RF": {"flags": ["--retry", "revise", "--max-attempts", "3",
                     "--feedback-into", "file"],
           "placeholder": False,
           "why": "回饋走工作區的 VACANT_FEEDBACK.md（agent 可以不讀它）"},
    "RP": {"flags": ["--retry", "revise", "--max-attempts", "3",
                     "--feedback-into", "prompt"],
           "placeholder": True,
           "why": "回饋走 argv 尾端（一定出現在模型輸入裡，但看得到 ≠ 照做）"},
}
ARM_ORDER = ("RF", "RP")

#: pi 的 user 訊息。**兩臂逐字相同。**
#: 與 R535 的那一句不同，只因為這個題庫的樣板是 `goal.md` ＋ `contract.md`
#: 兩個檔而不是一個 `TASK.md`——那是題庫的形狀，不是實驗處理。
#: KS-1（鐵律 1）：沒有「你有責任／會被懲罰」類措辭。
PI_PROMPT = ("Read goal.md and contract.md and do what they say. "
             "Use your tools to write the files.")

FEEDBACK_PLACEHOLDER = "{VACANT_FEEDBACK}"
EXIT_ACCEPTED, EXIT_REFUSED, EXIT_INFRA_VOID = 0, 20, 22

#: 基建失敗重試次數（鐵律 3：retry×4）。
INFRA_RETRIES = 4

#: 推論模式的釘值（同 R535 的 NOTHINK 裁決；「不送」＝把模式交給後端版本決定）。
DEFAULT_REASONING_EFFORT = "none"
REASONING_CHOICES = ("none", "low", "medium", "high", "backend-default")

#: **load 門檻預設 8**（人類指令：超過 8 就暫停派工）。那台機器剛從 load 71
#: 救回來，所以這個值刻意比 R535 的 80 嚴格一個數量級。
DEFAULT_LOAD_PAUSE = 8.0
#: uptime 落盤的間隔（秒）＝**每 15 分鐘記一次**（人類指令）。
UPTIME_EVERY_S = 900.0

#: agent 逾時（秒）。重量級題庫 ⇒ 比 R535 寬。`agent_timed_out` 是**正常的
#: 嘗試結果不 void**（launcher 誠實邊界 7），逐次落盤。
DEFAULT_AGENT_TIMEOUT_S = 900.0


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def jsonl_append(path: pathlib.Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_dir(d: pathlib.Path) -> str:
    """目錄雜湊：`(相對路徑, 檔案 sha256)` 依路徑排序後再雜湊一次。

    ⚠ **排除 `wshash.EXCLUDED_DIRS`**（`__pycache__` 等）。2026-09-19 冒煙踩到：
    worker 真的跑了工作區裡那一份可見驗收 ⇒ 生出 `tests_visible/__pycache__/`
    ⇒ 不排除的話 `ws_suite_sha256 != suite_sha256`，而那一行的意思是
    「agent 動過驗收」。**一個會誤報的旗標比沒有旗標更糟。**
    `__pycache__` 本身是有用的觀測，另外記成 `ws_suite_pycache`。
    """
    h = hashlib.sha256()
    for p in sorted(d.rglob("*")):
        if not p.is_file():
            continue
        if any(part in wshash.EXCLUDED_DIRS for part in p.relative_to(d).parts):
            continue
        h.update(str(p.relative_to(d)).encode("utf-8"))
        h.update(b"\0")
        h.update(sha256_file(p).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def load1() -> float | None:
    try:
        return os.getloadavg()[0]
    except (OSError, AttributeError):
        return None


def uptime_line() -> str:
    try:
        return subprocess.run(["uptime"], capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except Exception:                                      # noqa: BLE001
        return ""


def task_ids() -> list[str]:
    return sorted(d.name for d in BANK.iterdir()
                  if d.is_dir() and d.name.startswith("ow_"))


def task_meta(task_id: str) -> dict:
    return json.loads((BANK / task_id / "meta.json").read_text(
        encoding="utf-8"))


# ── 計畫 ──────────────────────────────────────────────────────────────────

def plan_rows(tasks: list[str]) -> list[dict]:
    """同一題的兩格排在**相鄰兩列**，臂序按 `task_index mod 2` 輪轉。

    配上 `--shard k:2` ⇒ 兩條流同時在跑**同一題的兩個臂**，而且每條流兩個臂的
    量一樣。這樣後端任何漂移（重載、TTL、別的 agent 搶）都不會變成
    **臂與臂之間的時間混淆**。
    """
    rows: list[dict] = []
    for ti, task_id in enumerate(tasks):
        meta = task_meta(task_id)
        order = ARM_ORDER[ti % len(ARM_ORDER):] + ARM_ORDER[:ti % len(ARM_ORDER)]
        for ap, arm in enumerate(order):
            rows.append({
                "plan_index": len(rows),
                "cell": f"{task_id}__{arm}",
                "task_id": task_id, "arm": arm,
                "stratum": meta.get("stratum"),
                "visible_n": meta.get("visible_n"),
                "hidden_n": meta.get("hidden_n"),
                "ref_solution_lines": meta.get("ref_solution_lines"),
                "task_index": ti, "arm_pos": ap,
            })
    return rows


def freeze_suites(out: pathlib.Path, tasks: list[str]) -> dict:
    """把每一題的可見驗收複製到 `<out>/suites/<task>/tests_visible/`。

    **工作區外**——這是 `--suite` 的落點。工作區裡另有一份同樣位元組的副本
    （題庫的設計），兩份的 sha256 都落盤，事後看得出 agent 有沒有動過他那一份。
    """
    root = out / "suites"
    pinned: dict[str, dict] = {}
    for task_id in tasks:
        dst = root / task_id / "tests_visible"
        dst.mkdir(parents=True, exist_ok=True)
        src = TEMPLATES / task_id / "tests_visible"
        for p in sorted(src.iterdir()):
            if not p.is_file():
                continue
            # **內容相同就不要重寫**（2026-09-19 加寬到 4 串時發現的競爭）：
            # 後加入的流會再跑一次 `write_plan`，而**同時**可能有一個
            # launcher 正在把這一份驗收複製進它的 `_verify/`。覆寫同樣的位元組
            # 看起來無害，但中途被讀到就是一個截斷的檔案 ⇒ 那一格的
            # `driver_error` 會被讀成「模型寫壞了」。冪等就沒有這個窗口。
            target = dst / p.name
            if target.is_file() and sha256_file(target) == sha256_file(p):
                continue
            shutil.copy2(p, target)
        pinned[task_id] = {"suite_dir": str(dst), "sha256": sha256_dir(dst),
                           "files": sorted(p.name for p in dst.iterdir())}
    return pinned


def write_plan(out: pathlib.Path, tasks: list[str], args) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    rows = plan_rows(tasks)
    suites = freeze_suites(out, tasks)
    plan_path = out / "plan.jsonl"
    if not plan_path.exists():
        with open(plan_path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    manifest = {
        "generated": now_iso(),
        "not_preregistered": True,
        "reading_discipline": (
            "沒有預註冊 ⇒ 這些數字不可以當假說檢定；不准做統計檢定、"
            "不准與 R535／R530 原始結果合併、不准寫「複製」「效果消失」「等價」。"
            "能說的只有：在這 20 題上，X 是 a/b。"),
        "bank": str(BANK),
        "bank_sha256": sha256_dir(BANK),
        "templates_sha256": sha256_dir(TEMPLATES),
        "tasks": tasks, "cells_n": len(rows),
        "arms": {k: v["flags"] for k, v in ARMS.items()},
        "prompt": PI_PROMPT,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "test_timeout_s": args.test_timeout,
        "test_timeout_source": args.test_timeout_source,
        "agent_timeout_s": args.agent_timeout,
        "sandbox": args.sandbox,
        "load_pause": args.load_pause,
        "suites": suites,
    }
    mpath = out / "manifest.json"
    if not mpath.exists():
        mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    return json.loads(mpath.read_text(encoding="utf-8"))


def read_plan(out: pathlib.Path) -> list[dict]:
    path = out / "plan.jsonl"
    if not path.exists():
        raise SystemExit(f"沒有 {path}——先不帶 --shard 跑一次讓它建計畫。停。")
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()
            if s.strip()]


def materialise_ws(ws: pathlib.Path, task_id: str) -> list[str]:
    """把 `templates/<task_id>/` 逐檔複製進工作區（**含 `tests_visible/`**）。

    ⚠ 與 R535 的 `materialise_ws` 刻意不同：那裡 `tests_visible/` 不進工作區，
    因為 R535 的題庫設計是這樣；R530 的題庫設計是 worker 看得到、跑得到可見驗收
    （`TASK_FORMAT.md` §八-5），連 `run_tests.sh` 都附了。照題庫走。
    紅線沒有鬆：計分用的那一份在工作區外（`freeze_suites`）。
    """
    src = TEMPLATES / task_id
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(src, ws)
    return sorted(str(p.relative_to(ws)) for p in ws.rglob("*") if p.is_file())


class Driver:
    def __init__(self, args, manifest: dict):
        self.a = args
        self.manifest = manifest
        self.out = pathlib.Path(args.out).resolve()
        self.cells_dir = self.out / "cells"
        self.log = self.out / f"driver_{args.stream}.jsonl"
        self.upstream = r535.upstream_base(args.endpoint)
        self._stop = threading.Event()

    def ev(self, kind: str, **kw) -> None:
        jsonl_append(self.log, {"ts": now_iso(), "stream": self.a.stream,
                                "event": kind, **kw})

    def _uptime_thread(self) -> None:
        """**每 15 分鐘記一次 `uptime`**（人類指令；load 是派工決策的證據）。"""
        while not self._stop.wait(UPTIME_EVERY_S):
            self.ev("uptime", load1=load1(), uptime=uptime_line())

    def wait_for_load(self) -> None:
        """1 分鐘 load > 門檻就**暫停派工**——不是砍 run。"""
        while True:
            l1 = load1()
            if l1 is None or l1 <= self.a.load_pause:
                return
            self.ev("load_pause", load1=l1, threshold=self.a.load_pause,
                    uptime=uptime_line(), sleep_s=self.a.load_poll_s)
            print(f"[{self.a.stream}] load={l1:.2f} > {self.a.load_pause} "
                  f"⇒ 暫停派工 {self.a.load_poll_s}s", flush=True)
            if self.a.dry_run:
                return
            time.sleep(self.a.load_poll_s)

    def suite_dir(self, task_id: str) -> pathlib.Path:
        return self.out / "suites" / task_id / "tests_visible"

    def cell_argv(self, cell: pathlib.Path, task_id: str, arm: str) -> list[str]:
        spec = ARMS[arm]
        prompt = PI_PROMPT + (FEEDBACK_PLACEHOLDER if spec["placeholder"] else "")
        return [sys.executable, "-m", "vacant_network.vrun.launcher",
                "--workspace", str(cell / "ws"),
                "--run-dir", str(cell / "run"),
                "--suite", str(self.suite_dir(task_id)),
                "--task-id", f"r530vrun_{task_id}_{arm}",
                "--vacant", "1",
                "--sandbox", self.a.sandbox,
                "--test-timeout", str(self.a.test_timeout),
                "--port", str(self.a.pi_port),
                "--timeout", str(self.a.agent_timeout),
                "--json", *spec["flags"],
                "--", self.a.pi_bin, "-p",
                "--provider", "vacantproxy", "--model", "m", prompt]

    def cell_env(self, cell: pathlib.Path) -> dict:
        env = dict(os.environ)
        env["VACANT"] = "1"
        env["VACANT_RUN_UPSTREAM_OPENAI"] = self.upstream
        # **寫死，不 setdefault**：父行程如果有一把真的雲端金鑰，setdefault
        # 會把它原封不動轉給本機端點。
        env["OPENAI_API_KEY"] = "lmstudio"
        env["PI_CODING_AGENT_DIR"] = str(cell / "piconf")
        env["PI_OFFLINE"] = "1"
        env["PI_SKIP_VERSION_CHECK"] = "1"
        env["PYTHONPATH"] = (str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
                             ).rstrip(os.pathsep)
        pib = pathlib.Path(self.a.pi_bin)
        if pib.parent.name and pib.exists():
            env["PATH"] = str(pib.parent) + os.pathsep + env.get("PATH", "")
        return env

    @staticmethod
    def write_cell(cell: pathlib.Path, state: dict) -> None:
        """**邊跑邊寫**（所以讀的人要看 `run_complete`，不要看檔案存在）。"""
        tmp = cell / "cell.json.tmp"
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(cell / "cell.json")

    @staticmethod
    def cell_done(cell: pathlib.Path) -> bool:
        p = cell / "cell.json"
        if not p.is_file():
            return False
        try:
            return bool(json.loads(p.read_text(encoding="utf-8")
                                   ).get("run_complete"))
        except Exception:                                  # noqa: BLE001
            return False

    def harvest(self, cell: pathlib.Path, summary: dict, arm_name: str) -> dict:
        """從 launcher 的 summary ＋ wire 把這一格的量測整理出來。

        M7／F6／F3 用的是 **R535 那一把尺**（`r535.measure_*`），一個位元組沒改。
        """
        run_dir, arm = cell / "run", summary["arm"]
        attempts = summary.get("attempts") or []
        slices, slice_meta = r535.wire_slices(run_dir, arm, attempts)
        out: dict = {
            "accepted": summary.get("accepted"),
            "refused": summary.get("refused"),
            "stop_reason": summary.get("stop_reason"),
            "infra_void": summary.get("infra_void"),
            "attempts_used": summary.get("attempts_used"),
            "max_attempts": summary.get("max_attempts"),
            "requests_seen": summary.get("requests_seen"),
            "agent_wall_s": summary.get("agent_wall_s"),
            "visible_passed": summary.get("visible_passed"),
            "visible_total": summary.get("visible_total"),
            "ws_start_sha256": summary.get("ws_start_sha256"),
            "ws_end_sha256": summary.get("ws_end_sha256"),
            "verdict_sha256": summary.get("verdict_sha256"),
            "verdict_hash": summary.get("verdict_hash"),
            "wire_digest": summary.get("wire_digest"),
            "wire_slice_meta": slice_meta,
            # **bytes 去了誰的伺服器**（2026-09-19 的 `upstreams_defaulted` 修正）：
            # 沒指定的那條 wire 會走 DEFAULT_UPSTREAM ⇒ 真的出網。逐格落盤。
            "upstreams": summary.get("upstreams"),
            "upstreams_defaulted": summary.get("upstreams_defaulted"),
            "sandbox": summary.get("sandbox"),
            "attempts": [{
                "attempt": a["attempt"],
                "accepted": a.get("accepted"),
                "stop_reason": a.get("stop_reason"),
                "visible_passed": a.get("visible_passed"),
                "visible_total": a.get("visible_total"),
                "requests_seen": a.get("requests_seen"),
                "agent_rc": a.get("agent_rc"),
                "agent_timed_out": a.get("agent_timed_out"),
                "agent_wall_s": a.get("agent_wall_s"),
                "orphans_killed": a.get("orphans_killed"),
                "argv_sha256": a.get("argv_sha256"),
                "feedback_delivery": a.get("feedback_delivery"),
                "feedback_in_prompt_bytes": a.get("feedback_in_prompt_bytes"),
                "feedback_sha256": (a.get("feedback") or {}).get("sha256"),
                "frozen_path": a.get("frozen_path"),
                "ws_end_sha256": a.get("ws_end_sha256"),
                "reset": a.get("reset"),
            } for a in attempts],
        }
        idx = run_dir / f"wire_{arm}" / "index.jsonl"
        out["wire_upstreams"] = sorted({
            json.loads(s)["upstream"].rsplit("/v1", 1)[0]
            for s in idx.read_text(encoding="utf-8").splitlines() if s.strip()
        }) if idx.exists() else []
        out["upstream_expected"] = self.upstream
        out["upstream_matches"] = all(
            self.upstream.startswith(u) for u in out["wire_upstreams"]
        ) if out["wire_upstreams"] else None
        out.update(r535.measure_m7_file(run_dir, arm_name, summary, slices,
                                        slice_meta))
        out.update(r535.measure_m7_name(run_dir, arm_name, summary, slices,
                                        slice_meta))
        out.update(r535.measure_m7_ws(run_dir, summary, slices, slice_meta,
                                      tools_path=cell / "tools.jsonl"))
        out.update(r535.measure_f6(arm_name, summary))
        out.update(r535.measure_f3(run_dir, arm, expect=self.a.reasoning_effort))
        out.update(r535.measure_suspect_timeout(run_dir, arm))
        out["agent_timed_out_any"] = any(
            bool(a.get("agent_timed_out")) for a in attempts)
        out["agent_timed_out_n"] = sum(
            1 for a in attempts if a.get("agent_timed_out"))
        # **工作區裡那一份可見驗收有沒有被動過**——不相等是觀測不是錯誤
        # （計分用的是工作區外那一份，所以動了也騙不到閘門）。
        ws_suite = cell / "ws" / "tests_visible"
        out["ws_suite_sha256"] = sha256_dir(ws_suite) if ws_suite.is_dir() else None
        # **worker 有沒有真的去跑題庫附給他的那組驗收**：`__pycache__` 是執行的
        # 副產物，只有 import 過才會有。這是 R530 題庫特有的觀測（R535 的
        # 工作區裡根本沒有驗收，量不到這件事），**不是**判準。
        out["ws_suite_pycache"] = (ws_suite / "__pycache__").is_dir() \
            if ws_suite.is_dir() else None
        out["ws_has_run_tests_sh"] = (cell / "ws" / "run_tests.sh").is_file()
        if not out.get("requests_seen"):
            out["not_mediated"] = True
        return out

    @staticmethod
    def row_of(state: dict) -> dict:
        keys = ("cell", "task_id", "arm", "stratum", "cell_status", "accepted",
                "stop_reason", "attempts_used", "requests_seen",
                "m7_file", "m7_file_reason", "m7_name", "m7_name_reason",
                "m7_ws", "m7_ws_ratio", "m7_ws_solution",
                "m7_ws_solution_ratio", "f6", "f3_verdict", "reasoning_effort",
                "agent_timed_out_n", "suspect_timeout", "visible_passed",
                "visible_total", "upstreams_defaulted", "ws_suite_sha256",
                "ws_suite_pycache", "suite_sha256", "infra_void", "wall_s",
                "agent_wall_s", "run_complete")
        return {"ts": now_iso(), **{k: state.get(k) for k in keys}}

    def run_cell(self, row: dict) -> dict | None:
        task_id, arm = row["task_id"], row["arm"]
        cell = self.cells_dir / row["cell"]
        try:
            cell.mkdir(parents=True)
        except FileExistsError:
            done = self.cell_done(cell)
            self.ev("skip", cell=row["cell"],
                    reason="run_complete" if done else "dir_exists_not_complete")
            return None
        io = cell / "io.jsonl"
        started = time.time()
        suite_meta = self.manifest["suites"][task_id]
        jsonl_append(io, {"ts": now_iso(), "event": "cell_start", **row,
                          "arm_flags": ARMS[arm]["flags"],
                          "upstream": self.upstream,
                          "endpoint_var": "VACANT_GAIN_API",
                          "suite_sha256": suite_meta["sha256"]})
        state: dict = {
            "cell": row["cell"], "task_id": task_id, "arm": arm,
            "stratum": row.get("stratum"), "run_complete": False,
            "cell_status": None, "started": now_iso(),
            "arm_flags": ARMS[arm]["flags"], "prompt": PI_PROMPT,
            "prompt_has_placeholder": ARMS[arm]["placeholder"],
            "stream": self.a.stream, "pi_port": self.a.pi_port,
            "reasoning_effort": self.a.reasoning_effort,
            "agent_timeout_s": self.a.agent_timeout,
            "test_timeout_s": self.a.test_timeout,
            "test_timeout_source": self.a.test_timeout_source,
            "suite_sha256": suite_meta["sha256"],
            "hidden_n": row.get("hidden_n"), "visible_n": row.get("visible_n"),
            "ref_solution_lines": row.get("ref_solution_lines"),
            "task_index": row.get("task_index"), "arm_pos": row.get("arm_pos"),
            "plan_index": row.get("plan_index"),
            "not_preregistered": True,
        }
        self.write_cell(cell, state)

        landed = materialise_ws(cell / "ws", task_id)
        r535.write_pi_config(cell / "piconf", port=self.a.pi_port,
                             model_id=self.a.model,
                             reasoning_effort=r535.effort_or_none(
                                 self.a.reasoning_effort))
        state["workspace_files"] = landed
        argv = self.cell_argv(cell, task_id, arm)
        state["launcher_argv"] = argv
        jsonl_append(io, {"ts": now_iso(), "event": "materialised",
                          "files": landed, "argv": argv})
        if self.a.dry_run:
            state.update({"cell_status": "dry_run", "run_complete": False})
            self.write_cell(cell, state)
            return state

        rc, tries, void_reason = None, [], None
        for i in range(1, INFRA_RETRIES + 1):
            if i > 1:
                for name in ("run", "ws"):
                    src = cell / name
                    if src.exists():
                        src.rename(cell / f"{name}_void_{i - 1}")
                materialise_ws(cell / "ws", task_id)
            t0 = time.time()
            proc = subprocess.run(argv, cwd=str(REPO), env=self.cell_env(cell),
                                  capture_output=True, text=True)
            rc = proc.returncode
            (cell / f"launcher_stdout_{i}.json").write_text(
                proc.stdout or "", encoding="utf-8")
            (cell / f"launcher_stderr_{i}.log").write_text(
                proc.stderr or "", encoding="utf-8")
            tries.append({"try": i, "rc": rc,
                          "wall_s": round(time.time() - t0, 3)})
            jsonl_append(io, {"ts": now_iso(), "event": "launcher_done",
                              "try": i, "rc": rc,
                              "wall_s": round(time.time() - t0, 3),
                              "stderr_tail": (proc.stderr or "")[-600:]})
            if rc in (EXIT_ACCEPTED, EXIT_REFUSED):
                # `requests_seen == 0` ＝ agent 根本沒被中介到 ⇒ **infra_void
                # 不是 0 分**。接線壞掉不准偽裝成「模型答不出來」。
                sp = cell / "run" / "run_RUN-ON.json"
                seen = None
                if sp.exists():
                    try:
                        seen = json.loads(sp.read_text(encoding="utf-8")
                                          ).get("requests_seen")
                    except Exception:                      # noqa: BLE001
                        seen = None
                if seen:
                    break
                void_reason = (f"requests_seen={seen!r}：agent 沒被中介到"
                               f"（pi 的 models.json 指的埠與 --port "
                               f"{self.a.pi_port} 對不上？），第 {i} 次")
                jsonl_append(io, {"ts": now_iso(), "event": "not_mediated",
                                  "try": i, "requests_seen": seen})
                rc = None
                continue
            if rc == 2:
                void_reason = f"launcher 拒收參數（rc=2）：{(proc.stderr or '')[-400:]}"
                state.update({"cell_status": "driver_bug",
                              "infra_void": void_reason, "run_complete": True,
                              "launcher_tries": tries})
                self.write_cell(cell, state)
                raise SystemExit(void_reason)
            void_reason = f"rc={rc}（infra_void 或未知），第 {i} 次"
        state["launcher_tries"] = tries
        state["launcher_rc"] = rc

        summary_path = cell / "run" / "run_RUN-ON.json"
        if rc not in (EXIT_ACCEPTED, EXIT_REFUSED) or not summary_path.exists():
            # **沒量到 ≠ 量到 0**：accepted 落 null，不落 False。
            state.update({
                "cell_status": "infra_void", "accepted": None,
                "infra_void": void_reason or "run_RUN-ON.json 不存在",
                "m7_file": None, "m7_file_reason": "infra_void",
                "m7_name": None, "m7_name_reason": "infra_void",
                "m7_ws": None, "m7_ws_reason": "infra_void",
                "f6": None, "f6_reason": "infra_void",
                "wall_s": round(time.time() - started, 3),
                "run_complete": True, "finished": now_iso()})
            self.write_cell(cell, state)
            jsonl_append(self.out / "cells.jsonl", self.row_of(state))
            self.ev("cell_void", cell=row["cell"], reason=state["infra_void"])
            return state

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        state.update(self.harvest(cell, summary, arm))
        state.update({"wall_s": round(time.time() - started, 3),
                      "cell_status": "measured", "finished": now_iso(),
                      "run_complete": True})
        self.write_cell(cell, state)
        jsonl_append(self.out / "cells.jsonl", self.row_of(state))
        self.ev("cell_done", cell=row["cell"], accepted=state.get("accepted"),
                stop_reason=state.get("stop_reason"),
                attempts=state.get("attempts_used"),
                requests_seen=state.get("requests_seen"),
                m7_file=state.get("m7_file"), m7_ws=state.get("m7_ws"),
                f6=state.get("f6"), f3=state.get("f3_verdict"),
                timed_out_n=state.get("agent_timed_out_n"),
                wall_s=state["wall_s"])
        return state

    def run(self, rows: list[dict]) -> int:
        t = threading.Thread(target=self._uptime_thread, daemon=True)
        t.start()
        self.ev("stream_start", rows=len(rows), load1=load1(),
                uptime=uptime_line(), test_timeout=self.a.test_timeout,
                agent_timeout=self.a.agent_timeout)
        try:
            for row in rows:
                self.wait_for_load()
                st = self.run_cell(row)
                if st is not None:
                    print(f"[{self.a.stream}] {row['cell']:<28} "
                          f"{st.get('cell_status')}  "
                          f"accepted={st.get('accepted')}  "
                          f"{st.get('stop_reason')}  "
                          f"att={st.get('attempts_used')}  "
                          f"req={st.get('requests_seen')}  "
                          f"{st.get('wall_s')}s", flush=True)
        finally:
            self._stop.set()
        self.ev("stream_done", load1=load1(), uptime=uptime_line())
        return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="R530 開放目標題庫 × `vacant run` 收件口（**非預註冊**）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tasks", default="all")
    ap.add_argument("--shard", default=None, help="k:n（用計畫裡的列號分片）")
    ap.add_argument("--stream", default="s0")
    ap.add_argument("--pi-bin", default="pi")
    ap.add_argument("--pi-port", type=int, required=False, default=8890)
    ap.add_argument("--model", default="gemma-4-12b-it-qat")
    ap.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT,
                    choices=REASONING_CHOICES)
    ap.add_argument("--endpoint",
                    default=os.environ.get("VACANT_GAIN_API", ""),
                    help="完整的 http://<host>:1234/v1/chat/completions"
                         "（環境變數 VACANT_GAIN_API，**不是** VACANT_ENDPOINT）")
    ap.add_argument("--test-timeout", type=float, required=True,
                    help="每個驗收測試檔的逾時秒數。**先用 probe_timeout.py 量**，"
                         "不要照抄 R535 的 30 秒（那是為微型題定的）")
    ap.add_argument("--test-timeout-source", default="probe_timeout.py",
                    help="這個數字哪來的——會逐格落盤")
    ap.add_argument("--agent-timeout", type=float,
                    default=DEFAULT_AGENT_TIMEOUT_S)
    ap.add_argument("--sandbox", default="auto")
    ap.add_argument("--load-pause", type=float, default=DEFAULT_LOAD_PAUSE)
    ap.add_argument("--load-poll-s", type=float, default=60.0)
    ap.add_argument("--dry-run", action="store_true")
    return ap


def select(rows: list[dict], args) -> list[dict]:
    out = rows
    if args.tasks != "all":
        want = {t.strip() for t in args.tasks.split(",") if t.strip()}
        out = [r for r in out if r["task_id"] in want]
    if args.shard:
        k, n = (int(x) for x in args.shard.split(":"))
        # 分片用**計畫裡的列號**，不是過濾後的位置——否則 `--tasks` 一過濾，
        # 兩條流就會拿到重疊的格子。
        out = [r for r in out if r["plan_index"] % n == k]
    return out


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.endpoint:
        raise SystemExit(
            "要給 --endpoint 或設 VACANT_GAIN_API"
            "（完整的 http://<host>:1234/v1/chat/completions）。停。")
    out = pathlib.Path(args.out).resolve()
    tasks = task_ids() if args.tasks == "all" else \
        [t.strip() for t in args.tasks.split(",") if t.strip()]
    manifest = write_plan(out, task_ids(), args)
    rows = select(read_plan(out), args)
    print(f"# r530vrun  stream={args.stream}  cells={len(rows)}  "
          f"test_timeout={args.test_timeout}s  load_pause={args.load_pause}  "
          f"{now_iso()}", flush=True)
    print("# ⚠ 非預註冊：這些數字不可以當假說檢定，也不可以與 R535／R530 合併。",
          flush=True)
    return Driver(args, manifest).run(rows)


if __name__ == "__main__":
    sys.exit(main())
