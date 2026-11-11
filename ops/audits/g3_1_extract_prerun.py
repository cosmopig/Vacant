#!/usr/bin/env python3
"""G3.1 H2.0 extract 預跑門（P20261111_1315-2；2026-11-11 人類常設定案 2.a）。
H2.0：≥1/4 題有 ≥1 條確定性 claim → H2_0_MET；0/4 題 → H2_0_REFUTED（否決＋停止同路徑工單＋上報人類）。
確定性 claim＝item.unverified=False（verifier∈SUPPORTED_VERIFIERS、params 合格，可重算 PASS/FAIL）；
unverified＝report.unverified（UNKNOWN＋原因，絕不當通過）；擷取/解析失敗＝空集合（fail-closed，不計 MET）。
--selftest：0 模型呼叫（正/負/解析失敗控制，先紅後綠）；--run：4 次 glm 呼叫 → g3_1_h20_prerun_report.json。
紅線：凍結 4 檔不改；hidden/scorer 不讀；預跑不擅自點火完整批（H2.0 結果上報人類）。"""
import argparse
import datetime as _dt
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from vacant_network.reqloop.extract import ExtractReport, GlmClient, RequirementSet, extract_requirements  # noqa: E402
from vacant_network.reqloop.g3 import compose_extract_user_text, input_sha256  # noqa: E402

MANIFEST = REPO / "ops/reqloop/g3_1/manifest.json"
REPORT = REPO / "ops/audits/g3_1_h20_prerun_report.json"
H2_MET, H2_REFUTED = "H2_0_MET", "H2_0_REFUTED"
PURPOSE_TAG = "G3.1 H2.0 prerun"
# glm CLI 帳本固定在 OPS 目錄（~/.local/bin/glm：LEDGER={OPS}/state/vibe_calls.jsonl），與 CWD 無關。
LEDGER = Path.home() / "dev/ops/state/vibe_calls.jsonl"
_U_POS = "Compute the mean of the Amount column from sales.csv and write the result to answer.txt."
_U_NEG = "Do the thing with the data."
_M_POS = ('[{"id":"R1","quote":"Compute the mean of the Amount column","deliverable":"answer.txt",'
          '"verifier":"answer_kv","params":{"keys":[{"key":"mean","type":"number"}]},"description":"d",'
          '"kind":"explicit"},{"id":"R2","quote":"write the result to answer.txt","deliverable":"answer.txt",'
          '"verifier":"made_up_verifier","params":{},"kind":"explicit"}]')
_M_NEG = ('[{"id":"R1","quote":"Do the thing","deliverable":"answer.txt",'
          '"verifier":"made_up_verifier","params":{},"kind":"explicit"}]')

def load_manifest(path: Path = MANIFEST) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "vacant.reqloop.g3gate.plan/1":
        raise ValueError(f"manifest schema 不符：{data.get('schema')!r}")
    tasks = data.get("tasks", [])
    if [t.get("task_id") for t in tasks] != ["dab_035", "dab_055", "dab_105", "dab_218"]:
        raise ValueError(f"manifest 題單 ≠ 凍結 4 題：{[t.get('task_id') for t in tasks]}")
    return tasks

def classify(req_set: RequirementSet, report: ExtractReport) -> dict:
    """確定性（可 PASS/FAIL 重算）vs unverified（UNKNOWN＋原因）分類。"""
    det = [it.id for it in req_set.items if not it.unverified]
    unv = [{"id": u.id, "reason": u.reason} for u in report.unverified]
    return {"n_requirements": len(req_set.items), "n_deterministic_claims": len(det),
            "deterministic_claim_ids": det, "n_unverified_claims": len(unv),
            "unverified_claims": unv,
            "reason_distribution": dict(sorted(Counter(u.reason for u in report.unverified).items())),
            "n_discarded": len(report.discarded), "has_deterministic_claim": len(det) >= 1,
            "extract_error": report.extract_error, "parse_error": report.parse_error}

def h20_verdict(rows: list[dict]) -> str:
    return H2_MET if any(r["has_deterministic_claim"] for r in rows) else H2_REFUTED

def run_prerun(client, manifest_path: Path = MANIFEST, tasks_root: Path = REPO / "ops/reqloop/g3_1/tasks") -> list[dict]:
    rows = []  # user_text＝workspace/goal.md＋contract.md（公開交付規格），與 g3.py 發射路徑同口徑（P20261111_1516-1）
    for t in load_manifest(manifest_path):
        tdir = tasks_root / t["task_id"]
        gt = (tdir / "workspace/goal.md").read_text(encoding="utf-8")
        cp = tdir / "workspace" / "contract.md"
        contract = cp.read_text(encoding="utf-8") if cp.is_file() else None
        user_text = compose_extract_user_text(gt, contract)
        req, report = extract_requirements(user_text=user_text, client=client, task_id=t["task_id"])
        row = {"task_id": t["task_id"], "input_sha256": input_sha256(tdir, t["files"]),
               "goal_sha256": hashlib.sha256(gt.encode("utf-8")).hexdigest()}
        row.update(classify(req, report))
        rows.append(row)
    return rows

def build_report(rows: list[dict], *, model: str, cost: dict) -> dict:
    return {"schema": "vacant.audit/g3_1_h20_prerun/1", "ticket": "P20261111_1315-2",
            "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "purpose": "G3.1 H2.0 extract 預跑門：4 凍結題擷取需求的 verifier 支援性與確定性可驗證性",
            "model": model,
            "manifest": {"path": str(MANIFEST), "sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest()},
            "h20_rule": "≥1/4 題 ≥1 條確定性 claim → H2_0_MET；0/4 題 → H2_0_REFUTED（fail-closed：擷取/解析失敗＝空集合，不計 MET）",
            "n_tasks": len(rows),
            "n_tasks_with_deterministic_claim": sum(r["has_deterministic_claim"] for r in rows),
            "h20_verdict": h20_verdict(rows), "cost": cost, "tasks": rows}

def _mock(payload: str, user: str, tid: str) -> dict:
    client = SimpleNamespace(complete=lambda prompt: payload)  # 0 模型呼叫
    req, rep = extract_requirements(user_text=user, client=client, task_id=tid)
    return classify(req, rep)

def selftest() -> int:
    checks: list[tuple[str, bool]] = []
    def ck(name: str, cond: bool, detail: str = "") -> None:
        checks.append((name, bool(cond))); print(f"{'PASS' if cond else 'FAIL'} {name}" + (f"（{detail}）" if not cond else ""))

    load_manifest()  # 題單/schema 不對直接 throw＝自測紅（manifest 釘住另見 test_reqloop_g3_1_manifest.py）
    pos = _mock(_M_POS, _U_POS, "mock_pos")
    neg = _mock(_M_NEG, _U_NEG, "mock_neg")
    ck("pos_classify", pos["n_requirements"] == 2 and pos["n_deterministic_claims"] == 1
       and pos["reason_distribution"] == {"unknown_verifier:made_up_verifier": 1}, str(pos))
    ck("neg_classify", neg["n_deterministic_claims"] == 0 and neg["n_unverified_claims"] == 1, str(neg))
    ck("h20_verdicts", h20_verdict([pos] + [neg] * 3) == H2_MET and h20_verdict([neg] * 4) == H2_REFUTED)
    bad = _mock("not a json at all", _U_POS, "mock_bad")
    ck("bad_fail_closed", bad["n_requirements"] == 0 and bool(bad["parse_error"])
       and h20_verdict([bad] * 4) == H2_REFUTED, str(bad))
    ck("report_format", {"schema", "h20_verdict", "n_tasks", "n_tasks_with_deterministic_claim",
                         "cost", "tasks"} <= set(build_report(
        [pos] + [neg] * 3, model="mock", cost={"model_calls": 4, "total_tokens": "UNKNOWN"}))
       and h20_verdict([pos] + [neg] * 3) == H2_MET)
    failed = [n for n, ok in checks if not ok]
    print(f"VERDICT: G3_1_PRERUN_SELFTEST_BROKEN（{len(failed)} 項失敗：{failed}）") if failed else print("VERDICT: G3_1_PRERUN_SELFTEST_OK")
    return 1 if failed else 0

def _usage_since(before: int) -> tuple[int, "int | str"]:
    if not LEDGER.is_file():
        return 0, "UNKNOWN"
    tot, seen = 0, 0
    for ln in LEDGER.read_text(encoding="utf-8").splitlines()[before:]:
        d = json.loads(ln) if ln.strip() else None
        if d is None or PURPOSE_TAG not in str(d.get("purpose", "")):
            continue
        v = d.get("total_tokens")
        if not (isinstance(v, int) or (isinstance(v, str) and v.isdigit())):
            return seen, "UNKNOWN"
        seen += 1
        tot += int(v)
    return seen, (tot if seen else "UNKNOWN")

def run_live() -> int:
    before = len(LEDGER.read_text(encoding="utf-8").splitlines()) if LEDGER.is_file() else 0
    rows = run_prerun(GlmClient(model="glm53", purpose=PURPOSE_TAG, timeout=300.0))
    calls, toks = _usage_since(before)
    report = build_report(rows, model="glm53", cost={"model_calls": calls, "total_tokens": toks})
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for r in rows:
        print(f"{r['task_id']}: req={r['n_requirements']} det={r['n_deterministic_claims']} "
              f"unv={r['n_unverified_claims']} dist={r['reason_distribution']}")
    print(f"cost: {report['cost']}")
    print(f"VERDICT: H2_0 = {report['h20_verdict']}")
    return 0

def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description="G3.1 H2.0 extract 預跑門（0 或 4 模型呼叫）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true", help="0 模型呼叫：正/負/解析失敗控制")
    g.add_argument("--run", action="store_true", help="4 次 glm 呼叫，寫真實報告")
    return selftest() if ap.parse_args(argv).selftest else run_live()

if __name__ == "__main__":
    raise SystemExit(main())
