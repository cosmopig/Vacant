"""X1×EvalPlus 整合（G1 後段／lab P0-evalplus-x1-integration 同規）：

  1. GT canary 隔離：canary 只活在 hidden_check（verifier 側），逐路徑負向
     掃描 prompt／trace／ledger／episode／記憶注入——GT 不得洩到模型側。
  2. require_usage：缺端點 usage 的 trial 判 infra_void（測量層紀律）。
  3. finalize_run_package：產出 RECORD_SPEC 合格包（check PASS、無私鑰）。
  4. pilot_report：oracle-lesson 一票否決判準的算術（手算對照）。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from vacant.batch import RunLedger
from vacant.codebench import EvalPlusMBPPLoader
from vacant.identity import Identity
from vacant.logbook import Logbook
from vacant.memory import MemoryManager, MemoryStream
from vacant.x1 import (
    finalize_run_package,
    load_x1_tasks,
    pilot_report,
    run_x1,
)

GT_CANARY = "CANARY_GT_9f3c7e"
NUM_CANARY = "4242424242"

_REC_OK = {
    "task_id": "Mbpp/C1",
    "prompt": "Write a function add(a, b) that returns their sum.",
    "entry_point": "add",
    "canonical_solution": f"def add(a, b):\n    # {GT_CANARY}\n    return a + b",
    "base_input": [[1, 2]],
    "plus_input": [[3, 4], [4242424242, 1]],
    "atol": None, "contract": "", "assertion": "",
}
_REC_HARD = {
    "task_id": "Mbpp/C2",
    "prompt": "Write a function dbl(a) that returns a*2.",
    "entry_point": "dbl",
    "canonical_solution": f"def dbl(a):\n    # {GT_CANARY}\n    return a * 2",
    "base_input": [[2]],
    "plus_input": [[4242424242]],
    "atol": None, "contract": "", "assertion": "",
}


def _loader(tmp_path: Path) -> EvalPlusMBPPLoader:
    p = tmp_path / "fixture.jsonl"
    body = "".join(json.dumps(r) + "\n" for r in (_REC_OK, _REC_HARD)).encode()
    p.write_bytes(body)
    return EvalPlusMBPPLoader(
        str(p), expected_sha256=hashlib.sha256(body).hexdigest(), expected_count=2)


class _ScriptedBrain:
    """照腳本回答的 stub 腦；記錄每個 prompt；可選附 usage。"""

    name = "stub:scripted"

    def __init__(self, answers: list[str], *, usage: dict | None = None):
        self._answers = answers
        self.prompts: list[str] = []
        self.last_usage = usage

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._answers[(len(self.prompts) - 1) % len(self._answers)]


_GOOD = ["def add(a, b):\n    return b + a", "def dbl(a):\n    return a + a"]
_BAD = ["def add(a, b):\n    return a - b", "def dbl(a):\n    return a + 1"]


def _stream() -> MemoryStream:
    return MemoryStream(Logbook(), Identity.generate())


def test_gt_canary_never_leaks_to_model_side(tmp_path):
    """canary 在 hidden_check 裡（sanity），但逐路徑掃描模型側一律零命中。"""
    tasks = load_x1_tasks(_loader(tmp_path), "s0", 2)
    # sanity：canary 確實存在於 GT（hidden_check），且不在 public prompt
    for t in tasks:
        assert GT_CANARY in t.check["code"] or NUM_CANARY in t.check["code"]
        assert GT_CANARY not in t.prompt and NUM_CANARY not in t.prompt

    brain = _ScriptedBrain(_GOOD)
    stream = _stream()
    manager = MemoryManager("M2")
    trace = tmp_path / "trace.jsonl"
    ledger = RunLedger(tmp_path / "ledger.jsonl")
    records = run_x1(
        brain, "M2", tasks, stream=stream, manager=manager,
        ledger=ledger, seed="s0",
        distill=lambda task, answer, passed: "同型任務注意運算方向與邊界輸入。",
        trace_path=trace, retry_backoff_s=0,
    )
    assert len(records) == 2

    # 逐路徑負向掃描
    for prompt in brain.prompts:
        assert GT_CANARY not in prompt and NUM_CANARY not in prompt
    trace_text = trace.read_text(encoding="utf-8")
    assert GT_CANARY not in trace_text and NUM_CANARY not in trace_text
    ledger_text = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")
    assert GT_CANARY not in ledger_text and NUM_CANARY not in ledger_text
    for entry in stream.logbook.entries:
        payload = json.dumps(entry.payload, ensure_ascii=False)
        assert GT_CANARY not in payload and NUM_CANARY not in payload
    # 記憶注入（M2 實際送進下一題 prompt 的內容）
    block = manager.inject(stream, "Write a function sub(a, b).")
    assert GT_CANARY not in block and NUM_CANARY not in block

    # verifier 仍能用同一 private case 判分（V≠GT 沒被拆掉）
    assert all(r["audit"] and r["audit"]["ran"] for r in records)
    assert all(r["passed"] for r in records)  # _GOOD 答案過 hidden


def test_require_usage_missing_becomes_infra_void(tmp_path):
    """缺 usage → infra_void（不計票、resume 重試），不是硬塞估值。"""
    tasks = load_x1_tasks(_loader(tmp_path), "s0", 2)
    brain = _ScriptedBrain(_GOOD)  # last_usage=None
    records = run_x1(brain, "M2", tasks, stream=_stream(),
                     seed="s0", require_usage=True, retry_backoff_s=0)
    assert all(r["outcome"] == "infra_void" for r in records)
    assert all(r["usage"] is None for r in records)
    assert all("usage_missing" in (r["infra_error"] or "") for r in records)


def test_require_usage_records_real_cost(tmp_path):
    """有 usage → 落盤端點實回數，trial 正常計分。"""
    tasks = load_x1_tasks(_loader(tmp_path), "s0", 2)
    usage = {"prompt_tokens": 111, "completion_tokens": 22, "total_tokens": 133}
    brain = _ScriptedBrain(_GOOD, usage=usage)
    records = run_x1(brain, "M2", tasks, stream=_stream(),
                     seed="s0", require_usage=True, retry_backoff_s=0)
    assert all(r["outcome"] == "pass" for r in records)
    assert all(r["usage"] == usage for r in records)
    assert all(r["gen_wall_ms"] >= 0 for r in records)


def test_finalize_run_package_passes_record_check(tmp_path):
    """一條臂的產物 → RECORD_SPEC 合格包：check PASS、無私鑰、斷言落盤。"""
    run_dir = tmp_path / "runs" / "x1_pilot" / "M2_s0"
    tasks = load_x1_tasks(_loader(tmp_path), "s0", 2)
    stream = _stream()
    trace = tmp_path / "trace.jsonl"
    records = run_x1(
        _ScriptedBrain(_GOOD), "M2", tasks, stream=stream,
        manager=MemoryManager("M2"), seed="s0",
        distill=lambda task, answer, passed: "同型任務注意邊界。",
        trace_path=trace, retry_backoff_s=0,
    )
    ok, problems = finalize_run_package(
        run_dir, policy="M2", stream=stream, tasks=tasks, records=records,
        trace_path=trace,
        extra_meta={"model_id": "stub:scripted", "endpoint": "in-process",
                    "no_think": False, "seeds": ["s0"], "trust_arm": "M2"},
    )
    assert ok, problems
    # 必要件
    for name in ("manifest.json", "model_io.jsonl", "ledger_events.jsonl",
                 "chain_verify.txt", "anomalies.md", "SHA256SUMS",
                 "ks1_a4_assertions.jsonl"):
        assert (run_dir / name).exists(), name
    assert "PASS" in (run_dir / "chain_verify.txt").read_text(encoding="utf-8")
    # 私鑰從未寫入 run 目錄（比排除更強）
    assert not list(run_dir.rglob("identity.key"))
    assert "identity.key" not in (run_dir / "SHA256SUMS").read_text(encoding="utf-8")
    # KS-1/A4 斷言內容
    lines = [json.loads(x) for x in
             (run_dir / "ks1_a4_assertions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert lines[0]["check"] == "ks1_template_sha256" and lines[0]["clean"] is True
    assert all(e["leaks_test_data"] is False for e in lines[1:])
    # infra_void 排除率算得出（ledger 保留全量 outcome）
    outcomes = [json.loads(x)["outcome"] for x in
                (run_dir / "ledger_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert outcomes == ["pass", "pass"]


def test_pilot_report_veto_arithmetic():
    """手算對照：b=6,c=0 → p=2/64=0.03125<.05 → 偵到遷移；b=c → 未偵到。"""
    def rec(fam, passed):
        return {"outcome": "pass" if passed else "fail", "passed": passed,
                "family": fam, "task": "t", "policy": "M2", "seed": "s0"}

    seq = [False] * 6 + [True] + [True] * 7  # 前 7 題 1 對，後 7 題全對 → b=6,c=0
    records = [rec("fam_a", x) for x in seq]
    rep = pilot_report(records)
    assert rep["pooled"]["b"] == 6 and rep["pooled"]["c"] == 0
    assert abs(rep["pooled"]["p"] - 0.03125) < 1e-9
    assert rep["transfer_detected"] is True

    even = [rec("fam_a", x) for x in [False, True, False, True, True, False, True, False]]
    rep2 = pilot_report(even)
    assert rep2["pooled"]["b"] == rep2["pooled"]["c"]
    assert rep2["transfer_detected"] is False
