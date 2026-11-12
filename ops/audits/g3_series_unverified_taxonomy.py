#!/usr/bin/env python3
"""G3 系列跨批 unverified 原因機械分類審計（票 R20261112_0422-1；0 model calls，報告只讀）。

對 4 份 in-repo 審計報告機械重算（分母明示；g3_3 僅計第 3 次獨立呼叫，
其 call1/call2 即 g3_2 預跑/fire 的既有 2 點，不重複計入）：
1) 需求總數 76＝18+27+26+5；確定性 claim 2/76；unverified 總數 74/76；
2) reason 前綴分佈（52/14/4/3/1）；
3) 52 條 deliverable_not_in_request 子串分類（自短句恢復檔名的真實比例）：
   contains_answer_txt 14／contains_input_path_only 6／no_filename_token 32。
本審計為 g3_3_candidate_hypothesis.md 第 7–9 行過度宣稱之更正依據（該檔 r1485 註記）。
用法：python3 ops/audits/g3_series_unverified_taxonomy.py --run | --selftest
"""
import argparse
import hashlib
import json
import pathlib
from collections import Counter
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parents[2]
AUD = REPO / "ops/audits"
FILES = {
    "g3_1_prerun": AUD / "g3_1_h20_prerun_report.json",
    "g3_2_prerun": AUD / "g3_2_h0_prerun_report.json",
    "g3_2_fire": AUD / "g3_2_fire_summary.json",
    "g3_3_call3": AUD / "g3_3_h0_stability_report.json",
}
OUT = AUD / "g3_series_unverified_taxonomy.json"
DNR = "deliverable_not_in_request"


def classify(raw: str) -> str:
    if "answer.txt" in raw:
        return "contains_answer_txt"
    if "data/" in raw or ".csv" in raw:
        return "contains_input_path_only"
    return "no_filename_token"


def load_batches() -> dict:
    def J(b):
        return json.loads(FILES[b].read_text(encoding="utf-8"))
    g1, g2, fs, g3 = J("g3_1_prerun"), J("g3_2_prerun"), J("g3_2_fire"), J("g3_3_call3")
    new = [c for c in g3["calls"] if c.get("unverified_claims") is not None]
    assert len(new) == 1, f"g3_3 報告應恰 1 次呼叫帶 unverified 明細：{len(new)}"
    c3 = new[0]
    tc = lambda d: [c["reason"] for t in d["tasks"] for c in t.get("unverified_claims", [])]
    det = lambda d: sum(t.get("n_deterministic_claims", 0) for t in d["tasks"])
    nr = lambda d: sum(t["n_requirements"] for t in d["tasks"])
    return {
        "g3_1_prerun": {"n_requirements": nr(g1), "n_deterministic": det(g1), "claims": tc(g1), "ids": None},
        "g3_2_prerun": {"n_requirements": nr(g2), "n_deterministic": det(g2), "claims": tc(g2), "ids": None},
        "g3_2_fire": {"n_requirements": nr(fs),
                      "n_deterministic": int(fs["claims"]["deterministic_cells"].split("/")[0]),
                      "claims": [r for t in fs["tasks"] for r in t.get("unverified_reasons", {}).values()],
                      "ids": None},
        "g3_3_call3": {"n_requirements": c3["n_requirements"],
                       "n_deterministic": c3.get("n_deterministic_claims", 0),
                       "claims": [c["reason"] for c in c3["unverified_claims"]],
                       "ids": [c["id"] for c in c3["unverified_claims"]]},
    }


def build(batches: dict, classifier=classify) -> dict:
    per, dist, dnr = {}, Counter(), []
    for b, v in batches.items():
        dnr_ = [c.split(":", 1)[1] for c in v["claims"] if c.startswith(DNR + ":")]
        e = {"n_requirements": v["n_requirements"], "n_deterministic": v["n_deterministic"],
             "n_unverified": len(v["claims"]), "dnr_total": len(dnr_),
             "dnr_taxonomy": dict(Counter(classifier(x) for x in dnr_))}
        if v.get("ids"):
            e["claims_by_id"] = {i: classifier(r.split(":", 1)[1]) for i, r in zip(v["ids"], v["claims"])}
        per[b] = e
        dist.update(c.split(":", 1)[0] for c in v["claims"])
        dnr.extend(dnr_)
    return {
        "schema": "vacant.audit/g3_series_taxonomy/1", "ticket": "R20261112_0422-1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": {b: {"file": str(FILES[b].relative_to(REPO)),
                        "sha256": hashlib.sha256(FILES[b].read_bytes()).hexdigest()} for b in batches},
        "totals": {"requirements": sum(e["n_requirements"] for e in per.values()),
                   "deterministic_claims": sum(e["n_deterministic"] for e in per.values()),
                   "unverified": sum(e["n_unverified"] for e in per.values()),
                   "prefix_distribution": dict(dist), "dnr_total": len(dnr),
                   "dnr_taxonomy": dict(Counter(classifier(x) for x in dnr))},
        "per_batch": per,
        "note": "0 model calls；hidden/scorer 未讀；g3_3 僅計第 3 次獨立呼叫（既有 2 點不重複計）",
    }


EXPECTED = {
    "totals": {"requirements": 76, "deterministic_claims": 2, "unverified": 74,
               "prefix_distribution": {DNR: 52, "unsupported_recompute_type": 14,
                                       "model_declared_unverified": 4, "unknown_verifier": 3, "missing_param": 1},
               "dnr_total": 52,
               "dnr_taxonomy": {"contains_answer_txt": 14, "contains_input_path_only": 6, "no_filename_token": 32}},
    "per": {"g3_1_prerun": (18, 18), "g3_2_prerun": (27, 25), "g3_2_fire": (26, 26), "g3_3_call3": (5, 5)},
    "g3_3_call3_dnr": {"contains_answer_txt": 1, "contains_input_path_only": 1, "no_filename_token": 3},
    "g3_3_call3_claims": {"R1": "no_filename_token", "R2": "no_filename_token", "R3": "no_filename_token",
                          "R4": "contains_answer_txt", "R5": "contains_input_path_only"},
}


def verify(res: dict) -> list:
    v = []

    def eq(key, got, want):
        if got != want:
            v.append(f"{key}: got {got!r} want {want!r}")

    t = res.get("totals")
    if t is None:
        return ["totals: missing"]
    eq("totals", t, EXPECTED["totals"])
    pb = res.get("per_batch", {})
    for b, (req, unv) in EXPECTED["per"].items():
        e = pb.get(b) or {}
        eq(f"per[{b}].n_requirements", e.get("n_requirements"), req)
        eq(f"per[{b}].n_unverified", e.get("n_unverified"), unv)
    g = pb.get("g3_3_call3", {})
    eq("g3_3_call3.dnr_taxonomy", g.get("dnr_taxonomy"), EXPECTED["g3_3_call3_dnr"])
    eq("g3_3_call3.claims_by_id", g.get("claims_by_id"), EXPECTED["g3_3_call3_claims"])
    return v


def _report(ok: list) -> int:
    failed = [(n, d) for n, passed, d in ok if not passed]
    if failed:
        for n, d in failed:
            print(f"CONTROL FAILED: {n}: {d[:3]}")
        print("VERDICT: G3_SERIES_TAXONOMY_BROKEN")
        return 1
    print("positive control（真檔＋關鍵恆等）＋負控制 3（數字篡改／分類篡改／空集 fail-closed）全如預期")
    print("VERDICT: G3_SERIES_TAXONOMY_OK")
    return 0


def selftest() -> int:
    batches = load_batches()
    vpos = verify(build(batches))
    ok = [("positive：真檔重算＝票面分母", not vpos, vpos)]
    b1 = {k: dict(v) for k, v in batches.items()}
    b1["g3_1_prerun"] = dict(b1["g3_1_prerun"])
    b1["g3_1_prerun"]["claims"] = b1["g3_1_prerun"]["claims"][:-1]  # 篡改數字：18→17
    ok.append(("negative1：數字篡改（g3_1 −1 claim）必紅", bool(verify(build(b1))), None))

    def bad(raw):  # 篡改分類：漏掉 answer.txt 規則
        if "data/" in raw or ".csv" in raw:
            return "contains_input_path_only"
        return "no_filename_token"

    ok.append(("negative2：分類篡改（漏 answer.txt 規則）必紅", bool(verify(build(batches, classifier=bad))), None))
    empty = {b: {"n_requirements": 0, "n_deterministic": 0, "claims": [], "ids": None} for b in batches}
    ok.append(("negative3：空集 fail-closed 必紅", bool(verify(build(empty))), None))
    return _report(ok)


def run() -> int:
    res = build(load_batches())
    v = verify(res)
    if v:
        for x in v:
            print("VIOLATION:", x)
        print("VERDICT: G3_SERIES_TAXONOMY_BROKEN")
        return 1
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    t = res["totals"]
    print(f"written: {OUT.relative_to(REPO)}（{t['requirements']} req／{t['deterministic_claims']} det／"
          f"{t['unverified']} unv；dnr {t['dnr_total']}＝{t['dnr_taxonomy']}）")
    print("VERDICT: G3_SERIES_TAXONOMY_OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run", action="store_true", help="重算 4 份報告並寫出 JSON")
    g.add_argument("--selftest", action="store_true", help="正控制＋3 負控制")
    a = ap.parse_args()
    return selftest() if a.selftest else run()


if __name__ == "__main__":
    raise SystemExit(main())
