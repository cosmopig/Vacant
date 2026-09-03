#!/usr/bin/env python3
"""G 實驗 runner——三條臂，量「需求＝產出」。

規格：`SPEC_GAIN.md`。這支只做規格說的事，不多做。

    OFF     隨機路由，交回來就收                      1 呼叫／題
    ON      信譽路由 ＋ K=3 同儕評審 ＋ 抽樣稽核      ≈5 呼叫／題
    OFF5    同題跑 5 次取多數決（self-consistency）    5 呼叫／題

**OFF5 是這個實驗誠實與否的分水嶺**：ON 比 OFF 好幾乎必然，因為多花五倍呼叫。
要答的是「等預算下 Vacant 打不打得贏最土的做法」。

用法：
    python3 ops/gain/gain_run.py --out runs/g1 --n 40 --seed g1
    python3 ops/gain/gain_run.py --out runs/g1 --n 40 --arms probe   # 只跑量具驗證

全 I/O 落盤：`<out>/calls.jsonl`（每次模型呼叫的 prompt/回應全文）、
`<out>/rows.jsonl`（逐題）、`<out>/summary.json`。
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.brain_cline import (DEFAULT_MODEL, POOL, REVIEWER_SYSTEM,  # noqa: E402
                                  REVIEW_LENSES, ClineBrain, InfraVoid,
                                  load_keys)
from vacant.codebench import BuiltinSampleLoader, EvalPlusMBPPLoader  # noqa: E402
from vacant.identity import Identity  # noqa: E402
from vacant.logbook import Logbook  # noqa: E402


# The official no-extreme concept applied to this runner's declared product envelope:
# canonical itself must finish the full base+plus suite within 10 wall seconds and a
# 128 MiB sandbox. These seven do not; counting candidates against an impossible oracle
# would turn infrastructure capacity into model error. IDs/reasons are pinned and tested.
GAIN_EVALPLUS_RESOURCE_EXCLUSIONS = {
    "mbppplus_Mbpp/255": "combinations_with_replacement output explosion",
    "mbppplus_Mbpp/271": "extreme linear iteration with huge integer powers",
    "mbppplus_Mbpp/392": "O(n) table exceeds the sandbox envelope",
    "mbppplus_Mbpp/599": "up to 100M Python-level additions",
    "mbppplus_Mbpp/603": "quadratic list-removal sieve",
    "mbppplus_Mbpp/630": "exponential coordinate materialization",
    "mbppplus_Mbpp/644": "extreme list materialization exceeds memory envelope",
}


def load_tasks(bank: str, seed: str, n: int, *, offset: int = 0) -> list[dict]:
    """預設用**真題庫**（EvalPlus MBPP+ 378 題，sha256 釘死、fail-closed）。

    ⚠ `BuiltinSampleLoader` 只在明確指定時才用，而且它的 docstring 自己警告過：
      「同一顆 reference solver 配不同隨機測資的變體，不是真的不同題目，
        正式跑分前必須換成真 EvalPlus 資料」。
      拿它跑增益實驗會把「題目其實都一樣」誤讀成「機制沒有差別」。
    """
    if bank == "evalplus":
        loader = EvalPlusMBPPLoader(expose_contract=True)
    elif bank == "lcb":
        from vacant.codebench import LiveCodeBenchLoader
        loader = LiveCodeBenchLoader()          # sha256/題數釘死，fail-closed
    else:
        loader = BuiltinSampleLoader()
    ts = list(loader.iter_tasks(seed))
    if bank == "evalplus":
        ts = [t for t in ts if t["task_id"] not in GAIN_EVALPLUS_RESOURCE_EXCLUSIONS]
    if bank == "builtin":
        print("⚠ 用的是合成題庫，結論不可外推（見 load_tasks docstring）")
    return ts[offset:offset + n] if n else ts[offset:]


# ── 判定：產出滿不滿足需求 ────────────────────────────────────────
# ON 的隱藏判定與 OFF5 的行為簽名共用同一份 import 白名單——
# 兩條路徑對候選碼的限制必須一致，否則多數決與驗收會在不同規則下跑。
#
# round393：加入 "typing"。它零執行期副作用（純型別標註，不碰 I/O／檔案／
# 網路），被漏掉純屬白名單疏漏，不是刻意的安全邊界。round393 逐題查證
# off5va 剩下 2 個 discordant（736/790）發現：ON 對這兩題的 initial 與
# revised 都因為 `from typing import List/Union` 被這道白名單擋下
# （sandbox_check_failed，跟邏輯對不對無關），而 OFF5 的多數決剛好落在
# 沒用 typing 的樣本上才躲過去。全域掃描：ON 的 visible_ok=False 裡
# 6/7（86%）是這個 typing 阻擋，OFF 是 2/7（29%），OFF5 是 2/6（33%）——
# ON 被這道白名單漏洞打得結構性地重，因為它只有 initial+revision 兩次
# 真正的機會，OFF5 有 5 個獨立樣本多數決，撞上白名單漏洞的機率天然更低。
# 這不是「哪個模型比較會寫程式」的證據，是量具本身的偏誤。
# 見 `ops/gain/DECISION_20260831_R393_TYPING_IMPORT_WHITELIST_BUG.md`。
_GAIN_ALLOWED_IMPORTS = (
    "bisect", "cmath", "collections", "functools", "heapq", "itertools",
    "math", "operator", "re", "sys", "typing",
)


def extract_code(text: str) -> str:
    """從回應裡挖出 python 程式碼。挖不到就原樣回傳——不要猜。"""
    if "```" in text:
        parts = text.split("```")
        for i in range(1, len(parts), 2):
            blk = parts[i]
            if blk.startswith("python"):
                blk = blk[6:]
            elif blk.startswith("py"):
                blk = blk[2:]
            if blk.strip():
                return blk.strip()
    return text.strip()


def meets_demand(
    code: str, check_code: str, timeout_s: int = 10, entry_point: str | None = None,
) -> tuple[bool, str]:
    """跑隱藏測資。回傳 (通過?, 訊息)。

    隱藏測資**不進 prompt**——那個分離就是「需求 vs 產出」的操作定義。
    """
    from vacant.checks import CheckInfraError, run_python_check
    try:
        ok = run_python_check(
            code, check_code, timeout=timeout_s, allowed_imports=_GAIN_ALLOWED_IMPORTS,
            allowed_entry_points=(entry_point,) if entry_point else (),
        )
        return ok, "" if ok else "sandbox_check_failed"
    except CheckInfraError as exc:
        # A verifier launch/protocol failure is missing data, not evidence that the
        # candidate is wrong.  Keep it out of both numerator and denominator.
        raise InfraVoid(f"sandbox verifier unavailable: {exc}") from exc


# ── 量具驗證：先答已知答案 ────────────────────────────────────────
LCB_PROBE_SOLUTIONS_PATH = (
    pathlib.Path(__file__).resolve().parent / "data" / "lcb_probe_solutions.json"
)


def _canonical_solutions(bank: str = "evalplus", path: str | None = None) -> dict[str, str]:
    """只給量具驗證用的官方參考解。

    ⚠ 為什麼要另外讀：`EvalPlusMBPPLoader` **刻意不把 `canonical_solution`
      放進 public projection**——它是 GT，只進 `hidden_check`，永不進 prompt
      （codebench.py 的 V/GT 分離紀律，負向測試在 tests/test_x1_evalplus.py）。

    ⚠ 為什麼這樣讀不算作弊：量具驗證是**驗證者側**的動作，跟 agent 無關。
      這個 dict 只餵給 `meets_demand`，**不進任何 prompt**。
      如果哪天有人把它接進 agent 那條路，V/GT 分離就破了——所以它只在
      `probe_instrument` 裡被用到，不要擴大使用範圍。

    ⚠ round441：LCB bank 的原始資料**沒有**官方參考解欄位（`_lcb_check_code`
      的註解自己寫「LCB 的 GT 是 dataset 的 expected output，無 canonical」）
      ——`bank="lcb"` 這條分支讀的是 `lcb_probe_solutions.json`，**手寫並在
      本機用真的 hidden_check 逐題驗證過**（round441 的 DECISION 檔記過程與
      驗證輸出），不是官方資料的一部分，只給量具用。`separateSquares`
      （lcb_3763）刻意不收進來——該題 dataset 的 expected 只到小數 5 位，
      跟檢查式 `abs(a-b)<=1e-6` 的容忍度矛盾，連精確解都會被判錯，
      見 DECISION_20260901_R441。
    """
    if bank == "lcb":
        p = pathlib.Path(path) if path else LCB_PROBE_SOLUTIONS_PATH
        with p.open(encoding="utf-8") as f:
            return json.load(f)
    import gzip
    import os
    from vacant.codebench import EVALPLUS_DEFAULT_PATH
    p = pathlib.Path(path or os.environ.get("VACANT_EVALPLUS_PATH", EVALPLUS_DEFAULT_PATH))
    out: dict[str, str] = {}
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            out[f"mbppplus_{r['task_id']}"] = r.get("canonical_solution", "")
    return out


def probe_instrument(tasks, log, *, sample=12, bank: str = "evalplus") -> dict:
    """SPEC_GAIN §5.2：餵一份**確定正確**與一份**確定錯誤**，兩邊都要判對。

    沒有這一步的話，「量到 0」與「線根本沒接上」在報告裡長得一模一樣。

    正確那份用官方（或 round441 手驗）參考解。錯誤那份用一個一定跑不過的樁。
    **兩個方向都過才算量具可用**——只驗正向會漏掉「什麼都判通過」，
    只驗反向會漏掉「什麼都判失敗」。

    round441：抽樣改成**先篩有參考解的題目、再取前 `sample` 個**，不是
    「取前 `sample` 個題目、沒參考解的跳過」——後者在 lcb bank 上會因為
    seed 排序把有解的題目排到抽樣窗外，量到 n=0 但看起來像是資料沒接上
    （實際發生過，見 DECISION_20260901_R441）。
    """
    try:
        refs = _canonical_solutions(bank)
    except Exception as e:                                   # noqa: BLE001
        raise SystemExit(f"讀不到官方參考解，量具無法驗證：{e}")
    good = bad = 0
    detail = []
    covered = [t for t in tasks if refs.get(t["task_id"])][:sample]
    for t in covered:
        ref = refs[t["task_id"]]
        hidden = t["hidden_check"]["code"]
        ok_good, msg_g = meets_demand(ref, hidden, entry_point=t.get("entry_point"))
        ok_bad, _ = meets_demand(
            f"def {t.get('entry_point','_f')}(*a, **k):\n    return None\n", hidden,
            entry_point=t.get("entry_point"))
        good += int(ok_good)
        bad += int(not ok_bad)
        detail.append({"task_id": t["task_id"], "ref_pass": ok_good,
                       "broken_rejected": not ok_bad, "err": msg_g[:160]})
    res = {"n": len(detail), "ref_pass": good, "broken_rejected": bad,
           "detail": detail}
    log(res)
    return res


# ── 三條臂 ────────────────────────────────────────────────────────
def arm_off(task, agents, rng, calls):
    a = rng.choice(agents)
    txt = a.generate(task["prompt"], role="gen",
                     meta={"arm": "OFF", "task_id": task["task_id"]})
    calls[0] += 1
    code = extract_code(txt)
    # round342：只是**記錄**可見測試結果，不改變本臂的 accepted 語意（仍恆為 True）。
    # 零模型呼叫、不抽 rng ⇒ 本臂的抽樣與產出逐位元不變，只是多一個落盤欄位。
    # 用途見 CONCLUSION_20260830_G_EXPERIMENT.md「推翻條件 1」：
    # 有了這個欄位，「OFF + 免費可見測試閘」的對照可以**離線**從同一個 run 算出來，
    # 不必新增一條會在抽樣上分岔的臂。
    visible_ok, _ = meets_demand(
        code, task["visible_check"]["code"], entry_point=task.get("entry_point"))
    return code, a.agent_id, [a.agent_id], {"visible_ok": visible_ok}


def behavior_signature(code: str, task: dict, timeout_s: int = 10) -> str:
    """Observe candidate behavior on public/base inputs without canonical outputs.

    Literal source hashing is not self-consistency: two equivalent implementations would
    be split into different buckets. EvalPlus base inputs contain no hidden plus cases or
    expected outputs, so they can safely identify behaviorally equivalent candidates.

    2026-08-20 修正：改走 `run_python_capture`——與 ON 臂同一條受限 worker 路徑。
    舊版用 `subprocess.run([sys.executable, …])` 直接執行模型產生的程式，
    沒有 RLIMIT、沒有 import 白名單、沒有 env 清理；OFF5 的多數決因此曾在
    非受限環境跑模型碼。候選碼現在只活在 worker，經 literal-only proxy 呼叫；
    候選自己的 stdout 留在 worker（DEVNULL），不會污染簽名。
    """
    inputs = task.get("behavior_inputs")
    entry_point = task.get("entry_point")
    if not inputs or not entry_point:
        visible_ok, _ = meets_demand(
            code, task["visible_check"]["code"], timeout_s, entry_point=entry_point)
        return "VISIBLE_PASS" if visible_ok else "VISIBLE_FAIL"

    from vacant.checks import CheckInfraError, run_python_capture
    probe = [
        "import json as __vacant_json",
        "__vacant_results = []",
    ]
    for args in inputs:
        probe.extend([
            "try:",
            f"    __vacant_value = {entry_point}(*{args!r})",
            "    __vacant_results.append(['ok', type(__vacant_value).__name__, repr(__vacant_value)])",
            "except BaseException as __vacant_exc:",
            "    __vacant_results.append(['err', type(__vacant_exc).__name__, str(__vacant_exc)])",
        ])
    probe.append("print('__VACANT_BEHAVIOR__' + __vacant_json.dumps(__vacant_results, sort_keys=True))")
    try:
        out = run_python_capture(
            code, "\n".join(probe), timeout=timeout_s,
            allowed_imports=_GAIN_ALLOWED_IMPORTS,
            allowed_entry_points=(entry_point,),
        )
    except CheckInfraError as exc:
        raise InfraVoid(f"sandbox verifier unavailable: {exc}") from exc
    if out is None:
        return "EXEC_FAIL"
    marker = "__VACANT_BEHAVIOR__"
    lines = [line for line in out.splitlines() if line.startswith(marker)]
    return lines[-1][len(marker):] if lines else "EXEC_FAIL"


def arm_off5(task, agents, rng, calls, k=5):
    """self-consistency：同題跑 k 次，取多數決。

    多數決的定義：把每份解答的**行為**當簽名——用同一組可見測資跑一遍，
    結果字串相同的視為同一票。這比字面比對公平（同義寫法不該被拆票）。
    """
    assigned = [rng.choice(agents) for _ in range(k)]

    def generate_one(a):
        txt = a.generate(task["prompt"], role="gen",
                         meta={"arm": "OFF5", "task_id": task["task_id"]})
        calls[0] += 1
        return extract_code(txt), a.agent_id

    # 依序送出，不用 ThreadPoolExecutor 併發：round22/23 量到 3-way 併發
    # review 打同一個中轉端點時，排隊延遲會把個別請求推過 timeout（後端很可能
    # 是單一 GPU/LM Studio 實例，client 併發不會換來真正的平行運算，只會讓
    # 每個請求各自的 timeout 時鐘在排隊等待時空轉）。這裡的 k=5 generate 面臨
    # 同一種風險，尚未實測到失敗（OFF5 在 ON 之後才跑），依同一機制理由預先改掉，
    # 見 DECISION_20260824_SERIALIZE_CONCURRENT_CALLS.md。
    outs = [generate_one(a) for a in assigned]
    # 行為簽名：同義實作投同一票；只看 base inputs，不碰 hidden plus cases。
    buckets: dict[str, list[tuple[str, str]]] = {}
    for code, aid in outs:
        sig = behavior_signature(code, task)
        buckets.setdefault(sig, []).append((code, aid))
    max_votes = max(len(v) for v in buckets.values())
    tied = [v for v in buckets.values() if len(v) == max_votes]
    win = rng.choice(tied)
    chosen = rng.choice(win)
    # round342：同 arm_off——只記錄，不改 accepted 語意。rng 已經抽完，這行不動它。
    # `behavior_signature` 本來就已經把每個候選跑過可見測資，所以這道閘在資訊上
    # 是免費的（零額外模型呼叫）；記下來才能離線算 OFF5+閘門的對照。
    visible_ok, _ = meets_demand(
        chosen[0], task["visible_check"]["code"], entry_point=task.get("entry_point"))
    n_agree = max_votes
    return chosen[0], chosen[1], [a for _, a in outs], {
        "visible_ok": visible_ok, "vote_agreement": n_agree, "n_buckets": len(buckets)}


def arm_conform(task, agents, rng, calls, book, ident, k=5):
    """驗收閘門（CONFORM）：跑客戶自己的驗收測資，不開評審會。

    這支在架構裡承重什麼（DECISION_20260903_R440P §四）：
    R438/R516 量到「評審票近乎常數函數」，R518 量到反例精確度上界 <0.80，
    E1 的 revise 在 167 題裡 improved 6 / harmed 0——**委員會那三通呼叫買不到東西**。
    但同一批資料也量到：ON 的拒交閘門比任何從 5 個樣本導出的信心值都校準得好，
    而「跑一次可見驗收」是零模型呼叫（`arm_off5` 的 behavior_signature 早就在跑）。
    所以把 ON 從委員會改成閘門：**執行取代意見，收據取代投票**。

    與 OFF5 的差別只有兩個，其餘（同一個 agent 池、同一個 k 上限）完全相同：
      1. 不投票，而是逐一執行 `visible_check`；
      2. 通過就停（早停），全不通過就**拒交**。

    誠實邊界（R440P §五，改碼不得刪）：
    - 這一切建立在「需求可以編譯成可執行的驗收測資」。需求跑不起來時本機制沒有
      免費裁判，會退化成「問一個模型」，而那正是量出來很差的東西。
    - 「可見篩選不會誤丟正確解」在 MBPP+ 上量到 0/1630，但那**部分是題庫性質**
      （hidden ＝ base＋plus，可見沒過結構上蘊含隱藏沒過）。驗收測資不是真需求
      子集的部署裡，拒交會殺掉好答案。

    收據：每一次嘗試都簽進 hash-chain（`vacant/logbook.py`），事後可獨立驗鏈。
    回傳的 `receipt_head` 是鏈頭 hash，`attempts` 是逐次的具名紀錄。
    """
    assigned = [rng.choice(agents) for _ in range(k)]
    attempts: list[dict] = []
    chosen: tuple[str, str] | None = None
    last: tuple[str, str] | None = None

    for idx, a in enumerate(assigned, 1):
        txt = a.generate(task["prompt"], role="gen",
                         meta={"arm": "CONFORM", "task_id": task["task_id"]})
        calls[0] += 1
        code = extract_code(txt)
        last = (code, a.agent_id)
        # 只用 visible：hidden 是計分用的，選擇時碰它＝V/GT 分離破功（SPEC §5.3）。
        vis_ok, vis_err = meets_demand(
            code, task["visible_check"]["code"], entry_point=task.get("entry_point"))
        entry = book.append(
            "conform_attempt",
            {"task_id": task["task_id"], "attempt": idx, "worker": a.agent_id,
             "visible_ok": bool(vis_ok), "err": vis_err[:120],
             "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest()},
            ident, ts_ms=int(time.time() * 1000),
        )
        attempts.append({"attempt": idx, "worker": a.agent_id,
                         "visible_ok": bool(vis_ok), "err": vis_err[:120],
                         "entry_hash": entry.hash()})
        if vis_ok:
            chosen = (code, a.agent_id)
            break

    accepted = chosen is not None
    # 拒交時仍然要回傳一份程式碼——dispatch 端無條件用 hidden_check 計分，
    # 那是**離線評分**不是出貨。`accepted=False` 才是「沒有交出去」的語意，
    # 與 ON 一致（leaked = accepted and not truth）。
    code, worker = chosen if accepted else last
    book.append(
        "conform_verdict",
        {"task_id": task["task_id"], "accepted": accepted,
         "attempts": len(attempts), "worker": worker},
        ident, ts_ms=int(time.time() * 1000),
    )
    return code, worker, [a.agent_id for a in assigned[:len(attempts)]], {
        "accepted": accepted,
        "visible_ok": accepted,
        "conform_attempts": attempts,
        "conform_calls": len(attempts),
        "receipt_head": book.head(),
    }


def _review_vote(text: str) -> bool:
    """Parse fail-closed: malformed reviewer output is not an approval."""
    first = text.strip().splitlines()[0].strip().upper() if text.strip() else ""
    return first == "VERDICT: PASS"


def parse_review_claim(text: str) -> tuple[list | tuple, object] | None:
    """Parse a reviewer's inert counterexample literals; never execute reviewer text."""
    fields = {}
    for line in text.strip().splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip().upper() in {"TEST_ARGS", "EXPECTED"}:
            fields[key.strip().upper()] = value.strip()
    if not fields or "TEST_ARGS" not in fields or "EXPECTED" not in fields:
        return None
    if fields["TEST_ARGS"].upper() == "NONE" or fields["EXPECTED"].upper() == "NONE":
        return None
    try:
        args = ast.literal_eval(fields["TEST_ARGS"])
        expected = ast.literal_eval(fields["EXPECTED"])
    except (SyntaxError, ValueError):
        return None
    if not isinstance(args, (list, tuple)):
        return None
    return args, expected


def verify_review_counterexample(
    code: str, entry_point: str | None, review: str, timeout_s: int = 10,
    input_contract: str = "", input_parameters: list[str] | None = None,
) -> tuple[bool, str]:
    """Confirm that a FAIL review's literal test actually falsifies the candidate.

    This is visible evidence, not hidden ground truth. Reviewer-supplied text is parsed
    with ``literal_eval`` and re-serialized with ``repr`` before entering the sandbox.
    """
    if _review_vote(review) or not entry_point:
        return False, "review_not_fail"
    claim = parse_review_claim(review)
    if claim is None:
        return False, "unparseable_claim"
    args, expected = claim
    if input_contract:
        parameters = list(input_parameters or [])
        if not parameters:
            try:
                tree = ast.parse(code)
                fn = next(
                    node for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == entry_point
                )
                parameters = [
                    arg.arg for arg in (*fn.args.posonlyargs, *fn.args.args)
                ]
            except (SyntaxError, StopIteration):
                return False, "unavailable_input_signature"
        if len(args) != len(parameters):
            return False, "outside_input_contract"
        assignments = "\n".join(
            f"{name} = {value!r}" for name, value in zip(parameters, args)
        )
        # Execute only the pinned dataset's public preconditions. Out-of-domain examples
        # are not counterexamples; the candidate worker cannot see this test code.
        contract_check = f"""
{assignments}
{input_contract}
"""
        in_domain, _ = meets_demand(
            code, contract_check, timeout_s, entry_point=entry_point)
        if not in_domain:
            return False, "outside_input_contract"
    check = counterexample_check(entry_point, args, expected)
    matches, err = meets_demand(code, check, timeout_s, entry_point=entry_point)
    return not matches, "counterexample_confirmed" if not matches else "candidate_passed_claim"


def counterexample_check(entry_point: str, args: list, expected) -> str:
    """一份可重放的斷言字串：`entry_point(*args) == expected`。

    round439 抽出這支：revise 選擇邏輯需要拿同一份反例斷言重新跑在
    `revised_code` 上（見 `arm_on`），不能只跟 `verify_review_counterexample`
    內部耦合，否則沒有管道驗證修訂版真的修掉了被指控的那個反例。
    """
    return f"""
import math as __vacant_math
def __vacant_equal(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return __vacant_math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(__vacant_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(__vacant_equal(a[k], b[k]) for k in a)
    return a == b
__vacant_actual = {entry_point}(*{args!r})
assert __vacant_equal(__vacant_actual, {expected!r}), (__vacant_actual, {expected!r})
"""


def _route_agent(agents, rep, rng, *, exclude=()):
    """UCB-shaped routing with randomized ties; list order must not be a whitelist."""
    excluded = set(exclude)
    eligible = [a for a in agents if a.agent_id not in excluded]
    if not eligible:
        raise ValueError("routing has no eligible agent")

    def score(a):
        s = rep[a.agent_id]
        n = s["n"]
        mean = (s["ok"] + 1) / (n + 2)
        explore = (2.0 / (n + 1)) ** 0.5
        return mean + 0.4 * explore

    scores = {a.agent_id: score(a) for a in eligible}
    best = max(scores.values())
    return rng.choice([a for a in eligible if abs(scores[a.agent_id] - best) < 1e-12])


def apply_audit_reputation(rep, worker_id: str, audit_ok: bool | None) -> bool:
    """Only an actually sampled hidden audit may update hidden-quality reputation."""
    if audit_ok is None:
        return False
    rep[worker_id]["n"] += 1
    rep[worker_id]["ok"] += int(audit_ok)
    return True


def _model_family(agent) -> str:
    model = getattr(agent, "model", "")
    return model.split("/", 1)[0] if model else "unknown"


def _diverse_reviewers(pool, k: int, rng) -> list:
    """Prefer distinct model families without granting any identity a whitelist."""
    shuffled = list(pool)
    rng.shuffle(shuffled)
    chosen = []
    seen = set()
    for reviewer in shuffled:
        family = _model_family(reviewer)
        if family not in seen:
            chosen.append(reviewer)
            seen.add(family)
            if len(chosen) == k:
                return chosen
    for reviewer in shuffled:
        if reviewer not in chosen:
            chosen.append(reviewer)
            if len(chosen) == k:
                break
    return chosen


def _independent_reviser(agents, worker, rep, rng):
    """Prefer a different model family so revision is not self-confirmation."""
    different = [
        a for a in agents
        if a.agent_id != worker.agent_id and _model_family(a) != _model_family(worker)
    ]
    eligible = different or [a for a in agents if a.agent_id != worker.agent_id]
    return _route_agent(eligible, rep, rng)


def arm_on(task, agents, rng, calls, rep, *, audit_rate=0.2, k_review=3,
           review_timeout_s: int = 60, review_retries: int = 2):
    """信譽路由＋K=3 審查＋一次修訂＋確定性抽樣稽核（恰好五次呼叫）。

    路由用 rep 的分數；評審用**同一個池**——所以共同盲區是真的存在，
    不是被假設掉。評審準確率會被單獨記錄（SPEC_GAIN §5.1）。

    評審呼叫用獨立的較短 deadline（預設 60s×2）：clinepass-clean-v2 的死因就是
    reviewer 跟著全域 240s×4 走，尾延遲支配整條臂。bounded deadline 讓單題
    評審階段最壞 ~2 分鐘封頂；用盡仍失敗依舊記 infra_void，不當候選的錯。
    """
    worker = _route_agent(agents, rep, rng)
    txt = worker.generate(task["prompt"], role="gen",
                          meta={"arm": "ON", "phase": "initial",
                                "task_id": task["task_id"]})
    calls[0] += 1
    initial_code = extract_code(txt)

    # 同儕評審：不能自評
    pool = [a for a in agents if a.agent_id != worker.agent_id]
    reviewers = _diverse_reviewers(pool, min(k_review, len(pool)), rng)
    votes = []
    rprompt = (f"題目：\n{task['prompt']}\n\n候選解答：\n"
               f"```python\n{initial_code}\n```\n")

    def review_one(r):
        v = r.generate(rprompt, role="review",
                       meta={"arm": "ON", "task_id": task["task_id"],
                             "target": worker.agent_id},
                       system=f"{REVIEWER_SYSTEM}\n{REVIEW_LENSES.get(r.agent_id, '')}",
                       timeout_s=review_timeout_s, retries=review_retries)
        calls[0] += 1
        return r.agent_id, v

    # 依序送出，不用 ThreadPoolExecutor 併發：round22 量到 3 個 reviewer 同時
    # 送出時，即使成功的呼叫延遲也普遍 100-241s，逼近甚至超過 review_timeout_s；
    # round23 補量到 review 呼叫失敗率 17/30=57%、平均分布在 5/6 個 agent（不是
    # 單一 agent 的問題）⇒ 併發搶佔同一個中轉端點（後端很可能是單一 GPU/LM
    # Studio 實例，client 端「併發」換不到真正的平行運算，只會讓排隊中的請求
    # 各自的 timeout 時鐘持續空轉，越後面送出的請求越可能撞牆）。序列送出讓
    # 每個請求的 timeout 從它真正開始處理時起算，總耗時不會顯著變多（後端本來
    # 就是排隊處理），但可以避免這種人為的逾時。見
    # DECISION_20260824_SERIALIZE_CONCURRENT_CALLS.md。
    raw_reviews = [review_one(r) for r in reviewers]
    review_evidence = []
    confirmed_checks = []
    for aid, review in raw_reviews:
        raw_pass = _review_vote(review)
        confirmed, evidence_status = verify_review_counterexample(
            initial_code, task.get("entry_point"), review,
            input_contract=task.get("input_contract", ""),
            input_parameters=task.get("input_parameters", []),
        )
        # PASS remains approval. FAIL counts only with a machine-confirmed counterexample;
        # unsupported accusations are abstentions resolved in favor of the submitted code.
        grounded_pass = raw_pass or not confirmed
        votes.append((aid, grounded_pass))
        review_evidence.append({
            "agent_id": aid, "raw_pass": raw_pass,
            "grounded_pass": grounded_pass,
            "counterexample_confirmed": confirmed,
            "status": evidence_status,
        })
        if confirmed:
            # round439: keep the exact assertion that falsified the initial candidate so the
            # revision can be checked against what was actually wrong, not just re-run against
            # the same sparse visible suite it may already have passed or failed independent of
            # the complaint. See DECISION_20260901_R439_REVISE_SELECTION_COUNTEREXAMPLE_CHECK.md.
            claim = parse_review_claim(review)
            if claim is not None:
                claim_args, claim_expected = claim
                confirmed_checks.append(
                    counterexample_check(task.get("entry_point"), claim_args, claim_expected)
                )

    passed_review = sum(1 for _, ok in votes if ok) >= (len(votes) + 1) // 2

    # 審查若不能改變交付，ON 只能拒絕、不能提高正確交付。第五次呼叫交給不同
    # 模型家族的 synthesizer，避免原 worker 對自己的初稿做自我確認。
    confirmed_ids = {
        row["agent_id"] for row in review_evidence if row["counterexample_confirmed"]
    }
    grounded_reviews = [
        (aid, text) for aid, text in raw_reviews if aid in confirmed_ids
    ]
    review_text = "\n\n".join(
        f"Reviewer {aid}（反例已由系統執行並確認）:\n{text}"
        for aid, text in grounded_reviews
    ) or "沒有通過執行驗證的反例；不要因未證實的文字指控改壞初稿。"
    revise_prompt = (
        f"原題：\n{task['prompt']}\n\n待修訂初稿：\n```python\n{initial_code}\n```\n\n"
        f"三份同儕審查：\n{review_text}\n\n"
        "逐條判斷審查意見。修正真正的問題，忽略錯誤指控。"
        "最後只輸出一個完整的 ```python 程式碼區塊，不要解釋。"
    )
    reviser = _independent_reviser(agents, worker, rep, rng)
    revised = reviser.generate(
        revise_prompt, role="revise",
        meta={"arm": "ON", "phase": "revision", "task_id": task["task_id"],
              "initial_worker": worker.agent_id},
    )
    calls[0] += 1
    revised_code = extract_code(revised)
    initial_visible_ok, _ = meets_demand(
        initial_code, task["visible_check"]["code"], entry_point=task.get("entry_point"))
    revised_visible_ok, _ = meets_demand(
        revised_code, task["visible_check"]["code"], entry_point=task.get("entry_point"))
    # round439: re-running the same visible suite on revised_code proves nothing about
    # whether it fixed the specific counterexample(s) that triggered the revision in the
    # first place (that's usually why a grounded FAIL exists despite initial_visible_ok, or
    # why passed_review is False even when initial already clears the sparse visible suite).
    # DECISION_20260901_R438 measured discarded_win=0/113 on the prior selection rule; this
    # gives the selector evidence to actually score a revision instead of rubber-stamping it.
    revised_fixes_counterexamples = all(
        meets_demand(revised_code, chk, entry_point=task.get("entry_point"))[0]
        for chk in confirmed_checks
    ) if confirmed_checks else True
    if passed_review and initial_visible_ok:
        # The fifth call keeps the equal budget, but an unrequested rewrite must not replace
        # an answer that peers approved. Its output remains logged for offline analysis.
        code = initial_code
        selected_version = "initial"
    elif revised_visible_ok and revised_fixes_counterexamples:
        code = revised_code
        selected_version = "revised"
    elif initial_visible_ok:
        code = initial_code
        selected_version = "initial_fallback"
    elif revised_visible_ok:
        # Revised clears the sparse visible suite but does not fix the specific
        # counterexample a reviewer proved against initial; neither candidate is verified
        # against the actual complaint. Revised is still the least-bad fallback since
        # initial fails the same visible suite outright. Kept distinct from
        # "revised_both_visible_fail" so offline analysis can tell the two apart.
        code = revised_code
        selected_version = "revised_unconfirmed_fallback"
    else:
        code = revised_code
        selected_version = "revised_both_visible_fail"
    kept_initial = selected_version.startswith("initial")
    visible_ok = initial_visible_ok if kept_initial else revised_visible_ok
    responsible_agent = worker.agent_id if kept_initial else reviser.agent_id

    # 稽核：確定性抽樣（sha256(seed:task_id) < rate），跑隱藏測資
    h = int(hashlib.sha256(f"audit:{task['task_id']}".encode()).hexdigest()[:8], 16)
    audited = (h / 0xFFFFFFFF) < audit_rate
    audit_ok = None
    if audited:
        audit_ok, _ = meets_demand(
            code, task["hidden_check"]["code"], entry_point=task.get("entry_point"))

    accepted = visible_ok and (audit_ok is not False)
    return code, worker.agent_id, [a for a, _ in votes], {
        "votes": votes, "passed_review": passed_review,
        "raw_reviews": raw_reviews, "initial_code": initial_code,
        "review_evidence": review_evidence,
        "reviewer_models": [getattr(r, "model", None) for r in reviewers],
        "reviser": reviser.agent_id, "reviser_model": reviser.model,
        "initial_visible_ok": initial_visible_ok,
        "revised_visible_ok": revised_visible_ok,
        "confirmed_counterexample_count": len(confirmed_checks),
        "revised_fixes_counterexamples": revised_fixes_counterexamples,
        "selected_version": selected_version,
        "responsible_agent": responsible_agent,
        "visible_ok": visible_ok, "audited": audited,
        "audit_ok": audit_ok, "accepted": accepted,
    }


def arm_onr(task, agents, rng, calls, rep, *, audit_rate=0.2):
    """ON 的路由段單獨成臂：UCB 路由 + 1 次呼叫，沒有審查、沒有修訂。

    round212 新增。目的是把 `arm_on` 的第 1 次呼叫抽出來當一個獨立的臂，
    和 `arm_off`（均勻隨機挑 agent + 1 次呼叫）做**等預算**對比 ⇒ 唯一的
    差別是「挑誰來做」。round212 的離線拆解量到 ON_initial 81.77% vs
    OFF 79.28%（b/c=22/13, p=0.1755），方向為正但判別力不足；那次是跨兩個
    不同 run 配對的，這個臂讓同一個 run 內就能配對。

    刻意與 `arm_on` 共用同一條聲譽迴路：`_route_agent` 路由、只有真的抽到的
    hidden audit 才更新聲譽（`apply_audit_reputation`），抽樣規則
    `sha256("audit:"+task_id)` 與 `arm_on` 逐字元相同 ⇒ 同一題在兩個臂被
    抽到稽核與否是一致的，不是新的隨機來源。
    """
    worker = _route_agent(agents, rep, rng)
    txt = worker.generate(
        task["prompt"], role="gen",
        meta={"arm": "ONR", "task_id": task["task_id"]},
    )
    calls[0] += 1
    code = extract_code(txt)
    visible_ok, _ = meets_demand(
        code, task["visible_check"]["code"], entry_point=task.get("entry_point"))
    h = int(hashlib.sha256(f"audit:{task['task_id']}".encode()).hexdigest()[:8], 16)
    audited = (h / 0xFFFFFFFF) < audit_rate
    audit_ok = None
    if audited:
        audit_ok, _ = meets_demand(
            code, task["hidden_check"]["code"], entry_point=task.get("entry_point"))
    accepted = visible_ok and (audit_ok is not False)
    return code, worker.agent_id, [worker.agent_id], {
        "responsible_agent": worker.agent_id,
        "visible_ok": visible_ok,
        "audited": audited,
        "audit_ok": audit_ok,
        "accepted": accepted,
    }


def calibrate_pool(tasks, agents, rows_path: pathlib.Path) -> dict:
    """Measure pool heterogeneity on a disjoint set; never feed results into routing."""
    by_agent = {
        a.agent_id: {"model": a.model, "attempted": 0, "correct": 0, "infra_void": 0}
        for a in agents
    }
    rows = []
    for i, task in enumerate(tasks, 1):
        def run_one(agent):
            try:
                text = agent.generate(
                    task["prompt"], role="calibration",
                    meta={"arm": "CALIBRATION", "task_id": task["task_id"]},
                )
                code = extract_code(text)
                truth, err = meets_demand(
                    code, task["hidden_check"]["code"],
                    entry_point=task.get("entry_point"))
                return agent, truth, err, None
            except InfraVoid as exc:
                return agent, None, "", str(exc)

        # 依序送出，不用 ThreadPoolExecutor 併發：round22/23 已經在 arm_on／
        # arm_off5 量到對同一中轉端點併發送出多個請求會觸發 HTTP 500／逾時
        # （DECISION_20260824_SERIALIZE_CONCURRENT_CALLS.md），但 calibrate_pool
        # 是後來才加的，沒有套用那次修復。round210 用這支函式的併發版本卡死
        # 39 分鐘沒跑完第 1 題，round211 診斷成「qwen3.8-27b 這個 model 掛了」；
        # round262 重測發現連對**同一個** model 併發 3 筆都會炸（2 筆立即 500、
        # 1 筆逾時）——是併發本身觸發後端 contention，不是特定 model 死掉。
        results = [run_one(agent) for agent in agents]
        for agent, truth, err, void in results:
            stat = by_agent[agent.agent_id]
            if void is not None:
                stat["infra_void"] += 1
            else:
                stat["attempted"] += 1
                stat["correct"] += int(bool(truth))
            rows.append({
                "i": i, "task_id": task["task_id"], "agent_id": agent.agent_id,
                "model": agent.model, "meets_demand": truth,
                "infra_void": void, "err": err[:200],
            })
        print(f"  [CALIBRATION {i}/{len(tasks)}] 完成 {len(agents)} 個 agent", flush=True)

    with rows_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    for stat in by_agent.values():
        stat["accuracy"] = (
            stat["correct"] / stat["attempted"] if stat["attempted"] else None
        )
    accuracies = [s["accuracy"] for s in by_agent.values() if s["accuracy"] is not None]
    return {
        "tasks": len(tasks), "calls_expected": len(tasks) * len(agents),
        "by_agent": by_agent,
        "accuracy_spread": max(accuracies) - min(accuracies) if accuracies else None,
        "used_for_routing": False,
    }


def calibration_ready(result: dict) -> bool:
    """Require complete measurements and observed heterogeneity before causal claims."""
    tasks = result.get("tasks", 0)
    stats = list(result.get("by_agent", {}).values())
    return bool(
        tasks
        and stats
        and all(s.get("attempted") == tasks and s.get("infra_void") == 0 for s in stats)
        and result.get("accuracy_spread") is not None
        and result["accuracy_spread"] > 0
    )


def latency_summary(calls_path: pathlib.Path, arm: str) -> dict:
    """Summarize successful endpoint latency and failed attempts for one arm."""
    records = [json.loads(line) for line in calls_path.read_text().splitlines() if line]
    selected = [r for r in records if r.get("meta", {}).get("arm") == arm]

    def stats(values):
        if not values:
            return None
        ordered = sorted(values)

        def nearest_rank(p):
            return ordered[max(0, min(len(ordered) - 1, (len(ordered) * p + 99) // 100 - 1))]

        return {"n": len(ordered), "p50": nearest_rank(50), "p95": nearest_rank(95),
                "max": ordered[-1]}

    roles = sorted({r.get("role", "unknown") for r in selected if r.get("ok")})
    return {
        "all": stats([r["latency_ms"] for r in selected if r.get("ok")]),
        "by_role": {
            role: stats([r["latency_ms"] for r in selected
                         if r.get("ok") and r.get("role") == role])
            for role in roles
        },
        "failed_attempts": sum(1 for r in selected if not r.get("ok")),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    # R440G 閘門（機制，不是建議）：沒有一份「寫著這個 run 名字」的 DECISION 檔就拒絕啟動。
    # 迴圈三輪三次自發射未預註冊的 run（R440F），提示詞規則擋不住，改成 harness 擋。
    ap.add_argument("--decision", required=True,
        help="預註冊 DECISION 檔路徑；檔案必須存在且內文含 --out 的目錄名，否則不跑")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", default="g1")
    ap.add_argument("--arms", default="OFF,ON,OFF5")
    ap.add_argument("--bank", default="evalplus", choices=["evalplus", "builtin", "lcb"])
    ap.add_argument("--audit-rate", type=float, default=0.2)
    ap.add_argument(
        "--calibration-n", type=int, default=0,
        help="disjoint preflight tasks per agent; measured but never fed into routing",
    )
    ap.add_argument(
        "--probe-sample", type=int, default=12,
        help="instrument checks before model calls; 0 checks every selected task",
    )
    ap.add_argument(
        "--models", default=DEFAULT_MODEL,
        help="comma-separated model IDs, assigned round-robin across the open agent pool",
    )
    ap.add_argument(
        "--request-timeout-s", type=int, default=240,
        help="per-endpoint-attempt deadline; lower this for interactive/product pilots",
    )
    ap.add_argument(
        "--review-timeout-s", type=int, default=60,
        help="bounded deadline per reviewer attempt（clinepass-clean-v2 的死因修復）",
    )
    ap.add_argument(
        "--review-retries", type=int, default=2,
        help="reviewer attempts before the task is recorded as infra_void",
    )
    ap.add_argument(
        "--retries", type=int, default=4,
        help="endpoint attempts before the task is recorded as infra_void",
    )
    ap.add_argument("--retry-backoff-s", type=float, default=2.0)
    args = ap.parse_args()
    # ── R440G 預註冊閘門（在任何 mkdir/落盤之前：被拒的啟動不得留下空目錄）──
    _dec = pathlib.Path(args.decision)
    _run_name = pathlib.Path(args.out).name
    if not _dec.exists():
        raise SystemExit(f"拒絕啟動：DECISION 檔不存在 {_dec}（每個 run 都要先預註冊）")
    if _run_name not in _dec.read_text(encoding="utf-8", errors="replace"):
        raise SystemExit(f"拒絕啟動：{_dec.name} 內文沒有寫到 run 名字「{_run_name}」"
                         "——先把 run 名字與預測寫進 DECISION 再跑")
    print(f"預註冊閘門通過：{_dec.name} 授權 {_run_name}", flush=True)
    # round212：`--arms` 以前沒有 choices，dispatch 的 else 會把任何不認得的
    # 名字當成 ON 跑掉（打錯字＝安靜跑錯臂）。檢查放在 preflight 之前，
    # 打錯字不該先燒掉模型呼叫。
    KNOWN_ARMS = {"OFF", "OFF5", "ON", "ONR", "CONFORM"}
    if args.arms.strip() != "probe":
        _unknown = [a.strip() for a in args.arms.split(",")
                    if a.strip() and a.strip() not in KNOWN_ARMS]
        if _unknown:
            raise SystemExit(
                f"未知的臂 {_unknown}；可用：{sorted(KNOWN_ARMS)}（或 --arms probe）")
    if (args.request_timeout_s <= 0 or args.retries <= 0
            or args.review_timeout_s <= 0 or args.review_retries <= 0
            or args.retry_backoff_s < 0 or args.probe_sample < 0):
        raise SystemExit(
            "timeout/retries 必須為正數，backoff 與 probe-sample 不得為負"
        )

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    calls_log = out / "calls.jsonl"
    rows_path = out / "rows.jsonl"
    occupied = [
        p for p in (calls_log, rows_path, out / "summary.json", out / "notes.jsonl",
                    out / "calibration_rows.jsonl")
        if p.exists()
    ]
    if occupied:
        raise SystemExit(
            "輸出目錄已有實驗產物，拒絕 append 造成重複計數："
            + ", ".join(str(p) for p in occupied)
        )

    def note(obj):
        with (out / "notes.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")

    tasks = load_tasks(args.bank, args.seed, args.n)
    print(f"{len(tasks)} 題（{args.bank}）　輸出 {out}")

    # ── 先驗量具 ──
    print("── 量具驗證（先答已知答案）")
    probe_sample = len(tasks) if args.probe_sample == 0 else args.probe_sample
    pr = probe_instrument(tasks, note, sample=probe_sample, bank=args.bank)
    print(f"   參考解通過 {pr['ref_pass']}/{pr['n']}　"
          f"壞解被擋 {pr['broken_rejected']}/{pr['n']}")
    if pr["n"] == 0:
        raise SystemExit("量具驗證一題都沒驗到——這不是通過，是沒接上。停。")
    if pr["ref_pass"] < pr["n"] or pr["broken_rejected"] < pr["n"]:
        raise SystemExit("量具沒有兩個方向都答對——在壞尺上跑實驗等於沒跑。停。")
    if args.arms.strip() == "probe":
        return

    # 量具探針是零模型呼叫；只有真的跑 arm 才要求秘密憑證。
    keys = load_keys()
    models = [model.strip() for model in args.models.split(",") if model.strip()]
    if not models:
        raise SystemExit("--models 至少要有一個 model ID")
    agents = [ClineBrain(aid, sys_p, key=keys[i % len(keys)], log_path=calls_log,
                         model=models[i % len(models)],
                         timeout_s=args.request_timeout_s, retries=args.retries,
                         backoff_s=args.retry_backoff_s)
              for i, (aid, sys_p) in enumerate(POOL)]
    print(f"── 模型池：{len(agents)} 個 agent／{len(set(models))} 個模型家族")

    # ── 模型池預檢：每個設定的 model 先問一句，答不出來就停 ──────────────
    #
    # 為什麼要有這一步（2026-08-24 燒掉兩輪換來的）：
    # agent 分配是 `models[i % len(models)]`，**決定性**不是隨機。傳兩個模型
    # 而其中一個不可達時，index 為奇數的 agent（POOL 裡所有 `-2` 尾碼）
    # 保證 100% 失敗——不管跑幾題都是那一半。runs/g_off60_relay_20260824
    # 就是這樣拿到 18/60 infra_void（30%，接近一半），超過判決表的 10% 擋門，
    # 整輪 f 作廢；當時中轉根本沒有服務 nemotron，而我們跑了 55 分鐘才知道。
    #
    # 這跟既有的「量具要先答已知答案」是同一條紀律：**在壞尺上跑實驗等於沒跑**，
    # 在死掉的模型上跑實驗也一樣。差別只是量具驗的是判定邏輯，這裡驗的是後端。
    # 成本是每個 model 一次呼叫；省下的是一整輪。
    print("── 模型池預檢（每個 model 問一句，零容忍）")
    for model_id in dict.fromkeys(models):          # 去重但保留順序
        probe = ClineBrain("preflight", "You are a helpful assistant.",
                           key=keys[0], log_path=calls_log, model=model_id,
                           timeout_s=min(args.request_timeout_s, 120), retries=2,
                           backoff_s=args.retry_backoff_s)
        try:
            reply = probe.generate("Reply with exactly: OK",
                                   role="preflight", meta={"model": model_id})
        except InfraVoid as exc:
            raise SystemExit(
                f"模型 {model_id} 預檢失敗：{exc}\n"
                f"  這個 model 分到的 agent 會 100% 失敗（分配是 i % len(models)，"
                f"決定性不是隨機）。\n"
                f"  先確認端點真的服務這個 model，或把它從 --models 拿掉。"
            ) from exc
        print(f"   {model_id}　回 {len(reply)} 字　✓")

    calibration = None
    if args.calibration_n:
        calibration_tasks = load_tasks(
            args.bank, args.seed, args.calibration_n, offset=len(tasks)
        )
        if len(calibration_tasks) != args.calibration_n:
            raise SystemExit("題庫不足以建立與正式題不重疊的 calibration set")
        print(f"── Agent calibration：{len(calibration_tasks)} 題，結果不餵回路由")
        calibration_cost_before = sum(a.cost for a in agents)
        calibration_market_before = sum(a.market_cost for a in agents)
        calibration = calibrate_pool(
            calibration_tasks, agents, out / "calibration_rows.jsonl"
        )
        calibration["cost_usd"] = round(
            sum(a.cost for a in agents) - calibration_cost_before, 4)
        calibration["market_cost_usd"] = round(
            sum(a.market_cost for a in agents) - calibration_market_before, 4)
        print(f"── calibration spread: {calibration['accuracy_spread']}")
        if not calibration_ready(calibration):
            raise SystemExit(
                "calibration 未完整量到每個 agent，或沒有觀察到能力差距；"
                "信譽路由缺少成立前提，拒絕繼續跑 arm。"
            )

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    summary = {}

    def write_summary(*, run_complete: bool) -> None:
        equal_budget_valid = bool(
            summary.get("ON", {}).get("complete")
            and summary.get("OFF5", {}).get("complete")
            and summary.get("ON", {}).get("calls_per_task") == 5
            and summary.get("OFF5", {}).get("calls_per_task") == 5
        )
        # `run_complete` 要求零 void（比例才可信），有 void 的 run 永遠是 False——
        # R516 §8 抓到的是下游拿它當「這輪跑完了沒」的訊號會永遠等不到 True。
        # `run_terminal` 只回答「迴圈是不是把每個 task 都跑到底了」，
        # 不管中途有沒有 void；兩個訊號分開才不會互相冒充。
        run_terminal = bool(arms) and all(
            summary.get(a, {}).get("terminal") for a in arms
        )
        (out / "summary.json").write_text(
            json.dumps({
                "seed": args.seed,
                "n": args.n,
                "run_complete": run_complete,
                "run_terminal": run_terminal,
                "request_policy": {
                    "timeout_s": args.request_timeout_s,
                    "retries": args.retries,
                    "backoff_s": args.retry_backoff_s,
                    "review_timeout_s": args.review_timeout_s,
                    "review_retries": args.review_retries,
                },
                "pool": [
                    {"agent_id": a.agent_id, "model": a.model} for a in agents
                ],
                "instrument": pr,
                "calibration": calibration,
                "arms": summary,
                "equal_budget_comparison_valid": equal_budget_valid and run_complete,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # Keep validated preflight metadata even if an endpoint or operator stops the
    # run before the first arm finishes.
    write_summary(run_complete=False)
    # round278：arm 順序改交錯（`for task: for arm:`）。round138 已經驗證過這是
    # 統計上免費的：`tasks` 在 arm 迴圈之外只建一次 ⇒ 兩臂題序相同；
    # `rng`/`rep`/`calls` 每臂各一份；`grep -n "random\." | grep -v rng` 為空
    # ⇒ 沒有共用的全域亂數狀態。每臂的抽樣序列只取決於「該臂依題序處理的順序」，
    # 交錯不改變它 ⇒ 每一格 (arm, task) 的抽樣與循序版逐字元相同。
    #
    # 為什麼要改：循序版是 `for arm: for task:` ⇒ ON 全部 179 題跑完才碰第一題
    # OFF5。r274 實測 ON 6.7 分/列 ⇒ **第一筆 OFF5 要等 20 小時**，而 OFF5 是
    # 唯一能回答「等預算誰贏」的臂（判準 3）。跑了 20 小時以內被中斷 ⇒ OFF5 = 0。
    # 這不是假想：r271 在 1h49m 被中止、g_onoff5_371_r123 也是中途停的。
    st = {
        arm: {
            "rng": random.Random(f"{args.seed}:{arm}"),
            "rep": {a.agent_id: {"n": 0, "ok": 0} for a in agents},
            # CONFORM 的收據鏈：每臂一條，簽章身份只在本 run 內存活
            # （私鑰不落盤——RECORD_SPEC §7 排除 identity.key）。
            "book": Logbook(),
            "ident": Identity.generate(),
            "calls": [0],
            "n_acc": 0, "n_acc_ok": 0, "n_void": 0,
            "rv_correct": 0, "rv_total": 0, "rv_raw_correct": 0,
            "fail_claims": 0, "confirmed_claims": 0, "confirmed_on_wrong": 0,
            "raw_correct": 0, "processed": 0,
            "transitions": {"improved": 0, "harmed": 0,
                            "stayed_correct": 0, "stayed_wrong": 0},
            # 交錯之後「臂的 wall time」不能再用 t_end - t_start（兩臂在時間上
            # 交纏）。改成逐格累加該格實際耗時＝該臂的作用時間。循序版這兩個數字
            # 幾乎相同；交錯版只有累加版有意義。
            "wall_s": 0.0, "cost": 0.0, "market_cost": 0.0,
        }
        for arm in arms
    }

    def finalize(arm: str) -> dict:
        s = st[arm]
        measured = s["processed"] - s["n_void"]
        n_acc, n_acc_ok, calls_n = s["n_acc"], s["n_acc_ok"], s["calls"][0]
        rv_total = s["rv_total"]
        return {
            "tasks": len(tasks), "calls": calls_n, "infra_void": s["n_void"],
            # ⚠ 循序版寫 `n_void == 0` 就夠，因為 summary[arm] 只在該臂整個題目
            #   迴圈跑完之後才寫一次。交錯版每一格都會寫 summary ⇒ 一個才跑到
            #   第 3 題、還沒遇到 void 的臂會被寫成 complete=True。必須連
            #   `processed == len(tasks)` 一起要求，否則就是 round224 那個
            #   「run_complete 說跑完了、其實一格都沒量到」的同型錯誤。
            "complete": s["n_void"] == 0 and s["processed"] == len(tasks),
            # `complete` 綁死零 void，是「比例可不可信」的判準，不是「跑完了沒」——
            # 只要這一輪有任何 void（infra_void 規則本來就預期會有）它就永遠 False，
            # 下游拿 complete 當收官訊號會永遠等不到（R516 §8）。`terminal` 只問
            # 迴圈有沒有把每個 task 都處理過一次，void 不影響它。
            "terminal": s["processed"] == len(tasks),
            "processed": s["processed"],
            "accepted": n_acc, "accepted_and_meets_demand": n_acc_ok,
            "demand_equals_output_rate": (n_acc_ok / n_acc) if n_acc else None,
            "coverage": (n_acc / measured) if measured else None,
            "correct_delivery_rate": (n_acc_ok / measured) if measured else None,
            "raw_final_accuracy": (s["raw_correct"] / measured) if measured else None,
            "calls_per_task": (calls_n / measured) if measured else None,
            "calls_per_correct_delivery": (calls_n / n_acc_ok) if n_acc_ok else None,
            "leaked": n_acc - n_acc_ok,
            "reviewer_accuracy": (s["rv_correct"] / rv_total) if rv_total else None,
            "raw_reviewer_accuracy": (
                s["rv_raw_correct"] / rv_total if rv_total else None),
            "reviewer_votes": rv_total,
            "review_fail_claims": s["fail_claims"],
            "machine_confirmed_counterexamples": s["confirmed_claims"],
            "confirmed_counterexample_precision_against_hidden_truth": (
                s["confirmed_on_wrong"] / s["confirmed_claims"]
                if s["confirmed_claims"] else None),
            "revision_transitions": s["transitions"] if arm == "ON" else None,
            "endpoint_latency_ms": latency_summary(calls_log, arm),
            "wall_s": round(s["wall_s"], 1),
            "cost_usd": round(s["cost"], 4),
            "market_cost_usd": round(s["market_cost"], 4),
            "market_cost_per_correct_delivery": (
                round(s["market_cost"] / n_acc_ok, 6) if n_acc_ok else None),
        }

    for i, t in enumerate(tasks, 1):
        for arm in arms:
            s = st[arm]
            rng, rep, calls = s["rng"], s["rep"], s["calls"]
            calls_before = calls[0]
            cell_t0 = time.time()
            cost_before = sum(a.cost for a in agents)
            market_cost_before = sum(a.market_cost for a in agents)
            s["processed"] += 1
            try:
                if arm == "OFF":
                    code, worker, involved, extra = arm_off(t, agents, rng, calls)
                    accepted = True
                elif arm == "OFF5":
                    code, worker, involved, extra = arm_off5(t, agents, rng, calls)
                    accepted = True
                elif arm == "ONR":
                    code, worker, involved, extra = arm_onr(
                        t, agents, rng, calls, rep, audit_rate=args.audit_rate)
                    accepted = extra["accepted"]
                elif arm == "CONFORM":
                    code, worker, involved, extra = arm_conform(
                        t, agents, rng, calls, s["book"], s["ident"])
                    accepted = extra["accepted"]
                elif arm == "ON":
                    code, worker, involved, extra = arm_on(
                        t, agents, rng, calls, rep, audit_rate=args.audit_rate,
                        review_timeout_s=args.review_timeout_s,
                        review_retries=args.review_retries)
                    accepted = extra["accepted"]
            except InfraVoid as e:
                s["n_void"] += 1
                s["wall_s"] += time.time() - cell_t0
                s["cost"] += sum(a.cost for a in agents) - cost_before
                s["market_cost"] += (
                    sum(a.market_cost for a in agents) - market_cost_before)
                note({"arm": arm, "task_id": t["task_id"], "infra_void": str(e)})
                continue

            truth, err = meets_demand(
                code, t["hidden_check"]["code"], entry_point=t.get("entry_point"))
            s["raw_correct"] += int(truth)
            if arm == "ONR":
                # 與 ON 同一條聲譽迴路：只有真的抽到的 audit 能更新，truth 不回餵。
                apply_audit_reputation(
                    rep, extra["responsible_agent"], extra["audit_ok"])
            if arm == "ON":
                # truth 是離線評分，不能餵回產品；路由只吃真的抽樣 audit。
                apply_audit_reputation(
                    rep, extra["responsible_agent"], extra["audit_ok"])
                initial_truth, _ = meets_demand(
                    extra["initial_code"], t["hidden_check"]["code"],
                    entry_point=t.get("entry_point"))
                transition = (
                    "improved" if not initial_truth and truth else
                    "harmed" if initial_truth and not truth else
                    "stayed_correct" if initial_truth else "stayed_wrong"
                )
                s["transitions"][transition] += 1
                extra["initial_meets_demand"] = initial_truth
                extra["revision_transition"] = transition
                # 評審看的是 initial_code，不能拿修訂後 final truth 幫它算對。
                for _, v in extra["votes"]:
                    s["rv_total"] += 1
                    s["rv_correct"] += int(v == initial_truth)
                for evidence in extra["review_evidence"]:
                    s["rv_raw_correct"] += int(evidence["raw_pass"] == initial_truth)
                    if not evidence["raw_pass"]:
                        s["fail_claims"] += 1
                    if evidence["counterexample_confirmed"]:
                        s["confirmed_claims"] += 1
                        s["confirmed_on_wrong"] += int(not initial_truth)
            if accepted:
                s["n_acc"] += 1
                s["n_acc_ok"] += int(truth)

            s["wall_s"] += time.time() - cell_t0
            s["cost"] += sum(a.cost for a in agents) - cost_before
            s["market_cost"] += (
                sum(a.market_cost for a in agents) - market_cost_before)

            with rows_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "arm": arm, "seed": args.seed, "i": i,
                    "task_id": t["task_id"], "family": t["family"], "entry_point": t.get("entry_point"),
                    "worker": worker, "involved": involved,
                    "meets_demand": truth, "err": err[:200],
                    "accepted": accepted, "calls_used": calls[0] - calls_before,
                    "calls_so_far": calls[0],
                    **{k: v for k, v in extra.items()
                       if k not in {"votes", "raw_reviews", "initial_code"}},
                    "votes": extra.get("votes"),
                }, ensure_ascii=False) + "\n")
            print(f"  [{arm} {i}/{len(tasks)}] 需求符合={truth} 接受={accepted} "
                  f"累計呼叫={calls[0]}", flush=True)

        # 交錯的重點就在這裡：每跑完一題的所有臂就把 summary 全部重寫一次，
        # 中斷在任何時刻都會留下**兩臂格數相等**的可分析資料。
        for arm in arms:
            summary[arm] = finalize(arm)
        write_summary(run_complete=False)

    for arm in arms:
        print(f"── {arm}: {json.dumps(summary[arm], ensure_ascii=False)}")

    # ⚠ 2026-08-24 實測抓到：這裡原本無條件寫 True。runs/g_off60_20260824 那一輪
    #   端點 403、60 題全部 infra_void、每臂 complete=False，頂層卻是
    #   run_complete: true。SPEC_GAIN §7 寫的是「只有全部指定臂完成才設 true」。
    #   幾個月後翻歸檔 JSONL 的人第一眼看的就是這個欄位——它說跑完了，
    #   而那一輪其實一格都沒量到。
    all_arms_complete = all(summary.get(a, {}).get("complete") for a in arms)
    write_summary(run_complete=all_arms_complete)
    if not all_arms_complete:
        incomplete = [a for a in arms if not summary.get(a, {}).get("complete")]
        print(f"⚠ run_complete=False——這些臂沒跑完：{', '.join(incomplete)}。"
              f"這一輪的比例不得拿去比較（SPEC_GAIN §7）。")
    print(f"\n寫出 {out/'summary.json'}")
    print("⚠ 這是待驗證的宣稱不是結果——OFF5 沒跑贏之前不能說機制有效。")


if __name__ == "__main__":
    main()
