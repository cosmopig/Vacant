"""R440P 稽核：獨立重放「跑一次就好」——不沿用 workflow 的腳本，獨立程式碼路徑。

這支在架構裡承重什麼：workflow 的三個提案都宣稱「用客戶自己的可見驗收測資篩候選解」
在等預算下有 +1.8~+5.2pp、在預算軸上有 4 倍節省，但那 6 個對抗驗證 agent 全部撞到
session 上限沒跑成。稽核輪（fable）的職責是重算一次（LOOP_PROMPT 模型政策）。

紀律：
- 選擇只准用 visible_check；hidden_check 只用來計分。V/GT 分離是紅線（SPEC §5.3）。
- 零 API 呼叫。只讀 runs/*/calls.jsonl 與 rows.jsonl，本機沙箱執行。
- 用 runtime 自己的 extract_code／meets_demand，不自己重寫判定。
用法：.venv/bin/python ops/gain/replay/audit_fable_r440p.py <run> [workers]
"""
from __future__ import annotations

import collections
import json
import math
import os
import pathlib
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
)

from ops.gain.gain_run import extract_code, meets_demand  # noqa: E402
from vacant.codebench import EvalPlusMBPPLoader  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent


def _one(job):
    """(key, code, visible_code, hidden_code, entry) -> (key, vis, hid)。"""
    key, code, vis_code, hid_code, entry = job
    try:
        vis, _ = meets_demand(code, vis_code, timeout_s=10, entry_point=entry)
    except Exception:
        vis = None
    try:
        hid, _ = meets_demand(code, hid_code, timeout_s=10, entry_point=entry)
    except Exception:
        hid = None
    return key, vis, hid


def mcnemar(pairs):
    """pairs: list[(a_ok, b_ok)] -> (n, b, c, p) 精確二項雙尾。"""
    b = sum(1 for x, y in pairs if x and not y)
    c = sum(1 for x, y in pairs if y and not x)
    n = b + c
    if n == 0:
        return len(pairs), b, c, 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1))
    return len(pairs), b, c, min(1.0, 2 * tail / 2 ** n)


def main(run: str, workers: int = 6) -> None:
    root = pathlib.Path("runs") / run
    tasks = {t["task_id"]: t for t in EvalPlusMBPPLoader(expose_contract=True).iter_tasks("x")}

    rows = [json.loads(l) for l in (root / "rows.jsonl").open()]
    shipped = {
        r["task_id"]: bool(r.get("meets_demand"))
        for r in rows
        if r.get("arm") == "OFF5"
    }

    # OFF5 的 gen 候選，保持 calls.jsonl 的原始順序（＝真實抽樣順序）
    cands: dict[str, list[str]] = collections.defaultdict(list)
    for line in (root / "calls.jsonl").open():
        d = json.loads(line)
        if d.get("role") != "gen" or not d.get("ok"):
            continue
        meta = d.get("meta") or {}
        if meta.get("arm") != "OFF5":
            continue
        tid = meta.get("task_id")
        if tid in shipped:
            cands[tid].append(extract_code(d.get("response") or ""))

    jobs = []
    for tid, codes in cands.items():
        t = tasks.get(tid)
        if not t:
            continue
        for i, code in enumerate(codes):
            jobs.append(((tid, i), code, t["visible_check"]["code"],
                         t["hidden_check"]["code"], t.get("entry_point")))
    print(f"{run}: {len(cands)} OFF5 tasks, {len(jobs)} candidates to execute "
          f"(x2 checks, {workers} workers)", flush=True)

    facts: dict[tuple, tuple] = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, (key, vis, hid) in enumerate(ex.map(_one, jobs, chunksize=4), 1):
            facts[key] = (vis, hid)
            if i % 100 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)

    (OUT / f"audit_r440p_{run}.json").write_text(
        json.dumps({f"{k[0]}#{k[1]}": v for k, v in facts.items()}, indent=1))

    # ── 主張 1：可見篩選是無損的？（hidden 過但 visible 沒過 = 會被誤丟的正確解）
    lossless_viol = [k for k, (v, h) in facts.items() if h and not v]
    print(f"\n[1] 無損性：hidden 過但 visible 沒過的候選 = {len(lossless_viol)} / {len(facts)}")
    if lossless_viol:
        print("    違反樣本:", lossless_viol[:8])

    # ── 主張 2：first-visible-pass（早停）vs OFF5 實際出貨
    pairs_ship, calls_used, n_none, oracle_hit, refuse_ok = [], [], 0, 0, 0
    for tid, codes in cands.items():
        seq = [facts.get((tid, i), (None, None)) for i in range(len(codes))]
        pick, used = None, len(seq)
        for i, (v, h) in enumerate(seq, 1):
            if v:
                pick, used = h, i
                break
        if pick is None:                       # 沒有任何候選通過可見測資
            n_none += 1
            if not any(h for _, h in seq):
                refuse_ok += 1                 # 拒交是對的：本來就沒有正確解
            pairs_ship.append((False, shipped.get(tid, False)))
        else:
            pairs_ship.append((bool(pick), shipped.get(tid, False)))
        calls_used.append(used)
        if any(h for _, h in seq):
            oracle_hit += 1

    n = len(pairs_ship)
    pol = sum(1 for a, _ in pairs_ship if a)
    shp = sum(1 for _, b in pairs_ship if b)
    N, b, c, p = mcnemar(pairs_ship)
    print(f"\n[2] first-visible-pass（早停）vs OFF5 實際出貨   n={n}")
    print(f"    policy {pol}/{n} = {100*pol/n:.2f}%   平均呼叫 {sum(calls_used)/n:.2f}/題")
    print(f"    OFF5   {shp}/{n} = {100*shp/n:.2f}%   呼叫 5.00/題")
    print(f"    差 {100*(pol-shp)/n:+.2f}pp   McNemar b={b} c={c} n_disc={b+c} p={p:.4f}")

    # ── 主張 3：嚴格等預算——抽滿 5 個，再篩可見、取第一個通過者
    #    ⚠ 這裡原本寫成「取通過可見者的 hidden 多數決」，那是用 hidden 決定要交哪一個，
    #      本身就違反 V/GT 分離、不是可出貨的機制（稽核時自己抓到，照實留註記）。
    #      正確的等預算規則只准用 visible：抽滿 5 個之後挑第一個通過可見測資的。
    #      它與早停選中的是同一個候選，差別只有花掉的呼叫數——這正好把
    #      「準確率來自篩選、便宜來自早停」這兩件事分開。
    pairs5 = []
    for tid, codes in cands.items():
        seq = [facts.get((tid, i), (None, None)) for i in range(len(codes))]
        pick = next((h for v, h in seq if v), None)
        pairs5.append((bool(pick), shipped.get(tid, False)))
    n5 = len(pairs5); p5 = sum(1 for a, _ in pairs5 if a)
    _, b5, c5, pv5 = mcnemar(pairs5)
    print(f"\n[3] 可見篩選（抽滿 5 通，嚴格等預算，只用 visible 決定） {p5}/{n5} = {100*p5/n5:.2f}%"
          f"  差 {100*(p5-shp)/n5:+.2f}pp  b={b5} c={c5} p={pv5:.4f}")

    # ── 主張 4：天花板——池子裡有沒有正確解
    print(f"\n[4] 池子上限：至少一個候選 hidden 過 = {oracle_hit}/{n} = {100*oracle_hit/n:.2f}%"
          f"   （{n-oracle_hit} 題五個候選全錯，任何選擇機制都救不了）")
    print(f"    無任何候選通過可見測資 = {n_none} 題，其中 {refuse_ok} 題本來就沒有正確解"
          f"（拒交正確）")

    # ── 主張 5：單抽基線（第一個候選）——早停的對照
    pairs1 = [(bool(facts.get((tid, 0), (None, None))[1]), shipped.get(tid, False))
              for tid in cands]
    p1 = sum(1 for a, _ in pairs1 if a)
    print(f"\n[5] 單抽（只用第一個候選，1 通呼叫）{p1}/{n} = {100*p1/n:.2f}%")
    pairs_es_vs_1 = []
    for i, tid in enumerate(cands):
        pairs_es_vs_1.append((pairs_ship[i][0], pairs1[i][0]))
    _, be, ce, pe = mcnemar(pairs_es_vs_1)
    print(f"    早停 vs 單抽（同一份重放標籤，無標籤不對稱）："
          f"b={be} c={ce} p={pe:.4f}  差 {100*(pol-p1)/n:+.2f}pp")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 6)
