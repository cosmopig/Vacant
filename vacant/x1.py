"""X1 — 記憶→品質 主實驗與遷移 pilot（10 §4；裁決 W1「pilot v0 不等 demo」）。

設計（10 §4.1）：單一 Resident 走連續任務流，每題 生成→交付→稽核（X1 稽核率
100%，驗的是記憶通道不是稽核稀缺）→稽核結論寫入 MemoryStream→下一題。
三臂 M0/M1/M2 同題序、同身體、同 seed 配對；記憶各自隨軌跡生長（禁用跨臂快取）。

任務流（10 §4.2）：任務按「家族」組織——族內坑型重複出現、表面題目不同；
變體生成規則在此檔寫死（deterministic by (family, index)），變體測資守隱藏
測資紀律（prompt 只給描述＋一個可見例，隱藏測試不出現在 prompt）。

pilot 判準（一票否決）：族內序列上「見過族內 m 題（帶稽核結論）後第 m+1 題
的提升」；oracle-lesson 條件（把正確教訓直接給它）都測不到遷移 → 任務集重選。
裁決 A3 加驗：非 oracle 管線的實現遷移率、變體與原題相似度上界。

KS-1（10 §4.5）：PROMPT_TEMPLATE 三臂逐字相同、經 assert_ks1_clean 檢查；
唯一差異是 {memory} 槽的內容，而那些內容全部由管線真實生成。

⚠️ 本檔的任務族是 pilot v0 種子集；正式 X1 的 MBPP+ 分族與凍結在 W3
（裁決 §3-C），屆時任務來源替換、harness 不動。
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .auditor import Auditor
from .batch import RunLedger
from .checks import compile_check
from .memory import MemoryManager, MemoryStream, assert_ks1_clean

# --- 三臂逐字相同的 prompt 模板（KS-1 承重點）---------------------------------

PROMPT_TEMPLATE = """{memory}

請寫一個 Python 函式解下面的題目。只輸出程式碼（可用 ```python fence），
函式名必須是 solve。

{task}
"""


# --- 任務族與變體生成（規則寫死、確定性）-------------------------------------

@dataclass
class X1Task:
    task_id: str
    family: str
    pitfall: str           # 坑型標籤（族內重複出現的那個坑）
    prompt: str            # 題目描述＋一個可見例（不含隱藏測資）
    check: dict            # {"type":"run_python","code": 隱藏 asserts}
    variant_params: dict[str, Any] = field(default_factory=dict)


# 每族的 oracle 教訓：坑型層級抽象、零逐字測資（裁決 A4 蒸餾規則的示範樣本）。
ORACLE_LESSONS = {
    "string_edge": (
        "字串處理題最常在三種輸入上出錯：空字串、單一字元、全部相同字元。"
        "實作前先寫下這三種輸入的期望輸出，並確認迴圈邊界對它們成立。"
    ),
    "off_by_one": (
        "切片與分組題的坑在圍籬柱：最後一段不足 k 個時的處理、起點是 0-index "
        "還是 1-index、range 終點是否含尾。先用「長度剛好整除」與「差 1」兩種長度心算一次。"
    ),
    "state_parse": (
        "解析/狀態機題的坑在狀態未正確重置與巢狀深度：遇到關閉符號時必須檢查"
        "棧頂配對而不只是計數；輸入結束時棧必須為空才算合法。"
    ),
}


def _tid(family: str, idx: int) -> str:
    return hashlib.sha256(f"x1:{family}:{idx}".encode()).hexdigest()[:12]


def _string_edge(idx: int) -> X1Task:
    variants = [
        # (描述, 可見例, 隱藏測試)
        ("壓縮相鄰重複字元：把連續重複的字元縮成一個。",
         "solve('aabbcc') == 'abc'",
         "assert solve('aaab')=='ab'\nassert solve('')==''\nassert solve('x')=='x'\n"
         "assert solve('zzzz')=='z'\nassert solve('abab')=='abab'"),
        ("去掉字串頭尾成對出現的相同字元（鏡像修剪），直到頭尾不同。",
         "solve('abcba') == 'c'",
         "assert solve('aa')==''\nassert solve('')==''\nassert solve('a')=='a'\n"
         "assert solve('abba')==''\nassert solve('abc')=='abc'"),
        ("把字串中的空白連跑（一個以上連續空白）壓成單一空格，並去頭尾空白。",
         "solve('a  b') == 'a b'",
         "assert solve('  ')==''\nassert solve('')==''\nassert solve(' a ')=='a'\n"
         "assert solve('a\\t\\tb')=='a b'\nassert solve('ab')=='ab'"),
        ("回傳字串中第一個不重複出現的字元；沒有則回空字串。",
         "solve('aabbc') == 'c'",
         "assert solve('')==''\nassert solve('x')=='x'\nassert solve('aabb')==''\n"
         "assert solve('abcab')=='c'\nassert solve('aa')==''"),
        ("判斷字串去掉非字母後是否為回文（不分大小寫），回傳 True/False。",
         "solve('A man, a plan') == False",
         "assert solve('')==True\nassert solve('a')==True\nassert solve('ab')==False\n"
         "assert solve('Aa')==True\nassert solve('a!!a')==True"),
    ]
    desc, example, tests = variants[idx % len(variants)]
    return X1Task(
        task_id=_tid("string_edge", idx), family="string_edge",
        pitfall="empty/single/uniform 邊界",
        prompt=f"{desc}\n可見例：{example}",
        check={"type": "run_python", "code": tests},
        variant_params={"variant": idx % len(variants), "round": idx // len(variants)},
    )


def _off_by_one(idx: int) -> X1Task:
    k = 2 + (idx % 3)  # 參數化：k ∈ {2,3,4}
    variants = [
        (f"把 list 切成每 {k} 個一組（最後一組可不足 {k}），回傳 list of lists。",
         f"solve([1,2,3,4,5]) 的第一組是 [1,2{',3' if k >= 3 else ''}{',4' if k >= 4 else ''}]",
         f"assert solve([])==[]\nassert solve([1])==[[1]]\n"
         f"assert solve(list(range({k})))==[list(range({k}))]\n"
         f"assert solve(list(range({k + 1})))==[list(range({k})),[{k}]]\n"
         f"assert len(solve(list(range({3 * k}))))==3"),
        (f"取 list 中第 {k}、第 {2 * k}、第 {3 * k}…個元素（1-index），回傳新 list。",
         f"solve([10,20,30,40]) 對 k={k} 取第 {k} 個起",
         f"assert solve([])==[]\nassert solve(list(range(1,{k})))==[]\n"
         f"assert solve(list(range(1,{k + 1})))==[{k}]\n"
         f"assert solve(list(range(1,{2 * k + 1})))==[{k},{2 * k}]"),
        (f"回傳長度為 {k} 的滑動視窗個數（len(xs)-{k}+1，不足時為 0）。",
         f"solve([1,2,3]) 在 k={k} 時＝{max(0, 3 - k + 1)}",
         f"assert solve([])==0\nassert solve(list(range({k - 1})))==0\n"
         f"assert solve(list(range({k})))==1\nassert solve(list(range({k + 2})))==3"),
    ]
    desc, example, tests = variants[idx % len(variants)]
    return X1Task(
        task_id=_tid("off_by_one", idx), family="off_by_one",
        pitfall="fence-post／最後一段不足 k",
        prompt=f"{desc}\n可見例：{example}",
        check={"type": "run_python", "code": tests},
        variant_params={"variant": idx % len(variants), "k": k},
    )


def _state_parse(idx: int) -> X1Task:
    variants = [
        ("判斷括號序列是否合法配對，支援 ()[]{} 三種，回傳 True/False。",
         "solve('([])') == True",
         "assert solve('')==True\nassert solve('(')==False\nassert solve('([)]')==False\n"
         "assert solve('()[]{}')==True\nassert solve(']')==False"),
        ("run-length 解碼：輸入形如 'a3b1' 的字串，回傳展開結果（次數為個位數）。",
         "solve('a3b1') == 'aaab'",
         "assert solve('')==''\nassert solve('a1')=='a'\nassert solve('a9')=='a'*9\n"
         "assert solve('a2b3')=='aabbb'\nassert solve('x1y1')=='xy'"),
        ("解析 'k=v;k2=v2' 形式的字串成 dict（值可為空字串；無分號尾）。",
         "solve('a=1;b=2') == {'a':'1','b':'2'}",
         "assert solve('')=={}\nassert solve('a=')=={'a':''}\n"
         "assert solve('a=1')=={'a':'1'}\nassert solve('a=1;b=')=={'a':'1','b':''}"),
    ]
    desc, example, tests = variants[idx % len(variants)]
    return X1Task(
        task_id=_tid("state_parse", idx), family="state_parse",
        pitfall="狀態重置／棧頂配對／結尾檢查",
        prompt=f"{desc}\n可見例：{example}",
        check={"type": "run_python", "code": tests},
        variant_params={"variant": idx % len(variants), "round": idx // len(variants)},
    )


FAMILIES: dict[str, Callable[[int], X1Task]] = {
    "string_edge": _string_edge,
    "off_by_one": _off_by_one,
    "state_parse": _state_parse,
}


# --- EvalPlus 整合（G1 後段；GT 隔離的承重點）---------------------------------
def task_from_dict(d: dict[str, Any]) -> X1Task:
    """把 TaskLoader 的任務 dict（EvalPlus 真資料）轉成 X1Task。

    GT 隔離紀律（lab P0-evalplus-x1-integration 同規）：
      - prompt 只放 public projection（task["prompt"]，loader 已保證不含 GT）；
      - hidden_check 進 task.check——它是 verifier 側物件，**只**被
        compile_check／auditor／A4 洩漏防呆消費，run_x1 的 prompt／episode／
        trace／ledger 一律不序列化它（canary 負向測試見 tests/test_x1_evalplus.py）。
    """
    return X1Task(
        task_id=d["task_id"],
        family=d.get("family", "general"),
        pitfall=d.get("family", "general"),
        prompt=d["prompt"],
        check=d["hidden_check"],
        variant_params={"source": "evalplus", "entry_point": d.get("entry_point", "solve")},
    )


def load_x1_tasks(loader: Any, seed: Any, n: int) -> list[X1Task]:
    """從 TaskLoader 取 n 題轉成 X1Task（正式 X1 的任務來源；17 §P1-2 凍結用）。"""
    import itertools
    return [task_from_dict(d) for d in itertools.islice(loader.iter_tasks(seed), n)]


def template_sha256() -> str:
    """三臂共用模板的 sha256——KS-1「模板逐字相同」的可落盤斷言（17 §P1-3）。"""
    return hashlib.sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest()


def make_family_sequence(family: str, n: int) -> list[X1Task]:
    """族內序列：同族 n 題（變體循環＋參數變化），確定性生成。"""
    return [FAMILIES[family](i) for i in range(n)]


def make_pilot_tasks(n_per_family: int = 17) -> list[X1Task]:
    """pilot 預設 ~50 題（3 族 × 17）；順序＝族內連續（量族內遷移用）。"""
    out: list[X1Task] = []
    for fam in FAMILIES:
        out.extend(make_family_sequence(fam, n_per_family))
    return out


# --- pilot / 主實驗迴圈 --------------------------------------------------------

def _digest(x: Any) -> str:
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)
                          .encode()).hexdigest()[:16]


def run_x1(
    brain,                       # Brain protocol：generate(prompt)->str
    policy: str,                 # "M0" | "M1" | "M2"
    tasks: list[X1Task],
    *,
    stream: MemoryStream,
    manager: MemoryManager | None = None,
    auditor: Auditor | None = None,
    ledger: RunLedger | None = None,
    seed: str = "s0",
    oracle: bool = False,        # pilot：稽核後直接寫入該族 oracle 教訓
    distill: Callable[[X1Task, str, bool], str | None] | None = None,  # 正式：+1 呼叫蒸餾
    trace_path: Path | None = None,
    retries: int = 4,
    retry_backoff_s: float = 2.0,
    require_usage: bool = False,  # 正式 run：缺端點 usage → infra_void（測量層紀律）
    now_ms: Callable[[], int] = lambda: time.time_ns() // 1_000_000,
    _sleep: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """一條臂跑完整任務流。回傳逐題記錄（全 I/O 落盤到 trace_path）。

    X1 紀律：稽核率 100%（forced）；retry×4（指數 backoff）後仍 infra 錯 →
    outcome=infra_void 且**不記入 ledger**（下次 resume 自動重試——瞬斷不留永久洞）；
    斷點續跑靠 ledger 以 (policy, task_id, seed) 跳過已完成格，並把已完成格的
    episode **重播回 MemoryStream**（否則 resume 後 M1/M2 臂帶著殘缺記憶跑，
    整條臂的記憶→品質訊號作廢）。
    """
    manager = manager or MemoryManager(policy)
    auditor = auditor or Auditor(rate=1.0)
    assert_ks1_clean(PROMPT_TEMPLATE)
    records: list[dict[str, Any]] = []

    for task in tasks:
        if ledger is not None and ledger.is_done(policy, task.task_id, seed):
            done = ledger.result(policy, task.task_id, seed) or {}
            # resume 重播：把已完成格的 episode 依 ledger 記錄重建進 stream，
            # 讓後續任務的記憶注入與未中斷的 run 完全一致（確定性重建）。
            if done.get("outcome") in ("pass", "fail"):
                manager.record(
                    stream,
                    task_id=task.task_id,
                    spec_digest=done.get("spec_digest", ""),
                    answer_digest=done.get("answer_digest", ""),
                    reviews=[],
                    audit=done.get("audit"),
                    outcome=done["outcome"],
                    lesson=done.get("lesson"),
                    check=task.check,
                    ts_ms=done.get("ts_ms", 0),
                )
            records.append(done)
            continue

        memory_block = manager.inject(stream, task.prompt)
        prompt = PROMPT_TEMPLATE.format(memory=memory_block, task=task.prompt)

        answer, infra_error = "", None
        gen_t0 = now_ms()
        for attempt in range(retries):
            try:
                answer = brain.generate(prompt)
                infra_error = None
                break
            except Exception as e:  # 端點瞬斷等 infra 錯：retry×4＋指數 backoff
                infra_error = f"{type(e).__name__}: {e}"
                if attempt < retries - 1 and retry_backoff_s > 0:
                    _sleep(retry_backoff_s * (2 ** attempt))
        gen_wall_ms = now_ms() - gen_t0
        ts = now_ms()

        # 真實成本（17 §P1／lab real-cost-ledger）：端點實回 usage，不用字數代理。
        usage = getattr(brain, "last_usage", None)
        if infra_error is None and require_usage and not usage:
            # 測量層 infra_void：呼叫成功但成本沒落盤——缺 usage 的 trial 永不進
            # 正式分母（同 infra_void 紀律：不計票、resume 重試）。
            infra_error = "usage_missing: 端點未回 usage（require_usage=True）"

        if infra_error is not None:
            outcome, passed, audit_rec = "infra_void", None, None
        else:
            passed = bool(compile_check(task.check)(answer))
            outcome = "pass" if passed else "fail"
            audit_rec = auditor.audit(
                task_id=task.task_id, target_id=stream.logbook.stream_id() or "",
                answer=answer, check=task.check, claimed_pass=passed,
                ts_ms=ts, forced=True,  # X1 稽核率 100%
            )

        lesson = None
        if audit_rec is not None and audit_rec.ran:
            if oracle:
                lesson = ORACLE_LESSONS[task.family]
            elif distill is not None:
                lesson = distill(task, answer, bool(audit_rec.passed))  # +1 呼叫

        if outcome != "infra_void":
            manager.record(
                stream,
                task_id=task.task_id,
                spec_digest=_digest(task.prompt),
                answer_digest=_digest(answer),
                reviews=[],
                audit=(audit_rec.to_json() if audit_rec else None),
                outcome=outcome,
                lesson=lesson,
                check=task.check,
                ts_ms=ts,
            )

        rec = {
            "policy": policy, "seed": seed, "task": task.task_id,
            "family": task.family, "variant": task.variant_params,
            "outcome": outcome, "passed": passed,
            "audit": (audit_rec.to_json() if audit_rec else None),
            "memory_tokens": len(memory_block) // 4,
            "lesson_written": bool(lesson), "infra_error": infra_error, "ts_ms": ts,
            # 真實成本落盤（缺 usage 的 trial 已在上面判 infra_void）
            "usage": usage if outcome != "infra_void" else None,
            "gen_wall_ms": gen_wall_ms,
            # resume 重播 episode 所需（見迴圈開頭）：
            "spec_digest": _digest(task.prompt), "answer_digest": _digest(answer),
            "lesson": lesson,
        }
        if trace_path:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            with trace_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({**rec, "prompt_sha": _digest(prompt),
                                    "answer": answer}, ensure_ascii=False) + "\n")
        # infra_void 不記入 ledger：瞬斷的格子下次 resume 重試，不留永久洞。
        if ledger is not None and outcome != "infra_void":
            ledger.mark_done(policy, task.task_id, seed, rec)
        records.append(rec)
    return records


def transfer_curve(records: list[dict[str, Any]]) -> dict[str, list[float]]:
    """pilot 判準的原料：每族「第 m 題」的逐題通過序列（0/1，infra_void 剔除）。

    遷移存在 ＝ 序列後段（見過族內 m 題帶稽核結論）通過率高於前段；
    統計檢定（McNemar/bootstrap）用 research.py 的既有函式在分析端做。"""
    by_family: dict[str, list[float]] = {}
    for r in records:
        if r["outcome"] == "infra_void":
            continue
        by_family.setdefault(r["family"], []).append(1.0 if r["passed"] else 0.0)
    return by_family


def pilot_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    """oracle-lesson 一票否決判準（10 §4.2／17 §P1-3）：族內前後半配對 McNemar。

    配對方式：同族第 i 題（前半）對第 i 題（後半）——變體循環使同位題同型；
    b＝前錯後對（遷移證據）、c＝前對後錯。判準事前寫死：
      - pooled（跨族合計）b>c 且 mcnemar_exact p<.05 → transfer_detected=True；
      - 連 oracle-lesson 都測不到 → 任務集重選；三度重選仍無 → 回退 X3 主線
        （10 §4.2，決定進 ledger、通知人類）。
    誠實邊界：這是「任務集是否有可測遷移」的工程判準，不是 trust effect 的宣稱。
    """
    from .research import mcnemar_exact
    curve = transfer_curve(records)
    per_family: dict[str, Any] = {}
    b_all = c_all = 0
    for fam, seq in curve.items():
        half = len(seq) // 2
        front, back = seq[:half], seq[half:half * 2]
        b = sum(1 for f0, b0 in zip(front, back) if f0 == 0.0 and b0 == 1.0)
        c = sum(1 for f0, b0 in zip(front, back) if f0 == 1.0 and b0 == 0.0)
        b_all += b
        c_all += c
        per_family[fam] = {
            "n": len(seq), "front_pass": f"{int(sum(front))}/{len(front)}",
            "back_pass": f"{int(sum(back))}/{len(back)}",
            "b": b, "c": c, "p": mcnemar_exact(b, c),
        }
    p_pool = mcnemar_exact(b_all, c_all)
    detected = bool(b_all > c_all and p_pool < 0.05)
    return {
        "per_family": per_family,
        "pooled": {"b": b_all, "c": c_all, "p": p_pool},
        "transfer_detected": detected,
        "verdict": (
            "oracle-lesson 遷移存在（任務集保留）" if detected
            else "oracle-lesson 測不到遷移 → 任務集重選（三度仍無 → 回退 X3，10 §4.2）"
        ),
    }


# --- RECORD_SPEC 證據包收尾（17 §P1-3 的 run 合格門；紀錄紅線：不 pack＝沒跑過）--
def finalize_run_package(
    run_dir: Path,
    *,
    policy: str,
    stream: MemoryStream,
    tasks: list[X1Task],
    records: list[dict[str, Any]],
    trace_path: Path | None,
    extra_meta: dict[str, Any],
) -> tuple[bool, list[str]]:
    """把一條臂的產物整理成 RECORD_SPEC 合格包，回 check 的 (ok, problems)。

    產出（缺任一 → check 點名）：
      model_io.jsonl        ← trace（每次呼叫全 I/O；鐵律 3 本體）
      ledger_events.jsonl   ← 逐題 X1_TRIAL 事件（由 records 轉寫）
      residents/<policy>/trust/{logbook.ndjson, identity.pub, vacant_id}
                            ← 該臂記憶鏈（**不含 identity.key**——SPEC §7，
                              私鑰從一落盤就不進 run 目錄，比排除更強）
      ks1_a4_assertions.jsonl ← KS-1 模板 sha256＋每條教訓的 A4 洩漏防呆結果
    誠實邊界：pack 保證「完整且自洽」，內容真實性由簽章鏈承擔（RECORD_SPEC §4）。
    """
    from . import crypto, record as record_mod
    from .memory import lesson_leaks_test_data

    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1) model_io.jsonl：trace 逐字搬入（已含 prompt_sha＋answer；全 I/O 的本體）
    if trace_path is not None and Path(trace_path).exists():
        (run_dir / "model_io.jsonl").write_bytes(Path(trace_path).read_bytes())

    # 2) ledger_events.jsonl：逐題事件（infra_void 如實保留——排除率要算得出）
    with (run_dir / "ledger_events.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps({
                "type": "X1_TRIAL", "ts_ms": r.get("ts_ms", 0), "policy": policy,
                "task": r["task"], "family": r["family"], "outcome": r["outcome"],
                "passed": r["passed"], "usage": r.get("usage"),
                "gen_wall_ms": r.get("gen_wall_ms"),
            }, ensure_ascii=False) + "\n")

    # 3) 居民鏈落盤（公鑰材料即可離線驗鏈；私鑰永不寫進 run 目錄）
    trust_dir = run_dir / "residents" / policy / "trust"
    trust_dir.mkdir(parents=True, exist_ok=True)
    stream.logbook.save(trust_dir / "logbook.ndjson")
    (trust_dir / "identity.pub").write_text(
        crypto.pub_to_hex(stream.identity.pub), encoding="utf-8")
    (trust_dir / "vacant_id").write_text(stream.identity.vacant_id, encoding="utf-8")

    # 4) KS-1／A4 斷言落盤（17 §P1-3：開跑即查、抽查落盤——這裡全量查）
    task_by_id = {t.task_id: t for t in tasks}
    with (run_dir / "ks1_a4_assertions.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps({
            "check": "ks1_template_sha256", "sha256": template_sha256(),
            "clean": bool(assert_ks1_clean(PROMPT_TEMPLATE)),
        }, ensure_ascii=False) + "\n")
        for r in records:
            lesson = r.get("lesson")
            if not lesson:
                continue
            t = task_by_id.get(r["task"])
            leaks = lesson_leaks_test_data(lesson, t.check) if t is not None else None
            f.write(json.dumps({
                "check": "a4_lesson", "task_id": r["task"],
                "lesson_sha256": hashlib.sha256(lesson.encode()).hexdigest(),
                "leaks_test_data": leaks,
            }, ensure_ascii=False) + "\n")

    # 5) pack＋check（紀錄紅線的可執行判準）
    record_mod.pack(run_dir, extra_meta)
    return record_mod.check(run_dir)
