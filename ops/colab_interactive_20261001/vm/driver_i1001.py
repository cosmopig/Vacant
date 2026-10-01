#!/usr/bin/env python3
"""driver_i1001 — i1001 的排程：一條共用佇列、固定的全域並行、可續跑，單位＝一題（A 線＋C 線，R／K 巢狀在 A 之後）。

    python3 driver_i1001.py --phase auto --slots 24 --prefix i1 [--deadline 2026-10-02T06:00:00Z] [--stop-file /srv/eval/STOP]

排法（對照第一批 `driver.py`，但單位的內容不同）：
- 一個單位＝一題：A 線與 C 線**同時**開（一起拿位置，同一時段的負載對兩組一樣）；A 的第 1 段結束後，R（在複本上）與
  K（就地）兩條分支才接著開，它們的每一段 session 各自拿一個位置（接續段優先於新單位）。
- 位置數＝**同時在跑的 pi 對話數**（`--slots`），整批固定。計畫（plan）的題目順序就是種子洗牌後的順序。
- 續跑：檔案系統就是狀態。A 線的單位以 A／R／K 三格的 DONE 判斷（DONE 在整條線結束時才一起寫）；有目錄沒有 DONE ＝ 中斷的殘骸，
  搬到 `cells_aborted/` 後整條線從頭重跑（A 的狀態 K 要就地接續，不能只補一半）。
- **infra_void 重跑一次**：某條線 void（模型端 5xx／429／串流錯誤、第一通請求前就崩、tmux 死了沒 session 檔、安裝失敗、
  工具例外…）⇒ 以 `v2` 後綴整條線重跑一次；第二次還 void 就留著 void（分析列出、不算進任何一組的失敗）。
- **停止檔／時限**：出現就不再開**新單位**；已經開始的單位照樣跑完（配對不會被切一半）。只看時間，不看結果。
- 階段（`--phase auto`）：先跑篩選計畫（任務題庫各 10 題、只跑 A）→ 套天花板規則（A 答對 ≥ 9/10 的題庫丟掉並記錄）→
  產生主跑計畫（LCB 池＋剩下題庫的全部題）→ 跑主跑。`--phase screen|main --plan <檔>` 只跑一個階段。
- 每條線結束寫一行 `/srv/eval/progress.jsonl`：**不含任何分數**（監看只看 rc、牆鐘、逾時、void、安裝）。
  篩選階段的天花板規則要讀 A 的分數——由 plan_builder 直接讀 score.json，不經過 progress。
- 結束時把這一批的整體紀錄（計畫、天花板決定、driver 日誌）放進 `cells/_run_<前綴>/`（有 DONE ⇒ 被 packer 打包），
  然後才寫 `DRIVER_DONE`（packer 看到它才收尾）。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_builder  # noqa: E402
import tui_cell  # noqa: E402
from tui_cell import Cfg, add_cfg_args, cfg_from_args, load_ledger, log, now  # noqa: E402
from tui_lib import SlotPool, cell_name  # noqa: E402


def read_meta(d: Path) -> dict | None:
    try:
        return json.loads((d / "meta.json").read_text())
    except (OSError, ValueError):
        return None


def required_arms(plan: dict, task: dict, group: str, a_meta: dict | None) -> list[str]:
    """這條線應該有哪幾格（K 若在 prepare 時被判不可用，A 的 meta.k_on＝False，K 沒有目錄是正常的）。"""
    if group == "C":
        return ["C"]
    arms = ["A"]
    if "R" in plan.get("nested", []):
        arms.append("R")
    if "K" in plan.get("nested", []) and task.get("k") and (a_meta is None or a_meta.get("k_on", True)):
        arms.append("K")
    return arms


def _group_dirs(cfg: Cfg, prefix: str, task: dict, group: str, sample: int, attempt: int) -> list[Path]:
    arms = ["C"] if group == "C" else ["A", "R", "K"]
    out = []
    for arm in arms:
        p = cfg.cells / cell_name(prefix, arm, task["bank"], task["id"], sample, attempt)
        if p.exists():
            out.append(p)
    return out


def append_event(cfg: Cfg, row: dict) -> None:
    """progress.jsonl 是 append-only：除了每格的完成列，也記「搬走殘骸」「重跑」這類事件（有 `event` 欄；沒有分數）。"""
    cfg.eval_root.mkdir(parents=True, exist_ok=True)
    with (cfg.eval_root / "progress.jsonl").open("a") as f:
        f.write(json.dumps({**row, "at": now()}, ensure_ascii=False) + "\n")


def _archive_partial(cfg: Cfg, dirs: list[Path]) -> None:
    for p in dirs:
        dst = cfg.eval_root / "cells_aborted" / f"{p.name}.{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(dst))
        append_event(cfg, {"event": "aborted_partial_moved", "cell": p.name, "to": f"cells_aborted/{dst.name}"})
        log(f"moved incomplete cell {p.name} -> cells_aborted/{dst.name}")


def group_status(cfg: Cfg, plan: dict, task: dict, group: str, prefix: str, sample: int) -> tuple[str, int]:
    """("done", 最後那次) 或 ("todo", 下一個要跑的 attempt)。中斷的殘骸（有目錄、這條線沒有全部寫好 DONE）整條線搬去
    `cells_aborted/`、同一個 attempt 重跑；void 的 attempt 1 ⇒ 下一次是 attempt 2；attempt 2 不論結果都到此為止。"""
    arm0 = "C" if group == "C" else "A"
    for attempt in (1, 2):
        d0 = cfg.cells / cell_name(prefix, arm0, task["bank"], task["id"], sample, attempt)
        meta = read_meta(d0) if (d0 / "DONE").exists() else None
        existing = _group_dirs(cfg, prefix, task, group, sample, attempt)
        if meta is None:
            _archive_partial(cfg, existing)
            return "todo", attempt
        arms = required_arms(plan, task, group, meta)
        missing = [a for a in arms if not (cfg.cells / cell_name(prefix, a, task["bank"], task["id"], sample, attempt) / "DONE").exists()]
        if missing:
            _archive_partial(cfg, existing)
            return "todo", attempt
        if not (meta.get("void") or meta.get("group_void")):
            return "done", attempt
    return "done", 2


def progress_row(meta: dict) -> dict:
    return {"cell": meta["cell"], "unit": meta["unit"], "bank": meta["bank"], "task": meta["task"], "arm": meta["arm"],
            "sample": meta["sample"], "attempt": meta["attempt"], "void": meta.get("void"), "void_reason": meta.get("void_reason"),
            "timeout": meta.get("timeout"), "rc": meta.get("rc"), "wall_s": meta.get("wall_s"), "n_sessions": meta.get("n_sessions"),
            "install_rc": meta.get("install_rc"), "c_arm_ok": meta.get("c_arm_ok"), "done_reason": meta.get("done_reason"),
            "at": now()}


class Driver:
    def __init__(self, cfg: Cfg, slots: int, prefix: str, stop_file: Path, deadline: float | None, max_units: int | None):
        self.cfg, self.prefix, self.stop_file, self.deadline = cfg, prefix, stop_file, deadline
        self.pool = SlotPool(slots)
        self.ledger = load_ledger(cfg)
        self.prog = cfg.eval_root / "progress.jsonl"
        self.lock = threading.Lock()
        self.max_units = max_units
        self.threads: list[threading.Thread] = []
        self.started_units = 0

    def stopping(self) -> bool:
        return self.stop_file.exists() or (self.deadline is not None and time.time() > self.deadline)

    def record(self, metas: list[dict]) -> None:
        with self.lock, self.prog.open("a") as f:
            for m in metas:
                if m:
                    f.write(json.dumps(progress_row(m), ensure_ascii=False) + "\n")
        for m in metas:
            if m:
                log(f"done {m['cell']} void={m.get('void')} timeout={m.get('timeout')} wall={m.get('wall_s')}s sessions={m.get('n_sessions')}"
                    + (f" reason={m.get('void_reason')}" if m.get("void") else ""))

    def run_group(self, plan: dict, task: dict, group: str, attempt: int, sample: int, prefix: str) -> None:
        """一條線的執行緒：已經拿著第一段的位置；void 且 attempt==1 ⇒ 拿一個接續位置、整條線重跑一次。"""
        held = True
        try:
            while True:
                if not held:
                    self.pool.acquire(1, priority=True)
                    held = True
                try:
                    if group == "C":
                        meta = tui_cell.run_c_group(self.cfg, self.ledger, self.pool, task, prefix=prefix, sample=sample,
                                                    attempt=attempt, first_slot_held=True)
                        metas = [meta]
                        void = bool(meta.get("void"))
                    else:
                        out = tui_cell.run_a_group(self.cfg, self.ledger, self.pool, task, prefix=prefix,
                                                   nested=tuple(plan.get("nested", [])), sample=sample, attempt=attempt,
                                                   first_slot_held=True)
                        metas = [out.get("A"), out.get("R"), out.get("K")]
                        void = bool(out.get("void"))
                    held = False                       # run_*_group 內部已經放掉第一段的位置
                except Exception as e:  # noqa: BLE001
                    log(f"group thread exception {task['bank']}/{task['id']} {group}: {type(e).__name__}: {e}\n{traceback.format_exc()}")
                    metas, void = [], True
                    if held:
                        self.pool.release(1)
                        held = False
                self.record([m for m in metas if m])
                if void and attempt < 2:
                    attempt += 1
                    append_event(self.cfg, {"event": "infra_void_rerun", "unit": f"{task['bank']}/{task['id']}", "group": group,
                                            "attempt": attempt})
                    log(f"infra_void -> rerun once: {task['bank']}/{task['id']} group {group} (attempt {attempt})")
                    continue
                return
        finally:
            if held:
                self.pool.release(1)

    def run_plan(self, plan: dict, prefix: str) -> dict:
        """prefix：這個階段的格子名前綴。篩選階段用 `<前綴>s`、主跑用 `<前綴>`——同一題在兩個階段各自重跑 A
        （篩選用的 A 結果決定題庫去留，主跑的 A 不能重用它：重用會把「因為 A 在這些題上表現差而選了這個題庫」的選擇偏誤帶進 C 對 A 的比較）。"""
        log(f"plan kind={plan['kind']} prefix={prefix} units={len(plan['tasks'])} arms={plan['arms']} nested={plan.get('nested')} slots={self.pool.n}")
        sample = int(plan.get("samples", [1])[0])
        skipped = launched = 0
        for task in plan["tasks"]:
            if self.max_units is not None and launched >= self.max_units:
                break
            if self.stopping():
                log("stop file / deadline: no new units")
                break
            task = dict(task, phase=plan["kind"])
            todo = []
            for group in (["A"] if "A" in plan["arms"] else []) + (["C"] if "C" in plan["arms"] else []):
                st, attempt = group_status(self.cfg, plan, task, group, prefix, sample)
                if st == "todo":
                    todo.append((group, attempt))
            if not todo:
                skipped += 1
                continue
            self.pool.acquire(len(todo))            # 一個單位的各條線一起拿位置（同時開跑）
            if self.stopping():
                self.pool.release(len(todo))
                log("stop file / deadline: no new units")
                break
            launched += 1
            for group, attempt in todo:
                th = threading.Thread(target=self.run_group, args=(plan, task, group, attempt, sample, prefix), daemon=False,
                                      name=f"{task['bank']}/{task['id']}:{group}")
                th.start()
                self.threads.append(th)
        for th in self.threads:
            th.join()
        self.threads = []
        log(f"plan {plan['kind']} finished: launched={launched} already_done={skipped} peak_slots={self.pool.peak}")
        return {"launched": launched, "already_done": skipped}


def parse_deadline(s: str | None) -> float | None:
    if not s:
        return None
    import calendar
    return float(calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ")))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--phase", choices=["auto", "screen", "main"], default="auto")
    ap.add_argument("--plan", type=Path, help="phase=screen|main：計畫檔")
    ap.add_argument("--staged", type=Path, default=Path("/srv/eval/staged"))
    ap.add_argument("--slots", type=int, default=16, help="同時在跑的 pi 對話數（整批固定）")
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--seed", type=int, default=20261001)
    ap.add_argument("--deadline")
    ap.add_argument("--stop-file", type=Path, default=Path("/srv/eval/STOP"))
    ap.add_argument("--max-units", type=int)
    ap.add_argument("--nested", default="R,K", help="主跑的巢狀分支（逗號分隔）；空字串＝只跑 A、C")
    ap.add_argument("--logfile", type=Path, help="這個 driver 的 stdout 日誌（結束時複製進紀錄）")
    ap.add_argument("--final", action="store_true", help="phase=screen|main 單跑時也在結束寫 DRIVER_DONE")
    ap.add_argument("--dry-run", action="store_true")
    add_cfg_args(ap)
    a = ap.parse_args(argv)
    cfg = cfg_from_args(a)
    cfg.cells.mkdir(parents=True, exist_ok=True)
    cfg.receivers.mkdir(parents=True, exist_ok=True)
    cfg.receivers.chmod(0o700)
    drv = Driver(cfg, a.slots, a.prefix, a.stop_file, parse_deadline(a.deadline), a.max_units)
    scr_prefix = f"{a.prefix}s"
    index, manifest = plan_builder.load_inputs(a.staged)
    nested = tuple(x for x in a.nested.split(",") if x)
    phases: dict = {}

    def stamp(plan: dict) -> dict:
        plan["source"] = {"tasks_index_sha256": plan_builder.sha256_file(a.staged / "tasks_index.json"),
                          "manifest_sha256": plan_builder.sha256_file(a.staged / "MANIFEST.json")}
        return plan

    def save_plans() -> None:
        (cfg.eval_root / "plan.json").write_text(json.dumps(phases, ensure_ascii=False, indent=1) + "\n")

    if a.phase in ("auto", "screen"):
        splan = json.loads(a.plan.read_text()) if (a.phase == "screen" and a.plan) else stamp(plan_builder.screening_plan(index, manifest, a.seed))
        phases["screen"] = splan
        (cfg.eval_root / "plan_screen.json").write_text(json.dumps(splan, ensure_ascii=False, indent=1) + "\n")
        save_plans()
        if a.dry_run:
            print(json.dumps({"screen": splan["estimate"]}))
        else:
            drv.run_plan(splan, scr_prefix)
    decision = None
    if a.phase == "auto":
        outcomes = plan_builder.screen_outcomes(cfg.cells, scr_prefix, phases["screen"])
        expected = {b: len(ids) for b, ids in (manifest.get("screen_sample") or {}).items()}
        decision = plan_builder.ceiling_decision(outcomes, expected)
        (cfg.eval_root / "ceiling_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=1) + "\n")
        phases["ceiling_decision"] = decision
        log("ceiling decision: " + json.dumps({b: (v["dropped"], v["passes"], v["n"]) for b, v in decision["banks"].items()}))
    if a.phase in ("auto", "main"):
        if a.phase == "main" and a.plan:
            mplan = json.loads(a.plan.read_text())
        else:
            mplan = stamp(plan_builder.main_plan(index, manifest, decision, a.seed, nested=nested))
        phases["main"] = mplan
        (cfg.eval_root / "plan_main.json").write_text(json.dumps(mplan, ensure_ascii=False, indent=1) + "\n")
        save_plans()
        if a.dry_run:
            print(json.dumps({"main": mplan["estimate"], "dropped_banks": mplan.get("dropped_banks")}))
        else:
            drv.run_plan(mplan, a.prefix)
    if a.dry_run:
        return 0
    # 這一批的整體紀錄 → 一個「_run_」格子（有 DONE ⇒ 被 packer 打包）
    rd = cfg.cells / f"_run_{a.prefix}"
    rd.mkdir(parents=True, exist_ok=True)
    save_plans()
    for f in ("plan.json", "plan_screen.json", "plan_main.json", "ceiling_decision.json"):
        if (cfg.eval_root / f).exists():
            shutil.copy2(cfg.eval_root / f, rd / f)
    if a.logfile and a.logfile.exists():
        shutil.copy2(a.logfile, rd / "driver.log")
    (rd / "meta.json").write_text(json.dumps({"cell": rd.name, "kind": "run_record", "prefix": a.prefix, "ended": now(),
                                              "slots": a.slots, "peak_slots": drv.pool.peak}, indent=1) + "\n")
    (rd / "DONE").write_text(now() + "\n")
    if a.phase == "auto" or a.final:
        (cfg.eval_root / "DRIVER_DONE").write_text(now() + "\n")
        log("DRIVER_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
