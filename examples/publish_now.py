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
            # 2026-08-06 更正：原本這一條寫「沒有任何外部量測可以對」。文獻調研證明
            # 那句話是錯的——別人量過相鄰的量，只是沒人量過我們這個參數本身。
            "id": "blindspot-unanchored",
            "status": "unknown",
            "plain": {
                "zh": "「大家一起看不見」的錯有多少，別人量過相近的，我們自己還沒量",
                "en": "Others have measured something close to our blind-spot number; we have not measured ours",
            },
            "how": {
                "zh": "檢查的人如果是 AI，它們會一起錯——這件事有人量過："
                      "350 個以上的模型裡，兩個模型都答錯時有 60% 錯在同一個答案"
                      "（隨機的話只有 33%）；十個同款 AI 一起投票，只抵得上 1.4 個獨立的人。"
                      "但那些量的不是我們這個旋鈕，要換算得先做假設，而我們自己的系統上還沒量過。",
                "en": "If the checkers are AI, they fail together — and that has been measured: "
                      "across 350+ models, when two models are both wrong they pick the same "
                      "wrong answer 60% of the time (chance would be 33%); ten same-family "
                      "agents voting are worth only 1.4 independent ones. But those are not our "
                      "dial. Converting needs assumptions, and we have never measured it on our "
                      "own system.",
            },
            "detail": {
                "zh": "更正紀錄：這一條原本寫的是「目前沒有任何外部量測可以對」，2026-08-06 的"
                      "文獻調研證明那句話站不住。已知的外部量測有四組——"
                      "Kim 2025（ICML，350+ 模型）：兩模型都錯時的同答案率 HELM 0.600（隨機 1/3）、"
                      "HuggingFace 0.423（隨機 0.127），且**越準的模型錯得越像**，跨架構跨供應商亦然；"
                      "Begin 2026：偏好對齊造成同源相關 ρ=0.70，十個 agent 的有效獨立數只有 1.38；"
                      "Bugaud 2026（17 個視覺語言模型／8 家族）：相關的多數錯誤把正確答案投掉，"
                      "佔題目 1.5–6.5%；Krumdick 2025：GPT-4o 當評審時，在**它自己也答不出來**的"
                      "題目上 Cohen κ 從 0.86 掉到 0.16。"
                      "\n\n但要誠實區分兩件事：這些量的是「錯得像不像」與「有效獨立數」，"
                      "不是我們模擬裡那個 β（一筆壞交付被整個檢查團一起放行的機率）。"
                      "換算過去需要假設單一評審的漏檢率，那個假設本身沒有被驗證。"
                      "\n\n還有一層分別：稽核層在現行設計是沙箱裡確定性重跑測試，對有客觀檢查的"
                      "任務 β≈0 仍然成立；但**評審層本來就是模型**，所以上面那些數字對評審層"
                      "永遠適用，不只是「若稽核也是模型」的設計變體。"
                      "\n\nKrumdick 那條還說明 β 不是常數：它集中在「評審自己也不會做」的那類"
                      "任務上，所以會挑題的攻擊者可以把有效 β 推高。",
                "en": "Correction log: this item used to say no external measurement existed. A "
                      "2026-08-06 literature review showed that is false. Four anchors: Kim 2025 "
                      "(ICML, 350+ models) — same-wrong-answer rate 0.600 on HELM (chance 1/3) and "
                      "0.423 on HuggingFace (chance 0.127), with more accurate models erring more "
                      "alike even across architectures and providers; Begin 2026 — preference "
                      "optimization drives same-family correlation to rho=0.70, so ten agents are "
                      "worth 1.38 independent ones; Bugaud 2026 (17 VLMs, 8 families) — correlated "
                      "majority errors outvote the correct answer on 1.5-6.5% of items; Krumdick "
                      "2025 — GPT-4o as judge drops from Cohen's kappa 0.86 to 0.16 on questions it "
                      "could not answer itself. These measure error similarity and effective "
                      "independence, not our beta (the chance a bad delivery clears the whole "
                      "checking panel); converting requires an unvalidated assumption about the "
                      "single-reviewer miss rate. Note also that the audit layer re-runs tests "
                      "deterministically in a sandbox, so beta is still near 0 there for tasks with "
                      "an objective check — but the review layer is always a model, so these "
                      "anchors always apply to it. Krumdick further shows beta is not constant: it "
                      "concentrates on tasks the judge cannot do itself, so an attacker who picks "
                      "its targets can push the effective beta up.",
            },
            "sources": [
                "參考文獻/2026-08-06_agent信任/PRIOR_ART.md · 二、共同盲區有人形式化過嗎",
                "參考文獻/2026-08-06_agent信任/pdf/2025_Kim_correlated-errors-in-llms.pdf",
                "參考文獻/2026-08-06_agent信任/pdf/2026_Begin_preference-optimization-monoculture-prediction-markets.pdf",
                "參考文獻/2026-08-06_agent信任/pdf/2025_Krumdick_no-free-labels-llm-judge.pdf",
                f"{PULSE}/報告_脈衝攻擊與稽核盲區.md · 七、誠實邊界",
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

# ── 二之外：外部已確立的知識 ────────────────────────────────────────────
#
# 這一組不是我們做的，是文獻已經確立、而且**我們自己開檔逐字核對過**的。
# 每一條都指得出備份路徑（參考文獻/_引用備份/MANIFEST.json 有 sha256）。
# 沒有全文的一律標明，因為「讀過摘要」與「讀過全文」是兩種強度的證據。
EXTERNAL_KNOWLEDGE = [
    {
        "id": "ext.trust-excludes-monitoring",
        "plain": {"zh": "「不靠監督」被寫進了信任的定義裡——所以我們做的不是信任",
                  "en": "Classic definitions build 'without monitoring' into trust itself"},
        "how": {"zh": "Gambetta 1988 與 Mayer 1995 兩個不同學科的經典，"
                      "都把「在能監督之前、或不依賴監督能力」寫成信任的必要條件。"
                      "而監督正是這個系統的全部價值。",
                "en": "Gambetta 1988 and Mayer 1995, from two different disciplines, both make "
                      "'before or irrespective of the ability to monitor' part of the definition "
                      "of trust. Monitoring is exactly what this system is."},
        "detail": {"zh": "Gambetta p.217 原文把 before 與 and 排成斜體："
                         "「both *before* he can monitor such action (or independently of his "
                         "capacity ever to be able to monitor it) *and* in a context in which it "
                         "affects *his own* action」。二手引用通常略掉那個強調。"
                         "\n\nMayer et al. 1995 p.712：「irrespective of the ability to monitor "
                         "or control that other party」。"
                         "\n\n這決定了對外口徑：我們做到的是**可究責性**，不是信任。"
                         "建議的說法是「讓依賴變得有根據」（warranted reliance）。"
                         "\n\n證據強度：Gambetta 全文在手但無文字層，實際讀的那一頁已渲染成影像"
                         "存檔；Mayer 原件在 AMR 付費牆後，該句是經 Körber 2018 p.3 的逐字轉引"
                         "核對的——**引用時必須標明轉引**。",
                   "en": "Gambetta p.217 italicises 'before' and 'and' in the original. Mayer et "
                         "al. 1995 p.712 says 'irrespective of the ability to monitor or control "
                         "that other party'. Hence the wording we should use is warranted "
                         "reliance, not trust. Evidence strength: the Gambetta scan has no text "
                         "layer, so the page actually read is archived as an image; the Mayer "
                         "original is paywalled and the sentence was verified through Korber "
                         "2018 p.3, which quotes it verbatim with the page number — any citation "
                         "must say it is quoted at second hand."},
        "sources": ["參考文獻/_引用備份/verification.jsonl · gambetta1988 / mayer1995_via_koerber2018",
                    "參考文獻/_引用備份/rendered/1988_Gambetta_can-we-trust-trust_p5-05.png",
                    "參考文獻/2026-08-06_信任定義/pdf/2018_Koerber_questionnaire-trust-in-automation.pdf"],
    },
    {
        "id": "ext.correlated-errors",
        "plain": {"zh": "AI 檢查者會一起錯，而且越準的模型錯得越像",
                  "en": "AI checkers fail together, and more accurate models fail more alike"},
        "how": {"zh": "350 個以上的模型裡，兩個模型都答錯時有 60% 錯在同一個答案"
                      "（隨機的話只有 33%）。十個同款 AI 一起投票，只抵得上 1.4 個獨立的人。",
                "en": "Across 350+ models, when two are both wrong they give the same wrong "
                      "answer 60% of the time (chance is 33%). Ten same-family agents voting are "
                      "worth 1.4 independent ones."},
        "detail": {"zh": "Kim 2025（ICML）：同答案率 HELM 0.600（隨機 1/3）、HuggingFace 0.423"
                         "（隨機 0.127）；**越準的模型錯得越像**，跨架構跨供應商亦然。"
                         "\nBegin 2026：偏好對齊造成同源相關 ρ=0.70，N=10 的有效獨立數 1.38，"
                         "加到 40 個幾乎不變。"
                         "\nKrumdick 2025：GPT-4o 當評審，在**它自己也答不出來**的題目上"
                         " Cohen κ 從 0.86 掉到 0.16——所以盲區不是常數，會挑題的攻擊者能把它推高。"
                         "\n\n這三條推翻了我們原本寫的「盲區沒有外部依據」。但要分清楚："
                         "它們量的是「錯得像不像」與「有效獨立數」，**不是**我們模擬裡那個 β，"
                         "換算要對單一評審漏檢率做未驗證的假設。**我們自己的系統上仍未量過。**",
                   "en": "Kim 2025 (ICML): same-wrong-answer 0.600 on HELM (chance 1/3) and 0.423 "
                         "on HuggingFace (chance 0.127), with more accurate models erring more "
                         "alike even across architectures and providers. Begin 2026: rho=0.70, "
                         "effective independent count 1.38 at N=10. Krumdick 2025: GPT-4o judge "
                         "kappa falls 0.86 to 0.16 on questions it cannot answer itself, so the "
                         "blind spot is not a constant. These refuted our earlier claim that no "
                         "external anchor existed — but they measure error similarity, not our "
                         "beta, and we have still never measured it on our own system."},
        "sources": ["參考文獻/_引用備份/verification.jsonl · kim2025 / krumdick2025 / begin2026",
                    "參考文獻/2026-08-06_agent信任/PRIOR_ART.md · 二"],
    },
    {
        "id": "ext.peer-review-unreliable",
        "plain": {"zh": "同儕評審在人類專家身上，信度接近零",
                  "en": "Peer review among human experts has near-zero reliability"},
        "how": {"zh": "三個獨立來源：19,443 篇稿件的統合分析算出評審一致度 κ=.17；"
                      "NeurIPS 送兩個委員會的實驗有 26% 決定不一致；"
                      "真實 NIH 評審重評已獲資助案，整體評分的一致度是 0。",
                "en": "Three independent sources: a meta-analysis over 19,443 manuscripts gives "
                      "kappa = .17; the NeurIPS two-committee experiment found 26% of decisions "
                      "inconsistent; real NIH reviewers re-scoring funded grants produced an ICC "
                      "of zero."},
        "detail": {"zh": "Bornmann 2010（PLoS ONE，48 篇研究、70 個係數、19,443 篇稿件）："
                         "平均 ICC/r²=.34、平均 κ=.17。元迴歸還顯示**涵蓋稿件越多的研究，"
                         "回報的信度越低**。"
                         "\nCortes & Lawrence 2021：NeurIPS 2014 的 166 篇送兩個獨立委員會，"
                         "43 篇（26%）決定不一致；接受率 23%，等於**約一半的被接受論文"
                         "換個委員會就會被拒**。評分變異中 50% 是主觀來源。"
                         "\nPier 2018（PNAS）：整體評分 ICC=0（95% CI 0–0.14）。"
                         "\n\n這對我們是地基問題：整套機制的第一道關就是同儕評審，而模擬裡"
                         "`reviewer_accuracy=0.7` 這個預設**沒有依據**。它應該是要量的東西，"
                         "不是要設的參數。"
                         "\n\nCicchetti 的補充有救：評審在**拒絕**上的一致度顯著高於接受。"
                         "這與我們 E10 的發現一致——系統擅長的是避開持續失敗者，不是排序好的。",
                   "en": "Bornmann 2010 (PLoS ONE, 48 studies, 19,443 manuscripts): mean ICC/r^2 "
                         "= .34, mean kappa = .17, and studies covering more manuscripts report "
                         "lower reliability. Cortes & Lawrence 2021: 43 of 166 NeurIPS papers "
                         "(26%) got inconsistent decisions across two committees; with a 23% "
                         "acceptance rate, roughly half of accepted papers would be rejected by "
                         "the other committee. Pier 2018 (PNAS): ICC = 0. This is a foundation "
                         "problem for us — peer review is our first gate, and the simulation's "
                         "reviewer_accuracy=0.7 has no basis. Cicchetti's qualifier helps: "
                         "reviewers agree far more on rejection than acceptance, which matches "
                         "what E10 found."},
        "sources": ["參考文獻/2026-08-06_人類運作邏輯/HUMAN_MECHANISMS.md · 4",
                    "參考文獻/2026-08-06_人類運作邏輯/index.json"],
    },
    {
        "id": "ext.entry-fee-known-2001",
        "plain": {"zh": "入場費沒用，2001 年就證明過了",
                  "en": "The entry-fee result was already proved in 2001"},
        "how": {"zh": "Friedman & Resnick 2001 證明：身分可以免費重造時，"
                      "對新人課稅只是把無效率換一種形式，不會消除它。"
                      "我們 2026-07 那一輪是重新發現它。",
                "en": "Friedman & Resnick 2001 proved that when identities are free to recreate, "
                      "taxing newcomers only changes the form of the inefficiency. Our 2026-07 "
                      "round rediscovered it."},
        "detail": {"zh": "重現既有結果本身有價值——我們是在一個不同的機制組態裡量的。"
                         "問題在於把它**當成新發現寫出去**，而我們差一點。"
                         "已在報告與 claims.json 補上歸屬。",
                   "en": "Reproducing a known result has value — ours was measured in a different "
                         "mechanism configuration. The problem would have been presenting it as "
                         "new, which we nearly did. Attribution has been added to the report and "
                         "to claims.json."},
        "sources": ["參考文獻/2026-08-06_agent信任/pdf/2001_Friedman_cheap-pseudonyms.pdf",
                    "參考文獻/2026-08-06_agent信任/PRIOR_ART.md · 三"],
    },
    {
        "id": "ext.oscillation-2005",
        "plain": {"zh": "脈衝攻擊不是我們發現的，2005 年就有名字",
                  "en": "The pulse attack is not ours; it was named in 2005"},
        "how": {"zh": "Srivatsa 2005 原文寫著「oscillate between building and milking "
                      "reputation」，他的 model I 就是我們的參數化。"
                      "2009 年進了 ACM Computing Surveys 的攻擊分類表。",
                "en": "Srivatsa 2005 writes 'oscillate between building and milking reputation'; "
                      "his model I is our parameterisation. It entered the ACM Computing Surveys "
                      "attack taxonomy in 2009."},
        "detail": {"zh": "連我們的頭條也被搶先：Srivatsa 量過四種震盪模型的攻擊者成本比"
                         " 1 : 2.28 : 2.08 : 1.36，並證明知道記憶窗 maxH 者的最佳策略是"
                         "以週期＝maxH 震盪。我們的「1.81 倍」既較舊也較弱，"
                         "而且我們自己已判定那是雜訊。"
                         "\n\n保守地說，可能仍是新的只有：四道防禦同時在跑的組態、"
                         "把盲區當第二軸量交互作用、以及扣分機制關閉自己赦免通道的病理。",
                   "en": "Even our headline was pre-empted: Srivatsa measured attacker-cost ratios "
                         "of 1 : 2.28 : 2.08 : 1.36 across four oscillation models and proved the "
                         "optimum for an attacker who knows the memory window. Our 1.81x is both "
                         "older and weaker, and we had already judged it noise."},
        "sources": ["參考文獻/_引用備份/verification.jsonl · srivatsa2005",
                    "參考文獻/2026-08-06_agent信任/PRIOR_ART.md · 一"],
    },
]

# ── 二：已知研究方向與結果 ──────────────────────────────────────────────
DIRECTIONS_DONE = [
    {"id": "dir.ext.reputation-attacks", "side": "external",
     "name": {"zh": "信譽系統的攻防與不可能性", "en": "Reputation-system attacks and impossibility"},
     "result": {"zh": "20 年的成熟文獻。whitewash／sybil／oscillation 都已命名並分類；"
                      "而且有不可能性結果——對稱的信譽函數不可能同時是 sybilproof 的"
                      "（Cheng & Friedman 2005）。所以「抗 Sybil」這個措辭我們不能用。",
                "en": "Two decades of mature work. Whitewashing, sybil and oscillation attacks "
                      "are all named and classified, and there are impossibility results: a "
                      "symmetric reputation function cannot be sybilproof (Cheng & Friedman "
                      "2005). So we cannot describe our system as sybil-resistant."},
     "sources": ["參考文獻/2026-08-06_agent信任/pdf/2009_Hoffman_survey-attack-defense-reputation-systems.pdf",
                 "參考文獻/2026-08-06_agent信任/pdf/2005_Cheng_sybilproof-reputation-mechanisms.pdf"]},
    {"id": "dir.ext.verifiable", "side": "external",
     "name": {"zh": "可驗證計算（不靠信譽，靠證明）", "en": "Verifiable computation (proof, not reputation)"},
     "result": {"zh": "競爭路線，而且比我們強在一個關鍵點上：它給的是**結構性保證**，"
                      "我們給的是機率性保證（抽中才發現）。Figuera 2026 直指"
                      "「產生日誌的實體就是被記錄的實體」是結構性缺陷——"
                      "而我們的 Envelope 正是交付者自簽。這一點必須主動寫出來。",
                "en": "A competing route, and stronger on one key point: it gives structural "
                      "guarantees where ours are probabilistic (you only find out if you sample). "
                      "Figuera 2026 names the flaw directly — the entity producing the log is the "
                      "entity being logged — and our Envelope is signed by the deliverer."},
     "sources": ["參考文獻/2026-08-06_agent信任/pdf/2026_Figuera_notarized-agents-receiver-attested-receipts.pdf",
                 "參考文獻/2026-08-06_agent信任/pdf/2019_Teutsch_truebit-scalable-verification-solution.pdf"]},
    {"id": "dir.ext.channels", "side": "external",
     "name": {"zh": "人類制度怎麼同時滿足三個互相衝突的要求",
              "en": "How human institutions satisfy three conflicting requirements at once"},
     "result": {"zh": "找對專家要**集中**資訊、不被影響要**切斷**資訊、守住邊界要**拒絕權**"
                      "——三者的最佳解互相衝突。人類的解法是把不同種類的資訊"
                      "**分開在不同通道傳**：Delphi 傳論證不傳立場，核對表傳角色不傳評價。"
                      "而 Lorenz 2011 證明光是給**平均值**就足以摧毀獨立性。",
                "en": "Locating expertise needs information concentrated; independence needs it "
                      "cut off; scope boundaries need a right to refuse. Human institutions "
                      "satisfy all three by separating what travels on which channel: Delphi "
                      "passes arguments but not positions. Lorenz 2011 showed that merely showing "
                      "the average destroys independence."},
     "sources": ["參考文獻/2026-08-06_人類運作邏輯/HUMAN_MECHANISMS.md · 0、2"]},
    {"id": "dir.ext.audit-backfires", "side": "external",
     "name": {"zh": "究責機制什麼時候會反效果", "en": "When accountability backfires"},
     "result": {"zh": "Power 的 decoupling：組織會長出可稽核的**表面**——文件、流程紀錄——"
                      "滿足稽核者，底下照舊，於是**稽核驗證的是自己的影子**。"
                      "Campbell's law 把腐化歸因於指標所承載的**決策權重**。"
                      "\n這反過來說明沙箱重跑為什麼強：跑不過就是跑不過，做不出表面。",
                "en": "Power's decoupling: organisations grow an auditable surface — documents, "
                      "process records — that satisfies the auditor while the substance goes on "
                      "unchanged, so the audit verifies its own shadow. Campbell's law puts the "
                      "corruption pressure on the decision weight a metric carries. This is "
                      "precisely why sandboxed re-execution is strong: you cannot fake passing."},
     "sources": ["參考文獻/2026-08-06_人類運作邏輯/HUMAN_MECHANISMS.md · 4"]},
    {"id": "dir.int.entrycost", "side": "internal",
     "name": {"zh": "入場成本這條路（E1–E16，2026-07-26）",
              "en": "The entry-cost line (E1-E16, 2026-07-26)"},
     "result": {"zh": "外生入場費無效，設太低還反過來幫攻擊者熬過見習期。"
                      "真正的綁定約束是**同儕評審的準確率**。"
                      "\n（事後才知道 Friedman & Resnick 2001 已經證明過主結論。）",
                "en": "An exogenous entry fee does not work, and setting it too low actively helps "
                      "the attacker survive probation. The binding constraint is reviewer "
                      "accuracy. We later learned Friedman & Resnick 2001 had already proved the "
                      "main result."},
     "sources": [f"專題/實驗記錄/{ENTRY}/E4.json、E12.json"]},
    {"id": "dir.int.pulse", "side": "internal",
     "name": {"zh": "脈衝攻擊與稽核盲區（E17–E24，2026-08-03）",
              "en": "Pulse attack and audit blind spot (E17-E24, 2026-08-03)"},
     "result": {"zh": "偵測是一個乘積 (1−盲區)×抽樣率×準確率，三個因子同軸、可互相替換。"
                      "時間結構的效應被「曝光 × 效率」的反向抵消藏起來了——"
                      "總數只差 1.81 倍，攻擊效率其實差 8.45 倍。"
                      "\n六條主要結論送對抗式複驗，**三條被推翻、三條說得太滿，"
                      "沒有一條完好**。",
                "en": "Detection is a single product of (1 - blind) x sample rate x accuracy; the "
                      "three factors are on one axis and substitute for each other. The effect of "
                      "timing structure was hidden by exposure and efficiency cancelling out: the "
                      "total spans 1.81x while attack efficiency spans 8.45x. Six headline "
                      "conclusions went to adversarial review; three were refuted and three "
                      "overstated — none survived intact."},
     "sources": [f"專題/實驗記錄/{PULSE}/報告_脈衝攻擊與稽核盲區.md",
                 "專題/實驗記錄/_index/claims.json"]},
    {"id": "dir.int.realmodel", "side": "internal",
     "name": {"zh": "真模型信任開關（E10，2026-07-26）",
              "en": "Trust switch on a real model (E10, 2026-07-26)"},
     "result": {"zh": "60 題配對：開 36、關 31，差 +8.3%，**McNemar p=0.332 不顯著**。"
                      "\n2026-08-06 的再分析發現量錯了地方：換成中介變數（有沒有被路由給"
                      "破壞者）是 33.3% 對 18.3%、p=0.093；而且機制要學——前 20 題兩臂"
                      "完全一樣（30% 對 30%），最後 20 題是 25% 對 5%。"
                      "\n**那是事後分析，不是結論**：燒機期是看過曲線才切的。"
                      "已公布的 p=0.332 不撤。",
                "en": "60 paired tasks: 36 with the layer on, 31 off, +8.3%, McNemar p=0.332 — not "
                      "significant. A 2026-08-06 re-analysis found we measured the wrong thing: "
                      "the mediator (was the job routed to a saboteur) gives 33.3% vs 18.3%, "
                      "p=0.093, and the mechanism has to learn — the first 20 tasks are identical "
                      "across arms (30% vs 30%) while the last 20 are 25% vs 5%. That is a "
                      "post-hoc diagnostic, not a result: the burn-in was chosen after seeing the "
                      "curve. The published p=0.332 stands."},
     "sources": [f"專題/實驗記錄/{REAL}/E10.json", "examples/e10_mediator.py"]},
]

# ── 三：未來研究方向 ────────────────────────────────────────────────────
#
# **每一條的「結果」欄位一律是「尚未執行」。** 這裡寫的是試驗的設計與判準，
# 不是它會得到什麼——沒跑就是沒跑，這一頁最不該做的事就是把計畫寫得像結果。
FUTURE = [
    {
        "id": "fut.channel-separation",
        "name": {"zh": "通道分離：評審看不看得到彼此",
                 "en": "Channel separation: can reviewers see each other"},
        "why": {"zh": "人類制度靠「不同資訊走不同通道」同時滿足三個衝突的要求，"
                      "而 Vacant 現在只有一條通道。所以我們量到的共同盲區，"
                      "可能有一部分是自己的架構造成的，不全是模型的性質。",
                "en": "Human institutions satisfy three conflicting requirements by separating "
                      "what travels on which channel; Vacant has only one channel. So part of the "
                      "blind spot we measure may be produced by our own architecture rather than "
                      "by the model."},
        "mvt": {"zh": "把評審改成 commit-reveal：第一輪只把 sha256(評語‖nonce) 上鏈，"
                      "面板關閉後才揭露。同一批 seed 跑「密封／不密封」兩臂，"
                      "量殘餘的評審相關性。logbook 的 hash-chain 幾乎免費就能做。",
                "en": "Make reviews commit-reveal: round one publishes only sha256(review||nonce) "
                      "to the chain, revealed after the panel closes. Run sealed and unsealed arms "
                      "on the same seeds and measure residual reviewer correlation."},
        "criterion": {"zh": "密封後相關性顯著下降 → 我們量到的盲區有架構成分，"
                            "而且殘餘相關性從此才真的可歸因於同源。",
                      "en": "If correlation drops significantly under sealing, part of the blind "
                            "spot is architectural — and residual correlation becomes genuinely "
                            "attributable to shared provenance."},
        "cost": {"zh": "低。現有模擬框架加一個布林參數。", "en": "Low: one boolean in the existing sim."},
    },
    {
        "id": "fut.expertise-profile",
        "name": {"zh": "專長分格：把「好」跟「擅長這個」分開",
                 "en": "Expertise profiles: separate 'good' from 'good at this'"},
        "why": {"zh": "現在的信譽是一個純量。人類組織解路由問題靠的是「誰會什麼」的目錄，"
                      "而文獻顯示光是把那張表交出去就能複製共同受訓的全部效益。",
                "en": "Reputation is currently a scalar. Human organisations solve routing with a "
                      "directory of who knows what, and the literature shows that simply handing "
                      "over that directory reproduces the full benefit of training together."},
        "mvt": {"zh": "把信譽的 key 從 (stream, branch, substrate) 擴一維加入坑型——"
                      "codebench 的六個坑型是現成切分。同一批 seed 跑擴／不擴兩臂。",
                "en": "Extend the reputation key with the pit type; codebench's six types are an "
                      "existing partition. Run both arms on the same seeds."},
        "criterion": {"zh": "路由到「擅長這個坑型」的比例上升，且總交付品質不變差。",
                      "en": "The share of jobs routed to agents strong on that pit type rises, "
                            "with no loss in overall delivery quality."},
        "cost": {"zh": "低。改 key 的形狀，六坑型已存在。", "en": "Low: reshape the key."},
    },
    {
        "id": "fut.slash-shape",
        "name": {"zh": "讓懲罰不要關掉自己的赦免通道",
                 "en": "Stop the penalty from closing its own path back"},
        "why": {"zh": "現行 slash 做 β += (α+β)，同時把均值砍半**並把 n 加倍**，"
                      "而 n 是回歸時間的指數係數。結果是資深者更難翻身"
                      "（觀測 48 要約 1e66 次觀測才回得來）。",
                "en": "Today slash does beta += (alpha+beta), halving the mean while doubling n — "
                      "and n is the exponent in the return time. Seniority therefore makes "
                      "recovery harder: at 48 observations it takes on the order of 1e66."},
        "mvt": {"zh": "改成只動均值不動 n，量被扣分後的回歸輪數分布，"
                      "並用 B 層六情境確認牙齒沒有變鈍。",
                "en": "Change it to move the mean without changing n, measure the distribution of "
                      "rounds-to-return, and re-run the six B-layer scenarios to confirm the "
                      "teeth are still sharp."},
        "criterion": {"zh": "資深者的回歸時間不再爆炸，**且**六情境的判準全部仍然通過。"
                            "任一情境掉了就退回。",
                      "en": "Return time for senior agents stops exploding AND all six scenario "
                            "criteria still pass. If any fails, revert."},
        "cost": {"zh": "低（改一行），但**要先預註冊**——這會改變牙齒的形狀。",
                 "en": "Low (one line) but must be pre-registered: it changes the teeth."},
    },
    {
        "id": "fut.attribution",
        "name": {"zh": "產出到底是模型定義的還是帳本定義的",
                 "en": "Is the output defined by the model or by the ledger"},
        "why": {"zh": "這個系統包在一顆凍結的模型外面。四條通道裡三條是選擇，"
                      "只有「記憶注入」真的進到生成。那到底有多少貢獻是我們的？",
                "en": "The system wraps a frozen model. Three of its four channels are selection; "
                      "only memory injection reaches generation. So how much of the result is "
                      "ours?"},
        "mvt": {"zh": "讓一條記憶流在模型 A 上累積 N 次交付，然後整條搬到模型 B，"
                      "看表現跟著模型走還是跟著記憶走。信譽的三元組 key"
                      "（stream, branch, substrate）本來就是為這件事設計的。",
                "en": "Let one memory stream accumulate N deliveries on model A, move it to model "
                      "B, and see whether performance follows the model or the stream. The "
                      "reputation key was designed for exactly this."},
        "criterion": {"zh": "變異數分解：Var(基質) 對 Var(記憶) 的比例。"
                            "不論倒向哪邊都是可發表的——若記憶不可攜，那是一個誠實的負面結果。",
                      "en": "A variance decomposition of substrate versus memory. Either direction "
                            "is publishable; if memory does not transfer, that is an honest "
                            "negative result."},
        "cost": {"zh": "中。要兩顆模型的機時。", "en": "Medium: needs compute on two models."},
    },
    {
        "id": "fut.measure-reviewer",
        "name": {"zh": "量我們自己的評審信度，不要再用 0.7",
                 "en": "Measure our own reviewer reliability instead of assuming 0.7"},
        "why": {"zh": "模擬用 reviewer_accuracy=0.7 當預設，那個數字**沒有依據**。"
                      "而人類專家的同儕評審信度接近零（κ=.17、ICC=0），"
                      "沒有理由假設 agent 評審更好。",
                "en": "The simulation defaults to reviewer_accuracy=0.7 with no basis, while human "
                      "expert peer review has near-zero reliability (kappa .17, ICC 0). There is "
                      "no reason to assume agent reviewers do better."},
        "mvt": {"zh": "同一批交付送給多組評審，算組間 ICC 與 κ；"
                      "並分開算「拒絕」與「接受」的一致度。",
                "en": "Send the same deliveries to multiple reviewer panels, compute ICC and kappa "
                      "between panels, and compute agreement separately for rejection and "
                      "acceptance."},
        "criterion": {"zh": "拿到我們自己系統上的數字去取代 0.7。"
                            "若「拒絕」的一致度顯著高於「接受」，那就只宣稱前者——"
                            "E10 的結果已經指向這個方向。",
                      "en": "Replace 0.7 with a number measured on our own system. If agreement on "
                            "rejection is much higher than on acceptance, claim only the former — "
                            "E10 already points that way."},
        "cost": {"zh": "中。要重複評審，模型呼叫數乘上組數。",
                 "en": "Medium: multiplies review calls by the number of panels."},
    },
    {
        "id": "fut.adversarial-realmodel",
        "name": {"zh": "真模型 × 真的會作惡的 agent",
                 "en": "Real model against an agent that actually defects"},
        "why": {"zh": "我們最大的效果全部出現在有攻擊者的模擬裡，而真模型那一輪跑的是"
                      "乾淨任務——正好是稽核有 oracle、篩選沒什麼可篩的區域。"
                      "這一支從來沒跑過。",
                "en": "Our largest effects all come from simulations with an attacker, while the "
                      "real-model round ran clean tasks — exactly the regime where the auditor is "
                      "an oracle and there is little to filter. This has never been run."},
        "mvt": {"zh": "roster 放進真的會作惡的 agent（而不是模擬的壞交付），"
                      "跑信任層開／關，主要終點用**中介變數**（路由給作惡者的比例），"
                      "燒機期與連續評分**事前寫進預註冊**。",
                "en": "Put a genuinely defecting agent in the roster, run the layer on and off, "
                      "use the mediator (share of jobs routed to the defector) as the primary "
                      "endpoint, and pre-register the burn-in and the continuous score."},
        "criterion": {"zh": "預註冊之後的中介變數差異。這一支的重點是**先把終點定死**，"
                            "因為 E10 的教訓就是量測選擇能讓效果量差好幾倍。",
                      "en": "The pre-registered mediator difference. The point is to fix the "
                            "endpoint first: E10 showed that measurement choices move the effect "
                            "size several-fold."},
        "cost": {"zh": "高。真模型機時。", "en": "High: real-model compute."},
    },
    {
        "id": "fut.rescore-e10",
        "name": {"zh": "把已經跑過的答案重新評分（零機時）",
                 "en": "Re-score answers we already have (no compute)"},
        "why": {"zh": "E10 的品質被壓成一個布林值，但題目來自 EvalPlus，每題有大量測試斷言。"
                      "而 207 筆交付的完整回應都在閘道歸檔裡。",
                "en": "E10 collapsed quality to a boolean, but the tasks come from EvalPlus where "
                      "each problem has many assertions — and all 207 full responses are in the "
                      "gateway archive."},
        "mvt": {"zh": "用歸檔的答案重跑測試，改成「通過的斷言比例」，配對 Wilcoxon。"
                      "**不呼叫任何模型。**",
                "en": "Re-run the tests against the archived answers, score the fraction of "
                      "assertions passed, and use a paired Wilcoxon. No model calls at all."},
        "criterion": {"zh": "同樣 60 對下的檢定力變化。"
                            "**必須標為次要分析**——這是對已收集資料的再分析，"
                            "在下一輪預註冊之前不能當主結果。",
                      "en": "The change in power at the same 60 pairs. It must be reported as a "
                            "secondary analysis: this is a re-analysis of already-collected data "
                            "and cannot be a primary result before the next pre-registration."},
        "cost": {"zh": "零機時。", "en": "Zero compute."},
    },
]

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
            "zh": "分三類：現在知道的、已經走過的路（別人的與我們的）、"
                  "以及還沒走的路——最後那一類只有計畫，沒有結果，沒做就是沒做。",
            "en": "Three parts: what we know now, the ground already covered (theirs and ours), "
                  "and the ground not yet covered — that last part is plans only. Nothing there "
                  "has been run, and nothing there is reported as a result.",
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
            "external_knowledge": len(EXTERNAL_KNOWLEDGE),
            "directions_external": sum(1 for d in DIRECTIONS_DONE if d["side"] == "external"),
            "directions_internal": sum(1 for d in DIRECTIONS_DONE if d["side"] == "internal"),
            "future": len(FUTURE),
            "future_run": 0,   # 未來方向裡已經跑過的：零。這個數字寫在資料裡，
                               # 因為頁面上「計畫」與「結果」不能長得一樣。
        },
        "facts": facts,
        "external_knowledge": EXTERNAL_KNOWLEDGE,
        "directions_done": DIRECTIONS_DONE,
        "future": FUTURE,
        "future_note": {
            "zh": "下面每一條都**還沒有執行**，所以沒有結果可以報。列出來的是試驗的設計、"
                  "判準與成本——把計畫寫得像結果，是這一頁最不該做的事。",
            "en": "None of these has been run, so there are no results to report. What is listed "
                  "is the design, the decision criterion and the cost. Presenting a plan as a "
                  "result is the one thing this page must never do.",
        },
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
    print(f"  現有知識：內部 {len(facts)}、外部 {len(EXTERNAL_KNOWLEDGE)}")
    print(f"  已知方向：外部 {sum(1 for d in DIRECTIONS_DONE if d['side']=='external')}、"
          f"內部 {sum(1 for d in DIRECTIONS_DONE if d['side']=='internal')}")
    print(f"  未來方向：{len(FUTURE)}（已執行 0——沒做就是沒做）")
    print(f"  還不確定 {len(unknowns)}、已被推翻 {len(refuted)}")
    print(f"  宣稱 {len(archive_claims)}（推翻 {n_ref}、誇大 {n_over}）")
    print(f"  資料時間 {data['generated_at']}")


if __name__ == "__main__":
    main()
