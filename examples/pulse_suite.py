"""E17–E24：脈衝攻擊與稽核盲區（2026-08-03）。

## 這一輪要回答什麼

前一輪（E1–E16）的結論是：入場費沒有用、真正的約束是評審準確率。這一輪
往下追兩個問題：

  Q1  脈衝攻擊是怎樣的攻擊？
  Q2  它的具體影響是什麼？

## 脈衝攻擊的定義（可被檢驗的形式）

交替於兩個相位：**放電** burst 筆連續作惡 → **蓄積** recover 筆乾淨交付
→ 重複。它不是「更兇的攻擊」，而是利用防禦的三個時間性質：

  1. 稽核是抽樣的（audit_rate < 1）——有一部分作惡本來就不會被看到
  2. 扣分只在被抓到時發生——沒被抓到就沒有代價
  3. 信譽高的身份會被路由得更頻繁（UCB）——養高信譽等於擴大提領管道

既有三種策略是這個參數空間的特例：recover=0 ≈ whitewash（一直作惡）、
burst=1 且 recover 很大 ≈ 稀疏的 patient。所以這不是「多一種攻擊」，
而是把攻擊的**時間結構**變成一個可掃描的維度。

## 實驗

  E17  放電長度掃描（burst 1→13，recover 固定）
  E18  蓄積長度掃描（recover 0→40，burst 固定）
  E19  等預算對照：所有策略作惡總量鎖在同一個數字，只比時機
  E20  盲區掃描（核心）：blindspot 0→1 × {patient, pulse}
  E21  盲區 × 稽核率：加大抽樣能不能救回來
  E22  反應延遲：一波從第一次作惡到第一次被抓，中間漏掉幾筆
  E23  脈衝 × 選擇性（只打高價值）：複合最壞情況
  E24  攻擊者最佳參數搜尋：(burst, recover) 網格，找對防禦者最壞的一組

## 誠實邊界

  - 這是**機制模擬**，不是生態效果。它回答「在這套規則下，這個策略值多少」，
    不回答「真實攻擊者會不會這樣做」。
  - blindspot 這個參數描述的是「若稽核也是模型」的設計變體。現行設計的
    稽核是 sandbox 確定性重跑單元測試，對**有客觀檢查的任務**而言
    blindspot=0 才是對的。盲區適用於驗收標準本身由模型產生、或任務沒有
    客觀檢查的情況——E20–E23 是對那個變體的條件性結論，不是對現行設計的描述。
  - 攻擊者策略空間仍是我們寫死的；真實攻擊者可能更強。本套件給的是
    攻擊成本上界的下界，證不了安全。
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import time
from pathlib import Path

from vacant.entrycost import SimConfig, simulate

ROUNDS = 600
SEEDS = [f"p{i}" for i in range(30)]     # 每格 30 個 seed


def _agg(cells: list[dict], key: str, label: str, axis: str,
         question: str, note: str = "") -> dict:
    return {"question": question, "axis": axis, "note": note, "cells": cells}


def _cell(label: str, cfgs: list[SimConfig], logdir: Path | None) -> dict:
    """跑同一格的所有 seed，回聚合＋每個 seed 的原始值。"""
    runs = []
    for cfg in cfgs:
        lp = None
        if logdir is not None:
            logdir.mkdir(parents=True, exist_ok=True)
            lp = logdir / f"{label.replace('/', '_').replace('=', '')}__{cfg.seed}.jsonl"
        runs.append(simulate(cfg, log_path=lp))

    def col(k):
        return [r[k] for r in runs if r[k] is not None]

    def stat(k):
        v = col(k)
        if not v:
            return {"mean": None, "sd": None, "min": None, "max": None, "n": 0}
        return {"mean": round(st.mean(v), 4),
                "sd": round(st.pstdev(v), 4) if len(v) > 1 else 0.0,
                "min": min(v), "max": max(v), "n": len(v)}

    return {
        "label": label,
        "n_seeds": len(runs),
        "accepted_bad": stat("accepted_bad"),
        "high_value_hits": stat("high_value_hits"),
        "defected": stat("defected"),
        "caught": stat("caught"),
        "routed_to_attacker": stat("routed_to_attacker"),
        "n_bursts": stat("n_bursts"),
        "hits_per_burst": stat("hits_per_burst"),
        "max_burst_hits": stat("max_burst_hits"),
        "react_lag_mean": stat("react_lag_mean"),
        "bursts_never_caught": stat("bursts_never_caught"),
        "blind_passes": stat("blind_passes"),
        "honest_damage": stat("honest_damage"),
        "roi": stat("roi"),
        # 全數擋下的比例：得手 0 的 seed 佔比。平均值會被離群值帶偏，
        # 「有多少比例的世界裡攻擊者一次都沒得手」才是防禦者關心的量。
        "shutout_rate": round(sum(1 for r in runs if r["accepted_bad"] == 0) / len(runs), 4),
        "config_digest": runs[0]["config_digest"],
    }


def _mk(seed: str, **kw) -> SimConfig:
    base = dict(rounds=ROUNDS, seed=seed)
    base.update(kw)
    return SimConfig(**base)


# ── E17 放電長度 ─────────────────────────────────────────────────────
def e17(out: Path) -> dict:
    cells = [_cell(f"burst={b}",
                   [_mk(s, strategy="pulse", pulse_burst=b, pulse_recover=10,
                        blindspot=0.5) for s in SEEDS],
                   out / "E17" / "logs")
             for b in (1, 2, 3, 5, 8, 13)]
    return _agg(cells, "e17", "burst", "放電長度",
                "一波連續作惡幾筆最划算？",
                "recover 固定 10、盲區固定 0.5（中間值，讓兩種力量都看得到）")


# ── E18 蓄積長度 ─────────────────────────────────────────────────────
def e18(out: Path) -> dict:
    cells = [_cell(f"recover={r}",
                   [_mk(s, strategy="pulse", pulse_burst=3, pulse_recover=r,
                        blindspot=0.5) for s in SEEDS],
                   out / "E18" / "logs")
             for r in (0, 3, 5, 10, 20, 40)]
    return _agg(cells, "e18", "recover", "蓄積長度",
                "兩波之間要養多久？recover=0 就是「一直作惡」的特例。",
                "burst 固定 3、盲區固定 0.5")


# ── E19 等預算對照 ───────────────────────────────────────────────────
def e19(out: Path) -> dict:
    BUDGET = 12
    specs = [("whitewash", dict(strategy="whitewash")),
             ("patient", dict(strategy="patient", build_rounds=10)),
             ("sybil", dict(strategy="sybil")),
             ("pulse(3,10)", dict(strategy="pulse", pulse_burst=3, pulse_recover=10)),
             ("pulse(5,20)", dict(strategy="pulse", pulse_burst=5, pulse_recover=20))]
    cells = [_cell(lab, [_mk(s, defect_budget=BUDGET, blindspot=0.5, **kw) for s in SEEDS],
                   out / "E19" / "logs")
             for lab, kw in specs]
    return _agg(cells, "e19", "strategy", "策略（作惡總量鎖死）",
                f"把作惡總量都鎖在 {BUDGET} 筆，剩下的差異就只剩「時機」。",
                "這格回答的是：脈衝的優勢是不是只是「作惡比較多次」？")


# ── E20 盲區掃描（核心）──────────────────────────────────────────────
def e20(out: Path) -> dict:
    cells = []
    for strat, kw in [("patient", dict(strategy="patient", build_rounds=10)),
                      ("pulse(3,10)", dict(strategy="pulse", pulse_burst=3, pulse_recover=10))]:
        for blind in (0.0, 0.25, 0.5, 0.75, 1.0):
            cells.append(_cell(f"{strat} · blind={blind}",
                               [_mk(s, blindspot=blind, **kw) for s in SEEDS],
                               out / "E20" / "logs"))
    return _agg(cells, "e20", "blindspot × strategy", "同源盲區比例",
                "稽核與評審共享盲區時，脈衝攻擊的威力如何變化？",
                "blindspot＝落在「同源檢查者都看不到」的錯誤比例。"
                "現行設計的稽核是確定性重跑，對應 blindspot=0。")


# ── E21 盲區 × 稽核率 ────────────────────────────────────────────────
def e21(out: Path) -> dict:
    cells = []
    for blind in (0.0, 0.5):
        for rate in (0.1, 0.2, 0.5, 1.0):
            cells.append(_cell(f"blind={blind} · audit={rate}",
                               [_mk(s, strategy="pulse", pulse_burst=3,
                                    pulse_recover=10, blindspot=blind,
                                    audit_rate=rate) for s in SEEDS],
                               out / "E21" / "logs"))
    return _agg(cells, "e21", "blindspot × audit_rate", "盲區 × 稽核率",
                "有盲區的時候，把稽核率拉高救得回來嗎？",
                "若救不回來，代表「多查一點」對這一類失敗無效——"
                "盲區與抽樣率是正交的兩件事。")


# ── E22 反應延遲 ─────────────────────────────────────────────────────
def e22(out: Path) -> dict:
    cells = [_cell(f"blind={b}",
                   [_mk(s, strategy="pulse", pulse_burst=8, pulse_recover=10,
                        blindspot=b, audit_rate=0.2) for s in SEEDS],
                   out / "E22" / "logs")
             for b in (0.0, 0.25, 0.5, 0.75)]
    return _agg(cells, "e22", "blindspot", "反應延遲",
                "一波從第一次作惡到第一次被抓，中間漏掉幾筆？",
                "burst 拉到 8 是為了讓「延遲」有空間顯現。"
                "react_lag_mean 是輪次差；hits_per_burst 是實際漏掉的筆數。")


# ── E23 脈衝 × 選擇性 ────────────────────────────────────────────────
def e23(out: Path) -> dict:
    specs = [("無差別 · blind=0", dict(selective=False, blindspot=0.0)),
             ("無差別 · blind=0.5", dict(selective=False, blindspot=0.5)),
             ("選擇性 · blind=0", dict(selective=True, blindspot=0.0)),
             ("選擇性 · blind=0.5", dict(selective=True, blindspot=0.5))]
    cells = [_cell(lab, [_mk(s, strategy="pulse", pulse_burst=3, pulse_recover=10,
                             high_value_ratio=0.2, **kw) for s in SEEDS],
                   out / "E23" / "logs")
             for lab, kw in specs]
    return _agg(cells, "e23", "selective × blindspot", "選擇性 × 盲區",
                "只打高價值任務的脈衝攻擊，實際造成的損害有多集中？",
                "看 high_value_hits 而不是 accepted_bad——"
                "同樣的得手次數，打在高價值上損害完全不同。")


# ── E24 攻擊者最佳參數 ───────────────────────────────────────────────
def e24(out: Path) -> dict:
    cells = []
    for b in (1, 2, 3, 5, 8):
        for r in (3, 10, 20):
            cells.append(_cell(f"({b},{r})",
                               [_mk(s, strategy="pulse", pulse_burst=b,
                                    pulse_recover=r, blindspot=0.5) for s in SEEDS],
                               out / "E24" / "logs"))
    return _agg(cells, "e24", "(burst, recover)", "攻擊者參數網格",
                "從攻擊者的角度，哪一組 (放電, 蓄積) 最划算？",
                "找的是對防禦者最壞的一組——不是我們希望的，是我們必須知道的。")


EXPS = {"E17": e17, "E18": e18, "E19": e19, "E20": e20,
        "E21": e21, "E22": e22, "E23": e23, "E24": e24}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--no-logs", action="store_true",
                    help="不落逐輪紀錄（只在快速探索時用；正式跑一定要留）")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    names = a.only or list(EXPS)
    summary = {}
    sp = a.out / "summary.json"
    if sp.exists():
        summary = json.loads(sp.read_text())      # 合併而非覆蓋

    for name in names:
        t0 = time.time()
        print(f"── {name} ──", flush=True)
        res = EXPS[name](a.out if not a.no_logs else Path("/dev/null").parent)
        res["elapsed_s"] = round(time.time() - t0, 1)
        res["rounds"] = ROUNDS
        res["n_seeds"] = len(SEEDS)
        (a.out / f"{name}.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        summary[name] = {"question": res["question"], "axis": res["axis"],
                         "elapsed_s": res["elapsed_s"],
                         "cells": [c["label"] for c in res["cells"]]}
        for c in res["cells"]:
            print(f"   {c['label']:<26} 得手 {c['accepted_bad']['mean']:>6}"
                  f"  高價值 {c['high_value_hits']['mean']:>5}"
                  f"  全擋 {c['shutout_rate']:>5}"
                  f"  波次 {c['n_bursts']['mean']:>5}"
                  f"  每波 {c['hits_per_burst']['mean']}", flush=True)
        print(f"   （{res['elapsed_s']}s）", flush=True)

    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.out / "manifest.json").write_text(json.dumps({
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "rounds": ROUNDS, "seeds": SEEDS,
        "note": "脈衝攻擊與稽核盲區。blindspot>0 是「若稽核也是模型」的設計變體，"
                "不是對現行（sandbox 確定性重跑）設計的描述。",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n寫出 {a.out}")


if __name__ == "__main__":
    main()
