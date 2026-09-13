"""題庫健檢：找出「精確解也會被判錯」的題目（round642 / R440T）。

為什麼要有這支：`probe_instrument()` 只驗**有參考解**的題目
（`[t for t in tasks if refs.get(...)][:sample]`）。LCB 沒有官方參考解，
手寫的只有 12 題，所以即使 `--probe-sample 0`（語意＝全驗）覆蓋率也只有
12/91 = 13.2%。另外 79 題的 `hidden_check` 從沒被證明過「正確解會通過」。
E3 就這樣把兩題「保證失敗」的題目算進了分母。

輸出三個數字（不要只報一個，理由見 R440T §二）：
  decisive_bad  有參考解、實跑判錯     ← 確定壞掉
  screened      沒參考解、篩出可疑     ← 線索，不是判決
  unverifiable  沒參考解、看起來正常   ← 不知道，別當成好的

判別量是**機制導出**的，不是從一個例子挑的代理：
浮點比對寫 `abs(a-b) <= T`，而 dataset 的 expected 存成 d 位小數時，
量化誤差上界是 0.5*10^-d。`0.5*10^-d > T` ⇒ 這題的檢查式**分不出**
正確答案與錯誤答案，是harness不健全，與模型無關。
只是 d 要取「這個值真的被四捨五入過」的那些——整數位或 .25/.75 這種
二進位可表示的值本來就是精確的，不算。所以 screen 的條件是
「小數位數 == 該題最大位數 d_max，且 d_max 足以觸發上式」。

⚠ screened 是篩子不是判決：要人眼確認（R440T 就是這樣確認 lcb_3613 的）。
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import re
import sys

_ROOT = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_gr", _ROOT / "gain_run.py")
_gr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gr)


def _expected_floats(check_code: str) -> list[float]:
    m = re.search(r"__tests = (\[.*?\])\n", check_code, re.S)
    if not m:
        return []
    try:
        tests = ast.literal_eval(m.group(1))
    except Exception:                                        # noqa: BLE001
        return []
    return [t["expected"] for t in tests
            if isinstance(t.get("expected"), float)]


def _tolerance(check_code: str) -> float | None:
    m = re.search(r"abs\(a - b\) <= ([0-9.e-]+)", check_code)
    return float(m.group(1)) if m else None


def audit(bank: str, seed: str, n: int) -> dict:
    tasks = _gr.load_tasks(bank, seed, n)
    try:
        refs = _gr._canonical_solutions(bank)
    except Exception:                                        # noqa: BLE001
        refs = {}
    decisive_bad, screened, unverifiable, ok = [], [], [], []
    for t in tasks:
        tid, hidden = t["task_id"], t["hidden_check"]["code"]
        tol = _tolerance(hidden)
        exps = _expected_floats(hidden)
        suspect = False
        if tol is not None and exps:
            dmax = max(len(repr(e).split(".")[1].rstrip("0") or "0") for e in exps)
            # 只看「位數 == d_max 且末位非 0」的那些：被四捨五入過的候選
            rounded = [e for e in exps
                       if len(repr(e).split(".")[1]) == dmax and repr(e)[-1] != "0"]
            suspect = bool(rounded) and 0.5 * 10 ** (-dmax) > tol
        if refs.get(tid):
            # 決定性：真的跑一次官方／手寫參考解
            good, _ = _gr.meets_demand(refs[tid], hidden,
                                       entry_point=t.get("entry_point"))
            (ok if good else decisive_bad).append(tid)
        elif suspect:
            screened.append(tid)
        else:
            unverifiable.append(tid)
    return {"bank": bank, "n": len(tasks), "decisive_ok": ok,
            "decisive_bad": decisive_bad, "screened": screened,
            "unverifiable": unverifiable}


# R440T：人眼確認過的「精確解也會被判錯」名單。修好題庫才准從這裡拿掉。
# lcb2（v2 題庫，2026-09-04）沿用同兩題——**不是新的人眼確認**：v2 是 v1 的嚴格
# 超集，這兩筆紀錄與 v1 逐欄相同（`ops/gain/verify_lcb_bank.py --version v2
# --compare v1` 的 overlap_records_identical=true 證明），所以 R440T 的確認直接
# 適用。test4 視窗新增的 29 題**沒有**任何一題被旗標，若將來冒出新的，這支照樣
# FAIL——名單是白名單不是消音器。
KNOWN_BAD = {"lcb": {"lcb_3613", "lcb_3763"},
             "lcb2": {"lcb_3613", "lcb_3763"}}

if __name__ == "__main__":
    bank = sys.argv[1] if len(sys.argv) > 1 else "lcb"
    seed = sys.argv[2] if len(sys.argv) > 2 else "g-r442-lcb"
    # round440y：預設 n 原本寫死 91，對 120 題的 lcb2 會截掉後 29 題，KNOWN_BAD 兩題落在
    # 截掉的那段就「沒被抓到」——尺沒鈍，是尺只量了一半。0 = 全題庫（load_tasks 的語意）。
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    r = audit(bank, seed, n)
    cov = len(r["decisive_ok"]) + len(r["decisive_bad"])
    print(f"bank={r['bank']} n={r['n']}")
    print(f"  量具決定性覆蓋 {cov}/{r['n']} = {100*cov/r['n']:.1f}%"
          f"（其餘沒有參考解，證不了正解會通過）")
    print(f"  decisive_bad  {len(r['decisive_bad'])} {sorted(r['decisive_bad'])}")
    print(f"  screened      {len(r['screened'])} {sorted(r['screened'])}  ← 線索，要人眼")
    print(f"  unverifiable  {len(r['unverifiable'])}")
    flagged = set(r["decisive_bad"]) | set(r["screened"])
    known = KNOWN_BAD.get(bank, set())
    if flagged - known:
        print(f"\nFAIL: 冒出名單外的可疑題 {sorted(flagged - known)}"
              f"——人眼確認後才准加進 KNOWN_BAD")
        sys.exit(1)
    if known - flagged:
        print(f"\nFAIL: KNOWN_BAD 裡的 {sorted(known - flagged)} 這次沒被抓到"
              f"——尺鈍了或題庫修好了，兩種都要人來判")
        sys.exit(1)
    print(f"\nOK: 旗標與 KNOWN_BAD 一致 {sorted(known)}")
