#!/usr/bin/env python3
"""r444 的 P-C3 後半結算——`leaked` 的三項分解與等覆蓋率反事實。

算術照 `CRITERION_20260903_R668_LEAK_DECOMPOSITION.md`，**量測前寫死**。
零模型呼叫、零沙箱：只讀 rows.jsonl／summary.json 已落盤的欄位，
loader 與逐臂統計沿用 round667 的 `conform_settle`（同一份不變量，不另寫一套）。

要解的問題（判準 §一）：R440R 的 P-C3 後半「leaked 明顯低於 OFF5」沒有門檻、
也沒有指定算法，而 `leaked = n_acc - n_acc_ok` 是**逐題**計數且 CONFORM 拒交時
該題不進 n_acc ⇒

    leaked = measured − refused − deliv                      （恆等式，判準 §二）

    Δleaked = leaked(OFF5) − leaked(CONFORM)
            = refusal_driven + accuracy_driven + void_asymmetry

「漏得少」可以完全由「交得少」買到。所以本尺**一律同時印三個數字**（判準 §三）：
  (a) 字面計數      leaked(CONFORM) vs leaked(OFF5)
  (b) 三項分解      拒交驅動 ≥50% ⇒ mostly_bought_by_refusing=true，收官文字必須照寫
  (c) 反事實        forced_leak = leaked + (refused − md∧¬acc)＝強迫交出拒交題會漏幾題

新增可調參數：**零**。恆等式對不上就 BROKEN，不回傳好看的數字。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from conform_settle import (  # noqa: E402
    Broken, _bool, arm_block, index_by_task, load_rows,
)


def decompose(rows_path: pathlib.Path, summary_path: pathlib.Path,
              test_arm: str, baseline: str, third: str | None,
              tail_from: int | None) -> dict:
    rows = load_rows(rows_path)
    if not summary_path.exists():
        raise Broken(f"找不到 {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    arms = [a for a in (baseline, test_arm, third) if a]
    declared = list(summary.get("arms", {}))
    for a in arms:
        if a not in declared:
            raise Broken(f"summary.json 的 arms 沒有 {a!r}（有的是 {declared}）")
    idx = {a: index_by_task(rows, a) for a in arms}
    blocks = {a: arm_block(idx[a]) for a in arms}

    terminal = all(summary["arms"][a].get("terminal") for a in arms)

    # ⚠ round668 實測：判準 §四 的 P-R668-1（單源恆等式）**是恆等式不是預測**。
    #   leaked ≡ count(acc∧¬md)，而 measured−refused−deliv ≡ acc−count(acc∧md)
    #   ≡ count(acc∧¬md)，兩邊都由同一份 rows 算出 ⇒ 2000 組隨機／任意翻轉的列
    #   100% 成立，沒有任何輸入能推翻它。它只擋得住我自己寫錯這支程式，
    #   擋不住資料。留著（當算術護欄）但**不准當成通過的檢定**。
    identity = {}
    for a in arms:
        b = blocks[a]
        lhs, rhs = b["leaked"], b["rows"] - b["refused"] - b["deliv"]
        if lhs != rhs:  # 只有本檔算錯才會走到這裡
            raise Broken(f"{a} 臂 leaked={lhs} ≠ measured−refused−deliv={rhs}")
        identity[a] = {"leaked": lhs, "measured": b["rows"], "refused": b["refused"],
                       "deliv": b["deliv"], "holds": True,
                       "tautology": True}

    # 有牙齒的那條：rows 與 summary.json 是**兩個獨立的產出者**
    #   （rows 逐格 append；summary 由 st[arm] 的計數器每題重寫一次）⇒ 對不上
    #   就是真的有一邊壞了。沿用 round667 M6 的邊界：這條不變量只在 run 靜止時
    #   成立，terminal=False 的快照必然差到一題 ⇒ 降級成照實報 skew。
    cross = {}
    skew = []
    for a in arms:
        b, sa = blocks[a], summary["arms"][a]
        pairs = [("leaked", b["leaked"]),
                 ("accepted", b["accepted"]),
                 ("accepted_and_meets_demand", b["deliv"])]
        for field, recomputed in pairs:
            declared_v = sa.get(field)
            if declared_v is None:
                raise Broken(f"summary.json 的 {a} 臂沒有 {field} 欄位——不准安靜跳過")
            if declared_v != recomputed:
                msg = (f"{a}.{field}：summary={declared_v} vs 逐列覆算={recomputed}")
                if terminal:
                    raise Broken(msg + "（收官結算時兩個獨立產出者必須逐位相同）")
                skew.append(msg)
        cross[a] = {f: sa.get(f) for f, _ in pairs}

    t, o = blocks[test_arm], blocks[baseline]
    delta = o["leaked"] - t["leaked"]
    refusal_driven = t["refused"] - o["refused"]
    accuracy_driven = t["deliv"] - o["deliv"]
    void_asym = o["rows"] - t["rows"]

    # 判準 §四 P-R668-2：三項和必須逐位等於 Δleaked。
    if refusal_driven + accuracy_driven + void_asym != delta:
        raise Broken(
            f"三項分解對不上：{refusal_driven}+{accuracy_driven}+{void_asym}"
            f"={refusal_driven + accuracy_driven + void_asym} ≠ Δleaked={delta}")

    # 判準 §三 (c)：等覆蓋率反事實。md∧¬acc 是「拒交但離線候選其實是對的」，
    # 強迫交出去不會變成漏出，所以要扣掉。
    md_not_acc = t["meets_demand_and_not_accepted"]
    forced_leak = t["leaked"] + (t["refused"] - md_not_acc)

    share = (refusal_driven / delta) if delta else None

    # 判準 §四 P-R668-4：最後一段（未被中途快照污染的增量）的 md∧¬acc。
    tail = None
    if tail_from is not None:
        tail_rows = [r for r in rows if r["arm"] == test_arm and int(r["i"]) > tail_from]
        tail = {
            "test_arm": test_arm, "i_gt": tail_from, "n": len(tail_rows),
            "refused": sum(1 for r in tail_rows if not _bool(r, "accepted")),
            "meets_demand_and_not_accepted": sum(
                1 for r in tail_rows
                if _bool(r, "meets_demand") and not _bool(r, "accepted")),
        }

    return {
        "rows_source": str(rows_path),
        "rows_sha256_8": hashlib.sha256(rows_path.read_bytes()).hexdigest()[:8],
        "n_rows": len(rows),
        "run_terminal": bool(terminal),
        "settlement_ready": bool(terminal),
        "identity_leaked_eq_measured_minus_refused_minus_deliv": identity,
        "cross_source_rows_vs_summary": cross,
        "live_snapshot_skew": skew,
        "literal": {  # 判準 §三 (a)
            "leaked_test": t["leaked"], "leaked_baseline": o["leaked"],
            "direction_ok": t["leaked"] < o["leaked"],
            "obvious_threshold": None,  # R440R 沒給門檻，且已污染 ⇒ 不判「明顯」
        },
        "decomposition": {  # 判準 §三 (b)
            "delta_leaked": delta,
            "refusal_driven": refusal_driven,
            "accuracy_driven": accuracy_driven,
            "void_asymmetry": void_asym,
            "refusal_share": share,
            "mostly_bought_by_refusing": (share is not None and share >= 0.5),
        },
        "counterfactual_equal_coverage": {  # 判準 §三 (c)
            "forced_leak_test": forced_leak,
            "leaked_baseline": o["leaked"],
            "meets_demand_and_not_accepted": md_not_acc,
            "gap_raw": delta,
            "gap_forced": o["leaked"] - forced_leak,
            "gate_selects_better": forced_leak < o["leaked"],
        },
        "tail_uncontaminated": tail,
        "arms": blocks,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--rows", default=None, help="預設 <run>/rows.jsonl；可指向唯讀快照")
    ap.add_argument("--summary", default=None)
    ap.add_argument("--test-arm", default="CONFORM")
    ap.add_argument("--baseline", default="OFF5")
    ap.add_argument("--third", default="OFF")
    ap.add_argument("--tail-from", type=int, default=None,
                    help="只統計 i > 這個值的受測臂列（判準 §四 P-R668-4 的未污染增量）")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    run = pathlib.Path(a.run)
    rows = pathlib.Path(a.rows) if a.rows else run / "rows.jsonl"
    summ = pathlib.Path(a.summary) if a.summary else run / "summary.json"
    try:
        out = decompose(rows, summ, a.test_arm, a.baseline, a.third, a.tail_from)
    except Broken as e:
        print(f"BROKEN: {e}", file=sys.stderr)
        return 2

    d, c, l = out["decomposition"], out["counterfactual_equal_coverage"], out["literal"]
    print(f"rows={out['n_rows']} sha256_8={out['rows_sha256_8']} "
          f"terminal={out['run_terminal']}"
          + ("" if out["run_terminal"] else "  ⚠ 未收官＝不是結論"))
    print("恆等式 leaked = measured − refused − deliv：三臂成立"
          "（⚠ 這是恆等式不是檢定，任何輸入都成立——見 round668）")
    print(f"跨來源 rows vs summary：{'逐位相同' if not out['live_snapshot_skew'] else out['live_snapshot_skew']}")
    print(f"(a) 字面   leaked {a.test_arm}={l['leaked_test']} vs "
          f"{a.baseline}={l['leaked_baseline']}  方向{'對' if l['direction_ok'] else '錯'}"
          "（『明顯』無門檻⇒不判）")
    print(f"(b) 分解   Δleaked={d['delta_leaked']} = 拒交驅動 {d['refusal_driven']}"
          f" + 準確率驅動 {d['accuracy_driven']} + void不對稱 {d['void_asymmetry']}")
    sh = "n/a" if d["refusal_share"] is None else f"{100*d['refusal_share']:.1f}%"
    print(f"           拒交佔比={sh}  ⇒ 主要靠交得少？{d['mostly_bought_by_refusing']}")
    print(f"(c) 反事實 forced_leak={c['forced_leak_test']} vs {a.baseline}="
          f"{c['leaked_baseline']}  等覆蓋率差距={c['gap_forced']}（原始差距={c['gap_raw']}）"
          f"  閘門選得較準？{c['gate_selects_better']}")
    if out["tail_uncontaminated"]:
        t = out["tail_uncontaminated"]
        print(f"未污染增量 i>{t['i_gt']}：n={t['n']} 拒交={t['refused']} "
              f"md∧¬acc={t['meets_demand_and_not_accepted']}")
    if a.json:
        p = pathlib.Path(a.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"→ {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
