"""路由混合分析：信譽路由「選到比較差的 agent」這個假說能解釋多少 ON-vs-OFF 落差？

round56 把「信譽路由選到比較差的 agent」記成**假說**，並指出驗證它要新開一條
ON-random-routing 臂。本工具指出那條新臂大部分是多餘的，理由是資料上的：

    `arm_off` 的實作就是 `rng.choice(agents)` ＝ **OFF baseline 本身就是
    「隨機路由 ＋ 1 通呼叫」**；而 ON 的初稿是「信譽路由 ＋ 1 通呼叫」。
    兩者相減就是隨機 vs 信譽的對照，不需要新臂。

本工具只讀既有 run 目錄的 rows.jsonl，不打端點、不改判準、不重跑實驗。

它算三件事：

1. **逐 agent 單稿品質**（OFF 的 `meets_demand` 與 ON 的 `initial_meets_demand`
   都是隱藏測資的結果，可比）。OFF 那一欄是隨機指派，是無偏樣本；ON 那一欄
   的指派只看稽核歷史、不看題目內容，故對 persona 品質同樣無偏。
2. **混合效應**：把 ON 實際的路由份額，套在逐 agent 品質上，得到「若品質估計
   為真，ON 的路由混合預期交付率」；再跟均勻份額的預期值相比。兩者之差就是
   **路由政策最多能解釋的落差**。
3. **persona 品質離散度**是否存在（careful-1 vs 其餘的 Fisher 精確檢定）。
   選擇機制只有在被選的對象「真的有好壞之分」時才可能帶來增益；若池子裡
   人人一樣好，任何路由政策的期望值都相同。

用法：
    python3 ops/gain/analyze_routing_mix.py \
        --on runs/g_onoff5_qwenonly_v3_20260824 \
        --off runs/g_off60_qwenonly_20260824 \
        [--off5 runs/g_onoff5_qwenonly_v3_20260824] \
        [--json-out /dev/shm/routing_mix.json]

`--off5` 是**前瞻性推翻條件**用的：OFF5 的 5 通 gen 是 `rng.choice`，均勻抽樣，
跑滿 60 題會累積 ~300 次抽籤（每個 persona ~50 次），是獨立於本結論的乾淨樣本。
"""
from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path


def _rows(run_dir: Path) -> list[dict]:
    path = run_dir / "rows.jsonl"
    if not path.exists():
        raise SystemExit(f"找不到 {path}")
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def _log_comb(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """2x2 表的 Fisher 精確雙尾 p（以機率法累加不比觀測更可能的表）。"""
    n = a + b + c + d
    row1, col1 = a + b, a + c
    lo = max(0, col1 - (n - row1))
    hi = min(row1, col1)

    def logp(x: int) -> float:
        return (_log_comb(row1, x) + _log_comb(n - row1, col1 - x)) - _log_comb(n, col1)

    observed = logp(a)
    total = 0.0
    for x in range(lo, hi + 1):
        lp = logp(x)
        if lp <= observed + 1e-9:
            total += math.exp(lp)
    return min(1.0, total)


def wilson(k: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - margin) / denom, (centre + margin) / denom)


def collect(on_dir: Path, off_dir: Path, off5_dir: Path | None) -> dict:
    off_rows = [r for r in _rows(off_dir) if r.get("arm") == "OFF"]
    on_rows = [r for r in _rows(on_dir) if r.get("arm") == "ON"]

    # infra_void 的題目不在 rows.jsonl（它們寫進 notes.jsonl），故 rows 一律是
    # 「量到的格子」；err='sandbox_check_failed' 是**候選碼答錯**，不是 infra_void，
    # 千萬不能拿 err 當過濾條件（那會把所有失敗刪掉、每個 agent 都變 100%）。
    per_agent: dict[str, dict] = collections.defaultdict(
        lambda: {"off_ok": 0, "off_n": 0, "on_ok": 0, "on_n": 0})
    for r in off_rows:
        s = per_agent[r["worker"]]
        s["off_n"] += 1
        s["off_ok"] += int(bool(r.get("meets_demand")))
    for r in on_rows:
        s = per_agent[r["worker"]]
        s["on_n"] += 1
        s["on_ok"] += int(bool(r.get("initial_meets_demand")))

    for name, s in per_agent.items():
        s["pooled_ok"] = s["off_ok"] + s["on_ok"]
        s["pooled_n"] = s["off_n"] + s["on_n"]
        s["pooled_rate"] = s["pooled_ok"] / s["pooled_n"] if s["pooled_n"] else None
        s["off_rate"] = s["off_ok"] / s["off_n"] if s["off_n"] else None
        s["pooled_ci95"] = wilson(s["pooled_ok"], s["pooled_n"])

    agents = sorted(per_agent)
    on_share = {a: per_agent[a]["on_n"] for a in agents}
    on_total = sum(on_share.values())

    # 混合效應：同一組品質估計，兩種份額。
    def mix(rates: dict[str, float | None], share: dict[str, float]) -> float | None:
        num = den = 0.0
        for a in agents:
            if rates.get(a) is None:
                return None
            num += share[a] * rates[a]
            den += share[a]
        return num / den if den else None

    uniform = {a: 1.0 for a in agents}
    pooled_rates = {a: per_agent[a]["pooled_rate"] for a in agents}
    off_only_rates = {a: per_agent[a]["off_rate"] for a in agents}

    # ⚠ pooled 估計是**循環的**，不可用於歸因：agent 的 pooled 品質裡含有 ON 臂
    # 自己的成績，而 ON 的份額正是被解釋的對象 ⇒ 任何 ON-vs-OFF 落差都會被
    # pooled 估計自動部分改寫成「路由造成的」。植入測試證實了這一點：兩個 agent
    # 真品質相同(0.4)、ON 份額全偏向 A 時，off_only 正確吐 +0.00pp，pooled 吐
    # 出憑空的 +10.00pp。歸因一律看 off_only；pooled 只留著當診斷對照。
    mix_effect = {}
    for label, rates in (("pooled_CIRCULAR", pooled_rates), ("off_only", off_only_rates)):
        routed = mix(rates, {a: float(on_share[a]) for a in agents})
        rand = mix(rates, uniform)
        mix_effect[label] = {
            "routed_mix_predicted": routed,
            "uniform_mix_predicted": rand,
            "attributable_pp": None if routed is None or rand is None
            else (routed - rand) * 100.0,
        }

    # persona 離散度：最差的 agent vs 其餘。同樣要分「乾淨」與「循環」兩種估計。
    def spread_for(ok_key: str, n_key: str) -> dict:
        usable = [a for a in agents if per_agent[a][n_key] > 0]
        if not usable:
            return {"worst_agent": None}
        worst = min(usable, key=lambda a: per_agent[a][ok_key] / per_agent[a][n_key])
        w = per_agent[worst]
        rest_ok = sum(per_agent[a][ok_key] for a in usable if a != worst)
        rest_n = sum(per_agent[a][n_key] for a in usable if a != worst)
        return {
            "worst_agent": worst,
            "worst": f"{w[ok_key]}/{w[n_key]}",
            "worst_rate": w[ok_key] / w[n_key],
            "rest": f"{rest_ok}/{rest_n}",
            "rest_rate": rest_ok / rest_n if rest_n else None,
            "fisher_two_sided_p": fisher_exact_two_sided(
                w[ok_key], w[n_key] - w[ok_key], rest_ok, rest_n - rest_ok),
        }

    spread = {
        "off_only": spread_for("off_ok", "off_n"),
        "pooled_CIRCULAR": spread_for("pooled_ok", "pooled_n"),
    }

    off_delivered = sum(1 for r in off_rows if r.get("meets_demand"))
    on_draft_ok = sum(1 for r in on_rows if r.get("initial_meets_demand"))
    observed = {
        "off_measured": len(off_rows),
        "off_correct_delivery_rate": off_delivered / len(off_rows) if off_rows else None,
        "on_measured": len(on_rows),
        "on_initial_draft_rate": on_draft_ok / len(on_rows) if on_rows else None,
        "observed_gap_pp": None if not off_rows or not on_rows
        else (on_draft_ok / len(on_rows) - off_delivered / len(off_rows)) * 100.0,
    }

    out = {
        "per_agent": {a: per_agent[a] for a in agents},
        "on_routing_share": on_share,
        "on_routing_total": on_total,
        "mix_effect": mix_effect,
        "persona_spread": spread,
        "observed": observed,
    }

    if off5_dir is not None:
        # 前瞻性樣本：OFF5 的每一通 gen 都是 rng.choice，均勻抽樣。
        calls_path = off5_dir / "calls.jsonl"
        tally: dict[str, int] = collections.Counter()
        if calls_path.exists():
            for line in calls_path.open(encoding="utf-8"):
                if not line.strip():
                    continue
                c = json.loads(line)
                if (c.get("meta") or {}).get("arm") == "OFF5" and c.get("role") == "gen":
                    tally[c["agent_id"]] += 1
        out["off5_draw_tally"] = dict(sorted(tally.items()))
        out["off5_draws_total"] = sum(tally.values())
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--on", required=True, type=Path)
    ap.add_argument("--off", required=True, type=Path)
    ap.add_argument("--off5", type=Path, default=None)
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args()

    res = collect(args.on, args.off, args.off5)

    print("== 逐 agent 單稿品質（隱藏測資）==")
    print(f"{'agent':10s} {'OFF 隨機 1-shot':>16s} {'ON 信譽初稿':>14s} "
          f"{'pooled':>12s} {'pooled 95%CI':>18s}")
    for a, s in res["per_agent"].items():
        off = f"{s['off_ok']}/{s['off_n']}" + (f" {s['off_rate']:.0%}" if s["off_n"] else "")
        on = f"{s['on_ok']}/{s['on_n']}" + (f" {s['on_ok']/s['on_n']:.0%}" if s["on_n"] else "")
        pooled = f"{s['pooled_ok']}/{s['pooled_n']} {s['pooled_rate']:.0%}"
        lo, hi = s["pooled_ci95"]
        print(f"{a:10s} {off:>16s} {on:>14s} {pooled:>12s} {f'[{lo:.2f},{hi:.2f}]':>18s}")

    o = res["observed"]
    print(f"\n觀測：OFF 交付 {o['off_correct_delivery_rate']:.4f} (n={o['off_measured']})、"
          f"ON 初稿 {o['on_initial_draft_rate']:.4f} (n={o['on_measured']})、"
          f"落差 {o['observed_gap_pp']:+.2f}pp")

    print("\n== 路由份額 ==")
    print(f"ON（信譽）：{res['on_routing_share']}  總計 {res['on_routing_total']}")

    print("\n== 混合效應：路由政策最多能解釋多少落差 ==")
    print("  ⚠ 歸因只看 off_only；pooled 是循環估計（含被解釋的 ON 成績），僅供診斷")
    for label, m in res["mix_effect"].items():
        print(f"  用 {label:8s} 品質估計："
              f"信譽份額預期 {m['routed_mix_predicted']:.4f}、"
              f"均勻份額預期 {m['uniform_mix_predicted']:.4f} ⇒ "
              f"可歸因於路由 {m['attributable_pp']:+.2f}pp")

    print("\n== persona 品質離散度（選擇機制有沒有東西可選）==")
    for label, s in res["persona_spread"].items():
        if not s.get("worst_agent"):
            continue
        print(f"  [{label}] 最差 {s['worst_agent']}: {s['worst']} ({s['worst_rate']:.0%}) vs "
              f"其餘 {s['rest']} ({s['rest_rate']:.0%})  "
              f"Fisher 雙尾 p={s['fisher_two_sided_p']:.4f}")

    if "off5_draw_tally" in res:
        print(f"\n== OFF5 均勻抽籤累積（前瞻性推翻條件用）==\n  "
              f"{res['off5_draw_tally']}  總計 {res['off5_draws_total']}")

    if args.json_out:
        args.json_out.write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print(f"\nJSON ⇒ {args.json_out}")


if __name__ == "__main__":
    main()
