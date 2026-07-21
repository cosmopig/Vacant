"""blayer — B 層機制驗收六情境（13 §3；15 §2 畢業軌必要；17 §P4）。

核心紀律（事前寫死）：「每個信任機制真的承重——**拆掉它，數字必須變**」。
每個情境同時跑機制開（on）與機制拆（off，反事實）兩組，on 的判準成立、
且 on/off 數字有差，才算該機制驗收通過；「拆掉數字沒變」＝降級為裝飾、
從一切主張移除（13 §3）。

掃描規格（17 §P4）：惡意比例 0→70% 步進 10%（8 格）、每格 ≥1000 seeds、
bootstrap 95% CI、每情境 ≤30 分、產出 JSONL＋一頁結果。各情境的「惡意比例」
語義與判準逐一定義在下方 SCENARIOS 與各函式 docstring——判準常數全部
寫死在這裡（事後不得依數字回改）。

誠實邊界：六情境是確定性離線模擬（假腦／合成攻擊），驗的是**機制承重**，
不是生態效果——效果宣稱屬 X 系列（C-3 門後）。
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

RATIOS: tuple[float, ...] = tuple(i / 10 for i in range(8))  # 0.0 … 0.7 步進 10%
DEFAULT_N_SEEDS = 1000  # 17 §P4：每格 ≥1000 seeds（測試用小種子數，正式用預設）


@dataclass
class Cell:
    """一格（scenario × ratio）的量測結果。"""
    scenario: str
    ratio: float
    n_seeds: int
    value: float
    ci_lo: float
    ci_hi: float

    def to_json(self) -> dict[str, Any]:
        return {"scenario": self.scenario, "ratio": self.ratio, "n_seeds": self.n_seeds,
                "value": round(self.value, 6), "ci_lo": round(self.ci_lo, 6),
                "ci_hi": round(self.ci_hi, 6)}


@dataclass
class ScenarioReport:
    name: str
    metric: str
    on_cells: list[Cell] = field(default_factory=list)
    off_cells: list[Cell] = field(default_factory=list)
    verdict: bool = False
    detail: str = ""


def _sweep(
    name: str, metric: str, fn: Callable[[float, random.Random, bool], float],
    *, n_seeds: int, base_seed: str,
) -> ScenarioReport:
    """對一個情境跑 on/off × 8 格，bootstrap CI（research.boot_ci 同源）。"""
    from .research import boot_ci
    rep = ScenarioReport(name=name, metric=metric)
    for on in (True, False):
        cells = []
        for ratio in RATIOS:
            vals = [
                fn(ratio, random.Random(f"{base_seed}:{name}:{ratio}:{on}:{i}"), on)
                for i in range(n_seeds)
            ]
            mean = sum(vals) / len(vals)
            lo, hi = boot_ci(vals, lambda s: sum(s) / len(s), n_boot=500,
                             seed=hash((name, ratio, on)) & 0xFFFF)
            cells.append(Cell(name, ratio, n_seeds, mean, lo, hi))
        if on:
            rep.on_cells = cells
        else:
            rep.off_cells = cells
    return rep


def _at(cells: list[Cell], ratio: float) -> Cell:
    return next(c for c in cells if abs(c.ratio - ratio) < 1e-9)


# === ① 簽章歸屬（Sybil 灌票：關驗簽被灌爆、開驗簽全拒）=========================
def _sig_attribution(ratio: float, rng: random.Random, on: bool) -> float:
    """灌 round(10×ratio) 票偽造 review（未公告身份的 Sybil，簽章形式合法）。
    回**被收下的偽造票數**。判準：on 恆＝0；off（拆驗簽鏈）＝灌入數。"""
    from .body import CapabilityCard
    from .envelope import ReviewEnvelope
    from .identity import Identity
    from .registry import Registry, ReviewRejected
    from .reputation import DIMS
    from . import crypto

    reg = Registry()
    target = Identity.generate()
    reg.announce(CapabilityCard(
        vacant_id=target.vacant_id, niches=["code"],
        pub_hex=crypto.pub_to_hex(target.pub)))
    reg.note_head(target.vacant_id, "s" * 64, "main", "h" * 64)
    forged = round(10 * ratio)
    accepted = 0
    for i in range(forged):
        sybil = Identity.generate()  # 未公告 → 驗簽鏈第一關即拒（on 模式）
        env = ReviewEnvelope.create(
            sybil, target_id=target.vacant_id, target_stream_id="s" * 64,
            branch_id="main", target_head="h" * 64, task_id=f"flood{i}",
            substrate="echo", scores={d: 1.0 for d in DIMS}, ts_ms=1)
        if on:
            try:
                reg.record_review(env)
                accepted += 1
            except ReviewRejected:
                pass
        else:
            reg._rep.record_review("s" * 64, "main", "echo", env.scores, weight=1.0)
            accepted += 1
    return float(accepted)


# === ② 同源降權（行為推斷版；承重路徑零 controller_id）=========================
def _same_source(ratio: float, rng: random.Random, on: bool) -> float:
    """克隆團（5 個行為完全同步的 reviewer）＋ 4 個獨立 reviewer 對同一 target
    連審 20 題。惡意比例＝克隆團佔比（ratio≥0.5 才成群，低比例回 0）。
    回**末輪克隆團總實收權重**（穩態，偵測暖機已完成；20 題讓鑑別題 ~12，
    跨過 ≥5 題的偵測門檻）。判準：on ≤0.5（floor 曲線，總貢獻 log 級）；
    off ≥2.0（五克隆 × 高信譽權重，路由可被劫持）。"""
    from .body import CapabilityCard
    from .envelope import ReviewEnvelope
    from .identity import Identity
    from .registry import Registry, ReviewRejected
    from .reputation import DIMS, SAME_SIGNAL_FLOOR
    from . import crypto

    if ratio < 0.5:
        return 0.0
    reg = Registry()
    target = Identity.generate()
    reg.announce(CapabilityCard(
        vacant_id=target.vacant_id, niches=["code"],
        pub_hex=crypto.pub_to_hex(target.pub)))

    def _mk(vid: Identity) -> None:
        reg.announce(CapabilityCard(
            vacant_id=vid.vacant_id, niches=[],
            pub_hex=crypto.pub_to_hex(vid.pub)))
        # 給 reviewer 高信譽（讓 weight≈0.6：score 0.9 × obs 飽和）——拆機制時
        # 劫持效果才顯現；on 模式下行為降權照樣壓回地板。
        reg.note_head(vid.vacant_id, f"st-{vid.vacant_id[:8]}", "main", "h" * 64)
        for _ in range(10):
            reg._rep.record_review(f"st-{vid.vacant_id[:8]}", "main", "echo",
                                   {d: 1.0 for d in DIMS}, weight=1.0)

    clones = [Identity.generate() for _ in range(5)]
    honest = [Identity.generate() for _ in range(4)]
    for r in clones + honest:
        _mk(r)
    last_round_group = 0.0  # 量穩態：第 20 輪克隆團總實收權重（偵測暖機已完成）
    for t in range(20):
        reg.note_head(target.vacant_id, "s" * 64, "main", f"{t}{'h' * 63}")
        clone_vote = rng.random() < 0.8  # 克隆團同進同退（同一個亂數流）
        for r in clones:
            v = clone_vote
            env = ReviewEnvelope.create(
                r, target_id=target.vacant_id, target_stream_id="s" * 64,
                branch_id="main", target_head=f"{t}{'h' * 63}", task_id=f"t{t}",
                substrate="echo", scores={d: (1.0 if v else 0.0) for d in DIMS}, ts_ms=t)
            try:
                w = reg.record_review(env) if on else reg._reviewer_weight(
                    r.vacant_id, "echo")
                if t == 19:
                    last_round_group += w
            except ReviewRejected:
                pass
        for r in honest:
            v = rng.random() < 0.8  # 獨立投票（各自的亂數）
            env = ReviewEnvelope.create(
                r, target_id=target.vacant_id, target_stream_id="s" * 64,
                branch_id="main", target_head=f"{t}{'h' * 63}", task_id=f"t{t}",
                substrate="echo", scores={d: (1.0 if v else 0.0) for d in DIMS}, ts_ms=t)
            try:
                if on:
                    reg.record_review(env)
            except ReviewRejected:
                pass
    return last_round_group


# === ③ probation 洗白（沉沒者換 key 重生：權重上限＋強制稽核、不即時得利）=========
def _probation_whitewash(ratio: float, rng: random.Random, on: bool) -> float:
    """3 個已證明老手（score≈0.9）＋ round(7×ratio) 個洗白者（新 key、probation）。
    回**洗白者在 100 筆路由中的佔比**。判準：on ≤0.2（蓋 0.55＋每 10 筆才一筆
    配額）；off ≥ 0.35（洗白者吃 obs=0 探索額、即時得利）。"""
    from .body import CapabilityCard
    from .registry import Registry
    from .reputation import DIMS

    reg = Registry()
    for i in range(3):  # 老手：10 筆好評
        vid = f"veteran{i}"
        reg._cards[vid] = CapabilityCard(vacant_id=vid, niches=["code"])
        reg.note_head(vid, f"sv{i}", "main", "h" * 64)
        for _ in range(10):
            reg._rep.record_review(f"sv{i}", "main", "echo", {d: 1.0 for d in DIMS})
    n_white = round(7 * ratio)
    whites = [f"white{i}" for i in range(n_white)]
    for vid in whites:
        reg._cards[vid] = CapabilityCard(vacant_id=vid, niches=["code"])
        if on:
            reg.set_probation(vid, True)
    if not whites:
        return 0.0
    picks = 0
    for _ in range(100):
        c = reg.route("code", "echo")
        if c and c.vacant_id in whites:
            picks += 1
    return picks / 100


# === ④ reviewer 入押（連續誤放行 → review 權重實測下降 ≥ 預期曲線）================
def _reviewer_stake(ratio: float, rng: random.Random, on: bool) -> float:
    """高信譽 reviewer（weight≈0.6 起步）對 20 筆交付投票：交付一半是好一半壞，
    reviewer 以機率＝惡意比例對壞交付誤放行（投 PASS）。稽核確定性全抓。
    回**期末權重／期初權重**。判準：on 在 ratio=0.7 ≤0.7（每次誤放行 honesty
    ×0.5 的幾何下墜）；off ≈1.0（無後果）。"""
    from .registry import Registry, REVIEWER_SATURATION_OBS, REVIEWER_WEIGHT_FLOOR
    from .reputation import DIMS

    reg = Registry()
    rid, stream = "corrupt-reviewer", "st-reviewer"
    reg.note_head(rid, stream, "main", "h" * 64)
    for _ in range(10):
        reg._rep.record_review(stream, "main", "echo", {d: 1.0 for d in DIMS})
    score0, obs0 = reg.standing(rid, "echo")
    w0 = max(REVIEWER_WEIGHT_FLOOR, score0 * obs0 / (obs0 + REVIEWER_SATURATION_OBS))
    for _ in range(20):
        bad = rng.random() < 0.5
        if bad and rng.random() < ratio:  # 誤放行壞交付：其 PASS 對五維皆假陳述
            if on:
                reg.apply_slash(rid, "echo", 0.5)
    score1, obs1 = reg.standing(rid, "echo")
    w1 = max(REVIEWER_WEIGHT_FLOOR, score1 * obs1 / (obs1 + REVIEWER_SATURATION_OBS))
    return w1 / w0


# === ⑤ decay/slash 下墜（高信譽連續交壞 → 信譽可觀測下墜）========================
def _decay_slash(ratio: float, rng: random.Random, on: bool) -> float:
    """高信譽居民（10 好評，score≈0.9）連做 20 筆交付：每筆以機率＝惡意比例是
    provable fault。回**期末信譽分**。判準：on 在 ratio=0.7 ≤0.65、ratio=0 ≥0.85；
    off ≈0.9 不動（只增不減的舊世界）。"""
    from .reputation import DIMS, Reputation

    rep = Reputation()
    key = ("high-rep", "main", "echo")
    rep.record_review(*key, {d: 1.0 for d in DIMS}, weight=10.0)
    for _ in range(20):
        if rng.random() < ratio:  # provable fault：稽核 fail
            if on:
                rep.slash(*key, 0.5)
            rep.record_review(*key, {d: 0.0 for d in DIMS}, weight=0.05)
        else:
            rep.record_review(*key, {d: 1.0 for d in DIMS}, weight=0.05)
    return rep.score(*key)


# === ⑥ M2 記憶（wipe 前後同族任務：表現回落）====================================
def _memory_wipe(ratio: float, rng: random.Random, on: bool) -> float:
    """前窗 20 題中 round(20×ratio) 題屬目標族（其餘干擾族）；M2＋oracle 教訓
    跑完後 wipe（同 key 新 stream），後窗全目標族。回**表現回落＝前窗通過率
    −後窗通過率**。判準：on 在 ratio≥0.3 ≥0.3（教訓隨記憶抹除消失）；
    off（不 wipe）≈0（教訓還在、後窗全過）。"""
    from .identity import Identity
    from .logbook import Logbook
    from .memory import MemoryManager, MemoryStream
    from .x1 import make_family_sequence, run_x1

    n_fam = round(20 * ratio)
    if n_fam == 0:
        return 0.0

    # 用自造極小任務族：通過與否完全由記憶注入決定（這正是本情境要驗的機制）。
    # check 用 contains（無沙箱子行程）——六情境各 ≤30 分的預算紅線（17 §P4）。
    # 假腦只認 M2 注入區塊的專用標記【MEM】（任務本文不含它——第一題無教訓
    # 可注入必敗、之後教訓接上即過；wipe 後標記消失 → 全敗＝表現回落）。
    from .x1 import X1Task
    good_code = "x = 1"
    bad_code = "x = 2"

    class Brain:
        name = "mem-stub"

        def generate(self, prompt: str) -> str:
            return good_code if "【MEM】" in prompt else bad_code

    check = {"type": "contains", "value": good_code}
    fam_tasks = [
        X1Task(task_id=f"fam{i}", family="fam", pitfall="p",
               prompt="做這題（關鍵詞：邊界 輸入 期望）", check=check)
        for i in range(n_fam)
    ]
    other_tasks = [
        X1Task(task_id=f"oth{i}", family="oth", pitfall="p",
               prompt="無關題 zzz", check={"type": "contains", "value": "NEVER-MATCH"})
        for i in range(20 - n_fam)
    ]

    ident = Identity.generate()
    stream = MemoryStream(Logbook(), ident)
    mgr = MemoryManager("M2")

    def oracle_lesson(fam: str) -> str:
        return "【MEM】同型任務：先列邊界輸入的期望輸出再實作。"

    # 前窗：目標族＋干擾族（干擾族必敗，不計入通過率分子）。
    # 教訓無論成敗都寫（被稽核 episode 就有蒸餾資格——M2 的「被審」是資格線）；
    # 第一題還沒有教訓可注入 → 必敗，之後教訓接上 → 通過（遷移鏈）。
    pre = run_x1(Brain(), "M2", fam_tasks + other_tasks, stream=stream, manager=mgr,
                 seed="b6", oracle=False,
                 distill=lambda t, a, p: oracle_lesson(t.family) if t.family == "fam" else None,
                 retry_backoff_s=0)
    pre_fam = [r for r in pre if r["family"] == "fam"]
    pre_rate = sum(1 for r in pre_fam if r["passed"]) / max(1, len(pre_fam))

    if on:  # wipe：同一把 key、新創世 stream（記憶歸零）
        stream = MemoryStream(Logbook(), ident)
    post_tasks = [
        X1Task(task_id=f"post{i}", family="fam", pitfall="p",
               prompt="做這題（關鍵詞：邊界 輸入 期望）", check=check)
        for i in range(n_fam)
    ]
    post = run_x1(Brain(), "M2", post_tasks, stream=stream, manager=mgr,
                  seed="b6", oracle=False, distill=lambda *a: None, retry_backoff_s=0)
    post_rate = sum(1 for r in post if r["passed"]) / max(1, len(post))
    return pre_rate - post_rate


# === 判準（事前寫死；13 §3「拆掉數字沒變＝裝飾」）=================================
SCENARIOS: dict[str, tuple[Callable[[float, random.Random, bool], float], str]] = {
    "sig_attribution": (_sig_attribution, "被收下的偽造票數"),
    "same_source": (_same_source, "克隆團總實收權重"),
    "probation_whitewash": (_probation_whitewash, "洗白者路由佔比"),
    "reviewer_stake": (_reviewer_stake, "reviewer 期末/期初權重比"),
    "decay_slash": (_decay_slash, "高信譽期末分"),
    "memory_wipe": (_memory_wipe, "wipe 前後表現回落"),
}


def _verdict(name: str, rep: ScenarioReport) -> tuple[bool, str]:
    on, off = rep.on_cells, rep.off_cells
    if name == "sig_attribution":
        ok = all(c.value == 0.0 for c in on) and _at(off, 0.7).value == 7.0
        return ok, f"on 全拒（max={max(c.value for c in on):.0f}）；off 收下 {_at(off, 0.7).value:.0f}/7"
    if name == "same_source":
        ok = _at(on, 0.7).value <= 0.5 and _at(off, 0.7).value >= 2.0
        return ok, (f"on 末輪克隆團總重 {_at(on, 0.7).value:.2f}（≤0.5＝floor 曲線）；"
                    f"off {_at(off, 0.7).value:.2f}（≥2.0＝路由可被劫持）")
    if name == "probation_whitewash":
        ok = all(c.value <= 0.2 for c in on) and _at(off, 0.7).value >= 0.35
        return ok, f"on 佔比 max {max(c.value for c in on):.2f}（≤0.2）；off {_at(off, 0.7).value:.2f}（≥0.35）"
    if name == "reviewer_stake":
        ok = _at(on, 0.7).value <= 0.7 and _at(off, 0.7).value >= 0.9
        return ok, f"on 權重比 {_at(on, 0.7).value:.2f}（≤0.7）；off {_at(off, 0.7).value:.2f}（≥0.9）"
    if name == "decay_slash":
        ok = (_at(on, 0.7).value <= 0.65 and _at(on, 0.0).value >= 0.85
              and _at(off, 0.7).value >= 0.85)
        return ok, (f"on 0.7格 {_at(on, 0.7).value:.2f}（≤0.65）、0格 {_at(on, 0.0).value:.2f}（≥0.85）；"
                    f"off {_at(off, 0.7).value:.2f}（≥0.85）")
    if name == "memory_wipe":
        ok = _at(on, 0.5).value >= 0.3 and _at(off, 0.5).value <= 0.1
        return ok, f"on 回落 {_at(on, 0.5).value:.2f}（≥0.3）；off {_at(off, 0.5).value:.2f}（≤0.1）"
    return False, "unknown scenario"


# === 公開入口 =====================================================================
def run_all(
    *,
    n_seeds: int = DEFAULT_N_SEEDS,
    base_seed: str = "blayer-v1",
    out_dir: Path | None = None,
    only: tuple[str, ...] | None = None,
) -> dict[str, ScenarioReport]:
    """跑六情境（on＋off 雙組），回 {name: ScenarioReport}；給 out_dir 則落盤
    cells.jsonl＋summary.md（一頁結果，17 §P4 歸檔格式）。"""
    reports: dict[str, ScenarioReport] = {}
    for name, (fn, metric) in SCENARIOS.items():
        if only and name not in only:
            continue
        rep = _sweep(name, metric, fn, n_seeds=n_seeds, base_seed=base_seed)
        rep.verdict, rep.detail = _verdict(name, rep)
        reports[name] = rep

    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / "cells.jsonl").open("w", encoding="utf-8") as f:
            for rep in reports.values():
                for c in rep.on_cells + rep.off_cells:
                    f.write(json.dumps({**c.to_json(), "arm": ("on" if c in rep.on_cells else "off")},
                                       ensure_ascii=False) + "\n")
        lines = ["# B 層機制驗收六情境 — 一頁結果", ""]
        for name, rep in reports.items():
            mark = "✅" if rep.verdict else "❌"
            lines.append(f"{mark} **{name}**（{rep.metric}）：{rep.detail}")
        lines.append("")
        lines.append("判準事前寫死於 vacant/blayer.py `_verdict`；「拆掉數字沒變」＝裝飾、"
                     "從一切主張移除（13 §3）。")
        (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return reports
