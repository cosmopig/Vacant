#!/usr/bin/env python3
"""H 臂的 V/GT 洩漏動態稽核（跑在 run 的產物上，零模型呼叫）。

規格：`docs/HARNESS_STUDY_2026-09-07.md` §5.8。

**為什麼一定要跑在 rows／calls 上，不能只讀原始碼**：
「程式碼裡沒有 import 隱藏測資」不能證明「沒有 GT 進 prompt」——例如未來有人把
`conform_failure_detail` 的輸出擴充成帶期望值，靜態檢查照樣全綠。這支唯一的
輸入是**實際送出去的文字**（`calls.jsonl` 的 `messages`／`prompt` 全文）。

⚠ **D7：可見測資的內容（args／got／want）在 H 臂是刻意進 worker prompt 的**
  （HARNESS_STUDY §5.8；**本 repo 第一次**——既有的 OFF／CONFORM／OFF5 只送題目敘述）。
  合法性依據：`visible` 測資照設計就是給供應者看的驗收條件
  （LCB 的 assert 訊息三個欄位全部來自 `visible_tests`），
  **只有 `hidden \ visible`（隱藏測資扣掉可見測資）那一段才是 GT**。
  所以這支稽核的對象逐字是 **`hidden \ visible`**，不是「有沒有測資進 prompt」
  ——那個問題的答案是「有，而且是設計要的」，
  斷言「visible 沒出現」會**必然失敗**，因為它按設計就在裡面。

三條斷言（任何一條命中 ⇒ 整個 run 作廢，照 SPEC_GAIN §7 落盤並公開，
不得只修不報）：

  1. 送出的文字不含驗收碼專屬識別字（那幾個雙底線名字、`exec(`）
     ⇒ 驗收碼的**原始碼**從來沒有被送給模型，只有 `str(exc)` 被轉發。
     ⚠ 例外只有一個：`harness_arms._RULES` 那句給模型的禁令本身含 `exec(`
       （「Do not call … exec() …」）。掃描前把那個**凍結常數**整段扣掉；
       扣的是逐字相等的那一段，任何別處出現的 `exec(` 照樣會被抓到。
  2. 對該題「隱藏測資 \\ 可見測資」的每一個 case，`repr(args)` 與 `repr(expected)`
     都不出現在任何送出的文字裡。
  3. MBPP+ 的複製跑：另外斷言不含只在隱藏側出現的輸入運算式（同一條規則，
     只是那個題庫的驗收碼形狀不同）。

**誠實邊界**：`repr(expected)` 太短時（`0`、`[]`、`True`）子字串比對必然命中，
那不是洩漏而是量具沒有鑑別力。這支**不**把那種 needle 算成違規，但會**單獨列出
被跳過的數量**——跳過的東西要說出來，不能讓「沒有違規」順手把「沒有檢查」蓋掉。

用法（D9：兩塊各跑一次，兩塊都要綠才算過）：
    python3 ops/gain/harness_vgt_audit.py --run runs/g_r460_harness_lcb2_a --bank lcb2
    python3 ops/gain/harness_vgt_audit.py --run runs/g_r460_harness_lcb2_b --bank lcb2
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.harness_arms import (RULES_NO_CALL_LINE, VARIANTS,  # noqa: E402
                                   _RULES)

# 驗收碼專屬的識別字。`exec(` 是最弱的一條（凍結常數會撞到，見上面的例外說明），
# 其餘三個只可能來自驗收碼本身。
CODE_NEEDLES = ("__canon", "exec(", "__aeq", "__tests")

# 短到子字串比對沒有鑑別力的 needle 不算違規，但要單獨計數。
MIN_NEEDLE_CHARS = 4


#: 送出文字裡**唯一**允許出現 `exec(` 的地方：給模型的那句禁令（`harness_arms`
#: 的 `RULES_NO_CALL_LINE`，逐字凍結）。掃描前只扣掉這一行與整段 Rules 模板，
#: 別處的 `exec(` 照樣算違規。
FROZEN_SENT_CONSTANTS = (RULES_NO_CALL_LINE, _RULES)


def strip_frozen_constants(text: str) -> str:
    """把 H 臂的凍結 prompt 常數逐字扣掉（相等才扣，不做模糊比對）。"""
    out = text or ""
    for frozen in FROZEN_SENT_CONSTANTS:
        out = out.replace(frozen, "")
    return out


def sent_texts(rec: dict) -> list[str]:
    """一筆 `calls.jsonl` 實際送出去的全部文字（system ＋ 每一則訊息）。"""
    out = []
    if rec.get("system"):
        out.append(rec["system"])
    msgs = rec.get("messages")
    if isinstance(msgs, list) and msgs:
        out += [m.get("content", "") for m in msgs if isinstance(m, dict)]
    elif rec.get("prompt"):
        out.append(rec["prompt"])
    return [t for t in out if t]


def lcb_cases(check_code: str) -> list[dict] | None:
    """LCB 形狀：`__tests = <list literal>`。認不出來回 None（**不猜**）。"""
    try:
        tree = ast.parse(check_code)
    except SyntaxError:
        return None
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "__tests"):
            try:
                tests = ast.literal_eval(node.value)
            except (ValueError, SyntaxError, TypeError):
                return None
            return tests if isinstance(tests, list) else None
    return None


def mbpp_inputs(check_code: str) -> list[str] | None:
    """MBPP+ 形狀：尾端一串 `assert __aeq(entry(*<expr>), …)`；回 `<expr>` 的原始碼。"""
    try:
        tree = ast.parse(check_code)
    except SyntaxError:
        return None
    exprs: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assert):
            continue
        for call in ast.walk(node.test):
            if isinstance(call, ast.Call):
                for arg in call.args:
                    if isinstance(arg, ast.Starred):
                        exprs.append(ast.unparse(arg.value))
    return exprs or None


def hidden_only_needles(task: dict) -> tuple[list[str], list[str]]:
    """回 `(needles, skipped)`：只在隱藏側出現的 case 的 repr。"""
    vis_code = task["visible_check"]["code"]
    hid_code = task["hidden_check"]["code"]
    needles: list[str] = []
    skipped: list[str] = []

    vis_cases, hid_cases = lcb_cases(vis_code), lcb_cases(hid_code)
    if vis_cases is not None and hid_cases is not None:
        vis_repr = {repr(c) for c in vis_cases}
        for case in hid_cases:
            if repr(case) in vis_repr:
                continue
            for key in ("args", "expected"):
                if key not in case:
                    continue
                needle = repr(case[key])
                (needles if len(needle) >= MIN_NEEDLE_CHARS else skipped).append(needle)
        return needles, skipped

    vis_in, hid_in = mbpp_inputs(vis_code), mbpp_inputs(hid_code)
    if vis_in is not None and hid_in is not None:
        seen = set(vis_in)
        for expr in hid_in:
            if expr in seen:
                continue
            seen.add(expr)
            for needle in {expr, _literal_repr(expr)} - {None}:
                (needles if len(needle) >= MIN_NEEDLE_CHARS
                 else skipped).append(needle)
        return needles, skipped

    raise SystemExit(f"認不出驗收碼形狀：{task['task_id']}——認不出來不是通過，是沒接上。停。")


def _literal_repr(expr: str) -> str | None:
    try:
        return repr(ast.literal_eval(expr))
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None


def audit_run(run_dir: pathlib.Path, tasks: dict[str, dict]) -> dict:
    """回一份可落盤的稽核結果；`violations` 非空 ⇒ 整個 run 作廢。"""
    calls_path = run_dir / "calls.jsonl"
    if not calls_path.exists():
        raise SystemExit(f"{calls_path} 不存在——沒有 calls 就沒有稽核對象。停。")
    violations: list[dict] = []
    n_records = n_texts = n_skipped = n_checked = 0
    cache: dict[str, tuple[list[str], list[str]]] = {}
    unknown_tasks: set[str] = set()
    per_arm: dict[str, int] = {}
    with calls_path.open(encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            rec = json.loads(line)
            arm = (rec.get("meta") or {}).get("arm")
            if arm not in VARIANTS:
                continue
            n_records += 1
            per_arm[arm] = per_arm.get(arm, 0) + 1
            texts = sent_texts(rec)
            n_texts += len(texts)
            scrubbed = [strip_frozen_constants(t) for t in texts]
            for needle in CODE_NEEDLES:
                for i, text in enumerate(scrubbed):
                    if needle in text:
                        violations.append({
                            "line": ln, "arm": arm, "rule": "check_code_identifier",
                            "needle": needle, "message_index": i,
                            "task_id": (rec.get("meta") or {}).get("task_id"),
                            "excerpt": text[max(0, text.find(needle) - 80):
                                            text.find(needle) + 80]})
            task_id = (rec.get("meta") or {}).get("task_id")
            task = tasks.get(task_id)
            if task is None:
                unknown_tasks.add(str(task_id))
                continue
            if task_id not in cache:
                cache[task_id] = hidden_only_needles(task)
            needles, skipped = cache[task_id]
            n_skipped += len(skipped)
            n_checked += len(needles)
            for needle in needles:
                for i, text in enumerate(texts):
                    if needle in text:
                        violations.append({
                            "line": ln, "arm": arm, "rule": "hidden_case_leak",
                            "needle": needle, "message_index": i,
                            "task_id": task_id,
                            "excerpt": text[max(0, text.find(needle) - 80):
                                            text.find(needle) + 80]})
    return {
        "run": str(run_dir), "records_audited": n_records,
        "texts_audited": n_texts, "per_arm": per_arm,
        # 檢查了幾個 needle、跳過幾個——跳過的要說出來，
        # 不能讓「沒有違規」順手把「沒有檢查」蓋掉（見模組 docstring 的誠實邊界）。
        "needles_checked": n_checked,
        "needles_skipped_too_short": n_skipped,
        "unknown_task_ids": sorted(unknown_tasks),
        "violations": violations,
        "verdict": "CLEAN" if not violations and not unknown_tasks else "VIOLATION",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="H 臂 V/GT 洩漏動態稽核（零模型呼叫）")
    ap.add_argument("--run", required=True)
    ap.add_argument("--bank", default="lcb2",
                    help="題庫名（summary.json 沒有記 bank，必須顯式給，不猜）")
    ap.add_argument("--seed", default=None, help="預設讀 summary.json 的 seed")
    ap.add_argument("--out", default=None, help="稽核結果 JSON 落盤路徑")
    args = ap.parse_args()

    run_dir = pathlib.Path(args.run)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    seed = args.seed or summary["seed"]
    from ops.gain.gain_run import load_tasks
    tasks = {t["task_id"]: t for t in load_tasks(args.bank, seed, 0)}
    result = audit_run(run_dir, tasks)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        pathlib.Path(args.out).write_text(text + "\n", encoding="utf-8")
    if result["verdict"] != "CLEAN":
        raise SystemExit(
            f"V/GT 稽核不通過：{len(result['violations'])} 筆違規／"
            f"{len(result['unknown_task_ids'])} 個對不到題目的 task_id"
            "——整個 run 作廢（SPEC_GAIN §7），不得只修不報。")


if __name__ == "__main__":
    main()
