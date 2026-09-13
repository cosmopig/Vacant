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
  # R449 §四-3 的套件量具閘（先 census＋腐化變體標籤，再過閘）
  .venv/bin/python ops/gain/replay/peer_exec_sim.py --gauge-census g_r446_eq5_mbpp g_r443_gemma_lcb
  .venv/bin/python ops/gain/replay/peer_exec_sim.py --build-variant weak g_r446_eq5_mbpp g_r443_gemma_lcb
  .venv/bin/python ops/gain/replay/peer_exec_sim.py --build-variant targeted g_r446_eq5_mbpp g_r443_gemma_lcb
  .venv/bin/python ops/gain/replay/peer_exec_sim.py --build-variant mimic g_r446_eq5_mbpp g_r443_gemma_lcb
  .venv/bin/python ops/gain/replay/peer_exec_sim.py --gauge-gate
  .venv/bin/python ops/gain/replay/peer_exec_sim.py --gauge-gate --gauge-stubs 1
"""
from __future__ import annotations

import argparse
import ast
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
from vacant import suitespec as ss  # noqa: E402
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


def load_specs(run: str) -> dict[str, "ss.SuiteSpec"]:
    """round452：`peerexec` 只接受 `SuiteSpec`，所以本檔每一條掃描都要先有 spec。

    ⚠ 這改變了本檔舊掃描的**分母**：轉不出 spec 的題目沒有套件可交，會被跳過。
      轉換率是 `r452_suitespec.py --convert` 的產物，逐題落盤在
      `cache/suitespec_<run>.json`，不准在這裡默默補一份假的。

    round452b：每一份 spec 都在這裡**綁上題目的 entry_point**（`ss.validate(...,
    entry_point=...)`）。cache 是資料檔，資料檔可以被改；一份 entry_point 被換成
    `exec` 的 cache 進不了這道門。綁不上的照實丟掉並印出來，不當成「這題沒有 spec」
    默默混進轉換成本裡。
    """
    p = CACHE / f"suitespec_{run}.json"
    if not p.exists():
        raise SystemExit(
            f"缺 spec cache：先跑 ops/gain/replay/r452_suitespec.py --convert {run}")
    d = json.loads(p.read_text())
    tasks, _cands = load_pool(run)
    out, rejected = {}, {}
    for tid, v in d["specs"].items():
        if not v["spec"]:
            continue
        try:
            out[tid] = ss.validate(v["spec"], entry_point=(tasks.get(tid) or {}).get(
                "entry_point"))
        except ss.SuiteSpecError as exc:
            rejected[tid] = str(exc)
    if rejected:
        print(f"⚠ {len(rejected)} 份 spec 綁不上題目的 entry_point，已丟棄："
              f"{sorted(rejected.items())[:5]}", flush=True)
    return out


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

    specs = load_specs(run)
    rows, lie_named, lie_total, hon_named, hon_total = [], 0, 0, 0, 0
    flagged_exec: set[str] = set()
    runs_total = 0
    for tid, codes in sorted(cands.items()):
        t = tasks.get(tid)
        if t is None or tid not in specs:
            continue
        drafts = [(c, f"w{i}") for i, c in enumerate(codes)]
        sel = px.select_by_quorum(t, drafts, execs, roster=roster, suite=specs[tid],
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
    specs = load_specs(run)
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
                    if t is None or tid not in specs:
                        continue
                    sel = px.select_by_quorum(t, [(c, f"w{i}") for i, c in enumerate(codes)],
                                              execs, roster=roster, quorum=k // 2 + 1,
                                              suite=specs[tid],
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
    specs = load_specs(run)
    for tid, codes in sorted(cands.items()):
        t = tasks.get(tid)
        if t is None or tid not in specs:
            continue
        sel = px.select_by_quorum(t, [(c, f"w{i}") for i, c in enumerate(codes)], execs,
                                  roster=roster, quorum=k // 2 + 1, suite=specs[tid],
                                  ts_ms=1_700_000_000_000)
        if not sel.refused:
            continue
        refused += 1
        for vi, v in enumerate(sel.verdicts):
            ch = px.challenge_rerun(t, codes[vi], panel, v, roster=proster,
                                    suite=specs[tid],
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

    ⚠ round749（R449 §四-3）之後這張表要**和 `--gauge-gate` 一起讀**：這裡的 8 格是
      「閘門關著」的世界（保留原樣，因為它是那道閘要擋的東西的量）。同一批題目
      加上量具閘之後，371/371 與 91/91 的 trivial 套件在 **commit 就被拒**，交付與
      假交付都變成 0——但**只有這一類**被擋掉，`--gauge-gate` 的 weak 那一列
      量的就是擋不到的那一類。
    """
    raise SystemExit(
        "round452 之後這張表**跑不動了，而且那正是重點**：`pass` 是一段任意 Python，"
        "`peerexec` 現在只接受 `SuiteSpec`（entry_point ＋ 字面值測資 ＋ 比對設定），"
        "「什麼都不驗」在那個型別裡的唯一寫法是 tests=[]，被 validator 以 "
        "`empty_suite_rejected` 拒絕。舊數字（−6.47pp／−18.68pp、假交付 31%／49%）"
        "留在 `ops/gain/replay/peer_exec_sweep.json` 與 R449／R451 兩份裁決文件裡，"
        "不在這裡重算。殘餘的量測改看 `ops/gain/replay/r452_suitespec.py --gate`。")
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


# ── 套件量具閘（R449 §四-3）：套件要上鏈，先證明它擋得住已知壞草稿 ────────────
GAUGE_NONCE = "r449-suite-gauge-nonce-0001"      # 固定 nonce：重放要可重現（>=16 bytes）
#: 已知壞草稿集合。**驗證者側**的物件：不是任何 worker 的產出、不進任何 prompt、
#: 不進 hidden_check 路徑（V/GT 分離，論證同 `gain_run._canonical_solutions`）。
#: 第 0 個與 `probe_instrument` 的 `stub` 逐字相同（`vacant.suitegauge.broken_stub`），
#: 所以「只用第 0 個」那一欄就是 repo 現成量具的原樣覆蓋率。
def stub_set(entry_point: str | None) -> list[str]:
    ep = entry_point or "_f"
    return [
        px.broken_stub(ep),
        f"def {ep}(*a, **k):\n    return 0\n",
        f"def {ep}(*a, **k):\n    return []\n",
        f"def {ep}(*a, **k):\n    return a[0] if a else None\n",
    ]


def canonical_refs(run: str) -> dict[str, str]:
    """量具的正方向素材：官方（MBPP+）或 round441 手驗（LCB）的參考解。

    ⚠ LCB 只有 12 題有手寫解 ⇒ 79/91 題**量不了**。那不是「量到 0」，是「沒有量具」，
      兩者必須分開報（06-30 稽核紀律）。fail-closed 的後果就是那 79 題上不了鏈——
      這是本修補的直接成本，不准藏進「refused」那一格。
    """
    from ops.gain.gain_run import _canonical_solutions
    return _canonical_solutions(POOLS[run][0])


def weaken_suite(code: str) -> tuple[str | None, int, int]:
    """殘留攻擊的構造：**只留第一條可見驗收**，其餘刪掉。

    回傳 (弱化後的原始碼 or None, 原本幾條, 剩下幾條)。兩種題庫的形狀不同：
      MBPP+  頂層一串 `assert ...` ⇒ 留第一條 assert
      LCB    `__tests = [ {...}, {...} ]` 後面一個 for 迴圈 ⇒ 把表截成一筆
    這套件仍然**通過量具**（參考解過、已知壞樁被擋），所以它量的正是
    「量具擋不到的那一類爛套件」——這道修補的誠實上限。
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None, 0, 0
    asserts = [i for i, n in enumerate(tree.body) if isinstance(n, ast.Assert)]
    if len(asserts) > 1:
        tree.body = [n for i, n in enumerate(tree.body) if i not in asserts[1:]]
        return ast.unparse(tree), len(asserts), 1
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "__tests"
                and isinstance(node.value, ast.List) and len(node.value.elts) > 1):
            n_before = len(node.value.elts)
            node.value.elts = node.value.elts[:1]
            return ast.unparse(tree), n_before, 1
    return None, len(asserts), len(asserts)


def targeted_suite(entry_point: str | None) -> str:
    """**最惡意的通過量具的套件**：逐字認出那組已知壞樁，其餘一律放行。

    這一套驗收一次都沒有呼叫過候選函式。它做的事只有一件：把候選碼的原始碼
    雜湊拿去比對 `stub_set()` 那四個字面，命中就 assert 失敗，沒命中就結束
    （rc=0 ⇒ 通過）。於是量具的兩個方向**滿分**：參考解通過、四個壞樁全被擋，
    而任何一份真候選——不論多爛——都通過。

    ⚠ 它拿得到候選原始碼這件事，是 `vacant/checks.py` 沙箱的一個實測性質，不是
      假設：驗收碼跑在 runner 行程裡，`_worker` 這個 `subprocess.Popen` 物件在它的
      命名空間裡，`_worker.args` 就帶著 `candidate.py` 的路徑（round749 實測，見
      `tests/test_peerexec.py::test_a_suite_can_read_the_candidate_source_from_the_runner`）。
      V/GT 分離沒有被破——讀到的是**候選自己的**產出，不是 hidden_check、不是參考解。
      但「驗收套件看得見候選原始碼」本身要記進誠實邊界：它讓內容定址的白名單／
      黑名單攻擊在這個沙箱上是**可行的**，不只是理論上的。

    ⚠ 即使把這個讀檔管道堵掉，同一類攻擊還有純行為版本（只斷言回傳值不等於那四個
      壞樁會回的東西），見 `tests/test_peerexec.py` 的
      `test_a_behavioural_stub_blacklist_also_passes_the_gauge`。堵管道不是解，
      解是「量具只是下界」這句話要一直掛在收據上。
    """
    digests = sorted(sha(s) for s in stub_set(entry_point))
    return (
        "import hashlib\n"
        f"_known_bad = {digests!r}\n"
        "_p = next(p for p in _worker.args if str(p).endswith('candidate.py'))\n"
        "with open(_p, encoding='utf-8') as _fh:\n"
        "    _src = _fh.read()\n"
        "assert hashlib.sha256(_src.encode('utf-8')).hexdigest() not in _known_bad\n"
    )


def mimic_suite(real_code: str, entry_point: str | None) -> str | None:
    """**這道閘真正的上限**：與真套件逐位相同，只多一句「不是已知壞樁就換掉受測函式」。

    比 `targeted_suite` 難擋一個層次。targeted 自己捏一句 assert 去擋壞樁，所以
    它的**形狀**（`_visible_test_slicer` 認不認得）與**失敗細節**
    （`conform_failure_detail` 的 `first_failing_test`／`n_visible_tests`）都跟真套件
    不一樣——一個被強化成「連失敗的樣子都要對」的量具抓得到它。mimic 不會：

      - 尾端那串 `assert` **逐字保留**（形狀通過 `_visible_test_slicer` 的 A 型），
      - 已知壞樁走的是**原封不動的真套件**（swap 不觸發）⇒ 被擋，而且
        `first_failing_test`／`n_visible_tests`／`loads_ok` 與真套件**逐欄相同**，
      - 其餘任何候選——包括回傳 `'lol'` 的——受測函式已被換成該題自帶的參考解
        `__canon`（MBPP+ 的 `_check_code` 一定會產生它）⇒ 一律通過。

    LCB（B 型：`__tests = [...]` ＋ for 迴圈）沒有 `__canon`，改成把 `__tests` 清空：
    已知壞樁仍跑原表（第一個 `__tests` 沒被動，前綴切片器切的也是它）⇒ 細節相同；
    其餘候選跑零條測資 ⇒ 一律通過。

    ⇒ 把量具從「壞樁被擋?」強化成「壞樁被擋的樣子對不對?」也救不回來。只要已知壞
      集合有限、而且攻擊者看得見它，量具就永遠只是**一組要通過的測資**，不是一個
      對套件品質的保證（`peerexec.SUITE_FIXED_POINT_NOTE`）。
    """
    ep = entry_point or "_f"
    digests = sorted(sha(x) for x in stub_set(ep))
    guard = [
        "import hashlib as __vm_h",
        f"__vm_bad = {digests!r}",
        "__vm_p = next(p for p in _worker.args if str(p).endswith('candidate.py'))",
        "with open(__vm_p, encoding='utf-8') as __vm_f:",
        "    __vm_src = __vm_f.read()",
        "if __vm_h.sha256(__vm_src.encode('utf-8')).hexdigest() not in __vm_bad:",
    ]
    try:
        tree = ast.parse(real_code)
    except SyntaxError:
        return None
    lines = real_code.splitlines()
    # B 型（LCB）：把第一個 `__tests = [...]` 之後接上「非壞樁 ⇒ 清空測資表」。
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "__tests"
                and isinstance(node.value, ast.List)):
            at = node.end_lineno
            return "\n".join(lines[:at] + guard + ["    __tests = []"] + lines[at:]) + "\n"
    # A 型（MBPP+）：尾端連續 assert 前插入「非壞樁 ⇒ 受測函式換成該題的 __canon」。
    asserts = [nd for nd in tree.body if isinstance(nd, ast.Assert)]
    if not asserts or tree.body[-len(asserts):] != asserts or "__canon" not in real_code:
        return None
    at = asserts[0].lineno - 1
    return "\n".join(lines[:at] + guard + [f"    {ep} = __canon"] + lines[at:]) + "\n"


def suite_variants(run: str, tasks, cands) -> dict[str, dict[str, dict]]:
    """每題五套驗收：real（原樣）／trivial（`pass`）／weak（只留第一條）／
    targeted（逐字黑名單那組壞樁，其餘全放行）／mimic（真套件＋一句換函式）。"""
    out: dict[str, dict[str, dict]] = {}
    for tid in cands:
        t = tasks.get(tid)
        if t is None:
            continue
        real = (t.get("visible_check") or {}).get("code") or ""
        weak, nb, na = weaken_suite(real)
        out[tid] = {
            "real": {"code": real, "n_tests": nb},
            "trivial": {"code": TRIVIAL_SUITE_CODE, "n_tests": 0},
            "weak": {"code": weak, "n_tests": na, "n_before": nb},
            "targeted": {"code": targeted_suite(t.get("entry_point")), "n_tests": 0},
            "mimic": {"code": mimic_suite(real, t.get("entry_point")), "n_tests": nb},
        }
    return out


def _gauge_job(job):
    tid, variant, code, ref, ep = job
    from vacant.suitegauge import gauge_suite
    try:
        g = gauge_suite(code, ref, stub_set(ep), entry_point=ep)
    except Exception as exc:                                        # noqa: BLE001
        return tid, variant, {"error": f"{type(exc).__name__}:{exc}"[:160]}
    return tid, variant, g.as_dict()


GAUGE_VARIANTS = ("real", "trivial", "weak", "targeted", "mimic")
#: 「這一格根本沒有量具可用」的理由集合——與「量具擋下來了」必須分開，
#: 否則 r443 那 79 題沒有參考解會被讀成「閘門擋掉 79 題」（06-30 稽核紀律）。
UNGAUGEABLE = ("ungaugeable_no_reference", "not_censused", "not_constructible",
               "gauge_error", "gauge_stub_count_short", "label_error")


def gauge_census(run: str, variants=GAUGE_VARIANTS, workers: int = 6) -> dict:
    """對每題每個變體跑一次量具。落盤成 cache，因為它是純沙箱、可重放。

    **只覆蓋這次算的變體**，其餘沿用舊 cache：census 每一格是 5 次真沙箱
    （參考解＋4 個壞樁），整份重算在有負載的機器上是十幾分鐘，而
    `--gauge-variants targeted` 這種增量只要四分之一。整份重寫會讓一次
    「只想補一個變體」的呼叫安靜毀掉另外三個變體的資料。
    ⚠ 代價：合併意味著舊變體的數字**不是這一次跑出來的**。要重新量整份就明確
      給滿四個變體（本檔預設）。
    """
    tasks, cands = load_pool(run)
    refs = canonical_refs(run)
    sv = suite_variants(run, tasks, cands)
    jobs, missing_ref, no_weak = [], [], []
    for tid, v in sorted(sv.items()):
        ref = refs.get(tid)
        if not ref:
            missing_ref.append(tid)
            continue
        ep = tasks[tid].get("entry_point")
        for name in variants:
            code = v[name]["code"]
            if code is None:
                # weak／mimic 都可能造不出來（形狀認不得）。這是「沒有這一格」，
                # 不是「這一格量到 0」——分開記，別讓兩者在報表上長得一樣。
                no_weak.append(f"{name}:{tid}")
                continue
            jobs.append((tid, name, code, ref, ep))
    print(f"{run}: gauge census — {len(jobs)} runs "
          f"({len(sv)} tasks, {len(missing_ref)} without a reference solution, "
          f"{len(no_weak)} not constructible), {workers} workers", flush=True)
    p_cache = CACHE / f"peerexec_gauge_{run}.json"
    out: dict[str, dict] = {}
    prev: dict = {}
    if p_cache.exists():
        prev = json.loads(p_cache.read_text())
        out = {tid: dict(v) for tid, v in (prev.get("gauge") or {}).items()}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (tid, name, rec) in enumerate(ex.map(_gauge_job, jobs, chunksize=4), 1):
            out.setdefault(tid, {})[name] = rec
            if n % 200 == 0:
                print(f"  {n}/{len(jobs)}", flush=True)
    # `not_weakenable` 只有 weak 那一輪算得出來 ⇒ 增量跑（例如只補 targeted）時要
    # **併**舊值而不是用空 list 蓋掉，否則「這一輪沒算」會被寫成「沒有這種題目」。
    if "weak" not in variants:
        no_weak = list(no_weak) + list(prev.get("not_weakenable") or [])
    res = {"run": run, "gauge": out, "missing_ref": sorted(set(missing_ref)),
           "not_weakenable": sorted(set(no_weak)),
           "variants_last_run": sorted(variants),
           "n_tasks": len(sv)}
    CACHE.mkdir(parents=True, exist_ok=True)
    p_cache.write_text(json.dumps(res, indent=0, sort_keys=True))
    return res


def load_gauge(run: str) -> dict:
    p = CACHE / f"peerexec_gauge_{run}.json"
    if not p.exists():
        raise SystemExit(f"缺 gauge cache：先跑 --gauge-census {run}")
    return json.loads(p.read_text())


def _variant_label_job(job):
    key, code, suite_code, ep = job
    try:
        ok, _ = meets_demand(code, suite_code, 10, entry_point=ep)
    except Exception:                                               # noqa: BLE001
        ok = None
    return key, ok


def build_variant_labels(run: str, variant: str, workers: int = 6) -> dict[str, bool | None]:
    """每個候選在**某一套腐化驗收**下過不過。真沙箱，落在自己的 cache（不動 facts）。

    ⚠ `None`＝那一格的沙箱丟例外（InfraVoid 之類）。它**不是** False：
      `gate_delivery` 會把 None 單獨計成 `label_error` 而不是「沒通過」，
      否則「量不到」會被讀成「這份草稿不合格」（06-30 稽核紀律）。
    """
    tasks, cands = load_pool(run)
    sv = suite_variants(run, tasks, cands)
    jobs = []
    for tid, codes in sorted(cands.items()):
        if tid not in tasks or sv[tid][variant]["code"] is None:
            continue
        for i, c in enumerate(codes):
            jobs.append((f"{tid}#{i}", c, sv[tid][variant]["code"],
                         tasks[tid].get("entry_point")))
    print(f"{run}: {variant}-suite labels for {len(jobs)} candidates "
          f"({workers} workers)", flush=True)
    out: dict[str, bool | None] = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (key, ok) in enumerate(ex.map(_variant_label_job, jobs, chunksize=8), 1):
            out[key] = ok
            if n % 400 == 0:
                print(f"  {n}/{len(jobs)}", flush=True)
    (CACHE / f"peerexec_{variant}_{run}.json").write_text(
        json.dumps(out, indent=0, sort_keys=True))
    return out


def load_variant_labels(run: str, variant: str) -> dict[str, bool | None]:
    p = CACHE / f"peerexec_{variant}_{run}.json"
    if not p.exists():
        raise SystemExit(f"缺 {variant} cache：先跑 --build-variant {variant} {run}")
    return json.loads(p.read_text())


class VariantProbe(HonestProbe):
    """誠實地跑**某一套**驗收（real／trivial／weak／targeted）。誠實在這裡沒有保護力。"""

    def __init__(self, *a, label=None, **kw):
        super().__init__(*a, **kw)
        self.label = label

    def __call__(self, code, task):
        key = self.index[(task["task_id"], sha(code))]
        return px.ProbeResult(bool(self.label(key)), None, 0, True, None)


def gate_delivery(run, variant, *, k=3, workers=6, stub_n=4):
    """把某一套驗收**過一次真的 commit 閘**，再算閘後還交得出什麼。

    每一題：
      1. 用 `px.commit_suite_with_gauge` 把該變體上鏈——量具沒過就 `SuiteGaugeError`，
         **這一題連跑都不跑**（拒交，`n_sandbox_runs=0`）。量具素材取自 cache，
         所以這一步零沙箱（真跑時的成本另外算，見 `--gauge-census` 的 runs 數）。
      2. 過了閘的題目才走 `select_by_quorum`（k 個誠實執行器、真簽章、真鏈）。
    回傳逐題記錄 ＋ 匯總。
    """
    if variant != "real":
        raise SystemExit(
            f"變體 `{variant}` 是一段**任意 Python** 的驗收套件。round452 把套件改成"
            f"資料（`vacant/suitespec.SuiteSpec`）之後它**不可表達**——不是被擋，是"
            f"寫不出來（validator 只收 `ast.literal_eval` 過得了的字面值）。"
            f"R451 的舊數字留在 peer_exec_gauge_gate_k3_s*.json／r451_stateful_gate.json；"
            f"spec 形態下還表達得出來的殘餘（覆蓋不足＋比對旗標）改跑 "
            f"`ops/gain/replay/r452_suitespec.py --gate {run}`。")
    tasks, cands = load_pool(run)
    facts = load_facts(run)
    gauge = load_gauge(run)
    specs = load_specs(run)
    sv = suite_variants(run, tasks, cands)
    # 壞樁數不准超過 census 實際跑過的那組：`GaugeRecord(..., n_broken=len(stubs), ...)`
    # 是**宣告**，census 的 `accepted_stubs` 是證據；宣告大於證據＝這筆合格證在說謊。
    n_avail = len(stub_set(None))
    if not 1 <= stub_n <= n_avail:
        raise SystemExit(f"--gauge-stubs 必須在 1..{n_avail}（收到 {stub_n}）——"
                         f"census 只跑過 {n_avail} 個壞樁，宣告更多等於偽造合格證")
    index = {(tid, sha(c)): f"{tid}#{i}"
             for tid, codes in cands.items() for i, c in enumerate(codes)}
    if variant == "real":
        label = lambda key: facts[key]["visible"]                    # noqa: E731
    elif variant == "trivial":
        label = lambda key: facts[key].get("trivial")                # noqa: E731
    else:
        _vl = load_variant_labels(run, variant)
        label = _vl.get
    probe = VariantProbe(facts, index, label=label)
    execs = [px.Executor(f"x{i}", px.Identity.generate(), px.Logbook(), probe)
             for i in range(k)]
    roster = px.roster_of(execs)
    ident, book = px.Identity.generate(), px.Logbook()
    # 承諾者的公鑰一起帶進閘門：不帶的話，被灌水的量具紀錄在內容上照樣「合格」
    # （見 `tests/test_peerexec.py::test_select_by_quorum_verifies_the_committers_signature...`）。
    committer = px.PublicIdentity(ident.vacant_id, ident.pub)

    rows = []
    for tid, codes in sorted(cands.items()):
        t = tasks.get(tid)
        if t is None:
            continue
        code = sv[tid][variant]["code"]
        rec = (gauge["gauge"].get(tid) or {}).get(variant)
        row = {"task_id": tid, "variant": variant, "committed": False,
               "refuse_reason": None, "refused": True, "delivered_correct": False,
               "false_delivery": False, "contested": False, "n_runs": 0}
        if code is None:
            row["refuse_reason"] = "not_constructible"
        elif rec is None:
            # 「這題沒有參考解」與「這個變體還沒 census 過」是兩件事。合成同一格的話，
            # 忘了跑 `--gauge-census --gauge-variants mimic` 會被報成「79 題沒有參考解」
            # ——一個看起來完全合理、但把「線沒接上」講成「量到了」的數字（06-30 稽核紀律）。
            row["refuse_reason"] = ("ungaugeable_no_reference"
                                    if tid in set(gauge.get("missing_ref") or ())
                                    else "not_censused")
        elif "error" in rec:
            row["refuse_reason"] = "gauge_error"
        elif int(rec.get("n_broken", 0)) < stub_n:
            # cache 是用比 --gauge-stubs 更少的樁跑的 ⇒ 沒有證據支持這張合格證。
            row["refuse_reason"] = "gauge_stub_count_short"
        elif any(label(f"{tid}#{i}") is None for i in range(len(codes))):
            # 沙箱在這一格丟過例外 ⇒ 這題**沒有標籤**，不是「全部沒過」。
            row["refuse_reason"] = "label_error"
        else:
            stubs = list(range(stub_n))
            accepted = [i for i in rec["accepted_stubs"] if i in stubs]
            spec = specs.get(tid)
            if spec is None:
                row["refuse_reason"] = "unconvertible_task"
                rows.append(row)
                continue
            gr = px.GaugeRecord(spec.suite_sha256, rec["ref_sha256"], len(stubs),
                                not accepted, bool(rec["ref_passed"]))
            try:
                entry = px.commit_suite(book, ident, task_id=tid, suite=spec,
                                        nonce=GAUGE_NONCE,
                                        entry_point=t.get("entry_point"), gauge=gr,
                                        ts_ms=1_700_000_000_000)
                row["committed"] = True
            except px.SuiteGaugeError as exc:
                row["refuse_reason"] = str(exc).split(":")[0]
                entry = None
            if entry is not None:
                sel = px.select_by_quorum(
                    t, [(c, f"w{i}") for i, c in enumerate(codes)], execs,
                    roster=roster, quorum=k // 2 + 1, suite=spec, suite_commit=entry,
                    suite_nonce=GAUGE_NONCE, suite_committer=committer,
                    ts_ms=1_700_000_000_000)
                hit = (not sel.refused) and bool(facts[f"{tid}#{sel.shipped_index}"]["hidden"])
                row.update(refused=sel.refused, delivered_correct=hit,
                           false_delivery=(not sel.refused) and not hit,
                           contested=any(v.contested for v in sel.verdicts),
                           n_runs=sel.n_sandbox_runs,
                           refuse_reason=sel.refusal_reason)
        rows.append(row)
    n = len(rows)
    # 「有量具可用」的題目集合＝有參考解、而且這個變體造得出來。real／trivial／weak
    # 三個變體的這個集合**相同**，所以變體之間的 delta 只能在這個分母上比才誠實
    # （r443 有 79 題根本沒有參考解——那是「沒有量具」，不是「量具擋下來」）。
    gaugeable = [r for r in rows if r["refuse_reason"] not in UNGAUGEABLE]
    ng = max(1, len(gaugeable))
    agg = {
        "run": run, "variant": variant, "k": k, "n": n, "stub_n": stub_n,
        "committed": sum(r["committed"] for r in rows),
        "refused_at_commit": sum(not r["committed"] for r in rows),
        "n_gaugeable": len(gaugeable),
        "deliv_acc_gaugeable": sum(r["delivered_correct"] for r in gaugeable) / ng,
        "false_deliv_gaugeable": sum(r["false_delivery"] for r in gaugeable) / ng,
        "refuse_reasons": dict(collections.Counter(
            r["refuse_reason"] for r in rows if not r["committed"])),
        "deliv_acc": sum(r["delivered_correct"] for r in rows) / n,
        "false_deliv": sum(r["false_delivery"] for r in rows) / n,
        "refusal": sum(r["refused"] for r in rows) / n,
        "contested": sum(r["contested"] for r in rows) / n,
        "chain_ok": all(px.verify_executor_chain(e.executor_id, e.book, roster)
                        for e in execs),
    }
    return agg, rows


def gauge_gate_table(runs=("g_r446_eq5_mbpp", "g_r443_gemma_lcb"), k=3, stub_n=4,
                     variants=GAUGE_VARIANTS):
    """R449 §四-3 的收官表：同一批題目，五套驗收，各自過一次真的 commit 閘。

    五個變體讀法（順序就是「這道閘擋掉多少」的遞減順序）：
      real      原樣的可見驗收＝基線。它自己也要過閘（MBPP+ 有 2 題過不了，照實報）。
      trivial   `pass`。§三-3 那一格。**閘門擋掉 100%**。
      weak      只留第一條可見驗收。閘門擋掉一部分（`n_before` 大的擋不掉），
                擋不掉的那些就是殘留損害。
      targeted  逐字黑名單那四個已知壞樁、其餘全放行。**量具滿分、閘門一題都擋不掉**，
                而交付與 trivial 完全一樣——「量具在 commit 前面」的誠實上限。
      mimic     真套件 ＋ 一句「不是已知壞樁就把受測函式換成該題參考解」。形狀、
                測資條數、壞樁的失敗細節都與真套件**逐欄相同**，所以連「比對失敗
                細節」的強化版量具也擋不掉；其餘候選一律放行。上限的最強版本。

    delta 一律在 `gaugeable` 分母上算，並用配對 bootstrap（同一批題目、同一組重抽
    索引，`BOOT_SEED`）給區間；配對是必要的，因為五個變體跑的是**同一批題目**。
    """
    out = []
    print("\n=== 套件量具閘（commit 前必須擋得住已知壞草稿）===")
    print(f"    k={k} 誠實執行器、{stub_n} 個已知壞樁、參考解＝官方／手驗解")
    for run in runs:
        base = None
        base_rows: dict[str, dict] = {}
        for variant in variants:
            try:
                agg, rows = gate_delivery(run, variant, k=k, stub_n=stub_n)
            except SystemExit as exc:
                print(f"  {run[:18]:18s} {variant:8s} SKIP：{exc}")
                continue
            by_task = {r["task_id"]: r for r in rows}
            if variant == "real":
                base = agg["deliv_acc_gaugeable"]
                base_rows = by_task
            agg["delta_pp_vs_real"] = (None if base is None
                                       else 100 * (agg["deliv_acc_gaugeable"] - base))
            # 配對 bootstrap：逐題 (變體交對?) − (real 交對?)，只在兩邊都可量的題目上。
            paired = [int(by_task[tid]["delivered_correct"])
                      - int(base_rows[tid]["delivered_correct"])
                      for tid in sorted(base_rows)
                      if tid in by_task
                      and by_task[tid]["refuse_reason"] not in UNGAUGEABLE
                      and base_rows[tid]["refuse_reason"] not in UNGAUGEABLE]
            lo, hi = boot_ci_multi([[100.0 * x for x in paired]])[0] if paired else (None, None)
            agg["delta_pp_ci95"] = [lo, hi]
            agg["n_paired"] = len(paired)
            out.append(agg)
            d = agg["delta_pp_vs_real"]
            ci = ("" if lo is None or variant == "real"
                  else f" CI95[{lo:+.2f},{hi:+.2f}]")
            print(f"  {run[:18]:18s} {variant:8s} "
                  f"committed={agg['committed']:3d}/{agg['n']:3d} "
                  f"refused_at_commit={agg['refused_at_commit']:3d} "
                  f"deliv={100*agg['deliv_acc']:6.2f}% "
                  f"(gaugeable {agg['n_gaugeable']:3d}: "
                  f"{100*agg['deliv_acc_gaugeable']:6.2f}%, "
                  f"fd={100*agg['false_deliv_gaugeable']:5.2f}%) "
                  f"refuse={100*agg['refusal']:6.2f}% "
                  f"cont={100*agg['contested']:4.1f}% "
                  f"({'baseline' if d is None else f'{d:+.2f}pp vs real'}{ci}) "
                  f"chain={agg['chain_ok']}")
            if agg["refuse_reasons"]:
                print(f"      拒絕理由：{agg['refuse_reasons']}")
    # 檔名帶 k 與壞樁數：`--gauge-stubs 1` 與 `--gauge-stubs 4` 是**兩份不同的量**
    # （1 個樁＝repo 現成量具的原樣覆蓋率），寫進同一個檔名會讓後跑的那次安靜蓋掉前一次。
    p = OUT / f"peer_exec_gauge_gate_k{k}_s{stub_n}.json"
    if len(out) < len(runs) * len(variants):
        # round452：四個原始碼變體現在會 SKIP（不可表達）。這一份輸出因此**不完整**，
        # 寫下去等於用一列 `real` 蓋掉 R451 那份四列的證據。不寫，並說清楚。
        print(f"⚠ 沒有寫 {p.name}：{len(runs) * len(variants) - len(out)} 格 SKIP "
              f"（原始碼變體在 round452 之後不可表達），輸出不完整不得覆蓋 R451 的證據檔。"
              f"殘餘改看 ops/gain/replay/peer_exec_suitespec_gate.json。")
        return out
    p.write_text(json.dumps(out, indent=1))
    print(f"wrote {p}")
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
    ap.add_argument("--gauge-census", nargs="+", metavar="RUN",
                    help="對 real／trivial／weak／targeted／mimic 五套驗收"
                         "各跑一次量具（真沙箱）")
    ap.add_argument("--build-variant", nargs="+", metavar="VARIANT RUN...",
                    help="每個候選在某一套腐化驗收下過不過（真沙箱）。"
                         "第一個參數是變體名（weak／targeted／mimic），其後是 run 名")
    ap.add_argument("--gauge-gate", action="store_true",
                    help="四套驗收各過一次真的 commit 閘，報閘前／閘後的交付")
    ap.add_argument("--gauge-k", type=int, default=3)
    ap.add_argument("--gauge-stubs", type=int, default=4,
                    help="納入判定的已知壞樁數（1＝與 probe_instrument 的樁逐字相同）")
    ap.add_argument("--gauge-variants", nargs="+", default=list(GAUGE_VARIANTS),
                    metavar="VARIANT",
                    help="--gauge-census／--gauge-gate 只處理這幾個變體"
                         "（census 的其餘變體沿用既有 cache）")
    ap.add_argument("--gauge-runs", nargs="+", default=list(POOLS),
                    metavar="RUN", help="--gauge-gate 只跑這幾個池")
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
    if a.gauge_census:
        _bad = [v for v in a.gauge_variants if v not in GAUGE_VARIANTS]
        if _bad:
            raise SystemExit(f"未知變體 {_bad}；可用：{list(GAUGE_VARIANTS)}")
        for r in a.gauge_census:
            if r in POOLS:
                gauge_census(r, variants=tuple(a.gauge_variants), workers=a.workers)
    if a.build_variant:
        _variant, *_runs = a.build_variant
        if _variant not in GAUGE_VARIANTS:
            raise SystemExit(f"未知變體 {_variant}；可用：{list(GAUGE_VARIANTS)}")
        for r in _runs:
            if r in POOLS:
                build_variant_labels(r, _variant, a.workers)
    if a.gauge_gate:
        _bad = [v for v in a.gauge_variants if v not in GAUGE_VARIANTS]
        if _bad:
            raise SystemExit(f"未知變體 {_bad}；可用：{list(GAUGE_VARIANTS)}")
        gauge_gate_table(runs=tuple(a.gauge_runs), k=a.gauge_k, stub_n=a.gauge_stubs,
                         variants=tuple(a.gauge_variants))
    if a.flake:
        flake_table()
    if a.challenge:
        challenge_table()
