"""R440Q：LCB 上「可見測資 ⊆ 隱藏測資」是不是構造上就成立？

為什麼要這支：R440P §七 第一條把「在 LCB 重放，看有沒有 hidden 過但 visible 沒過的
候選」當成裁決的推翻條件，前提是「LCB 的可見／隱藏關係與 MBPP+ 不同」。這支就是去
驗那個前提本身——如果 LCB 的 hidden 也是 visible 的超集，那個重放在構造上就不可能
出現違反，量到 0 是套套邏輯，不能當外部效度的獨立驗證。

零 API、純標準庫、只讀 bank 與 loader。

用法：python3 ops/gain/replay/check_lcb_visible_subset.py [--selftest]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from vacant.codebench import LiveCodeBenchLoader, _lcb_check_code  # noqa: E402

MIN_TASKS = 91  # bank 釘死題數；量到比這少 = 安靜漏題，要 BROKEN 不是 PASS


def _tests_of(rec_tests: list[dict]) -> list[tuple]:
    """把測資正規化成可比較的 (args, expected) 序對。"""
    return [(repr(t["args"]), repr(t["expected"])) for t in rec_tests]


def audit(records: list[dict]) -> dict:
    """回傳每題的關係判定。prefix = visible 是 full 的前綴（順序保留的子集）。

    ⚠ 這一層是**循環的**，不能單獨當證據：本函式自己用 `visible + hidden` 組出
    `full`，跟 loader 的組法一模一樣，所以 prefix=100% 是定義使然而不是量測。
    留著只當描述性計數。**承重的是 `embed_check()`**——它讀 loader 真正生出來的
    check code 字串，那才是實際拿去跑的東西。
    """
    out = {"n": 0, "prefix": [], "subset_not_prefix": [], "not_subset": []}
    for rec in records:
        vis = _tests_of(rec["visible_tests"])
        full = _tests_of(rec["visible_tests"] + rec["hidden_tests"])
        tid = rec["task_id"]
        out["n"] += 1
        if full[: len(vis)] == vis:
            out["prefix"].append(tid)
        elif set(vis) <= set(full):
            out["subset_not_prefix"].append(tid)
        else:
            out["not_subset"].append(tid)
    return out


def embed_check(tasks) -> dict:
    """承重層：讀 loader 實際生成的 check code，hidden 的測資清單是否以 visible 開頭。

    這一層不循環——它比對的是 `iter_tasks()` 真正吐出來、之後真的會被沙箱執行的
    兩段程式碼字串。
    """
    out = {"n": 0, "embed_ok": 0, "embed_bad": [], "unparsed": []}
    for t in tasks:
        out["n"] += 1
        try:
            vis_body = t["visible_check"]["code"].split("__tests = ", 1)[1].split("\n", 1)[0]
            hid_body = t["hidden_check"]["code"].split("__tests = ", 1)[1].split("\n", 1)[0]
        except IndexError:
            out["unparsed"].append(t["task_id"])   # 解析不到 = BROKEN，不准算 PASS
            continue
        if vis_body.endswith("]") and hid_body.startswith(vis_body[:-1]):
            out["embed_ok"] += 1
        else:
            out["embed_bad"].append(t["task_id"])
    return out


def selftest() -> int:
    """植入缺陷：承重層 embed_check() 在三種壞法下都必須叫。

    這是「安靜量不到」的防線：解析不到、沒包住、題數掉下來，三種都要 BROKEN
    而不是 PASS。
    """
    ok = True

    def mk(tid, vis_lit, hid_lit):
        return {"task_id": tid,
                "visible_check": {"code": f"__tests = {vis_lit}\nfor __t in __tests:"},
                "hidden_check": {"code": f"__tests = {hid_lit}\nfor __t in __tests:"}}

    # 正常：hidden 以 visible 開頭
    r = embed_check([mk("T_ok", "[1, 2]", "[1, 2, 3]")])
    if r["embed_ok"] != 1 or r["embed_bad"]:
        print("SELFTEST FAIL: 正常題沒被判成 embed_ok", r); ok = False

    # 缺陷 1：hidden 沒有包住 visible（兩份測資脫鉤）
    r = embed_check([mk("T_decoupled", "[9]", "[1, 2, 3]")])
    if r["embed_bad"] != ["T_decoupled"]:
        print("SELFTEST FAIL: 脫鉤沒被抓到", r); ok = False

    # 缺陷 2：visible 是 hidden 的子集但不是前綴（順序被打散）
    r = embed_check([mk("T_reordered", "[2, 1]", "[1, 2]")])
    if r["embed_bad"] != ["T_reordered"]:
        print("SELFTEST FAIL: 非前綴沒被抓到", r); ok = False

    # 缺陷 3：check code 格式變了，解析不到 —— 要進 unparsed 不能算 ok
    r = embed_check([{"task_id": "T_unparsed",
                      "visible_check": {"code": "no marker here"},
                      "hidden_check": {"code": "no marker here"}}])
    if r["unparsed"] != ["T_unparsed"] or r["embed_ok"]:
        print("SELFTEST FAIL: 解析失敗被安靜當成通過", r); ok = False

    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    loader = LiveCodeBenchLoader()
    records = loader._records
    r = audit(records)

    print(f"LCB bank 題數 = {r['n']}（門檻 MIN_TASKS={MIN_TASKS}）")
    if r["n"] < MIN_TASKS:
        print("BROKEN：題數少於釘死值，安靜漏題")
        return 2
    print(f"  visible 是 full 的前綴        : {len(r['prefix'])}")
    print(f"  visible ⊆ full 但非前綴       : {len(r['subset_not_prefix'])}")
    print(f"  visible ⊄ full（關係真的不同）: {len(r['not_subset'])}")
    if r["not_subset"]:
        print("    樣本:", r["not_subset"][:8])

    # ── 承重層：讀 loader 真正生成的 check code（非循環）
    e = embed_check(LiveCodeBenchLoader().iter_tasks("x"))
    print(f"\n[承重層] 生成的 check code n={e['n']}")
    print(f"  hidden 的測資清單以 visible 開頭 : {e['embed_ok']}")
    print(f"  沒包住（關係真的不同）          : {len(e['embed_bad'])}", e["embed_bad"][:8])
    print(f"  解析不到（BROKEN）              : {len(e['unparsed'])}", e["unparsed"][:8])
    if e["n"] < MIN_TASKS or e["unparsed"]:
        print("BROKEN：題數不足或有解析不到的題")
        return 2
    if not e["embed_bad"]:
        print("\n結論：LCB 的 hidden 在構造上就是 visible 的超集（與 MBPP+ 同款）。")
        print("      ⇒ R440P §七 第一條在 LCB 上『構造上不可能違反』，")
        print("        重放量到 0 是套套邏輯，不能當外部效度的獨立驗證。")
        print("      唯一還活著的違反管道是候選程式碼自身的非決定性（亂數／時間／逾時）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
