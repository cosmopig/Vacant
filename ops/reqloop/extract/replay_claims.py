#!/usr/bin/env python3
"""G3-76 需求離線 claim 重播（工單 P20261113_0300-1；argon 20261113_0353 修量具）。

零模型、零網路、唯讀：用當前 repo 的 extract 校驗＋checks 支援集合，對 G3 四來源的 76 條
需求重判。四來源只存 claim id＋原 reason（g3_2_fire 另存 verifier）；params/quote/deliverable
未存（0/76）→ 這是「失敗階段重播」，不是完整重新編譯。因此每條翻轉都標信心：
  proven       ＝原失敗階段之後的所有 extract 檢查都能用已存欄位重跑（例：verifier 已存且非 tag_format
                 的 deliverable 翻轉）；
  upper_bound  ＝原失敗階段過了，但後續階段需要未存欄位（recompute 子參數、交付物、tag 名、未存 verifier）。
另標 check_class：content（重算值，會因錯值 FAIL）／format（answer_kv、tag_format、csv/table_structure
只查格式，錯值照樣 PASS）／unknown。成效門要看 content 且 proven 的條數，不能只看 deterministic。
執行層負控制（錯值→FAIL）在這裡做不到：params 未存，無從編譯成 RequirementItem 去跑 checks。
--trusted：D2 量效。優先用 extract.trusted_deliverable_from_contract（D2 落地後）；沒有就用本檔
reference 實作並在輸出標 trusted_source=replay_reference。
末行 REPLAY replayable=N deterministic=K proven=P content_proven=C baseline_match=B
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
# 只查格式的 verifier：錯值、格式對 → PASS。不能算「抓得到內容錯」。
FORMAT_VERIFIERS = frozenset({"answer_kv", "tag_format", "csv_structure", "table_structure"})
# 交付物必須是表格（read_table_deliverable / read_csv_rows）；交付物是 .txt 時不可能是正確的檢查。
TABLE_VERIFIERS = frozenset({"csv_structure", "table_structure", "monthly_sales_metrics", "monthly_top_products",
                             "rowset_filter", "group_aggregate"})
_TABLE_SUFFIXES = (".csv", ".tsv", ".json", ".jsonl", ".xlsx")
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


def refers_to_input(text: str, input_files: list[str]) -> bool:
    """描述字串裡以完整 token 點名輸入檔（例「資料檔 data/x.csv 保持未修改」）→ 這條在講輸入，不可改指交付物。"""
    return any(re.search(r"(?<![\w\-])" + re.escape(f) + r"(?![\w\-])", text or "") for f in input_files)


def reference_trusted_deliverable(user_text: str, input_files: list[str]) -> str | None:
    """D2 規格的 reference：原文以完整 token 出現、形如檔案路徑、不是輸入檔的檔名恰好一個 → 它；否則 None。"""
    found = []
    # 副檔名須以字母開頭且 ≥2 字元、主檔名須含字母：排除 0.000001、e.g.、i.e. 這類非檔名 token
    for m in re.finditer(r"(?<![\w\-/.])([\w\-][\w.\-/]*\.[A-Za-z][A-Za-z0-9]{1,7})(?![\w\-]|\.\w)", user_text):
        n = str(extract._strip_workspace_prefix(m.group(1))).strip()
        if not re.search(r"[A-Za-z]", n.rsplit(".", 1)[0]):
            continue
        if extract._FILE_PATH_RE.match(n) and not is_input_file(n, input_files) and n not in found:
            found.append(n)
    return found[0] if len(found) == 1 else None


def trusted_for(user_text: str, input_files: list[str]) -> tuple[str | None, str]:
    fn = getattr(extract, "trusted_deliverable_from_contract", None)
    if callable(fn):
        t = fn(user_text, input_files)
        if t is not None and is_input_file(t, input_files):  # 守則凌駕實作：輸入檔永不當交付物
            return None, "extract.trusted_deliverable_from_contract(rejected_input)"
        return t, "extract.trusted_deliverable_from_contract"
    return reference_trusted_deliverable(user_text, input_files), "replay_reference"


def check_class(verifier: str | None) -> str:
    if not verifier:
        return "unknown"
    return "format" if verifier in FORMAT_VERIFIERS else ("content" if verifier in checks.SUPPORTED_VERIFIERS else "unknown")


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
    if v in TABLE_VERIFIERS and not d.lower().endswith(_TABLE_SUFFIXES):
        return False, f"verifier_deliverable_mismatch:{v}->{d}"
    if v == "tag_format":
        tag = str((params or {}).get("tag", "")).strip()
        if tag and not re.search(r"@\s*" + re.escape(tag) + r"\b", user_text):
            return False, f"tag_not_in_request:{tag[:40]}"
    return True, None


def replay_claim(reason, user_text, input_files, saved_verifier=None, trusted=None) -> dict:
    """對「原失敗階段」重跑當前代碼。status: deterministic/unverified/missing_raw；confidence 只對 deterministic 有意義。"""
    out = {"status": "unverified", "reason": reason, "confidence": None, "check_class": check_class(saved_verifier)}
    if reason == "model_declared_unverified":
        return out  # fail-closed：模型自陳不可驗
    if reason.startswith("unknown_verifier:"):
        v = reason.split(":", 1)[1].strip()
        if v in checks.SUPPORTED_VERIFIERS:  # 後續 params/deliverable 階段需未存欄位
            out.update(status="deterministic", reason=None, confidence="upper_bound", check_class=check_class(v))
        return out
    if reason.startswith("unsupported_recompute_type:"):
        t = reason.split(":", 1)[1].strip()
        out["check_class"] = "content"  # 此 reason 只會出自 kv_recomputed/plain_recomputed
        allowed = extract._RECOMPUTE_TYPES.get(saved_verifier) or frozenset().union(*extract._RECOMPUTE_TYPES.values())
        if t in allowed:  # recompute 子參數與交付物階段需未存欄位
            out.update(status="deterministic", reason=None, confidence="upper_bound")
        return out
    if reason.startswith("deliverable_not_in_request:"):
        claimed = reason.split(":", 1)[1].strip()
        if trusted and refers_to_input(claimed, input_files):
            out["reason"] = "claimed_refers_to_input"
            return out
        d = str(trusted or claimed)
        if is_input_file(d, input_files):
            out["reason"] = "deliverable_is_input_file"
            return out
        if (p := extract._deliverable_problem(d, user_text)):
            out["reason"] = p
            return out
        if saved_verifier in TABLE_VERIFIERS and not d.lower().endswith(_TABLE_SUFFIXES):
            out["reason"] = f"verifier_deliverable_mismatch:{saved_verifier}->{d}"
            return out
        proven = bool(saved_verifier) and saved_verifier != "tag_format"  # tag_format 的 tag 名未存；verifier 未存則不知道
        out.update(status="deterministic", reason=None, confidence="proven" if proven else "upper_bound")
        return out
    out.update(status="missing_raw", reason=None)  # missing_param:* 等：params 未存 → 無法重判，不造假
    return out


def replay_reason(reason, user_text, input_files, saved_verifier=None, trusted=None):
    """相容介面：(True/False, reason)；(None, None)＝missing_raw。True 為上界（含 upper_bound）。"""
    r = replay_claim(reason, user_text, input_files, saved_verifier, trusted)
    if r["status"] == "missing_raw":
        return None, None
    return r["status"] == "deterministic", r["reason"]


def collect(*, trusted: bool = False):
    rows = []

    def add(batch, task_root, task_id, cid, verdict, reason, verifier=None):
        ut, inputs = load_task(task_root, task_id)
        t, tsrc = trusted_for(ut, inputs) if trusted else (None, None)
        if verdict == "deterministic":
            r = {"status": "missing_raw", "reason": "raw_fields_not_saved", "confidence": None, "check_class": "unknown"}
        else:
            r = replay_claim(reason, ut, inputs, saved_verifier=verifier, trusted=t)
        rows.append({"source": batch, "task_id": task_id, "claim_id": cid, "original_verdict": verdict,
                     "original_reason": reason, "saved_verifier": verifier, "replay_status": r["status"],
                     "replay_reason": r["reason"], "confidence": r["confidence"], "check_class": r["check_class"],
                     "trusted_deliverable": t, "trusted_source": tsrc,
                     "user_text_chars": len(ut), "input_files": inputs})

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
    total = len(rows)
    dets = [r for r in rows if r["replay_status"] == "deterministic"]
    mraw = [r for r in rows if r["replay_status"] == "missing_raw"]
    tax = json.loads(TAX.read_text(encoding="utf-8"))["totals"]
    det_in_mraw = sum(1 for r in mraw if r["original_verdict"] == "deterministic")
    det_tax, tax_req = int(tax["deterministic_claims"]), int(tax["requirements"])
    # 基線對帳＝分母對得上（總數、原 deterministic 全落在 missing_raw），不再寫死「當前 deterministic==0」：
    # 舊版把改善本身判成基線失敗，D2/D3 一落地 selftest 就紅。
    baseline_match = (total == tax_req) and (det_in_mraw == det_tax)
    dist: dict[str, int] = {}
    urt: dict[str, int] = {}
    for r in rows:
        k = "deterministic" if r["replay_status"] == "deterministic" else (
            "deliverable_not_in_request:*" if (r["replay_reason"] or "").startswith("deliverable_not_in_request:")
            else "verifier_deliverable_mismatch:*" if (r["replay_reason"] or "").startswith("verifier_deliverable_mismatch:")
            else (r["replay_reason"] or "missing_raw"))
        dist[k] = dist.get(k, 0) + 1
        if (r["original_reason"] or "").startswith("unsupported_recompute_type:"):
            t = r["original_reason"].split(":", 1)[1]
            urt[t] = urt.get(t, 0) + 1
    proven = [r for r in dets if r["confidence"] == "proven"]
    return {"total": total, "replayable": total - len(mraw), "deterministic": len(dets),
            "deterministic_proven": len(proven),
            "deterministic_content": sum(1 for r in dets if r["check_class"] == "content"),
            "deterministic_content_proven": sum(1 for r in proven if r["check_class"] == "content"),
            "deterministic_format": sum(1 for r in dets if r["check_class"] == "format"),
            "unverified": sum(1 for r in rows if r["replay_status"] == "unverified"), "missing_raw": len(mraw),
            "missing_raw_claims": [{**r, "why": r["original_reason"] or "deterministic claim; raw fields not saved"} for r in mraw],
            "reason_distribution": dict(sorted(dist.items())),
            "unsupported_recompute_types": dict(sorted(urt.items())),
            "execution_controls": "not_possible: params/quote 0/76 saved → 無法編譯成 RequirementItem 跑 checks；"
                                  "錯值→FAIL 控制須在 D2/D3 單元測試用真實資料做",
            "baseline": {"taxonomy_deterministic": det_tax, "deterministic_in_missing_raw": det_in_mraw,
                         "baseline_match": baseline_match,
                         "explanation": (f"taxonomy 的 {det_tax} 條 deterministic（g3_2_prerun dab_725 R1/R6）落在 missing_raw："
                                         "來源報告只存 claim id、未存 verifier/deliverable/params/quote，重播即造假；"
                                         "另 1 條 missing_param:values 因 params 未存同列 missing_raw。"
                                         "凍結代碼下 replayable 集合內 deterministic=0。")}}


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
    # 用保證不存在的型別名：舊版寫死 mean_col，D3 一落地 selftest 就紅
    check("replay 不支援的 recompute 型別 → 非 deterministic", replay_reason("unsupported_recompute_type:zz_no_such_type_9x", ut, inputs, "plain_recomputed")[0] is False)
    check("replay missing_param → missing_raw（不造假）", replay_reason("missing_param:values", ut, inputs) == (None, None))
    t = reference_trusted_deliverable(ut, inputs)
    check("trusted reference：dab_725 contract 唯一點名 answer.txt", t == "answer.txt")
    check("trusted reference：點名兩個輸出檔 → None", reference_trusted_deliverable("Write `a.txt` and `b.csv`.", []) is None)
    check("trusted reference：數字/縮寫不算檔名", reference_trusted_deliverable("tol 0.000001, e.g. i.e. write `out.txt`", []) == "out.txt")
    check("trusted reference：唯一點名的是輸入檔 → None", reference_trusted_deliverable("Use `data/x.csv`.", ["x.csv"]) is None)
    r = replay_claim("deliverable_not_in_request:資料檔 data/auto-mpg.csv 保持未修改", ut, inputs, "answer_kv", trusted=t)
    check("neg4 trusted 下講輸入檔的條目不改指交付物", r["status"] == "unverified" and r["reason"] == "claimed_refers_to_input")
    r = replay_claim("deliverable_not_in_request:依 displacement 出現次數選出前三大值", ut, inputs, "group_aggregate", trusted=t)
    check("neg5 表格 verifier 改指 answer.txt → mismatch 非 deterministic", r["status"] == "unverified" and r["reason"].startswith("verifier_deliverable_mismatch"))
    r = replay_claim("deliverable_not_in_request:六個數值皆四捨五入", ut, inputs, "tag_format", trusted=t)
    check("neg6 tag_format 翻轉只算上界（tag 名未存）＋format", r["confidence"] == "upper_bound" and r["check_class"] == "format")
    r = replay_claim("deliverable_not_in_request:analysis", ut, inputs, None, trusted=t)
    check("neg7 verifier 未存的翻轉只算上界", r["status"] == "deterministic" and r["confidence"] == "upper_bound")
    r = replay_claim("unsupported_recompute_type:zcount3", ut, inputs, "kv_recomputed")
    check("neg8 recompute 型別翻轉只算上界（子參數/交付物未存）", r["confidence"] == "upper_bound" and r["check_class"] == "content")
    r = replay_claim("deliverable_not_in_request:answer.txt 中六個 @name[value] 項目", ut, inputs, "answer_kv", trusted=t)
    check("pos2 verifier 已存的 answer_kv 翻轉＝proven 但 format", r["confidence"] == "proven" and r["check_class"] == "format")
    s = summarize(collect())
    check("76 條全收齊且基線對帳通過", s["total"] == 76 and s["baseline"]["baseline_match"] is True)
    st = summarize(collect(trusted=True))
    check("trusted 模式改善時基線對帳仍通過（不把改善判成基線失敗）", st["baseline"]["baseline_match"] is True)
    if fails:
        print(f"SELFTEST FAIL ({len(fails)}): {fails}")
        return 1
    print("SELFTEST PASS")
    return 0


def _write_if_changed(path: pathlib.Path, doc: dict) -> bool:
    """內容（除 generated_at）沒變就不重寫：每張票都要跑本量具，不該每跑一次就弄髒工作樹。"""
    if path.is_file():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            if {k: v for k, v in old.items() if k != "generated_at"} == {k: v for k, v in doc.items() if k != "generated_at"}:
                return False
        except (json.JSONDecodeError, OSError):
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="replay_claims")
    ap.add_argument("--selftest", action="store_true", help="跑負/正控制與基線對帳後即回")
    ap.add_argument("--trusted", action="store_true", help="D2 量效：交付物取自可信任務契約（見模組說明）")
    ap.add_argument("--out", default=None, help="輸出 JSON（預設 g26_claim_replay.json；--trusted 預設 g26_claim_replay_trusted.json）")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    rows = collect(trusted=a.trusted)
    s = summarize(rows)
    out = pathlib.Path(a.out) if a.out else (OUT.with_name("g26_claim_replay_trusted.json") if a.trusted else OUT)
    doc = {"ticket": "P20261113_0300-1-d1-offline-claim-replay", "mode": "trusted" if a.trusted else "claimed",
           "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "code_sha": code_sha(),
           "raw_fields_saved": {"verifier": "g3_2_fire 26/26；其餘三來源 0/50", "deliverable": "僅 reason 內截斷 60 字元",
                                "params": "0/76（未存）", "quote": "0/76（未存）"},
           "totals": s, "claims": rows}
    wrote = _write_if_changed(out, doc)
    print(f"{'寫入' if wrote else '內容未變、未重寫'} {out}（{s['total']} 條）")
    print(f"REPLAY replayable={s['replayable']} deterministic={s['deterministic']} proven={s['deterministic_proven']} "
          f"content_proven={s['deterministic_content_proven']} baseline_match={s['baseline']['baseline_match']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
