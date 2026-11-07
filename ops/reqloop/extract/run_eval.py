#!/usr/bin/env python3
"""
G2.5 vq-el4.3：run_eval.py 第一項——G1 用自動擷取需求重跑，對照手寫版（離線、不呼叫模型）。

用法：
    python3 ops/reqloop/extract/run_eval.py --all                # 全三項整合驗收（G1 重跑＋REAL14＋PHASE3）
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
import hashlib
import json
import pathlib
import re
import shutil
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from vacant_network.reqloop.checks import run_requirement_checks  # noqa: E402
from vacant_network.reqloop.extract import (  # noqa: E402
    GlmClient,
    build_requirement_set,
    extract_requirements,
    build_task_prompt,
    csv_preview,
    json_preview,
    parse_model_output,
    ExtractError,
)
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


def _extraction_failure(ext_path: pathlib.Path) -> str | None:
    """擷取結果檔的 report 有 extract_error／parse_error → 回傳原因；否則 None。

    擷取失敗（glm rc=4：deadline／token_limit／turn_limit 等）是「該題沒有產出需求」，
    與「產出了需求但沒抓出」是兩件事；對照表必須點名，不得讀成模型沒抓出（r1197）。
    """
    try:
        raw = json.loads(ext_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "擷取結果檔無法讀取"
    rep = raw.get("report") or {}
    return rep.get("extract_error") or rep.get("parse_error")


def run_models_comparison(models: list[str], g1: pathlib.Path, out_dir: pathlib.Path,
                          vibe_calls: pathlib.Path) -> dict:
    """多模型對照（vq-el4.6）：每模型各跑 evaluate_task＋read_extract_costs（離線、不呼叫模型）。

    結案口徑（2026-11-07 裁決）：正式對照表為 3 模型 glm53／glm53flash／deepseek41；
    證據 ops/reqloop/extract/out/eval_g1_compare_3m.json（glm53 39/39 100% FP0 門禁 PASS、
    glm53flash 16/39 41% FAIL、deepseek41 23/39 59% FP1 FAIL）；gemma 為 1004 本地端點、
    非 Vibe CLI 模型——依指示不繞過 glm 直呼 vibe、不自建 gemma client、不入本表。

    每模型門禁：抓錯 ≥ 70% 且 0 冤枉且擷取完整；缺擷取結果→MISSING（fail-closed）；
    任一題擷取失敗（report.extract_error／parse_error）→FAIL（擷取不完整；該題計未抓出，
    但 extract_failed 點名原因，不得讀成模型沒抓出）；任一題成本缺值 → calls/tokens＝None。
    """
    task_dirs = sorted(p for p in g1.iterdir() if p.is_dir() and (p / "requirements.json").is_file())
    ids = [p.name for p in task_dirs]
    out_models: dict[str, dict] = {}
    for model in models:
        caught = fp = total_bad = total_good = 0
        missing = [t for t in ids if not (out_dir / f"{t}.{model}.json").is_file()]
        extract_failed: dict[str, str] = {}
        for t_dir in task_dirs:
            if t_dir.name in missing:
                continue
            ext_path = out_dir / f"{t_dir.name}.{model}.json"
            reason = _extraction_failure(ext_path)
            if reason:
                extract_failed[t_dir.name] = reason
            res = evaluate_task(t_dir, RequirementSet.load(ext_path))
            total_bad += len(res["bad"])
            caught += sum(1 for b in res["bad"] if b["caught"])
            g = res["good"]
            if g in ("VERIFIED", "FP", "UNKNOWN"):
                total_good += 1
            if g == "FP":
                fp += 1
        costs = read_extract_costs(vibe_calls, model, ids)
        all_found = bool(ids) and all(costs[t]["found"] for t in ids)
        catch_rate = caught / total_bad if total_bad else 0.0
        if missing:
            gate = "MISSING"
        elif extract_failed:
            gate = "FAIL"     # 擷取不完整＝未達標（不得 PASS）
        else:
            gate = "PASS" if (total_good > 0 and fp == 0 and catch_rate >= GATE_CATCH_RATE) else "FAIL"
        out_models[model] = {
            "bad_caught": caught, "total_bad": total_bad, "caught_pct": round(catch_rate * 100, 1),
            "good_fp": fp, "total_good": total_good,
            "calls": sum(costs[t]["calls"] for t in ids) if all_found else None,
            "tokens": sum(costs[t]["total_tokens"] for t in ids) if all_found else None,
            "missing": missing, "files": len(ids) - len(missing),
            "extract_failed": extract_failed, "gate": gate}
    return {"models": out_models}


def print_models_table(result: dict) -> None:
    print("# G2.5 多模型對照（離線重算、不呼叫模型）")
    print(f"{'Model':<14}{'Bad Caught':<14}{'Caught %':<11}{'Extract OK':<12}"
          f"{'Good FP':<10}{'Total Good':<13}{'Calls':<9}{'Tokens'}")
    for model, s in result["models"].items():
        calls = "UNKNOWN" if s["calls"] is None else str(s["calls"])
        tokens = "UNKNOWN" if s["tokens"] is None else str(s["tokens"])
        files = s.get("files", 0)
        extract_ok = f"{files - len(s.get('extract_failed', {}))}/{files}"
        print(f"{model:<14}{s['bad_caught']}/{s['total_bad']:<10}{s['caught_pct']:.1f}%{'':<5}"
              f"{extract_ok:<12}{s['good_fp']:<10}{s['total_good']:<13}{calls:<9}{tokens}")
    for model, s in result["models"].items():
        if s["missing"]:
            print(f"## {model}：缺擷取結果（fail-closed）：{', '.join(s['missing'])}")
    for model, s in result["models"].items():
        for t, reason in s.get("extract_failed", {}).items():
            print(f"## {model} 擷取失敗（fail-closed、計未抓出）：{t}：{reason.splitlines()[0][:120]}")
    print("門禁：" + "; ".join(f"{m} {s['gate']}" for m, s in result["models"].items())
          + f"（抓錯 ≥ {GATE_CATCH_RATE * 100:.0f}% 且 0 冤枉且擷取完整；成本缺值＝UNKNOWN，不填 0）")


def write_models_json(path: pathlib.Path, result: dict, g1: pathlib.Path, out_dir: pathlib.Path) -> None:
    doc = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "g1": str(g1), "out_dir": str(out_dir), **result}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ── --all：G2.5 全三項整合驗收（vq-el4 結案指令）────────────────────────────
# 依序 run_phase1（G1 重跑）→ run_phase2（REAL14）→ run_phase3（localized 修復報告）；
# 三項全過 → 0，任一未過 → 20。全程離線重算（phase2 重用 out/real14 快取、
# phase3 接續 out/phase3/progress.json）；成本缺值＝UNKNOWN，絕不填 0。


def run_phase1(model: str = "glm53",
               g1: pathlib.Path | None = None,
               out_dir: pathlib.Path | None = None,
               vibe_calls: pathlib.Path | None = None,
               json_out: pathlib.Path | None = None) -> int:
    """item 1：G1 重跑（擷取需求 vs 手寫需求；離線重算、不呼叫模型）。

    退出碼：0 門禁 PASS；20 門禁 FAIL；2 缺任務或缺擷取結果（fail-closed）。
    """
    g1 = pathlib.Path(g1) if g1 else REPO_ROOT / "ops" / "reqloop" / "g1" / "tasks"
    out_dir = pathlib.Path(out_dir) if out_dir else REPO_ROOT / "ops" / "reqloop" / "extract" / "out"
    vibe_calls = (pathlib.Path(vibe_calls).expanduser() if vibe_calls
                  else pathlib.Path("~/dev/ops/state/vibe_calls.jsonl").expanduser())
    json_out = pathlib.Path(json_out) if json_out else None

    task_dirs = sorted(p for p in g1.iterdir() if p.is_dir() and (p / "requirements.json").is_file())
    if not task_dirs:
        print(f"錯誤：{g1} 內未找到任何 G1 任務", file=sys.stderr)
        return 2

    print(f"# G2.5 G1 重跑對照（model={model}；離線重算、不呼叫模型）")
    print()
    rows: list[dict] = []
    missing: list[str] = []
    for t_dir in task_dirs:
        hand = RequirementSet.load(t_dir / "requirements.json")
        ext_path = out_dir / f"{t_dir.name}.{model}.json"
        if not ext_path.is_file():
            missing.append(t_dir.name)
            print(f"## {t_dir.name}：缺擷取結果（{ext_path}）——fail-closed，不計入")
            rows.append({"task": t_dir.name, "missing": True})
            continue
        ext = RequirementSet.load(ext_path)
        hand_res = evaluate_task(t_dir, hand)
        ext_res = evaluate_task(t_dir, ext)
        ext_err = _extraction_failure(ext_path)
        rows.append({
            "task": t_dir.name, "missing": False,
            "hand": hand_res, "ext": ext_res,
            "ext_items": len(ext.items),
            "ext_unverified": sum(1 for i in ext.items if i.unverified),
            "ext_error": ext_err,
        })
        print(
            f"## {t_dir.name}：條目 手寫 {len(hand.items)}／擷取 {len(ext.items)}"
            f"（unverified {sum(1 for i in ext.items if i.unverified)}）"
        )
        if ext_err:
            print(f"- ⚠️ 擷取失敗（fail-closed、計未抓出）：{ext_err.splitlines()[0][:120]}")
        print(f"- good：手寫 {hand_res['good']}、擷取 {ext_res['good']}")
        for hb, eb in zip(hand_res["bad"], ext_res["bad"]):
            mark = "✅" if eb["caught"] else "❌漏抓"
            print(f"- {hb['case']}：手寫 {'抓出' if hb['caught'] else '漏抓'}、擷取 {mark}")
        print()

    costs = read_extract_costs(vibe_calls, model, [r["task"] for r in rows if not r.get("missing")])
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

    found_cost = {t: c for t, c in costs.items() if c.get("found")}
    cost_info = {
        "calls": sum(c["calls"] for c in found_cost.values()) if found_cost else None,
        "tokens": sum(c["total_tokens"] for c in found_cost.values()) if found_cost else None,
        "unknown_tasks": sorted(t for t, c in costs.items() if not c.get("found")),
    }

    if missing:
        print(f"❌ 門禁判定：FAIL（缺擷取結果：{', '.join(missing)}）")
        if json_out is not None:
            _write_json(json_out, rows, {"gate": "FAIL", "missing": missing, "cost": cost_info})
        return 2

    catch_rate = ext_caught / total_bad if total_bad else 0.0
    gate = (total_good > 0 and ext_fp == 0 and catch_rate >= GATE_CATCH_RATE)
    print(f"- 擷取版抓錯率 {catch_rate * 100:.1f}%（門檻 ≥ {GATE_CATCH_RATE * 100:.0f}%）、冤枉 {ext_fp}（門檻 0）")
    if gate:
        print("🏆 G2.5 第 1 項門禁：PASS（擷取需求在 G1 上達標）")
    else:
        print("❌ G2.5 第 1 項門禁：FAIL（未達抓錯門檻或存在冤枉——改擷取方法，不寫報告）")
    if json_out is not None:
        _write_json(json_out, rows,
                    {"gate": "PASS" if gate else "FAIL", "catch_rate": catch_rate,
                     "ext_caught": ext_caught, "total_bad": total_bad, "ext_fp": ext_fp,
                     "cost": cost_info})
    return 0 if gate else 20


def _print_all_dashboard(j1: pathlib.Path, j2: pathlib.Path, j3: pathlib.Path,
                         rc1: int, rc2: int, rc3: int) -> bool:
    """印出三項整合總結看板（各項指標／門禁狀態／成本）；回傳三項是否全過。"""
    def _doc(p: pathlib.Path) -> dict:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _gate(rc: int) -> str:
        if rc == 0:
            return "PASS"
        return "FAIL（rc=2，fail-closed／缺值）" if rc == 2 else "FAIL"

    def _cost(c: object) -> str:
        if not isinstance(c, dict) or not c:
            return "UNKNOWN（缺值不填 0）"
        labels = {"calls": "呼叫", "repair_sessions": "repair_sessions",
                  "model_calls": "model_calls", "tokens": "tokens"}
        parts = [f"{labels[k]} {c[k] if c[k] is not None else 'UNKNOWN'}"
                 for k in ("calls", "repair_sessions", "model_calls", "tokens") if k in c]
        if c.get("unknown_tasks"):
            parts.append(f"{len(c['unknown_tasks'])} 題 UNKNOWN")
        return "、".join(parts) if parts else "UNKNOWN"

    d1, d2, d3 = _doc(j1), _doc(j2), _doc(j3)
    bar = "=" * 64
    print()
    print(bar)
    print("📋 G2.5 全三項整合總結看板（各項指標／門禁狀態／成本）")
    print(bar)
    print(f"① G1 重跑（擷取 vs 手寫）：門禁 {_gate(rc1)}")
    if d1.get("missing"):
        print(f"   指標：缺擷取 {len(d1['missing'])} 題（{', '.join(map(str, d1['missing']))}）")
    else:
        print(f"   指標：抓錯 {d1.get('ext_caught')}/{d1.get('total_bad')}"
              f"（率 {(d1.get('catch_rate') or 0) * 100:.1f}%，門檻 ≥ {GATE_CATCH_RATE * 100:.0f}%）、"
              f"冤枉 {d1.get('ext_fp')}（門檻 0）")
    print(f"   成本：{_cost(d1.get('cost'))}")
    print(f"② REAL14（14 份真實草稿、自動擷取）：門禁 {_gate(rc2)}")
    print(f"   指標：抓錯 {d2.get('caught')}/{d2.get('total_bad')}（門檻 ≥ {MIN_CATCH_BAD}）、"
          f"冤枉 {d2.get('false_acc')}/{d2.get('total_good')}（門檻 ≤ {MAX_FALSE_GOOD}）"
          + (f"、{d2['errors']} cell 錯誤" if d2.get("errors") else ""))
    print(f"   成本：{_cost(d2.get('cost'))}")
    print(f"③ PHASE3（錯草稿＋localized 修復＋獨立 scorer）：門禁 {_gate(rc3)}")
    print(f"   指標：fixed {d3.get('fixed')}、unresolved {d3.get('unresolved')}、"
          f"rejected {d3.get('rejected')}、right_to_wrong {d3.get('right_to_wrong')}、"
          f"held {d3.get('held')}"
          + (f"、error {d3['errors']}" if d3.get("errors") else ""))
    print(f"   成本：{_cost(d3.get('cost'))}")
    print(bar)
    all_ok = rc1 == 0 and rc2 == 0 and rc3 == 0
    if all_ok:
        print("🏆 G2.5 全三項門禁整合驗收：PASS")
    else:
        failed = [n for n, rc in (("G1 重跑", rc1), ("REAL14", rc2), ("PHASE3", rc3)) if rc != 0]
        print(f"❌ G2.5 全三項門禁整合驗收：FAIL（未過：{'、'.join(failed)}）")
    return all_ok


def run_all(model: str = "glm53",
            g1: pathlib.Path | None = None,
            out_dir: pathlib.Path | None = None,
            vibe_calls: pathlib.Path | None = None,
            base: pathlib.Path | None = None,
            include_good: bool = False,
            provider: str | None = None,
            p3_model: str | None = None,
            max_rounds: int | None = None,
            timeout_s: float | None = None,
            p3_out: pathlib.Path | None = None,
            p3_req_dir: pathlib.Path | None = None,
            limit: int | None = None) -> int:
    """--all：G2.5 全三項整合驗收，依序 G1 重跑 → REAL14 → PHASE3（離線重算）。

    三項全過（rc 皆 0）→ 0；任一未過 → 20。逐項 JSON 落 <out-dir>/all/ 供複核；
    成本由各項自讀（vibe_calls／raw usage），缺值＝UNKNOWN，絕不填 0。
    """
    provider = PHASE3_PROVIDER if provider is None else provider
    p3_model = PHASE3_MODEL if p3_model is None else p3_model
    max_rounds = PHASE3_MAX_ROUNDS if max_rounds is None else max_rounds
    timeout_s = PHASE3_TIMEOUT_S if timeout_s is None else timeout_s
    base_dir = pathlib.Path(out_dir) if out_dir else REPO_ROOT / "ops" / "reqloop" / "extract" / "out"
    all_dir = base_dir / "all"
    all_dir.mkdir(parents=True, exist_ok=True)
    j1, j2, j3 = all_dir / "phase1.json", all_dir / "phase2.json", all_dir / "phase3.json"
    rc1 = run_phase1(model=model, g1=g1, out_dir=out_dir,
                     vibe_calls=vibe_calls, json_out=j1)
    rc2 = run_phase2(model=model, base=base, vibe_calls=vibe_calls, json_out=j2)
    rc3 = run_phase3(base=base, include_good=include_good, extract_model=model,
                     provider=provider, model=p3_model, max_rounds=max_rounds,
                     timeout_s=timeout_s, out_root=p3_out, req_dir=p3_req_dir,
                     json_out=j3, limit=limit)
    all_ok = _print_all_dashboard(j1, j2, j3, rc1, rc2, rc3)
    return 0 if all_ok else 20


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python3 ops/reqloop/extract/run_eval.py",
        description="G2.5 G1 重跑：擷取需求 vs 手寫需求（離線重算，不呼叫模型）",
    )
    ap.add_argument("--model", default="glm53", help="擷取模型別名（對應 out/<task>.<model>.json；預設 glm53）")
    ap.add_argument("--models", default=None,
                    help="多模型對照（逗號分隔，如 --models glm53,glm53flash）；輸出一張整合對照表（vq-el4.6）")
    ap.add_argument("--g1", default=None, help="G1 任務目錄（預設 ops/reqloop/g1/tasks）")
    ap.add_argument("--out-dir", default=None, help="擷取結果目錄（預設 ops/reqloop/extract/out）")
    ap.add_argument("--vibe-calls", default="~/dev/ops/state/vibe_calls.jsonl", help="擷取成本紀錄")
    ap.add_argument("--json", default=None, help="同時寫機器可讀結果 json")
    ap.add_argument("--phase2", action="store_true",
                    help="item 2：14 份真實草稿（effects2_20261106，9 壞／5 好）＋自動擷取需求")
    ap.add_argument("--phase3", action="store_true",
                    help="item 3（vq-el4.5）：9 份錯草稿＋自動擷取需求＋localized 修復＋獨立 scorer")
    ap.add_argument("--all", action="store_true",
                    help="執行 G2.5 全三項整合驗收：G1 重跑、真實 14 份、localized 修復報告")
    ap.add_argument("--effects2", default=None,
                    help="effects2 目錄（預設 ~/dev/ops/effects2_20261106）")
    ap.add_argument("--include-good", action="store_true",
                    help="phase3 連 5 份好草稿也跑（monitor right_to_wrong；預設只跑 9 錯）")
    ap.add_argument("--p3-provider", default=PHASE3_PROVIDER,
                    help="phase3 修復 pi provider（預設 lms1004nothink，effect_manifest 釘住）")
    ap.add_argument("--p3-model", default=PHASE3_MODEL,
                    help="phase3 修復 pi model（預設 gemma-4-12b-it-qat，與手寫 9/9 同模型）")
    ap.add_argument("--p3-rounds", type=int, default=PHASE3_MAX_ROUNDS, help="phase3 每 cell 修復輪數上限")
    ap.add_argument("--p3-timeout", type=float, default=PHASE3_TIMEOUT_S, help="phase3 單輪 wall timeout（秒）")
    ap.add_argument("--p3-out", default=None,
                    help="phase3 工作目錄（freeze/progress/tasks/repair；預設 ops/reqloop/extract/out/phase3）")
    ap.add_argument("--p3-req-dir", default=None,
                    help="自動擷取需求目錄（預設 ops/reqloop/extract/out/real14）")
    ap.add_argument("--limit", type=int, default=None, help="phase3 只跑前 N 格（冒煙用；不宣稱效果）")
    a = ap.parse_args(argv)

    if a.all:
        return run_all(model=a.model,
                       g1=pathlib.Path(a.g1) if a.g1 else None,
                       out_dir=pathlib.Path(a.out_dir) if a.out_dir else None,
                       vibe_calls=pathlib.Path(a.vibe_calls).expanduser(),
                       base=pathlib.Path(a.effects2).expanduser() if a.effects2 else None,
                       include_good=a.include_good,
                       provider=a.p3_provider, p3_model=a.p3_model,
                       max_rounds=a.p3_rounds, timeout_s=a.p3_timeout,
                       p3_out=pathlib.Path(a.p3_out).expanduser() if a.p3_out else None,
                       p3_req_dir=pathlib.Path(a.p3_req_dir).expanduser() if a.p3_req_dir else None,
                       limit=a.limit)

    if a.phase2:
        return run_phase2(model=a.model,
                          base=pathlib.Path(a.effects2).expanduser() if a.effects2 else None,
                          json_out=pathlib.Path(a.json) if a.json else None)

    if a.phase3:
        return run_phase3(
            base=pathlib.Path(a.effects2).expanduser() if a.effects2 else None,
            include_good=a.include_good,
            extract_model=a.model,
            provider=a.p3_provider, model=a.p3_model,
            max_rounds=a.p3_rounds, timeout_s=a.p3_timeout,
            out_root=pathlib.Path(a.p3_out).expanduser() if a.p3_out else None,
            req_dir=pathlib.Path(a.p3_req_dir).expanduser() if a.p3_req_dir else None,
            json_out=pathlib.Path(a.json) if a.json else None,
            limit=a.limit)

    g1 = pathlib.Path(a.g1) if a.g1 else REPO_ROOT / "ops" / "reqloop" / "g1" / "tasks"
    out_dir = pathlib.Path(a.out_dir) if a.out_dir else REPO_ROOT / "ops" / "reqloop" / "extract" / "out"
    vibe_calls = pathlib.Path(a.vibe_calls).expanduser()

    task_dirs = sorted(p for p in g1.iterdir() if p.is_dir() and (p / "requirements.json").is_file())
    if not task_dirs:
        print(f"錯誤：{g1} 內未找到任何 G1 任務", file=sys.stderr)
        return 2

    if a.models:
        models = [m.strip() for m in a.models.split(",") if m.strip()]
        if not models:
            print("錯誤：--models 為空", file=sys.stderr)
            return 2
        result = run_models_comparison(models, g1, out_dir, vibe_calls)
        print_models_table(result)
        if a.json:
            write_models_json(pathlib.Path(a.json), result, g1, out_dir)
        gates = [s["gate"] for s in result["models"].values()]
        if "MISSING" in gates:
            return 2
        return 0 if all(g == "PASS" for g in gates) else 20

    return run_phase1(model=a.model, g1=g1, out_dir=out_dir, vibe_calls=vibe_calls,
                      json_out=pathlib.Path(a.json) if a.json else None)


def _write_json(path: pathlib.Path, rows: list[dict], gate_info: dict) -> None:
    doc = {"rows": rows, **gate_info}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# item 2（vq-el4.4）：14 份真實草稿（effects2_20261106，9 壞／5 好）
# 門禁（RLOOP_PLAN 第 91 行）：抓錯 ≥ 5/9、冤枉 ≤ 1/5。
# 紅線：requirements 只用自動擷取的（out/real14/），不讀各 task 的手寫
# requirements.json；1753 本批排除。
# ---------------------------------------------------------------------------

REAL14_BASE_DEFAULT = pathlib.Path("~/dev/ops/effects2_20261106").expanduser()
SNAPSHOT_SETS = ("smoke", "smoke_e013", "smoke_e014")
MIN_CATCH_BAD = 5      # RLOOP_PLAN：抓錯 ≥ 5/9
MAX_FALSE_GOOD = 1     # RLOOP_PLAN：冤枉 ≤ 1/5


@dataclasses.dataclass(frozen=True)
class Real14Cell:
    cell: str              # before_after.json 的 draft 名（如 dab_039-pi-C）
    role: str              # "bad" | "good"
    task_dir: pathlib.Path
    draft_dir: pathlib.Path


# 與 checks.py dispatch 表逐字對應（單一事實來源；tests/test_reqloop_extract_run_eval.py 雙向比對）。
RECOMPUTE_TYPES = (
    "count_if", "zcount3", "mean_int_col", "max_row_first", "pearson2",
    "col_stats", "null_count", "mode_col", "unique_count", "col_max",
    "cond_rate", "group_ratio_stat", "fee_ids_lookup", "scheme_fee_avg",
)

RECOMPUTE_RULES = """【重算規則語法（kv_recomputed / plain_recomputed 的 recompute.type 只能是以下；欄位名、型別、巢狀結構逐字照抄）】
kv_recomputed params：{"key": "答案檔鍵名", "data_file": "資料檔名", "recompute": {…}}（選填 "atol": 容差）
plain_recomputed params：{"data_file": "資料檔名", "recompute": {…}}
- {"type": "count_if", "col": "cases", "eq": 3}                          col 等於 eq 的行數
- {"type": "zcount3", "col": "value"}                                     |z|>3 的數值個數（母體標準差）
- {"type": "mean_int_col", "col": "No. of cases"}                         col 整數儲存格的均值（Null/空白忽略；預設四捨五入為整數）
- {"type": "max_row_first", "sel_col": "max_wind", "out_col": "cost"}     sel_col 最大那行（平手取檔案序首列）的 out_col 值
- {"type": "pearson2", "col_a": "a", "col_b": "b"}                        兩欄 Pearson 相關係數
- {"type": "col_stats", "col": "importance.score", "stat": "kurtosis"}    stat 只能是 mean|median|sd|skewness|kurtosis（kurtosis=超额峰度、pandas 口徑）
- {"type": "null_count", "col": "min_p"}                                 col 的 null 儲存格數（預設 null 集 ''/none/null/nan/na/n-a；選填 null_values 字串列表）
- {"type": "mode_col", "col": "hour"}                                    col 出現次數最多的值
- {"type": "unique_count", "col": "merchant_id"}                         col 去重計數
- {"type": "col_max", "col": "eur_amount"}                               col 最大值
- {"type": "cond_rate", "where": [{"col": "year", "op": "eq", "value": 2023}],
   "num_where": [{"col": "has_fraudulent_dispute", "op": "eq", "value": true}]}    比率＝|where ∩ num_where| / |where|
- {"type": "group_ratio_stat", "group_col": "g", "sum_col": "amount", "num_where": […], "stat": "min", "out": "val"}
  分組加總比率取 min/max（選填 num_sum_col/denom_sum_col/where/percent；out 可為 val 或 group）
- {"type": "fee_ids_lookup", "fees_file": "data/fees.json", "merchants_file": "data/merchant_data.json",
   "merchant": "商戶名", "year": 2024, "month": 6}                      該商戶該自然月適用 fee ID 集合（答案＝逗號分隔數字）
- {"type": "scheme_fee_avg", "scheme": "GlobalCard", "is_credit": true, "amount": 10}
  平均費率＝mean(fixed_amount + rate * amount / 10000)（null 欄位＝wildcard）
條件 op（where/num_where）：eq / ne / gt / ge / lt / le；value 可為數字、字串、或欄位名（欄位對欄位比較）。
題目文字若明言四捨五入（round to N decimals），在對應 recompute 加 "round": N。
列表裡沒有的 type＝檢查器無法驗證＝該條目 UNKNOWN；不要自創 type。"""


def derive_real14_cells(base: pathlib.Path) -> list[Real14Cell]:
    """由 effects2 before_after.json 推導 14 份真實草稿（9 壞／5 好）。

    bad ⇔ before_d38d2eb2 任一臂的 fixed/unresolved 非空（修復前就有檢查缺口）；
    good ⇔ 無缺口。1753 本批排除。任一 cell 在 snapshot 缺 task/draft → fail-closed。
    """
    ba_path = base / "before_after.json"
    if not ba_path.is_file():
        raise FileNotFoundError(f"before_after.json 缺失：{ba_path}")
    ba = json.loads(ba_path.read_text(encoding="utf-8"))
    g2 = base / "snapshot" / "ops" / "reqloop" / "g2"
    roles: dict[str, str] = {}
    for rec in ba.get("cells", []):
        draft = str(rec.get("draft", ""))
        if not draft or "1753" in draft:
            continue
        gaps: set[str] = set()
        for policy, d in (rec.get("before_d38d2eb2") or {}).items():
            if isinstance(d, dict):
                gaps.update(d.get("fixed") or [])
                gaps.update(d.get("unresolved") or [])
        role = "bad" if gaps else "good"
        if draft in roles and roles[draft] != role:
            raise RuntimeError(f"cell {draft} 跨臂角色不一致：{roles[draft]} vs {role}")
        roles[draft] = role
    cells: list[Real14Cell] = []
    missing: list[str] = []
    for cell_name in sorted(roles):
        found = None
        task_id = _task_id_from_cell(cell_name)
        for s in SNAPSHOT_SETS:
            for cand in (cell_name, task_id):
                t_dir = g2 / s / cand / "task"
                d_dir = g2 / s / cand / "draft"
                if t_dir.is_dir() and d_dir.is_dir():
                    found = (t_dir, d_dir)
                    break
            if found is not None:
                break
        if found is None:
            missing.append(cell_name)
            continue
        cells.append(Real14Cell(
            cell=cell_name, role=roles[cell_name],
            task_dir=found[0], draft_dir=found[1]))
    if missing:
        raise RuntimeError(f"snapshot 缺 cell（fail-closed，不靜默少算）：{missing}")
    if not (sum(1 for c in cells if c.role == "bad") >= 1
            and sum(1 for c in cells if c.role == "good") >= 1):
        raise RuntimeError(f"cell 集合異常：bad/good 不能為空（cells={len(cells)}）")
    return cells


def _task_id_from_cell(cell: str) -> str:
    """dabstep-10-pi-C → dabstep-10；dab_039-pi-C → dab_039。"""
    return re.sub(r"-pi-(A|CB|C)$", "", cell)


def load_cell_request_text(task_dir: pathlib.Path, task_id: str,
                           real14_dir: pathlib.Path) -> str:
    """使用者原文：優先用任務 request.md；無則（3 個 dabstep factoid cell）用
    real14/<task_id>.request.md（來源與 sha 見該檔頭部 provenance）。兩者皆無 → fail-closed。

    argon 20261107_1248：任務目錄的 contract.md（agent 拿到的公開交付規格：寫到哪個檔、
    什麼格式）一併附上。首跑漏了它，擷取模型只能猜交付檔名（answer、@x[y]、
    /app/answer.txt），草稿明明有 answer.txt 也全判「答案檔不存在」——real14 首跑
    9 份抓錯中 6 份、4 份冤枉全部是這個假象。contract.md 不含答案、不含 hidden。"""
    primary = task_dir / "request.md"
    fallback = real14_dir / f"{task_id}.request.md"
    if primary.is_file():
        text = primary.read_text(encoding="utf-8")
    elif fallback.is_file():
        text = fallback.read_text(encoding="utf-8")
    else:
        raise FileNotFoundError(
            f"request.md 與 {fallback} 皆無（fail-closed；不猜使用者原文）")
    contract = task_dir / "contract.md"
    if contract.is_file():
        c_text = contract.read_text(encoding="utf-8").strip()
        if c_text and c_text not in text:
            text = text.rstrip() + "\n\n" + c_text + "\n"
    return text


def task_data_files(task_dir: pathlib.Path) -> list[pathlib.Path]:
    """任務資料檔（確定性順序、有上限）：data/*.csv ≤2、data/*.json ≤1、data/*.md ≤1；
    無 data/ 子目錄時退回頂層 *.csv（G1 形）。"""
    d = task_dir / "data"
    if d.is_dir():
        csvs = sorted(d.glob("*.csv"))[:2]
        jsons = sorted(d.glob("*.json"))[:1]
        mds = sorted(d.glob("*.md"))[:1]
        return [p for p in csvs + jsons + mds]
    return sorted(task_dir.glob("*.csv"))[:2]


def _data_preview(path: pathlib.Path) -> str:
    if path.suffix == ".csv":
        return csv_preview(path.read_text(encoding="utf-8", errors="replace"))
    if path.suffix == ".json":
        return json_preview(path.read_text(encoding="utf-8", errors="replace"))
    return path.read_text(encoding="utf-8", errors="replace")[:1500]


def build_phase2_prompt(user_text: str, data_names: list[str],
                        previews: dict[str, str]) -> str:
    """G2 形擷取 prompt＝G1 骨架（build_task_prompt）＋重算規則語法。

    語法表由 checks.py dispatch 表派生（單一事實來源）：模型自創型別會被
    UNKNOWN 掉，不如把合法型別與欄位形狀一次講明。
    """
    data_file = "; ".join(data_names) if data_names else None
    data_preview = "\n\n".join(
        f"--- {n} ---\n{p}" for n, p in previews.items()) if previews else ""
    base = build_task_prompt(user_text, data_file=data_file, data_preview=data_preview)
    return base + "\n\n" + RECOMPUTE_RULES


def gate_pass(caught_bad: int, total_bad: int, false_good: int, total_good: int,
              min_catch: int = MIN_CATCH_BAD, max_false: int = MAX_FALSE_GOOD) -> bool:
    """RLOOP_PLAN 第 91 行門禁：抓錯 ≥ 5/9 且 冤枉 ≤ 1/5。"""
    return caught_bad >= min_catch and false_good <= max_false


class _RecordingClient:
    """包住 client，留下模型原始輸出（存進 out 檔，之後改擷取規則可離線重建、不再計費）。"""

    def __init__(self, inner: GlmClient) -> None:
        self.inner = inner
        self.raw: str | None = None

    def complete(self, prompt: str) -> str:
        self.raw = self.inner.complete(prompt)
        return self.raw


def phase2_extract_cell(cell: Real14Cell, user_text: str, data_names: list[str],
                        previews: dict[str, str], model: str, client: GlmClient,
                        out_path: pathlib.Path) -> RequirementSet:
    """單一 cell 擷取需求；out 檔已存在 → 不再呼叫模型、不重複計費。

    argon 20261107_1248：out 檔記 prompt_sha256 與 raw_output。
    - prompt 改了（例如原文補上 contract.md）而 out 是舊 prompt 的結果 → 重新擷取，
      不靜默沿用舊 prompt 的需求（首跑後補 contract 若直接重用快取，數字不會變）。
    - prompt 相同且有 raw_output → 用目前的 build_requirement_set 從原始輸出重建
      （擷取規則改了也反映在數字上，0 呼叫）。
    - 舊格式（無 prompt_sha256）→ 照舊直接重用。
    """
    prompt = build_phase2_prompt(user_text, data_names, previews)
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    if out_path.is_file():
        doc = json.loads(out_path.read_text(encoding="utf-8"))
        pinned = (doc.get("provenance") or {}).get("prompt_sha256")
        if pinned is None:
            return RequirementSet.load(out_path)
        if pinned == prompt_sha:
            raw = doc.get("raw_output")
            if isinstance(raw, str):
                req, _ = build_requirement_set(cell.cell, parse_model_output(raw), user_text)
                return req
            return RequirementSet.load(out_path)
    rec = _RecordingClient(client)
    req, report = extract_requirements(
        user_text=user_text, client=rec, task_id=cell.cell,
        build_prompt=lambda _t: prompt)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = req.to_dict()
    doc.update({
        "model": model,
        "report": report.to_dict(),
        "raw_output": rec.raw,
        "provenance": {
            "cell": cell.cell,
            "role": cell.role,
            "task_dir": str(cell.task_dir),
            "user_text_chars": len(user_text),
            "data_files": data_names,
            "prompt_sha256": prompt_sha,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        },
    })
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return req


def read_real14_costs(vibe_calls: pathlib.Path) -> tuple[int, int] | None:
    """real14 擷取成本（purpose 前綴 real14）：(呼叫數, tokens)；無紀錄 → None（UNKNOWN）。"""
    if not vibe_calls.is_file():
        return None
    calls = 0
    tokens = 0
    for ln in vibe_calls.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if str(r.get("purpose", "")).startswith("real14"):
            calls += 1
            tokens += int(r.get("total_tokens") or 0)
    return (calls, tokens) if calls else None


def run_phase2(model: str = "glm53",
               base: pathlib.Path | None = None,
               vibe_calls: pathlib.Path | None = None,
               json_out: pathlib.Path | None = None) -> int:
    """item 2：14 份原始草稿 × 自動擷取需求 → 抓錯 x/9、冤枉 y/5 → 門禁。"""
    base = pathlib.Path(base) if base else REAL14_BASE_DEFAULT
    vibe_calls = (pathlib.Path(vibe_calls).expanduser() if vibe_calls
                  else pathlib.Path("~/dev/ops/state/vibe_calls.jsonl").expanduser())
    cells = derive_real14_cells(base)
    total_bad = sum(1 for c in cells if c.role == "bad")
    total_good = len(cells) - total_bad
    real14_dir = REPO_ROOT / "ops" / "reqloop" / "extract" / "real14"
    out_dir = REPO_ROOT / "ops" / "reqloop" / "extract" / "out" / "real14"
    client = GlmClient(model=model, purpose="real14 擷取需求")

    caught = 0
    false_acc = 0
    errors = 0
    rows: list[dict] = []
    print(f"REAL14（{base.name}，{total_bad} 壞／{total_good} 好）——自動擷取需求、14 份原始草稿")
    for c in cells:
        try:
            user_text = load_cell_request_text(
                c.task_dir, _task_id_from_cell(c.cell), real14_dir)
            data_paths = task_data_files(c.task_dir)
            names = [str(p.relative_to(c.task_dir)) for p in data_paths]
            previews = {n: _data_preview(p) for n, p in zip(names, data_paths)}
            req = phase2_extract_cell(
                c, user_text, names, previews, model, client,
                out_dir / f"{c.cell}.{model}.json")
            results = run_requirement_checks(c.task_dir, req, c.draft_dir)
        except (ExtractError, FileNotFoundError, RuntimeError,
                ValueError) as e:
            errors += 1
            rows.append({"cell": c.cell, "role": c.role, "status": "ERROR",
                         "detail": str(e)[:100]})
            print(f"  {c.cell:22s} {c.role:4s} ERROR（fail-closed）：{str(e)[:100]}")
            continue
        fails = [r for r in results if r.status == "FAIL"]
        unknowns = sum(1 for r in results if r.status == "UNKNOWN")
        if c.role == "bad":
            if fails:
                caught += 1
                note = "; ".join(f"{r.claim_id}: {r.detail[:50]}" for r in fails[:2])
                rows.append({"cell": c.cell, "role": c.role, "status": "CAUGHT",
                             "n_fail": len(fails), "n_unknown": unknowns, "detail": note})
                print(f"  {c.cell:22s} {c.role:4s} 抓錯  {len(fails)} FAIL／{unknowns} UNKNOWN——{note}")
            else:
                rows.append({"cell": c.cell, "role": c.role, "status": "MISSED",
                             "n_fail": 0, "n_unknown": unknowns, "n_results": len(results)})
                print(f"  {c.cell:22s} {c.role:4s} 漏掉  0 FAIL／{unknowns} UNKNOWN（{len(results)} 項）")
        else:
            if fails:
                false_acc += 1
                note = "; ".join(f"{r.claim_id}: {r.detail[:50]}" for r in fails[:2])
                rows.append({"cell": c.cell, "role": c.role, "status": "FALSE",
                             "n_fail": len(fails), "n_unknown": unknowns, "detail": note})
                print(f"  {c.cell:22s} {c.role:4s} 冤枉  {len(fails)} FAIL／{unknowns} UNKNOWN——{note}")
            else:
                rows.append({"cell": c.cell, "role": c.role, "status": "CLEAN",
                             "n_fail": 0, "n_unknown": unknowns, "n_results": len(results)})
                print(f"  {c.cell:22s} {c.role:4s} 乾淨  {unknowns} UNKNOWN（{len(results)} 項）")

    ok = gate_pass(caught, total_bad, false_acc, total_good)
    print(f"抓錯 {caught}/{total_bad}、冤枉 {false_acc}/{total_good}"
          + (f"（{errors} cell 擷取/檢查失敗，計入未抓）" if errors else ""))
    print(f"門禁：抓錯>={MIN_CATCH_BAD}/{total_bad} 且 冤枉<={MAX_FALSE_GOOD}/{total_good}"
          f" → {'PASS' if ok else 'FAIL'}")
    costs = read_real14_costs(vibe_calls)
    if costs:
        print(f"成本：{costs[0]} 次擷取、{costs[1]} tokens（vibe_calls.jsonl；含重跑前既有呼叫）")
    else:
        print("成本：UNKNOWN（vibe_calls.jsonl 無 real14 紀錄）")
    if json_out is not None:
        _write_json(pathlib.Path(json_out), rows,
                    {"gate": "PASS" if ok else "FAIL", "model": model,
                     "caught": caught, "total_bad": total_bad,
                     "false_acc": false_acc, "total_good": total_good,
                     "errors": errors,
                     "cost": {"calls": costs[0], "tokens": costs[1]} if costs else None})
        print(f"JSON 結果：{json_out}")
    return 0 if ok else 20


# ── phase3（vq-el4.5）：9 份錯草稿＋自動擷取需求＋localized 修復＋獨立 scorer ──
#
# 對照基線（g2-truth：G2 開發樣本逐格重算）：手寫需求下 localized 修好 9/9、
# generic 7/9；5 份對都保住。本相用**自動擷取**需求（out/real14/<cell>.<model>.json）
# 接同一條修復控制器（repair.py 凍結、reuse adapters/run.py）與同一個獨立 scorer，
# 量「自動需求」與「手寫需求」的修復力差距。
#
# 紅線：不讀 /srv/eval hidden／scorer 源；scorer 只出 pass/status；評分永不回饋修復；
# 成本缺值＝UNKNOWN（絕不填 0）；source_tampered ⇒ rejected（不得翻 fixed）。

PHASE3_PROVIDER = "lms1004nothink"          # effect_manifest.json 釘住的「1004 gemma」
PHASE3_MODEL = "gemma-4-12b-it-qat"         # 與手寫 9/9 同模型（non-thinking 口徑）
PHASE3_MAX_ROUNDS = 2                       # 同 G2 基準：2 輪×300s
PHASE3_TIMEOUT_S = 300.0


def load_phase3_sources(base: pathlib.Path) -> dict[str, dict]:
    """draft 名 → {'run','cell','before_pass'}；來源＝snapshot 的 effect_manifest.json。

    before_pass＝lab 既有記錄分數（只引用、不在本地重跑）。缺 manifest／缺 source
    → fail-closed（不准拿不存在的 source 去跑 scorer）。
    """
    man_path = base / "snapshot" / "ops" / "reqloop" / "g2" / "effect_manifest.json"
    if not man_path.is_file():
        raise FileNotFoundError(f"effect_manifest.json 缺失：{man_path}")
    man = json.loads(man_path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for d in man.get("drafts", []):
        s = d.get("source") or {}
        if s.get("run") and s.get("cell"):
            out[str(d["name"])] = {"run": s["run"], "cell": s["cell"],
                                   "before_pass": (s.get("score") or {}).get("pass")}
    return out


def prepare_phase3_task(cell: Real14Cell, req_set: RequirementSet,
                        dest: pathlib.Path) -> pathlib.Path:
    """組 phase3 任務目錄：原 request.md／contract.md／data/ ＋ requirements.json＝**自動擷取**版。

    快照（effects2 snapshot）只讀不改；手寫版 requirements.json 不帶入（那是對照組的輸入）。
    """
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("request.md", "contract.md"):
        src = cell.task_dir / name
        if src.is_file():
            shutil.copy2(src, dest / name)
    data = cell.task_dir / "data"
    if data.is_dir():
        shutil.copytree(data, dest / "data", dirs_exist_ok=True)
    (dest / "requirements.json").write_text(
        json.dumps(req_set.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


def _default_phase3_scorer():
    """實驗室既有獨立 scorer（sudo -n、只 pass/status 出評分端）；import 失敗 → 呼叫時 fail-closed。"""
    base = pathlib.Path("~/dev/ops/effects_20261105").expanduser()
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    from independent_score import score_workspace  # noqa: PLC0415
    return score_workspace


def phase3_cell(cell: Real14Cell, req_set: RequirementSet, source: dict,
                out_root: pathlib.Path, *, build, run,
                max_rounds: int = PHASE3_MAX_ROUNDS,
                timeout_s: float = PHASE3_TIMEOUT_S,
                scorer=None) -> dict:
    """一 cell：自動需求組 task → localized 修復（repair 凍結控制器）→ 獨立 scorer → 一行結果。

    build/run/scorer 皆可注入（測試用 fake；生產用 pi gemma＋lab scorer）。
    裁決口徑：bad 且 scorer pass=True 且無 source_tampered/satisfied_mutated → fixed；
    tampered/mutated → rejected（改來源迎合交付不得翻 fixed）；其餘 → unresolved。
    """
    from vacant_network.reqloop.repair import repair_slice  # 延遲 import：phase1/2 不依賴

    task_dir = prepare_phase3_task(cell, req_set, out_root / "tasks" / cell.cell)
    outcome = repair_slice(
        str(task_dir), req_set, cell.draft_dir,
        out_root=out_root / "repair" / cell.cell,
        build=build, run=run,
        feedback_mode="localized", max_rounds=max_rounds, timeout_s=timeout_s,
        min_rounds=0,  # localized 缺口驅動：無缺口 0 呼叫（同 G2 基準）
        include_dirs=("data",))
    d = outcome.to_dict()
    rounds = d.get("rounds") or []
    ws = pathlib.Path(rounds[-1]["workspace"]) if rounds else pathlib.Path(d["original_draft_dir"])
    deliverables = sorted({it.deliverable for it in req_set.items if it.deliverable})
    sc = scorer if scorer is not None else _default_phase3_scorer()
    try:
        g = sc(source, ws, deliverables)
        after = {"pass": g.get("pass"), "status": g.get("status", "UNKNOWN"),
                 "rc": g.get("rc")}
    except Exception as e:  # noqa: BLE001 — scorer 故障＝UNKNOWN，不冒稱 pass
        after = {"pass": None, "status": f"SCORER_ERROR:{type(e).__name__}", "rc": None}
    tampered = bool(d.get("source_tampered")) or bool(d.get("satisfied_mutated"))
    if cell.role == "bad":
        if tampered:
            verdict = "rejected"
        elif after["pass"] is True:
            verdict = "fixed"
        else:
            verdict = "unresolved"
    else:  # good
        if after["pass"] is True:
            verdict = "held" if not tampered else "rejected"
        elif after["pass"] is False:
            verdict = "right_to_wrong"
        else:
            verdict = "unknown"
    c = d.get("cost") or {}
    return {"cell": cell.cell, "role": cell.role, "before": source.get("before_pass"),
            "after": after, "verdict": verdict, "stopped": d.get("stopped"),
            "final_status": d.get("final_status"), "regressed": d.get("regressed"),
            "source_tampered": d.get("source_tampered"),
            "satisfied_mutated": list(d.get("satisfied_mutated") or ()),
            "workspace": str(ws), "deliverables": deliverables,
            "cost": {"repair_sessions": c.get("calls"), "model_calls": c.get("model_calls"),
                     "tokens": c.get("tokens"), "wall_ms_total": c.get("wall_ms_total")}}


def _dir_sha256(d: pathlib.Path) -> str:
    h = hashlib.sha256()
    for p in sorted(d.rglob("*")) if d.is_dir() else []:
        if p.is_file():
            h.update(str(p.relative_to(d)).encode("utf-8"))
            h.update(p.read_bytes())
    return h.hexdigest()


def run_phase3(base: pathlib.Path | None = None,
               include_good: bool = False,
               extract_model: str = "glm53",
               provider: str = PHASE3_PROVIDER,
               model: str = PHASE3_MODEL,
               max_rounds: int = PHASE3_MAX_ROUNDS,
               timeout_s: float = PHASE3_TIMEOUT_S,
               build=None, run=None, scorer=None,
               req_dir: pathlib.Path | None = None,
               out_root: pathlib.Path | None = None,
               json_out: pathlib.Path | None = None,
               limit: int | None = None) -> int:
    """vq-el4.5：9 份錯草稿（effects2 real14）×自動擷取需求×localized 修復×獨立 scorer。

    發射前凍結 freeze.json（cell 清單＋draft/需求 hash＋模型＋預算）；逐 cell 寫
    progress.json（長實驗可離線監控）。退出碼：0 全部 cell 有裁決；2 有 fail-closed。
    成本：repair_sessions（session 數）與 model_calls（API 請求數）嚴分；任一缺值⇒UNKNOWN。
    """
    from vacant_network.reqloop.repair import _default_build  # noqa: PLC0415

    base = pathlib.Path(base) if base else REAL14_BASE_DEFAULT
    cells = derive_real14_cells(base)
    if not include_good:
        cells = [c for c in cells if c.role == "bad"]
    if limit is not None:
        cells = cells[:limit]
    sources = load_phase3_sources(base)
    req_dir = pathlib.Path(req_dir) if req_dir else (
        REPO_ROOT / "ops" / "reqloop" / "extract" / "out" / "real14")
    out_root = pathlib.Path(out_root) if out_root else (
        REPO_ROOT / "ops" / "reqloop" / "extract" / "out" / "phase3")

    freeze_cells = []
    for c in cells:
        src = sources.get(c.cell)
        req_file = req_dir / f"{c.cell}.{extract_model}.json"
        freeze_cells.append({
            "cell": c.cell, "role": c.role,
            "task_dir": str(c.task_dir), "draft_dir": str(c.draft_dir),
            "draft_sha256": _dir_sha256(c.draft_dir) if c.draft_dir.is_dir() else None,
            "req_file": str(req_file),
            "req_sha256": hashlib.sha256(req_file.read_bytes()).hexdigest() if req_file.is_file() else None,
            "source": {"run": src["run"], "cell": src["cell"]} if src else None,
            "before_pass": src["before_pass"] if src else None,
        })
    out_root.mkdir(parents=True, exist_ok=True)
    freeze_doc = {
        "phase": 3, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "base": str(base), "extract_model": extract_model,
        "repair": {"provider": provider, "model": model, "feedback_mode": "localized",
                   "min_rounds": 0},
        "budget": {"max_rounds": max_rounds, "timeout_s_per_round": timeout_s,
                   "hard_token_cap": False,
                   "note": "無硬 token 上限；成本從 raw usage 讀、缺值＝UNKNOWN 不填 0"},
        "comparison": "手寫需求基線（g2-truth）：localized 9/9、generic 7/9；開發選樣單 rep",
        "cells": freeze_cells,
    }
    freeze_path = out_root / "freeze.json"
    if not freeze_path.is_file():
        freeze_path.write_text(json.dumps(freeze_doc, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    else:
        # 官方 freeze 不可變：驗證／接續 run 不得重寫 generated_at（凍結快照）；
        # 參數不一致時 fail-closed，絕不靜默覆蓋官方 freeze。
        try:
            _old = json.loads(freeze_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            _old = None
        if _old is None or any(_old.get(k) != freeze_doc[k] for k in
                               ("base", "extract_model", "repair", "budget", "comparison", "cells")):
            print("PHASE3 fail-closed：既有 freeze.json 與本次 run 參數不一致，拒絕覆蓋官方 freeze",
                  file=sys.stderr)
            return 2

    if build is None:
        build = _default_build(provider, model, hooks=True)
    if run is None:
        from vacant_network.adapters.run import run_agent  # noqa: PLC0415
        run = run_agent

    cached_rows: dict[str, dict] = {}
    prog_path = out_root / "progress.json"
    if prog_path.is_file():
        try:
            _p = json.loads(prog_path.read_text(encoding="utf-8"))
            for _r in _p.get("rows") or []:
                if isinstance(_r, dict) and _r.get("cell") and "verdict" in _r \
                        and _r.get("status") != "ERROR":
                    cached_rows[_r["cell"]] = _r
        except (json.JSONDecodeError, UnicodeDecodeError):
            cached_rows = {}  # 損壞的 progress 不接續、不猜
    if cached_rows:
        print(f"PHASE3 接續：progress.json 已有 {len(cached_rows)} 份裁決，該 cell 不重複執行")

    rows: list[dict] = []
    errors = 0
    n_bad = sum(1 for c in cells if c.role == "bad")
    print(f"PHASE3（vq-el4.5）：{len(cells)} 份草稿（{n_bad} 錯／{len(cells) - n_bad} 好）"
          f"＋自動擷取需求（{extract_model}）＋localized 修復（{provider}/{model}）＋獨立 scorer")
    for c in cells:
        if c.cell in cached_rows:
            rows.append(cached_rows[c.cell])
            print(f"  {c.cell:22s} {c.role:4s} RESUMED（已接續 progress.json，不重複呼叫）",
                  flush=True)
            continue
        src = sources.get(c.cell)
        req_file = req_dir / f"{c.cell}.{extract_model}.json"
        if src is None:
            errors += 1
            rows.append({"cell": c.cell, "role": c.role, "status": "ERROR",
                         "detail": "manifest 缺 source（fail-closed）"})
            print(f"  {c.cell:22s} {c.role:4s} ERROR（manifest 缺 source）")
        elif not req_file.is_file():
            errors += 1
            rows.append({"cell": c.cell, "role": c.role, "status": "ERROR",
                         "detail": f"缺擷取結果 {req_file.name}（fail-closed，不拿缺的當通過）"})
            print(f"  {c.cell:22s} {c.role:4s} ERROR（缺擷取結果）")
        else:
            req_set = RequirementSet.load(req_file)
            try:
                row = phase3_cell(c, req_set, src, out_root,
                                  build=build, run=run, scorer=scorer,
                                  max_rounds=max_rounds, timeout_s=timeout_s)
            except Exception as e:  # noqa: BLE001 — 單 cell 故障不拖垮全批，但如實計錯
                errors += 1
                row = {"cell": c.cell, "role": c.role, "status": "ERROR",
                       "detail": f"{type(e).__name__}: {str(e)[:100]}"}
            rows.append(row)
            (out_root / "progress.json").write_text(
                json.dumps({"complete": False, "rows": rows}, ensure_ascii=False, indent=1),
                encoding="utf-8")
            if "verdict" in row:
                a = row["after"]
                cost = row["cost"]
                tok = "UNKNOWN" if cost["tokens"] is None else str(cost["tokens"])
                mc = "UNKNOWN" if cost["model_calls"] is None else str(cost["model_calls"])
                print(f"  {row['cell']:22s} {row['role']:4s} {row['verdict']:14s}"
                      f"  after={a['pass']}（{a['status']}）stopped={row['stopped']}"
                      f"  model_calls={mc} tokens={tok}", flush=True)
            else:
                print(f"  {row['cell']:22s} {row['role']:4s} ERROR：{row.get('detail', '')[:80]}",
                      flush=True)

    (out_root / "progress.json").write_text(
        json.dumps({"complete": True, "rows": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    def _agg(key: str):
        vals = [r["cost"][key] for r in rows if "cost" in r and "verdict" in r]
        if not vals or any(v is None for v in vals):
            return None
        return sum(vals)

    fixed = sum(1 for r in rows if r.get("verdict") == "fixed")
    unresolved = sum(1 for r in rows if r.get("verdict") == "unresolved")
    rejected = sum(1 for r in rows if r.get("verdict") == "rejected")
    rtw = sum(1 for r in rows if r.get("verdict") == "right_to_wrong")
    held = sum(1 for r in rows if r.get("verdict") == "held")
    cost = {"repair_sessions": _agg("repair_sessions"), "model_calls": _agg("model_calls"),
            "tokens": _agg("tokens")}
    summary = {"phase": 3, "base": str(base), "extract_model": extract_model,
               "repair_model": {"provider": provider, "model": model},
               "cells": len(rows), "errors": errors,
               "fixed": fixed, "unresolved": unresolved, "rejected": rejected,
               "right_to_wrong": rtw, "held": held,
               "cost": cost,
               "cost_note": "repair_sessions＝修復 session 數；model_calls＝API 請求數（raw usage）；"
                           "任一缺值⇒UNKNOWN（不填 0）",
               "comparison_baseline": "手寫需求（g2-truth）：localized 9/9、generic 7/9；開發選樣單 rep，不宣稱較好",
               "rows": rows}
    print(f"\n裁決：fixed {fixed}、unresolved {unresolved}、rejected {rejected}、"
          f"right_to_wrong {rtw}、held {held}、error {errors}")
    for k, v in cost.items():
        print(f"  成本 {k}: {v if v is not None else 'UNKNOWN（缺值不填 0）'}")
    print("對照：手寫需求 localized 9/9（g2-truth；開發選樣單 rep）")
    if json_out is not None:
        pathlib.Path(json_out).write_text(
            json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"JSON 結果：{json_out}")
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
