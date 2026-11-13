#!/usr/bin/env python3
"""G3-76 需求離線 claim 重播（工單 P20261113_0300-1-d1-offline-claim-replay）。

零模型、零網路、唯讀：用當前 repo 的 extract 校驗＋checks 支援集合，對 G3 四來源的 76 條
需求重判 deterministic/unverified。不造假：四來源只存 claim id＋原 reason（g3_2_fire 另存
verifier）；params/quote/deliverable 未存 → 需未存欄位者（missing_param 的 params、2 條
deterministic）標 missing_raw，不計數不推測。基線：當前代碼下原本 unverified 者無一翻成
deterministic=12（D3 已落、P20261113_0300-3：mean_col/median_col/std_col；pearson 2 條屬
D3b、P20261113_0344-1，參數未存於來源）；taxonomy 的 2 條 deterministic（g3_2_prerun
dab_725 R1/R6）落在 missing_raw，差額即這些。D2 量效：K1＝走 trusted_deliverable
（trusted_deliverable_from_contract 自原文抽唯一非輸入檔；零個或多個＝None＝維持舊判定）；
checks.py recompute 型別集合擴充後自動反映。末行 REPLAY K0 deterministic=K0 → K1 deterministic=K1（兩數並列報告）
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import pathlib
import re
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from vacant_network.reqloop import checks, extract  # noqa: E402
from vacant_network.reqloop.g3 import compose_extract_user_text  # noqa: E402
from vacant_network.reqloop.requirements import RequirementItem, RequirementSet  # noqa: E402
from vacant_network.reqloop.specs import SpecIntegrityError, load_frozen_specs  # noqa: E402

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
        # P20261113_1507-1：verifier 空/None（模型擷取階段省略該欄位）點名為 missing（對齊 extract.py:806）
        return False, f"unknown_verifier:{v or 'missing'}"
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
    if reason == "unknown_verifier:missing":
        # P20261113_1507-1：模型擷取階段省略 verifier 欄位且預跑未存 raw fields（dab_587 三條根因）
        # → 永久 unverified，絕不翻 deterministic（I-4：未測量不是通過）
        return False, reason
    if reason.startswith("unknown_verifier:"):
        v = reason.split(":", 1)[1].strip()
        if not v:  # 空 verifier 欄位 → 點名為 missing（同 judge_claim 口徑）
            return False, "unknown_verifier:missing"
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
    if reason.startswith("missing_param:"):
        # P20261113_1708-2：缺必要參數（params 未存於來源）→ missing_raw，但點名保留缺失原因碼
        # （如 missing_param:values），不抹除根因；None＝絕不翻 deterministic（I-4：未測量不是通過）
        return None, reason
    return None, None  # 其它未知原因：raw 欄位未存 → 無法重判，不造假

def collect(*, use_trusted: bool = False):
    """use_trusted=False＝K0 基線（舊行為）；True＝D2：每任務先自原文抽 trusted
    交付物（恰一個非輸入檔才回值，否則 None＝維持舊判定），再走 replay_reason。"""
    rows = []

    def add(batch, task_root, task_id, cid, verdict, reason, verifier=None):
        ut, inputs = load_task(task_root, task_id)
        trusted = extract.trusted_deliverable_from_contract(ut, inputs) if use_trusted else None
        if verdict == "deterministic":
            status, r = "missing_raw", "raw_fields_not_saved"  # 原始欄位未存，不複驗不造假
        else:
            ok, r = replay_reason(reason, ut, inputs, saved_verifier=verifier, trusted=trusted)
            status = "missing_raw" if ok is None else ("deterministic" if ok else "unverified")
        rows.append({"source": batch, "task_id": task_id, "claim_id": cid, "original_verdict": verdict,
                     "original_reason": reason, "saved_verifier": verifier, "trusted_deliverable": trusted,
                     "replay_status": status, "replay_reason": r, "user_text_chars": len(ut), "input_files": inputs})

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

def missing_field_reason(row: dict) -> tuple[str, str]:
    """點名一條 missing_raw claim 的缺失欄位（票 P20261113_1358-2）：回 (欄位名, 原因碼)。

    只點名欄位名與原因碼，永不輸出欄位值（值本就不存，也不得進入輸出）：
    - original_reason=missing_param:<field> → field=<field>、reason=missing_param
      （欄位名取自 reason 碼本身；verifier 可能已存，但必要參數無值）
    - 其它（原始 deterministic：來源報告只存 claim id）→ field=verifier（judge
      契約首個未存欄位）、reason=raw_fields_not_saved
    """
    o = str(row.get("original_reason") or "")
    if o.startswith("missing_param:"):
        f = o.split(":", 1)[1].strip()
        if f:
            return f, "missing_param"
    return "verifier", "raw_fields_not_saved"

def summarize(rows):
    total, det = len(rows), sum(1 for r in rows if r["replay_status"] == "deterministic")
    mraw = [r for r in rows if r["replay_status"] == "missing_raw"]
    # P20261113_1358-2：缺失點名（欄位名＋原因碼，無值；排序穩定）
    missing_detail = []
    for r in sorted(mraw, key=lambda x: (x["task_id"], x["claim_id"])):
        f, rs = missing_field_reason(r)
        missing_detail.append({"task_id": r["task_id"], "claim_id": r["claim_id"], "field": f, "reason": rs})
    tax = json.loads(TAX.read_text(encoding="utf-8"))["totals"]
    det_in_mraw = sum(1 for r in mraw if r["original_verdict"] == "deterministic")
    det_tax, tax_req = int(tax["deterministic_claims"]), int(tax["requirements"])
    # D3/D3b 已落（P20261113_0300-3、P20261113_0344-1、11-13 定案第 3 條）：baseline 由「K0 deterministic=0」
    # 更新為「K0 deterministic=14（8 mean_col + 2 median_col + 2 std_col + 2 pearson）」；
    # taxonomy 中 14 條 unsupported 重算型別皆已落地。
    baseline_match = (total == tax_req) and (det == 14) and (det_in_mraw == det_tax)
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
    by_task: dict[str, dict[str, int]] = {}
    for r in rows:  # P20261113_0948-3：按任務分組摘要（機器可讀）
        t = by_task.setdefault(r["task_id"], {"total": 0, "deterministic": 0, "unverified": 0, "missing_raw": 0})
        t["total"] += 1
        t[r["replay_status"]] += 1
    return {"total": total, "by_task": by_task, "replayable": total - len(mraw), "deterministic": det,
            "unverified": sum(1 for r in rows if r["replay_status"] == "unverified"), "missing_raw": len(mraw),
            "missing_detail": missing_detail,
            "missing_raw_claims": [{**r, "why": r["original_reason"] or "deterministic claim; raw fields not saved"} for r in mraw],
            "reason_distribution": dict(sorted(dist.items())),
            "unsupported_recompute_types": dict(sorted(urt.items())),
            "baseline": {"taxonomy_deterministic": det_tax, "replay_deterministic_within_replayable": det,
                         "deterministic_in_missing_raw": det_in_mraw, "baseline_match": baseline_match,
                         "explanation": (f"replayable={total - len(mraw)} 集合內 deterministic={det}：K0 基線（不走 trusted）下，"
                                         "unverified 中 14 條 unsupported 已因 D3/D3b（P20261113_0300-3/0344-1，11-13 裁決："
                                         "extract.py/checks.py 受控解凍＝新增路徑＋run_eval --all 三門數字＝g25 filing）翻成"
                                         " deterministic；D2 量效見 d2_K1。taxonomy 的 "
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
    check("replay D3: mean_col 已 deterministic（11-13 定案、P20261113_0300-3 落盤）",
          replay_reason("unsupported_recompute_type:mean_col", ut, inputs, "plain_recomputed")[0] is True)
    check("replay D3b: pearson 已 deterministic（11-13 定案、P20261113_0344-1 落盤）",
          replay_reason("unsupported_recompute_type:pearson", ut, inputs, "plain_recomputed")[0] is True)
    check("replay missing_param → missing_raw（不造假、點名根因碼）",
          replay_reason("missing_param:values", ut, inputs) == (None, "missing_param:values"))
    s = summarize(collect())
    check("76 條全收齊且基線對帳通過", s["total"] == 76 and s["baseline"]["baseline_match"] is True)
    s1 = summarize(collect(use_trusted=True))
    check("D2+D3+D3b K1：66 條 → deterministic（52 可信任交付物＋14 重算型別，9 任務）", s1["deterministic"] == 66)
    check("D2 K1：deliverable_not_in_request 零殘留（全部解除，非強行翻綠）",
          not any(k.startswith("deliverable_not_in_request") for k in s1["reason_distribution"]))
    check("D3+D3b K1 未誤動其它類：unverified 7 條＝4 自陳＋3 unknown_verifier",
          s1["unverified"] == 7)
    if fails:
        print(f"SELFTEST FAIL ({len(fails)}): {fails}")
        return 1
    print("SELFTEST PASS")
    return 0

def gate_check() -> int:
    """成效門機械檢驗（2026-11-13 人類定案第 4 條、P20261113_0344-2）：
    (1) 確定性條數門禁：totals.deterministic >= 30/76
    (2) 全量負控制測試：對 dab_725 / dab_587 / dab_657 / dab_517 真實任務注入負控制：
        (a) 故意錯的交付物檔名／缺檔 → 必判 FAIL/UNKNOWN；
        (b) 輸入檔當交付物（如 auto-mpg.csv）→ 必判 UNKNOWN/FAIL（is_input_file 攔截）；
        (c) 故意篡改答案值（如 999999.99）→ 必判 FAIL。
    (3) 斷言在上述所有負控制情境下 false_pass == 0。
    通過時輸出：GATE_CHECK: deterministic=<K>/76 >= 30 false_pass=0 VERDICT: PASS
    P20261113_0846-3：補齊票面全量負控制——(a) 錯交付物檔名必判 deliverable_not_in_request、
    (b) 輸入檔當交付物必判 deliverable_is_input_file、(c) 未知 verifier 必判 unknown_verifier；
    run_gate_check 為票面同義名（同一實作）。
    """
    rows1 = collect(use_trusted=True)
    s1 = summarize(rows1)
    det = s1["deterministic"]
    if det < 30:
        print(f"GATE_CHECK FAIL: deterministic={det}/76 < 30")
        return 1

    false_pass = 0
    target_tasks = [
        ("dab_725", "workspace/data/auto-mpg.csv", "mean1", "mean_col", "mpg"),
        ("dab_587", "workspace/data/20170413_000000_group_statistics.csv", "correlation_coefficient", None, None),
        ("dab_657", "workspace/data/YAHOO-BTC_USD_D.csv", "mean_close", "mean_col", "Close"),
        ("dab_517", "workspace/data/titanic.csv", "correlation_pclass_fare", "pearson", ("Pclass", "Fare")),
    ]

    for tid, data_rel, key_name, rtype, col_spec in target_tasks:
        ut, inputs = load_task("g3_2", tid)
        tpath = REPO / "ops/reqloop/g3_2/tasks" / tid
        keys = [{"key": key_name, "type": "number"}]

        # 負控制 1（票 (a)）: 故意錯的交付物檔名／缺檔 → 必判 deliverable_not_in_request
        ok1, r1 = judge_claim("answer_kv", "non_existent_output_9x8y.txt", {"keys": keys}, ut, inputs)
        if ok1 or not str(r1).startswith("deliverable_not_in_request"):
            false_pass += 1
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            td = pathlib.Path(tmp_dir)
            req_item = RequirementItem(id="r_neg1", quote="測試", deliverable="missing_file.txt",
                                       verifier="plain_recomputed",
                                       params={"data_file": data_rel, "recompute": {"type": "mean_col", "col": "x"}})
            res = checks.run_requirement_checks(tpath, RequirementSet("t", [req_item]), td)
            if res and res[0].status == "PASS":
                false_pass += 1

        # 負控制 2（票 (b)）: 輸入檔當交付物 → 必判 deliverable_is_input_file
        for inp in inputs:
            ok2, r2 = judge_claim("answer_kv", inp, {"keys": keys}, ut, inputs)
            if ok2 or r2 != "deliverable_is_input_file":
                false_pass += 1
            if not is_input_file(inp, inputs):
                false_pass += 1

        # 負控制 3: 故意錯值（999999.99）
        if rtype is not None:
            with tempfile.TemporaryDirectory() as tmp_dir:
                td = pathlib.Path(tmp_dir)
                (td / "answer.txt").write_text(f"@{key_name}[999999.99]\n", encoding="utf-8")
                rc_dict: dict[str, Any] = {"type": rtype}
                if isinstance(col_spec, tuple):
                    rc_dict["col_a"], rc_dict["col_b"] = col_spec
                else:
                    rc_dict["col"] = col_spec
                req_item = RequirementItem(id="r_neg3", quote="測試", deliverable="answer.txt",
                                           verifier="kv_recomputed",
                                           params={"key": key_name, "data_file": data_rel, "recompute": rc_dict})
                res = checks.run_requirement_checks(tpath, RequirementSet("t", [req_item]), td)
                if res and res[0].status == "PASS":
                    false_pass += 1

        # 負控制 4（票 (c)）: 未知 verifier → 必判 unknown_verifier
        ok4, r4 = judge_claim("unsupported_dummy_check", "answer.txt", {}, ut, inputs)
        if ok4 or not str(r4).startswith("unknown_verifier:"):
            false_pass += 1

    if false_pass != 0:
        print(f"GATE_CHECK FAIL: false_pass={false_pass} != 0")
        return 1

    print(f"GATE_CHECK: deterministic={det}/76 >= 30 false_pass=0 VERDICT: PASS")
    return 0

run_gate_check = gate_check  # P20261113_0846-3 票面函式名（同一實作）

SPEC_DIR = REPO / "ops/reqloop/g4/specs"
FROZEN_TASKS = ("dab_725", "dab_587", "dab_657", "dab_517")
_KV_CTRL = {"mean_col": checks._mean_col, "median_col": checks._median_col, "std_col": checks._std_col,
            "pearson": checks._pearson_pair, "pearson2": checks._pearson_pair}

def _ctrl_rows(data_file: pathlib.Path) -> list:
    """控制用資料行載入（口徑同 checks.check_kv_recomputed：.csv DictReader／.json row 物件列表）。"""
    if data_file.suffix.lower() == ".json":
        d = json.loads(data_file.read_text(encoding="utf-8"))
        if not isinstance(d, list) or not all(isinstance(r, dict) for r in d):
            raise ValueError("data_file JSON 非 row 物件列表")
        return d
    with data_file.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def _checkable(item) -> bool:
    """條目可確定性檢查（口徑同 g3._item_uncheckable_reason／1100-2：unverified 標記、
    檢查器不在白名單、必要參數缺陷——任一命中即永久 UNKNOWN）。"""
    return (not item.unverified and item.verifier in checks.SUPPORTED_VERIFIERS
            and extract._param_problem(item.verifier, item.params) is None)

def _ctrl_answers(item, task_dir):
    """單條目 (正控制, 負控制) answer.txt 內容：正必 PASS、負必非 PASS（P20261113_1206-3）。
    值口徑同 checks 各驗證器（answer_kv 約束型別、tag_format value_type、kv_recomputed 重算＋round）；
    無法構造→(None, None)。"""
    if item.verifier == "answer_kv":
        pos = []
        for s in item.params.get("keys") or []:
            k, cons = str(s.get("key", "")).strip(), str(s.get("type", "number")).lower()
            if not k or cons not in ("number", "integer", "nonneg_int", "number_in_01"):
                return None, None
            pos.append(f"@{k}[{'1.5' if cons in ('number', 'number_in_01') else '3'}]")
        return "\n".join(pos) + "\n", f"@{pos[0].split('[')[0]}[not_a_number]\n"
    if item.verifier == "tag_format":
        tag, vt = str(item.params.get("tag", "")).strip(), str(item.params.get("value_type", "str")).lower()
        if not tag or vt not in ("str", "int", "integer", "float", "number"):
            return None, None
        if vt == "str":
            return f"@{tag}[hello]\n", f"@{tag} hello\n"  # 負：缺方括號 → missing_brackets FAIL
        base = 5.0 if vt in ("int", "integer") else 1.5
        if "min_value" in item.params:
            base = max(base, float(item.params["min_value"]))
        if "max_value" in item.params:
            base = min(base, float(item.params["max_value"]))
        if vt in ("int", "integer"):
            base = int(base)
        return f"@{tag}[{base}]\n", f"@{tag}[not_a_number]\n"
    if item.verifier == "kv_recomputed":
        key, rc = str(item.params.get("key", "")).strip(), item.params.get("recompute") or {}
        helper = _KV_CTRL.get(str(rc.get("type", "")).strip().lower())
        df = task_dir / str(item.params.get("data_file", "")).strip()
        if not key or helper is None or not df.is_file():
            return None, None
        try:
            exp = helper(_ctrl_rows(df), rc)
        except Exception:  # UnknownSource 等＝當前資料下無法確定性檢查
            return None, None
        rnd = rc.get("round") if rc.get("round") is not None else item.params.get("round")
        if isinstance(rnd, int) and not isinstance(rnd, bool):
            exp = round(exp, rnd)
        return f"@{key}[{exp}]\n", f"@{key}[{float(exp) + 12345.6789}]\n"  # 負：錯值必 mismatch FAIL
    return None, None

def verify_frozen_specs(specs_dir=SPEC_DIR, manifest_path=None) -> int:
    """G4 凍結規格交叉驗證（P20261113_1206-3、P20261113_1810-4、11-13 定案 §4）：
    先對 manifest 綁定之 spec_sha256 做密碼學核驗（不符／損毀即 fail-closed），
    再做 4 題規格 spec_sha256 自校驗＋
    每條 checkable 條目正控制（必 PASS）／負控制（錯值，必非 PASS）；0 假 PASS 且全部可構造才 PASS。
    零模型、唯讀。"""
    if manifest_path is None:
        manifest_path = REPO / "ops/reqloop/g4/manifest.json"
    try:
        load_frozen_specs(manifest_path)
    except SpecIntegrityError as e:
        print(f"FROZEN_SPECS FAIL: manifest integrity: {e}")
        return 1
    total_items = checkable_items = false_pass = 0
    for tid in FROZEN_TASKS:
        p = pathlib.Path(specs_dir) / f"{tid}.json"
        try:
            req_set = RequirementSet.from_dict(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError) as e:
            print(f"FROZEN_SPECS FAIL: {tid} 規格讀取失敗：{e}")
            return 1
        ok, reason = req_set.verify_self_hash()
        if not ok:
            print(f"FROZEN_SPECS FAIL: {tid} spec_sha256 自校驗失敗（{reason}）")
            return 1
        task_dir = REPO / "ops/reqloop/g3_2/tasks" / tid / "workspace"
        total_items += len(req_set.items)
        for item in req_set.items:
            if not _checkable(item):
                continue  # 永久 UNKNOWN 條目（參數缺陷）＝非 checkable，不計入分母
            checkable_items += 1
            pos, neg = _ctrl_answers(item, task_dir)
            for label, content in (("pos", pos), ("neg", neg)):
                if content is None:
                    false_pass += 1
                    print(f"FROZEN_SPECS FAIL: {tid} {item.id} {label} 控制無法構造")
                    continue
                with tempfile.TemporaryDirectory() as td:
                    pathlib.Path(td, "answer.txt").write_text(content, encoding="utf-8")
                    res = {r.claim_id: r.status for r in checks.run_requirement_checks(task_dir, req_set, td)}
                if (res.get(item.id) == "PASS") != (label == "pos"):
                    false_pass += 1
                    print(f"FROZEN_SPECS FAIL: {tid} {item.id} {label} 控制判 {res.get(item.id)}"
                          f"（預期 {'PASS' if label == 'pos' else '非 PASS'}）")
    if false_pass:
        print(f"FROZEN_SPECS FAIL: 4 tasks, {total_items} items, {checkable_items} checkable, false_pass={false_pass}")
        return 1
    print(f"FROZEN_SPECS: 4 tasks, {checkable_items} checkable, 0 false_pass VERDICT: PASS")
    return 0

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="replay_claims")
    ap.add_argument("--selftest", action="store_true", help="跑負/正控制與基線對帳後即回")
    ap.add_argument("--gate", action="store_true", help="成效門機械檢驗（確定性 >= 30 且負控制 0 假 PASS）")
    ap.add_argument("--verify-specs", action="store_true",
                    help="P20261113_1206-3：G4 凍結規格正/負控制交叉驗證（0 假 PASS）")
    ap.add_argument("--json", action="store_true", help="P20261113_0948-3：K1（trusted）統計輸出 JSON 到 stdout（RC 0、不寫檔）")
    ap.add_argument("--missing-report", action="store_true",
                    help="P20261113_1358-2：點名列出缺失 claim（欄位名＋原因碼、不印欄位值；唯讀、不寫檔）")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.gate:
        return gate_check()
    if a.verify_specs:  # P20261113_1206-3：凍結規格交叉驗證（不呼叫模型、不寫檔）
        return verify_frozen_specs()
    if a.json:  # P20261113_0948-3：--json 機器可讀輸出（不呼叫模型、不寫 OUT）
        s1 = summarize(collect(use_trusted=True))
        print(json.dumps({"totals": s1, "by_task": s1["by_task"], "deterministic": s1["deterministic"]},
                         indent=2, ensure_ascii=False))
        return 0
    if a.missing_report:  # P20261113_1358-2：缺失點名報告（不呼叫模型、不寫 OUT）
        s1 = summarize(collect(use_trusted=True))
        print(f"REPLAY K1 (trusted): total={s1['total']} deterministic={s1['deterministic']} "
              f"unverified={s1['unverified']} missing_raw={s1['missing_raw']}")
        for e in s1["missing_detail"]:
            print(f"CLAIM_MISSING: {e['task_id']}/{e['claim_id']}: {e['field']} {e['reason']}")
        return 0
    rows0 = collect()
    s0 = summarize(rows0)
    rows1 = collect(use_trusted=True)
    s1 = summarize(rows1)
    doc = {"ticket": "P20261113_0300-1-d1-offline-claim-replay（工具源出）/ P20261113_0300-2-d2-trusted-deliverable（本輪）",
           "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "code_sha": code_sha(),
           "raw_fields_saved": {"verifier": "g3_2_fire 26/26；其餘三來源 0/50", "deliverable": "僅 reason 內截斷 60 字元",
                                "params": "0/76（未存）", "quote": "0/76（未存）"},
           "baseline_K0": s0,
           "d2_K1": s1,
           "k0_to_k1": {"K0_deterministic": s0["deterministic"], "K1_deterministic": s1["deterministic"],
                        "flipped_to_deterministic": s1["deterministic"] - s0["deterministic"],
                        "K0_baseline_match": s0["baseline"]["baseline_match"]},
           "totals": s1, "claims": rows1}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"寫入 {OUT}（{s1['total']} 條）")
    print(f"REPLAY K0 deterministic={s0['deterministic']} (replayable={s0['replayable']}, baseline_match={s0['baseline']['baseline_match']}) "
          f"→ K1 deterministic={s1['deterministic']} (replayable={s1['replayable']}, flipped={s1['deterministic'] - s0['deterministic']})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
