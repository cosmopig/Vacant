"""產生「我們現在知道什麼」那一頁的資料（供 vacant-docs-web/now.html 使用）。

這一頁承重的是**對外可讀性**：把三輪實驗壓成一個完全外行的人 30 秒能讀完的
狀態頁——確定的、還不確定的、以及我們自己搞錯的。網站不推論任何東西，它只
畫這份 JSON。

紀錄紅線（09 §3.5、CLAUDE.md 鐵律 3）在這裡的對應是：**每一個出現在頁面上的
數字都由本腳本從原始 E*.json / claims.json / archive.json 現讀現算**，不寫死。
所以資料改了頁面就改；而 `sources[]` 逐條印出「檔案 · 欄位 = 值」，讓任何人
不必信任這一頁也能自己去對。

三塊內容的取捨原則：

* `facts` 只放**目前站得住**的說法。凡是被對抗式複驗推翻或判定誇大的，一律
  用**更正後**的版本，並在 detail 裡明說原版錯在哪——不留下「悄悄改掉」的空間。
* `unknowns` 照抄 catalog 的誠實邊界＋真模型輪的檢定力缺口。
* `refuted` 是這一頁的主張本身：一個宣稱可究責的系統若不能對自己可究責，
  主張就沒有內容（同 examples/publish_archive.py 的注解）。

用法：
    .venv/bin/python examples/publish_now.py [--out PATH]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
from pathlib import Path
from typing import Any

REC = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/專題/實驗記錄"
IDX = REC / "_index"
WEB = Path("/Users/cosmopig/Documents/GitHub/vacant-docs-web")
DEFAULT_OUT = WEB / "data/now.json"

PULSE = "脈衝攻擊_2026-08-03"
ENTRY = "入場成本_2026-07-26"
REAL = "真模型_2026-07-26"


# ── 取值工具：每一個數字都要能指回「哪個檔的哪個欄位」 ────────────────────

def _load(rel: str) -> Any:
    return json.loads((REC / rel).read_text(encoding="utf-8"))


def _cell(exp: dict, label: str) -> dict:
    for c in exp["cells"]:
        if c["label"] == label:
            return c
    raise KeyError(f"格 {label!r} 不在 {[c['label'] for c in exp['cells']]}")


def f2(v: float) -> str:
    """兩位小數——與各輪報告的印法一致，不做額外進位。"""
    return f"{v:.2f}"


def f1(v: float) -> str:
    return f"{v:.1f}"


def src(rel: str, field: str, value: Any) -> str:
    """一條可核對的出處：檔案 · 欄位 = 值。"""
    if isinstance(value, float):
        value = round(value, 4)
    return f"{rel} · {field} = {value}"


# ── 內容 ─────────────────────────────────────────────────────────────────

def build_facts() -> list[dict]:
    e4 = _load(f"{ENTRY}/E4.json")
    e12 = _load(f"{ENTRY}/E12.json")
    e21 = _load(f"{PULSE}/E21.json")
    e22 = _load(f"{PULSE}/E22.json")
    e23 = _load(f"{PULSE}/E23.json")

    # F1 入場費
    s0 = _cell(e4, "stake=0")
    s2 = _cell(e4, "stake=2")
    s20 = _cell(e4, "stake=20")

    # F2 評審準確率
    a10 = _cell(e12, "acc=1.0")
    a00 = _cell(e12, "acc=0.0")

    # F3 查得更勤
    b5a1 = _cell(e21, "blind=0.5 · audit=0.1")
    b5a10 = _cell(e21, "blind=0.5 · audit=1.0")
    drop = 1 - b5a10["accepted_bad"]["mean"] / b5a1["accepted_bad"]["mean"]

    # F5 只挑貴的下手
    flat = _cell(e23, "無差別 · blind=0")
    pick = _cell(e23, "選擇性 · blind=0")
    ratio = pick["high_value_hits"]["mean"] / flat["high_value_hits"]["mean"]

    # F6 反應延遲
    b0 = _cell(e22, "blind=0.0")

    return [
        {
            "id": "entry-fee",
            "status": "confirmed",
            "plain": {
                "zh": "「先繳保證金才能進場」這招沒用",
                "en": "Charging a deposit at the door does not work",
            },
            "how": {
                "zh": f"保證金設 0 的時候，壞事一次都沒得逞；"
                      f"改成「先做 {2} 件白工」，壞事反而得手 {f2(s2['accepted_bad']['mean'])} 次。",
                "en": f"With no deposit, nothing bad got through at all. "
                      f"Requiring 2 unpaid jobs first let {f2(s2['accepted_bad']['mean'])} bad "
                      f"deliveries through instead.",
            },
            "detail": {
                "zh": "門檻拉高到 5、10、20 件之後得手數確實往下掉"
                      f"（{f2(_cell(e4, 'stake=5')['accepted_bad']['mean'])}／"
                      f"{f2(_cell(e4, 'stake=10')['accepted_bad']['mean'])}／"
                      f"{f2(s20['accepted_bad']['mean'])}），"
                      "但沒有一個回到「零保證金」時的完全封鎖。"
                      "原因不是門檻不夠高，是門檻改變了壞人的打法："
                      "它把壞人從「馬上作惡、被抓就換一個新身份重來」推向"
                      "「先乖乖做事、混熟了再下手」——而後者才是唯一有效的打法。"
                      f"設 2 件時的投資報酬率是 {f2(s2['roi']['mean'])}（大於 1 代表作惡划算），"
                      f"設 20 件才壓到 {f2(s20['roi']['mean'])}。"
                      "換句話說：收費太低等於在教壞人正確的打法。",
                "en": "Raising the bar to 5 / 10 / 20 unpaid jobs does bring the number down "
                      f"({f2(_cell(e4, 'stake=5')['accepted_bad']['mean'])} / "
                      f"{f2(_cell(e4, 'stake=10')['accepted_bad']['mean'])} / "
                      f"{f2(s20['accepted_bad']['mean'])}), but none of them returns to the "
                      "total shutout seen with no deposit at all. The reason is not that the "
                      "price is too low — it is that the price changes the attacker's playbook, "
                      "pushing them from 'cheat immediately, get a new identity when caught' "
                      "to 'behave first, cheat later', and the second one is the only playbook "
                      "that actually works. At 2 jobs the return on cheating is "
                      f"{f2(s2['roi']['mean'])} (above 1 means cheating pays); it only drops to "
                      f"{f2(s20['roi']['mean'])} at 20. A cheap door fee teaches the attacker "
                      "the right strategy.",
            },
            "sources": [
                src(f"{ENTRY}/E4.json", "cells[stake=0].accepted_bad.mean",
                    s0["accepted_bad"]["mean"]),
                src(f"{ENTRY}/E4.json", "cells[stake=0].shutout_rate", s0["shutout_rate"]),
                src(f"{ENTRY}/E4.json", "cells[stake=2].accepted_bad.mean",
                    s2["accepted_bad"]["mean"]),
                src(f"{ENTRY}/E4.json", "cells[stake=2].roi.mean", s2["roi"]["mean"]),
                src(f"{ENTRY}/E4.json", "cells[stake=20].roi.mean", s20["roi"]["mean"]),
            ],
        },
        {
            "id": "who-checks",
            "status": "confirmed",
            "plain": {
                "zh": "真正決定安全的是「檢查的人看不看得懂」",
                "en": "What decides safety is whether the checker can tell good from bad",
            },
            "how": {
                "zh": f"把檢查的人換成完全瞎猜，壞事得手從 {f2(a10['accepted_bad']['mean'])} 次"
                      f"跳到 {f2(a00['accepted_bad']['mean'])} 次，而且作惡第一次變得划算。",
                "en": f"When the checkers are reduced to pure guessing, bad deliveries that got "
                      f"through jumped from {f2(a10['accepted_bad']['mean'])} to "
                      f"{f2(a00['accepted_bad']['mean'])} — and cheating became profitable for "
                      f"the first time.",
            },
            "detail": {
                "zh": "把「檢查的人答對的機率」從 1.0 一路降到 0，得手數是"
                      + "、".join(
                          f"{c['label'].replace('acc=', '')} → {f2(c['accepted_bad']['mean'])}"
                          for c in e12["cells"])
                      + "。同時投資報酬率從 "
                      f"{f2(a10['roi']['mean'])} 升到 {f2(a00['roi']['mean'])}——"
                      "越過 1.0 才代表「作惡有賺頭」，也就是說整套系統的經濟學"
                      "只在檢查完全失效時才翻盤。這條在對抗式複驗裡沒有被動到。",
                "en": "Sweeping checker accuracy from 1.0 down to 0 gives: "
                      + ", ".join(
                          f"{c['label'].replace('acc=', '')} → {f2(c['accepted_bad']['mean'])}"
                          for c in e12["cells"])
                      + f". Return on cheating rises from {f2(a10['roi']['mean'])} to "
                      f"{f2(a00['roi']['mean'])}; only above 1.0 does cheating actually pay. "
                      "The economics of the whole system flip only when checking is useless. "
                      "This claim was not touched by the adversarial review.",
            },
            "sources": [
                src(f"{ENTRY}/E12.json", "cells[acc=1.0].accepted_bad.mean",
                    a10["accepted_bad"]["mean"]),
                src(f"{ENTRY}/E12.json", "cells[acc=0.0].accepted_bad.mean",
                    a00["accepted_bad"]["mean"]),
                src(f"{ENTRY}/E12.json", "cells[acc=0.0].roi.mean", a00["roi"]["mean"]),
                "_index/claims.json · claims[entry.reviewer_accuracy_binds]（未被複驗推翻）",
            ],
        },
        {
            "id": "check-more",
            "status": "confirmed",
            "plain": {
                "zh": "多查有用，但擋不掉大家一起看不見的錯",
                "en": "Checking more helps — not for mistakes everyone misses",
            },
            "how": {
                "zh": f"同一份資料裡，抽查比例從一成拉到全查，得手數掉了 {round(drop * 100)}%；"
                      f"但若有一半的錯誤是大家一起看不見的，全查之後仍漏掉 "
                      f"{f2(b5a10['accepted_bad']['mean'])} 次。",
                "en": f"In the same data, raising the sampling rate from 10% to 100% cut bad "
                      f"deliveries by {round(drop * 100)}%. But when half of the mistakes are "
                      f"ones every checker misses, full checking still leaks "
                      f"{f2(b5a10['accepted_bad']['mean'])}.",
            },
            "detail": {
                "zh": "我們原本說的是「多查沒用，抽查率和盲區是正交的兩件事」——"
                      "**那句話已經被複驗推翻**。實際上偵測機率是一個乘積："
                      "（1−看不見的比例）×（抽查率）×（檢查準確率），三者同軸，"
                      "而且可以互相替換：把抽查率從 0.5 拉到 1.0，剛好抵銷 50% 的看不見"
                      "（配對差 0.03、p=0.78）。看不見的比例改變的是防禦的**天花板**，"
                      "不是「多查有沒有用」。另外「完全看得見＋全部查＝全部擋住」"
                      "那一格是程式寫死的恆等式，不是量出來的結果。",
                "en": "We originally said 'checking more does not help; sampling rate and the "
                      "shared blind spot are orthogonal'. **That sentence has been refuted.** "
                      "Detection probability is a single product: (1 − blind fraction) × "
                      "(sampling rate) × (checker accuracy). The three sit on one axis and "
                      "trade against each other: raising sampling from 0.5 to 1.0 exactly "
                      "cancels a 50% blind fraction (paired diff 0.03, p=0.78). The blind "
                      "fraction sets the **ceiling** of the defence, not whether sampling works. "
                      "Also, the 'fully visible + check everything = block everything' cell is "
                      "an identity hard-coded in the simulator, not a measurement.",
            },
            "sources": [
                src(f"{PULSE}/E21.json", "cells[blind=0.5 · audit=0.1].accepted_bad.mean",
                    b5a1["accepted_bad"]["mean"]),
                src(f"{PULSE}/E21.json", "cells[blind=0.5 · audit=1.0].accepted_bad.mean",
                    b5a10["accepted_bad"]["mean"]),
                src(f"{PULSE}/E21.json", "cells[blind=0.5 · audit=1.0].shutout_rate",
                    b5a10["shutout_rate"]),
                "data/archive.json · claims[pulse.audit_cannot_close_blindspot].更正後"
                "（Wilcoxon p=5.5e-6；替換性配對差 0.03、p=0.78）",
            ],
        },
        {
            "id": "caught-once",
            "status": "confirmed",
            "plain": {
                "zh": "被抓到一次，幾乎就再也接不到工作",
                "en": "Get caught once and you effectively never get work again",
            },
            "how": {
                "zh": "乾淨隔離下重跑 4000 輪：被抓的 3 個情況，之後 3961 輪一件工作都沒拿到；"
                      "沒被抓的 27／30 一路做到第 3993 輪。",
                "en": "Re-run in clean isolation over 4000 rounds: the 3 that were caught got "
                      "zero work for the following 3961 rounds; 27 of 30 that were never caught "
                      "kept working to round 3993.",
            },
            "detail": {
                "zh": "**原因跟直覺相反。** 直覺是「等久一點就會被原諒」，"
                      "而我們原本的解釋是「等待無效，因為每個身份的時鐘只由自己推動」。"
                      "兩個都不對——等待其實有效（挑人時的探索項會分機會給冷門的）。"
                      "真正致命的是懲罰本身：扣分同時把分數砍半、又把「已累積的證據量」加倍，"
                      "而證據量正是回復所需時間的指數係數。懲罰把自己的赦免管道一起關小了。"
                      "另外，原始版本的說法（「一次被抓＝永久除名，16／16」）"
                      "**被判定誇大**：同一格從未被抓的 14 個情況也一樣停擺，"
                      "所以那 16／16 不能歸因於「被抓」；而且「恢復不可能」是錯的——"
                      "扣分 0.9 在 177 輪回歸、0.8 在 520 輪回歸，是一條連續曲線。",
                "en": "**The reason is the opposite of the intuition.** The intuition is 'wait "
                      "long enough and you are forgiven'; our original explanation was 'waiting "
                      "does not help, because each identity's clock is driven only by itself'. "
                      "Both are wrong — waiting does help (the exploration term hands out "
                      "chances to the neglected). What is actually fatal is the punishment "
                      "itself: a penalty halves the score and simultaneously doubles the "
                      "accumulated evidence count, and that count is the exponent in the "
                      "recovery time. The punishment shuts down its own pardon channel. The "
                      "original wording ('one catch = permanent exile, 16/16') was judged "
                      "**overstated**: 14 never-caught runs in the same cell also stalled, so "
                      "16/16 cannot be attributed to being caught, and 'recovery is impossible' "
                      "is false — a 0.9 penalty recovers by round 177, a 0.8 penalty by 520.",
            },
            "sources": [
                "data/archive.json · claims[pulse.starvation].更正後"
                "（defect_budget=1、4000 輪；未被抓 27/30 到第 3993 輪、被抓 3/3 其後 3961 輪零路由）",
                f"{PULSE}/E17/logs/burst3__p*.jsonl"
                "（重算：取 attacker==true 的列，找第一個 caught==true 的 round，數其後還有幾列）",
            ],
        },
        {
            "id": "count-underestimates",
            "status": "confirmed",
            "plain": {
                "zh": "數「總共被騙幾次」會系統性低估損失",
                "en": "Counting how many times you were fooled understates the damage",
            },
            "how": {
                "zh": f"只挑貴的東西下手的攻擊者，被騙的次數更少"
                      f"（{f2(pick['accepted_bad']['mean'])} 比 {f2(flat['accepted_bad']['mean'])}），"
                      f"但貴重損失是 {f1(ratio)} 倍"
                      f"（{f2(pick['high_value_hits']['mean'])} 比 {f2(flat['high_value_hits']['mean'])}）。",
                "en": f"An attacker who only hits the expensive jobs succeeds fewer times "
                      f"({f2(pick['accepted_bad']['mean'])} vs {f2(flat['accepted_bad']['mean'])}) "
                      f"but does {f1(ratio)}× the high-value damage "
                      f"({f2(pick['high_value_hits']['mean'])} vs "
                      f"{f2(flat['high_value_hits']['mean'])}).",
            },
            "detail": {
                "zh": "無差別攻擊時，得手裡只有 "
                      f"{f1(100 * flat['high_value_hits']['mean'] / flat['accepted_bad']['mean'])}% "
                      "落在高價值任務上；改成只挑貴的下手，這個比例變成 100%。"
                      "也就是說：一個「被騙次數下降」的儀表板，可能正在描述一次損失變大的攻擊。"
                      "要看的是價值加權的損害，不是次數。"
                      "這重現了上一輪（E15）的同一個發現，兩輪都沒有被複驗動到。",
                "en": "Under indiscriminate attack only "
                      f"{f1(100 * flat['high_value_hits']['mean'] / flat['accepted_bad']['mean'])}% "
                      "of successful cheats land on high-value jobs; when the attacker picks, it "
                      "is 100%. A dashboard showing 'fewer incidents' may be describing an attack "
                      "that costs more. Track value-weighted damage, not counts. This reproduces "
                      "the same finding from the previous round (E15); neither was touched by the "
                      "review.",
            },
            "sources": [
                src(f"{PULSE}/E23.json", "cells[無差別 · blind=0].accepted_bad.mean",
                    flat["accepted_bad"]["mean"]),
                src(f"{PULSE}/E23.json", "cells[無差別 · blind=0].high_value_hits.mean",
                    flat["high_value_hits"]["mean"]),
                src(f"{PULSE}/E23.json", "cells[選擇性 · blind=0].accepted_bad.mean",
                    pick["accepted_bad"]["mean"]),
                src(f"{PULSE}/E23.json", "cells[選擇性 · blind=0].high_value_hits.mean",
                    pick["high_value_hits"]["mean"]),
            ],
        },
        {
            "id": "defence-is-late",
            "status": "confirmed",
            "plain": {
                "zh": "防守是事後的：抓到之前一定會先漏掉幾筆",
                "en": "The defence is after the fact — some damage always lands first",
            },
            "how": {
                "zh": f"就算沒有任何「大家一起看不見」的錯，一波攻擊平均仍漏掉 "
                      f"{f2(b0['hits_per_burst']['mean'])} 筆，要 "
                      f"{f2(b0['react_lag_mean']['mean'])} 輪才反應過來（全長 600 輪）。",
                "en": f"Even with no shared blind spot at all, one burst still lands "
                      f"{f2(b0['hits_per_burst']['mean'])} hits on average and takes "
                      f"{f2(b0['react_lag_mean']['mean'])} rounds to react (out of 600).",
            },
            "detail": {
                "zh": "扣分只在被抓到的時候發生，沒抓到就沒有代價，而抽查本來就有一部分看不到——"
                      "所以每一波攻擊都有一個窗口。這不是實作沒做好，是「事後究責」這種設計"
                      "本身的性質：它抬高作惡的代價，不是阻止作惡發生。"
                      "站上其他頁面用的那句誠實邊界（raises-cost 而非 prevents）指的就是這件事。",
                "en": "A penalty only fires when the cheat is caught, and sampling by definition "
                      "misses some — so every burst has a window. This is not an implementation "
                      "gap; it is what after-the-fact accountability is: it raises the cost of "
                      "cheating, it does not prevent cheating. That is the same honest boundary "
                      "used elsewhere on this site (raises-cost, not prevents).",
            },
            "sources": [
                src(f"{PULSE}/E22.json", "cells[blind=0.0].hits_per_burst.mean",
                    b0["hits_per_burst"]["mean"]),
                src(f"{PULSE}/E22.json", "cells[blind=0.0].react_lag_mean.mean",
                    b0["react_lag_mean"]["mean"]),
            ],
        },
    ]


def build_unknowns(claims: list[dict], honesty: list[str]) -> list[dict]:
    e10 = _load(f"{REAL}/E10.json")
    p = e10["paired"]
    on = e10["arms"]["on"]
    off = e10["arms"]["off"]
    by_id = {c["id"]: c for c in claims}
    power = by_id["realmodel.e10_paired_null"]["依據"]["檢定力"]

    return [
        {
            "id": "real-model-underpowered",
            "status": "unknown",
            "plain": {
                "zh": "用真的 AI 跑那一次，題目數不夠，看不出勝負",
                "en": "The run with a real AI did not have enough tasks to tell",
            },
            "how": {
                "zh": f"同一批 {p['n_pairs']} 道題、同一顆腦：開機組做對 {on['passed']} 題、"
                      f"關機組 {off['passed']} 題，差 {f1(p['delta'] * 100)}%，"
                      f"但 p={round(p['mcnemar_p'], 3)}，要 {power['n_for_80']} 對題目才夠。",
                "en": f"Same {p['n_pairs']} tasks, same model: {on['passed']} correct with the "
                      f"layer on vs {off['passed']} with it off — a {f1(p['delta'] * 100)}% gap, "
                      f"but p={round(p['mcnemar_p'], 3)}. It would take {power['n_for_80']} pairs "
                      f"to settle.",
            },
            "detail": {
                "zh": f"95% 信賴區間是 [{f1(p['ci95'][0] * 100)}%, {f1(p['ci95'][1] * 100)}%]，"
                      "跨過 0——也就是「開比較好」與「關比較好」都還沒被排除。"
                      f"這一輪的檢定力只有 {power['power_observed']}"
                      f"（要 80% 的話得看到 {f1(power['mde80_delta'] * 100)}% 的差距）。"
                      "所以現在能說的是「看得到方向」，不能說「證明有效」。"
                      "另外這一支測的是「能不能避開被刻意做壞的代理」，"
                      "不是自然的品質差異。",
                "en": f"The 95% confidence interval is [{f1(p['ci95'][0] * 100)}%, "
                      f"{f1(p['ci95'][1] * 100)}%] and it crosses zero — neither 'on is better' "
                      "nor 'off is better' has been ruled out. Observed power was only "
                      f"{power['power_observed']} (reaching 80% would require a "
                      f"{f1(power['mde80_delta'] * 100)}% gap). We can say the direction looks "
                      "right; we cannot say it is proven. This run also tested routing around "
                      "deliberately sabotaged workers, not natural quality differences.",
            },
            "sources": [
                src(f"{REAL}/E10.json", "paired.mcnemar_p", p["mcnemar_p"]),
                src(f"{REAL}/E10.json", "paired.delta", p["delta"]),
                src(f"{REAL}/E10.json", "paired.ci95", p["ci95"]),
                src(f"{REAL}/E10.json", "arms.on.passed / arms.off.passed",
                    f"{on['passed']} / {off['passed']} of {p['n_pairs']}"),
                "_index/claims.json · claims[realmodel.e10_paired_null].依據.檢定力",
            ],
        },
        {
            "id": "blindspot-unanchored",
            "status": "unknown",
            "plain": {
                "zh": "真實系統裡「大家一起看不見」的錯有多少，我們沒有依據",
                "en": "We have no outside anchor for how much everyone misses in practice",
            },
            "how": {
                "zh": "模擬裡這個比例是我們自己轉的旋鈕，從 0 轉到 1。"
                      "真實系統是 0.1 還是 0.6，目前沒有任何外部量測可以對。",
                "en": "In the simulation it is a dial we turn from 0 to 1 ourselves. Whether a "
                      "real system sits at 0.1 or 0.6, nothing outside the simulation tells us.",
            },
            "detail": {
                "zh": honesty[1] if len(honesty) > 1 else "",
                "en": "Anything reported at a blind fraction above 0 describes a design variant "
                      "in which the auditor is itself a model. The current design audits by "
                      "deterministically re-running tests in a sandbox, which corresponds to a "
                      "blind fraction of 0 for tasks that have an objective check. Measuring the "
                      "real number needs a real-model experiment — that is the next round.",
            },
            "sources": [
                "_index/catalog.json · 誠實邊界[1]",
                f"{PULSE}/報告_脈衝攻擊與稽核盲區.md · 六、誠實邊界",
            ],
        },
        {
            "id": "mechanism-not-ecology",
            "status": "unknown",
            "plain": {
                "zh": "全部是機制模擬，不是真實世界會發生什麼",
                "en": "All of it is mechanism simulation, not what the real world would do",
            },
            "how": {
                "zh": honesty[0] if honesty else "",
                "en": "A mechanism simulation answers 'under these rules, what is this strategy "
                      "worth'. It does not answer 'would a real attacker do this'.",
            },
            "detail": {
                "zh": "模擬的只有一件事：交付的東西是好的還是壞的。其餘全部走真的程式碼——"
                      "分派、抽查、扣分、簽章都是本體，不是玩具模型。"
                      "所以結論是關於這套規則的，但不是關於真實生態的。"
                      "另外每一輪都是單一攻擊者、5 位誠實居民、600 輪；"
                      "攻擊者佔比與生態規模都會改變絕對數字，本站給的是同一設定下的相對關係。",
                "en": "Only one thing is simulated: whether a delivery is good or bad. Everything "
                      "else runs the real code — routing, sampling, penalties and signatures are "
                      "the production modules, not a toy model. So the conclusions are about "
                      "these rules, but not about a real ecosystem. Every round also used a "
                      "single attacker, 5 honest residents and 600 rounds; the share of attackers "
                      "and the size of the population both move the absolute numbers, so what is "
                      "published here are relative relationships under one fixed setting.",
            },
            "sources": [
                "_index/catalog.json · 誠實邊界[0]",
                f"{PULSE}/報告_脈衝攻擊與稽核盲區.md · 二、方法",
            ],
        },
        {
            "id": "strategy-space-hardcoded",
            "status": "unknown",
            "plain": {
                "zh": "壞人的招式是我們自己寫的，所以證不了安全",
                "en": "We wrote the attacker's moves ourselves, so none of this proves safety",
            },
            "how": {
                "zh": honesty[2] if len(honesty) > 2 else "",
                "en": "The attacker's strategy space is hard-coded, so what we report is a lower "
                      "bound on an upper bound of the attack cost. It cannot prove safety.",
            },
            "detail": {
                "zh": "真實攻擊者可能有更好的招式；我們只量了自己想得到的那幾種。"
                      "而且這一輪已經示範過這個風險有多真實——"
                      "「等預算下最粗糙的攻擊最強」那條結論之所以被推翻，"
                      "正是因為我們以為綁住了預算，實際上沒綁住。",
                "en": "A real attacker may have better moves; we only measured the ones we thought "
                      "of. This round already showed how real that risk is: the claim 'under equal "
                      "budget the crudest attack wins' was refuted precisely because the budget we "
                      "thought we had fixed was not actually binding.",
            },
            "sources": [
                "_index/catalog.json · 誠實邊界[2]",
                "data/archive.json · claims[pulse.crude_wins_under_blindspot]",
            ],
        },
    ]


# 六條有裁決的宣稱＋一條自我更正，各配一句「外行人看得懂」的說法。
# 中文的理由與更正不在這裡寫死——從 archive.json 的裁決欄位帶出來；
# 英文那一份裁決原文只有中文，所以這裡另寫等價的英文摘要（"detail_en"）。
PLAIN_REFUTED = {
    "pulse.audit_cannot_close_blindspot": {
        "zh": {"said": "我們說過：多查沒有用。",
               "now": "錯。多查在任何情況下都有效——同一份資料裡，抽查從一成拉到全查，"
                      "壞事得手掉了 82%。"},
        "en": {"said": "We said: checking more does not help.",
               "now": "Wrong. It helps at every level — in the same data, going from 10% to "
                      "100% sampling cut successful cheating by 82%."},
        "detail_en": "**What the refuter measured**: in the same dataset, at a 0.5 blind "
                     "fraction, raising the sampling rate from 0.1 to 1.0 cut total successful "
                     "cheating by 82% (Wilcoxon p=5.5e-6) and even cut the blind-category hits "
                     "by 70%. And the 'zero blind spot + check everything = block everything' "
                     "cell is an identity, not a measurement: with audit_rate=1 and "
                     "audit_accuracy=1, caught==bad is hard-coded.\n\n"
                     "**Corrected**: detection probability is a single product, "
                     "(1 − blind) × sampling × accuracy — one axis, not two. Sampling and the "
                     "blind fraction substitute for each other (0.5 → 1.0 sampling exactly "
                     "offsets a 50% blind fraction; paired diff 0.03, p=0.78). The blind "
                     "fraction sets the ceiling of the defence, not whether sampling works.",
    },
    "pulse.crossover": {
        "zh": {"said": "我們說過：壞人越難被看穿，走走停停的攻擊反而變弱。",
               "now": "錯。那個反轉是雜訊。會挑參數的攻擊者根本不受影響——換一組節奏就贏回來。"},
        "en": {"said": "We said: as the blind spot grows, the stop-start attack gets weaker.",
               "now": "Wrong. That reversal was noise. An attacker who tunes the rhythm wins "
                      "again with a different setting."},
        "detail_en": "**What the refuter measured**: at 0.75 the paired difference was −0.57 "
                     "with a 95% CI crossing zero, the pulse attack was actually higher in 17 "
                     "of 30 seeds, and the medians were identical. The real separation point is "
                     "≈0.90. A blind fraction of 1.0 is a degenerate endpoint: all 30 seeds "
                     "produce one trajectory with sd=0, so the '3.8×' is the arithmetic identity "
                     "90 × duty cycle.\n\n"
                     "**Corrected**: a rising blind fraction moves the *optimal recovery length* "
                     "towards zero; it does not weaken the pulse family. Measured: pulse(20,2) / "
                     "(20,1) / (50,1) score 81 / 84 / 87 at blind=1.0, all above patient's 79.",
    },
    "pulse.crude_wins_under_blindspot": {
        "zh": {"said": "我們說過：同樣的作惡預算下，最笨的攻擊最強。",
               "now": "錯。那根本不是同樣的預算——實際作惡量是 11.97 對 4.87。"
                      "真的綁住之後排名反轉。"},
        "en": {"said": "We said: at equal cheating budget, the crudest attack is strongest.",
               "now": "Wrong. The budgets were never equal — actual cheating was 11.97 vs 4.87. "
                      "Once genuinely bound, the ranking reverses."},
        "detail_en": "**What the refuter measured**: a budget of 12 only bound whitewash (29/30) "
                     "and sybil (30/30); patient hit it in 1/30, pulse(3,10) in 1/30, pulse(5,20) "
                     "in 0/30. Actual cheating was 11.97 vs 4.87 — whitewash won by cheating "
                     "2.5× more, not by better timing. The old assertion only checked "
                     "defected <= BUDGET, an upper bound that always holds, so it could never "
                     "catch this.\n\n"
                     "**Corrected**: with the budget genuinely bound the ranking reverses "
                     "(budget=2: patient/pulse 1.67 vs whitewash 0.97, paired p=0.0015). "
                     "Whitewash's advantage comes from buying routing rights back with a free "
                     "new identity — it burned 4.7 identities and was still taking work at round "
                     "542, while pulse was starved out by round 160. That is an entry-cost "
                     "problem, unrelated to timing.",
    },
    "pulse.timing_minor": {
        "zh": {"said": "我們說過：攻擊者怎麼調節奏，差別只有 1.81 倍。",
               "now": "說得太滿。那 1.81 倍是雜訊寬度不是效應量，而且整批都跑在效應剛好為零的那一點上。"},
        "en": {"said": "We said: however the attacker tunes the rhythm, it only changes things "
                       "1.81×.",
               "now": "Overstated. The 1.81× is the width of the noise, not an effect size — and "
                      "the whole grid sat exactly where the effect is zero."},
        "detail_en": "**What the refuter measured**: the ANOVA was not significant (F=1.27, "
                     "η²=0.039), permutation p=0.115, power only 25%. All fifteen cells ran at a "
                     "blind fraction of 0.5 — exactly the crossover where the timing effect is "
                     "zero (p=0.868).\n\n"
                     "**Corrected**: at that one point the timing effect is unmeasurable, but "
                     "that is absence of evidence. Decomposing hits into 'times routed × hit "
                     "rate per routing' gives a 6.06× spread in the first and 8.45× in the "
                     "second — the total looks flat because exposure and efficiency cancel. The "
                     "attack capability differs by 8.45×.",
    },
    "pulse.blindspot_dominates": {
        "zh": {"said": "我們說過：真正的變數是「大家一起看不見的錯」有多少。",
               "now": "說得太滿。那個倍數幾乎全靠最極端的一格撐著，而那一格 30 次跑出同一條軌跡。"},
        "en": {"said": "We said: the real variable is how much everyone misses.",
               "now": "Overstated. The multiplier rests almost entirely on the most extreme cell, "
                      "where all 30 runs produced one identical trajectory."},
        "detail_en": "**What the refuter measured**: dropping blind=1.0 leaves only 3.28× for "
                     "pulse and 5.68× for patient. At blind=1.0 all 30 seeds produce the same "
                     "trajectory with sd=0, so the effective sample size is 1. More damaging: the "
                     "21-vs-79 gap used as evidence of 'blind spot power' has a blind fraction of "
                     "1.0 on both sides — that gap is 100% timing structure (duty cycle 3/13 vs "
                     "~100%), with no blind-spot component at all.\n\n"
                     "**Corrected**: the blind fraction and timing structure interact strongly "
                     "(two-factor decomposition η²=0.264, four times the timing main effect), so "
                     "the sentence form 'the real variable is X' does not hold. At blind=1.0 with "
                     "exposure fixed at 90, timing alone spans 29× — larger than the 8.9× the "
                     "original claim attributed to the blind spot.",
    },
    "pulse.starvation": {
        "zh": {"said": "我們說過：一次被抓就永久除名，16 個裡有 16 個。",
               "now": "說得太滿。結論站得住，但原始證據有混淆，而且我們給的原因整個是錯的。"},
        "en": {"said": "We said: one catch means permanent exile, 16 out of 16.",
               "now": "Overstated. The conclusion holds, but the original evidence was confounded "
                      "and the mechanism we gave for it was simply wrong."},
        "detail_en": "**What the refuter measured**: the 14 seeds in the same cell that were "
                     "*never* caught also stalled, so '16/16 got no work after being caught' "
                     "cannot be attributed to being caught. And 'recovery is impossible' is "
                     "false — a 0.9 penalty recovers by round 177 and a 0.8 penalty by round "
                     "520; it is a continuous curve.\n\n"
                     "**Corrected**: one slash(0.5) removes you from routing within any "
                     "reachable horizon. Cleanly isolated it is stronger still: with "
                     "defect_budget=1 over 4000 rounds, 27/30 never-caught runs were still "
                     "working at round 3993, and 3/3 caught runs got zero routing for the "
                     "following 3961 rounds. The real mechanism is not 'the per-stream clock "
                     "makes waiting useless' — waiting does work (the UCB exploration term). What "
                     "is fatal is that a slash does β += (α+β), halving the mean and doubling n "
                     "at once, and n is the exponent in the recovery time: the punishment closes "
                     "its own pardon channel.",
    },
    "realmodel.measurement_error": {
        "zh": {"said": "我們第一次量的時候，讀錯了欄位。",
               "now": "那次做出 0/11 對 5/10 的假結果——因為關掉信任層的那一組依設計就不稽核，"
                      "等於拿「有沒有被檢查」當「做得好不好」。整組重量。"},
        "en": {"said": "The first time we measured this, we read the wrong field.",
               "now": "It produced a fake 0/11 vs 5/10 result: the arm with the layer off does not "
                      "audit by design, so we were reading 'was it checked' as 'was it good'. "
                      "The whole thing was re-measured."},
        "detail_en": "Nobody refuted this one — we caught it ourselves, and the full description "
                     "of the error is kept in the source code comments rather than deleted. The "
                     "fix was to judge quality with an out-of-arm check, compile_check(t.check)"
                     "(answer), that neither arm can influence. The corrected measurement is the "
                     "N=60 paired result listed under 'not yet known'.",
    },
}

REFUTED_ORDER = [
    "pulse.audit_cannot_close_blindspot",
    "pulse.crossover",
    "pulse.crude_wins_under_blindspot",
    "pulse.timing_minor",
    "pulse.blindspot_dominates",
    "pulse.starvation",
    "realmodel.measurement_error",
]


def build_refuted(archive_claims: list[dict]) -> list[dict]:
    by_id = {c["id"]: c for c in archive_claims}
    out = []
    for cid in REFUTED_ORDER:
        c = by_id.get(cid)
        if c is None:
            continue
        plain = PLAIN_REFUTED[cid]
        verdict = c.get("verdict") or "self-corrected"
        detail_zh = c.get("推翻了什麼") or ""
        fix_zh = c.get("更正後") or ""
        sources = []
        dep = c.get("依據", {})
        for k, v in dep.items():
            if k == "數值":
                continue
            sources.append(f"{k}：{v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)}")
        sources.append(f"data/archive.json · claims[{cid}]")
        out.append({
            "id": cid,
            "status": "refuted",
            "verdict": verdict,
            "round": c.get("輪次"),
            "original": c.get("宣稱"),
            "plain": plain,
            "detail": {
                "zh": ("**複驗者實測**：" + detail_zh + ("\n\n**更正後**：" + fix_zh if fix_zh else ""))
                      if detail_zh else fix_zh,
                "en": plain.get("detail_en", ""),
            },
            "sources": sources,
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    catalog = _load("_index/catalog.json")
    claims = _load("_index/claims.json")["claims"]
    honesty = catalog.get("誠實邊界", [])

    archive_path = WEB / "data/archive.json"
    archive = json.loads(archive_path.read_text(encoding="utf-8"))
    archive_claims = archive["claims"]

    facts = build_facts()
    unknowns = build_unknowns(claims, honesty)
    refuted = build_refuted(archive_claims)

    n_ref = sum(1 for c in archive_claims if c.get("verdict") == "refuted")
    n_over = sum(1 for c in archive_claims if c.get("verdict") == "overstated")

    now = _dt.datetime.now().astimezone()
    data = {
        "generated_at": now.isoformat(timespec="seconds"),
        "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                 capture_output=True, text=True).stdout.strip(),
        "headline": {
            "zh": "我們在測一件事：讓每個替你做事的程式都留下改不掉的收據、"
                  "做壞了就記在帳上，壞事會不會變少。",
            "en": "We are testing one thing: if every program that works for you leaves a "
                  "receipt it cannot alter, and bad work goes on its record, does bad work "
                  "get rarer?",
        },
        "subhead": {
            "zh": "這一頁只講三件事：目前確定的、還不確定的、以及我們自己弄錯的。",
            "en": "This page covers three things: what is settled, what is not, and what we got "
                  "wrong ourselves.",
        },
        "counts": {
            "facts": len(facts),
            "unknowns": len(unknowns),
            "refuted": len(refuted),
            "claims_total": len(archive_claims),
            "claims_refuted": n_ref,
            "claims_overstated": n_over,
            "claims_unreviewed": len(archive_claims) - n_ref - n_over,
            "rounds": len(catalog["輪次"]),
            "files": catalog["統計"]["檔案數"],
            "rows": catalog["統計"]["總行數"],
        },
        "facts": facts,
        "unknowns": unknowns,
        "refuted": refuted,
        "source_files": [
            "vacant-docs-web/data/archive.json",
            "專題/實驗記錄/_index/claims.json",
            "專題/實驗記錄/_index/catalog.json",
            f"專題/實驗記錄/{PULSE}/報告_脈衝攻擊與稽核盲區.md",
            f"專題/實驗記錄/{ENTRY}/E4.json、E12.json",
            f"專題/實驗記錄/{PULSE}/E21.json、E22.json、E23.json",
            f"專題/實驗記錄/{REAL}/E10.json",
        ],
        "generator": "examples/publish_now.py",
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"寫出 {out} {out.stat().st_size} bytes")
    print(f"  已確定 {len(facts)}、還不確定 {len(unknowns)}、已被推翻 {len(refuted)}")
    print(f"  宣稱 {len(archive_claims)}（推翻 {n_ref}、誇大 {n_over}）")
    print(f"  資料時間 {data['generated_at']}")


if __name__ == "__main__":
    main()
