"""repair — R-loop G2: 需求驅動修復控制器。

原生 pi 接收草稿與可見反例 → 修正產物 → 重驗所有必要條目 → 輸出前後差異及成本。
承重規則（2026-11-04 使用者方向）：
1. 真正 G2 必須從可讀真實交付物選樣；不向修復模型提供隱藏答案。
2. 連續兩次修復沒有消除已確認缺口，控制器停止同種重試，回傳停因及未解決項。
3. wall time/呼叫/token 由執行器實際攔截；只有提示詞不算預算實作。
4. 模型用既有 pi provider（開發 qwen、效果比較現有 gemma）。
5. 成本從原始 usage/metrics 讀；缺值 UNKNOWN，絕不填 0。
6. G2 保留原候選；FAIL→UNKNOWN 不算修好；缺項/UNKNOWN/CONFLICT 不得宣告完成。
7. 任何原有 PASS 退步都要記錄，不能用淨改善掩蓋。上游變動相關 PASS 必須失效重驗。
"""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import subprocess
import time
from typing import Any, Callable

from ..intake.verifiers import ClaimResult
from .checks import run_requirement_checks
from .requirements import RequirementSet


def parse_pi_metrics(stdout_text: str) -> dict[str, Any]:
    """從 pi --mode json 輸出中解析模型呼叫與 token 成本。

    若未記錄 usage，相關 token 填 UNKNOWN，絕不填 0。
    """
    calls = 0
    input_tokens = 0
    output_tokens = 0
    reasoning_tokens = 0
    has_usage = False
    stop_reason: str | None = None

    for line in stdout_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue

        if ev.get("type") == "message_end":
            msg = ev.get("message", {})
            if msg.get("role") == "assistant":
                calls += 1
                usage = msg.get("usage")
                if isinstance(usage, dict):
                    has_usage = True
                    input_tokens += usage.get("input", 0)
                    output_tokens += usage.get("output", 0)
                    reasoning_tokens += usage.get("reasoning", 0)
                if msg.get("stopReason"):
                    stop_reason = msg.get("stopReason")

    if not has_usage:
        return {
            "model_calls": calls if calls > 0 else "UNKNOWN",
            "input_tokens": "UNKNOWN",
            "output_tokens": "UNKNOWN",
            "reasoning_tokens": "UNKNOWN",
            "stop_reason": stop_reason or "UNKNOWN",
        }

    return {
        "model_calls": calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "stop_reason": stop_reason or "stop",
    }


def generate_repair_prompt(
    task_prompt: str,
    failing_claims: list[ClaimResult],
    feedback_mode: str,
) -> str:
    """根據 feedback_mode (generic / localized) 生成修復提示詞。"""
    if feedback_mode == "generic":
        return (
            f"{task_prompt}\n\n"
            "【自動檢查回饋】\n"
            "目前工作區內的交付產物在初步自動檢查中未通過。\n"
            "請重新檢查工作區內產生的產物與原始任務的所有格式及約束要求，進行相應修正。"
        )

    # localized: 具體反例與可見證據
    shortfalls: list[str] = []
    for c in failing_claims:
        ev_str = f"（可見反例/證據: {json.dumps(c.evidence, ensure_ascii=False)}）" if c.evidence else ""
        shortfalls.append(f"- 條目 [{c.claim_id}]: {c.detail} {ev_str}")

    shortfalls_text = "\n".join(shortfalls)
    return (
        f"{task_prompt}\n\n"
        "【自動檢查具體反例回饋】\n"
        "目前交付產物經程式重算檢查發現以下具體缺口，請針對這些缺口進行精確修正，"
        "並務必保持其餘已正確部分不退步：\n"
        f"{shortfalls_text}\n"
    )


def execute_repair_turn(
    workspace_dir: pathlib.Path,
    prompt: str,
    *,
    provider: str = "lms1003qwen",
    model: str = "qwen/qwen3.8-27b",
    timeout_s: float = 180.0,
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """呼叫原生 pi 執行一輪修復，真實攔截 wall time 與 token。"""
    ws = workspace_dir.resolve()
    env = {
        **os.environ,
        "PWD": str(ws),
        "PI_SKIP_VERSION_CHECK": "1",
        **(extra_env or {}),
    }

    argv = ["pi", "--provider", provider, "--model", model, "-p", "--mode", "json", prompt]

    t0 = time.time()
    timed_out = False
    stdout_data = ""
    stderr_data = ""
    rc = -1

    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(ws),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout_data, stderr_data = proc.communicate(timeout=timeout_s)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, 9)
            except (ProcessLookupError, PermissionError):
                pass
            stdout_data, stderr_data = proc.communicate()
            rc = proc.returncode or 124
    except Exception as e:
        return {
            "rc": -1,
            "timed_out": False,
            "wall_ms": int((time.time() - t0) * 1000),
            "metrics": {
                "model_calls": "UNKNOWN",
                "input_tokens": "UNKNOWN",
                "output_tokens": "UNKNOWN",
                "reasoning_tokens": "UNKNOWN",
                "stop_reason": f"error:{type(e).__name__}",
            },
            "error": str(e),
            "stdout": stdout_data,
            "stderr": stderr_data,
        }

    wall_ms = int((time.time() - t0) * 1000)
    metrics = parse_pi_metrics(stdout_data)

    return {
        "rc": rc,
        "timed_out": timed_out,
        "wall_ms": wall_ms,
        "metrics": metrics,
        "error": None,
        "stdout": stdout_data,
        "stderr": stderr_data,
    }


def run_repair_loop(
    task_dir: str | pathlib.Path,
    req_set: RequirementSet,
    workspace_dir: str | pathlib.Path,
    task_prompt: str,
    *,
    feedback_mode: str = "localized",
    provider: str = "lms1003qwen",
    model: str = "qwen/qwen3.8-27b",
    max_attempts: int = 2,
    timeout_s: float = 180.0,
    deliverable_dir: str | pathlib.Path | None = None,
    turn_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """R-loop G2 修復控制器核心。

    - 原生 pi 接收草稿與可見反例
    - 修正產物
    - 重驗所有必要條目
    - 輸出前後差異及成本
    - 連續兩次修復未消除缺口則停止
    """
    t_dir = pathlib.Path(task_dir)
    ws_dir = pathlib.Path(workspace_dir)
    d_dir = pathlib.Path(deliverable_dir) if deliverable_dir else ws_dir

    if feedback_mode not in ("generic", "localized"):
        raise ValueError(f"feedback_mode must be 'generic' or 'localized', got {feedback_mode!r}")

    execute_turn = turn_fn or execute_repair_turn

    # 1. 初始重算檢驗（草稿狀態）
    initial_results = run_requirement_checks(t_dir, req_set, d_dir)
    initial_claims_map = {c.claim_id: c.status for c in initial_results}
    initial_failing = [c for c in initial_results if c.required and c.status != "PASS"]

    # 若初始已經全過，無需修復，立即放行
    if not initial_failing:
        return {
            "task_id": req_set.task_id or t_dir.name,
            "feedback_mode": feedback_mode,
            "provider": provider,
            "model": model,
            "initial_claims": initial_claims_map,
            "final_claims": initial_claims_map,
            "fixed_claims": [],
            "regressed_claims": [],
            "unresolved_claims": [],
            "completed": True,
            "stop_reason": "already_passed",
            "attempts": [],
            "total_cost": {
                "model_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "reasoning_tokens": 0,
                "wall_ms": 0,
            },
        }

    # 2. 開始修復迭代
    attempt = 0
    history: list[dict[str, Any]] = []
    consecutive_no_progress = 0
    current_failing = initial_failing
    previous_failing_ids = set(c.claim_id for c in initial_failing)
    current_results = initial_results
    stop_reason = ""
    completed = False

    tot_calls = 0
    tot_in_tok = 0
    tot_out_tok = 0
    tot_reason_tok = 0
    tot_wall_ms = 0
    token_metrics_valid = True

    while attempt < max_attempts:
        attempt += 1

        prompt = generate_repair_prompt(task_prompt, current_failing, feedback_mode)
        turn_res = execute_turn(
            ws_dir,
            prompt,
            provider=provider,
            model=model,
            timeout_s=timeout_s,
        )

        metrics = turn_res.get("metrics", {})
        wall_ms = turn_res.get("wall_ms", 0)
        tot_wall_ms += wall_ms

        if isinstance(metrics.get("model_calls"), int):
            tot_calls += metrics["model_calls"]
        else:
            tot_calls = "UNKNOWN"

        if isinstance(metrics.get("input_tokens"), int) and token_metrics_valid:
            tot_in_tok += metrics["input_tokens"]
            tot_out_tok += metrics.get("output_tokens", 0)
            tot_reason_tok += metrics.get("reasoning_tokens", 0)
        else:
            token_metrics_valid = False

        # 產物修改後，所有必要條目必須重新重算驗證
        current_results = run_requirement_checks(t_dir, req_set, d_dir)
        current_claims_map = {c.claim_id: c.status for c in current_results}
        unresolved = [c for c in current_results if c.required and c.status != "PASS"]
        current_failing_ids = set(c.claim_id for c in unresolved)

        # 評估本輪進展
        eliminated_this_attempt = previous_failing_ids - current_failing_ids
        if not eliminated_this_attempt:
            consecutive_no_progress += 1
        else:
            consecutive_no_progress = 0

        # 計算對比初態的整體轉移
        fixed_ids = [
            c.claim_id for c in current_results
            if c.required and c.status == "PASS" and initial_claims_map.get(c.claim_id) != "PASS"
        ]
        regressed_ids = [
            c.claim_id for c in current_results
            if c.required and c.status != "PASS" and initial_claims_map.get(c.claim_id) == "PASS"
        ]

        attempt_record = {
            "attempt": attempt,
            "wall_ms": wall_ms,
            "metrics": metrics,
            "current_claims": current_claims_map,
            "fixed_this_attempt": list(eliminated_this_attempt),
            "unresolved_count": len(unresolved),
        }
        history.append(attempt_record)

        # 檢查是否全部完成（無缺口、無退步）
        if not unresolved and not regressed_ids:
            completed = True
            stop_reason = "completed"
            break

        # 連續兩次修復未消除任何已確認缺口：控制器停止重試
        if consecutive_no_progress >= 2:
            stop_reason = "consecutive_no_progress"
            completed = False
            break

        previous_failing_ids = current_failing_ids
        current_failing = unresolved

    if not stop_reason:
        stop_reason = "max_attempts_reached"
        completed = False

    # 最終彙整
    final_fixed = [
        c.claim_id for c in current_results
        if c.required and c.status == "PASS" and initial_claims_map.get(c.claim_id) != "PASS"
    ]
    final_regressed = [
        c.claim_id for c in current_results
        if c.required and c.status != "PASS" and initial_claims_map.get(c.claim_id) == "PASS"
    ]
    final_unresolved = [c.claim_id for c in current_results if c.required and c.status != "PASS"]

    total_cost = {
        "model_calls": tot_calls,
        "input_tokens": tot_in_tok if token_metrics_valid else "UNKNOWN",
        "output_tokens": tot_out_tok if token_metrics_valid else "UNKNOWN",
        "reasoning_tokens": tot_reason_tok if token_metrics_valid else "UNKNOWN",
        "wall_ms": tot_wall_ms,
    }

    return {
        "task_id": req_set.task_id or t_dir.name,
        "feedback_mode": feedback_mode,
        "provider": provider,
        "model": model,
        "initial_claims": initial_claims_map,
        "final_claims": {c.claim_id: c.status for c in current_results},
        "fixed_claims": final_fixed,
        "regressed_claims": final_regressed,
        "unresolved_claims": final_unresolved,
        "completed": completed,
        "stop_reason": stop_reason,
        "attempts": history,
        "total_cost": total_cost,
    }
