#!/usr/bin/env python3
"""round452：把驗收套件從**程式**改成**資料**（`vacant/suitespec.SuiteSpec`），量兩件事。

這支在架構裡承重什麼
====================
R451（`DECISION_20260906_R451_FABLE_AUDIT_SUITE_GAUGE.md`）§三-3 的裁決：
**量具量的是一次執行，不是一件工件**——驗收碼是任意 Python，只要它能分辨
「現在是量具在看」與「現在是出貨」，有限次測試對它就沒有約束力。§四 的修法是
把套件改成 `SuiteSpec`（entry_point ＋ 一串 (args, expected) 字面值 ＋ 比對設定），
執行器只跑**自己的**渲染器。本檔量的正是那份修法能不能兌現：

  1. **無損轉換**（`--convert` ＋ `--census`）：371 題 MBPP+ 與 91 題 LCB 全部轉成
     spec，把渲染出來的碼在**真沙箱**上跑過 1855／455 個已歸檔候選，逐格比對
     `cache/peerexec_facts_*.json` 的可見標籤。有一格不同就要指名說明。
  2. **殘餘**（`--matrix` ／ `--flags` ／ `--gate`）：spec 形態裡**還能表達**的攻擊
     只剩兩類——覆蓋不足（少測資）與比對旗標放寬——各自過一次真的 commit 閘
     （真簽章、真鏈、k=3 誠實執行器），量交付掉多少。

round452c：殘餘**要用兩個數字講，不准縮成一個**
================================================
攻擊者（`ops/gain/replay/r452c_generic_gate.py`）指出 R452 的座標少了中間那一格：
`weak_*` 是**盲挑**（第 0 條／亂數），`weak_oracle` 是**事後諸葛**（看得到 5 份候選
與 hidden），而一個**真實**的供應者兩者都不是——他看得到自己那份 spec 的內容、
參考解與已知壞樁，而且可以在本機重試到過量具為止。那一格就是 `generic_gauged`：

    可實現（`generic_gauged`）    假交付 17.93% → 20.65%（**+2.72pp**），交付 −0.82pp
    事後諸葛上限（`weak_oracle`）假交付 **+4.35pp**，交付 −1.63pp

⚠ 舊講法「殘餘＝−8.70pp」（`weak_first` 的交付率）**停用**：那個數字掉的大半是
  **量具把它擋掉**（committed 331/371 vs 完整套件 366），也就是機制在生效；
  它的假交付只 +1.36pp，比會挑的 `generic_gauged` 還低。用交付率當殘餘會把
  「機制擋住了攻擊」讀成「攻擊很成功」——看假交付才看得到攻擊者要的東西。

R451 的三種攻擊（stateful／targeted／mimic）在這裡**沒有欄位可以放**：validator
只收字面值。那不是一個數字，是一個型別性質，釘在
`tests/test_suitespec.py::test_r451_attack_suites_have_no_encoding`。

紀律
----
- 零 API、零模型呼叫、零 `runs/` 寫入（只讀 `runs/<run>/calls.jsonl`）。
- V/GT 分離：`hidden` 只用來**計分**，一處都沒有進入 spec、量具或判決路徑。
- 每一格標籤都是**真沙箱**，不是「從 facts 推導」（R451 已經量過推導會高估）。

用法
----
  .venv/bin/python ops/gain/replay/r452_suitespec.py --convert g_r446_eq5_mbpp g_r443_gemma_lcb
  .venv/bin/python ops/gain/replay/r452_suitespec.py --census g_r446_eq5_mbpp g_r443_gemma_lcb
  .venv/bin/python ops/gain/replay/r452_suitespec.py --matrix g_r446_eq5_mbpp
  .venv/bin/python ops/gain/replay/r452_suitespec.py --flags g_r446_eq5_mbpp
  .venv/bin/python ops/gain/replay/r452_suitespec.py --gate g_r446_eq5_mbpp \\
      --out peer_exec_suitespec_gate_r452c.json     # round452c 那一份（含 generic_*）
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import pathlib
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
)
os.chdir(ROOT)

import peer_exec_sim as sim  # noqa: E402  (同目錄；池子／facts／壞樁共用一份)
from ops.gain.gain_run import meets_demand  # noqa: E402
from vacant import peerexec as px  # noqa: E402
from vacant import suitespec as ss  # noqa: E402

CACHE = sim.CACHE
OUT = HERE
GAUGE_NONCE = "r452-suitespec-nonce"
BOOT_B = 2000
BOOT_SEED = 20260906

#: 覆蓋不足這一類的三個座標。`weak_oracle` 是**事後諸葛**（hindsight）：
#: 它拿已歸檔的 5 份候選與 hidden 標籤去挑最傷的那一條測資，真實攻擊者沒有
#: 這份資料。所以它是**上限**，不是一個會發生的攻擊——報表上必須這樣標。
SINGLE_TEST_VARIANTS = ("weak_first", "weak_rand_s1", "weak_rand_s2", "weak_rand_s3",
                        "weak_oracle")

#: round452c：`weak_*`（盲挑）與 `weak_oracle`（事後諸葛）中間**沒有人量過**的那一格
#: ——一個**真實**的供應者。他看不到候選、看不到 hidden，但他看得到自己那份 spec
#: 的內容（`args`／`expected` 都是他寫的），也看得到參考解與已知壞樁
#: （`commit_suite_with_gauge` 就是拿這兩樣跑量具的，committer 手上一定有）。
#: 選擇規則來自攻擊者的 `ops/gain/replay/r452c_generic_gate.py`（照抄，不是重寫；
#: 兩份的數字在 `--gate` 末尾逐位對帳）。
#:   generic_blind ：挑排名第 1 的，量具過不過就認了。
#:   generic_gauged：照排名往下走，挑**第一個過得了量具**的（供應者本來就可以在
#:                   本機重試到過為止）；全部過不了就照交完整套件。
GENERIC_VARIANTS = ("generic_blind", "generic_gauged")
FLAG_VARIANTS = ("flag_atol", "flag_seteq", "flag_regex")
VARIANTS = ("real", *SINGLE_TEST_VARIANTS, *GENERIC_VARIANTS, *FLAG_VARIANTS)

#: 「退化期望值」——錯的實作最容易剛好命中的那些輸出。純粹從 spec 的 `expected`
#: 字面值判斷，不看候選、不看 hidden。逐字取自 `r452c_generic_gate.DEGENERATE`。
DEGENERATE_EXPECTED = frozenset({
    "0", "1", "-1", "2", "True", "False", "None", "''", '""', "[]", "{}", "()",
    "0.0", "1.0", "b''", "'0'", "'1'", "0j",
})


# ── 轉換 ────────────────────────────────────────────────────────────────────
def _convert_job(job):
    tid, task = job
    c = ss.from_task(task, timeout_s=30.0)
    return tid, (None if c.spec is None else c.spec.to_json()), c.reason


def convert(run: str, workers: int = 6) -> dict:
    """整個池子轉一次 spec。轉不了的**照實記 reason**，不補、不猜。"""
    tasks, cands = sim.load_pool(run)
    jobs = [(tid, tasks[tid]) for tid in sorted(cands) if tid in tasks]
    t0 = time.time()
    print(f"{run}: SuiteSpec 轉換 — {len(jobs)} 題（MBPP+ 每題一個子行程算期望值），"
          f"{workers} workers", flush=True)
    out: dict[str, dict] = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (tid, spec, reason) in enumerate(ex.map(_convert_job, jobs, chunksize=4), 1):
            out[tid] = {"spec": spec, "reason": reason}
            if n % 100 == 0:
                print(f"  {n}/{len(jobs)}  {time.time()-t0:.0f}s", flush=True)
    ok = sum(1 for v in out.values() if v["spec"])
    reasons = collections.Counter(v["reason"].split(":")[0] for v in out.values()
                                  if not v["spec"])
    p = CACHE / f"suitespec_{run}.json"
    p.write_text(json.dumps({"run": run, "n_tasks": len(jobs), "n_converted": ok,
                             "reasons": dict(reasons), "specs": out},
                            indent=0, sort_keys=True))
    print(f"  轉換 {ok}/{len(jobs)}   轉不了 {dict(reasons)}   {time.time()-t0:.0f}s")
    print(f"wrote {p}")
    return out


def load_specs(run: str) -> dict[str, ss.SuiteSpec]:
    """cache → spec，每一份都**綁上題目宣告的 entry_point**（round452b）。

    entry_point 屬於題目不屬於套件。cache 是一個檔案，檔案可以被改；綁在這裡的話，
    一份 entry_point 被換成 `exec` 的 spec 連進記憶體都進不來（`entry_point_mismatch`
    ／`entry_point_reserved`）。綁不上的照實印出來，不默默併進轉換成本。
    """
    p = CACHE / f"suitespec_{run}.json"
    if not p.exists():
        raise SystemExit(f"缺 spec cache：先跑 --convert {run}")
    d = json.loads(p.read_text())
    tasks, _cands = sim.load_pool(run)
    out, rejected = {}, {}
    for tid, v in d["specs"].items():
        if not v["spec"]:
            continue
        try:
            out[tid] = ss.validate(v["spec"],
                                   entry_point=(tasks.get(tid) or {}).get("entry_point"))
        except ss.SuiteSpecError as exc:
            rejected[tid] = str(exc)
    if rejected:
        print(f"⚠ {len(rejected)} 份 spec 綁不上題目的 entry_point，已丟棄："
              f"{sorted(rejected.items())[:5]}", flush=True)
    return out


# ── 無損普查：渲染出來的碼 vs 快取的可見標籤 ────────────────────────────────
def _label_job(job):
    key, code, check_code, ep = job
    try:
        ok, _ = meets_demand(code, check_code, 10, entry_point=ep)
    except Exception:                                               # noqa: BLE001
        ok = None
    return key, ok


def census(run: str, workers: int = 6) -> dict:
    tasks, cands = sim.load_pool(run)
    facts = sim.load_facts(run)
    specs = load_specs(run)
    jobs, skipped = [], []
    rendered: dict[str, str] = {}
    for tid, codes in sorted(cands.items()):
        if tid not in tasks:
            continue
        spec = specs.get(tid)
        if spec is None:
            skipped.append(tid)
            continue
        rendered[tid] = spec.render()
        for i, c in enumerate(codes):
            jobs.append((f"{tid}#{i}", c, rendered[tid], tasks[tid].get("entry_point")))
    t0 = time.time()
    print(f"{run}: 無損普查 — {len(jobs)} 個候選跑渲染後的套件（真沙箱），"
          f"{workers} workers", flush=True)
    labels: dict[str, bool | None] = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (key, ok) in enumerate(ex.map(_label_job, jobs, chunksize=8), 1):
            labels[key] = ok
            if n % 400 == 0:
                print(f"  {n}/{len(jobs)}  {time.time()-t0:.0f}s", flush=True)
    same = diff = err = 0
    mismatches = []
    for key, ok in labels.items():
        want = facts.get(key, {}).get("visible")
        if ok is None or want is None:
            err += 1
            mismatches.append({"key": key, "rendered": ok, "cached": want,
                               "kind": "unmeasurable"})
        elif bool(ok) == bool(want):
            same += 1
        else:
            diff += 1
            mismatches.append({"key": key, "rendered": ok, "cached": want,
                               "kind": "mismatch"})
    byte_identical = sum(1 for tid, code in rendered.items()
                         if code == (tasks[tid].get("visible_check") or {}).get("code"))
    res = {"run": run, "n_tasks": len(cands), "n_specs": len(specs),
           "unconvertible_tasks": sorted(skipped), "n_candidates": len(jobs),
           "same": same, "mismatch": diff, "unmeasurable": err,
           "render_byte_identical_to_loader": byte_identical,
           "mismatches": mismatches[:200],
           "elapsed_s": round(time.time() - t0, 1)}
    (CACHE / f"r452_census_{run}.json").write_text(
        json.dumps({**res, "labels": labels}, indent=0, sort_keys=True))
    print(f"  逐格相同 {same}/{len(jobs)}   不同 {diff}   量不到 {err}   "
          f"渲染碼與 loader 逐位元組相同的題數 {byte_identical}/{len(rendered)}   "
          f"{time.time()-t0:.0f}s")
    for m in mismatches[:20]:
        print(f"   {m['kind']} {m['key']}: rendered={m['rendered']} cached={m['cached']}")
    return res


# ── 逐測資矩陣（覆蓋不足這一類的共用計算）──────────────────────────────────
def single_test_spec(spec: ss.SuiteSpec, j: int,
                     entry_point: str | None = None) -> ss.SuiteSpec:
    """只留第 j 條測資的 spec。

    round452c：重驗時要**帶著題目宣告的 entry_point**。省略參數時退回
    `spec.entry_point`——`load_specs` 已經把每一份 spec 綁過題目了，所以那是同一個
    字串；但**不准**傳 `None`，那在 round452c 之後是「題目那一格是空的 ⇒ 拒」。
    """
    return ss.validate({**spec.to_json(), "tests": [spec.tests[j].to_json()]},
                       entry_point=entry_point or spec.entry_point)


def _matrix_job(job):
    tid, j, code, subjects, ep = job
    out = []
    for name, src in subjects:
        try:
            ok, _ = meets_demand(src, code, 10, entry_point=ep)
        except Exception:                                           # noqa: BLE001
            ok = None
        out.append((name, ok))
    return tid, j, out


def matrix(run: str, workers: int = 6) -> dict:
    """每 (題, 單一測資) 一格：參考解／4 個壞樁／5 個候選各跑一次真沙箱。

    一次算完 weak_first／weak_rand×3／weak_oracle 五個變體要用的全部標籤——
    它們都是「只留一條測資」的套件，差別只在**留哪一條**。分開跑等於把同一批
    沙箱執行做五遍。
    """
    tasks, cands = sim.load_pool(run)
    specs = load_specs(run)
    refs = sim.canonical_refs(run)
    jobs = []
    for tid, codes in sorted(cands.items()):
        spec = specs.get(tid)
        if tid not in tasks or spec is None:
            continue
        ep = tasks[tid].get("entry_point")
        ref = refs.get(tid)
        subjects = [(f"cand{i}", c) for i, c in enumerate(codes)]
        subjects += [(f"stub{s}", src) for s, src in enumerate(sim.stub_set(ep))]
        if ref:
            subjects.append(("ref", ref))
        for j in range(spec.n_tests):
            jobs.append((tid, j, single_test_spec(spec, j, ep).render(), subjects, ep))
    t0 = time.time()
    n_runs = sum(len(j[3]) for j in jobs)
    print(f"{run}: 逐測資矩陣 — {len(jobs)} 格 × ~{n_runs//max(1,len(jobs))} 次沙箱 "
          f"= {n_runs} 次，{workers} workers", flush=True)
    out: dict[str, dict[str, dict[str, bool | None]]] = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (tid, j, res) in enumerate(ex.map(_matrix_job, jobs, chunksize=2), 1):
            out.setdefault(tid, {})[str(j)] = dict(res)
            if n % 100 == 0:
                print(f"  {n}/{len(jobs)}  {time.time()-t0:.0f}s", flush=True)
    p = CACHE / f"r452_matrix_{run}.json"
    p.write_text(json.dumps(out, indent=0, sort_keys=True))
    print(f"  wrote {p}   {time.time()-t0:.0f}s")
    return out


def load_matrix(run: str, tag: str = "r452") -> dict:
    """逐測資矩陣 cache。`tag="r452c"` ＝ 攻擊者在**修補後**的渲染器上重量的那一份。

    round452c：`r452c_matrix_*` 是攻擊者用修補後的渲染器**全量重跑**的
    1143 格／11430 次真沙箱（`ops/gain/replay/r452c_generic_gate.py --sweep`），
    而且與 1cfec80 那份逐格對過：11430/11430 相同、0 不同。generic 變體讀這一份，
    因為它的每一格都是本輪現量的；`weak_*` 讀原本那份，逐位不變才比得出來。
    """
    p = CACHE / f"{tag}_matrix_{run}.json"
    if not p.exists():
        raise SystemExit(f"缺 matrix cache（{tag}）：先跑 --matrix {run}")
    return json.loads(p.read_text())


# ── round452c：非事後諸葛的純資料攻擊（挑最泛的那一條測資）──────────────────
#
# 規則整段搬自攻擊者的 `ops/gain/replay/r452c_generic_gate.py`（`score`／`rank_order`）。
# 搬過來而不是 import：那支 import 本檔，反向 import 會成環；而**照抄**而不是重寫，
# 是因為這裡要重現的是**別人量到的那個數字**，不是我自己想的一個近似規則。
# `--gate` 末尾會拿攻擊者落盤的 aggs 逐位對帳，抄錯了會當場吵。
def generic_score(args_lit: str, expected_lit: str) -> int:
    """供應者手上就有的三個訊號。零候選可見度、零 hidden 可見度。"""
    s = 3 if expected_lit in DEGENERATE_EXPECTED else 0
    if len(expected_lit) <= 2:
        s += 2
    elif len(expected_lit) <= 4:
        s += 1
    if len(args_lit) <= 6:
        s += 1
    return s


def generic_rank_order(spec: ss.SuiteSpec) -> list[int]:
    """供應者的挑選順序。只吃 spec 自己的內容，全確定性、可重算。"""
    keyed = [(-generic_score(t.args, t.expected), len(t.expected), len(t.args), j)
             for j, t in enumerate(spec.tests)]
    return [k[-1] for k in sorted(keyed)]


def _cell_gauge_ok(cell: dict) -> bool:
    """一格「單一測資」的量具：參考解過 ＋ 四個已知壞樁全擋。"""
    return (cell.get("ref") is True
            and all(cell.get(f"stub{s}") is False for s in range(4)))


def _generic_plan(spec: ss.SuiteSpec, cells: dict, variant: str,
                  entry_point: str | None):
    """回傳 `(spec 或 "real", pick, gauge_ok)`。**不看候選、不看 hidden。**"""
    order = generic_rank_order(spec)
    if variant == "generic_blind":
        pick = order[0]
        return single_test_spec(spec, pick, entry_point), pick, _cell_gauge_ok(
            cells[str(pick)])
    if variant == "generic_gauged":
        for pick in order:
            if _cell_gauge_ok(cells[str(pick)]):
                return single_test_spec(spec, pick, entry_point), pick, True
        # 全部過不了量具 ⇒ 攻擊者最好的選擇就是照交完整套件
        # （與 `weak_oracle` 的 fallback 同一條規則）。
        return "real", None, None
    raise SystemExit(f"未知 generic 變體 {variant}")


# ── 旗標放寬 ────────────────────────────────────────────────────────────────
def flag_spec(spec: ss.SuiteSpec, variant: str,
              entry_point: str | None = None) -> ss.SuiteSpec:
    """把比對旗標放寬的 spec。`entry_point` 同 `single_test_spec`（round452c）。"""
    d = spec.to_json()
    if variant == "flag_atol":
        d["cmp"]["atol"] = 1e9
    elif variant == "flag_seteq":
        d["cmp"]["set_equivalent"] = True
    elif variant == "flag_regex":
        d["cmp"]["regex_predicate"] = True
    else:
        raise SystemExit(f"未知旗標變體 {variant}")
    return ss.validate(d, entry_point=entry_point or spec.entry_point)


def flags(run: str, workers: int = 6) -> dict:
    """三種旗標放寬各跑一次：5 個候選 ＋ 參考解 ＋ 4 個壞樁。"""
    tasks, cands = sim.load_pool(run)
    specs = load_specs(run)
    refs = sim.canonical_refs(run)
    jobs = []
    for tid, codes in sorted(cands.items()):
        spec = specs.get(tid)
        if tid not in tasks or spec is None:
            continue
        ep = tasks[tid].get("entry_point")
        ref = refs.get(tid)
        subjects = [(f"cand{i}", c) for i, c in enumerate(codes)]
        subjects += [(f"stub{s}", src) for s, src in enumerate(sim.stub_set(ep))]
        if ref:
            subjects.append(("ref", ref))
        for v in FLAG_VARIANTS:
            jobs.append((tid, v, flag_spec(spec, v, ep).render(), subjects, ep))
    t0 = time.time()
    print(f"{run}: 旗標放寬 — {len(jobs)} 格 × ~10 次沙箱，{workers} workers", flush=True)
    out: dict[str, dict] = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (tid, v, res) in enumerate(ex.map(_matrix_job, jobs, chunksize=2), 1):
            out.setdefault(tid, {})[v] = dict(res)
            if n % 150 == 0:
                print(f"  {n}/{len(jobs)}  {time.time()-t0:.0f}s", flush=True)
    p = CACHE / f"r452_flags_{run}.json"
    p.write_text(json.dumps(out, indent=0, sort_keys=True))
    print(f"  wrote {p}   {time.time()-t0:.0f}s")
    return out


def load_flags(run: str) -> dict:
    p = CACHE / f"r452_flags_{run}.json"
    if not p.exists():
        raise SystemExit(f"缺 flags cache：先跑 --flags {run}")
    return json.loads(p.read_text())


# ── 真閘門 ──────────────────────────────────────────────────────────────────
def _real_gauge_job(job):
    tid, code, ref, ep = job
    from vacant.suitegauge import gauge_suite
    try:
        g = gauge_suite(code, ref, sim.stub_set(ep), entry_point=ep)
    except Exception as exc:                                        # noqa: BLE001
        return tid, {"error": f"{type(exc).__name__}:{exc}"[:160]}
    return tid, g.as_dict()


def real_gauge(run: str, workers: int = 6) -> dict:
    """`real` 變體（完整 spec）的量具普查：每題 1 參考解 ＋ 4 壞樁，真沙箱。"""
    tasks, cands = sim.load_pool(run)
    specs = load_specs(run)
    refs = sim.canonical_refs(run)
    jobs, missing = [], []
    for tid in sorted(cands):
        spec = specs.get(tid)
        if tid not in tasks or spec is None:
            continue
        ref = refs.get(tid)
        if not ref:
            missing.append(tid)
            continue
        jobs.append((tid, spec.render(), ref, tasks[tid].get("entry_point")))
    t0 = time.time()
    print(f"{run}: real spec 量具普查 — {len(jobs)} 題 × 5 次沙箱，{workers} workers",
          flush=True)
    out: dict[str, dict] = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (tid, rec) in enumerate(ex.map(_real_gauge_job, jobs, chunksize=4), 1):
            out[tid] = rec
            if n % 100 == 0:
                print(f"  {n}/{len(jobs)}  {time.time()-t0:.0f}s", flush=True)
    p = CACHE / f"r452_realgauge_{run}.json"
    p.write_text(json.dumps({"gauge": out, "missing_ref": sorted(missing)},
                            indent=0, sort_keys=True))
    ok = sum(1 for r in out.values() if r.get("ok"))
    print(f"  量具通過 {ok}/{len(out)}   沒有參考解 {len(missing)}   {time.time()-t0:.0f}s")
    return out


def load_real_gauge(run: str) -> dict:
    p = CACHE / f"r452_realgauge_{run}.json"
    if not p.exists():
        raise SystemExit(f"缺 real gauge cache：先跑 --gate（它會自己算）")
    return json.loads(p.read_text())


def _variant_plan(run: str, spec: ss.SuiteSpec, tid: str, variant: str,
                  mat: dict, facts: dict, n_cand: int,
                  entry_point: str | None = None):
    """回傳 (spec, labels[list[bool|None]], gauge_ok, gauge_detail)。

    labels 一律取自**真沙箱**的矩陣／旗標 cache，不是推導。
    """
    if variant in SINGLE_TEST_VARIANTS:
        cells = mat.get(tid) or {}
        js = sorted(int(j) for j in cells)
        if not js:
            return None, None, False, "no_matrix"
        gauge_ok = {j: (cells[str(j)].get("ref") is True
                        and all(cells[str(j)].get(f"stub{s}") is False for s in range(4)))
                    for j in js}
        if variant == "weak_first":
            pick = 0
        elif variant.startswith("weak_rand_s"):
            seed = int(variant[-1])
            pick = random.Random(f"{seed}|{tid}").randrange(len(js))
        else:  # weak_oracle
            pick = _oracle_pick(tid, js, cells, gauge_ok, facts, n_cand)
            if pick is None:
                # 沒有任何單一測資過得了量具 ⇒ 攻擊者最好的選擇就是照交真套件。
                return "real", None, True, "oracle_falls_back_to_real"
        labels = [cells[str(pick)].get(f"cand{i}") for i in range(n_cand)]
        return (single_test_spec(spec, pick, entry_point), labels, gauge_ok[pick],
                f"test={pick}")
    raise SystemExit(f"unhandled variant {variant}")


def _oracle_pick(tid, js, cells, gauge_ok, facts, n_cand):
    """事後諸葛：在**過得了量具**的單一測資裡，挑「出貨錯得最兇」的那一條。

    這是 hindsight 上限，不是一個真實攻擊者做得到的事——它需要看得到 5 份候選
    與 hidden 標籤。報表上必須跟 weak_first／weak_rand 分開標示（`oracle=True`）。
    """
    best, best_key = None, None
    for j in js:
        if not gauge_ok[j]:
            continue
        labels = [cells[str(j)].get(f"cand{i}") for i in range(n_cand)]
        ship = next((i for i, v in enumerate(labels) if v is True), None)
        if ship is None:
            wrong, right = 0, 0
        else:
            hid = bool(facts.get(f"{tid}#{ship}", {}).get("hidden"))
            wrong, right = int(not hid), int(hid)
        key = (wrong, -right, -j)
        if best_key is None or key > best_key:
            best_key, best = key, j
    return best


def gate(run: str, k: int = 3, workers: int = 6, variants=VARIANTS) -> dict:
    """每個變體過一次**真的** commit 閘 ＋ `select_by_quorum`（真簽章、真鏈）。"""
    tasks, cands = sim.load_pool(run)
    facts = sim.load_facts(run)
    specs = load_specs(run)
    census_labels = json.loads((CACHE / f"r452_census_{run}.json").read_text())["labels"]
    mat = load_matrix(run)
    # round452c：generic 變體讀攻擊者在**修補後**渲染器上重量的那份矩陣
    # （逐格與上面那份相同，11430/11430；讀哪一份不會改數字，但要說得出讀的是哪一份）。
    mat_c = load_matrix(run, "r452c") if set(variants) & set(GENERIC_VARIANTS) else {}
    flg = load_flags(run)
    if not (CACHE / f"r452_realgauge_{run}.json").exists():
        real_gauge(run, workers=workers)
    rg = load_real_gauge(run)["gauge"]
    refs = sim.canonical_refs(run)

    all_rows: list[dict] = []
    aggs: list[dict] = []
    base_rows: dict[str, dict] = {}
    base_acc = base_false = None
    for variant in variants:
        rows = []
        for tid, codes in sorted(cands.items()):
            t = tasks.get(tid)
            spec = specs.get(tid)
            n_cand = len(codes)
            row = {"task_id": tid, "variant": variant, "committed": False,
                   "refuse_reason": None, "refused": True, "delivered_correct": False,
                   "false_delivery": False, "contested": False, "n_runs": 0,
                   "n_tests": None, "detail": ""}
            if t is None or spec is None:
                row["refuse_reason"] = "unconvertible_task"
                rows.append(row)
                continue
            if variant == "real":
                use, labels = spec, [census_labels.get(f"{tid}#{i}") for i in range(n_cand)]
                rec = rg.get(tid)
                gok = bool(rec and rec.get("ok"))
                detail = "full"
            elif variant in FLAG_VARIANTS:
                cells = (flg.get(tid) or {}).get(variant) or {}
                if not cells:
                    row["refuse_reason"] = "no_flag_cell"
                    rows.append(row)
                    continue
                use = flag_spec(spec, variant, t.get("entry_point"))
                labels = [cells.get(f"cand{i}") for i in range(n_cand)]
                gok = (cells.get("ref") is True
                       and all(cells.get(f"stub{s}") is False for s in range(4)))
                detail = variant
            elif variant in GENERIC_VARIANTS:
                cells = mat_c.get(tid) or {}
                if not cells:
                    # 這一題沒有逐測資的格子 ⇒ 攻擊者沒得挑，照交完整套件。
                    # （攻擊者那支的 `no_cells_fallback_full` 同一條規則。）
                    use, labels = spec, [census_labels.get(f"{tid}#{i}")
                                         for i in range(n_cand)]
                    rec = rg.get(tid)
                    gok, detail = bool(rec and rec.get("ok")), "no_cells_fallback_full"
                else:
                    use, pick, gok = _generic_plan(spec, cells, variant,
                                                   t.get("entry_point"))
                    if use == "real":
                        use, labels = spec, [census_labels.get(f"{tid}#{i}")
                                             for i in range(n_cand)]
                        rec = rg.get(tid)
                        gok, detail = (bool(rec and rec.get("ok")),
                                       "gauge_fallback_full")
                    else:
                        labels = [cells[str(pick)].get(f"cand{i}")
                                  for i in range(n_cand)]
                        detail = f"test={pick}"
                        row["pick"] = pick
            else:
                use, labels, gok, detail = _variant_plan(
                    run, spec, tid, variant, mat, facts, n_cand,
                    t.get("entry_point"))
                if use == "real":
                    use = spec
                    labels = [census_labels.get(f"{tid}#{i}") for i in range(n_cand)]
                    rec = rg.get(tid)
                    gok = bool(rec and rec.get("ok"))
                if use is None:
                    row["refuse_reason"] = detail
                    rows.append(row)
                    continue
            row["n_tests"] = use.n_tests
            row["detail"] = detail
            if any(v is None for v in labels):
                # 沙箱在這一格丟過例外 ⇒ 這題**沒有標籤**，不是「全部沒過」。
                row["refuse_reason"] = "label_error"
                rows.append(row)
                continue
            # 量具紀錄：`n_broken` 是宣告，矩陣／普查的逐格結果是證據。
            gr = px.GaugeRecord(use.suite_sha256, sim.sha(refs.get(tid, "")),
                                4, bool(gok), True)
            ident, book = px.Identity.generate(), px.Logbook()
            committer = px.PublicIdentity(ident.vacant_id, ident.pub)
            try:
                entry = px.commit_suite(book, ident, task_id=tid, suite=use,
                                        nonce=GAUGE_NONCE,
                                        entry_point=t.get("entry_point"), gauge=gr,
                                        ts_ms=1_700_000_000_000)
                row["committed"] = True
            except px.SuiteGaugeError as exc:
                row["refuse_reason"] = str(exc).split(":")[0]
                rows.append(row)
                continue
            probe = _LabelProbe(labels, codes)
            execs = [px.Executor(f"x{i}", px.Identity.generate(), px.Logbook(), probe)
                     for i in range(k)]
            roster = px.roster_of(execs)
            sel = px.select_by_quorum(
                t, [(c, f"w{i}") for i, c in enumerate(codes)], execs, roster=roster,
                quorum=k // 2 + 1, suite=use, suite_commit=entry,
                suite_nonce=GAUGE_NONCE, suite_committer=committer,
                ts_ms=1_700_000_000_000)
            hit = (not sel.refused) and bool(facts[f"{tid}#{sel.shipped_index}"]["hidden"])
            row.update(refused=sel.refused, delivered_correct=hit,
                       false_delivery=(not sel.refused) and not hit,
                       contested=any(v.contested for v in sel.verdicts),
                       n_runs=sel.n_sandbox_runs,
                       refuse_reason=sel.refusal_reason)
            row["chain_ok"] = all(px.verify_executor_chain(e.executor_id, e.book, roster)
                                  for e in execs)
            rows.append(row)
        by_task = {r["task_id"]: r for r in rows}
        n = len(rows)
        # 「轉得出 spec 的題目」是**所有變體共同的**分母：轉不出來的 3 題沒有套件，
        # 那是轉換成本不是變體效果。兩個分母都報，免得 delta 被讀成「攻擊造成的」。
        conv = [r for r in rows if r["refuse_reason"] != "unconvertible_task"]
        nc = max(1, len(conv))
        agg = {
            "run": run, "variant": variant, "k": k, "n": n,
            "oracle": variant == "weak_oracle",
            # round452c：這一格是不是**可實現的**攻擊（只用供應者手上有的資訊）。
            # 兩個布林分開放，是為了讓讀 JSON 的人不必記住哪個變體名是哪一類。
            "realisable": variant in GENERIC_VARIANTS,
            "committed": sum(r["committed"] for r in rows),
            "refused_at_commit": sum(not r["committed"] for r in rows),
            "n_convertible": len(conv),
            "deliv_acc_convertible": sum(r["delivered_correct"] for r in conv) / nc,
            "false_deliv_convertible": sum(r["false_delivery"] for r in conv) / nc,
            "deliv_acc": sum(r["delivered_correct"] for r in rows) / n,
            "false_deliv": sum(r["false_delivery"] for r in rows) / n,
            "refusal": sum(r["refused"] for r in rows) / n,
            "contested": sum(r["contested"] for r in rows) / n,
            "mean_n_tests": (sum(r["n_tests"] or 0 for r in rows)
                             / max(1, sum(1 for r in rows if r["n_tests"]))),
            "refuse_reasons": dict(collections.Counter(
                r["refuse_reason"] for r in rows if not r["committed"])),
            "chain_ok": all(r.get("chain_ok", True) for r in rows),
        }
        if variant == "real":
            base_acc, base_rows = agg["deliv_acc_convertible"], by_task
            base_false = agg["false_deliv_convertible"]
        agg["delta_pp_vs_real"] = (None if base_acc is None
                                   else 100 * (agg["deliv_acc_convertible"] - base_acc))
        agg["false_delta_pp_vs_real"] = (
            None if base_acc is None
            else 100 * (agg["false_deliv_convertible"] - base_false))
        paired = [int(by_task[tid]["delivered_correct"])
                  - int(base_rows[tid]["delivered_correct"])
                  for tid in sorted(base_rows)
                  if tid in by_task
                  and by_task[tid]["refuse_reason"] != "unconvertible_task"]
        agg["ci95_pp"] = _boot_ci(paired)
        agg["n_paired"] = len(paired)
        aggs.append(agg)
        all_rows.extend(rows)
        d = agg["delta_pp_vs_real"]
        fd = agg["false_delta_pp_vs_real"]
        tag = ""
        if agg["oracle"]:
            tag = "   ← ORACLE（事後諸葛，上限）"
        elif variant == "generic_gauged":
            tag = "   ← 可實現（供應者手上的資訊）"
        print(f"  {variant:16s} committed {agg['committed']:3d}/{agg['n']}  "
              f"deliv {100*agg['deliv_acc_convertible']:6.2f}%  "
              f"false {100*agg['false_deliv_convertible']:5.2f}%  "
              f"delta {d:+.2f}pp CI95[{agg['ci95_pp'][0]:+.2f},{agg['ci95_pp'][1]:+.2f}]  "
              f"false_delta {fd:+.2f}pp" + tag, flush=True)
    return {"aggs": aggs, "rows": all_rows}


class _LabelProbe:
    """誠實執行器：跑渲染後的套件、回放**真沙箱**量到的那一格標籤。

    為什麼可以回放：渲染是確定性的，同一份 spec 在 k 台機器上渲染出同一份碼；
    確定性套件 ⇒ 誠實執行器依建構一致（`peer_exec_sim.HonestProbe` 的同一條假設，
    也是它的同一條邊界——沙箱抖動沒有被模型化）。
    """

    def __init__(self, labels, codes):
        self.by_sha = {sim.sha(c): labels[i] for i, c in enumerate(codes)}

    def __call__(self, code, task):
        return px.ProbeResult(bool(self.by_sha.get(sim.sha(code))), None, 0, True, None)


def _boot_ci(paired, b=BOOT_B, seed=BOOT_SEED):
    if not paired or all(v == 0 for v in paired):
        return [0.0, 0.0]
    rng = random.Random(seed)
    n = len(paired)
    means = []
    for _ in range(b):
        means.append(sum(paired[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return [round(100 * means[int(0.025 * b)], 2), round(100 * means[int(0.975 * b) - 1], 2)]


#: `--gate` 之後的對帳來源：哪幾個變體要跟哪一份既有證物逐位相同。
#: round452c 的主張有兩半，兩半都必須是**可核對的**而不是宣稱的：
#:   (a) 修補沒有動到既有的數字 ⇒ `real`／`weak_*`／`flag_*` 對 R452b 那份逐位相同；
#:   (b) 新增的兩格是**攻擊者量到的那個數字** ⇒ `generic_*` 對攻擊者那份逐位相同。
RECONCILE_AGAINST = (
    ("peer_exec_suitespec_gate_r452b.json",
     ("real", *SINGLE_TEST_VARIANTS, *FLAG_VARIANTS)),
    ("r452c_generic_gate.json", GENERIC_VARIANTS),
)
#: 對帳看哪幾個欄位。挑的是**結果**欄位，不是描述欄位（`refuse_reasons` 之類的
#: dict 在兩支之間鍵序可能不同，比它只會製造假警報）。
RECONCILE_FIELDS = ("n_convertible", "committed", "deliv_acc_convertible",
                    "false_deliv_convertible", "mean_n_tests")


def reconcile(aggs) -> list[dict]:
    """把本次的 aggs 跟既有證物逐位對帳，回傳（並印出）每一格的結論。

    這支不修任何東西，只負責讓「逐位不變」這句話**有東西可看**。找不到對照檔就
    照實記 `missing`，不當成通過——「沒比」與「比過了相同」在報告裡不准長得一樣。
    """
    out = []
    for fname, variants in RECONCILE_AGAINST:
        p = OUT / fname
        if not p.exists():
            out.append({"against": fname, "status": "missing"})
            print(f"  ⚠ 對照檔不存在：{fname}")
            continue
        ref = {a["variant"]: a for a in json.loads(p.read_text())["aggs"]}
        for v in variants:
            mine, theirs = ({a["variant"]: a for a in aggs}).get(v), ref.get(v)
            if mine is None or theirs is None:
                out.append({"against": fname, "variant": v, "status": "absent"})
                print(f"  ⚠ {v:16s} 對照缺席（本次 {mine is not None}／"
                      f"對照 {theirs is not None}）")
                continue
            diffs = {f: [mine.get(f), theirs.get(f)] for f in RECONCILE_FIELDS
                     if mine.get(f) != theirs.get(f)}
            out.append({"against": fname, "variant": v,
                        "status": "identical" if not diffs else "differs",
                        "diffs": diffs})
            print(f"  {v:16s} vs {fname}: "
                  + ("逐位相同" if not diffs else f"不同 {diffs}"))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--convert", nargs="+", metavar="RUN")
    ap.add_argument("--census", nargs="+", metavar="RUN")
    ap.add_argument("--matrix", nargs="+", metavar="RUN")
    ap.add_argument("--flags", nargs="+", metavar="RUN")
    ap.add_argument("--gate", nargs="+", metavar="RUN")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--k", type=int, default=3)
    # round452b：`--out` 讓修補後的重跑寫到**新檔**。R452 的證物
    # （peer_exec_suitespec_gate.json）不准被覆蓋——覆蓋掉就沒有「修補前後逐位比對」
    # 這件事可做了。
    ap.add_argument("--out", default="peer_exec_suitespec_gate.json", metavar="NAME")
    a = ap.parse_args()
    for run in a.convert or []:
        convert(run, workers=a.workers)
    for run in a.census or []:
        census(run, workers=a.workers)
    for run in a.matrix or []:
        matrix(run, workers=a.workers)
    for run in a.flags or []:
        flags(run, workers=a.workers)
    if a.gate:
        out = []
        print("\n=== SuiteSpec 殘餘：套件是資料之後還表達得出來的攻擊 ===")
        print(f"    k={a.k} 誠實執行器、4 個已知壞樁、真簽章真鏈")
        for run in a.gate:
            res = gate(run, k=a.k, workers=a.workers)
            out.append(res)
        aggs = [r for x in out for r in x["aggs"]]
        print("\n=== 殘餘表（完整）===")
        print(f"{'variant':16s} {'commit':>7s} {'deliv%':>8s} {'Δdeliv':>8s} "
              f"{'false%':>8s} {'Δfalse':>8s} {'n_tests':>8s}  註")
        for g in aggs:
            note = ("ORACLE 上限（事後諸葛）" if g["oracle"]
                    else "可實現（供應者側資訊）" if g["variant"] == "generic_gauged"
                    else "")
            print(f"{g['variant']:16s} {g['committed']:3d}/{g['n']:3d} "
                  f"{100*g['deliv_acc_convertible']:8.2f} "
                  f"{g['delta_pp_vs_real']:+8.2f} "
                  f"{100*g['false_deliv_convertible']:8.2f} "
                  f"{g['false_delta_pp_vs_real']:+8.2f} "
                  f"{g['mean_n_tests']:8.3f}  {note}")
        print("\n=== 對帳（修補沒動到舊數字／新兩格＝攻擊者量到的那個數字）===")
        recon = reconcile(aggs)
        payload = {"aggs": aggs, "rows": [r for x in out for r in x["rows"]],
                   "reconciliation": recon}
        p = OUT / a.out
        p.write_text(json.dumps(payload, indent=1, sort_keys=True))
        print(f"wrote {p}")


if __name__ == "__main__":
    main()
