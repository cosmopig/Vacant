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
import re
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from vacant_network.reqloop.checks import run_requirement_checks  # noqa: E402
from vacant_network.reqloop.extract import (  # noqa: E402
    GlmClient,
    extract_requirements,
    build_task_prompt,
    csv_preview,
    json_preview,
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
    ap.add_argument("--phase2", action="store_true",
                    help="item 2：14 份真實草稿（effects2_20261106，9 壞／5 好）＋自動擷取需求")
    ap.add_argument("--effects2", default=None,
                    help="effects2 目錄（預設 ~/dev/ops/effects2_20261106）")
    a = ap.parse_args(argv)

    if a.phase2:
        return run_phase2(model=a.model,
                          base=pathlib.Path(a.effects2).expanduser() if a.effects2 else None,
                          json_out=pathlib.Path(a.json) if a.json else None)

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
    real14/<task_id>.request.md（來源與 sha 見該檔頭部 provenance）。兩者皆無 → fail-closed。"""
    primary = task_dir / "request.md"
    if primary.is_file():
        return primary.read_text(encoding="utf-8")
    fallback = real14_dir / f"{task_id}.request.md"
    if fallback.is_file():
        return fallback.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"request.md 與 {fallback} 皆無（fail-closed；不猜使用者原文）")


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


def phase2_extract_cell(cell: Real14Cell, user_text: str, data_names: list[str],
                        previews: dict[str, str], model: str, client: GlmClient,
                        out_path: pathlib.Path) -> RequirementSet:
    """單一 cell 擷取需求；out 檔已存在 → 直接重用（不再呼叫模型、不重複計費）。"""
    if out_path.is_file():
        return RequirementSet.load(out_path)
    prompt = build_phase2_prompt(user_text, data_names, previews)
    req, report = extract_requirements(
        user_text=user_text, client=client, task_id=cell.cell,
        build_prompt=lambda _t: prompt)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = req.to_dict()
    doc.update({
        "model": model,
        "report": report.to_dict(),
        "provenance": {
            "cell": cell.cell,
            "role": cell.role,
            "task_dir": str(cell.task_dir),
            "user_text_chars": len(user_text),
            "data_files": data_names,
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


if __name__ == "__main__":
    sys.exit(main())
