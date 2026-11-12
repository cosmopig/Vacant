#!/usr/bin/env python3
"""G3.3 H0 門跨獨立呼叫穩定性 extract 檢驗與 H2 假說判定（P20261112_0119-2；2026-11-11 人類常設定案 2.a）。
H2（g3_2_candidate_hypothesis.md §6）：同題 dab_725、glm53、同 input；3 次獨立 extract 呼叫 ≥2/3 次 ≥1 條確定性 claim；
既有 2 點含 1 達 1 未達（prerun r1469=2/R1,R6；fire r1472=0）⇒ H2 等價於：第 3 次獨立 extract 呼叫產出 ≥1 條確定性 claim。
本票發射第 3 次獨立 extract（1 通 glm、0 answer）：達→H2_MET（孤立漂移、下候選 G3.4 共識門、仍需人類核准）；未達→H2_REFUTED（呼叫隨機；停止規則：G 系列停止＋上報人類、不加重試/靜態 prompt/regex 工單）。
--selftest：0 模型呼叫（正控制→MET；負控制/解析失敗→REFUTED；history 核）；
--run：2M/日守衛（glm CLI rc=3 fail-closed）＋input 同 hash 核＋1 通 glm→真實報告。
紅線：凍結 4 檔不改；hidden/scorer 不讀；缺值 UNKNOWN 絕不填 0；extract/parse 失敗＝空集合不計達（I-4）。"""
import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from vacant_network.reqloop.extract import ExtractReport, GlmClient, RequirementSet, extract_requirements  # noqa: E402
from vacant_network.reqloop.g3 import compose_extract_user_text, input_sha256  # noqa: E402

MANIFEST = REPO / "ops/reqloop/g3_3/manifest.json"
TASKS_ROOT = REPO / "ops/reqloop/g3_3/tasks"
PRERUN = REPO / "ops/audits/g3_2_h0_prerun_report.json"   # call1（prerun r1469）
FIRE = REPO / "ops/audits/g3_2_fire_summary.json"         # call2（fire r1472）
REPORT = REPO / "ops/audits/g3_3_h0_stability_report.json"
TASK_ID, H2_MET, H2_REFUTED = "dab_725", "H2_MET", "H2_REFUTED"
PURPOSE_TAG = "G3.3 H2 stability"
LEDGER = Path.home() / "dev/ops/state/vibe_calls.jsonl"   # glm CLI 帳本固定於此，與 CWD 無關
_U_POS, _U_NEG = ("Compute the mean of the Amount column from sales.csv and write the result to answer.txt.",
                  "Do the thing with the data.")
_M_POS = ('[{"id":"R1","quote":"Compute the mean of the Amount column","deliverable":"answer.txt",'
          '"verifier":"answer_kv","params":{"keys":[{"key":"mean","type":"number"}]},"kind":"explicit"}]')
_M_NEG = ('[{"id":"R1","quote":"Do the thing","deliverable":"answer.txt",'
          '"verifier":"made_up_verifier","params":{},"kind":"explicit"}]')

def load_manifest(path: Path = MANIFEST) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "vacant.reqloop.g3gate.plan/1":
        raise ValueError(f"manifest schema 不符：{data.get('schema')!r}")
    if [t.get("task_id") for t in data.get("tasks", [])] != [TASK_ID]:
        raise ValueError(f"manifest 題單 ≠ 單題 {TASK_ID}")
    return data["tasks"][0]

def classify(req_set: RequirementSet, report: ExtractReport) -> dict:
    """確定性（可 PASS/FAIL 重算）vs unverified（UNKNOWN＋原因）分類（與 g3_2 同口徑）。"""
    det = [it.id for it in req_set.items if not it.unverified]
    unv = [{"id": u.id, "reason": u.reason} for u in report.unverified]
    return {"n_requirements": len(req_set.items), "n_deterministic_claims": len(det),
            "deterministic_claim_ids": det, "n_unverified_claims": len(unv), "unverified_claims": unv,
            "has_deterministic_claim": len(det) >= 1, "extract_error": report.extract_error, "parse_error": report.parse_error}

def history_calls() -> list[dict]:
    """既有 2 次獨立呼叫自 in-repo 審計報告機械讀取（不手抄）。"""
    pre = next(r for r in json.loads(PRERUN.read_text(encoding="utf-8"))["tasks"] if r["task_id"] == TASK_ID)
    per = next(t for t in json.loads(FIRE.read_text(encoding="utf-8"))["h0_reproducibility"]["per_task"] if t["task_id"] == TASK_ID)
    def mk(call, source, n_req, det):
        return {"call": call, "source": source, "n_requirements": n_req, "n_deterministic_claims": len(det),
                "deterministic_claim_ids": list(det), "input_sha256": pre["input_sha256"], "reached": len(det) >= 1}
    return [mk(1, "prerun r1469", pre["n_requirements"], pre["deterministic_claim_ids"]),
            mk(2, "fire r1472", per["fire_n_requirements"], per["fire_deterministic_ids"])]

def h2_verdict(calls: list[dict]) -> str:  # ≥2/3 達→MET；既有 1 達 1 未達 ⇒ 等價於 call3 達
    return H2_MET if sum(c["reached"] for c in calls) >= 2 else H2_REFUTED

CONSEQUENCE = {H2_MET: "單呼叫 H0 門可重現；G3.2 fire 失靈＝孤立漂移；下候選＝G3.4 多呼叫共識門（假說 §6 任務單 2，仍需人類核准）", H2_REFUTED: "單呼叫 H0 門為呼叫隨機；停止規則：G 系列停止、上報人類；不加同題重試／靜態 prompt／錯誤字串 regex 工單"}

def build_report(calls: list[dict], cost: dict, model: str = "glm53") -> dict:
    verdict = h2_verdict(calls)
    return {"schema": "vacant.audit/g3_3_h0_stability/1", "ticket": "P20261112_0119-2",
            "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"), "model": model,
            "h2_rule": "3 次獨立 extract 呼叫 ≥2/3 次 ≥1 條確定性 claim（PASS/FAIL、程式重算）→H2_MET；"
                       "既有 2 點 1 達 1 未達，故等價於 call3 產出 ≥1 條確定性 claim；call3=0（1/3 達）→H2_REFUTED"
                       "（fail-closed：extract/parse 失敗＝空集合不計達；UNKNOWN 非裁決非通過 I-4；"
                       "規則源：ops/reqloop/g3_2_candidate_hypothesis.md §6）",
            "n_calls": len(calls), "n_calls_reached": sum(c["reached"] for c in calls),
            "h2_verdict": verdict, "h2_consequence": CONSEQUENCE[verdict], "cost": cost, "calls": calls,
            "manifest": {"path": str(MANIFEST.relative_to(REPO)),
                         "sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest()}}

def _mock(payload: str, user: str) -> dict:
    row = classify(*extract_requirements(user_text=user, client=SimpleNamespace(complete=lambda p: payload), task_id="mock"))
    row["reached"] = row["n_deterministic_claims"] >= 1
    return row

def selftest() -> int:
    oks = []
    def ck(name, cond, detail=""):
        oks.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name + (f"（{detail}）" if not cond else ""))
    load_manifest()  # 題單/schema 不對直接 throw＝自測紅
    hist = history_calls()
    ck("history_two_calls", [c["call"] for c in hist] == [1, 2]
       and hist[0]["n_deterministic_claims"] == 2 and hist[0]["deterministic_claim_ids"] == ["R1", "R6"]
       and hist[1]["n_deterministic_claims"] == 0 and hist[0]["reached"] and not hist[1]["reached"], str(hist))
    pos, neg, bad = _mock(_M_POS, _U_POS), _mock(_M_NEG, _U_NEG), _mock("not a json at all", _U_POS)
    ck("pos_h2_met", pos["n_deterministic_claims"] == 1 and h2_verdict(hist + [pos]) == H2_MET, str(pos))
    ck("neg_h2_refuted", neg["n_deterministic_claims"] == 0 and neg["has_deterministic_claim"] is False
       and h2_verdict(hist + [neg]) == H2_REFUTED, str(neg))
    ck("bad_fail_closed", bad["n_requirements"] == 0 and bool(bad["parse_error"])
       and h2_verdict(hist + [bad]) == H2_REFUTED, str(bad))
    rep = build_report(hist + [pos], cost={"model_calls": 1, "total_tokens": "UNKNOWN"})
    ck("report_format", {"schema", "h2_rule", "h2_verdict", "n_calls", "n_calls_reached", "cost", "calls"} <= set(rep)
       and rep["h2_verdict"] == H2_MET and rep["n_calls_reached"] == 2 and rep["n_calls"] == 3)
    if not all(oks): print("VERDICT: G3_3_STABILITY_SELFTEST_BROKEN"); return 1
    print("VERDICT: G3_3_STABILITY_SELFTEST_OK"); return 0

def _usage_since(before: int) -> tuple[int, "int | str"]:
    if not LEDGER.is_file():
        return 0, "UNKNOWN"
    tot, seen = 0, 0
    for ln in LEDGER.read_text(encoding="utf-8").splitlines()[before:]:
        d = json.loads(ln) if ln.strip() else None
        if d is None or PURPOSE_TAG not in str(d.get("purpose", "")): continue
        v = d.get("total_tokens")
        if not (isinstance(v, int) or (isinstance(v, str) and v.isdigit())): return seen, "UNKNOWN"
        seen, tot = seen + 1, tot + int(v)
    return seen, (tot if seen else "UNKNOWN")

def run_live() -> int:
    task = load_manifest()
    tdir = TASKS_ROOT / TASK_ID
    gt = (tdir / "workspace/goal.md").read_text(encoding="utf-8")
    cp = tdir / "workspace" / "contract.md"
    contract = cp.read_text(encoding="utf-8") if cp.is_file() else None
    sha = input_sha256(tdir, task["files"])
    hist = history_calls()
    if sha != hist[0]["input_sha256"]:
        print(f"INPUT_MISMATCH：g3_3 副本 {sha} ≠ call1 {hist[0]['input_sha256']}；不發射（0 模型呼叫）"); return 4
    before = len(LEDGER.read_text(encoding="utf-8").splitlines()) if LEDGER.is_file() else 0
    req, rep = extract_requirements(user_text=compose_extract_user_text(gt, contract), task_id=TASK_ID,
                                    client=GlmClient(model="glm53", purpose=PURPOSE_TAG, timeout=300.0))
    row = {"call": 3, "source": "G3.3 第 3 次獨立 extract 呼叫（本票 --run）", "input_sha256": sha}
    row.update(classify(req, rep)); row["reached"] = row["n_deterministic_claims"] >= 1  # 達＝≥1 條確定性
    calls, toks = _usage_since(before)
    report = build_report(hist + [row], cost={"model_calls": calls, "total_tokens": toks})
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"call3: req={row['n_requirements']} det={row['n_deterministic_claims']} ids={row['deterministic_claim_ids']} "
          f"err={row['extract_error']}/{row['parse_error']} cost={report['cost']}")
    print(f"VERDICT: H2 = {report['h2_verdict']}（後果：{report['h2_consequence']}）")
    return 0

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="G3.3 H0 門跨獨立呼叫穩定性（0 或 1 模型呼叫）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true", help="0 模型呼叫：正/負/解析失敗控制")
    g.add_argument("--run", action="store_true", help="1 通 glm 呼叫（第 3 次獨立 extract），寫真實報告")
    return selftest() if ap.parse_args(argv).selftest else run_live()

if __name__ == "__main__": raise SystemExit(main())
