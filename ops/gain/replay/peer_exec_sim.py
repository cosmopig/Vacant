#!/usr/bin/env python3
"""peer_exec_sim — 把真實候選池重放過 `vacant/peerexec.py`，加上腐化的執行器。

零 API 呼叫、零模型呼叫。只讀 `runs/<run>/calls.jsonl`（每一次生成的完整回應都在
磁碟上）＋本機沙箱。跑的是 `vacant/peerexec.py` 的**真程式碼路徑**：真的 Ed25519
簽章、真的 hash-chain、真的 `form_verdict`。腐化的執行器不是 mock 出來的判決，
是**同一個 Executor 類別換一個探針**——它照樣誠實地簽名，只是簽了一句謊。
歸屬之所以成立，正是因為謊被自己的金鑰簽住。

兩階段
------
1. `--build-facts`：對每一個候選跑一次**真的**沙箱（`ops.gain.gain_run.meets_demand`
   ＋ `conform_failure_detail`），落盤成 facts cache。誠實執行器在模擬裡回放這份
   結果——因為驗收套件是確定性的，k 個誠實執行器**依建構**完全一致。
   ⚠ 這正是本模擬的關鍵假設，也是它的邊界：真實沙箱的抖動（timeout、機器負載、
     `checks.py` 白名單漏洞）**沒有**被模型化。`--flake` 那張表就是量這一條。
2. 掃描：k ∈ {1,3,5,7} × f ∈ {0,.1,.3,.5,.7} × 五種對手 × 兩個池。

對手模型（都給了 oracle 知識——強對手假設；**機制本身一處都沒碰 hidden**）
-----------------------------------------------------------------------
- LIAR       **各行其是**的說謊者：每個腐化執行器自己挑一份要放行的草稿（在該題
             hidden 錯誤的候選裡種子化均勻抽），對它永遠簽 visible_ok=True，其餘照實跑。
             全部候選都正確的題目上這位對手沒有目標（照實記錄，不美化）。
- COLLUDERS  **協調過**的說謊者：整個集團鎖定**同一份**目標草稿——池子裡最早的
             hidden 錯誤候選（最強版本：CONFORM 交第一份通過的，越早的位置控制力
             越大）。與 LIAR 唯一的差別就是「有沒有講好」，所以兩欄相減量到的正是
             **協調本身的價值**。這是「分歧即證據」這條路線最該怕的對手。
- SABOTEUR   對每一份草稿都簽 visible_ok=False，且**不真的跑**，所以 first_failing_test
             只能瞎猜（固定填 1）。⚠ 這個「懶惰」設定對偵測有利：一個真的跑、只在
             布林值上說謊的破壞者不會被 detail 通道抓到（布林通道照樣抓得到）。
- RANDOM     每 (task, draft) 擲一次種子化的硬幣。
- SMART_LIAR **會閉嘴**的說謊者。只在三個條件同時成立時才簽假 PASS，其餘時間輸出
             與誠實執行器**逐位相同**：
               S1 目標 hidden 錯（oracle）；
               S2 目標是**近失**——載入成功且 `first_failing_test >= 2`（至少通過一條
                  可見驗收）。對連載入都失敗的草稿簽 PASS 太顯眼；近失的謊看起來像抖動。
               S3 集團**贏得了這一票**：`n_corrupt >= quorum`（predicts it will not
                  be outvoted）。不划算就完全不說謊。
             目標取該題最早的合格草稿，且必須排在第一份誠實通過者之前，否則謊到不了。
             它量的是「分歧即證據」這條路線的真正上界：**偵測率只對笨對手成立**。

紀律
----
- V/GT 分離：`hidden_check` 只用來**計分**與**定義對手的目標**，一處都沒有進入
  `peerexec` 的判決路徑（SPEC §5.3）。
- 不改任何既有臂、不寫進任何既有 run 目錄。

用法
----
  export VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz
  .venv/bin/python ops/gain/replay/peer_exec_sim.py --build-facts g_r446_eq5_mbpp
  .venv/bin/python ops/gain/replay/peer_exec_sim.py --build-facts g_r443_gemma_lcb
  .venv/bin/python ops/gain/replay/peer_exec_sim.py --build-trivial g_r446_eq5_mbpp g_r443_gemma_lcb
  .venv/bin/python ops/gain/replay/peer_exec_sim.py --calibrate
  .venv/bin/python ops/gain/replay/peer_exec_sim.py --sweep
  .venv/bin/python ops/gain/replay/peer_exec_sim.py --trivial-suite
  .venv/bin/python ops/gain/replay/peer_exec_sim.py --flake --challenge
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import pathlib
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Mapping

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
)

from ops.gain.gain_run import (conform_failure_detail, extract_code,  # noqa: E402
                               meets_demand)
from vacant import peerexec as px  # noqa: E402
from vacant.codebench import EvalPlusMBPPLoader, LiveCodeBenchLoader  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
CACHE = HERE / "cache"
OUT = HERE

# 池子：run 名稱 → (bank, 產生候選的臂, 每題候選數)
POOLS = {
    "g_r446_eq5_mbpp": ("evalplus", "EQ5", 5),
    "g_r443_gemma_lcb": ("lcb", "OFF5", 5),
}
BOOT_B = 2000
BOOT_SEED = 20260904


def sha(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


# ── 池子讀取 ────────────────────────────────────────────────────────────────
def load_pool(run: str) -> tuple[dict[str, dict], dict[str, list[str]]]:
    """回傳 (tasks by id, 候選碼 by task id，保持 calls.jsonl 的原始抽樣順序)。"""
    bank, arm, _k = POOLS[run]
    loader = (LiveCodeBenchLoader() if bank == "lcb"
              else EvalPlusMBPPLoader(expose_contract=True))
    tasks = {t["task_id"]: t for t in loader.iter_tasks("x")}
    cands: dict[str, list[str]] = collections.defaultdict(list)
    with (pathlib.Path("runs") / run / "calls.jsonl").open() as f:
        for line in f:
            d = json.loads(line)
            if d.get("role") != "gen" or not d.get("ok"):
                continue
            meta = d.get("meta") or {}
            if meta.get("arm") != arm:
                continue
            cands[meta["task_id"]].append(extract_code(d.get("response") or ""))
    return tasks, dict(cands)


# ── 階段 1：真沙箱事實 ──────────────────────────────────────────────────────
def _fact_job(job):
    key, code, task = job
    ep = task.get("entry_point")
    try:
        vis, _ = meets_demand(code, task["visible_check"]["code"], 10, entry_point=ep)
    except Exception:  # noqa: BLE001
        vis = None
    try:
        hid, _ = meets_demand(code, task["hidden_check"]["code"], 10, entry_point=ep)
    except Exception:  # noqa: BLE001
        hid = None
    detail = {"first_failing_test": None, "n_visible_tests": None,
              "loads_ok": None, "detail_reason": None}
    if vis is False:
        try:
            detail = conform_failure_detail(code, task)
        except Exception as exc:  # noqa: BLE001
            detail = {"first_failing_test": None, "n_visible_tests": None,
                      "loads_ok": None, "detail_reason": f"probe_error:{type(exc).__name__}"}
    return key, {"visible": vis, "hidden": hid, **detail}


def build_facts(run: str, workers: int = 6) -> pathlib.Path:
    tasks, cands = load_pool(run)
    jobs = []
    for tid, codes in cands.items():
        t = tasks.get(tid)
        if not t:
            continue
        for i, code in enumerate(codes):
            jobs.append((f"{tid}#{i}", code, t))
    print(f"{run}: {len(cands)} tasks, {len(jobs)} candidates "
          f"(visible + hidden + failure-detail, {workers} workers)", flush=True)
    facts: dict[str, dict] = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (key, val) in enumerate(ex.map(_fact_job, jobs, chunksize=4), 1):
            facts[key] = val
            if n % 200 == 0:
                print(f"  {n}/{len(jobs)}", flush=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"peerexec_facts_{run}.json"
    p.write_text(json.dumps(facts, indent=0, sort_keys=True))
    print(f"wrote {p} ({len(facts)} entries)")
    return p


TRIVIAL_SUITE_CODE = "pass"
#: 「零條驗收」的合法寫法。空字串在沙箱裡 rc≠0（`conform_failure_detail` 的註解已實測），
#: 會把「跑了零條驗收」誤讀成「候選載入失敗」；`pass` 才是真正的空套件。


def _trivial_job(job):
    key, code, task = job
    try:
        ok, _ = meets_demand(code, TRIVIAL_SUITE_CODE, 10,
                             entry_point=task.get("entry_point"))
    except Exception:  # noqa: BLE001
        ok = None
    return key, ok


def build_trivial(run: str, workers: int = 6) -> pathlib.Path:
    """加算 `trivial` 欄位＝「這份草稿在**一套什麼都不驗的驗收**下過不過」。

    這是 §五「套件本身被腐化」那一格的輸入：全體執行器誠實、全體跑同一套驗收，
    只是那套驗收退化成「載入得起來就算過」。用真沙箱算，不是用假設推。
    """
    tasks, cands = load_pool(run)
    facts = load_facts(run)
    jobs = [(f"{tid}#{i}", c, tasks[tid])
            for tid, codes in cands.items() if tid in tasks
            for i, c in enumerate(codes)]
    print(f"{run}: trivial-suite pass/fail for {len(jobs)} candidates "
          f"({workers} workers)", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (key, ok) in enumerate(ex.map(_trivial_job, jobs, chunksize=8), 1):
            facts[key]["trivial"] = ok
            if n % 400 == 0:
                print(f"  {n}/{len(jobs)}", flush=True)
    (CACHE / f"peerexec_facts_{run}.json").write_text(
        json.dumps(facts, indent=0, sort_keys=True))
    n_ok = sum(1 for k in facts if facts[k].get("trivial"))
    print(f"{run}: trivial suite admits {n_ok}/{len(facts)} candidates "
          f"(real suite admits {sum(1 for k in facts if facts[k]['visible'])})")
    return CACHE / f"peerexec_facts_{run}.json"


def _rehidden_job(job):
    key, code, task, timeout_s = job
    try:
        hid, _ = meets_demand(code, task["hidden_check"]["code"], timeout_s,
                              entry_point=task.get("entry_point"))
    except Exception:  # noqa: BLE001
        hid = None
    return key, hid


def repair_hidden(run: str, workers: int = 3, timeout_s: int = 60) -> dict:
    """把 hidden 標籤的 **timeout 假陰性** 修掉。規則統一、方向安全、不看 runtime。

    為什麼需要（本輪實測，不是預防性的）：`--build-facts` 用 6 個 worker 並行跑，
    而 MBPP+ 的 `hidden_check`（base＋plus）有些題目本身要 3–9 秒；並行負載下
    它們撞上 `meets_demand` 的 10 秒上限，被記成 False。逐題復跑（60 秒上限）：
    `mbppplus_Mbpp/{123,389,301,162}` 全部穩定回 True、`592` 在 9.4–10.0 秒邊界抖動。

    規則：**凡是 hidden=False 的候選，一律用 60 秒上限重跑一次；翻成 True 就採用。**
    - 統一：不挑「跟 runtime 不合的那幾筆」重跑，那會把結果往 runtime 拉。
    - 方向安全：逾時只可能造成**假陰性**（該過的被記成沒過），不可能造成假陽性。
      所以「False→True 才改、True→False 不改」不是選擇性報告，是這個誤差的形狀。
    - **只動 hidden（計分用）**，不動 visible（機制的輸入）。visible 這一側已經和
      runtime 落盤逐筆比對過，1855/1855 完全相同，重跑只會引進新的雜訊。
    """
    tasks, cands = load_pool(run)
    facts = load_facts(run)
    jobs = []
    for tid, codes in cands.items():
        t = tasks.get(tid)
        if not t:
            continue
        for i, code in enumerate(codes):
            if facts.get(f"{tid}#{i}", {}).get("hidden") is not True:
                jobs.append((f"{tid}#{i}", code, t, timeout_s))
    print(f"{run}: re-checking {len(jobs)} hidden=False candidates at {timeout_s}s "
          f"({workers} workers)", flush=True)
    flips = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (key, hid) in enumerate(ex.map(_rehidden_job, jobs, chunksize=2), 1):
            if hid is True and facts[key]["hidden"] is not True:
                facts[key]["hidden"] = True
                facts[key]["hidden_repaired"] = True
                flips += 1
            if n % 200 == 0:
                print(f"  {n}/{len(jobs)} flips={flips}", flush=True)
    (CACHE / f"peerexec_facts_{run}.json").write_text(
        json.dumps(facts, indent=0, sort_keys=True))
    print(f"{run}: {flips}/{len(jobs)} hidden=False candidates were timeout false-negatives")
    return {"run": run, "rechecked": len(jobs), "flips": flips}


def load_facts(run: str) -> dict[str, dict]:
    p = CACHE / f"peerexec_facts_{run}.json"
    if not p.exists():
        raise SystemExit(f"缺 facts cache：先跑 --build-facts {run}")
    return json.loads(p.read_text())


# ── 探針：誠實 ＋ 四種腐化 ──────────────────────────────────────────────────
class HonestProbe:
    """回放真沙箱結果。確定性套件 ⇒ k 個誠實執行器依建構一致（本模擬的核心假設）。"""

    def __init__(self, facts: Mapping[str, dict], index: Mapping[tuple[str, str], str],
                 flake: float = 0.0, rng: random.Random | None = None):
        self.facts, self.index, self.flake, self.rng = facts, index, flake, rng

    def truth(self, code: str, task: Mapping[str, Any]) -> dict:
        return self.facts[self.index[(task["task_id"], sha(code))]]

    def __call__(self, code: str, task: Mapping[str, Any]) -> px.ProbeResult:
        f = self.truth(code, task)
        vis = bool(f["visible"])
        if self.flake and self.rng is not None and self.rng.random() < self.flake:
            vis = not vis  # 沙箱抖動：不是腐化，但長得跟腐化一樣
        return px.ProbeResult(vis, f["first_failing_test"], f["n_visible_tests"],
                              f["loads_ok"], f["detail_reason"])


class LiarProbe(HonestProbe):
    """對被買通的那一份永遠簽 PASS，其餘照實。"""

    def __init__(self, *a, bribes: Mapping[str, str] | None = None, **kw):
        super().__init__(*a, **kw)
        self.bribes = bribes or {}

    def __call__(self, code: str, task: Mapping[str, Any]) -> px.ProbeResult:
        if self.bribes.get(task["task_id"]) == sha(code):
            return px.ProbeResult(True, None, self.truth(code, task)["n_visible_tests"],
                                  True, None)
        return super().__call__(code, task)


class SaboteurProbe(HonestProbe):
    """對所有草稿簽 FAIL，且不真的跑 ⇒ 條號只能瞎猜（固定 1）。"""

    def __call__(self, code: str, task: Mapping[str, Any]) -> px.ProbeResult:
        return px.ProbeResult(False, 1, self.truth(code, task)["n_visible_tests"], True, None)


class RandomProbe(HonestProbe):
    """每 (task, draft) 擲一次種子化硬幣。"""

    def __init__(self, *a, coin_seed: int = 0, **kw):
        super().__init__(*a, **kw)
        self.coin_seed = coin_seed

    def __call__(self, code: str, task: Mapping[str, Any]) -> px.ProbeResult:
        h = hashlib.sha256(f"{self.coin_seed}|{task['task_id']}|{sha(code)}".encode()).digest()
        vis = bool(h[0] & 1)
        return px.ProbeResult(vis, None if vis else 1,
                              self.truth(code, task)["n_visible_tests"], True, None)


class SmartLiarProbe(LiarProbe):
    """只在「說謊贏得了、而且不顯眼」的時候說謊；其餘時間與誠實執行器逐位相同。

    `bribes` 由 `smart_bribes` 算好（S1/S2 在那裡篩，S3 在 `run_cell` 決定要不要
    把 bribes 給它）。所以這個類別本身只剩一件事：**在收據上留下一個可辨識的名字**。
    行為與 `LiarProbe` 相同不是偷懶，是主張的一部分——腐化的差別在**目標選得多聰明**，
    不在簽名那一步；簽名那一步誠實與否機制看得到，目標選得聰不聰明機制看不到。
    """


ADVERSARIES = ("LIAR", "COLLUDERS", "SABOTEUR", "RANDOM", "SMART_LIAR")
# 有隨機性的對手才需要多種子；SABOTEUR／COLLUDERS／SMART_LIAR 依建構確定性（種子變異 = 0）。
SEEDED_ADVERSARIES = {"RANDOM", "LIAR"}


def wrong_targets(tasks, cands, facts) -> dict[str, list[str]]:
    """每題「hidden 錯誤」的候選 sha 清單 ＝ 說謊者可以放行的目標集合。

    ⚠ 這裡用了 hidden 標籤，那是**對手的能力假設**（強對手知道哪一份是錯的），
      不是機制的一部分——`peerexec` 的判決路徑一處都沒有 hidden。
    """
    out: dict[str, list[str]] = {}
    for tid, codes in cands.items():
        if tid not in tasks:
            continue
        out[tid] = [sha(c) for i, c in enumerate(codes)
                    if not facts[f"{tid}#{i}"]["hidden"]]
    return out


def coordinated_bribes(targets) -> dict[str, str]:
    """協調版：整個集團鎖定**最早**的錯誤候選（位置越早，控制第一個通過者的力量越大）。"""
    return {tid: v[0] for tid, v in targets.items() if v}


def independent_bribes(targets, rng: random.Random) -> dict[str, str]:
    """各行其是版：每個說謊者自己種子化地抽一份目標。"""
    return {tid: rng.choice(v) for tid, v in targets.items() if v}


def near_miss(fact: Mapping[str, Any]) -> bool:
    """「近失」＝載入成功、而且**至少通過一條**可見驗收才卡住。

    為什麼用這條當隱蔽性的操作定義：對一份連載入都失敗（`loads_ok=False`）或第一條
    就卡住的草稿簽 PASS，是一句一眼假的話；對一份跑得動、只在後面某條翻車的草稿簽
    PASS，看起來就像沙箱抖動。這條**不是**機制的一部分，是**對手**用來挑目標的濾網。
    """
    return bool(fact.get("loads_ok")) and (fact.get("first_failing_test") or 0) >= 2


def smart_bribes(tasks, cands, facts) -> dict[str, str]:
    """SMART_LIAR 的目標：每題最早那份「hidden 錯 ＋ 可見沒過 ＋ 近失」的草稿，
    而且必須排在第一份**誠實通過可見驗收**者之前——否則早停根本走不到它，謊白說。

    沒有合格目標的題目 ⇒ 這一題完全不說謊（輸出與誠實執行器逐位相同）。
    這就是它拿到 0% 偵測率的方式：**不是騙過了偵測，是根本沒有留下可偵測的東西。**
    """
    out: dict[str, str] = {}
    for tid, codes in cands.items():
        if tid not in tasks:
            continue
        seq = [facts[f"{tid}#{i}"] for i in range(len(codes))]
        stop = next((i for i, f in enumerate(seq) if f["visible"]), len(seq))
        pick = next((i for i in range(stop)
                     if not seq[i]["visible"] and not seq[i]["hidden"]
                     and near_miss(seq[i])), None)
        if pick is not None:
            out[tid] = sha(codes[pick])
    return out


# ── 掃描 ────────────────────────────────────────────────────────────────────
def n_corrupt_for(k: int, f: float) -> int:
    """四捨五入（half-up）。實際比例另外回報成 f_eff——不准用名目 f 講結論。"""
    import math
    return int(math.floor(f * k + 0.5))


def run_cell(run, tasks, cands, facts, index, *, k, f, adv, seed):
    """跑一格。回傳 per-task 記錄 ＋ 歸屬統計。真簽章、真驗章、真 hash-chain。"""
    nc = n_corrupt_for(k, f)
    quorum = k // 2 + 1
    targets = wrong_targets(tasks, cands, facts)

    execs: list[px.Executor] = []
    corrupt_ids: set[str] = set()
    honest = HonestProbe(facts, index)
    coord = coordinated_bribes(targets) if adv == "COLLUDERS" else None
    # S3：集團贏不了這一票就完全不說謊（空 bribes ⇒ SmartLiarProbe 退化成誠實回放）。
    smart = (smart_bribes(tasks, cands, facts)
             if adv == "SMART_LIAR" and nc >= quorum else {})
    for i in range(k):
        eid = f"x{i}"
        if i < nc:
            corrupt_ids.add(eid)
            if adv == "SMART_LIAR":
                probe = SmartLiarProbe(facts, index, bribes=smart)
            elif adv == "LIAR":
                # 各行其是：每個說謊者自己的種子 ⇒ 目標很少撞在一起。
                probe = LiarProbe(facts, index, bribes=independent_bribes(
                    targets, random.Random(f"{run}|{k}|{f}|LIAR|{seed}|{i}")))
            elif adv == "COLLUDERS":
                # 協調：整個集團同一份目標 ⇒ 票會疊起來，集團內部分歧恆為 0。
                probe = LiarProbe(facts, index, bribes=coord)
            elif adv == "SABOTEUR":
                probe = SaboteurProbe(facts, index)
            elif adv == "RANDOM":
                probe = RandomProbe(facts, index, coin_seed=seed * 1000 + i)
            else:
                raise SystemExit(f"unknown adversary {adv}")
        else:
            probe = honest
        execs.append(px.Executor(eid, px.Identity.generate(), px.Logbook(), probe))
    roster = px.roster_of(execs)

    rows, lie_named, lie_total, hon_named, hon_total = [], 0, 0, 0, 0
    flagged_exec: set[str] = set()
    runs_total = 0
    for tid, codes in sorted(cands.items()):
        t = tasks.get(tid)
        if t is None:
            continue
        drafts = [(c, f"w{i}") for i, c in enumerate(codes)]
        sel = px.select_by_quorum(t, drafts, execs, roster=roster,
                                  quorum=quorum, ts_ms=1_700_000_000_000)
        runs_total += sel.n_sandbox_runs
        # 歸屬統計：逐 (draft, executor) 比對「宣稱 vs 真相」與「有沒有被指名」
        named_here: set[str] = set()
        lied_here: set[str] = set()
        for vi, v in enumerate(sel.verdicts):
            named = set(v.dissenters) | set(v.equivocators) | set(v.detail_dissenters)
            truth = bool(facts[f"{tid}#{vi}"]["visible"])
            named_here |= named
            for eid in list(v.camp_pass) + list(v.camp_fail):
                claimed = eid in v.camp_pass
                lied = claimed != truth
                if eid in corrupt_ids:
                    lie_total += int(lied)
                    lie_named += int(lied and eid in named)
                    if lied:
                        lied_here.add(eid)
                else:
                    hon_total += 1
                    hon_named += int(eid in named)
                if eid in named:
                    flagged_exec.add(eid)
        shipped_hidden = None
        if not sel.refused:
            shipped_hidden = bool(facts[f"{tid}#{sel.shipped_index}"]["hidden"])
        rows.append({
            "task_id": tid,
            "refused": sel.refused,
            "shipped_index": sel.shipped_index,
            "delivered_correct": bool(shipped_hidden),
            "false_delivery": (not sel.refused) and not shipped_hidden,
            "contested": any(v.contested for v in sel.verdicts),
            "pool_has_correct": any(facts[f"{tid}#{i}"]["hidden"] for i in range(len(codes))),
            "n_runs": sel.n_sandbox_runs,
            # 逐題偵測率：**分母是全部腐化執行器**，不是「有說謊的那些」。
            # 一個這一題剛好跟多數方一致的腐化執行器＝沒被偵測到，計 0（人類指令原句）。
            "detect_task": (len(named_here & corrupt_ids) / nc) if nc else None,
            "corrupt_lied_here": len(lied_here),
        })
    chain_ok = all(px.verify_executor_chain(e.executor_id, e.book, roster) for e in execs)
    dt = [r["detect_task"] for r in rows if r["detect_task"] is not None]
    return {
        "rows": rows,
        "n_corrupt": nc,
        "f_eff": nc / k,
        # 三個偵測率，分開報，不准只報最好看的那一個：
        #   detect_exec  整個池跑完，**曾經**被指名的腐化執行器比例（運維視角，最寬鬆）
        #   detect_task  逐題被指名的腐化執行器比例（單一決策視角，最嚴格）
        #   detect_lie   逐「謊」被指名的比例（分母只算真的說了謊的那些證言）
        "detect_exec": (len(flagged_exec & corrupt_ids) / nc) if nc else None,
        "detect_task": (sum(dt) / len(dt)) if dt else None,
        "detect_lie": (lie_named / lie_total) if lie_total else None,
        "n_lies": lie_total,
        "false_accuse": (hon_named / hon_total) if hon_total else None,
        "n_honest_att": hon_total,
        "runs_per_task": runs_total / max(1, len(rows)),
        "chain_ok": chain_ok,
    }


def boot_ci_multi(vecs: list[list[float]], b: int = BOOT_B, seed: int = BOOT_SEED):
    """一次抽樣、多個估計量共用同一組重抽索引（配對 bootstrap，種子固定）。

    共用索引不只是省時間：deliv/false_deliv/false_refusal 是同一批題目上的三個量，
    分開抽會讓它們的區間互相不相容。
    """
    if not vecs or not vecs[0]:
        return [(None, None) for _ in vecs]
    rng = random.Random(seed)
    n = len(vecs[0])
    means: list[list[float]] = [[] for _ in vecs]
    for _ in range(b):
        idx = [rng.randrange(n) for _ in range(n)]
        for j, v in enumerate(vecs):
            means[j].append(sum(v[i] for i in idx) / n)
    out = []
    for m in means:
        m.sort()
        out.append((m[int(0.025 * b)], m[int(0.975 * b) - 1]))
    return out


def sweep(runs=("g_r446_eq5_mbpp", "g_r443_gemma_lcb"),
          ks=(1, 3, 5, 7), fs=(0.0, 0.1, 0.3, 0.5, 0.7)):
    results = []
    for run in runs:
        tasks, cands = load_pool(run)
        facts = load_facts(run)
        index = {}
        for tid, codes in cands.items():
            for i, c in enumerate(codes):
                index[(tid, sha(c))] = f"{tid}#{i}"
        # 基線 = k=1, f=0 ＝ CONFORM 本身（校準檢查）
        base = run_cell(run, tasks, cands, facts, index, k=1, f=0.0, adv="LIAR", seed=0)
        base_correct = {r["task_id"]: r["delivered_correct"] for r in base["rows"]}
        n = len(base["rows"])
        print(f"\n=== {run}  n={n}  CALIBRATION k=1 f=0 (=CONFORM): "
              f"delivered {sum(base_correct.values())}/{n} "
              f"= {100*sum(base_correct.values())/n:.2f}%  "
              f"refused {sum(r['refused'] for r in base['rows'])}  "
              f"chain_ok={base['chain_ok']}  runs/task={base['runs_per_task']:.2f}", flush=True)
        for adv in ADVERSARIES:
            for k in ks:
                for f in fs:
                    seeds = range(5) if adv in SEEDED_ADVERSARIES else range(1)
                    per_task: dict[str, list[dict]] = collections.defaultdict(list)
                    agg = []
                    for s in seeds:
                        c = run_cell(run, tasks, cands, facts, index, k=k, f=f, adv=adv, seed=s)
                        agg.append(c)
                        for r in c["rows"]:
                            per_task[r["task_id"]].append(r)
                    tids = sorted(per_task)
                    def mean_over_seeds(key):
                        return [sum(bool(r[key]) for r in per_task[t]) / len(per_task[t])
                                for t in tids]
                    dc = mean_over_seeds("delivered_correct")
                    fd = mean_over_seeds("false_delivery")
                    ref = mean_over_seeds("refused")
                    con = mean_over_seeds("contested")
                    fr = [sum(bool(r["refused"]) and base_correct[t] for r in per_task[t])
                          / len(per_task[t]) for t in tids]
                    (lo, hi), (flo, fhi), (rlo, rhi) = boot_ci_multi([dc, fd, fr])
                    def mean_of(key):
                        v = [c[key] for c in agg if c[key] is not None]
                        return (sum(v) / len(v)) if v else None
                    # 逐題偵測率的 CI 與 deliv 共用同一組重抽索引（同一批題目）。
                    dtv = ([sum(r["detect_task"] for r in per_task[t]) / len(per_task[t])
                            for t in tids] if agg[0]["n_corrupt"] else None)
                    dt_ci = boot_ci_multi([dtv])[0] if dtv else (None, None)
                    row = {
                        "run": run, "n": n, "adv": adv, "k": k, "f": f,
                        "n_corrupt": agg[0]["n_corrupt"], "f_eff": agg[0]["f_eff"],
                        "quorum": k // 2 + 1, "majority_bound": (k - 1) // 2,
                        "above_bound": agg[0]["n_corrupt"] > (k - 1) // 2,
                        "n_seeds": len(agg), "seeds": list(seeds),
                        "deliv_acc": sum(dc) / n, "deliv_ci": [lo, hi],
                        "false_deliv": sum(fd) / n, "false_deliv_ci": [flo, fhi],
                        "refusal": sum(ref) / n,
                        "false_refusal": sum(fr) / n, "false_refusal_ci": [rlo, rhi],
                        "contested": sum(con) / n,
                        "detect_exec": mean_of("detect_exec"),
                        "detect_task": mean_of("detect_task"),
                        "detect_task_ci": list(dt_ci),
                        "detect_lie": mean_of("detect_lie"),
                        "n_lies": mean_of("n_lies"),
                        "false_accuse": mean_of("false_accuse"),
                        "runs_per_task": mean_of("runs_per_task"),
                        "chain_ok": all(c["chain_ok"] for c in agg),
                    }
                    results.append(row)
                    def _p(x):
                        return "  -  " if x is None else f"{x:.3f}"
                    print(f"{run[:18]:18s} {adv:10s} k={k} f={f:.1f} "
                          f"(nc={row['n_corrupt']},f_eff={row['f_eff']:.2f},"
                          f"{'OVER' if row['above_bound'] else ' ok '}) "
                          f"deliv={100*row['deliv_acc']:6.2f}% "
                          f"[{100*lo:5.2f},{100*hi:5.2f}] "
                          f"fd={100*row['false_deliv']:5.2f}% "
                          f"fr={100*row['false_refusal']:5.2f}% "
                          f"det_ex={_p(row['detect_exec'])} "
                          f"det_task={_p(row['detect_task'])} "
                          f"det_lie={_p(row['detect_lie'])} "
                          f"f_acc={_p(row['false_accuse'])} "
                          f"lies={0 if row['n_lies'] is None else row['n_lies']:.0f} "
                          f"cont={100*row['contested']:5.1f}% chain={row['chain_ok']}",
                          flush=True)
    p = OUT / "peer_exec_sweep.json"
    p.write_text(json.dumps(results, indent=1))
    print(f"\nwrote {p}")
    return results


def smart_target_table(runs=("g_r446_eq5_mbpp", "g_r443_gemma_lcb")):
    """SMART_LIAR 用多少「機會」換到 0% 偵測率——三道濾網逐層剩多少題。

    這張表是 SMART_LIAR 那幾格的解釋：偵測率 0 不是它騙過了什麼，是它把 90%+ 的
    出手機會丟掉，只留下「贏得了、而且看起來像抖動」的那幾題。
    """
    out = []
    print("\n=== SMART_LIAR 的機會成本（三道濾網）===")
    for run in runs:
        tasks, cands = load_pool(run)
        facts = load_facts(run)
        n = len(cands)
        n_any = len(coordinated_bribes(wrong_targets(tasks, cands, facts)))
        n_before = 0
        for tid, codes in cands.items():
            seq = [facts[f"{tid}#{i}"] for i in range(len(codes))]
            stop = next((i for i, f in enumerate(seq) if f["visible"]), len(seq))
            n_before += int(any(not seq[i]["visible"] and not seq[i]["hidden"]
                                for i in range(stop)))
        n_smart = len(smart_bribes(tasks, cands, facts))
        row = {"run": run, "n": n, "any_wrong_target": n_any,
               "reachable_before_first_pass": n_before, "smart_target": n_smart,
               "abstain_rate": (n - n_smart) / n}
        out.append(row)
        print(f"  {run[:18]:18s} n={n:3d}  ① 有 hidden 錯的候選 {n_any:3d} "
              f"({100*n_any/n:4.1f}%) → ② 其中排在第一份誠實通過者之前 {n_before:3d} "
              f"({100*n_before/n:4.1f}%) → ③ 其中是近失 {n_smart:3d} "
              f"({100*n_smart/n:4.1f}%)   ⇒ 放棄出手 {100*row['abstain_rate']:.1f}% 的題")
    return out


def print_table(path=None, runs=None, advs=None):
    """把 `peer_exec_sweep.json` 重新印成表，不重跑。掃描要一小時，表要看很多次。"""
    p = pathlib.Path(path) if path else (OUT / "peer_exec_sweep.json")
    rows = json.loads(p.read_text())
    def _p(x):
        return "  -  " if x is None else f"{x:.3f}"
    for run in (runs or sorted({r["run"] for r in rows}, reverse=True)):
        sub = [r for r in rows if r["run"] == run]
        if not sub:
            continue
        base = next(r for r in sub if r["k"] == 1 and r["n_corrupt"] == 0)
        print(f"\n=== {run}  n={base['n']}  baseline(k=1,f=0)="
              f"{100*base['deliv_acc']:.2f}% deliv / {100*base['refusal']:.2f}% refuse ===")
        print(f"{'adversary':11s}{'k':>2s} {'f':>4s} {'nc':>3s} {'bnd':>4s} "
              f"{'deliv%':>7s} {'  95% CI':>16s} {'fd%':>6s} {'fr%':>6s} "
              f"{'det_ex':>7s} {'det_tk':>7s} {'det_lie':>8s} {'f_acc':>7s} {'cont%':>6s}")
        for r in sub:
            if advs and r["adv"] not in advs:
                continue
            lo, hi = r["deliv_ci"]
            print(f"{r['adv']:11s}{r['k']:>2d} {r['f']:>4.1f} {r['n_corrupt']:>3d} "
                  f"{'OVER' if r['above_bound'] else ' ok ':>4s} "
                  f"{100*r['deliv_acc']:>7.2f} [{100*lo:>6.2f},{100*hi:>6.2f}] "
                  f"{100*r['false_deliv']:>6.2f} {100*r['false_refusal']:>6.2f} "
                  f"{_p(r['detect_exec']):>7s} {_p(r.get('detect_task')):>7s} "
                  f"{_p(r['detect_lie']):>8s} {_p(r['false_accuse']):>7s} "
                  f"{100*r['contested']:>6.1f}")
    return rows


def flake_table(run="g_r446_eq5_mbpp", ks=(1, 3, 5, 7), flakes=(0.0, 0.01, 0.05)):
    """沙箱抖動敏感度：誠實執行器獨立以機率 p 翻轉 visible_ok。

    這一格量的是誠實邊界 §3：抖動不是腐化，但它會被同一套機制記成「分歧」。
    """
    tasks, cands = load_pool(run)
    facts = load_facts(run)
    index = {(tid, sha(c)): f"{tid}#{i}"
             for tid, codes in cands.items() for i, c in enumerate(codes)}
    print(f"\n=== flake sensitivity ({run}, honest only, f=0) ===")
    out = []
    for p_fl in flakes:
        for k in ks:
            accs, cons = [], []
            for s in range(3):
                rng = random.Random(f"flake|{k}|{p_fl}|{s}")
                probe = HonestProbe(facts, index, flake=p_fl, rng=rng)
                execs = [px.Executor(f"x{i}", px.Identity.generate(), px.Logbook(), probe)
                         for i in range(k)]
                roster = px.roster_of(execs)
                ok = con = tot = 0
                for tid, codes in sorted(cands.items()):
                    t = tasks.get(tid)
                    if t is None:
                        continue
                    sel = px.select_by_quorum(t, [(c, f"w{i}") for i, c in enumerate(codes)],
                                              execs, roster=roster, quorum=k // 2 + 1,
                                              ts_ms=1_700_000_000_000)
                    tot += 1
                    ok += int((not sel.refused)
                              and bool(facts[f"{tid}#{sel.shipped_index}"]["hidden"]))
                    con += int(any(v.contested for v in sel.verdicts))
                accs.append(ok / tot)
                cons.append(con / tot)
            row = {"run": run, "k": k, "flake": p_fl,
                   "deliv_acc": sum(accs) / len(accs), "contested": sum(cons) / len(cons)}
            out.append(row)
            print(f"  k={k} flake={p_fl:.2f}  deliv={100*row['deliv_acc']:.2f}%  "
                  f"contested={100*row['contested']:.1f}%")
    (OUT / "peer_exec_flake.json").write_text(json.dumps(out, indent=1))
    return out


def challenge_table(run="g_r446_eq5_mbpp", k=3, f=0.7, adv="SABOTEUR"):
    """落敗方的重跑權：被拒交的草稿換一組不相交的執行器再判一次。

    只在**新面板的腐化比例低於一半**時救得回來——這裡故意用一個乾淨面板量上界。
    """
    tasks, cands = load_pool(run)
    facts = load_facts(run)
    index = {(tid, sha(c)): f"{tid}#{i}"
             for tid, codes in cands.items() for i, c in enumerate(codes)}
    nc = n_corrupt_for(k, f)
    honest = HonestProbe(facts, index)
    execs = [px.Executor(f"x{i}", px.Identity.generate(), px.Logbook(),
                         SaboteurProbe(facts, index) if i < nc else honest)
             for i in range(k)]
    roster = px.roster_of(execs)
    panel = [px.Executor(f"c{i}", px.Identity.generate(), px.Logbook(), honest)
             for i in range(k)]
    proster = px.roster_of(panel)
    recovered = refused = overturned = 0
    for tid, codes in sorted(cands.items()):
        t = tasks.get(tid)
        if t is None:
            continue
        sel = px.select_by_quorum(t, [(c, f"w{i}") for i, c in enumerate(codes)], execs,
                                  roster=roster, quorum=k // 2 + 1, ts_ms=1_700_000_000_000)
        if not sel.refused:
            continue
        refused += 1
        for vi, v in enumerate(sel.verdicts):
            ch = px.challenge_rerun(t, codes[vi], panel, v, roster=proster,
                                    quorum=k // 2 + 1, ts_ms=1_700_000_000_000)
            if ch.outcome == "overturned":
                overturned += 1
                recovered += int(bool(facts[f"{tid}#{vi}"]["hidden"]))
                break
    print(f"\n=== challenge/re-run right ({run}, k={k}, f={f}, {adv}, clean panel) ===")
    print(f"  refused tasks={refused}  overturned by re-run={overturned}  "
          f"of which hidden-correct={recovered}")
    return {"refused": refused, "overturned": overturned, "recovered": recovered}


def trivial_suite_table(runs=("g_r446_eq5_mbpp", "g_r443_gemma_lcb"), ks=(1, 3, 5, 7)):
    """§五的第三個破口：**驗收套件本身被腐化**（全體執行器誠實）。

    這裡把 `visible_check` 換成 `pass`——一套什麼都不驗、任何載入得起來的草稿都通過
    的驗收。執行器一個都沒有腐化，所以：

      - 每一票都誠實、每一條鏈都驗得過、`contested` 恆為 0、`dissenters` 恆為空；
      - 也就是說，**機制的所有健康指標都顯示滿分**，而出貨的東西已經沒有被驗過。

    這正是 `vacant/peerexec.py` 誠實邊界 §2 那句「驗收套件仍然是被信任的輸入」的
    數字版本。去中心化執行對這個破口**一點幫助都沒有**，因為它分散的是「誰來跑」，
    不是「跑什麼」。commit-reveal（`commit_suite`）只把套件在時間上釘死，防的是
    「看到草稿之後再改套件」，防不了「一開始就給一套爛套件」。
    """
    out = []
    print("\n=== TRIVIAL SUITE：套件被腐化，執行器全誠實 ===")
    print("    (visible_check := 'pass'；載入得起來就算通過)")
    for run in runs:
        tasks, cands = load_pool(run)
        facts = load_facts(run)
        if any("trivial" not in facts[k] for k in facts):
            raise SystemExit(f"缺 trivial 欄位：先跑 --build-trivial {run}")
        index = {(tid, sha(c)): f"{tid}#{i}"
                 for tid, codes in cands.items() for i, c in enumerate(codes)}

        class TrivialProbe(HonestProbe):
            """誠實地跑那套什麼都不驗的驗收——誠實在這裡完全沒有保護力。"""

            def __call__(self, code, task):
                f = self.truth(code, task)
                return px.ProbeResult(bool(f.get("trivial")), None, 0, True, None)

        for k in ks:
            probe = TrivialProbe(facts, index)
            execs = [px.Executor(f"x{i}", px.Identity.generate(), px.Logbook(), probe)
                     for i in range(k)]
            roster = px.roster_of(execs)
            ok = fd = ref = con = tot = 0
            real_ok = 0
            for tid, codes in sorted(cands.items()):
                t = tasks.get(tid)
                if t is None:
                    continue
                trivial_task = {**t, "visible_check": {"type": "run_python",
                                                       "code": TRIVIAL_SUITE_CODE,
                                                       "timeout": 10}}
                sel = px.select_by_quorum(
                    trivial_task, [(c, f"w{i}") for i, c in enumerate(codes)], execs,
                    roster=roster, quorum=k // 2 + 1, ts_ms=1_700_000_000_000)
                tot += 1
                hit = (not sel.refused) and bool(facts[f"{tid}#{sel.shipped_index}"]["hidden"])
                ok += int(hit)
                fd += int((not sel.refused) and not hit)
                ref += int(sel.refused)
                con += int(any(v.contested for v in sel.verdicts))
                # 對照：同一題在**真**套件下 k=1 會交什麼
                i_real = next((i for i in range(len(codes))
                               if facts[f"{tid}#{i}"]["visible"]), None)
                real_ok += int(i_real is not None and facts[f"{tid}#{i_real}"]["hidden"])
            row = {"run": run, "k": k, "suite": "trivial", "n": tot,
                   "deliv_acc": ok / tot, "false_deliv": fd / tot, "refusal": ref / tot,
                   "contested": con / tot, "real_suite_deliv_acc": real_ok / tot,
                   "delta_pp": 100 * (ok - real_ok) / tot}
            out.append(row)
            print(f"  {run[:18]:18s} k={k}  deliv={100*row['deliv_acc']:6.2f}%  "
                  f"fd={100*row['false_deliv']:6.2f}%  refuse={100*row['refusal']:5.2f}%  "
                  f"contested={100*row['contested']:4.1f}%  "
                  f"(real suite {100*row['real_suite_deliv_acc']:.2f}% ⇒ "
                  f"{row['delta_pp']:+.2f}pp)")
    (OUT / "peer_exec_trivial_suite.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {OUT / 'peer_exec_trivial_suite.json'}")
    return out


def calibrate(runs=("g_r446_eq5_mbpp", "g_r443_gemma_lcb")):
    """校準檢查：k=1、f=0 的 peerexec 必須還原 CONFORM（＝ R446／R440P 的閘門規則）。

    **三個層次分開報，不准合併成一個「對上了」**：
      A `visible_ok` 逐格重放 vs 當時 runtime／既有稽核落盤的標籤。這是**機制的輸入**。
      M **機制身分**：逐題的出貨決定（拒交 or 出貨哪一份的 sha256）是否與 runtime
        逐位相同。這是唯一一個「閘門有沒有被忠實還原」的檢查。
      B **交付數**：delivered/refused 對上文件宣稱值。B 用的是 `hidden`（計分側），
        所以 B 對不上**不代表**機制沒還原——M 才代表。兩者混講就會把一個計分側的
        浮點可攜性問題講成機制不一致。
    """
    out = {}
    for run in runs:
        tasks, cands = load_pool(run)
        facts = load_facts(run)
        rows = [json.loads(l) for l in (pathlib.Path("runs") / run / "rows.jsonl").open()]
        rows = [r for r in rows if r.get("arm") == POOLS[run][1]]
        by_tid = {r["task_id"]: r for r in rows}
        index = {(tid, sha(c)): f"{tid}#{i}"
                 for tid, codes in cands.items() for i, c in enumerate(codes)}
        print(f"\n──────── {run} ────────")

        # [A] visible 標籤逐格比對
        agree = disagree = 0
        mism = []
        for r in rows:
            tid = r["task_id"]
            for a in r.get("conform_attempts") or []:
                key = f"{tid}#{a['attempt'] - 1}"
                if key not in facts:
                    continue
                if bool(facts[key]["visible"]) == bool(a["visible_ok"]):
                    agree += 1
                else:
                    disagree += 1
                    mism.append((key, a["visible_ok"], facts[key]["visible"]))
        src = "runtime rows.jsonl conform_attempts"
        if agree + disagree == 0:  # r443 沒有 conform_attempts ⇒ 用既有的獨立稽核產物
            ap = OUT / f"audit_r440p_{run}.json"
            if ap.exists():
                aud = json.loads(ap.read_text())
                src = ap.name
                for key, (v, _h) in aud.items():
                    if key in facts:
                        if bool(facts[key]["visible"]) == bool(v):
                            agree += 1
                        else:
                            disagree += 1
                            mism.append((key, v, facts[key]["visible"]))
        print(f"[A] visible_ok 逐格 vs {src}: agree={agree} disagree={disagree} "
              f"= {100*agree/max(1,agree+disagree):.2f}% identical")
        for m in mism[:10]:
            print("    mismatch", m)

        # [M] 機制身分：逐題出貨決定
        cell = run_cell(run, tasks, cands, facts, index, k=1, f=0.0, adv="LIAR", seed=0)
        n = len(cell["rows"])
        # ⚠ runtime 拒交時 `gate_code_sha256` **仍然**記著最後一份候選的 sha
        #   （`accepted=false`），所以只能拿「有出貨」的那些題比 sha，拒交的題比
        #   「有沒有拒交」。不分開比會憑空生出 26 筆假的不一致。
        same_ship = ship_cmp = same_ref = ref_cmp = 0
        ship_diff = []
        for r in cell["rows"]:
            rt = by_tid.get(r["task_id"])
            if rt is None or rt.get("gate_deliv") is None:
                continue
            if rt.get("accepted"):
                ship_cmp += 1
                mine = (sha(cands[r["task_id"]][r["shipped_index"]])
                        if r["shipped_index"] is not None else None)
                if mine == rt["gate_code_sha256"]:
                    same_ship += 1
                else:
                    ship_diff.append((r["task_id"], mine, rt["gate_code_sha256"]))
            else:
                ref_cmp += 1
                if r["refused"]:
                    same_ref += 1
                else:
                    ship_diff.append((r["task_id"], "shipped", "runtime_refused"))
        if ship_cmp or ref_cmp:
            print(f"[M] 出貨題的草稿 sha256 逐題 vs runtime gate_code_sha256: "
                  f"{same_ship}/{ship_cmp} identical；"
                  f"拒交題 {same_ref}/{ref_cmp} 也拒交")
            for d in ship_diff[:10]:
                print("    ship-diff", d)
        else:
            print("[M] runtime 沒有落盤 gate_code_sha256（此 run 的臂不是 CONFORM）；"
                  "機制身分只能靠 [A] 的 visible 標籤 ＋ 拒交數")

        # [B] 交付數
        rt_deliv = sum(1 for r in rows if r.get("gate_deliv") is True)
        rt_ref = sum(1 for r in rows if r.get("gate_deliv") is not None
                     and not r.get("accepted"))
        d = sum(r["delivered_correct"] for r in cell["rows"])
        rf = sum(r["refused"] for r in cell["rows"])
        if rt_deliv or rt_ref:
            print(f"[B] runtime gate         : delivered={rt_deliv}/{len(rows)} "
                  f"refused={rt_ref}")
        print(f"[B] peerexec k=1 f=0     : delivered={d}/{n} refused={rf} "
              f"chain_ok={cell['chain_ok']} runs/task={cell['runs_per_task']:.2f}")
        ap = OUT / f"audit_r440p_{run}.json"
        if ap.exists():
            # 同一條 first-visible-pass 規則、同一份 visible 標籤，只有 hidden 標籤不同：
            # 稽核那份是 10 秒上限，本 facts 是 10 秒 ＋ 60 秒逐筆復跑（見 repair_hidden）。
            aud = json.loads(ap.read_text())
            ad = arf = 0
            for tid, codes in cands.items():
                seq = [aud.get(f"{tid}#{i}") for i in range(len(codes))]
                if any(x is None for x in seq):
                    continue
                pick = next((h for v, h in seq if v), None)
                if not any(v for v, _ in seq):
                    arf += 1
                ad += int(bool(pick))
            n_rep = sum(1 for k in facts if facts[k].get("hidden_repaired"))
            print(f"[B] 同規則、{ap.name} 的 10s hidden 標籤: delivered={ad}/{n} "
                  f"refused={arf}  （差 {d - ad:+d} 全部來自 {n_rep} 筆 60s timeout 修復）")
        if rt_deliv:
            print(f"[B] delta vs runtime     : delivered {d - rt_deliv:+d}  "
                  f"refused {rf - rt_ref:+d}")
            # 把差異逐題指名——差 1 也要說得出是哪一題、為什麼。
            for r in cell["rows"]:
                rt = by_tid.get(r["task_id"])
                if rt and bool(rt.get("gate_deliv")) != bool(r["delivered_correct"]):
                    print(f"    score-diff {r['task_id']} runtime_hidden="
                          f"{rt.get('gate_deliv')} replay_hidden={r['delivered_correct']} "
                          f"same_shipped_sha="
                          f"{sha(cands[r['task_id']][r['shipped_index']]) == rt.get('gate_code_sha256')}")
        out[run] = {"agree": agree, "disagree": disagree, "ship_same": same_ship,
                    "ship_cmp": ship_cmp, "replay_deliv": d, "replay_refused": rf,
                    "runtime_deliv": rt_deliv, "runtime_refused": rt_ref, "n": n}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-facts", nargs="+", metavar="RUN")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--flake", action="store_true")
    ap.add_argument("--challenge", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--repair-hidden", nargs="+", metavar="RUN")
    ap.add_argument("--build-trivial", nargs="+", metavar="RUN")
    ap.add_argument("--trivial-suite", action="store_true")
    ap.add_argument("--table", action="store_true",
                    help="重印 peer_exec_sweep.json，不重跑")
    ap.add_argument("--smart-targets", action="store_true",
                    help="SMART_LIAR 的三道濾網逐層剩多少題")
    a = ap.parse_args()
    if a.table:
        print_table()
    if a.smart_targets:
        smart_target_table()
    if a.build_facts:
        for r in a.build_facts:
            if r in POOLS:
                build_facts(r, a.workers)
    if a.repair_hidden:
        for r in a.repair_hidden:
            if r in POOLS:
                repair_hidden(r)
    if a.build_trivial:
        for r in a.build_trivial:
            if r in POOLS:
                build_trivial(r, a.workers)
    if a.calibrate:
        calibrate()
    if a.sweep:
        sweep()
    if a.trivial_suite:
        trivial_suite_table()
    if a.flake:
        flake_table()
    if a.challenge:
        challenge_table()
