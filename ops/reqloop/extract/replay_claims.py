#!/usr/bin/env python3
"""G3-76 需求離線 claim 重播（工單 P20261113_0300-1-d1-offline-claim-replay）。

零模型、零網路、唯讀：用當前 repo 的 extract 校驗＋checks 支援集合，對 G3 四來源的 76 條
需求重判 deterministic/unverified。不造假：四來源只存 claim id＋原 reason（g3_2_fire 另存
verifier）；params/quote/deliverable 未存 → 需未存欄位者（missing_param 的 params、2 條
deterministic）標 missing_raw，不計數不推測。基線：當前代碼下原本 unverified 者無一翻成
deterministic → replayable 內 deterministic=0；taxonomy 的 2 條 deterministic（g3_2_prerun
dab_725 R1/R6）落在 missing_raw，差額即這些。D2/D3 量效：trusted_deliverable 走 judge_claim
參數；checks.py recompute 型別集合擴充後自動反映。末行 REPLAY replayable=N deterministic=K baseline_match=True
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from vacant_network.reqloop import checks, extract  # noqa: E402
from vacant_network.reqloop.g3 import compose_extract_user_text  # noqa: E402

OUT, TAX = REPO / "ops/audits/g26_claim_replay.json", REPO / "ops/audits/g3_series_unverified_taxonomy.json"
SOURCES = (("g3_1_prerun", "g3_1", "ops/audits/g3_1_h20_prerun_report.json"),
           ("g3_2_prerun", "g3_2", "ops/audits/g3_2_h0_prerun_report.json"), ("g3_2_fire", "g3_2", "ops/audits/g3_2_fire_summary.json"),
           ("g3_3_call3", "g3_3", "ops/audits/g3_3_h0_stability_report.json"))
_CACHE: dict[tuple[str, str], tuple[str, list[str]]] = {}

def code_sha() -> dict:
    return {r: (subprocess.run(["git", "hash-object", str(REPO / r)], capture_output=True, text=True).stdout.strip() or "git-failed")
            for r in ("vacant_network/reqloop/extract.py", "vacant_network/reqloop/checks.py")}

def load_task(task_root: str, task_id: str) -> tuple[str, list[str]]:
    """凍結任務 workspace：user_text＝goal.md＋公開 contract.md（與 G3 發射路徑同口徑），inputs＝data/ 檔名。"""
    key = (task_root, task_id)
    if key not in _CACHE:
        w = REPO / "ops/reqloop" / task_root / "tasks" / task_id / "workspace"
        goal = (w / "goal.md").read_text(encoding="utf-8")
        c = w / "contract.md"
        ut = compose_extract_user_text(goal, c.read_text(encoding="utf-8") if c.is_file() else None)
        d = w / "data"
        _CACHE[key] = (ut, sorted(p.name for p in d.iterdir() if p.is_file()) if d.is_dir() else [])
    return _CACHE[key]

def is_input_file(d: str, input_files: list[str]) -> bool:
    """輸入檔永遠不可當交付物（11-13 人工決定第 2 條；與 D2 同一守則）。"""
    n = str(extract._strip_workspace_prefix(str(d))).strip()
    return bool(re.fullmatch(r"[\w.\-/]+\.\w{1,8}", n)) and (n in input_files or n.split("/")[-1] in input_files)

def judge_claim(verifier, deliverable, params, user_text, input_files, *, trusted_deliverable=None):
    """用當前代碼重判一條「原始需求」（順序同 extract.build_requirement_set）。回 (deterministic, reason)。"""
    v = str(verifier or "").strip()
    if not v or v not in checks.SUPPORTED_VERIFIERS:
        return False, f"unknown_verifier:{verifier}"
    if (p := extract._param_problem(v, params or {})):
        return False, p
    d = str(trusted_deliverable or deliverable or "").strip()
    if not d:
        return False, "deliverable_missing"
    if is_input_file(d, input_files):
        return False, "deliverable_is_input_file"
    if (p := extract._deliverable_problem(d, user_text)):
        return False, p
    return True, None

def replay_reason(reason, user_text, input_files, saved_verifier=None, trusted=None):
    """對「原失敗階段」重跑當前代碼。回 (True/False, reason)；(None, None)＝missing_raw（原始欄位未存，不重判）。"""
    if reason == "model_declared_unverified":
        return False, reason  # fail-closed：模型自陳不可驗，當前代碼下穩定
    if reason.startswith("unknown_verifier:"):
        v = reason.split(":", 1)[1].strip()
        ok = v in checks.SUPPORTED_VERIFIERS
        return ok, (None if ok else reason)
    if reason.startswith("unsupported_recompute_type:"):
        t = reason.split(":", 1)[1].strip()
        allowed = extract._RECOMPUTE_TYPES.get(saved_verifier, checks.KV_RECOMPUTE_TYPES | checks.PLAIN_RECOMPUTE_TYPES)
        return (t in allowed), (None if t in allowed else reason)
    if reason.startswith("deliverable_not_in_request:"):
        claimed = reason.split(":", 1)[1].strip()
        if is_input_file(str(trusted or claimed), input_files):
            return False, "deliverable_is_input_file"
        p = extract._deliverable_problem(str(trusted or claimed), user_text)
        return (not p), (None if not p else p)
    return None, None  # missing_param:* 等：params 未存 → 無法重判，不造假

def collect():
    rows = []

    def add(batch, task_root, task_id, cid, verdict, reason, verifier=None):
        ut, inputs = load_task(task_root, task_id)
        if verdict == "deterministic":
            status, r = "missing_raw", "raw_fields_not_saved"  # 原始欄位未存，不複驗不造假
        else:
            ok, r = replay_reason(reason, ut, inputs, saved_verifier=verifier)
            status = "missing_raw" if ok is None else ("deterministic" if ok else "unverified")
        rows.append({"source": batch, "task_id": task_id, "claim_id": cid, "original_verdict": verdict,
                     "original_reason": reason, "saved_verifier": verifier, "replay_status": status,
                     "replay_reason": r, "user_text_chars": len(ut), "input_files": inputs})

    for batch, root, rel in SOURCES:
        data, claims = json.loads((REPO / rel).read_text(encoding="utf-8")), []
        if batch in ("g3_1_prerun", "g3_2_prerun"):
            for t in data["tasks"]:
                claims += [(t["task_id"], c["id"], "unverified", c["reason"], None) for c in t["unverified_claims"]]
                claims += [(t["task_id"], cid, "deterministic", None, None) for cid in t.get("deterministic_claim_ids", [])]
        elif batch == "g3_2_fire":
            claims += [(cell["task"], cl["id"], cl.get("status", "unverified"), cl["evidence"].get("reason"), cl.get("verifier"))
                       for cell in data["cells"] for cl in cell["content_reverify"]["claims"]]
        else:  # g3_3_call3：報告未存 task_id → 取 g3_3 凍結 manifest 的唯一任務
            tid = json.loads((REPO / "ops/reqloop/g3_3/manifest.json").read_text(encoding="utf-8"))["tasks"][0]["task_id"]
            call = next(c for c in data["calls"] if c.get("unverified_claims"))
            claims += [(tid, c["id"], "unverified", c["reason"], None) for c in call["unverified_claims"]]
        for task_id, cid, verdict, reason, verifier in claims:
            add(batch, root, task_id, cid, verdict, reason, verifier)
    return rows

def summarize(rows):
    total, det = len(rows), sum(1 for r in rows if r["replay_status"] == "deterministic")
    mraw = [r for r in rows if r["replay_status"] == "missing_raw"]
    tax = json.loads(TAX.read_text(encoding="utf-8"))["totals"]
    det_in_mraw = sum(1 for r in mraw if r["original_verdict"] == "deterministic")
    det_tax, tax_req = int(tax["deterministic_claims"]), int(tax["requirements"])
    baseline_match = (total == tax_req) and (det == 0) and (det_in_mraw == det_tax)
    dist: dict[str, int] = {}
    urt: dict[str, int] = {}
    for r in rows:
        k = "deterministic" if r["replay_status"] == "deterministic" else (
            "deliverable_not_in_request:*" if (r["replay_reason"] or "").startswith("deliverable_not_in_request:")
            else (r["replay_reason"] or "missing_raw"))
        dist[k] = dist.get(k, 0) + 1
        if (r["original_reason"] or "").startswith("unsupported_recompute_type:"):
            t = r["original_reason"].split(":", 1)[1]
            urt[t] = urt.get(t, 0) + 1
    return {"total": total, "replayable": total - len(mraw), "deterministic": det,
            "unverified": sum(1 for r in rows if r["replay_status"] == "unverified"), "missing_raw": len(mraw),
            "missing_raw_claims": [{**r, "why": r["original_reason"] or "deterministic claim; raw fields not saved"} for r in mraw],
            "reason_distribution": dict(sorted(dist.items())),
            "unsupported_recompute_types": dict(sorted(urt.items())),
            "baseline": {"taxonomy_deterministic": det_tax, "replay_deterministic_within_replayable": det,
                         "deterministic_in_missing_raw": det_in_mraw, "baseline_match": baseline_match,
                         "explanation": (f"replayable={total - len(mraw)} 集合內 deterministic={det}：當前代碼（extract.py/checks.py 凍結 blob）下，"
                                         "原本 unverified 者無一翻成 deterministic（與原判時同代碼）。taxonomy 的 "
                                         f"{det_tax} 條 deterministic（g3_2_prerun dab_725 R1/R6）落在 missing_raw：來源報告只存 claim id、"
                                         "未存 verifier/deliverable/params/quote，重播即造假；另 1 條 missing_param:values 因 params 未存同列 missing_raw。")}}

def selftest() -> int:
    ut, inputs = load_task("g3_2", "dab_725")
    keys = [{"key": "mean1", "type": "number"}]
    fails = []

    def check(name, cond):
        print(f"  {'ok   ' if cond else 'FAIL '} {name}")
        fails.append(name) if not cond else None

    print("replay_claims selftest (zero model):")
    ok, r = judge_claim("answer_kv", "data/auto-mpg.csv", {"keys": keys}, ut, inputs)
    check("neg1 deliverable=輸入 CSV 路徑 → 非 deterministic", (not ok) and r == "deliverable_is_input_file")
    ok, r = judge_claim("answer_kv", "no_such_output_9x7z.csv", {"keys": keys}, ut, inputs)
    check("neg2 deliverable=不存在的檔名 → 非 deterministic", (not ok) and r.startswith("deliverable_not_in_request"))
    ok, r = judge_claim("totally_bogus_verifier", "answer.txt", {}, ut, inputs)
    check("neg3 verifier 不在白名單 → 非 deterministic", (not ok) and r == "unknown_verifier:totally_bogus_verifier")
    ok, r = judge_claim("answer_kv", "answer.txt", {"keys": keys}, ut, inputs)
    check("pos  有效交付物 answer.txt → deterministic", ok and r is None)
    check("replay urt:mean_col 當前非 deterministic", replay_reason("unsupported_recompute_type:mean_col", ut, inputs, "plain_recomputed")[0] is False)
    check("replay missing_param → missing_raw（不造假）", replay_reason("missing_param:values", ut, inputs) == (None, None))
    s = summarize(collect())
    check("76 條全收齊且基線對帳通過", s["total"] == 76 and s["baseline"]["baseline_match"] is True)
    if fails:
        print(f"SELFTEST FAIL ({len(fails)}): {fails}")
        return 1
    print("SELFTEST PASS")
    return 0

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="replay_claims")
    ap.add_argument("--selftest", action="store_true", help="跑負/正控制與基線對帳後即回")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    rows = collect()
    s = summarize(rows)
    doc = {"ticket": "P20261113_0300-1-d1-offline-claim-replay",
           "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "code_sha": code_sha(),
           "raw_fields_saved": {"verifier": "g3_2_fire 26/26；其餘三來源 0/50", "deliverable": "僅 reason 內截斷 60 字元",
                                "params": "0/76（未存）", "quote": "0/76（未存）"},
           "totals": s, "claims": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"寫入 {OUT}（{s['total']} 條）")
    print(f"REPLAY replayable={s['replayable']} deterministic={s['deterministic']} baseline_match={s['baseline']['baseline_match']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
