"""對每個 Twin-2K-500 參與者跑六個臂。

MAJORITY 不呼叫模型。其餘五臂各一題一次請求，走同一個 budget ledger。
生成時不讀 labels.jsonl。分數在預測寫完之後才接合。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .backend import FixtureBackend
from .budget import BudgetLedger, map_usage
from .metrics import leave_one_out_majority, score_twin
from .runner import RunnerError
from .twin2k import TWIN_ARMS, TWIN_LLM_ARMS, load_participant, twin_user_prompt


class _Jsonl:
    """每筆寫完就 flush。行程中斷時已完成的列還在。"""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._fh = path.open("a", encoding="utf-8")

    def write(self, row: dict[str, Any]) -> None:
        self._fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def close(self) -> None:
        self._fh.close()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _load_calls(ledger: BudgetLedger, path: Path) -> int:
    rows = _read_jsonl(path)
    for row in rows:
        if row.get("usage") and not row.get("usage_mapped"):
            row["usage_mapped"] = map_usage(row["usage"])
        ledger.calls.append(row)
    return len(rows)


def _letter(option_id: str | None, presented_order: list[str]) -> str | None:
    if option_id == presented_order[0]:
        return "A"
    if option_id == presented_order[1]:
        return "B"
    return None


def _parse_prediction(text: str, case_id: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        fence = raw.rfind("```")
        if fence >= 0:
            raw = raw[:fence]
    try:
        obj = json.loads(raw.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    if obj.get("case_id") not in (None, case_id):
        return None
    prediction = obj.get("prediction")
    if isinstance(prediction, str):
        prediction = prediction.strip()
    if prediction not in ("A", "B", "tie", "neither", "unsure"):
        return None
    uncertainty = obj.get("uncertainty") if obj.get("uncertainty") in ("low", "medium", "high") else "medium"
    return {"prediction": prediction, "uncertainty": uncertainty}


def _key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("pid")), str(row.get("arm")), str(row.get("case_id")))


def _skip_on_resume(row: dict[str, Any]) -> bool:
    """完成的格子不重送。usage_unknown 留著對帳，不重送，避免把可能已計費的請求再算一次。"""
    return row.get("status") in ("completed", "usage_unknown")


def parse_arms(raw: str | None) -> list[str] | None:
    """None means every arm. Otherwise a canonical-order subset of TWIN_ARMS."""
    if raw is None or str(raw).strip() == "":
        return None
    requested = [part.strip().upper() for part in str(raw).split(",") if part.strip()]
    if not requested:
        raise RunnerError("--arms is empty")
    unknown = [name for name in requested if name not in TWIN_ARMS]
    if unknown:
        raise RunnerError("unknown arm(s): " + ", ".join(unknown) + "; choose from " + ", ".join(TWIN_ARMS))
    return [name for name in TWIN_ARMS if name in requested]


def execute_twin(participants: list[dict[str, Any]], backend, out_dir: Path, *, max_output_tokens: int = 200, resume: bool = False, retry_transient: bool = True, arms: list[str] | None = None) -> dict[str, Any]:
    """participants 的 labels 只在這裡拿來算 MAJORITY，不放進 prompt。

    每一筆預測與呼叫寫完就 flush。`--resume` 跳過已完成的 (pid, arm, case_id)。
    逾時與連線錯誤在 twin 跑裡最多再試一次，而且不因此停掉後面的格子。
    `--arms` 只跑列出的臂；未列出的臂既不呼叫模型，也不寫新列。
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pred_path = out / "predictions.jsonl"
    call_path = out / "calls.jsonl"
    prompt_path = out / "prompts.jsonl"
    if pred_path.exists() and not resume:
        raise RunnerError(f"{pred_path} already exists; pass --resume or use a new directory")
    labels = [label for person in participants for label in person["labels"]]
    majority = leave_one_out_majority(labels)
    prior = {_key(row): row for row in _read_jsonl(pred_path)} if resume else {}
    if arms is None:
        selected = list(TWIN_ARMS)
    else:
        unknown = [name for name in arms if name not in TWIN_ARMS]
        if unknown:
            raise RunnerError("unknown arm(s): " + ", ".join(unknown))
        selected = [name for name in TWIN_ARMS if name in arms]
        if not selected:
            raise RunnerError("no arms selected")
    llm_arms = [name for name in selected if name in TWIN_LLM_ARMS]
    include_majority = "MAJORITY" in selected
    ledger = getattr(backend, "ledger", None)
    flushed_calls = _load_calls(ledger, call_path) if resume and ledger is not None else 0
    predictions = _Jsonl(pred_path)
    prompts = _Jsonl(prompt_path)
    calls = _Jsonl(call_path) if ledger is not None else None
    kept: dict[tuple[str, str, str], dict[str, Any]] = dict(prior)
    written = 0
    stopped = False
    stop_reason = None

    def flush_calls() -> None:
        nonlocal flushed_calls
        if calls is None or ledger is None:
            return
        rows = ledger.public_rows()
        for row in rows[flushed_calls:]:
            calls.write(row)
        flushed_calls = len(rows)

    try:
        for person in participants:
            order_by = {case["case_id"]: case["presented_order"] for case in person["holdout_cases"]}
            for case in person["holdout_cases"]:
                letter = _letter(majority.get((person["pid"], case["case_id"])), case["presented_order"])
                majority_row = {
                    "pid": person["pid"],
                    "case_id": case["case_id"],
                    "arm": "MAJORITY",
                    "status": "completed",
                    "sent": False,
                    "call_id": None,
                    "prediction": letter,
                    "presented_order": case["presented_order"],
                    "backend": "majority",
                    "human_acceptance": None,
                }
                mkey = _key(majority_row)
                if include_majority and not (resume and mkey in prior and _skip_on_resume(prior[mkey])):
                    predictions.write(majority_row)
                    written += 1
                    kept[mkey] = majority_row
                for arm in llm_arms:
                    key = (person["pid"], arm, case["case_id"])
                    if resume and key in prior and _skip_on_resume(prior[key]):
                        continue
                    if ledger is not None and not stopped:
                        allowed, why = ledger.authorize(
                            purpose=f"twin|{person['pid']}|{arm}|{case['case_id']}",
                            estimated_output_tokens=max_output_tokens,
                        )
                        if not allowed:
                            stopped = True
                            stop_reason = why
                    if stopped or (ledger is not None and ledger.stopped):
                        row = {
                            "pid": person["pid"],
                            "case_id": case["case_id"],
                            "arm": arm,
                            "status": "budget_stopped",
                            "sent": False,
                            "call_id": None,
                            "prediction": None,
                            "presented_order": order_by[case["case_id"]],
                            "error": stop_reason or getattr(ledger, "stop_reason", None),
                            "human_acceptance": None,
                        }
                        predictions.write(row)
                        written += 1
                        kept[key] = row
                        stopped = True
                        continue
                    prompt = twin_user_prompt(arm, _public(person), case)
                    prompts.write({"pid": person["pid"], "arm": arm, "case_id": case["case_id"], "prompt": prompt})
                    result = backend.complete(
                        prompt,
                        purpose=f"twin|{person['pid']}|{arm}|{case['case_id']}",
                        max_output_tokens=max_output_tokens,
                        system="You answer with one JSON object. You do not use tools.",
                        retry_transient=retry_transient,
                    )
                    flush_calls()
                    row = {
                        "pid": person["pid"],
                        "case_id": case["case_id"],
                        "arm": arm,
                        "status": "budget_stopped" if not result.get("sent") else result.get("status"),
                        "sent": bool(result.get("sent")),
                        "call_id": result.get("call_id"),
                        "prediction": None,
                        "presented_order": case["presented_order"],
                        "backend": result.get("backend"),
                        "usage": result.get("usage"),
                        "error": result.get("error"),
                        "attempts": result.get("attempts"),
                        "request_extra": result.get("request_extra"),
                        "human_acceptance": None,
                    }
                    if not result.get("sent"):
                        stopped = True
                        stop_reason = result.get("error")
                        row["status"] = "budget_stopped"
                    elif result.get("status") == "completed":
                        parsed = _parse_prediction(result.get("content") or "", case["case_id"])
                        if parsed is None:
                            row["status"] = "parse_failed"
                            row["error"] = "prediction JSON was not usable"
                        else:
                            row["prediction"] = parsed["prediction"]
                            row["uncertainty"] = parsed["uncertainty"]
                    elif result.get("status") == "usage_unknown":
                        stopped = True
                        stop_reason = "usage_unknown"
                    predictions.write(row)
                    written += 1
                    kept[key] = row
    finally:
        predictions.close()
        prompts.close()
        if calls is not None:
            calls.close()
    retests = {person["pid"]: person["test_retest"] for person in participants}
    scored = score_twin(list(kept.values()), labels, retests)
    (out / "scores.json").write_text(json.dumps(scored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"rows": len(kept), "written": written, "stopped": stopped, "scores": scored}


def _public(person: dict[str, Any]) -> dict[str, Any]:
    """送給 prompt 的副本不含 labels。"""
    return {key: person[key] for key in person if key != "labels"}


def load_prepared(prepared: Path) -> list[dict[str, Any]]:
    root = Path(prepared)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    people = []
    for pid in manifest["pids"]:
        people.append(load_participant(root / "pids" / str(pid)))
    return people


def fixture_handler(prompt: str, *, purpose: str, max_output_tokens: int) -> dict[str, Any]:
    case_id = purpose.split("|", 3)[-1]
    body = json.dumps({"case_id": case_id, "prediction": "A", "uncertainty": "medium"})
    return {"content": body, "status": "completed"}


def fixture_backend(config: dict[str, Any] | None = None) -> FixtureBackend:
    limits = (config or {}).get("budget")
    # local：fixture 不推 API 美元，請求數上限仍生效。unset 會拒絕非 fixture purpose。
    return FixtureBackend(handler=fixture_handler, ledger=BudgetLedger(limits, pricing="local"))
