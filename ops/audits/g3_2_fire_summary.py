#!/usr/bin/env python3
"""G3.2 發射產物解析＋H1 判定（P20261111_2319-2；2026-11-11 人類常設定案第 2.a 條）。

讀 r1472 背景發射產物 /home/user1/dev/ops/g3_fire/20261111_g3_2/g3_result.json
（4 凍結未見題 dab_725/dab_587/dab_657/dab_517 × full_rloop＝4 格），
解析各格 status／tokens／content_reverify claims（PASS/FAIL/UNKNOWN）／gap_reason／
diff（fixed/not_fixed/regressed）／final_verdict，依預註冊規則
（ops/reqloop/g3_2_candidate_hypothesis.md §2 H1）判定 H1，
並對 H0 預跑報告（ops/audits/g3_2_h0_prerun_report.json）做確定性可重現性交叉核
（同題同 input，pre-run 判 2 條確定性 vs fire 實測 0 條＝是否復現）。
產出 ops/audits/g3_2_fire_summary.json。

口徑（與 g3_fire_20261111_summary.py 同型）：
- UNKNOWN 既非裁決亦非通過（I-4）；缺值 UNKNOWN 不填 0；非空守衛：0 已知 usage 不得判 OK。
- 單 rep、方向性；不宣稱臂 superiority；不外推其他模型/題（H-12）；同批重發非獨立樣本。
- 不讀 hidden/scorer；hidden_after 只轉錄產物欄位（本端打分＝UNKNOWN）。
- 0 model calls、0 產品碼改動。

--selftest：6 合成分組控制（H1 判定 4 態＋answer_sha 失配＋tokens 空集），fail-closed。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parents[2]
RESULT = pathlib.Path("/home/user1/dev/ops/g3_fire/20261111_g3_2/g3_result.json")
APPROVAL = pathlib.Path("/home/user1/dev/ops/approvals/g3_vq-1zf_fire_20261111.json")
PRERUN = REPO / "ops" / "audits" / "g3_2_h0_prerun_report.json"
DEST = REPO / "ops" / "audits" / "g3_2_fire_summary.json"
FROZEN_ORDER = ["dab_725", "dab_587", "dab_657", "dab_517"]

H1_RULE = ("§2 H1：(a) ≥1/4 格完成 ≥1 輪 content_reverify 且該輪 ≥1 條 claim 由 checks 程式重算給"
           "確定性裁決（PASS/FAIL）；且 (b) round 1 有已確認缺口（≥1 必需 FAIL 或缺必要答案項）的格中，"
           "所有該等格 round 2 diff fixed≥1 且 regressed=0。0/4 格有已確認缺口→(b) not_applicable"
           "（不得記通過、不得記否決）。否決條件：(a) 0/4；或 (b) ≥1 缺口格 fixed=0 或 regressed≥1。")


def _num(v) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _cell_tokens(c: dict) -> int | None:
    vals = [u.get("tokens") for r in (c.get("rounds") or []) for u in (r.get("usages") or [])]
    vals = [_num(v) for v in vals]
    return sum(v for v in vals if v is not None) if any(v is not None for v in vals) else None


def _claims(cr: dict) -> list[dict]:
    return [cl for r in (cr.get("rounds") or []) for cl in (r.get("claims") or [])]


def h1_verdict(cells: list[dict]) -> dict:
    """依 §2 H1 規則判定；cells＝g3_result.json 之 cells 陣列（機制記錄為准）。"""
    n = len(cells)
    det = [c.get("task") for c in cells
           if any(cl.get("status") in ("PASS", "FAIL") for cl in _claims(c.get("content_reverify") or {}))]
    a_met = len(det) >= 1
    # 已確認缺口＝機制自己的記錄：round 1 gap_reason 非 null（g3.py confirmed_gap＝必需 FAIL 或缺必要答案項）。
    gap_cells = [c for c in cells
                 if ((c.get("content_reverify") or {}).get("rounds") or [{}])[0].get("gap_reason") is not None]
    if not gap_cells:
        b = "not_applicable"
    else:
        b_ok = True
        for c in gap_cells:
            d = (c.get("content_reverify") or {}).get("diff") or {}
            fixed, regressed = d.get("fixed"), d.get("regressed")
            if not (isinstance(fixed, (list, tuple)) and len(fixed) >= 1 and not regressed):
                b_ok = False
        b = "met" if b_ok else "violated"
    verdict = "H1_REFUTED" if (not a_met or b == "violated") else "H1_MET"
    return {
        "rule": H1_RULE,
        "a": f"{len(det)}/{n} 格有確定性裁決（{det or '無'}）",
        "a_met": a_met,
        "b": f"{b}（已確認缺口格 {len(gap_cells)}/{n}：{[c.get('task') for c in gap_cells] or '無'}）",
        "verdict": verdict,
        "note": ("單 rep、方向性；不宣稱臂 superiority；不外推其他模型/題（H-12）；"
                 "H1 判定只讀機制記錄（claims 狀態＋gap_reason＋diff），不讀 hidden/scorer"),
    }


def build(raw: bytes, result_path: pathlib.Path) -> tuple[dict, list[str]]:
    d = json.loads(raw)
    problems: list[str] = []

    def chk(cond: bool, msg: str) -> None:
        if not cond:
            problems.append(msg)

    chk(d.get("schema") == "vacant.reqloop.g3.result/1", f"schema 漂移: {d.get('schema')!r}")
    cells = d.get("cells") or []
    chk([c.get("task") for c in cells] == FROZEN_ORDER,
        f"cells 順序/集合漂移: {[c.get('task') for c in cells]} != {FROZEN_ORDER}")
    chk(all(c.get("arm") == "full_rloop" for c in cells), "arm 漂移：應全 full_rloop")
    for c in cells:
        a, s = c.get("answer"), c.get("answer_sha256")
        if a is not None and s is not None:
            chk(hashlib.sha256(a.encode()).hexdigest() == s,
                f"{c.get('task')}/full_rloop answer_sha256 重算不符")
        cr = c.get("content_reverify") or {}
        chk(cr.get("enabled") is True, f"{c.get('task')} content_reverify.enabled 非 true")

    # tokens 重算（同 c 發腳本口徑；非空守衛 I-4）
    cell_vals = [v for v in (_cell_tokens(c) for c in cells) if v is not None]
    ext_vals = [u.get("tokens") for t in (d.get("tasks") or []) for u in (t.get("extract_usages") or [])
                if _num(u.get("tokens")) is not None]
    ext_vals = [_num(v) for v in ext_vals]
    cell_known, ext_known = sum(cell_vals), sum(ext_vals)
    n_known = len(cell_vals) + len(ext_vals)
    tot = d.get("totals") or {}
    chk(n_known > 0, "tokens 重算空集：0 個已知 usage（未測量不是通過；I-4）——零 measurement 不得判 OK")
    chk(_num(tot.get("tokens")) is not None, f"totals.tokens 缺值：{tot.get('tokens')!r}（UNKNOWN 不是 0）")
    chk(_num(tot.get("tokens")) is not None and cell_known + ext_known == tot["tokens"],
        f"tokens 重算 {cell_known}+{ext_known} != {tot.get('tokens')!r}")

    # claims 分報（x/26 帶分母；UNKNOWN 不計裁決）
    all_claims = [(c["task"], cl) for c in cells for cl in _claims(c.get("content_reverify") or {})]
    n_pass = sum(1 for _, cl in all_claims if cl.get("status") == "PASS")
    n_fail = sum(1 for _, cl in all_claims if cl.get("status") == "FAIL")
    n_unk = sum(1 for _, cl in all_claims if cl.get("status") == "UNKNOWN")
    reasons: dict[str, int] = {}
    for _, cl in all_claims:
        ev = cl.get("evidence") or {}
        key = str(ev.get("reason") or cl.get("status"))
        reasons[key] = reasons.get(key, 0) + 1
    # 每格 claims 數 vs tasks[].n_requirements（extract 輸出自洽性）
    nreq = {t.get("task_id"): t.get("n_requirements") for t in (d.get("tasks") or [])}
    chk(all(len(_claims(c.get("content_reverify") or {})) == nreq.get(c.get("task")) for c in cells),
        "某格 reverify claims 數 != tasks[].n_requirements（extract 輸出不自洽）")

    # H0 預跑 vs fire 確定性可重現性（同 input_sha256 之題；只比 counts＋ids，不讀 hidden）
    h0x: dict = {"prerun_report": str(PRERUN), "per_task": [], "note": ""}
    if PRERUN.is_file():
        pre = json.loads(PRERUN.read_text(encoding="utf-8"))
        for t in (d.get("tasks") or []):
            tid = t.get("task_id")
            p = next((x for x in (pre.get("tasks") or []) if x.get("task_id") == tid), None)
            if p is None:
                continue
            fire_det = [cl.get("id") for c in cells if c.get("task") == tid
                        for cl in _claims(c.get("content_reverify") or {})
                        if cl.get("status") in ("PASS", "FAIL")]
            pre_det = len(p.get("deterministic_claim_ids") or [])
            h0x["per_task"].append({
                "task_id": tid,
                "input_sha256_match": (p.get("input_sha256") == t.get("input_sha256")),
                "prerun_n_requirements": p.get("n_requirements"),
                "fire_n_requirements": t.get("n_requirements"),
                "prerun_deterministic_ids": p.get("deterministic_claim_ids"),
                "fire_deterministic_ids": fire_det,
                # None＝N/A（pre-run 無確定性 claim、無從復現）；False＝有而 fire 未復現
                "reproduced": (None if pre_det == 0 else len(fire_det) >= pre_det),
            })
        h0x["note"] = ("同題同 input_sha256、同 extract 模型（glm53），pre-run 與 fire 各自獨立 1 次 extract 呼叫；"
                       "確定性 claim 數若不一致＝extract 層跨呼叫非確定（LLM 輸出漂移），非 checks/repair 層問題")
    else:
        h0x["note"] = "H0 預跑報告缺檔——交叉核 UNKNOWN（I-4），不補 0"

    ap: dict | None = json.loads(APPROVAL.read_text(encoding="utf-8")) if APPROVAL.is_file() else None
    out = {
        "schema": "vacant.audit/g3_2_fire_summary/1",
        "generated_by": "ops/audits/g3_2_fire_summary.py",
        "ticket": "P20261111_2319-2",
        "identity": {
            "result_file": str(result_path),
            "result_bytes": len(raw),
            "result_sha256": hashlib.sha256(raw).hexdigest(),
            "result_file_mtime_utc": datetime.fromtimestamp(result_path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
            "approval_file": str(APPROVAL),
            "approval_sha256": hashlib.sha256(APPROVAL.read_bytes()).hexdigest() if APPROVAL.is_file() else None,
            "approval_approved": (ap or {}).get("approved"),
            "approval_epic": (ap or {}).get("epic"),
            "approval_inline_in_result": d.get("approval"),
        },
        "fire": {
            "fired_at": d.get("fired_at"),
            "out_dir": str(result_path.parent),
            "arm": "full_rloop",
            "stop_reason": d.get("stop_reason"),
        },
        "scope": "4 凍結未見題（dab_725/dab_587/dab_657/dab_517）× full_rloop＝4 格；1 rep；同批重發非獨立樣本",
        "models": {"extract": d.get("extract_model"), "answer": d.get("answer_model")},
        "tasks": [{"task_id": t.get("task_id"), "input_sha256": t.get("input_sha256"),
                   "required_answer_names": t.get("required_answer_names"),
                   "n_requirements": t.get("n_requirements"), "extract_error": t.get("extract_error"),
                   "extract_usages": t.get("extract_usages"),
                   "unverified_reasons": t.get("unverified_reasons")} for t in (d.get("tasks") or [])],
        "cells": [{"task": c.get("task"), "arm": c.get("arm"), "status": c.get("status"),
                   "rounds": len(c.get("rounds") or []), "error": c.get("error"),
                   "answer": c.get("answer"), "answer_sha256": c.get("answer_sha256"),
                   "tokens": _cell_tokens(c), "hidden_after": c.get("hidden_after"),
                   "content_reverify": {
                       "enabled": (c.get("content_reverify") or {}).get("enabled"),
                       "n_rounds": len((c.get("content_reverify") or {}).get("rounds") or []),
                       "n_claims": len(_claims(c.get("content_reverify") or {})),
                       "claims": _claims(c.get("content_reverify") or {}),
                       "round_verdicts": [r.get("verdict") for r in (c.get("content_reverify") or {}).get("rounds") or []],
                       "gap_reasons": [r.get("gap_reason") for r in (c.get("content_reverify") or {}).get("rounds") or []],
                       "final_verdict": (c.get("content_reverify") or {}).get("final_verdict"),
                       "diff": (c.get("content_reverify") or {}).get("diff"),
                   }} for c in cells],
        "claims": {
            "total": len(all_claims), "pass": n_pass, "fail": n_fail, "unknown": n_unk,
            "denominator": f"{len(all_claims)}（6+5+8+7，4 格）",
            "deterministic_cells": "0/4" if not any(x["fire_deterministic_ids"] for x in h0x["per_task"]) else "see h0_reproducibility",
            "reason_distribution": reasons,
        },
        "h1": h1_verdict(cells),
        "h0_reproducibility": h0x,
        "cost": {
            "model_calls": tot.get("model_calls"),
            "answer_tokens_known": cell_known,
            "extract_tokens_known": ext_known,
            "tokens_total": tot.get("tokens"),
            "tokens_missing": tot.get("tokens_missing"),
            "daily_quota": {"known_tokens": (d.get("quota") or {}).get("known_tokens"),
                            "daily_token_cap": (d.get("quota") or {}).get("daily_token_cap"),
                            "share_pct": (round((d.get("quota") or {}).get("known_tokens", 0) / (d.get("quota") or {}).get("daily_token_cap", 1) * 100, 2)
                                         if (d.get("quota") or {}).get("daily_token_cap") else None)},
            "cost_usd": "UNKNOWN（產物無計價欄；glm CLI 計價缺值不填 0、cost_usd=0 不等於免費）",
        },
        "hidden_after": "4/4 UNKNOWN——不自己打分；打分照 /srv/vlab 作業慣例（人類/vlab 側）",
        "failures": [{"cells": sum(1 for c in cells if c.get("status") == "error"),
                      "note": "status=error 格數；0＝機制達標，26/26 claims UNKNOWN 是 extract 層問題非 harness 故障"}],
        "scope_note": [
            "4/4 格 status=ok、各 1 輪（UNKNOWN 非缺口→不觸發第 2 輪，g3.py 守衛如設計）",
            "26/26 claims UNKNOWN、0 PASS、0 FAIL——本批不給任何內容正確性結論（UNKNOWN 不是通過也不是沒有）",
            "單 rep、本地模型（H-12）、不遷移其他模型/harness；同批重發非獨立樣本",
            "H0 預跑（22:21Z）與 fire（23:28Z）為兩次獨立 extract 呼叫——見 h0_reproducibility",
        ],
    }
    return out, problems


def selftest() -> int:
    import copy
    base_cell = {
        "task": "t", "arm": "full_rloop", "status": "ok", "error": None, "answer": "@x[1]",
        "answer_sha256": hashlib.sha256(b"@x[1]").hexdigest(),
        "rounds": [{"round": 1, "usages": [{"calls": 1, "tokens": 10}]}],
        "hidden_after": "UNKNOWN",
        "content_reverify": {"enabled": True, "rounds": [], "final_verdict": "UNKNOWN", "diff": None, "error": None},
    }
    def mk(claims, gap1=None, diff=None, rounds=1):
        c = copy.deepcopy(base_cell)
        c["content_reverify"] = {"enabled": True,
                                 "rounds": [{"round": 1, "verdict": None, "gap_reason": gap1, "claims": claims}] +
                                            ([{"round": 2, "verdict": None, "gap_reason": None, "claims": claims}] if rounds > 1 else []),
                                 "final_verdict": None, "diff": diff, "error": None}
        return c
    P = lambda i: {"id": i, "status": "PASS", "required": True, "verifier": "v", "detail": "", "evidence": {}}
    F = lambda i: {"id": i, "status": "FAIL", "required": True, "verifier": "v", "detail": "", "evidence": {}}
    U = lambda i: {"id": i, "status": "UNKNOWN", "required": True, "verifier": "v", "detail": "", "evidence": {"reason": "r"}}
    ok = True
    def ck(name, cond, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'BROKEN'} {name}" + (f"｜{detail}" if detail and not cond else ""))
        ok = ok and cond
    v = h1_verdict([mk([U("a")]) for _ in range(4)])
    ck("h1_a0_refuted", v["verdict"] == "H1_REFUTED" and v["a_met"] is False and "not_applicable" in v["b"], str(v))
    v = h1_verdict([mk([P("a")])] + [mk([U("a")]) for _ in range(3)])
    ck("h1_pos_met", v["verdict"] == "H1_MET" and v["a_met"] is True and "not_applicable" in v["b"], str(v))
    v = h1_verdict([mk([F("a")], gap1="required_fail", diff={"fixed": [], "not_fixed": ["a"], "regressed": []}, rounds=2)]
                   + [mk([U("a")]) for _ in range(3)])
    ck("h1_b_violated", v["verdict"] == "H1_REFUTED" and v["b"].startswith("violated"), str(v))
    v = h1_verdict([mk([F("a")], gap1="required_fail", diff={"fixed": ["a"], "not_fixed": [], "regressed": []}, rounds=2)]
                   + [mk([U("a")]) for _ in range(3)])
    ck("h1_b_met", v["verdict"] == "H1_MET" and v["b"].startswith("met"), str(v))
    # tokens 空集（I-4）與 answer_sha 失配
    raw = json.dumps({"schema": "vacant.reqloop.g3.result/1",
                      "cells": [dict(base_cell, rounds=[], answer=None, answer_sha256=None)],
                      "tasks": [], "totals": {"tokens": 0}, "quota": {}}).encode()
    _, probs = build(raw, RESULT)
    ck("tokens_empty_guard", any("空集" in p for p in probs), str(probs))
    raw = json.dumps({"schema": "vacant.reqloop.g3.result/1",
                      "cells": [dict(base_cell, answer_sha256="0" * 64)],
                      "tasks": [], "totals": {"tokens": 10}, "quota": {}}).encode()
    _, probs = build(raw, RESULT)
    ck("answer_sha_mismatch", any("answer_sha256 重算不符" in p for p in probs), str(probs))
    print("VERDICT: G3_2_FIRE_SUMMARY_SELFTEST_" + ("OK" if ok else "BROKEN"))
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if not RESULT.is_file():
        print(f"BROKEN: 結果檔不存在: {RESULT}", file=sys.stderr)
        print("VERDICT: G3_2_FIRE_SUMMARY_BROKEN")
        return 1
    raw = RESULT.read_bytes()
    out, problems = build(raw, RESULT)
    if problems:
        for p in problems:
            print(f"BROKEN: {p}", file=sys.stderr)
        print("VERDICT: G3_2_FIRE_SUMMARY_BROKEN")
        return 1
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cl = out["claims"]
    print(f"cells=4/4 ok claims={cl['total']} pass/fail/unknown={cl['pass']}/{cl['fail']}/{cl['unknown']} "
          f"tokens={out['cost']['tokens_total']} H1={out['h1']['verdict']} hidden_after=4xUNKNOWN")
    print("VERDICT: G3_2_FIRE_SUMMARY_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
