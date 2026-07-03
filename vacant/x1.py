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
    now_ms: Callable[[], int] = lambda: time.time_ns() // 1_000_000,
) -> list[dict[str, Any]]:
    """一條臂跑完整任務流。回傳逐題記錄（全 I/O 落盤到 trace_path）。

    X1 紀律：稽核率 100%（forced）；retry×4 後仍 infra 錯 → outcome=infra_void
    （09 §3.5）；斷點續跑靠 ledger 以 (policy, task_id, seed) 跳過已完成格。
    """
    manager = manager or MemoryManager(policy)
    auditor = auditor or Auditor(rate=1.0)
    assert_ks1_clean(PROMPT_TEMPLATE)
    records: list[dict[str, Any]] = []

    for task in tasks:
        if ledger is not None and ledger.is_done(policy, task.task_id, seed):
            records.append(ledger.result(policy, task.task_id, seed))  # type: ignore[arg-type]
            continue

        memory_block = manager.inject(stream, task.prompt)
        prompt = PROMPT_TEMPLATE.format(memory=memory_block, task=task.prompt)

        answer, infra_error = "", None
        for attempt in range(retries):
            try:
                answer = brain.generate(prompt)
                infra_error = None
                break
            except Exception as e:  # 端點瞬斷等 infra 錯：retry×4
                infra_error = f"{type(e).__name__}: {e}"
        ts = now_ms()

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
        }
        if trace_path:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            with trace_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({**rec, "prompt_sha": _digest(prompt),
                                    "answer": answer}, ensure_ascii=False) + "\n")
        if ledger is not None:
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
