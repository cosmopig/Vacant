#!/usr/bin/env python3
"""R453：跨機**真跑**多方執行——三台機器各自開沙箱、各自簽自己的鏈。零模型呼叫。

這支在架構裡承重什麼：它是 R449 §七-1 那條推翻條件的唯一實驗裝置。

    R449 §七-1：若真跑（非重放）的多方執行在門檻以下出現與單執行器不同的
    交付決定 ⇒「逐位相同」是重放假象。

在它之前，`peer_exec_sim.py`／`r452_suitespec.py` 的 k 個「執行器」共用同一份
`facts` cache 或同一支 `_LabelProbe`，所以「k 台一致」是恆真句不是量測
（R452 §四已把這件事列在誠實邊界裡）。本檔把執行器搬到三台真機器上：
每台自己 `SuiteSpec.render()`、自己跑 `vacant/checks.py` 的沙箱、自己用
自己的 Ed25519 金鑰簽進自己的 `Logbook`；合票在 Mac 上用
`peerexec.form_verdict`（帶量具白名單、帶 `render_sha256`）＋
`select_by_quorum` 的同一條早停迴圈。

預註冊：`DECISION_20260906_R453_REAL_MULTIPARTY_PREREG.md`（P-1…P-6、窗口、
判定規則、fallback 都寫在那裡，本檔只負責產生數字）。

兩個角色
--------
    # 在每一台機器上（含 Mac 自己）
    python3 ops/gain/replay/peer_exec_real.py --role executor \
        --run g_r446_eq5_mbpp --specs <specs.json> --pool <pool.json> \
        --identity <keydir> --out <att.ndjson> --workers 6

    # 只在 Mac 上
    python3 ops/gain/replay/peer_exec_real.py --role verdict \
        --run g_r446_eq5_mbpp --specs <specs.json> --pool <pool.json> \
        --books ops/gain/replay/r453/att_mac.ndjson ... \
        --out ops/gain/replay/r453/r453_result.json

紅線
----
- **零模型呼叫**：本檔沒有任何網路路徑；`sandbox_probe` 只 import
  `ops.gain.gain_run` 的判準函式（`meets_demand`／`conform_failure_detail`），
  那兩支只開本機 subprocess。
- **判準不重寫**：探針一律走 `peerexec.sandbox_probe`（＝出貨閘門用的同一份
  `meets_demand`）。在這裡重寫一份「長得像的」判準等於多出第二套規格，
  正是 `conform_failure_detail` 的 docstring 已經寫過的坑。
- **`hidden_check` 只計分**：遠端機器完全不碰它；`--role verdict` 從 Mac 既有的
  `peerexec_facts_*` cache 讀 hidden 標籤，只用來算交付正確／假交付。
- **一條鏈不並行**：沙箱在 N 個 worker 行程裡真跑，簽章與串鏈在主行程依固定
  順序序列化。worker 回傳它自己那次真跑的 `ProbeResult` **與它算的
  `render_sha256`**；主行程用自己算的 render sha 比對，不符就記成
  `render_local_mismatch` 異常而不是默默吃掉。這不是重放別台的結果，
  是同一台機器同一次執行的結果換一個行程去簽。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

_HERE = pathlib.Path(__file__).resolve()
#: 本檔可能被放在 repo 內（Mac）或 scratch 目錄旁（遠端解開的 git archive）。
#: `--repo` 明著指定時以它為準；否則往上找有 `vacant/peerexec.py` 的那一層。
def _guess_repo(explicit: str | None) -> pathlib.Path:
    if explicit:
        return pathlib.Path(explicit).resolve()
    for p in [_HERE.parents[3], *_HERE.parents]:
        if (p / "vacant" / "peerexec.py").exists():
            return p
    return _HERE.parents[3]


_REPO = _guess_repo(os.environ.get("R453_REPO"))
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from vacant import peerexec as px  # noqa: E402
from vacant import suitespec as ss  # noqa: E402
from vacant.identity import Identity, PublicIdentity  # noqa: E402
from vacant.logbook import LogEntry, Logbook  # noqa: E402

#: 承重檔案：三台機器上這幾支的 sha256 必須逐位相同，否則「跨機一致」講的是
#: 兩份不同的程式碼碰巧同意。逐檔落盤進 `pub_<machine>.json`。
LOAD_BEARING = (
    "vacant/peerexec.py", "vacant/suitespec.py", "vacant/checks.py",
    "vacant/logbook.py", "vacant/identity.py", "ops/gain/gain_run.py",
    "ops/gain/replay/peer_exec_real.py",
)

#: 量具 commit 的 nonce。固定值：本輪的 commit-reveal 不做 hiding
#: （`commit_suite` 的 docstring 已寫明承諾 binding 但不 hiding），
#: 隨機 nonce 只會讓結果不可重算。
GAUGE_NONCE = "r453-real-multiparty-20260906"

#: 簽章時間戳釘死：牆鐘進 `pub_*.json` 的量測欄位，不進 payload。
#: 讓 ts 進 payload 會使「同一台機器重跑」產出不同的 entry hash，
#: 那會把「可重算」變成一句空話。
TS_MS = 1_700_000_000_000


def sha256_text(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def _git(*a: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(_REPO), *a], capture_output=True,
                             text=True, timeout=15)
    except Exception:  # noqa: BLE001
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def machine_info() -> dict:
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "python": sys.version,
        "python_version": platform.python_version(),
        "executable": sys.executable,
        "repo": str(_REPO),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "file_sha256": {
            f: (sha256_text((_REPO / f).read_text(encoding="utf-8"))
                if (_REPO / f).exists() else None)
            for f in LOAD_BEARING
        },
        "cpu_count": os.cpu_count(),
    }


# ── 載入輸入 ────────────────────────────────────────────────────────────────
def load_specs(path: str) -> dict[str, dict]:
    """`cache/suitespec_<run>.json` 的格式：`{"specs": {tid: {"spec": {...}}}}`。

    這裡**不**綁 entry_point——綁定是 `Executor.attest`／`as_suite_spec` 的工作，
    而題目的 entry_point 來自 `--pool`（題庫那一側），不是來自 spec 檔。
    在這裡先綁一次只會把「cache 被改過」這件事提前吃掉。
    """
    d = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    return {t: v["spec"] for t, v in d["specs"].items() if v.get("spec")}


def load_pool(path: str) -> dict:
    """`{"run":…, "tasks": {tid: {"entry_point":…, "timeout":…}}, "candidates": {tid: [code…]}}`

    **只有抽出來的候選碼**會被送到別台機器：prompt、reviewer 紀錄、
    `calls.jsonl` 本身都留在 Mac。執行器本來就只看得到草稿碼。
    """
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def build_jobs(specs: dict[str, dict], pool: dict,
               limit: int = 0) -> list[tuple]:
    """固定順序：`sorted(task_id)` × 候選索引。三台機器據此產生**同構的**鏈。"""
    tasks, cands = pool["tasks"], pool["candidates"]
    jobs = []
    for tid in sorted(specs):
        if tid not in tasks or tid not in cands:
            continue
        t = tasks[tid]
        for i, code in enumerate(cands[tid]):
            jobs.append((tid, i, code, t.get("entry_point"), t.get("timeout") or 8,
                         specs[tid]))
    if limit:
        keep = sorted(specs)[:limit]
        jobs = [j for j in jobs if j[0] in set(keep)]
    return jobs


# ── 角色一：執行器 ──────────────────────────────────────────────────────────
def _probe_job(job: tuple) -> tuple:
    """在 worker 行程裡真跑一格：渲染 → 沙箱 → `ProbeResult`。

    刻意複製 `Executor.attest` 的前三行（`as_suite_spec` → `render()` →
    組 view → `self.probe`）而不是呼叫 `attest`：`attest` 會 append 進鏈，
    而鏈在主行程。渲染的 sha 一起回傳給主行程核對，兩邊不符就是異常。
    """
    tid, i, code, ep, timeout, spec_json = job
    try:
        spec = px.as_suite_spec(spec_json, ep)
        rendered = spec.render()
        view = {
            "task_id": tid, "entry_point": ep,
            "visible_check": {"type": "run_python", "code": rendered,
                              "timeout": timeout},
        }
        t0 = time.perf_counter()
        # 刻意**不**傳 timeout_s：`Executor.attest` 呼叫 `self.probe(code, view)`
        # 也不傳，所以真實路徑上生效的是 `sandbox_probe` 自己的 10 秒預設，
        # 不是題目 `visible_check.timeout` 那個 8（那一欄只被 attest 抄進 view）。
        # 在這裡「順手修正」成 8 會讓本輪量的東西跟出貨路徑不是同一條。
        res = px.sandbox_probe(code, view)
        dt = time.perf_counter() - t0
        return (tid, i, res.as_payload(), sha256_text(rendered),
                spec.suite_sha256, round(dt * 1000, 3), None)
    except Exception as exc:  # noqa: BLE001
        return (tid, i, None, None, None, None, f"{type(exc).__name__}:{exc}"[:300])


class _RecordedProbe:
    """把 worker 行程剛剛真跑出來的結果交給 `Executor.attest` 去簽。

    ⚠ 這**不是**重放另一台機器的標籤（那正是 R449 §七-1 要推翻的東西）。
      它重放的是**本機、本次執行**的沙箱結果，只是換一個行程去簽名——
      因為一條 hash-chain 的 append 不能並行。
    """

    def __init__(self) -> None:
        self.current: px.ProbeResult | None = None

    def __call__(self, code: str, task) -> px.ProbeResult:  # noqa: ANN001
        assert self.current is not None, "probe 沒有被餵入本格的結果"
        return self.current


def run_executor(args) -> int:  # noqa: ANN001
    specs = load_specs(args.specs)
    pool = load_pool(args.pool)
    jobs = build_jobs(specs, pool, limit=args.limit)
    keydir = pathlib.Path(args.identity)
    if (keydir / "identity.key").exists():
        ident = Identity.load(keydir)
    else:
        ident = Identity.generate()
        ident.save(keydir)
    probe = _RecordedProbe()
    ex = px.Executor(args.executor_id, ident, Logbook(), probe)

    print(f"[{args.executor_id}] {len(jobs)} 格（{len(specs)} 題），"
          f"{args.workers} workers，repo={_REPO}", flush=True)
    t_start = time.time()
    results: dict[tuple[str, int], tuple] = {}
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as pool_ex:
            for n, r in enumerate(pool_ex.map(_probe_job, jobs, chunksize=4), 1):
                results[(r[0], r[1])] = r
                if n % 200 == 0:
                    print(f"  probe {n}/{len(jobs)}  {time.time()-t_start:.0f}s",
                          flush=True)
    else:
        for n, j in enumerate(jobs, 1):
            r = _probe_job(j)
            results[(r[0], r[1])] = r
            if n % 200 == 0:
                print(f"  probe {n}/{len(jobs)}  {time.time()-t_start:.0f}s",
                      flush=True)
    t_probe = time.time() - t_start

    # ── 序列化簽章：固定順序 ⇒ 三台機器的鏈是同構的（seq 對得起來）
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_err = n_render_mismatch = 0
    t_sign0 = time.time()
    with out_path.open("w", encoding="utf-8") as fh:
        for tid, i, code, ep, timeout, spec_json in jobs:
            r = results.get((tid, i))
            rec = {"task_id": tid, "cand_index": i,
                   "draft_sha256": sha256_text(code)}
            if r is None or r[6] is not None:
                rec["error"] = (r[6] if r else "missing_probe_result")
                n_err += 1
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
                continue
            _, _, payload, w_render_sha, w_suite_sha, ms, _ = r
            spec = px.as_suite_spec(spec_json, ep)
            m_render_sha = sha256_text(spec.render())
            if m_render_sha != w_render_sha or spec.suite_sha256 != w_suite_sha:
                # 同一台機器的兩個行程渲染出不同的位元組 ⇒ 這不是「跨機不可攜」，
                # 是本機出了更嚴重的事。照實記，不簽。
                rec["error"] = "render_local_mismatch"
                rec["worker_render_sha256"] = w_render_sha
                rec["main_render_sha256"] = m_render_sha
                n_render_mismatch += 1
                n_err += 1
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
                continue
            probe.current = px.ProbeResult(
                bool(payload["visible_ok"]), payload["first_failing_test"],
                payload["n_visible_tests"], payload["loads_ok"],
                payload["detail_reason"])
            task = {"task_id": tid, "entry_point": ep,
                    "visible_check": {"timeout": timeout}}
            att = ex.attest(task, code, suite=spec, ts_ms=TS_MS)
            rec.update({
                "suite_sha256": spec.suite_sha256,
                "render_sha256": m_render_sha,
                "visible_ok": bool(att.visible_ok),
                "first_failing_test": payload["first_failing_test"],
                "n_visible_tests": payload["n_visible_tests"],
                "loads_ok": payload["loads_ok"],
                "detail_reason": payload["detail_reason"],
                "probe_ms": ms,
                "entry": att.entry.to_json(),
            })
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
    t_sign = time.time() - t_sign0
    wall = time.time() - t_start

    book_path = out_path.with_suffix(".book.json")
    ex.book.save(book_path)
    chain_ok = px.verify_executor_chain(args.executor_id, ex.book,
                                        {args.executor_id: ex.public})
    pub = {
        "executor_id": args.executor_id,
        "vacant_id": ident.vacant_id,
        "pub_hex": _pub_hex(ex.public),
        "run": args.run,
        "n_jobs": len(jobs),
        "n_signed": len(ex.book),
        "n_error": n_err,
        "n_render_local_mismatch": n_render_mismatch,
        "chain_ok_local": bool(chain_ok),
        "book_head": ex.book.head(),
        "wall_s": round(wall, 2),
        "probe_wall_s": round(t_probe, 2),
        "sign_wall_s": round(t_sign, 2),
        "workers": args.workers,
        "nice": os.nice(0) if hasattr(os, "nice") else None,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t_start)),
        **machine_info(),
    }
    pub_path = out_path.with_name(out_path.name.replace("att_", "pub_")
                                  .replace(".ndjson", ".json"))
    pub_path.write_text(json.dumps(pub, indent=1, sort_keys=True), encoding="utf-8")
    print(f"[{args.executor_id}] 簽了 {len(ex.book)} 筆，錯 {n_err} 筆，"
          f"chain_ok={chain_ok}，{wall:.0f}s（probe {t_probe:.0f}s / sign {t_sign:.0f}s）",
          flush=True)
    print(f"  {out_path}\n  {pub_path}\n  {book_path}", flush=True)
    return 0 if (chain_ok and n_err == 0) else 1


def _pub_hex(who: PublicIdentity) -> str:
    from vacant.crypto import pub_to_hex
    return pub_to_hex(who.pub)


# ── 角色二：合票（只在 Mac） ────────────────────────────────────────────────
def _gauge_job(job: tuple) -> tuple:
    """一題的量具：1 參考解 ＋ 4 壞樁，真沙箱。與 R452 `real_gauge` 逐字同一組樁。"""
    tid, spec_json, ep, ref = job
    try:
        spec = px.as_suite_spec(spec_json, ep)
        stubs = [
            px.broken_stub(ep or "_f"),
            f"def {ep}(*a, **k):\n    return 0\n",
            f"def {ep}(*a, **k):\n    return []\n",
            f"def {ep}(*a, **k):\n    return a[0] if a else None\n",
        ]
        rec = px.run_suite_gauge(spec, ref, stubs, entry_point=ep)
        return tid, rec.as_payload(), None
    except Exception as exc:  # noqa: BLE001
        return tid, None, f"{type(exc).__name__}:{exc}"[:300]


def build_gauge_index(specs: dict[str, dict], pool: dict, refs: dict[str, str],
                      workers: int) -> tuple[dict, dict, dict, PublicIdentity]:
    """Mac 側量具 ＋ commit ⇒ `form_verdict` 的白名單。

    `commit_suite_with_gauge` 拆成可並行的兩段（`run_suite_gauge` 在 worker、
    `commit_suite` 在主行程），語意逐字相同——那支自己就是這兩步的組合。
    白名單一律用 `gauged_suite_index` 造：它自己 fail-closed，呼叫端不必
    再記得檢查一次。
    """
    tasks = pool["tasks"]
    jobs = [(tid, specs[tid], tasks[tid].get("entry_point"), refs.get(tid, ""))
            for tid in sorted(specs) if tid in tasks and refs.get(tid)]
    missing_ref = [t for t in sorted(specs) if not refs.get(t)]
    print(f"量具：{len(jobs)} 題 × 5 次沙箱，{workers} workers"
          f"（沒有參考解 {len(missing_ref)}）", flush=True)
    t0 = time.time()
    recs: dict[str, dict] = {}
    errs: dict[str, str] = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (tid, payload, err) in enumerate(ex.map(_gauge_job, jobs, chunksize=4), 1):
            if err:
                errs[tid] = err
            else:
                recs[tid] = payload
            if n % 100 == 0:
                print(f"  gauge {n}/{len(jobs)}  {time.time()-t0:.0f}s", flush=True)

    ident = Identity.generate()
    book = Logbook()
    committed: list[tuple] = []
    commit_refused: dict[str, str] = {}
    for tid in sorted(recs):
        ep = tasks[tid].get("entry_point")
        spec = px.as_suite_spec(specs[tid], ep)
        rec = px.GaugeRecord.from_payload(recs[tid])
        try:
            entry = px.commit_suite(book, ident, task_id=tid, suite=spec,
                                    nonce=GAUGE_NONCE, entry_point=ep,
                                    gauge=rec, ts_ms=TS_MS)
        except px.SuiteGaugeError as exc:
            commit_refused[tid] = str(exc).split(":")[0]
            continue
        committed.append((entry, spec, GAUGE_NONCE, ep))
    index = px.gauged_suite_index(committed)
    print(f"  量具通過並上鏈 {len(committed)}/{len(specs)}；"
          f"擋下 {len(commit_refused)}；量具跑出例外 {len(errs)}；"
          f"沒有參考解 {len(missing_ref)}  {time.time()-t0:.0f}s", flush=True)
    meta = {"n_committed": len(committed), "commit_refused": commit_refused,
            "gauge_errors": errs, "missing_ref": missing_ref,
            "gauge_records": recs, "committer_vacant_id": ident.vacant_id,
            "commit_book_head": book.head(), "nonce": GAUGE_NONCE}
    by_task = {c[0].payload["task_id"]: c for c in committed}
    committer = PublicIdentity(ident.vacant_id, ident.pub)
    return index, meta, by_task, committer


def load_book_ndjson(path: str) -> tuple[dict, dict[tuple[str, int], dict], Logbook]:
    """讀一台機器的 ndjson ⇒ (pub meta, {(tid,i): 該格紀錄}, 重建的 Logbook)。"""
    p = pathlib.Path(path)
    pub_path = p.with_name(p.name.replace("att_", "pub_").replace(".ndjson", ".json"))
    pub = json.loads(pub_path.read_text(encoding="utf-8"))
    cells: dict[tuple[str, int], dict] = {}
    entries: list[LogEntry] = []
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            cells[(d["task_id"], d["cand_index"])] = d
            if d.get("entry"):
                entries.append(LogEntry.from_json(d["entry"]))
    return pub, cells, Logbook(entries)


def _select_loop(tid, codes, cell_verdicts) -> dict:  # noqa: ANN001
    """`select_by_quorum` 的同一條早停迴圈，逐行對照。

    差別**只有一個**：證言不是本機現跑出來的，是三台遠端機器簽好送回來的
    （本檔的整個重點）。所以 `attest` 那一行換成查表，其餘語意
    ——依序看草稿、第一份被法定人數判通過的出貨、全不通過就拒交、
    套件不合格就連跑都不跑——一字不改。
    """
    for i, code in enumerate(codes):
        v = cell_verdicts.get(i)
        if v is None:
            return {"shipped_index": None, "shipped_sha256": None, "refused": True,
                    "refusal_reason": "missing_verdict", "n_cells": i}
        if v.visible_ok:
            return {"shipped_index": i, "shipped_sha256": sha256_text(code),
                    "refused": False, "refusal_reason": None, "n_cells": i + 1}
        if v.gauge_status not in ("unchecked", "ok"):
            return {"shipped_index": None, "shipped_sha256": None, "refused": True,
                    "refusal_reason": f"suite_gate:{v.gauge_status}",
                    "n_cells": i + 1}
    return {"shipped_index": None, "shipped_sha256": None, "refused": True,
            "refusal_reason": None, "n_cells": len(codes)}


class _ReplayProbe:
    """把某一台機器**已經簽好**的那一格結果重放給本機的 `select_by_quorum`。

    只用在 `_crosscheck_select`：那支的唯一目的是證明 `_select_loop` 真的是
    `select_by_quorum` 的同一條迴圈，而不是一個長得像的抄本。它**不產生**
    本輪任何一個 P-1…P-6 的數字。
    """

    def __init__(self, cells: dict, codes: dict[str, list[str]]) -> None:
        self.by_key = {}
        for (tid, i), c in cells.items():
            if c.get("error") or "visible_ok" not in c:
                continue
            self.by_key[(tid, sha256_text(codes[tid][i]))] = c

    def __call__(self, code: str, task) -> px.ProbeResult:  # noqa: ANN001
        c = self.by_key[(task["task_id"], sha256_text(code))]
        return px.ProbeResult(bool(c["visible_ok"]), c.get("first_failing_test"),
                              c.get("n_visible_tests"), c.get("loads_ok"),
                              c.get("detail_reason"))


def _crosscheck_select(specs, pool, books, commits, committer, quorum, mine):  # noqa: ANN001
    """`_select_loop` vs **真的** `select_by_quorum`：逐題比出貨索引。

    為什麼需要：合票端拿到的是三台機器離線簽好的證言，而
    `select_by_quorum` 的簽名是「執行器現場跑」——沒有辦法把遠端的私鑰搬過來。
    所以本檔自己寫了一條早停迴圈。**自己寫的迴圈就是自己的規格**，除非它跟
    被稽核過的那一支對得起來。這裡用重放探針讓 `select_by_quorum` 看到
    完全相同的 k 條標籤流，然後比出貨索引。零沙箱、零模型呼叫。

    量具沒過因而沒有 commit 的題目跳過並單獨計數：那些題在真實部署裡
    `commit_suite` 就丟例外了，`select_by_quorum` 根本沒有合法的 `suite_commit`
    可以傳，兩條路徑都拒交但拒交的**理由字串**不同（一個在 commit、一個在
    `form_verdict` 的白名單），比字串會製造假的不一致。
    """
    tasks, cands = pool["tasks"], pool["candidates"]
    probes = {eid: _ReplayProbe(b["cells"], cands) for eid, b in books.items()}
    agree = disagree = skipped = 0
    diffs = []
    for tid in sorted(specs):
        if tid not in tasks or tid not in cands or tid not in commits:
            skipped += 1
            continue
        entry, spec, nonce, ep = commits[tid]
        try:
            execs = [px.Executor(eid, Identity.generate(), Logbook(), probes[eid])
                     for eid in sorted(books)]
            sel = px.select_by_quorum(
                {"task_id": tid, "entry_point": ep,
                 "visible_check": {"timeout": tasks[tid].get("timeout") or 8}},
                [(c, f"w{i}") for i, c in enumerate(cands[tid])], execs,
                roster=px.roster_of(execs), quorum=quorum, suite=spec,
                suite_commit=entry, suite_nonce=nonce, suite_committer=committer,
                ts_ms=TS_MS)
        except KeyError:
            skipped += 1
            continue
        m = mine[tid]
        if (sel.shipped_index == m["shipped_index"]
                and bool(sel.refused) == bool(m["refused"])):
            agree += 1
        else:
            disagree += 1
            diffs.append({"task_id": tid, "select_by_quorum": sel.shipped_index,
                          "select_loop": m["shipped_index"],
                          "refused": [sel.refused, m["refused"]]})
    return {"agree": agree, "disagree": disagree, "skipped_no_commit": skipped,
            "diffs": diffs[:20]}


def _pctl(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    k = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return round(s[k], 3)


def run_verdict(args) -> int:  # noqa: ANN001
    specs = load_specs(args.specs)
    pool = load_pool(args.pool)
    tasks, cands = pool["tasks"], pool["candidates"]

    books = {}
    for path in args.books:
        pub, cells, book = load_book_ndjson(path)
        books[pub["executor_id"]] = {"pub": pub, "cells": cells, "book": book,
                                     "path": path}
    k = len(books)
    quorum = k // 2 + 1
    roster = {eid: PublicIdentity.from_hex(b["pub"]["vacant_id"],
                                           b["pub"]["pub_hex"])
              for eid, b in books.items()}
    print(f"k={k}，quorum={quorum}，機器：{sorted(books)}", flush=True)

    # P-4 鏈驗證
    chain = {eid: bool(px.verify_executor_chain(eid, b["book"], roster))
             for eid, b in books.items()}
    print(f"P-4 chain verify: {chain}", flush=True)

    # 承重檔案跨機比對
    file_sha = {f: {eid: b["pub"]["file_sha256"].get(f) for eid, b in books.items()}
                for f in LOAD_BEARING}
    code_identical = {f: (len({v for v in d.values() if v is not None}) <= 1)
                      for f, d in file_sha.items()}

    # 量具白名單（Mac 側）
    from ops.gain.replay import peer_exec_sim as sim  # noqa: PLC0415
    refs = sim.canonical_refs(args.run)
    gauged, gauge_meta, commits, committer = build_gauge_index(
        specs, pool, refs, args.workers)
    gp = pathlib.Path(args.out).with_name("r453_gauge.json")
    gp.parent.mkdir(parents=True, exist_ok=True)
    gp.write_text(json.dumps(gauge_meta, indent=0, sort_keys=True), encoding="utf-8")

    # runtime 出貨決定
    rt = {}
    for line in (pathlib.Path(_REPO) / "runs" / args.run / "rows.jsonl").open(
            encoding="utf-8"):
        d = json.loads(line)
        rt[d["task_id"]] = d
    facts = json.loads((pathlib.Path(_REPO) / "ops" / "gain" / "replay" / "cache"
                        / f"peerexec_facts_{args.run}.json").read_text())

    # ── 逐格：跨機一致 ＋ form_verdict
    n_cells = n_agree = n_disagree = 0
    disagreements: list[dict] = []
    cell_errors: list[dict] = []
    render_sha_agree = suite_sha_agree = 0
    render_task_mismatch: list[str] = []
    verdicts: dict[str, dict[int, px.Verdict]] = {}
    contested_cells: list[dict] = []
    per_task_ms: dict[str, dict[str, float]] = {eid: {} for eid in books}
    per_task_prefix_ms: dict[str, dict[str, float]] = {eid: {} for eid in books}

    for tid in sorted(specs):
        if tid not in tasks or tid not in cands:
            continue
        ep = tasks[tid].get("entry_point")
        spec = px.as_suite_spec(specs[tid], ep)
        ssha, rsha = spec.suite_sha256, sha256_text(spec.render())
        rs = {eid: {b["cells"].get((tid, i), {}).get("render_sha256")
                    for i in range(len(cands[tid]))} for eid, b in books.items()}
        r_ok = all(v == {rsha} for v in rs.values())
        s_ok = all({b["cells"].get((tid, i), {}).get("suite_sha256")
                    for i in range(len(cands[tid]))} == {ssha}
                   for b in books.values())
        render_sha_agree += int(r_ok)
        suite_sha_agree += int(s_ok)
        if not (r_ok and s_ok):
            render_task_mismatch.append(tid)

        vt: dict[int, px.Verdict] = {}
        for i, code in enumerate(cands[tid]):
            n_cells += 1
            dsha = sha256_text(code)
            labels, atts, errs = {}, [], []
            for eid, b in books.items():
                c = b["cells"].get((tid, i))
                if not c or c.get("error") or not c.get("entry"):
                    errs.append({"executor": eid, "task_id": tid, "cand": i,
                                 "error": (c or {}).get("error", "missing_cell")})
                    continue
                labels[eid] = c["visible_ok"]
                atts.append(px.Attestation(eid, LogEntry.from_json(c["entry"])))
                per_task_ms[eid][tid] = per_task_ms[eid].get(tid, 0.0) + (
                    c.get("probe_ms") or 0.0)
            cell_errors.extend(errs)
            if len(set(labels.values())) <= 1:
                n_agree += 1
            else:
                n_disagree += 1
                disagreements.append({"task_id": tid, "cand": i, "labels": labels,
                                      "entry_point": ep})
            v = px.form_verdict(atts, roster, task_id=tid, draft_sha256=dsha,
                                suite_sha256=ssha, quorum=quorum,
                                gauged_suites=gauged, render_sha256=rsha)
            vt[i] = v
            if v.contested:
                contested_cells.append({
                    "task_id": tid, "cand": i, "visible_ok": v.visible_ok,
                    "dissenters": list(v.dissenters),
                    "detail_dissenters": list(v.detail_dissenters),
                    "equivocators": list(v.equivocators),
                    "rejected": [list(r) for r in v.rejected],
                    "gauge_status": v.gauge_status})
        verdicts[tid] = vt

    # ── 逐題：選擇 ＋ 與 runtime 比對
    ship_match = ship_mismatch = refuse_match = refuse_mismatch = 0
    excluded_gauge: list[str] = []
    task_rows: list[dict] = []
    for tid in sorted(specs):
        if tid not in tasks or tid not in cands:
            continue
        sel = _select_loop(tid, cands[tid], verdicts[tid])
        r = rt.get(tid, {})
        gauge_blocked = str(sel["refusal_reason"] or "").startswith("suite_gate:")
        row = {"task_id": tid, **sel, "runtime_accepted": r.get("accepted"),
               "runtime_sha": r.get("gate_code_sha256"),
               "gauge_blocked": gauge_blocked}
        if gauge_blocked:
            excluded_gauge.append(tid)
        elif r.get("accepted"):
            if (not sel["refused"]) and sel["shipped_sha256"] == r.get(
                    "gate_code_sha256"):
                ship_match += 1
                row["verdict_vs_runtime"] = "match"
            else:
                ship_mismatch += 1
                row["verdict_vs_runtime"] = "MISMATCH"
        else:
            if sel["refused"]:
                refuse_match += 1
                row["verdict_vs_runtime"] = "refuse_match"
            else:
                refuse_mismatch += 1
                row["verdict_vs_runtime"] = "MISMATCH_refuse"
        # 計分（hidden 只在這裡出現，只計分）
        if not sel["refused"]:
            hid = facts.get(f"{tid}#{sel['shipped_index']}", {}).get("hidden")
            row["delivered_correct"] = bool(hid)
            row["false_delivery"] = not bool(hid)
        # P-5b 早停前綴成本
        for eid in books:
            tot = 0.0
            for i in range(sel["n_cells"]):
                c = books[eid]["cells"].get((tid, i)) or {}
                tot += c.get("probe_ms") or 0.0
            per_task_prefix_ms[eid][tid] = tot
        task_rows.append(row)

    # ── 與單執行器（peerexec_facts）標籤比對
    vs_facts_agree = vs_facts_disagree = 0
    facts_disagreements = []
    for eid, b in books.items():
        for (tid, i), c in b["cells"].items():
            if c.get("error") or "visible_ok" not in c:
                continue
            ref_lab = facts.get(f"{tid}#{i}", {}).get("visible")
            if ref_lab is None:
                continue
            if bool(ref_lab) == bool(c["visible_ok"]):
                vs_facts_agree += 1
            else:
                vs_facts_disagree += 1
                facts_disagreements.append({"executor": eid, "task_id": tid,
                                            "cand": i, "facts": bool(ref_lab),
                                            "real": bool(c["visible_ok"])})

    cross = _crosscheck_select(specs, pool, books, commits, committer, quorum,
                               {r["task_id"]: r for r in task_rows})
    print(f"_select_loop vs select_by_quorum：相符 {cross['agree']}、"
          f"不符 {cross['disagree']}、跳過（沒有 commit）{cross['skipped_no_commit']}",
          flush=True)

    n_tasks = len([t for t in specs if t in tasks and t in cands])
    timing = {}
    for eid in books:
        full = [v / 1000.0 for v in per_task_ms[eid].values()]
        pre = [v / 1000.0 for v in per_task_prefix_ms[eid].values()]
        timing[eid] = {
            "workers": books[eid]["pub"].get("workers"),
            "wall_s": books[eid]["pub"].get("wall_s"),
            "p5a_full5_median_s": _pctl(full, 0.5), "p5a_full5_p95_s": _pctl(full, 0.95),
            "p5a_full5_max_s": _pctl(full, 1.0),
            "p5b_prefix_median_s": _pctl(pre, 0.5), "p5b_prefix_p95_s": _pctl(pre, 0.95),
            "p5b_prefix_max_s": _pctl(pre, 1.0),
        }

    p1_rate = (n_agree / n_cells) if n_cells else 0.0
    preds = {
        "P1_cross_machine_label_agreement": {
            "n_cells": n_cells, "agree": n_agree, "disagree": n_disagree,
            "rate": round(p1_rate, 6), "window": ">=0.995",
            "pass": bool(n_cells and p1_rate >= 0.995 and not cell_errors)},
        "P2_shipped_sha_vs_runtime": {
            "match": ship_match, "mismatch": ship_mismatch,
            "refuse_match": refuse_match, "refuse_mismatch": refuse_mismatch,
            "excluded_gauge_blocked": len(excluded_gauge),
            "window": "340/340 ship + 26/26 refuse",
            "pass": bool(ship_mismatch == 0 and refuse_mismatch == 0)},
        "P3_named_dissent": {
            "contested_cells": len(contested_cells), "window": "0",
            "pass": len(contested_cells) == 0},
        "P4_chain_verify": {"per_machine": chain, "window": "all True",
                            "pass": all(chain.values())},
        "P5_wall_clock": {"per_machine": timing,
                          "window": "P5a median <= 5s",
                          "pass": all((t["p5a_full5_median_s"] or 9e9) <= 5.0
                                      for t in timing.values())},
        "P6_render_portability": {
            "n_tasks": n_tasks, "render_sha_agree": render_sha_agree,
            "suite_sha_agree": suite_sha_agree,
            "mismatch_tasks": render_task_mismatch,
            "window": f"{n_tasks}/{n_tasks}",
            "pass": (render_sha_agree == n_tasks and suite_sha_agree == n_tasks)},
    }
    # 判定規則照預註冊 §四 的順序：先 INVALID（沒測到），再 REAL，最後 ARTIFACT。
    # P-5 **不進判定**——預註冊已寫明它超窗只改「展場秒級」那句話的措辭。
    core = ["P1_cross_machine_label_agreement", "P2_shipped_sha_vs_runtime",
            "P3_named_dissent", "P4_chain_verify", "P6_render_portability"]
    if (not all(chain.values())) or len(cell_errors) > 0.01 * max(1, n_cells * k):
        decision = "INVALID"
    elif all(preds[p]["pass"] for p in core):
        decision = "REAL_MATCHES_REPLAY"
    else:
        decision = "REPLAY_ARTIFACT"

    out = {
        "round": "R453",
        "run": args.run,
        "k": k, "quorum": quorum,
        "machines": {eid: b["pub"] for eid, b in books.items()},
        "code_identical_across_machines": code_identical,
        "file_sha256": file_sha,
        "predictions": preds,
        "decision": decision,
        "r449_seven_1_overturn": decision == "REPLAY_ARTIFACT",
        "r452_six_2_overturn": not preds["P6_render_portability"]["pass"] or n_disagree > 0,
        "disagreements": disagreements,
        "contested_cells": contested_cells[:200],
        "cell_errors": cell_errors[:200],
        "n_cell_errors": len(cell_errors),
        "excluded_gauge_blocked": excluded_gauge,
        "gauge": {kk: vv for kk, vv in gauge_meta.items() if kk != "gauge_records"},
        "select_loop_vs_select_by_quorum": cross,
        "vs_single_executor_facts": {
            "agree": vs_facts_agree, "disagree": vs_facts_disagree,
            "examples": facts_disagreements[:50]},
        "delivery_scoring_hidden_only": {
            "delivered_correct": sum(1 for r in task_rows
                                     if r.get("delivered_correct")),
            "false_delivery": sum(1 for r in task_rows if r.get("false_delivery")),
            "refused": sum(1 for r in task_rows if r["refused"]),
            "n_tasks": n_tasks},
        "task_rows": task_rows,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    outp = pathlib.Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")

    lines = [
        f"R453 跨機真跑多方執行  run={args.run}  k={k}  quorum={quorum}",
        "機器：" + "  ".join(
            f"{eid}({b['pub']['system']}/{b['pub']['python_version']})"
            for eid, b in sorted(books.items())),
        "",
        f"P-1 跨機可見標籤一致   {n_agree}/{n_cells}  ({p1_rate:.4%})  "
        f"窗口 >=99.5%   {'PASS' if preds['P1_cross_machine_label_agreement']['pass'] else 'FAIL'}",
        f"P-2 出貨 sha 與 r446   {ship_match} 相符 / {ship_mismatch} 不符；"
        f"拒交 {refuse_match} 相符 / {refuse_mismatch} 不符；"
        f"量具擋下 {len(excluded_gauge)}   "
        f"{'PASS' if preds['P2_shipped_sha_vs_runtime']['pass'] else 'FAIL'}",
        f"P-3 指名爭議格         {len(contested_cells)}   窗口 0   "
        f"{'PASS' if preds['P3_named_dissent']['pass'] else 'FAIL'}",
        f"P-4 鏈驗證             {chain}   "
        f"{'PASS' if preds['P4_chain_verify']['pass'] else 'FAIL'}",
        f"P-6 渲染逐位可攜       render {render_sha_agree}/{n_tasks}、"
        f"suite {suite_sha_agree}/{n_tasks}   "
        f"{'PASS' if preds['P6_render_portability']['pass'] else 'FAIL'}",
        "",
        "P-5 每題牆鐘（秒）",
        f"  {'機器':<12}{'workers':>8}{'P5a中位':>9}{'P5a p95':>9}{'P5a max':>9}"
        f"{'P5b中位':>9}{'P5b p95':>9}{'P5b max':>9}{'總牆鐘':>9}",
    ]
    for eid, t in sorted(timing.items()):
        cols = "".join(f"{str(t[c]):>9}" for c in
                       ("p5a_full5_median_s", "p5a_full5_p95_s", "p5a_full5_max_s",
                        "p5b_prefix_median_s", "p5b_prefix_p95_s", "p5b_prefix_max_s",
                        "wall_s"))
        lines.append(f"  {eid:<12}{str(t['workers']):>8}{cols}")
    lines += [
        "",
        f"與單執行器 facts 標籤：相符 {vs_facts_agree}、不符 {vs_facts_disagree}",
        f"_select_loop vs select_by_quorum：相符 {cross['agree']}、"
        f"不符 {cross['disagree']}、跳過 {cross['skipped_no_commit']}",
        f"格子錯誤（infra/例外）：{len(cell_errors)}",
        f"承重檔案跨機逐位相同：{all(code_identical.values())}  "
        f"{[f for f, v in code_identical.items() if not v]}",
        "",
        f"判定：{decision}",
        f"R449 §七-1 推翻：{'觸發' if out['r449_seven_1_overturn'] else '未觸發'}",
        f"R452 §六-2 推翻：{'觸發' if out['r452_six_2_overturn'] else '未觸發'}",
    ]
    table = "\n".join(lines)
    outp.with_name("r453_table.txt").write_text(table + "\n", encoding="utf-8")
    print(table, flush=True)
    return 0


# ── 輔助角色：在 Mac 上抽出可攜的輸入 ───────────────────────────────────────
def run_extract(args) -> int:  # noqa: ANN001
    """從 `calls.jsonl` 抽候選碼 ＋ 從題庫抽 entry_point ⇒ 可攜的 `pool.json`。

    **只輸出抽出來的碼**。prompt、reviewer 紀錄、`calls.jsonl` 本身不進這個檔——
    執行器本來就只看得到草稿碼，多送的每一個位元組都是白送的攻擊面。
    """
    from ops.gain.replay import peer_exec_sim as sim  # noqa: PLC0415
    tasks, cands = sim.load_pool(args.run)
    specs = load_specs(args.specs)
    out = {"run": args.run, "tasks": {}, "candidates": {}}
    for tid in sorted(specs):
        t = tasks.get(tid)
        if t is None or tid not in cands:
            continue
        out["tasks"][tid] = {"entry_point": t.get("entry_point"),
                             "timeout": (t.get("visible_check") or {}).get("timeout") or 8}
        out["candidates"][tid] = list(cands[tid])
    p = pathlib.Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=0, sort_keys=True), encoding="utf-8")
    n = sum(len(v) for v in out["candidates"].values())
    print(f"{p}：{len(out['tasks'])} 題、{n} 個候選、"
          f"{p.stat().st_size/1e6:.2f} MB、sha256={sha256_text(p.read_text())[:16]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--role", required=True,
                    choices=["executor", "verdict", "extract"])
    ap.add_argument("--run", default="g_r446_eq5_mbpp")
    ap.add_argument("--specs", default=None)
    ap.add_argument("--pool", default=None)
    ap.add_argument("--identity", default=None)
    ap.add_argument("--executor-id", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--books", nargs="*", default=[])
    ap.add_argument("--limit", type=int, default=0,
                    help="只跑前 N 題（冒煙測試用；正式跑一律 0）")
    a = ap.parse_args()
    if a.specs is None:
        a.specs = str(_REPO / "ops" / "gain" / "replay" / "cache"
                      / f"suitespec_{a.run}.json")
    if a.role == "extract":
        return run_extract(a)
    if a.role == "executor":
        if not a.executor_id:
            a.executor_id = platform.node().split(".")[0]
        if not a.identity:
            a.identity = str(pathlib.Path(a.out).parent / f"key_{a.executor_id}")
        return run_executor(a)
    return run_verdict(a)


if __name__ == "__main__":
    sys.exit(main())
