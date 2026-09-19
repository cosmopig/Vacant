#!/usr/bin/env python3
"""把 `harness_vgt_audit.py --scope v3` 回溯跑遍 repo 裡**每一份** `calls.jsonl`。

這支在架構裡承重什麼（round534，2026-09-18）
────────────────────────────────────────────
`harness_vgt_audit.audit_run()` 在 v1／v2 之下只掃 H 三臂（`VARIANTS`），
而我們拿它的輸出講過「R532 43/43 塊 V/GT 紅線 CLEAN」這種**整個 run** 的話。
v3 把範圍擴到十條臂並加上逐臂 fail-closed；這一支負責回答隨之而來的那個問題：
**過去那 179 份 `calls.jsonl`，在新判準下各是什麼結論？**
零機時、零模型呼叫——輸入只有已經歸檔的 JSONL 與釘死的題庫。

⚠ **題庫配對錯了會讓結論整個翻掉**：`--bank` 配錯 ⇒ 每一個 task_id 都對不到題目
  ⇒ `unknown_task_ids` 爆掉 ⇒ fail-closed 判 VIOLATION。那是**量具的假影**，
  不是洩漏。所以這支不讓人用手輸入 bank，改用下面這條**可覆核的推斷**：

  1. `summary.json` 有 `bank` 欄位而且是字串 ⇒ 用它（R529 之後的 run 才有）。
  2. 沒有 ⇒ 用**題目集合包含關係**推：把該 run 在 `calls.jsonl` 裡出現過的
     全部 `task_id` 收成集合 S，找出所有滿足 `S ⊆ 該題庫的 task_id 集合` 的題庫。
     · 恰好一個 ⇒ 用它。
     · 多個 ⇒ 依 `BANK_PREFERENCE` 取第一個。目前唯一會多重命中的是
       LCB v1 ⊂ v2（91 題全包含），而**那 91 題的 `prompt` 與
       `hidden_check.code` 在兩版逐字相同**（`bank_sets` 實測 0 筆相異），
       所以選哪一版對稽核結果沒有差別；釘 `lcb2` 只是要讓結果可重現。
     · 零個 ⇒ **標 `UNVERIFIABLE`，不猜**。「推不出來」不是「乾淨」。
  3. 全部 task_id 以 `ow_` 開頭 ⇒ 那是 R530（工作區題目，不在 `load_tasks`
     那條路徑上）⇒ 走 `audit_run_r530()`，不是 `audit_run()`。

  ⚠ 用 run 名稱裡的字串（`..._mbpp_...`／`..._lcb3m_...`）推 bank 是**不可靠**的：
    `lcb3m`／`lcb3h` 是 `--bank lcb3 --bank-filter difficulty=…` 的分層，
    不是題庫名；`mbpp` 其實是 `evalplus`。名稱只當人讀的線索，不進判斷。

⚠ **題庫要載入「整個」而不是 run 當時選中的那幾題**：`load_tasks(bank, seed, 0)`
  會套用 `GAIN_EVALPLUS_RESOURCE_EXCLUSIONS` 之類的**選題**排除，而排除掉的題目
  在舊 run 裡可能真的被跑過 ⇒ 對不到題目 ⇒ 假 VIOLATION。稽核要的是
  **對照表**不是**抽樣**，所以這支直接從 loader 拿全量（378／164／91／120／189），
  不走 `load_tasks`。

用法：
    python3 ops/gain/vgt_retro_audit.py --out ops/gain/vgt_retro_audit_20260918.json
    python3 ops/gain/vgt_retro_audit.py --run runs/g_r532_mbpp_a1     # 單跑一份
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.gain.harness_vgt_audit import (audit_run,  # noqa: E402
                                        audit_run_r530)

#: 多重命中時的取用順序（見模組 docstring 第 2 條）。
BANK_PREFERENCE = ("evalplus", "humanevalplus", "lcb2", "lcb3", "lcb")

_TASK_MAPS: dict[str, dict[str, dict]] = {}


def bank_maps() -> dict[str, dict[str, dict]]:
    """五個釘死題庫的 `task_id → task` 全量對照表（lazy、只建一次）。"""
    if _TASK_MAPS:
        return _TASK_MAPS
    from vacant_network.codebench import (EvalPlusHumanEvalLoader, EvalPlusMBPPLoader,
                                  LiveCodeBenchLoader)
    # `expose_contract=True` 必須與 `gain_run.load_tasks` 逐字相同——
    # `task["prompt"]` 是稽核規則 (a)「題目原文逐字扣掉」的扣除對象，
    # prompt 形狀不同就扣不掉，會製造整批假陽性。
    _TASK_MAPS["evalplus"] = {
        t["task_id"]: t
        for t in EvalPlusMBPPLoader(expose_contract=True).iter_tasks("retro")}
    _TASK_MAPS["humanevalplus"] = {
        t["task_id"]: t for t in EvalPlusHumanEvalLoader().iter_tasks("retro")}
    for name, ver in (("lcb", "v1"), ("lcb2", "v2"), ("lcb3", "v3")):
        _TASK_MAPS[name] = {
            t["task_id"]: t
            for t in LiveCodeBenchLoader(version=ver).iter_tasks("retro")}
    return _TASK_MAPS


def run_task_ids(calls_path: pathlib.Path) -> set[str]:
    """該 run 的 `calls.jsonl` 裡出現過的全部 `task_id`（preflight 沒有，略過）。"""
    out: set[str] = set()
    with calls_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = (rec.get("meta") or {}).get("task_id")
            if tid:
                out.add(str(tid))
    return out


def infer_bank(summary: dict, tids: set[str]) -> tuple[str | None, str]:
    """回 `(bank, how)`；推不出來回 `(None, 理由)`——**不猜**。"""
    declared = summary.get("bank")
    if isinstance(declared, str) and declared in bank_maps():
        return declared, "summary.json:bank"
    if not tids:
        return None, "calls.jsonl 裡一個 task_id 都沒有（多半是只有 preflight 的中止 run）"
    if all(t.startswith("ow_") for t in tids):
        return "r530", "task_id 全部是 ow_*（R530 工作區題目）"
    covers = [b for b in BANK_PREFERENCE if tids <= set(bank_maps()[b])]
    if not covers:
        sample = sorted(tids)[:3]
        return None, f"沒有任何釘死題庫涵蓋這些 task_id（例：{sample}）"
    return covers[0], ("task_id 集合包含關係"
                       + (f"（多重命中 {covers}，取 BANK_PREFERENCE 第一個）"
                          if len(covers) > 1 else ""))


def audit_one(run_dir: pathlib.Path) -> dict:
    """單一 run 的回溯稽核結果（含 bank 推斷的過程，好讓人覆核）。"""
    rel = str(run_dir.relative_to(ROOT))
    summary_path = run_dir / "summary.json"
    summary: dict = {}
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            summary = {"_unreadable": repr(exc)}
    tids = run_task_ids(run_dir / "calls.jsonl")
    bank, how = infer_bank(summary, tids)
    base = {"run": rel, "bank": bank, "bank_inference": how,
            "n_task_ids": len(tids)}
    if bank is None:
        return {**base, "verdict": "UNVERIFIABLE", "scope": None,
                "reason": how, "per_arm": {}, "arms_present": {},
                "arms_present_not_audited": [], "needles_checked": 0,
                "texts_scanned": 0, "unknown_task_ids": [], "violations": []}
    try:
        if bank == "r530":
            from ops.gain.r530 import tasks as r530tasks
            ids = summary.get("tasks") or sorted(tids)
            tasks = {t["task_id"]: t for t in (r530tasks.load_task(i) for i in ids)}
            res = audit_run_r530(run_dir, tasks)
        else:
            res = audit_run(run_dir, bank_maps()[bank], scope="v3")
    except SystemExit as exc:                                   # fail-closed
        return {**base, "verdict": "UNVERIFIABLE", "scope": "v3",
                "reason": f"稽核自己停下來了：{exc}", "per_arm": {},
                "arms_present": {}, "arms_present_not_audited": [],
                "needles_checked": 0, "texts_scanned": 0,
                "unknown_task_ids": [], "violations": []}
    keep = ("scope", "verdict", "records_audited", "texts_scanned",
            "arms_present", "per_arm", "arms_present_not_audited",
            "needles_checked", "needles_unique_scanned",
            "needles_skipped_trivial", "excused_n", "excused_by_rule",
            "unknown_task_ids")
    out = {**base, **{k: res[k] for k in keep if k in res}}
    # 每一列的欄位形狀要一致（`audit_run_r530` 沒有這幾格）——機器讀的檔案
    # 少一個鍵與「那一格是 0」在下游長得一樣，所以明著補成空值。
    out.setdefault("arms_present", {})
    out.setdefault("arms_present_not_audited", [])
    out.setdefault("needles_unique_scanned", None)
    # 違規**逐筆留著**（前 50 筆＋總數）——稽核證據不准只留一個數字。
    out["violations_n"] = len(res.get("violations") or [])
    out["violations"] = (res.get("violations") or [])[:50]
    if "workspace_needle_hits_n" in res:
        out["workspace_needle_hits_n"] = res["workspace_needle_hits_n"]
        out["deny_hidden_read_n"] = res.get("deny_hidden_read_n")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="V/GT 動態稽核回溯補掃（零機時、零模型呼叫）")
    ap.add_argument("--root", default=str(ROOT), help="從哪裡開始找 calls.jsonl")
    ap.add_argument("--run", default=None, help="只跑這一份 run 目錄")
    ap.add_argument("--out", default=None, help="結果 JSON 落盤路徑")
    args = ap.parse_args()

    if args.run:
        run_dirs = [pathlib.Path(args.run).resolve()]
    else:
        root = pathlib.Path(args.root).resolve()
        run_dirs = sorted(p.parent for p in root.rglob("calls.jsonl")
                          if ".git" not in p.parts)

    rows: list[dict] = []
    t0 = time.time()
    for i, d in enumerate(run_dirs, 1):
        row = audit_one(d)
        rows.append(row)
        print(f"[{i}/{len(run_dirs)}] {row['verdict']:13s} "
              f"bank={str(row['bank']):14s} arms={sorted(row.get('per_arm') or {})} "
              f"{row['run']}", flush=True)
        if row["verdict"] == "VIOLATION":
            print("    ⚠ 違規 %d 筆，前三：%s" % (
                row.get("violations_n", 0),
                json.dumps(row["violations"][:3], ensure_ascii=False)[:600]),
                flush=True)

    tally: dict[str, int] = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "scope": "v3（round534：十條臂＋逐臂 fail-closed）",
        "runs": len(rows), "tally": tally,
        "wall_s": round(time.time() - t0, 1),
        "honest_bounds": [
            "`UNVERIFIABLE` 不是「乾淨」也不是「髒」——它是「這一份在這套量具下"
            "沒有可稽核的對象」（只有 preflight／題庫推不出來／arm 不在名單上）。",
            "`CLEAN` 只保證：`hidden \\\\ visible` 的**字面 repr** 沒有出現在"
            "harness 自己寫的 system／user 文字裡。語意等價的改寫、以及"
            "`excused` 裡那些作者歸屬豁免，這支都認不出來。",
            "bank 是**推斷**出來的（見 `bank_inference` 欄位），不是 run 自己記的；"
            "R529 之前的 run 沒有 `--record-bank-field`，`summary.json` 沒有 bank 欄位。",
        ],
        "rows": rows,
    }
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.out:
        pathlib.Path(args.out).write_text(text + "\n", encoding="utf-8")
        print("wrote", args.out)
    print("tally:", tally)
    bad = [r["run"] for r in rows if r["verdict"] == "VIOLATION"]
    if bad:
        print("VIOLATION runs:", bad)


if __name__ == "__main__":
    main()
