#!/usr/bin/env python3
"""EQ5 收官前的 **schema 相容性**前置尺（round699）。

## 為什麼需要這把尺（它補的是 analyze_eq5 selftest 結構上看不見的東西）

`analyze_eq5.py --selftest` 有 A–N 十四條＋M1–M10 十個突變體，全綠。
但**每一條夾具都由同檔的 `_row()` 造**，而 `_row()` 與 analyzer 同一位作者、
同一組欄位名字串 ⇒ **selftest 全綠不構成「它讀得懂 runner 真的寫出來的 rows」
的任何證據**。這正是 round695 那類坑的同構型：夾具把要驗的兩端從同一處導出，
於是那條擋門結構上不可能被任何夾具看見。

本尺讀的是**真 run 落盤的 rows.jsonl**，而 `REQUIRED` 用 `ast` 從
`analyze_eq5.py` 原始碼逐字取出（不是抄一份），所以兩邊不可能漂開——
analyzer 改了 REQUIRED，本尺下一次跑就自動跟著改。

## 零新旋鈕
沒有任何門檻、沒有任何可調參數。判決全部是「有／沒有」與「型別對／不對」。

## 明令不做的事（DECISION_20260904_R446_EQUAL_BUDGET_ARM.md §五：中途不准算 Δ）
本檔**不 import `analyze()`**，不算 b／c／n_d／Δ／CI／四格判決／prereg 窗口。
它只回答「收官那一刻，analyzer 讀不讀得懂這份資料」。

## 「安靜量不到」兩型都要擋
型一 欄位不見／型別不對 ⇒ SCHEMA_INCOMPATIBLE（不是 PASS）。
型二 讀進來 0 列、或 arm 值不是 EQ5 ⇒ BROKEN（0 列全綠是套套邏輯）。

用法：
  python3 ops/gain/eq5_schema_precheck.py --selftest
  python3 ops/gain/eq5_schema_precheck.py --run runs/g_r446_eq5_mbpp [--json out.json]
"""
from __future__ import annotations
import argparse, ast, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve()
ANALYZER = HERE.parent / "analyze_eq5.py"

# analyzer 對每一欄實際做的運算所要求的型別。改這裡等於改契約 ⇒ 要同時改 analyzer。
TYPE_OK = {
    "gate_deliv": (bool,), "vote_deliv": (bool,), "calls_used": (int,),
    "same_choice": (bool,), "accepted": (bool,),
    "gate_code_sha256": (str,), "vote_code_sha256": (str,),
}


def required_from_source(path: pathlib.Path = None) -> tuple:
    """逐字從 analyze_eq5.py 的原始碼取 REQUIRED——不抄一份，避免兩邊漂開。
    （記憶鐵律：驗程式碼在什麼條件為真要取出真運算式，不准自己改寫一份。）"""
    src = (path or ANALYZER).read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "REQUIRED":
            return ast.literal_eval(node.value)
    raise SystemExit("BROKEN: analyze_eq5.py 裡找不到 REQUIRED ⇒ 契約來源不見了")


def check(rows: list[dict], summary: dict, required: tuple) -> dict:
    eq5 = [r for r in rows if r.get("arm") == "EQ5"]
    out: dict = {"rows_total": len(rows), "eq5_rows": len(eq5),
                 "arm_values": sorted({str(r.get("arm")) for r in rows}),
                 "required_from_source": list(required)}
    # 型二：0 列不准是綠燈
    if not eq5:
        out["verdict"] = "BROKEN"
        out["reasons"] = ["arm==EQ5 的列數為 0 ⇒ 量不到，不是通過"]
        return out

    unknown = [f for f in required if f not in TYPE_OK]
    if unknown:
        out["verdict"] = "BROKEN"
        out["reasons"] = [f"analyzer 新增了本尺沒有型別契約的欄位 {unknown} ⇒ "
                          "不准安靜跳過，要先補 TYPE_OK"]
        return out

    problems, fields = [], {}
    for f in required:
        absent = [r.get("task_id") for r in eq5 if f not in r]
        bad = [(r.get("task_id"), type(r[f]).__name__) for r in eq5
               if f in r and not isinstance(r[f], TYPE_OK[f])]
        fields[f] = {"absent": len(absent), "bad_type": len(bad),
                     "example_absent": absent[:3], "example_bad_type": bad[:3]}
        if absent:
            problems.append(f"{f}: {len(absent)} 列缺（例 {absent[:3]}）")
        if bad:
            problems.append(f"{f}: {len(bad)} 列型別不符（例 {bad[:3]}）")
    out["fields"] = fields

    # drift：same_choice 是否與兩份 sha 自洽（analyzer 的 N 條擋門會看的同一個不變量）
    drift = [r.get("task_id") for r in eq5
             if "same_choice" in r and "gate_code_sha256" in r and "vote_code_sha256" in r
             and bool(r["same_choice"]) != (r["gate_code_sha256"] == r["vote_code_sha256"])]
    out["drift_n"] = len(drift); out["drift_examples"] = drift[:5]

    notfive = [(r.get("task_id"), r.get("calls_used")) for r in eq5
               if r.get("calls_used") != 5]
    out["calls_not_5_n"] = len(notfive); out["calls_not_5_examples"] = notfive[:5]

    arm = (summary.get("arms") or {}).get("EQ5", {})
    out["summary_keys_present"] = {k: (k in arm) for k in
                                   ("processed", "infra_void", "terminal")}
    out["summary_terminal"] = arm.get("terminal")
    missing_summary = [k for k, v in out["summary_keys_present"].items() if not v]
    if missing_summary:
        problems.append(f"summary.arms.EQ5 缺 {missing_summary}")

    # AMEND-1 §七 的下游擋門（analyzer 的 M9）只在有落盤欄位時才可能觸發。
    # 一列都沒有 ⇒ 它在這個 run 上**結構上不可能被評估**，收官不得引用它為證據。
    landed = sum(1 for r in eq5 if "same_choice_effective" in r)
    out["same_choice_effective_landed"] = landed
    out["m9_guard_evaluable"] = landed > 0

    out["reasons"] = problems
    if problems:
        out["verdict"] = "SCHEMA_INCOMPATIBLE"
    elif drift:
        out["verdict"] = "DRIFT_FOUND"
    elif notfive:
        out["verdict"] = "BUDGET_DEFECT"
    else:
        out["verdict"] = "SCHEMA_COMPATIBLE"
    return out


# ------------------------------------------------------------------ selftest
def _real_row(tid: str, same: bool = True) -> dict:
    """夾具刻意**不**共用 analyze_eq5._row()——那正是本尺要補的盲點。
    欄位名在這裡是獨立寫死的字面字串；若 analyzer 的 REQUIRED 改了名而這裡沒改，
    自檢的 clean 條就會自己變紅，那是想要的行為（契約破了就要有人叫）。"""
    return {"arm": "EQ5", "task_id": tid, "calls_used": 5, "accepted": True,
            "same_choice": same, "gate_deliv": True, "vote_deliv": True,
            "gate_code_sha256": "aa" * 32,
            "vote_code_sha256": ("aa" if same else "bb") * 32}


def selftest() -> int:
    req = required_from_source()
    fails = []
    base = [_real_row(f"t{i}", same=(i % 3 != 0)) for i in range(30)]
    summ = {"arms": {"EQ5": {"processed": 30, "infra_void": 0, "terminal": True}}}

    def run(mutate=None, s=None):
        rs = [dict(r) for r in base]
        if mutate:
            mutate(rs)
        return check(rs, s or json.loads(json.dumps(summ)), req)

    cases = [
        ("clean",          None,
         "SCHEMA_COMPATIBLE"),
        ("X1 缺欄位",       lambda rs: rs[0].pop("vote_deliv"),
         "SCHEMA_INCOMPATIBLE"),
        ("X2 型別變字串",   lambda rs: rs[1].__setitem__("calls_used", "5"),
         "SCHEMA_INCOMPATIBLE"),
        ("X3 翻 same_choice（只翻欄位不動 sha）",
         lambda rs: rs[2].__setitem__("same_choice", not rs[2]["same_choice"]),
         "DRIFT_FOUND"),
        ("X4 預算改 4",     lambda rs: rs[3].__setitem__("calls_used", 4),
         "BUDGET_DEFECT"),
        ("X5 arm 改名（安靜量不到 型二）",
         lambda rs: [r.__setitem__("arm", "CONFORM") for r in rs],
         "BROKEN"),
        ("X6 全空",         lambda rs: rs.clear(),
         "BROKEN"),
    ]
    for name, mut, want in cases:
        got = run(mut)["verdict"]
        if got != want:
            fails.append(f"{name}: 期望 {want} 得到 {got}")

    # X7：summary 少一鍵要叫
    s2 = {"arms": {"EQ5": {"processed": 30, "infra_void": 0}}}
    if run(None, s2)["verdict"] != "SCHEMA_INCOMPATIBLE":
        fails.append("X7 summary 缺 terminal 竟然放行")

    # X8：analyzer 新增本尺沒有型別契約的欄位 ⇒ BROKEN，不准安靜跳過
    r8 = check([dict(x) for x in base], json.loads(json.dumps(summ)),
               req + ("brand_new_field",))
    if r8["verdict"] != "BROKEN" or not any("TYPE_OK" in x for x in r8["reasons"]):
        fails.append(f"X8 未知欄位竟然放行 -> {r8['verdict']}")

    # X9：M9 擋門可評估性——有落盤才是 True
    if run(None)["m9_guard_evaluable"] is not False:
        fails.append("X9 沒有落盤 same_choice_effective 卻說 M9 可評估")
    got9 = run(lambda rs: rs[0].__setitem__("same_choice_effective", True))
    if got9["m9_guard_evaluable"] is not True or got9["same_choice_effective_landed"] != 1:
        fails.append(f"X9 有落盤卻說不可評估 -> {got9['m9_guard_evaluable']}")

    # X10：REQUIRED 真的是從 analyzer 原始碼取的，不是本檔抄的
    if "gate_deliv" not in req or len(req) < 5:
        fails.append(f"X10 REQUIRED 取得可疑 -> {req}")

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST", "FAIL" if fails else "PASS",
          "(clean X1缺欄位 X2型別 X3drift X4預算 X5arm改名 X6全空 X7summary缺鍵"
          " X8未知欄位 X9M9可評估性 X10契約來源)")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run"); ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.run:
        print("需要 --run 或 --selftest"); return 2
    d = pathlib.Path(a.run)
    rows = [json.loads(l) for l in (d / "rows.jsonl").open(encoding="utf-8") if l.strip()]
    summ = json.load((d / "summary.json").open(encoding="utf-8"))
    out = check(rows, summ, required_from_source())
    out["run"] = str(d)
    js = json.dumps(out, ensure_ascii=False, indent=2)
    if a.json:
        pathlib.Path(a.json).write_text(js + "\n", encoding="utf-8")
    print(js)
    return 0 if out["verdict"] == "SCHEMA_COMPATIBLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
