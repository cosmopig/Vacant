#!/usr/bin/env python3
"""R447 的**前置**尺：先證明 `analyze_r447.py` 讀得懂 runner 真的寫出來的東西。

為什麼要有這一支（round699 的教訓，這裡是第二次套用）：
  `analyze_r447.py --selftest` 三十幾條全綠、M1–M10 全 caught——但那些夾具
  **全部由 analyze_r447 自己的 `_r()` 造**、與 analyzer 同一位作者同一組字面字串。
  全綠不構成「它讀得懂真 rows」的任何證據。真 rows 現在就在磁碟上，現在驗是幾秒；
  收官才發現會在三小時後拿到一個 BROKEN，而資料其實是好的。

三條結構性規矩：
  1. `REQUIRED` 用 `ast` 從 `analyze_r447.py` **原始碼逐字取出**，不在這裡抄一份
     ⇒ 兩邊不可能漂開。
  2. 夾具**不共用** analyze_r447 的任何 helper，欄位名在本檔獨立寫死。
  3. **不 import `analyze()`** ⇒ 本檔結構上算不出 Δ／b／c／任何比率。
     （中途偷看比率會誘導後續決定；本檔只答「讀不讀得懂」。）

另外釘死事前註冊文件本身：`DECISION_SHA256` 是 commit 2c82c63 當下的 sha256。
文件在資料落地後被改 ⇒ 本尺變紅。事前註冊不是被改了才發現的東西。

0 列 ⇒ BROKEN，不是 PASS（0 列全綠是套套邏輯）。

用法：
  python3 ops/gain/r447_schema_precheck.py --selftest
  python3 ops/gain/r447_schema_precheck.py --run runs/g_r447_conform_lcb2
"""
from __future__ import annotations
import argparse, ast, hashlib, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ANALYZER = ROOT / "ops" / "gain" / "analyze_r447.py"
DECISION = ROOT / "DECISION_20260904_R440Z_LCB2_PREREG.md"
DECISION_SHA256 = "7150d9db8e4018533344ad223f3beed54ccb68f599acde12498842c03c28b9e5"

MUTANT = ""
LAST_FAILS: list[str] = []


def contract_fields() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """用 ast 從 analyzer 原始碼逐字取 REQUIRED／REQUIRED_CONFORM（不抄一份）。"""
    tree = ast.parse(ANALYZER.read_text(encoding="utf-8"))
    got: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id in ("REQUIRED", "REQUIRED_CONFORM"):
                got[t.id] = tuple(ast.literal_eval(node.value))
    if MUTANT == "X10_contract_hardcoded":
        return ("arm", "task_id"), ()
    missing = {"REQUIRED", "REQUIRED_CONFORM"} - set(got)
    if missing:
        raise SystemExit(f"BROKEN 契約常數取不到：{sorted(missing)}（analyzer 改名了？）")
    return got["REQUIRED"], got["REQUIRED_CONFORM"]


def check(rows, summary, calls, files) -> dict:
    req, req_c = contract_fields()
    out: dict = {"broken": [], "required": list(req), "required_conform": list(req_c)}
    out["rows_lines"] = len(rows)
    if not rows:
        out["broken"].append("zero_rows")

    # 逐欄 absent / bad_type
    TYPES = {"arm": str, "task_id": str, "meets_demand": bool, "accepted": bool,
             "calls_used": int, "visible_ok": bool,
             "conform_attempts": list, "conform_calls": int, "receipt_head": str}
    stat: dict[str, dict[str, int]] = {}
    for k in tuple(req) + tuple(req_c):
        stat[k] = {"absent": 0, "bad_type": 0, "n": 0}
    for r in rows:
        keys = tuple(req) + (tuple(req_c) if r.get("arm") == "CONFORM" else ())
        for k in keys:
            st = stat[k]
            st["n"] += 1
            if k not in r:
                st["absent"] += 1
            elif k in TYPES and not isinstance(r[k], TYPES[k]):
                st["bad_type"] += 1
    out["field_stats"] = stat
    if MUTANT != "X1_ignore_absent":
        for k, st in stat.items():
            if st["absent"] or st["bad_type"]:
                out["broken"].append(f"field:{k}:absent={st['absent']}:bad_type={st['bad_type']}")

    # 臂齊不齊
    arms = sorted({r.get("arm") for r in rows})
    out["arms"] = arms
    for a in ("OFF", "CONFORM", "OFF5"):
        if a not in arms:
            out["broken"].append(f"arm_missing:{a}")

    # summary 必要鍵
    need = ("run_terminal", "arms")
    out["summary_keys_ok"] = all(k in summary for k in need)
    if not out["summary_keys_ok"]:
        out["broken"].append("summary_missing_keys")
    for a in arms:
        s = (summary.get("arms") or {}).get(a) or {}
        for k in ("processed", "infra_void"):
            if k not in s:
                out["broken"].append(f"summary:{a}:{k}_missing")
    out["run_terminal"] = summary.get("run_terminal")

    # P-Z5b 離線重建的前置條件：calls.jsonl 的每通 gen 都帶 meta.arm/meta.task_id，
    # 且每題 CONFORM 的通數 == 該列的 conform_calls。對不上 ⇒ 重建不可信。
    per_task: dict[str, int] = {}
    untagged = 0
    for c in calls:
        m = c.get("meta") or {}
        if c.get("role") != "gen":
            continue
        if not m.get("arm") or not m.get("task_id"):
            untagged += 1
            continue
        if m["arm"] == "CONFORM":
            per_task[m["task_id"]] = per_task.get(m["task_id"], 0) + 1
    mism = []
    for r in rows:
        if r.get("arm") != "CONFORM":
            continue
        want = r.get("conform_calls")
        got = per_task.get(r.get("task_id"), 0)
        if want != got:
            mism.append({"task_id": r.get("task_id"), "conform_calls": want, "calls_jsonl": got})
    out["reconstruct_untagged_gen_calls"] = untagged
    out["reconstruct_mismatch_n"] = len(mism)
    out["reconstruct_mismatch_sample"] = mism[:5]
    out["pz5b_reconstruction_feasible"] = (untagged == 0 and not mism and bool(per_task))
    if MUTANT == "X2_ignore_reconstruct":
        out["pz5b_reconstruction_feasible"] = True

    # 事前註冊文件本身不准動
    out["decision_sha256_ok"] = files.get("decision_sha") == DECISION_SHA256
    out["decision_sha256"] = files.get("decision_sha")
    if not out["decision_sha256_ok"] and MUTANT != "X3_ignore_decision_sha":
        out["broken"].append("decision_file_changed_after_prereg")

    # 收據落盤
    out["receipts_ndjson_present"] = files.get("receipts_ndjson", False)
    if arms and "CONFORM" in arms and not out["receipts_ndjson_present"]:
        out["broken"].append("receipts_CONFORM.ndjson_missing")

    out["verdict"] = "BROKEN" if out["broken"] else "SCHEMA_COMPATIBLE"
    return out


# ── 夾具：欄位名在本檔獨立寫死一次，**不** import analyze_r447 的 _r()／_summary()
def _fx_rows():
    base = []
    for i in range(3):
        t = f"lcb_x{i}"
        base.append({"arm": "OFF", "task_id": t, "meets_demand": False, "accepted": True,
                     "calls_used": 1, "visible_ok": False})
        base.append({"arm": "CONFORM", "task_id": t, "meets_demand": True, "accepted": True,
                     "calls_used": 2, "visible_ok": True,
                     "conform_attempts": [{"attempt": 1}, {"attempt": 2}],
                     "conform_calls": 2, "receipt_head": "ab" * 32})
        base.append({"arm": "OFF5", "task_id": t, "meets_demand": True, "accepted": True,
                     "calls_used": 5, "visible_ok": True})
    return base


def _fx_calls(rows):
    out = []
    for r in rows:
        n = r.get("conform_calls") if r["arm"] == "CONFORM" else r["calls_used"]
        for _ in range(n):
            out.append({"role": "gen", "meta": {"arm": r["arm"], "task_id": r["task_id"]}})
    return out


def _fx_summary(terminal=True):
    return {"run_terminal": terminal,
            "arms": {a: {"processed": 3, "infra_void": 0} for a in ("OFF", "CONFORM", "OFF5")}}


def _fx_files():
    return {"decision_sha": DECISION_SHA256, "receipts_ndjson": True}


def selftest() -> int:
    global MUTANT, LAST_FAILS
    fails: list[str] = []
    LAST_FAILS = fails

    def ck(label, cond, extra=""):
        print(f"  {'ok  ' if cond else 'FAIL'} {label} {extra}")
        if not cond:
            fails.append(label)

    rows = _fx_rows()
    clean = check(rows, _fx_summary(), _fx_calls(rows), _fx_files())
    ck("X0 乾淨夾具 SCHEMA_COMPATIBLE", clean["verdict"] == "SCHEMA_COMPATIBLE", str(clean["broken"]))
    ck("X0b 契約常數從 analyzer 原始碼取得",
       "meets_demand" in clean["required"] and "receipt_head" in clean["required_conform"])

    r = [dict(x) for x in rows]; r[1].pop("meets_demand")
    ck("X1 缺欄位 ⇒ BROKEN", check(r, _fx_summary(), _fx_calls(rows), _fx_files())["verdict"] == "BROKEN")

    r = [dict(x) for x in rows]; r[0]["meets_demand"] = "False"
    ck("X2 型別錯 ⇒ BROKEN", check(r, _fx_summary(), _fx_calls(rows), _fx_files())["verdict"] == "BROKEN")

    ck("X3 0 列 ⇒ BROKEN（不是 PASS）",
       check([], _fx_summary(), [], _fx_files())["verdict"] == "BROKEN")

    r = [x for x in rows if x["arm"] != "CONFORM"]
    ck("X4 缺臂 ⇒ BROKEN", check(r, _fx_summary(), _fx_calls(rows), _fx_files())["verdict"] == "BROKEN")

    s = _fx_summary(); s["arms"]["OFF"].pop("infra_void")
    ck("X5 summary 缺鍵 ⇒ BROKEN", check(rows, s, _fx_calls(rows), _fx_files())["verdict"] == "BROKEN")

    c = [dict(x) for x in _fx_calls(rows)]
    for x in c:
        if x["meta"]["arm"] == "CONFORM":
            x["meta"] = {}
            break
    o = check(rows, _fx_summary(), c, _fx_files())
    ck("X6 gen 呼叫沒標 arm ⇒ 重建不可行", o["pz5b_reconstruction_feasible"] is False,
       f"untagged={o['reconstruct_untagged_gen_calls']}")

    c = [x for x in _fx_calls(rows) if not (x["meta"].get("arm") == "CONFORM"
                                            and x["meta"].get("task_id") == "lcb_x0")]
    o = check(rows, _fx_summary(), c, _fx_files())
    ck("X7 conform_calls 與 calls.jsonl 對不上 ⇒ 重建不可行",
       o["pz5b_reconstruction_feasible"] is False and o["reconstruct_mismatch_n"] == 1)

    f = _fx_files(); f["decision_sha"] = "0" * 64
    ck("X8 事前註冊文件被改 ⇒ BROKEN",
       check(rows, _fx_summary(), _fx_calls(rows), f)["verdict"] == "BROKEN")

    f = _fx_files(); f["receipts_ndjson"] = False
    ck("X9 收據檔不見 ⇒ BROKEN",
       check(rows, _fx_summary(), _fx_calls(rows), f)["verdict"] == "BROKEN")

    ck("X10 契約常數若改成寫死一份，X0b 會紅",
       "receipt_head" in clean["required_conform"])

    # X11 用 ast 掃 import 節點，**不准**用字串比對原始碼——needle 會匹配到這一條自己
    # （與 `pgrep -f` 匹配到自己是同一個坑，第一版就是這樣恆為真）。
    _imports = set()
    for _n in ast.walk(ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))):
        if isinstance(_n, ast.Import):
            _imports.update(al.name for al in _n.names)
        elif isinstance(_n, ast.ImportFrom):
            _imports.add(_n.module or "")
            _imports.update(f"{_n.module or ''}.{al.name}" for al in _n.names)
    ck("X11 本檔不得 import analyze_r447（結構上算不出 Δ）",
       not any("analyze_r447" in m for m in _imports), str(sorted(m for m in _imports if m)))

    print(f"SELFTEST {'PASS' if not fails else 'FAIL'} ({len(fails)} failed) MUTANT={MUTANT or 'none'}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.run:
        ap.error("--run 或 --selftest 二選一")
    d = pathlib.Path(a.run)
    raw = (d / "rows.jsonl").read_bytes()
    rows = [json.loads(l) for l in raw.decode("utf-8").splitlines() if l.strip()]
    summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    calls = [json.loads(l) for l in (d / "calls.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    files = {"decision_sha": hashlib.sha256(DECISION.read_bytes()).hexdigest(),
             "receipts_ndjson": (d / "receipts_CONFORM.ndjson").exists()}
    out = check(rows, summary, calls, files)
    out["rows_sha256_16"] = hashlib.sha256(raw).hexdigest()[:16]
    out["run"] = str(d)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str),
                                        encoding="utf-8")
    return 0 if out["verdict"] == "SCHEMA_COMPATIBLE" else 1


if __name__ == "__main__":
    sys.exit(main())
