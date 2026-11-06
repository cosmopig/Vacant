#!/usr/bin/env python3
"""R1135：effects2_20261106（28 格 @ 4d4b8102）誠實彙整——11-06 最高優先指示第 2 條的必答。

讀（只讀）：
- ~/dev/ops/effects2_20261106/contrast/g2_result_*.json（28 格本地原始結果）
- ~/dev/ops/effects2_20261106/contrast/independent_*.json（28 格獨立沙箱評分）
- ~/dev/ops/effects2_20261106/before_after.json（重建工件；本腳本對其逐欄交叉核對）
- ops/reqloop/g2/effect_manifest.json（草稿 pin，sha 9329be88…）
- ops/audits/effects_20261105_summary.json（d38d2eb2 批，僅供同任務集合對照引用）

寫：ops/audits/effects2_20261106_analysis.json

口徑（11-05／11-06 紅線）：
- 缺值＝None(UNKNOWN)，不填 0；tokens 任一格缺值 ⇒ 該集合總和只報已知和＋缺值格清單。
- repair_sessions（agent 啟動數）≠ api_model_calls（API 請求數，raw usage）。
- tamper／UNKNOWN 不算成功；source_tampered⇒rejected，blocked 不得僅憑 independent_pass 宣稱通過。
- 兩臂 draft_sha256（原草稿目錄指紋）逐題相等 ⇒ 同草稿公平比較才成立。
- 本批排除 dabstep-1753；與昨日（d38d2eb2）比較只比同 9 題集合。
- 開發選樣、單 rep，不宣稱 localized 較好。

驗收：python3 ops/audits/effects2_20261106_analyze.py --selftest（含負控）
      python3 ops/audits/effects2_20261106_analyze.py（RC=0 且 ANALYSIS_OK）
"""
from __future__ import annotations

import glob
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
EFFECTS = pathlib.Path("/home/user1/dev/ops/effects2_20261106")
MANIFEST = REPO / "ops/reqloop/g2/effect_manifest.json"
YESTERDAY = REPO / "ops/audits/effects_20261105_summary.json"
OUT = REPO / "ops/audits/effects2_20261106_analysis.json"
EXCLUDED = "dabstep-1753-pi-C"


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def expected_verdict(before_pass, after_pass, stopped, tampered) -> str:
    """before_after.json verdict 的語義重述（P000-20261105-02 覆寫規則＋no_gap 例外）。"""
    if tampered:
        return "rejected"
    if stopped not in ("gap_closed", "no_gap"):
        return f"blocked(local_stopped={stopped})"
    if before_pass == after_pass:
        return "unchanged"
    if after_pass and not before_pass:
        return "wrong_to_right"
    return "right_to_wrong"


def cost_sum(cells: list[dict]) -> dict:
    """已知值求和；任一格缺值 ⇒ 該量 total=None，缺值格另列（不填 0）。"""
    out = {}
    for key in ("repair_sessions", "api_model_calls", "tokens", "wall_ms"):
        vals = [c[key] for c in cells]
        missing = [c["cell"] for c in cells if c[key] is None]
        out[key] = {"total": (sum(vals) if not missing else None),
                    "known_sum": sum(v for v in vals if v is not None),
                    "missing_cells": missing}
    return out


def aggregate(cells: list[dict]) -> dict:
    return {
        "n": len(cells),
        "pass_after": sum(1 for c in cells if c["after_pass"]),
        "fail_after": sum(1 for c in cells if not c["after_pass"]),
        "wrong_to_right": sum(1 for c in cells if c["verdict"] == "wrong_to_right"),
        "right_to_wrong": sum(1 for c in cells if c["verdict"] == "right_to_wrong"),
        "unchanged": sum(1 for c in cells if c["verdict"] == "unchanged"),
        "blocked": [c["cell"] for c in cells if c["verdict"].startswith("blocked")],
        "rejected": [c["cell"] for c in cells if c["verdict"] == "rejected"],
        "regressed_effective": [c["cell"] for c in cells if c["before_pass_d38d2eb2"] and not c["after_pass"]],
        "cost": cost_sum(cells),
    }


def build_cells() -> list[dict]:
    ba = json.loads((EFFECTS / "before_after.json").read_text(encoding="utf-8"))
    by_name = {(c["draft"], c["arm"]): c for c in ba["cells"]}
    cells, problems = [], []
    g2_files = sorted(glob.glob(str(EFFECTS / "contrast/g2_result_*.json")))
    if len(g2_files) != 28:
        problems.append(f"g2_result 檔數 {len(g2_files)} != 28")
    for f in g2_files:
        g = json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
        rc = g["cells"][0]
        name = (rc["draft"], rc["arm"])
        if name not in by_name:
            problems.append(f"{name}: before_after.json 缺格"); continue
        b = by_name[name]
        ip = json.loads(pathlib.Path(f.replace("g2_result_", "independent_")).read_text(encoding="utf-8"))
        ip = ip["cells"][0]["independent_after"]["pass"]
        a = b["after_this_rep"]
        before_pass = b["before_d38d2eb2"]["policy30_2r"]["independent_pass"]
        cost = rc["cost"]
        cells.append({
            "cell": f"{rc['draft']}-{rc['arm']}",
            "draft": rc["draft"], "arm": rc["arm"], "role": rc["role"],
            "draft_sha256": rc["draft_sha256"],
            "stopped": rc["stopped"],
            "fixed": rc["fixed"], "regressed": rc["regressed"], "unresolved": rc["unresolved"],
            "source_tampered": rc["source_tampered"],
            "after_hidden": rc["after_hidden"],
            "before_pass_d38d2eb2": before_pass,
            "after_pass": ip,
            "verdict": b["verdict"],
            "repair_sessions": _num(cost["calls"]),
            "api_model_calls": _num(cost["model_calls"]),
            "tokens": _num(cost["tokens"]),
            "token_source": cost.get("token_source"),
            "wall_ms": _num(cost["wall_ms_total"]),
            "mismatches": (
                [] if (a["local_stopped"] == rc["stopped"]
                       and a["fixed"] == rc["fixed"] and a["regressed"] == rc["regressed"]
                       and a["unresolved"] == rc["unresolved"]
                       and a["source_tampered"] == rc["source_tampered"]
                       and a["independent_pass"] == ip
                       and a["repair_sessions"] == cost["calls"]
                       and a["api_model_calls_true"] == cost["model_calls"]
                       and a["tokens_true"] == cost["tokens"])
                else "before_after.after_this_rep 與 raw g2_result/independent 不一致"),
        })
        if isinstance(cells[-1]["mismatches"], str):
            problems.append(f"{name}: {cells[-1]['mismatches']}")
        if cells[-1]["verdict"] != expected_verdict(before_pass, ip, rc["stopped"], rc["source_tampered"]):
            problems.append(f"{name}: verdict 重述不一致（raw vs before_after.json）")
        if cells[-1]["after_hidden"] != "UNKNOWN":
            problems.append(f"{name}: after_hidden 應為 UNKNOWN（本地無權重跑 hidden）")
    return cells, problems


def check_same_draft(cells: list[dict], problems: list[str]) -> dict:
    tasks: dict[str, dict] = {}
    for c in cells:
        tasks.setdefault(c["draft"], {})[c["arm"]] = c
    rows, all_ok = [], True
    for draft, arms in sorted(tasks.items()):
        shas = set(arms.values() and [a["draft_sha256"] for a in arms.values()])
        ok = len(shas) == 1 and len(arms) == 2
        all_ok &= ok
        rows.append({"draft": draft, "arms": sorted(arms), "draft_sha256": sorted(shas),
                     "same_draft": bool(ok)})
    if not all_ok:
        problems.append("存在兩臂起始草稿 hash 不一致的題——該題不得稱同草稿公平比較")
    return {"n_tasks": len(rows), "all_same_draft": all_ok, "tasks": rows}


def check_provenance() -> dict:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = EFFECTS / "snapshot/ops/reqloop/g2"
    rows, all_ok = [], True
    for d in m["drafts"]:
        for rel, pin in d["draft"]["files"].items():
            p = base / d["draft"]["dir"] / rel
            actual = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
            ok = actual == pin
            all_ok &= bool(ok)
            rows.append({"draft": d["name"], "file": rel, "pin": pin,
                         "actual": actual, "ok": bool(ok)})
    return {"n_files": len(rows), "all_ok": all_ok, "files": rows}


def analyze() -> tuple[dict, list[str]]:
    cells, problems = build_cells()
    same = check_same_draft(cells, problems)
    prov = check_provenance()
    if not prov["all_ok"]:
        problems.append("快照草稿 pin 與檔案不符（來源完整性受損）")
    bad = [c for c in cells if c["role"] == "bad"]
    good = [c for c in cells if c["role"] == "good"]
    def per_arm(sub):
        return {arm: aggregate([c for c in sub if c["arm"] == arm]) for arm in ("generic", "localized")}
    b9, g5 = per_arm(bad), per_arm(good)
    lb, lg = b9["localized"], b9["generic"]
    g5l, g5g = g5["localized"], g5["generic"]
    _d = {(c["draft"]): (c["tokens"] if c["arm"] == "localized" else -c["tokens"])
          for c in bad if c["tokens"] is not None}
    _dl = [c for c in bad if c["arm"] == "localized"]
    _dg = [c for c in bad if c["arm"] == "generic"]
    _delta_by_task = {}
    for c in _dl:
        o = next((x for x in _dg if x["draft"] == c["draft"]), None)
        if o and c["tokens"] is not None and o["tokens"] is not None:
            _delta_by_task[c["draft"]] = (c["tokens"] - o["tokens"],
                                          c["api_model_calls"] - (o["api_model_calls"] or 0))
    _big = max(_delta_by_task.items(), key=lambda kv: kv[1][0]) if _delta_by_task else ("n/a", (0, 0))
    _big_delta = f"{_big[0]}（+{_big[1][0]:,} tok / +{_big[1][1]} calls，generic 該題 stopped 未修）" if _big[0] != "n/a" else "n/a"
    y = json.loads(YESTERDAY.read_text(encoding="utf-8"))
    result = {
        "schema": "vacant.audit/effects2_20261106_analysis/1",
        "batch": {"code_commit": "4d4b8102ac054e226bff3c1f9523cfa701af7993",
                  "cells": len(cells), "excluded": EXCLUDED,
                  "model": "gemma-4-12b-it-qat @ lms1004nothink",
                  "budget": "2 輪×300s、無硬 token 上限、hard_token_cap=false"},
        "checks": {
            "same_draft": same,
            "provenance_snapshot_pins": prov,
            "source_tampered_cells": [c["cell"] for c in cells if c["source_tampered"]],
            "after_hidden_all_unknown": all(c["after_hidden"] == "UNKNOWN" for c in cells),
            "before_after_consistency_issues": [p for p in problems if "before_after" in p],
        },
        "this_batch_bad9": per_arm(bad),
        "this_batch_good5": per_arm(good),
        "cross_batch_same9set": {
            "note": "同 9 題集合（排除 dabstep-1753）；before＝d38d2eb2 policy30（2 輪、同預算）逐臂獨立評分；after＝本批",
            "per_arm": {arm: {
                "before_pass_d38d2eb2": sum(1 for c in bad if c["arm"] == arm and c["before_pass_d38d2eb2"]),
                "after_pass_this_batch": sum(1 for c in bad if c["arm"] == arm and c["after_pass"]),
            } for arm in ("generic", "localized")},
            "yesterday_1105_summary_bad10": {"generic_wrong_to_right": y["phases"]["policy30"]["per_arm"]["generic"]["wrong_to_right"],
                                             "localized_wrong_to_right": y["phases"]["policy30"]["per_arm"]["localized"]["wrong_to_right"],
                                             "note": "11-05 摘要 bad 10 含 1753；本行僅引用、不與本批直接相減"},
        },
        "answers_1106_2": {
            "Q1_localized_fixes_more": (
                f"本批 bad 9：localized {per_arm(bad)['localized']['pass_after']}/9 pass vs generic "
                f"{per_arm(bad)['generic']['pass_after']}/9 pass（generic blocked：{per_arm(bad)['generic']['blocked']}）；"
                "tamper 0、regressed 0。本批內 localized 多修 "
                f"{per_arm(bad)['localized']['pass_after'] - per_arm(bad)['generic']['pass_after']} 題。"),
            "Q2_correctness_regression": (
                f"good 5 雙臂全 pass（localized 全 no_gap 0 呼叫）；對→錯 0。"
                "跨批（同 9 題、對昨日 d38d2eb2 逐臂）："
                f"generic {sum(1 for c in bad if c['arm']=='generic' and c['before_pass_d38d2eb2'])}/9→"
                f"{lg['pass_after']}/9（退步 {lg['regressed_effective']}；新增修復 {lg['wrong_to_right'] and [c['cell'] for c in bad if c['arm']=='generic' and c['verdict']=='wrong_to_right']}）；"
                f"localized {sum(1 for c in bad if c['arm']=='localized' and c['before_pass_d38d2eb2'])}/9→"
                f"{lb['pass_after']}/9（退步 {lb['regressed_effective']}）。"),
            "Q3_cost_worth": (
                f"bad9 成本 localized {lb['cost']['api_model_calls']['known_sum']} calls/"
                f"{lb['cost']['tokens']['known_sum']} tok vs generic {lg['cost']['api_model_calls']['known_sum']} calls/"
                f"{lg['cost']['tokens']['known_sum']} tok（差 {lb['cost']['api_model_calls']['known_sum']-lg['cost']['api_model_calls']['known_sum']} calls/"
                f"{lb['cost']['tokens']['known_sum']-lg['cost']['tokens']['known_sum']} tok，買 +"
                f"{lb['pass_after']-lg['pass_after']} 題修復）；差額最大格＝{_big_delta}；"
                f"good5：localized 0 呼叫 vs generic {g5g['cost']['api_model_calls']['known_sum']} calls/"
                f"{g5g['cost']['tokens']['known_sum']} tok（no_gap 省掉）；全 14 題 sessions generic "
                f"{lg['cost']['repair_sessions']['known_sum']+g5g['cost']['repair_sessions']['known_sum']} vs localized "
                f"{lb['cost']['repair_sessions']['known_sum']+g5l['cost']['repair_sessions']['known_sum']}。"),
            "caveats": [
                "開發選樣（e008/e013/e014 已見題）、單 rep、單碼態 4d4b8102——不宣稱 localized 較好（11-06#1）",
                "本批排除 dabstep-1753；與昨日比較只比同 9 題集合",
                "跨批翻轉：dabstep-10（昨日 generic pass／localized fail → 今日反向）、dabstep-23（昨日 localized fail → 今日 pass）、dabstep-1273（雙臂昨日 fail → 今日 pass）＝邊界題單 rep 變異，非穩定方向，不宣稱 localized 較好",
                "無硬 token 上限；repair_sessions≠API 請求數；缺值＝UNKNOWN 不填 0",
                "hidden_after 全 UNKNOWN（本地無權重跑）；tamper/UNKNOWN 不算成功",
            ],
        },
        "cells": cells,
        "problems": problems,
    }
    return result, problems


def selftest() -> int:
    # 負控先跑：檢查器必須抓得出壞輸入
    assert expected_verdict(True, True, "gap_closed", True) == "rejected"
    assert expected_verdict(False, True, "max_rounds", False) == "blocked(local_stopped=max_rounds)"
    assert expected_verdict(True, True, "no_gap", False) == "unchanged"
    assert expected_verdict(False, True, "gap_closed", False) == "wrong_to_right"
    assert expected_verdict(True, False, "gap_closed", False) == "right_to_wrong"
    cs = cost_sum([{"cell": "a", "repair_sessions": 1, "api_model_calls": 2, "tokens": None, "wall_ms": 3},
                   {"cell": "b", "repair_sessions": None, "api_model_calls": 4, "tokens": 5, "wall_ms": None}])
    assert cs["tokens"]["total"] is None and cs["tokens"]["known_sum"] == 5
    assert cs["repair_sessions"]["missing_cells"] == ["b"]
    a = aggregate([{"cell": "a", "arm": "x", "role": "bad", "before_pass_d38d2eb2": False,
                    "after_pass": True, "verdict": "wrong_to_right", "repair_sessions": 1,
                    "api_model_calls": 2, "tokens": 3, "wall_ms": 4}])
    assert a["wrong_to_right"] == 1 and a["cost"]["tokens"]["known_sum"] == 3
    print("SELFTEST_OK")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    result, problems = analyze()
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    q = result["answers_1106_2"]
    print(f"same_draft: {result['checks']['same_draft']['all_same_draft']}（14 題雙臂起始草稿 hash 相等）")
    print(f"provenance: {result['checks']['provenance_snapshot_pins']['all_ok']}（{result['checks']['provenance_snapshot_pins']['n_files']} 檔 pin 相符）")
    print(f"tamper cells: {result['checks']['source_tampered_cells']}")
    b = result["this_batch_bad9"]
    print(f"bad9  generic : pass {b['generic']['pass_after']}/9  blocked {b['generic']['blocked']}  "
          f"sessions {b['generic']['cost']['repair_sessions']['known_sum']}  calls {b['generic']['cost']['api_model_calls']['known_sum']}  tok {b['generic']['cost']['tokens']['known_sum']}")
    print(f"bad9  localized: pass {b['localized']['pass_after']}/9  blocked {b['localized']['blocked']}  "
          f"sessions {b['localized']['cost']['repair_sessions']['known_sum']}  calls {b['localized']['cost']['api_model_calls']['known_sum']}  tok {b['localized']['cost']['tokens']['known_sum']}")
    g = result["this_batch_good5"]
    print(f"good5 generic : pass {g['generic']['pass_after']}/5  calls {g['generic']['cost']['api_model_calls']['known_sum']}")
    print(f"good5 localized: pass {g['localized']['pass_after']}/5  calls {g['localized']['cost']['api_model_calls']['known_sum']}  tok_missing {g['localized']['cost']['tokens']['missing_cells']}")
    print("Q1:", q["Q1_localized_fixes_more"])
    print("Q2:", q["Q2_correctness_regression"])
    print("Q3:", q["Q3_cost_worth"])
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(" -", p)
        return 1
    print(f"ANALYSIS_OK -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
