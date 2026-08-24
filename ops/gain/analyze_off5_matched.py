"""OFF5 逐 persona 劣勢的**題內配對**分析——round64 的判準工具。

## 為什麼需要這支（`analyze_off5_persona.py` 不夠用的地方）

`analyze_off5_persona.py` 算的是每個 persona 的**邊際**通過率（把它所有候選碼
不分題目合併）。round63 用它量到 `careful-1` 連四次快照單調變差
（Fisher p 0.0349 -> 0.0110 -> 0.0033 -> 0.0009）。但邊際通過率有一個結構性混淆：

`arm_off5` 的抽籤是 `[rng.choice(agents) for _ in range(k)]`（**取後放回**），
所以每個 persona 只出現在**部分**題目上。若 `careful-1` 剛好抽到比較難的題，
它的邊際通過率就會低，**而這跟它自己好不好無關**。11 題、每 persona 6-11 份
的樣本量下，這種抽題運氣完全足以造出 75pp 的假落差。

本工具用 OFF5 的一個結構優勢解掉它：**同一題有 5 份候選碼**，所以可以做
**題內配對**——只看目標 persona 有出現的題，拿它跟**同一批題**裡其他 persona
的候選碼比。題目難度在配對裡被消掉，剩下的才是 persona 自己的貢獻。

## 兩個統計量（都用同一套題內置換做零分佈）

置換方式：**在每一題內部**把 `agent_id` 標籤重新洗牌（候選碼的 ok 值留在原位）。
這保留了每題的難度、也保留了每題的 persona 出現次數，只打斷「persona -> 品質」
的關聯 => 正是需要的零假設。

- `matched_deficit`：目標 persona 在「它有出現的題」上的通過率，減掉**同一批題**
  裡其他候選碼的通過率。搭配置換 p（目標 persona 事先指定，不修正多重比較）。
- `min_fisher_p`：六個 persona 各做一次「它 vs 其餘」的邊際 Fisher，取**最小**的 p。
  這個統計量的置換 p **就是多重比較修正後的 p**——因為零分佈裡也取了同樣的最小值。
  round63 報的 p=0.0009 是「事後選出最差的那個」，沒有修正過。

## 量具雙向驗證：`--selftest`

- 植入正案：`careful-1` 每題都錯、其餘每題都對，且 `careful-1` 散佈在所有題
  => 題內配對劣勢應 = -100pp、置換 p 應打到下限。
- 植入 null 案：**所有 persona 品質相同**，但 `careful-1` 只出現在難題
  （難題全錯、易題全對）=> 邊際 Fisher 會很顯著（那正是混淆），
  但**題內配對劣勢應 = 0pp、置換 p 應不顯著**。
  這一案是專門用來證明本工具真的消掉了難度混淆，不是換個寫法重報同一個數字。

唯讀：只讀 `analyze_off5_persona.py --json-out` 產生的 JSON，不碰 run 目錄、
不重打端點、不重跑 sandbox。

用法：
    python3 ops/gain/analyze_off5_persona.py --run <run> --seed <s> --n <n> \
        --json-out /dev/shm/off5_persona.json
    python3 ops/gain/analyze_off5_matched.py --persona-json /dev/shm/off5_persona.json \
        [--iters 20000] [--json-out /dev/shm/off5_matched.json]
    python3 ops/gain/analyze_off5_matched.py --selftest
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.analyze_routing_mix import fisher_exact_two_sided  # noqa: E402


def _marginal(per_task: dict) -> dict[str, tuple[int, int]]:
    """每個 persona 的 (ok, n) 邊際計數。"""
    acc: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    for cands in per_task.values():
        for c in cands:
            acc[c["agent_id"]][1] += 1
            acc[c["agent_id"]][0] += int(bool(c["ok"]))
    return {a: (v[0], v[1]) for a, v in acc.items()}


def min_fisher_p(per_task: dict) -> tuple[float, str]:
    """六個 persona 各做一次「它 vs 其餘」，回傳最小 p 與對應 persona。"""
    marg = _marginal(per_task)
    tot_ok = sum(v[0] for v in marg.values())
    tot_n = sum(v[1] for v in marg.values())
    best_p, best_a = 1.0, ""
    for a, (ok, n) in sorted(marg.items()):
        p = fisher_exact_two_sided(ok, n - ok, tot_ok - ok, (tot_n - n) - (tot_ok - ok))
        if p < best_p:
            best_p, best_a = p, a
    return best_p, best_a


def matched_deficit(per_task: dict, target: str) -> dict:
    """題內配對：只看 target 有出現的題，比 target vs 同一批題的其他候選碼。"""
    t_ok = t_n = o_ok = o_n = 0
    tasks_used = []
    for tid, cands in per_task.items():
        if not any(c["agent_id"] == target for c in cands):
            continue
        tasks_used.append(tid)
        for c in cands:
            if c["agent_id"] == target:
                t_n += 1
                t_ok += int(bool(c["ok"]))
            else:
                o_n += 1
                o_ok += int(bool(c["ok"]))
    t_rate = t_ok / t_n if t_n else float("nan")
    o_rate = o_ok / o_n if o_n else float("nan")
    return {"target": target, "tasks_matched": len(tasks_used),
            "target_ok": t_ok, "target_n": t_n, "target_rate": t_rate,
            "others_ok": o_ok, "others_n": o_n, "others_rate": o_rate,
            "deficit_pp": (t_rate - o_rate) * 100 if t_n and o_n else float("nan")}


def _permute(per_task: dict, rng: random.Random) -> dict:
    """題內洗牌 agent_id 標籤；ok 值留在原位。"""
    out = {}
    for tid, cands in per_task.items():
        labels = [c["agent_id"] for c in cands]
        rng.shuffle(labels)
        out[tid] = [{"agent_id": lab, "ok": c["ok"]} for lab, c in zip(labels, cands)]
    return out


def analyse(per_task: dict, iters: int, seed: int = 20260824) -> dict:
    obs_minp, worst = min_fisher_p(per_task)
    obs_md = matched_deficit(per_task, worst)
    rng = random.Random(seed)
    ge_minp = 0      # 置換的 min p <= 觀測 min p（更極端）
    le_def = 0       # 置換的配對劣勢 <= 觀測（更極端，劣勢是負數）
    for _ in range(iters):
        perm = _permute(per_task, rng)
        pminp, _pw = min_fisher_p(perm)
        if pminp <= obs_minp + 1e-12:
            ge_minp += 1
        pmd = matched_deficit(perm, worst)["deficit_pp"]
        if pmd <= obs_md["deficit_pp"] + 1e-9:
            le_def += 1
    return {
        "worst_persona": worst,
        "marginal": {a: {"ok": v[0], "n": v[1], "rate": v[0] / v[1]}
                     for a, v in sorted(_marginal(per_task).items())},
        "min_fisher_p_uncorrected": obs_minp,
        "min_fisher_p_corrected": (ge_minp + 1) / (iters + 1),
        "matched": obs_md,
        "matched_perm_p": (le_def + 1) / (iters + 1),
        "iters": iters,
    }


# ── round61 混合效應用 OFF5 品質重算 ────────────────────────────────
def mixture_effect(on_shares: dict[str, int], quality: dict[str, float]) -> dict:
    """信譽路由份額 vs 均勻份額，在**同一組品質估計**下的期望交付率差。

    round61 算過同型的量，但當時只有 OFF 1-shot 的逐 persona 品質可用
    （`careful-1` 只有 n=4）。這裡改用 OFF5 的品質估計（n 較厚、題內配對驗過）。

    **不是循環估計**（round61 的 `pooled_CIRCULAR` 教訓）：品質全部來自 OFF5 臂，
    份額全部來自 ON 臂，兩邊沒有共用資料。被解釋的份額沒有進到品質估計裡。
    """
    agents = sorted(quality)
    tot = sum(on_shares.get(a, 0) for a in agents)
    if not tot:
        raise SystemExit("ON 份額總數為 0 => BROKEN")
    rep = sum(on_shares.get(a, 0) / tot * quality[a] for a in agents)
    uni = sum(quality[a] / len(agents) for a in agents)
    return {"reputation_expected": rep, "uniform_expected": uni,
            "mixture_effect_pp": (rep - uni) * 100,
            "shares": {a: on_shares.get(a, 0) for a in agents},
            "quality": quality, "n_share_calls": tot}


# ── 量具雙向驗證 ──────────────────────────────────────────────────
def _synth_positive() -> dict:
    """植入正案：careful-1 每題都錯、其餘都對，careful-1 散佈在所有題。"""
    others = ["careful-2", "hasty-1", "hasty-2", "plain-1", "plain-2"]
    pt = {}
    for i in range(12):
        cands = [{"agent_id": "careful-1", "ok": False}]
        cands += [{"agent_id": others[(i + j) % 5], "ok": True} for j in range(4)]
        pt[f"T{i}"] = cands
    return pt


def _synth_null_confounded() -> dict:
    """植入 null 案：所有 persona 品質相同，但 careful-1 只出現在難題。

    難題 = 該題所有候選碼都錯；易題 = 都對。careful-1 只被抽到難題。
    => 邊際上 careful-1 = 0%、其餘偏高（假訊號）；題內配對應該 = 0pp。
    """
    others = ["careful-2", "hasty-1", "hasty-2", "plain-1", "plain-2"]
    pt = {}
    for i in range(6):                     # 難題：全錯，careful-1 在場
        cands = [{"agent_id": "careful-1", "ok": False}]
        cands += [{"agent_id": others[(i + j) % 5], "ok": False} for j in range(4)]
        pt[f"H{i}"] = cands
    for i in range(12):                    # 易題：全對，careful-1 不在場
        pt[f"E{i}"] = [{"agent_id": others[(i + j) % 5], "ok": True} for j in range(5)]
    return pt


def selftest(iters: int) -> int:
    fails = 0

    pos = analyse(_synth_positive(), iters)
    ok_pos = (pos["worst_persona"] == "careful-1"
              and abs(pos["matched"]["deficit_pp"] + 100.0) < 1e-9
              and pos["matched_perm_p"] <= 0.001
              and pos["min_fisher_p_corrected"] <= 0.001)
    print(f"[植入正案] worst={pos['worst_persona']} "
          f"配對劣勢={pos['matched']['deficit_pp']:.2f}pp "
          f"配對置換p={pos['matched_perm_p']:.5f} "
          f"修正minFisher p={pos['min_fisher_p_corrected']:.5f} "
          f"=> {'PASS' if ok_pos else 'FAIL'}")
    fails += int(not ok_pos)

    nul = _synth_null_confounded()
    raw_p, raw_worst = min_fisher_p(nul)
    nl = analyse(nul, iters)
    ok_nul = (abs(nl["matched"]["deficit_pp"]) < 1e-9 and nl["matched_perm_p"] > 0.05)
    print(f"[植入null案-難度混淆] 未修正邊際 Fisher p={raw_p:.6f} (worst={raw_worst}) "
          f"<= 這就是混淆造出來的假訊號")
    print(f"[植入null案-難度混淆] 題內配對劣勢={nl['matched']['deficit_pp']:.2f}pp "
          f"配對置換p={nl['matched_perm_p']:.5f} => {'PASS' if ok_nul else 'FAIL'}")
    fails += int(not ok_nul)

    # 混合效應：null 案（品質全相同 => 不論份額多偏斜，效應必須 = 0）
    q_eq = {a: 0.4 for a in ["careful-1", "careful-2", "hasty-1", "hasty-2", "plain-1", "plain-2"]}
    sk = {"careful-1": 50, "plain-1": 1, "careful-2": 1, "hasty-1": 1, "hasty-2": 1, "plain-2": 1}
    me_null = mixture_effect(sk, q_eq)
    ok_mn = abs(me_null["mixture_effect_pp"]) < 1e-9
    # 混合效應：正案（只把份額全給品質 0.0 的那個，其餘 1.0 => 效應 = 0.0 - 5/6 = -83.33pp）
    q_pos = dict(q_eq)
    for a in q_pos:
        q_pos[a] = 1.0
    q_pos["careful-1"] = 0.0
    me_pos = mixture_effect({"careful-1": 60}, q_pos)
    ok_mp = abs(me_pos["mixture_effect_pp"] + 83.3333333) < 1e-4
    print(f"[混合效應 null 案] 品質全同、份額極偏 => {me_null['mixture_effect_pp']:+.2f}pp "
          f"=> {'PASS' if ok_mn else 'FAIL'}")
    print(f"[混合效應 正案] 全給最差(0.0)、其餘 1.0 => {me_pos['mixture_effect_pp']:+.2f}pp "
          f"(應 -83.33) => {'PASS' if ok_mp else 'FAIL'}")
    fails += int(not ok_mn) + int(not ok_mp)

    print("量具雙向驗證：" + ("全案皆過，可用" if not fails else f"{fails} 案不符，不可用"))
    return fails


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona-json", type=pathlib.Path,
                    help="analyze_off5_persona.py --json-out 的輸出")
    ap.add_argument("--iters", type=int, default=20000)
    ap.add_argument("--json-out", type=pathlib.Path, default=None)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--on-shares-run", type=pathlib.Path, default=None,
                    help="從這個 run 的 calls.jsonl 取 ON 臂逐 agent 份額，用 OFF5 品質重算 round61 混合效應")
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(1 if selftest(min(a.iters, 5000)) else 0)

    if not a.persona_json:
        raise SystemExit("要嘛 --selftest，要嘛給 --persona-json")
    raw = json.loads(a.persona_json.read_text(encoding="utf-8"))
    per_task = raw["per_task"]
    if not per_task:
        raise SystemExit("per_task 是空的 => BROKEN，不是 0 個發現")

    res = analyse(per_task, a.iters)
    res["source"] = str(a.persona_json)
    res["tasks_covered"] = len(per_task)
    res["candidates_total"] = sum(len(v) for v in per_task.values())

    print(f"== OFF5 題內配對分析（{res['tasks_covered']} 題 / "
          f"{res['candidates_total']} 份候選碼）==")
    for ag, v in res["marginal"].items():
        print(f"  {ag:<10} 邊際 {v['ok']}/{v['n']} {v['rate']*100:.0f}%")
    m = res["matched"]
    print(f"\n最差（邊際）persona = {res['worst_persona']}")
    print(f"未修正 min Fisher p = {res['min_fisher_p_uncorrected']:.6f}"
          f"   <= round63 報的就是這個數字（事後選最差，沒修正）")
    print(f"多重比較修正後 p     = {res['min_fisher_p_corrected']:.6f}"
          f"   ({res['iters']} 次題內置換)")
    print(f"\n題內配對（只看 {res['worst_persona']} 有出現的 {m['tasks_matched']} 題）：")
    print(f"  {res['worst_persona']:<10} {m['target_ok']}/{m['target_n']} = {m['target_rate']*100:.1f}%")
    print(f"  同批題其他候選 {m['others_ok']}/{m['others_n']} = {m['others_rate']*100:.1f}%")
    print(f"  配對劣勢 = {m['deficit_pp']:+.2f}pp   配對置換 p = {res['matched_perm_p']:.6f}")

    if a.on_shares_run:
        shares: dict[str, int] = collections.Counter()
        for line in (a.on_shares_run / "calls.jsonl").open(encoding="utf-8"):
            if not line.strip():
                continue
            c = json.loads(line)
            if c.get("role") == "gen" and (c.get("meta") or {}).get("arm") == "ON":
                shares[c.get("agent_id")] += 1
        quality = {ag: v["rate"] for ag, v in res["marginal"].items()}
        res["mixture_off5_quality"] = mixture_effect(dict(shares), quality)
        me = res["mixture_off5_quality"]
        print(f"\n== round61 混合效應（改用 OFF5 品質重算，{me['n_share_calls']} 通 ON gen）==")
        for ag in sorted(quality):
            print(f"  {ag:<10} ON份額 {me['shares'][ag]:>2}/{me['n_share_calls']} "
                  f"({me['shares'][ag]/me['n_share_calls']*100:4.1f}%) vs 均勻 16.7%   "
                  f"OFF5品質 {quality[ag]*100:.0f}%")
        print(f"  信譽份額期望交付 {me['reputation_expected']*100:.2f}%  "
              f"均勻份額期望交付 {me['uniform_expected']*100:.2f}%")
        print(f"  ** 混合效應 = {me['mixture_effect_pp']:+.2f}pp **  "
              f"(round61 用 OFF 1-shot 品質算的是 -1.33pp)")

    if a.json_out:
        a.json_out.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nJSON => {a.json_out}")


if __name__ == "__main__":
    main()
