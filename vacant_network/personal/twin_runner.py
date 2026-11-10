"""對每個 Twin-2K-500 參與者跑六個臂。

MAJORITY 不呼叫模型。其餘五臂各一題一次請求，走同一個 budget ledger。
生成時不讀 labels.jsonl。分數在預測寫完之後才接合。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .backend import FixtureBackend
from .budget import BudgetLedger
from .metrics import leave_one_out_majority, score_twin
from .twin2k import TWIN_LLM_ARMS, load_participant, twin_user_prompt


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


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


def execute_twin(participants: list[dict[str, Any]], backend, out_dir: Path, *, max_output_tokens: int = 200) -> dict[str, Any]:
    """participants 的 labels 只在這裡拿來算 MAJORITY，不放進 prompt。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    labels = [label for person in participants for label in person["labels"]]
    majority = leave_one_out_majority(labels)
    rows: list[dict[str, Any]] = []
    prompts: list[dict[str, str]] = []
    stopped = False
    stop_reason = None
    for person in participants:
        order_by = {case["case_id"]: case["presented_order"] for case in person["holdout_cases"]}
        for case in person["holdout_cases"]:
            letter = _letter(majority.get((person["pid"], case["case_id"])), case["presented_order"])
            rows.append({
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
            })
            for arm in TWIN_LLM_ARMS:
                ledger = getattr(backend, "ledger", None)
                if ledger is not None and not stopped:
                    allowed, why = ledger.authorize(purpose=f"twin|{person['pid']}|{arm}|{case['case_id']}", estimated_output_tokens=max_output_tokens)
                    if not allowed:
                        stopped = True
                        stop_reason = why
                if stopped or (ledger is not None and ledger.stopped):
                    rows.append({
                        "pid": person["pid"],
                        "case_id": case["case_id"],
                        "arm": arm,
                        "status": "budget_stopped",
                        "sent": False,
                        "call_id": None,
                        "prediction": None,
                        "presented_order": order_by[case["case_id"]],
                        "error": stop_reason or getattr(getattr(backend, "ledger", None), "stop_reason", None),
                        "human_acceptance": None,
                    })
                    stopped = True
                    continue
                prompt = twin_user_prompt(arm, _public(person), case)
                prompts.append({"pid": person["pid"], "arm": arm, "case_id": case["case_id"], "prompt": prompt})
                result = backend.complete(
                    prompt,
                    purpose=f"twin|{person['pid']}|{arm}|{case['case_id']}",
                    max_output_tokens=max_output_tokens,
                    system="You answer with one JSON object. You do not use tools.",
                )
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
                elif result.get("status") in ("usage_unknown", "timeout", "model_failed"):
                    stopped = True
                    stop_reason = result.get("status")
                rows.append(row)
    _jsonl(out / "predictions.jsonl", rows)
    _jsonl(out / "prompts.jsonl", prompts)
    if getattr(backend, "ledger", None) is not None:
        _jsonl(out / "calls.jsonl", backend.ledger.public_rows())
    retests = {person["pid"]: person["test_retest"] for person in participants}
    scored = score_twin(rows, labels, retests)
    (out / "scores.json").write_text(json.dumps(scored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"rows": len(rows), "prompts": len(prompts), "stopped": stopped, "scores": scored}


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
