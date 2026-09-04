"""等預算選擇規則的離線重放：同樣 5 通呼叫，**篩選**與**投票**誰比較準？

這支在架構裡承重什麼
--------------------
R440X §六 把「等預算版（CONFORM 花滿 5 通再比 OFF5）」列為**目前最重要的未做實驗**：
CONFORM 對 OFF5 的 +3.77pp 是**混淆的**——CONFORM 同時「比較便宜」（1.39–1.51 通）
又「用不同的選擇規則」（執行驗收 vs 行為多數決）。誰帶來增益分不開。
本支把預算軸鎖死：**每條規則都抽滿 5 個候選**，差別只剩選擇規則本身，
於是「準確率來自篩選」與「便宜來自早停」被切開成兩個可獨立回答的問題。

紀律（違反＝結果作廢）
- **零 API 呼叫**。只讀 `runs/<run>/calls.jsonl` 已歸檔的候選文字，本機沙箱執行。
- **V/GT 分離（SPEC §5.3）**：所有規則的「選誰」只准看 `visible_check` 與
  `behavior_signature`（後者只跑 base inputs，無正解）；`hidden_check` 只用來**計分**。
  程式碼層面的保證：`_pick_*` 系列函式的輸入只有 `vis`/`sig`/`depth` 三個欄位，
  它們拿不到 `hid`。
- **不自己重寫判定**：`extract_code` / `meets_demand` / `behavior_signature` /
  `conform_failure_detail` 全部 import 自 `ops.gain.gain_run`，與真跑同一條路徑。
- 不寫 `runs/` 底下任何檔案；事實表（每個候選的 vis/hid/sig/depth）落在本目錄。

規則清單（全部固定 5 通模型呼叫，本機執行免費）
  OFF5_SHIPPED   當時 runtime 落盤的 `rows.jsonl.meets_demand`（**標籤來自另一次執行**）
  OFF5_REPLAY    在**我這份重放標籤**上重跑 OFF5 的行為多數決，平手取抽樣序最前者
                 （真跑 `arm_off5` 平手是隨機抽；隨機平手版的期望值與 bootstrap
                 一併報在「穩健性」那一行，免得基線被平手規則壓低）
  FILTER_FIRST   抽滿 5 個，出貨**抽樣序中第一個通過可見驗收**者；全不過＝拒交
  FILTER_VOTE    抽滿 5 個，只留通過可見驗收者，在其中做行為多數決，平手取最前者；
                 全不過＝拒交
  FILTER_VOTE_FB 同上，但「全不過」時**退化成 OFF5 多數決**而不是拒交
                 （用途：把「篩選的功勞」與「拒交的功勞」拆開）
  DEPTH_BEST     取「通過的可見驗收條數（前綴深度）」最大者，平手取最前者；**永不拒交**
                 （＝題目說的 weighted-by-asserts-passed；亦即「拒交改成交最佳者」）

計分：一律用 `hidden_check`。拒交＝該題不算通過（與 `arm_conform` 的
`accepted=False` 語意一致：沒交出去就不可能滿足需求）。

用法（照這個順序跑就能重現本輪每一個數字）
  export VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz
  .venv/bin/python ops/gain/replay/equal_budget_rules.py facts      [--workers 10]
  .venv/bin/python ops/gain/replay/equal_budget_rules.py crosscheck             # 雜訊地板
  .venv/bin/python ops/gain/replay/equal_budget_rules.py repair     [--workers 8]
  .venv/bin/python ops/gain/replay/equal_budget_rules.py fidelity   [--workers 8]
  .venv/bin/python ops/gain/replay/equal_budget_rules.py report                 # 主表
  .venv/bin/python ops/gain/replay/equal_budget_rules.py report --raw           # 未修標籤
不給 run 名就跑 DEFAULT_RUNS 這五個；`all` ＝ facts（吃快取）＋ report。
事實表快取在 `ops/gain/replay/equal_budget_facts_<run>.json`，刪掉就會重算。
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import pathlib
import random
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
)

from ops.gain.gain_run import (  # noqa: E402
    _visible_test_slicer,
    behavior_signature,
    conform_failure_detail,
    extract_code,
    meets_demand,
)
from vacant.codebench import EvalPlusMBPPLoader, LiveCodeBenchLoader  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
REPO = pathlib.Path(__file__).resolve().parents[3]

# run -> 題庫。r443 是 LCB，其餘 MBPP+。
DEFAULT_RUNS = {
    "g_r441_gemma_only_mbpp_b": "evalplus",
    "g_r356_3arm_20260830": "evalplus",
    "g_r444_conform_mbpp": "evalplus",
    "g_r445_conform_mbpp_ext": "evalplus",
    "g_r443_gemma_lcb": "lcb",
}

RULES = ["OFF5_REPLAY", "FILTER_FIRST", "FILTER_VOTE", "FILTER_VOTE_FB", "DEPTH_BEST"]
BOOT_B = 10000
BOOT_SEED = 5440


# ── 事實表：每個候選的 (visible, hidden, behaviour signature, prefix depth) ──
def _one(job):
    """(key, code, task) -> (key, fact)。在子行程裡跑，每個 check 都是獨立沙箱。"""
    key, code, task = job
    ep = task.get("entry_point")
    fact: dict = {}
    try:
        fact["vis"] = bool(meets_demand(code, task["visible_check"]["code"],
                                        timeout_s=10, entry_point=ep)[0])
    except Exception as exc:                       # InfraVoid 等：記成 None 並計數
        fact["vis"] = None
        fact["vis_err"] = type(exc).__name__
    try:
        fact["hid"] = bool(meets_demand(code, task["hidden_check"]["code"],
                                        timeout_s=10, entry_point=ep)[0])
    except Exception as exc:
        fact["hid"] = None
        fact["hid_err"] = type(exc).__name__
    try:
        fact["sig"] = behavior_signature(code, task)
    except Exception as exc:
        fact["sig"] = None
        fact["sig_err"] = type(exc).__name__

    # 前綴深度：通過可見驗收者＝滿分（純 AST 數條數，零沙箱）；
    # 只有失敗者才值得花沙箱去二分。
    if fact["vis"] is True:
        sl = _visible_test_slicer(task["visible_check"]["code"])
        fact["n_vis"] = sl[0] if sl else None
        fact["depth"] = sl[0] if sl else 10 ** 6   # 切片器認不出形狀也仍是滿分
        fact["depth_kind"] = "full_pass"
    elif fact["vis"] is False:
        try:
            det = conform_failure_detail(code, task)
        except Exception as exc:
            det = {"detail_reason": "exception:" + type(exc).__name__,
                   "n_visible_tests": None, "first_failing_test": None,
                   "loads_ok": None}
        fact["n_vis"] = det.get("n_visible_tests")
        fact["loads_ok"] = det.get("loads_ok")
        fact["detail_reason"] = det.get("detail_reason")
        if det.get("loads_ok") is False:
            fact["depth"], fact["depth_kind"] = -1, "no_load"
        elif det.get("first_failing_test"):
            fact["depth"] = det["first_failing_test"] - 1
            fact["depth_kind"] = "prefix"
        else:
            fact["depth"], fact["depth_kind"] = None, det.get("detail_reason")
    else:
        fact["depth"], fact["depth_kind"] = None, "vis_unknown"
    return key, fact


def load_tasks(bank: str) -> dict:
    """LCB 明確釘 v1：`g_r443_gemma_lcb` 跑的是 v1（91 題，sha256 eb2a5876…）。
    2026-09-04 有平行 session 在加 v2 bank ＋ `VACANT_LCB_VERSION` 環境變數，
    不釘死的話別人 export 一下就會讓這支去載另一份題庫。舊版 loader 沒有
    `version` 參數，所以 TypeError 就退回無參數呼叫（那時預設本來就是 v1）。"""
    if bank == "lcb":
        try:
            loader = LiveCodeBenchLoader(version="v1")
        except TypeError:
            loader = LiveCodeBenchLoader()
    else:
        loader = EvalPlusMBPPLoader(expose_contract=True)
    return {t["task_id"]: t for t in loader.iter_tasks("x")}


def collect_candidates(run: str) -> tuple[dict[str, list[str]], dict[str, bool]]:
    """回傳 (task_id -> OFF5 gen 候選碼，**保持 calls.jsonl 的原始抽樣順序**,
    task_id -> OFF5 當時落盤的 meets_demand)。只收 rows 裡有 OFF5 列的題目。"""
    root = REPO / "runs" / run
    shipped = {}
    for line in (root / "rows.jsonl").open():
        d = json.loads(line)
        if d.get("arm") == "OFF5":
            shipped[d["task_id"]] = bool(d.get("meets_demand"))
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
    return dict(cands), shipped


def collect_off(run: str) -> tuple[dict[str, str], dict[str, bool]]:
    """OFF 臂（每題剛好 1 個候選 ⇒ 對應無歧義）的候選碼與當時落盤的 meets_demand。
    用途：量「重放標籤 vs runtime 標籤」的保真度，也就是 OFF5_SHIPPED 那一欄
    到底能不能拿來跟重放結果比。"""
    root = REPO / "runs" / run
    shipped = {}
    for line in (root / "rows.jsonl").open():
        d = json.loads(line)
        if d.get("arm") == "OFF":
            shipped[d["task_id"]] = bool(d.get("meets_demand"))
    code: dict[str, str] = {}
    for line in (root / "calls.jsonl").open():
        d = json.loads(line)
        meta = d.get("meta") or {}
        if (d.get("role") == "gen" and d.get("ok") and meta.get("arm") == "OFF"
                and meta.get("task_id") in shipped):
            code.setdefault(meta["task_id"], extract_code(d.get("response") or ""))
    return code, shipped


def _one_hidden(job):
    key, code, task = job
    try:
        ok = bool(meets_demand(code, task["hidden_check"]["code"], timeout_s=10,
                               entry_point=task.get("entry_point"))[0])
    except Exception:
        ok = None
    return key, ok


def fidelity(run: str, bank: str, workers: int) -> dict:
    """OFF 臂重放 vs runtime 標籤的一致率（R440P §五-5 的同一道檢查）。"""
    tasks = load_tasks(bank)
    code, shipped = collect_off(run)
    jobs = [(tid, c, tasks[tid]) for tid, c in code.items() if tid in tasks]
    got = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for k, ok in ex.map(_one_hidden, jobs, chunksize=4):
            got[k] = ok
    agree = sum(1 for k, v in got.items() if v is not None and v == shipped[k])
    cons = sum(1 for k, v in got.items() if v is False and shipped[k] is True)
    anti = sum(1 for k, v in got.items() if v is True and shipped[k] is False)
    return {"run": run, "n": len(got), "agree": agree,
            "replay_stricter": cons, "replay_looser": anti,
            "unknown": sum(1 for v in got.values() if v is None)}


def _atomic_write(path: pathlib.Path, text: str) -> None:
    """先寫暫存再 rename——事實表在改寫途中若被另一個 report 讀到會是半截 JSON。"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def _one_repair(job):
    """只重跑「目前標成 False/None」的那幾個檢查。回傳 (key, vis|None, hid|None)。"""
    key, code, task, need_vis, need_hid = job
    ep = task.get("entry_point")
    v = h = None
    if need_vis:
        try:
            v = bool(meets_demand(code, task["visible_check"]["code"], timeout_s=10,
                                  entry_point=ep)[0])
        except Exception:
            v = None
    if need_hid:
        try:
            h = bool(meets_demand(code, task["hidden_check"]["code"], timeout_s=10,
                                  entry_point=ep)[0])
        except Exception:
            h = None
    return key, v, h


def repair(run: str, bank: str, workers: int = 4) -> dict:
    """第二次量測，**只**重跑目前標成 False/None 的檢查，取 OR 寫回事實表。

    為什麼只往一個方向修（這不是選擇性報告，是量具的物理性質）：
    `vacant/checks.py` 的沙箱是 fail-closed——逾時、CPU rlimit、worker 起不來
    一律回 False。所以**假陰性**會發生（尤其機器負載高時），假陽性幾乎不可能
    （要碰巧通過整份 assert）。OR 因此是單調的去雜訊，而且對所有規則一視同仁：
    同一張表、同一批候選，任何規則都吃到同一份修正。

    抓到這件事的方式：本表與 R440P 稽核輪那份獨立重放（`audit_r440p_<run>.json`）
    比對時，不一致**全部**是同一個方向（那份說 hidden 過、本表說沒過），而且集中在
    少數幾題（Mbpp/123、84、389…）——那是題目層級的逾時，不是隨機雜訊。

    誠實邊界：修過的標籤比 runtime 當時的單次量測**寬鬆一點**。原始值保留在
    `vis1`/`hid1`，`report --raw` 用未修版本；兩份都要看。
    """
    tasks = load_tasks(bank)
    facts = json.loads(facts_path(run).read_text())
    cands, _ = collect_candidates(run)
    jobs, flips = [], {"vis": 0, "hid": 0, "checked": 0}
    for tid, codes in cands.items():
        t = tasks.get(tid)
        if t is None:
            continue
        for i, code in enumerate(codes):
            f = facts.get(f"{tid}#{i}")
            if f is None:
                continue
            need_vis = f.get("vis") is not True
            need_hid = f.get("hid") is not True
            if need_vis or need_hid:
                jobs.append(((tid, i), code, t, need_vis, need_hid))
    print(f"[repair] {run}: 重跑 {len(jobs)} 個候選的失敗標籤（{workers} workers）")
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for (tid, i), v, h in ex.map(_one_repair, jobs, chunksize=4):
            f = facts[f"{tid}#{i}"]
            flips["checked"] += 1
            f.setdefault("vis1", f.get("vis"))
            f.setdefault("hid1", f.get("hid"))
            f.setdefault("depth1", f.get("depth"))
            if v is True and f.get("vis") is not True:
                f["vis"] = True
                flips["vis"] += 1
                sl = _visible_test_slicer(tasks[tid]["visible_check"]["code"])
                f["n_vis"] = sl[0] if sl else None
                f["depth"] = sl[0] if sl else 10 ** 6
                f["depth_kind"] = "full_pass_repaired"
            if h is True and f.get("hid") is not True:
                f["hid"] = True
                flips["hid"] += 1
    facts["__repair__"] = flips
    _atomic_write(facts_path(run), json.dumps(facts, indent=1, sort_keys=True))
    print(f"[repair] {run}: vis 翻正 {flips['vis']}，hid 翻正 {flips['hid']}"
          f"（重跑 {flips['checked']} 個候選）")
    return flips


def crosscheck(run: str) -> None:
    """與 R440P 稽核輪那份**獨立腳本、不同時間**的重放比對，量出沙箱重放的雜訊地板。"""
    other = HERE / f"audit_r440p_{run}.json"
    if not other.exists():
        print(f"  {run:<28} 沒有 audit_r440p 快取可比對（r444/r445 是本輪才建的）")
        return
    a = json.loads(other.read_text())
    b = json.loads(facts_path(run).read_text())
    dv = dh = 0
    dh_dir = collections.Counter()
    for k, (v, h) in a.items():
        f = b.get(k)
        if not isinstance(f, dict):
            continue
        if f.get("vis") != v:
            dv += 1
        if f.get("hid") != h:
            dh += 1
            dh_dir[f"audit={h}→now={f.get('hid')}"] += 1
    print(f"  {run:<28} n={len(a):<4} vis 不一致 {dv}  hid 不一致 {dh}  {dict(dh_dir)}")


def facts_path(run: str) -> pathlib.Path:
    return HERE / f"equal_budget_facts_{run}.json"


def build_facts(run: str, bank: str, workers: int, force: bool = False) -> dict:
    path = facts_path(run)
    if path.exists() and not force:
        print(f"[facts] {run}: 用既有快取 {path.name}")
        return json.loads(path.read_text())
    tasks = load_tasks(bank)
    cands, _ = collect_candidates(run)
    jobs = []
    for tid, codes in cands.items():
        t = tasks.get(tid)
        if t is None:
            continue
        for i, code in enumerate(codes):
            jobs.append(((tid, i), code, t))
    print(f"[facts] {run}: {len(cands)} 題 / {len(jobs)} 個候選，{workers} workers")
    out: dict[str, dict] = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (key, fact) in enumerate(ex.map(_one, jobs, chunksize=4), 1):
            out[f"{key[0]}#{key[1]}"] = fact
            if n % 200 == 0:
                print(f"   {n}/{len(jobs)}", flush=True)
    _atomic_write(path, json.dumps(out, indent=1, sort_keys=True))
    print(f"[facts] 寫入 {path}")
    return out


# ── 選擇規則：輸入**只有** vis / sig / depth，拿不到 hid（V/GT 分離的程式碼保證）──
def _buckets(view: list[dict], idxs: list[int]) -> list[list[int]]:
    """依 behaviour signature 分桶，桶的順序＝各桶第一個成員的抽樣序。"""
    order: list[str] = []
    b: dict[str, list[int]] = {}
    for i in idxs:
        sig = view[i]["sig"]
        key = sig if sig is not None else f"__SIG_UNKNOWN_{i}"   # 未知不併桶
        if key not in b:
            b[key] = []
            order.append(key)
        b[key].append(i)
    return [b[k] for k in order]


def _vote_first(view, idxs):
    """多數決，平手取抽樣序最前者。回傳被選中的 index，或 None。"""
    if not idxs:
        return None
    buckets = _buckets(view, idxs)
    top = max(len(x) for x in buckets)
    tied = [x for x in buckets if len(x) == top]
    return min(min(x) for x in tied)


def _vote_dist(view, idxs):
    """真跑 `arm_off5` 的隨機平手：先在平手桶間均勻抽，再在桶內均勻抽。
    回傳 [(index, prob), ...]。"""
    if not idxs:
        return []
    buckets = _buckets(view, idxs)
    top = max(len(x) for x in buckets)
    tied = [x for x in buckets if len(x) == top]
    out = []
    for bkt in tied:
        for i in bkt:
            out.append((i, 1.0 / len(tied) / len(bkt)))
    return out


def _pick(view: list[dict], rule: str):
    """回傳 (picked_index|None, refused: bool)。只看 vis/sig/depth。"""
    n = len(view)
    allidx = list(range(n))
    passers = [i for i in allidx if view[i]["vis"] is True]
    if rule == "OFF5_REPLAY":
        return _vote_first(view, allidx), False
    if rule == "FILTER_FIRST":
        return (passers[0], False) if passers else (None, True)
    if rule == "FILTER_VOTE":
        return (_vote_first(view, passers), False) if passers else (None, True)
    if rule == "FILTER_VOTE_FB":
        return (_vote_first(view, passers) if passers
                else _vote_first(view, allidx)), False
    if rule == "DEPTH_BEST":
        def key(i):
            d = view[i]["depth"]
            return -(10 ** 9) if d is None else d
        best = max((key(i) for i in allidx), default=None)
        return next(i for i in allidx if key(i) == best), False
    raise ValueError(rule)


def _score(view, idx, refused):
    """出貨結果的 hidden 標籤。拒交＝沒交出去＝不算通過。"""
    if refused or idx is None:
        return False
    return view[idx]["hid"] is True


# ── 統計 ──────────────────────────────────────────────────────────
def mcnemar(pairs):
    """pairs: [(a_ok, b_ok)] -> (n, b, c, p)。精確二項雙尾。"""
    b = sum(1 for x, y in pairs if x and not y)
    c = sum(1 for x, y in pairs if y and not x)
    nd = b + c
    if nd == 0:
        return len(pairs), b, c, 1.0
    tail = sum(math.comb(nd, k) for k in range(0, min(b, c) + 1))
    return len(pairs), b, c, min(1.0, 2 * tail / 2 ** nd)


def boot_ci_rand(a_out, off5_dists, b=BOOT_B, seed=BOOT_SEED):
    """規則 a vs 「隨機平手的 OFF5」：每個 bootstrap 複本除了重抽題目，
    還照 `arm_off5` 真正的抽法重擲一次平手。回答「tie→first 是不是把投票基線做弱了」。

    `off5_dists[i]` ＝ 第 i 題的 [(hidden_ok, prob), ...]，機率和為 1。
    """
    n = len(a_out)
    if n == 0:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    reps = []
    for _ in range(b):
        s = 0
        for _ in range(n):
            i = rng.randrange(n)
            u, acc, y = rng.random(), 0.0, False
            for ok, p in off5_dists[i]:
                acc += p
                if u <= acc:
                    y = ok
                    break
            s += (1 if a_out[i] else 0) - (1 if y else 0)
        reps.append(100.0 * s / n)
    reps.sort()
    lo = reps[int(math.floor(0.025 * (b - 1)))]
    hi = reps[int(math.ceil(0.975 * (b - 1)))]
    return lo, hi


def boot_ci(pairs, b=BOOT_B, seed=BOOT_SEED):
    """配對任務 bootstrap：重抽**題目**（配對整體），回傳差值 (pp) 的 95% 百分位區間。"""
    n = len(pairs)
    if n == 0:
        return (float("nan"), float("nan"))
    d = [(1 if x else 0) - (1 if y else 0) for x, y in pairs]
    rng = random.Random(seed)
    reps = [100.0 * sum(rng.choices(d, k=n)) / n for _ in range(b)]
    reps.sort()
    lo = reps[int(math.floor(0.025 * (b - 1)))]
    hi = reps[int(math.ceil(0.975 * (b - 1)))]
    return lo, hi


# ── 每個 run 的重放 ────────────────────────────────────────────────
def replay_run(run: str, bank: str, workers: int, force: bool = False,
               raw: bool = False) -> dict:
    facts = build_facts(run, bank, workers, force)
    if raw:                                  # 回到第一次量測（未 OR 修正）的標籤
        facts = {k: ({**v, "vis": v.get("vis1", v.get("vis")),
                      "hid": v.get("hid1", v.get("hid")),
                      "depth": v.get("depth1", v.get("depth"))}
                     if isinstance(v, dict) else v)
                 for k, v in facts.items()}
    cands, shipped = collect_candidates(run)
    tasks_used, views = [], {}
    incomplete, unknown_cells = [], 0
    for tid, codes in sorted(cands.items()):
        view = []
        for i in range(len(codes)):
            f = facts.get(f"{tid}#{i}")
            if not isinstance(f, dict):
                view = None
                break
            view.append(f)
        if view is None:
            continue
        if len(view) != 5:
            incomplete.append((tid, len(view)))
            continue                       # 等預算的前提就是剛好 5 個候選
        unknown_cells += sum(1 for f in view
                             if f["vis"] is None or f["hid"] is None
                             or f["sig"] is None or f["depth"] is None)
        tasks_used.append(tid)
        views[tid] = view

    res = {
        "run": run, "bank": bank,
        "repair": None if raw else facts.get("__repair__"), "raw": raw,
        "n": len(tasks_used), "tasks": tasks_used,
        "incomplete": incomplete, "unknown_cells": unknown_cells,
        "outcome": {}, "refusals": {}, "picks": {},
        "shipped": [shipped[t] for t in tasks_used],
    }
    for rule in RULES:
        outs, refs, picks = [], 0, []
        for tid in tasks_used:
            idx, refused = _pick(views[tid], rule)
            refs += int(refused)
            picks.append(idx)
            outs.append(_score(views[tid], idx, refused))
        res["outcome"][rule] = outs
        res["refusals"][rule] = refs
        res["picks"][rule] = picks

    # OFF5 隨機平手的期望通過率（真跑 arm_off5 是隨機抽平手，本重放的
    # OFF5_REPLAY 取最前者；把兩者的差距報出來，免得基線被平手規則灌水或壓低）
    dists = []
    for tid in tasks_used:
        v = views[tid]
        dists.append([(v[i]["hid"] is True, p)
                      for i, p in _vote_dist(v, list(range(5)))])
    res["off5_dists"] = dists
    res["off5_replay_ev"] = (
        sum(sum(p for ok, p in d if ok) for d in dists) / len(dists)
        if dists else float("nan"))

    # 早停版的呼叫數：與 FILTER_FIRST 選中同一個候選，只差花掉的呼叫
    used = []
    for tid in tasks_used:
        v = views[tid]
        p = [i for i in range(5) if v[i]["vis"] is True]
        used.append(p[0] + 1 if p else 5)
    res["early_stop_calls"] = sum(used) / len(used) if used else float("nan")

    # 池子上限：至少一個候選 hidden 過（任何選擇規則的天花板）
    res["oracle"] = sum(1 for t in tasks_used
                        if any(f["hid"] is True for f in views[t]))
    # 「五個都沒通過可見」且「五個本來就都錯」＝拒交是對的
    none_vis = [t for t in tasks_used
                if not any(f["vis"] is True for f in views[t])]
    res["no_visible_pass"] = len(none_vis)
    res["refuse_correct"] = sum(1 for t in none_vis
                                if not any(f["hid"] is True for f in views[t]))
    # 機制診斷：為什麼篩選會贏投票？——因為錯誤是相關的，多數決的冠軍常常是
    # 一群「一模一樣的錯答案」。統計「這題明明有候選通過客戶自己的驗收，
    # 但行為多數決的冠軍卻是沒通過的那一種」。
    has_pass = [t for t in tasks_used if any(f["vis"] is True for f in views[t])]
    res["has_visible_passer"] = len(has_pass)
    res["vote_winner_fails_visible"] = sum(
        1 for t in has_pass
        if views[t][_pick(views[t], "OFF5_REPLAY")[0]]["vis"] is not True)
    # 篩選家族內部還有多少空間？——只有「通過可見驗收的候選彼此在 hidden 上不一致」
    # 的題目，任何 tie-break 規則（投票、深度加權、隨便什麼）才可能改變結果。
    # 這個數字是 FILTER_VOTE／DEPTH_BEST 能贏過 FILTER_FIRST 的**上限**。
    def _split(t):
        return len({f["hid"] is True for f in views[t] if f["vis"] is True}) > 1

    def _multisig(t):
        return len({f["sig"] for f in views[t] if f["vis"] is True}) > 1

    res["passers_split_on_hidden"] = sum(1 for t in tasks_used if _split(t))
    # …而其中「投票看得見差異」的（通過者之間行為簽名不只一種）才是投票有機會
    # 出手的題。兩者的落差就是「行為簽名只跑可見測資的輸入」這個設計的直接後果：
    # 通過可見驗收 ⇒ 在那些輸入上輸出正確 ⇒ 簽名幾乎必然相同，投票在這一層是瞎的。
    res["passers_split_and_visible_to_vote"] = sum(
        1 for t in tasks_used if _split(t) and _multisig(t))
    # 可見篩選無損性：hidden 過但 visible 沒過
    res["lossless_violations"] = sum(
        1 for t in tasks_used for f in views[t]
        if f["hid"] is True and f["vis"] is not True)
    res["n_candidates"] = 5 * len(tasks_used)
    return res


# ── 報表 ──────────────────────────────────────────────────────────
def _pct(x, n):
    return f"{x}/{n} = {100.0 * x / n:5.2f}%" if n else "n/a"


def _cmp_line(name, a, b_):
    n, b, c, p = mcnemar(list(zip(a, b_)))
    lo, hi = boot_ci(list(zip(a, b_)))
    diff = 100.0 * (sum(a) - sum(b_)) / n
    ps = f"{p:.4f}" if p >= 1e-4 else f"{p:.1e}"      # 別把 3.8e-06 印成 0.0000
    return (f"  {name:<34} b={b:<3} c={c:<3} n_disc={b + c:<3} p={ps:<8}"
            f"  diff={diff:+6.2f}pp  95%[{lo:+6.2f},{hi:+6.2f}]")


def report(results: list[dict]) -> None:
    for r in results:
        n = r["n"]
        print("\n" + "=" * 96)
        print(f"RUN {r['run']}  (bank={r['bank']})  n={n} 題 × 5 候選 = "
              f"{r['n_candidates']} 個候選")
        if r["incomplete"]:
            print(f"  ⚠ 候選數不足 5 而被排除的題目：{len(r['incomplete'])} "
                  f"{r['incomplete'][:6]}")
        if r.get("raw"):
            print("  【--raw】用第一次量測的標籤，未套用 repair 的假陰性修正")
        if r.get("repair"):
            print(f"  修過的標籤（第二次量測翻正的假陰性）："
                  f"vis {r['repair'].get('vis')}，hid {r['repair'].get('hid')}"
                  f"（重跑 {r['repair'].get('checked')} 個候選）")
        if r["unknown_cells"]:
            print(f"  ⚠ 事實表未知格（沙箱失敗）：{r['unknown_cells']}")
        print(f"  池子上限（≥1 候選 hidden 過）：{_pct(r['oracle'], n)}"
              f"   五候選全錯 {n - r['oracle']} 題")
        print(f"  可見篩選無損性違反（hidden 過但 visible 沒過）："
              f"{r['lossless_violations']} / {r['n_candidates']}")
        print(f"  無任何候選通過可見驗收：{r['no_visible_pass']} 題，"
              f"其中 {r['refuse_correct']} 題本來就沒有正確解（拒交正確）")
        hp = r["has_visible_passer"]
        print(f"  機制：有候選通過可見驗收的 {hp} 題裡，行為多數決的冠軍**沒有**通過"
              f"可見驗收的有 {r['vote_winner_fails_visible']} 題 "
              f"({100.0 * r['vote_winner_fails_visible'] / max(hp, 1):.1f}%)"
              f" ← 多數決常常是「一群一模一樣的錯答案」")
        print(f"\n  {'規則':<16}{'呼叫/題':>8}  {'通過':>18}   拒交")
        shp = r["shipped"]
        print(f"  {'OFF5_SHIPPED':<16}{5.00:>8.2f}  {_pct(sum(shp), n):>18}   -"
              "     ← rows.jsonl，標籤來自當時 runtime")
        for rule in RULES:
            o = r["outcome"][rule]
            print(f"  {rule:<16}{5.00:>8.2f}  {_pct(sum(o), n):>18}   "
                  f"{r['refusals'][rule]}")
        print(f"  （參考，非等預算）OFF5_REPLAY 隨機平手期望通過率 "
              f"{100 * r['off5_replay_ev']:.2f}%；"
              f"FILTER_FIRST 若早停則 {r['early_stop_calls']:.2f} 通/題")

        print("\n  vs OFF5_SHIPPED（rows.jsonl；跨執行標籤，含標籤不對稱）")
        for rule in RULES:
            print(_cmp_line(rule, r["outcome"][rule], shp))
        print("\n  vs OFF5_REPLAY（同一份重放標籤——這是等預算問題的乾淨對照）")
        for rule in RULES:
            if rule == "OFF5_REPLAY":
                continue
            print(_cmp_line(rule, r["outcome"][rule], r["outcome"]["OFF5_REPLAY"]))
        lo, hi = boot_ci_rand(r["outcome"]["FILTER_FIRST"], r["off5_dists"])
        ev_diff = (100.0 * sum(r["outcome"]["FILTER_FIRST"]) / r["n"]
                   - 100.0 * r["off5_replay_ev"])
        print(f"  ↳ 穩健性：FILTER_FIRST vs **隨機平手**的 OFF5（每個 bootstrap "
              f"複本重擲平手）diff={ev_diff:+6.2f}pp 95%[{lo:+6.2f},{hi:+6.2f}]")
        print("\n  規則之間（篩選家族內部）")
        print(f"  ↳ 這一節能有多少空間：通過可見驗收者在 hidden 上意見分歧的有 "
              f"{r['passers_split_on_hidden']} 題（任何 tie-break 規則的上限），"
              f"但其中投票**看得見**差異（通過者的行為簽名不只一種）的只有 "
              f"{r['passers_split_and_visible_to_vote']} 題"
              f" ← 行為簽名只跑可見測資的輸入，通過者在那些輸入上必然一樣")
        print(_cmp_line("FILTER_VOTE vs FILTER_FIRST", r["outcome"]["FILTER_VOTE"],
                        r["outcome"]["FILTER_FIRST"]))
        print(_cmp_line("FILTER_VOTE_FB vs FILTER_FIRST",
                        r["outcome"]["FILTER_VOTE_FB"], r["outcome"]["FILTER_FIRST"]))
        print(_cmp_line("DEPTH_BEST vs FILTER_FIRST", r["outcome"]["DEPTH_BEST"],
                        r["outcome"]["FILTER_FIRST"]))


def pooled(results: list[dict], label: str) -> None:
    print("\n" + "=" * 96)
    print(f"POOLED [{label}]  runs: {', '.join(r['run'] for r in results)}")
    print("  ⚠ 跨 run 併庫**不獨立**：同一題可能在多個 run 出現（r356 ⊂ r441 ＝ r444 的題集），")
    print("    而且併庫本身是序貫加樣本。名目 p 與區間偏樂觀，只能當敘述統計。")
    n = sum(r["n"] for r in results)
    shp = [x for r in results for x in r["shipped"]]
    out = {rule: [x for r in results for x in r["outcome"][rule]] for rule in RULES}
    ref = {rule: sum(r["refusals"][rule] for r in results) for rule in RULES}
    print(f"  n={n}")
    print(f"  {'OFF5_SHIPPED':<16}{5.00:>8.2f}  {_pct(sum(shp), n):>18}   -")
    for rule in RULES:
        print(f"  {rule:<16}{5.00:>8.2f}  {_pct(sum(out[rule]), n):>18}   {ref[rule]}")
    print("\n  vs OFF5_SHIPPED")
    for rule in RULES:
        print(_cmp_line(rule, out[rule], shp))
    print("\n  vs OFF5_REPLAY（同標籤）")
    for rule in RULES:
        if rule == "OFF5_REPLAY":
            continue
        print(_cmp_line(rule, out[rule], out["OFF5_REPLAY"]))
    dists = [d for r in results for d in r["off5_dists"]]
    lo, hi = boot_ci_rand(out["FILTER_FIRST"], dists)
    print(f"  ↳ 穩健性：FILTER_FIRST vs **隨機平手**的 OFF5 95%[{lo:+6.2f},{hi:+6.2f}]")
    print("\n  規則之間")
    print(_cmp_line("FILTER_VOTE vs FILTER_FIRST", out["FILTER_VOTE"],
                    out["FILTER_FIRST"]))
    print(_cmp_line("FILTER_VOTE_FB vs FILTER_FIRST", out["FILTER_VOTE_FB"],
                    out["FILTER_FIRST"]))
    print(_cmp_line("DEPTH_BEST vs FILTER_FIRST", out["DEPTH_BEST"],
                    out["FILTER_FIRST"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["facts", "report", "all", "fidelity",
                                    "repair", "crosscheck"])
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--bank", default=None, help="evalplus|lcb（預設查表）")
    ap.add_argument("--force", action="store_true", help="不吃快取，重算事實表")
    ap.add_argument("--raw", action="store_true",
                    help="用第一次量測的標籤（vis1/hid1），不吃 repair 的修正")
    a = ap.parse_args(argv)

    runs = a.runs or list(DEFAULT_RUNS)
    banks = {r: (a.bank or DEFAULT_RUNS.get(r, "evalplus")) for r in runs}

    if a.cmd == "facts":
        for r in runs:
            build_facts(r, banks[r], a.workers, a.force)
        return

    if a.cmd == "repair":
        for r in runs:
            repair(r, banks[r], max(2, a.workers // 2))
        return

    if a.cmd == "crosscheck":
        print("本表 vs R440P 稽核輪的獨立重放（不同腳本、不同時間、同一批候選）")
        for r in runs:
            crosscheck(r)
        return

    if a.cmd == "fidelity":
        print("OFF 臂（每題 1 個候選、對應無歧義）重放標籤 vs runtime 落盤標籤")
        for r in runs:
            f = fidelity(r, banks[r], a.workers)
            print(f"  {f['run']:<28} n={f['n']:<4} 一致 {f['agree']} "
                  f"({100 * f['agree'] / max(f['n'], 1):.1f}%)  "
                  f"重放較嚴(replay fail/runtime pass)={f['replay_stricter']}  "
                  f"重放較鬆={f['replay_looser']}  未知={f['unknown']}")
        return

    results = [replay_run(r, banks[r], a.workers, a.force, a.raw) for r in runs]
    report(results)

    by = {r["run"]: r for r in results}
    mbpp_disjoint = [by[k] for k in ("g_r444_conform_mbpp", "g_r445_conform_mbpp_ext")
                     if k in by]
    if len(mbpp_disjoint) == 2:
        pooled(mbpp_disjoint, "MBPP+ 題目互斥的兩個 run（371 題，＝R440X 的併庫）")
    alt = [by[k] for k in ("g_r441_gemma_only_mbpp_b", "g_r445_conform_mbpp_ext")
           if k in by]
    if len(alt) == 2:
        pooled(alt, "MBPP+ 題目互斥的另一種切法（r441+r445，371 題）")
    if len(results) > 1:
        pooled(results, "全部 run（題目重複計數，最不獨立）")


if __name__ == "__main__":
    main()
