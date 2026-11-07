#!/usr/bin/env python3
"""
G2.5 vq-el4.3：run_eval.py 第一項——G1 用自動擷取需求重跑，對照手寫版（離線、不呼叫模型）。

用法：
    python3 ops/reqloop/extract/run_eval.py --model glm53 [--json OUT]

對 G1 每題（ops/reqloop/g1/tasks/<t>/）：
- 手寫版：<t>/requirements.json
- 擷取版：ops/reqloop/extract/out/<t>.<model>.json
兩套需求各跑一遍 checks.py 的程式重算檢查，評 good/ 與各 bad_*/ 交付物。

判定口徑（與 ops/reqloop/g1/run_g1.py 一致）：
- good：任一 claim FAIL → FP（冤枉）；所有 required claim 恰好各一次 PASS → VERIFIED；
  否則（必要條目缺失／UNKNOWN）→ UNKNOWN（不是 PASS、也不是冤枉）。
- bad：任一 claim FAIL → 抓出（CAUGHT）；否則漏抓。
門禁（RLOOP_PLAN G2.5 第 1 項）：擷取版抓錯 ≥ 70% 且 good 0 冤枉。
退出碼：0 過、20 未過、2 有題缺擷取結果（fail-closed，不拿缺的當通過）。
成本：從 ~/dev/ops/state/vibe_calls.jsonl 讀該 model 的擷取呼叫；缺值 → UNKNOWN，絕不填 0。
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from vacant_network.reqloop.checks import run_requirement_checks  # noqa: E402
from vacant_network.reqloop.requirements import RequirementSet  # noqa: E402

GATE_CATCH_RATE = 0.70  # RLOOP_PLAN G2.5 第 1 項：39 份錯誤抓到 ≥ 70%


@dataclasses.dataclass(frozen=True)
class FakeItem:
    """測試用最小需求條目（good_verdict 只讀 id／required，duck-type）。"""

    id: str
    required: bool = True
    unverified: bool = False


def good_verdict(items: list, results: list) -> str:
    """good 交付物三態：FP（任一 FAIL）＞ UNKNOWN（必要未驗證）＞ VERIFIED（全 PASS）。"""
    if any(r.status == "FAIL" for r in results):
        return "FP"
    required = [it.id for it in items if it.required]
    if not required or len(required) != len(set(required)):
        return "UNKNOWN"
    for claim_id in required:
        matches = [r for r in results if r.claim_id == claim_id]
        if len(matches) != 1 or matches[0].status != "PASS":
            return "UNKNOWN"
    return "VERIFIED"


def bad_caught(results: list) -> bool:
    """bad 交付物：任一 claim FAIL 即抓出；PASS/UNKNOWN 都不算抓出。"""
    return any(r.status == "FAIL" for r in results)


def evaluate_task(task_dir: pathlib.Path, req_set: RequirementSet) -> dict:
    """一題一版需求：good 三態＋各 bad 抓錯。回傳結構化結果。"""
    out: dict = {"task_id": task_dir.name, "good": None, "bad": []}
    good_dir = task_dir / "good"
    if good_dir.is_dir():
        res = run_requirement_checks(task_dir, req_set, good_dir)
        out["good"] = good_verdict(req_set.items, res)
    for item in sorted(task_dir.iterdir()):
        if item.is_dir() and item.name.startswith("bad_"):
            res = run_requirement_checks(task_dir, req_set, item)
            out["bad"].append({"case": item.name, "caught": bad_caught(res)})
    return out


def read_extract_costs(vibe_calls: pathlib.Path, model: str, task_ids: list[str]) -> dict[str, dict]:
    """從 vibe_calls.jsonl 讀各題擷取成本（該 model、rc=0）；找不到→None（UNKNOWN，不填 0）。"""
    costs: dict[str, dict] = {t: {"calls": 0, "total_tokens": 0, "found": False} for t in task_ids}
    if not vibe_calls.is_file():
        return costs
    for line in vibe_calls.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("model") != model or row.get("rc") != 0:
            continue
        purpose = str(row.get("purpose", ""))
        for t in task_ids:
            if t in purpose:
                costs[t]["calls"] += 1
                costs[t]["total_tokens"] += int(row.get("total_tokens") or 0)
                costs[t]["found"] = True
    return costs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python3 ops/reqloop/extract/run_eval.py",
        description="G2.5 G1 重跑：擷取需求 vs 手寫需求（離線重算，不呼叫模型）",
    )
    ap.add_argument("--model", required=True, help="擷取模型別名（對應 out/<task>.<model>.json）")
    ap.add_argument("--g1", default=None, help="G1 任務目錄（預設 ops/reqloop/g1/tasks）")
    ap.add_argument("--out-dir", default=None, help="擷取結果目錄（預設 ops/reqloop/extract/out）")
    ap.add_argument("--vibe-calls", default="~/dev/ops/state/vibe_calls.jsonl", help="擷取成本紀錄")
    ap.add_argument("--json", default=None, help="同時寫機器可讀結果 json")
    a = ap.parse_args(argv)

    g1 = pathlib.Path(a.g1) if a.g1 else REPO_ROOT / "ops" / "reqloop" / "g1" / "tasks"
    out_dir = pathlib.Path(a.out_dir) if a.out_dir else REPO_ROOT / "ops" / "reqloop" / "extract" / "out"
    vibe_calls = pathlib.Path(a.vibe_calls).expanduser()

    task_dirs = sorted(p for p in g1.iterdir() if p.is_dir() and (p / "requirements.json").is_file())
    if not task_dirs:
        print(f"錯誤：{g1} 內未找到任何 G1 任務", file=sys.stderr)
        return 2

    print(f"# G2.5 G1 重跑對照（model={a.model}；離線重算、不呼叫模型）")
    print()
    rows: list[dict] = []
    missing: list[str] = []
    for t_dir in task_dirs:
        hand = RequirementSet.load(t_dir / "requirements.json")
        ext_path = out_dir / f"{t_dir.name}.{a.model}.json"
        if not ext_path.is_file():
            missing.append(t_dir.name)
            print(f"## {t_dir.name}：缺擷取結果（{ext_path}）——fail-closed，不計入")
            rows.append({"task": t_dir.name, "missing": True})
            continue
        ext = RequirementSet.load(ext_path)
        hand_res = evaluate_task(t_dir, hand)
        ext_res = evaluate_task(t_dir, ext)
        rows.append({
            "task": t_dir.name, "missing": False,
            "hand": hand_res, "ext": ext_res,
            "ext_items": len(ext.items),
            "ext_unverified": sum(1 for i in ext.items if i.unverified),
        })
        print(
            f"## {t_dir.name}：條目 手寫 {len(hand.items)}／擷取 {len(ext.items)}"
            f"（unverified {sum(1 for i in ext.items if i.unverified)}）"
        )
        print(f"- good：手寫 {hand_res['good']}、擷取 {ext_res['good']}")
        for hb, eb in zip(hand_res["bad"], ext_res["bad"]):
            mark = "✅" if eb["caught"] else "❌漏抓"
            print(f"- {hb['case']}：手寫 {'抓出' if hb['caught'] else '漏抓'}、擷取 {mark}")
        print()

    costs = read_extract_costs(vibe_calls, a.model, [r["task"] for r in rows if not r.get("missing")])
    print("## 擷取成本（vibe_calls.jsonl；缺值＝UNKNOWN，不填 0）")
    for r in rows:
        if r.get("missing"):
            continue
        c = costs.get(r["task"]) or {}
        if c.get("found"):
            print(f"- {r['task']}：{c['calls']} 次呼叫、{c['total_tokens']} tokens")
        else:
            print(f"- {r['task']}：UNKNOWN（無紀錄）")
    print()

    hand_caught = sum(b["caught"] for r in rows if not r.get("missing") for b in r["hand"]["bad"])
    ext_caught = sum(b["caught"] for r in rows if not r.get("missing") for b in r["ext"]["bad"])
    total_bad = sum(len(r["hand"]["bad"]) for r in rows if not r.get("missing"))
    hand_fp = sum(1 for r in rows if not r.get("missing") and r["hand"]["good"] == "FP")
    ext_fp = sum(1 for r in rows if not r.get("missing") and r["ext"]["good"] == "FP")
    ext_verified = sum(1 for r in rows if not r.get("missing") and r["ext"]["good"] == "VERIFIED")
    total_good = sum(1 for r in rows if not r.get("missing") and r["ext"]["good"] in ("VERIFIED", "FP", "UNKNOWN"))

    print("## 門禁指標彙整")
    print(f"- 錯誤交付物：{total_bad}；抓錯 手寫 {hand_caught}/{total_bad}、擷取 {ext_caught}/{total_bad}")
    print(f"- 正確交付物：{total_good}；冤枉 手寫 {hand_fp}、擷取 {ext_fp}（擷取 VERIFIED {ext_verified}/{total_good}）")

    if missing:
        print(f"❌ 門禁判定：FAIL（缺擷取結果：{', '.join(missing)}）")
        if a.json:
            _write_json(pathlib.Path(a.json), rows, {"gate": "FAIL", "missing": missing})
        return 2

    catch_rate = ext_caught / total_bad if total_bad else 0.0
    gate = (total_good > 0 and ext_fp == 0 and catch_rate >= GATE_CATCH_RATE)
    print(f"- 擷取版抓錯率 {catch_rate * 100:.1f}%（門檻 ≥ {GATE_CATCH_RATE * 100:.0f}%）、冤枉 {ext_fp}（門檻 0）")
    if gate:
        print("🏆 G2.5 第 1 項門禁：PASS（擷取需求在 G1 上達標）")
    else:
        print("❌ G2.5 第 1 項門禁：FAIL（未達抓錯門檻或存在冤枉——改擷取方法，不寫報告）")
    if a.json:
        _write_json(pathlib.Path(a.json), rows,
                    {"gate": "PASS" if gate else "FAIL", "catch_rate": catch_rate,
                     "ext_caught": ext_caught, "total_bad": total_bad, "ext_fp": ext_fp})
    return 0 if gate else 20


def _write_json(path: pathlib.Path, rows: list[dict], gate_info: dict) -> None:
    doc = {"rows": rows, **gate_info}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
