#!/usr/bin/env python3
"""plan_builder — i1001 的兩份計畫：篩選（只跑 A）與主跑（A＋C，R／K 巢狀在 A 之後），以及把兩者接起來的「天花板規則」。

這支在架構裡承重什麼：人類的第一條要求是「先測沒有 Vacant 的；滿分／沒有解不開的題，不要繼續測，換題目——要先知道
一般 agent 在沒裝 Vacant 時真的有題目解不開」。這條規則寫死在這裡、由篩選結果自動套用，不靠人在批次中間判斷：
  - 題庫（task banks）先各抽 10 題（MANIFEST 的 `screen_sample`，種子 20261001）只跑 A；
  - A 在那 10 題裡答對 ≥ 9 題 ⇒ 這個題庫在天花板、整個丟掉（記下來，不是安靜略過）；
  - 其餘題庫的**全部**題進主跑池（含被抽去篩選的 10 題——主跑重新跑 A，因為「因為 A 在這 10 題上表現差而選了這個題庫」
    本身會讓同一批 A 的結果偏低，重用它會把選擇偏誤灌進 C 對 A 的比較）；
  - LCB 池（C5 的 A 失敗題 93 ＋ 種子抽的 A 成功對照 40）不篩選：它們本來就是「A 失敗過」與「A 成功過」的已知題。
void 的篩選格先重跑一次（driver 負責）；仍然 void 的格**不算答對**（保守：題庫只在「看到答對」時才被丟）。
篩選沒跑完的題庫（停止檔、時限）：已看到的答對數 ≥ 9 就已經決定了（沒跑的格子只會讓數字不變或變大）⇒ 丟；
還有可能到 9（答對數＋沒跑的格數 ≥ 9）⇒ undecided、保留；到不了 9 ⇒ 保留。

誠實邊界：這條規則看的是「A 在 10 題上的答對數」，不是統計檢定；9/10 的門檻是規格定的，不是估出來的。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tui_lib import cell_name, deliverable_name, jsonl_rows  # noqa: E402

SCHEMA = "i1001.plan/1"
K_BANKS_DEFAULT = ("lcb_v1", "lcb_v2", "lcb_v3")     # 有可見驗收（check_* 格式）的題庫；任務題庫沒有（STAGING.md §四-3）
TASK_BANKS = ("dabench", "databench", "polyglot_py")
CEILING_N = 10
CEILING_THR = 9
AGENT_TIMEOUT_S = 1800


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _task_entry(t: dict, *, k_banks: tuple[str, ...], screened: bool, with_k: bool) -> dict:
    bank = t["bank"]
    return {"bank": bank, "id": t["id"], "dir": t["dir"], "role": t.get("role"),
            "deliverable": deliverable_name(bank, t.get("read_dir") or t["dir"], strict=True),
            "k": bool(with_k and bank in k_banks), "screened": screened}


def _shuffled(tasks: list[dict], seed: int, salt: str) -> list[dict]:
    rng = random.Random(f"{seed}-{salt}")
    out = sorted(tasks, key=lambda t: (t["bank"], t["id"]))
    rng.shuffle(out)
    return out


def screening_plan(index: list[dict], manifest: dict, seed: int) -> dict:
    """任務題庫各 10 題、只跑 A。名單取 MANIFEST 的 `screen_sample`（資料側已用 `random.Random(f"i1001-{seed}-{bank}")` 抽好）。"""
    want = {b: set(ids) for b, ids in (manifest.get("screen_sample") or {}).items()}
    tasks = [t for t in index if t["bank"] in want and t["id"] in want[t["bank"]]]
    got = {b: {t["id"] for t in tasks if t["bank"] == b} for b in want}
    missing = {b: sorted(want[b] - got[b]) for b in want if want[b] - got[b]}
    if missing:
        raise ValueError(f"screen_sample names tasks that are not in tasks_index: {missing}")
    entries = [_task_entry(t, k_banks=K_BANKS_DEFAULT, screened=True, with_k=False) for t in _shuffled(tasks, seed, "screen")]
    return {"schema": SCHEMA, "kind": "screen", "seed": seed, "arms": ["A"], "nested": [], "samples": [1],
            "k_banks": [], "tasks": entries, "ceiling_rule": {"n": CEILING_N, "pass_ge": CEILING_THR},
            "estimate": estimate(entries, ["A"], [], AGENT_TIMEOUT_S)}


def screen_outcomes(cells_dir: pathlib.Path, prefix: str, plan: dict) -> dict[str, list[dict]]:
    """每個篩選題的 A 結果：{pass: True|False|None(void/未跑), cell}。同一格有重跑（`v2`）時取最後一次且非 void 的。"""
    out: dict[str, list[dict]] = {}
    for t in plan["tasks"]:
        best = None
        for attempt in (1, 2, 3):                      # 最後一次跑的才算（第 2 次是 void 的重跑）
            name = cell_name(prefix, "A", t["bank"], t["id"], 1, attempt)
            d = cells_dir / name
            if not (d / "DONE").exists():
                continue
            try:
                meta = json.loads((d / "meta.json").read_text())
            except (OSError, ValueError):
                continue
            row = {"cell": name, "void": bool(meta.get("void")), "pass": None, "attempt": attempt}
            if not row["void"]:
                try:
                    sc = json.loads((d / "score.json").read_text().strip().splitlines()[-1])
                    row["pass"] = bool(sc.get("pass"))
                except (OSError, ValueError, IndexError):
                    row["void"], row["pass"] = True, None
            best = row
        out.setdefault(t["bank"], []).append({"task": t["id"], **(best or {"cell": None, "void": False, "pass": None})})
    return out


def ceiling_decision(outcomes: dict[str, list[dict]], expected: dict[str, int] | None = None,
                     thr: int = CEILING_THR) -> dict:
    """題庫 → {dropped, passes, n, voids, missing, unsolved, reason}。見模組 docstring。"""
    banks = {}
    for bank, rows in sorted(outcomes.items()):
        n_exp = (expected or {}).get(bank, len(rows))
        done = [r for r in rows if r.get("cell")]
        passes = sum(1 for r in done if r.get("pass") is True)
        voids = [r["task"] for r in done if r.get("pass") is None]
        missing = [r["task"] for r in rows if not r.get("cell")]
        unsolved = sorted(r["task"] for r in done if r.get("pass") is False)
        dropped = passes >= thr
        if dropped:
            reason = f"A passed {passes}/{n_exp} screened tasks (>= {thr}): the plain agent leaves (almost) nothing unsolved here; bank dropped"
        elif missing and passes + len(missing) >= thr:
            reason = (f"screening incomplete ({len(missing)} task(s) not run) and the bank could still reach {thr}/{n_exp}: "
                      f"undecided, bank kept")
        else:
            reason = (f"A passed {passes}/{n_exp} (< {thr}): {len(unsolved)} unsolved task(s) seen without Vacant; bank kept"
                      + (f"; {len(voids)} void cell(s) counted as not-pass" if voids else ""))
        banks[bank] = {"dropped": dropped, "passes": passes, "n": n_exp, "voids": voids, "missing": missing,
                       "unsolved": unsolved, "reason": reason}
    return {"schema": "i1001.ceiling_decision/1", "rule": {"n": CEILING_N, "pass_ge": thr}, "banks": banks,
            "dropped_banks": sorted(b for b, v in banks.items() if v["dropped"])}


def main_plan(index: list[dict], manifest: dict, decision: dict | None, seed: int, *,
              k_banks: tuple[str, ...] = K_BANKS_DEFAULT, nested: tuple[str, ...] = ("R", "K")) -> dict:
    dropped = set((decision or {}).get("dropped_banks") or [])
    screen = {b: set(ids) for b, ids in (manifest.get("screen_sample") or {}).items()}
    tasks: list[dict] = []
    for t in index:
        bank = t["bank"]
        if bank in dropped:
            continue
        if bank.startswith("lcb"):
            tasks.append(_task_entry(t, k_banks=k_banks, screened=False, with_k="K" in nested))
        elif bank in TASK_BANKS:
            tasks.append(_task_entry(t, k_banks=k_banks, screened=t["id"] in screen.get(bank, set()), with_k="K" in nested))
    order = _shuffled([{**t} for t in tasks], seed, "main")
    arms = ["A", "C"]
    return {"schema": SCHEMA, "kind": "main", "seed": seed, "arms": arms, "nested": list(nested), "samples": [1],
            "k_banks": list(k_banks), "tasks": order, "dropped_banks": sorted(dropped),
            "ceiling": decision, "estimate": estimate(order, arms, list(nested), AGENT_TIMEOUT_S)}


def estimate(tasks: list[dict], arms: list[str], nested: list[str], timeout_s: int) -> dict:
    """上限（不是預測）：每個單位最多幾段 session、全撞 1800 秒的話是幾個 session-分鐘。
    真實用量請用篩選階段量到的每段 session 平均牆鐘去乘（RUNBOOK §成本）。"""
    n = len(tasks)
    base = len(arms) * n
    r = (2 * n) if "R" in nested else 0
    k = (2 * sum(1 for t in tasks if t.get("k"))) if "K" in nested else 0
    mx = base + r + k
    return {"units": n, "first_sessions": base, "max_extra_R_sessions": r, "max_extra_K_sessions": k,
            "max_sessions": mx, "max_session_minutes": mx * timeout_s / 60.0,
            "note": "upper bound: every session hitting the wall limit; real use is far lower"}


def load_inputs(staged: pathlib.Path) -> tuple[list[dict], dict]:
    """tasks_index 的 `dir` 是 VM 上的路徑（/srv/eval/staged/…）；在別的機器上預覽計畫時讀不到，
    所以另給每題 `read_dir`＝<這個 staged 目錄>/<題庫>/<題>（只用來讀 hidden/expected.json，不寫進計畫）。"""
    index = json.loads((staged / "tasks_index.json").read_text())
    for t in index:
        t["read_dir"] = str(staged / t["bank"] / t["id"])
    return index, json.loads((staged / "MANIFEST.json").read_text())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("screen", "main"):
        p = sp.add_parser(name)
        p.add_argument("--staged", type=pathlib.Path, required=True, help="含 tasks_index.json 與 MANIFEST.json 的目錄")
        p.add_argument("--seed", type=int, default=20261001)
        p.add_argument("--out", type=pathlib.Path, required=True)
        if name == "main":
            p.add_argument("--cells", type=pathlib.Path, help="cells 目錄（讀篩選結果；省略＝不套天花板規則）")
            p.add_argument("--prefix", default="i1")
            p.add_argument("--screen-plan", type=pathlib.Path)
            p.add_argument("--decision-out", type=pathlib.Path)
    a = ap.parse_args(argv)
    index, manifest = load_inputs(a.staged)
    if a.cmd == "screen":
        plan = screening_plan(index, manifest, a.seed)
    else:
        decision = None
        if a.cells is not None:
            sp_plan = json.loads(a.screen_plan.read_text()) if a.screen_plan else screening_plan(index, manifest, a.seed)
            outcomes = screen_outcomes(a.cells, a.prefix, sp_plan)
            expected = {b: len(ids) for b, ids in (manifest.get("screen_sample") or {}).items()}
            decision = ceiling_decision(outcomes, expected)
            if a.decision_out:
                a.decision_out.write_text(json.dumps(decision, ensure_ascii=False, indent=1) + "\n")
        plan = main_plan(index, manifest, decision, a.seed)
    plan["source"] = {"tasks_index_sha256": sha256_file(a.staged / "tasks_index.json"),
                      "manifest_sha256": sha256_file(a.staged / "MANIFEST.json")}
    a.out.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {a.out}: kind={plan['kind']} units={len(plan['tasks'])} arms={plan['arms']} nested={plan['nested']}")
    print(json.dumps(plan["estimate"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
