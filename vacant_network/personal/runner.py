"""試驗格子、凍結與盲包。

這支在架構裡承重什麼：Stage 1 是 24 題 × 3 種表示。Stage 2 的
screen 批是 T01–T06：12 次首稿（A/C、B/D 各共用一次）加 24 次第二輪，
共 36 個送出的請求、48 列。失敗列留在分母裡。

resume 不重送已經送出但狀態不明的請求。盲包不寫 arm、profile、
模型自評或檢查分數。human_acceptance 在這裡永遠是 null。
"""

from __future__ import annotations

import hashlib
import json
import random
import subprocess
from pathlib import Path
from typing import Any

from . import profiles as profiles_mod
from .context import (
    check_lines_from_decision,
    draft_prompt,
    prediction_prompt,
    revision_prompt,
)
from .dataset import (
    DataError,
    join_answers,
    load_answers,
    load_bank,
    structural_memo,
    structural_plan,
    task_by_id,
)
from .intake_bridge import build_control, check_artifacts, write_artifacts
from .metrics import objective_pass, stage2_metrics
from .prompts import TEMPLATES
from . import BASE_COMMIT
from .schemas import (
    ARM_REPRESENTATION,
    ARMS,
    GATE_ON_ARMS,
    REPRESENTATIONS,
    parse_envelope,
    validate_prediction,
    validate_run_row,
)

SCREEN_TASKS = ("T01", "T02", "T03", "T04", "T05", "T06")


class RunnerError(RuntimeError):
    pass


class ResumeError(RunnerError):
    pass


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head(start: Path | None = None) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=start or Path.cwd(),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def load_config(path: Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RunnerError("config must be a JSON object")
    if "api_key" in raw or "api_key" in (raw.get("model") or {}):
        raise RunnerError("API keys do not belong in the config file")
    root = config_path.parent

    def resolve(value: str | None) -> str | None:
        if value is None:
            return None
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = root / candidate
        return str(candidate.resolve())

    raw["_config_path"] = str(config_path)
    raw["bank_dir"] = resolve(raw.get("bank_dir"))
    raw["prompt_dir"] = resolve(raw.get("prompt_dir"))
    raw["checker"] = resolve(raw.get("checker"))
    private = raw.get("private_pilot_root")
    raw["private_pilot_root"] = resolve(private) if isinstance(private, str) else None
    return raw


def load_banks(config: dict[str, Any]) -> dict[str, Any]:
    bank_dir = Path(config["bank_dir"])
    return {
        "calibration": load_bank(bank_dir / "calibration.json", kind="calibration"),
        "holdout": load_bank(bank_dir / "holdout.json", kind="holdout"),
        "tasks": load_bank(bank_dir / "tasks.json", kind="tasks"),
    }


def _dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def blank_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "run_id": None,
        "task_id": None,
        "arm": None,
        "pass_index": None,
        "status": "planned",
        "call_id": None,
        "shared_first_draft_group": None,
        "model_id": None,
        "base_commit": BASE_COMMIT,
        "profile_hash": None,
        "prompt_hash": None,
        "artifact_hashes": {},
        "contract_status": None,
        "check_results": [],
        "usage": None,
        "cost_usd": None,
        "wall_ms": None,
        "human_acceptance": None,
        "error": None,
    }
    row.update(overrides)
    problems = validate_run_row(row)
    if problems:
        raise RunnerError("; ".join(problems))
    return row


def plan_screen(tasks: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    ordered = list(tasks)
    rng.shuffle(ordered)
    steps = []
    for task in ordered:
        reps = ["SUMMARY", "STRUCTURED"]
        rng.shuffle(reps)
        for rep in reps:
            arms = ["A", "C"] if rep == "SUMMARY" else ["B", "D"]
            steps.append({"phase": "draft", "task_id": task["task_id"], "representation": rep, "arms": arms})
        arms = list(ARMS)
        rng.shuffle(arms)
        for arm in arms:
            steps.append({"phase": "revise", "task_id": task["task_id"], "arm": arm, "representation": ARM_REPRESENTATION[arm]})
    return steps


def _profile_hash(profiles: dict[str, Any], representation: str) -> str:
    return sha256_text(json.dumps(profiles[representation], ensure_ascii=False, sort_keys=True))


def _apply_call(row: dict[str, Any], result: dict[str, Any], prompt: dict[str, Any]) -> None:
    row["call_id"] = result.get("call_id")
    row["prompt_hash"] = prompt["prompt_hash"]
    row["usage"] = result.get("usage")
    row["cost_usd"] = result.get("cost_usd")
    row["wall_ms"] = result.get("wall_ms")
    row["backend"] = result.get("backend")
    row["status"] = result.get("status") or "model_failed"
    row["error"] = result.get("error")


def _check_row(row: dict[str, Any], control: Path, artifact: Path) -> dict[str, Any]:
    checked = check_artifacts(control, artifact)
    row["contract_status"] = checked["outcome"]
    row["check_results"] = [
        {"claim_id": item["claim_id"], "status": item["status"], "detail": item["detail"]}
        for item in checked["decision"].get("results") or []
    ]
    row["artifact_hashes"] = {key: value for key, value in checked["candidate_hashes"].items()}
    row["report_integrity"] = "ok" if checked["integrity"].get("ok") else "report_integrity_unknown"
    if not checked["integrity"].get("ok"):
        row["status"] = "report_integrity_unknown"
        row["error"] = checked["integrity"].get("reason")
    row["objective_pass"] = objective_pass(row)
    row["human_acceptance"] = None
    return checked


def execute_screen(config: dict[str, Any], backend, out_dir: Path, profiles: dict[str, Any], *, fixture_plumbing: bool = False, resume: bool = True) -> dict[str, Any]:
    banks = load_banks(config)
    tasks = [task for task in banks["tasks"]["tasks"] if task["task_id"] in SCREEN_TASKS]
    if len(tasks) != 6:
        raise RunnerError("screen batch must be T01–T06")
    allowed = {case["case_id"] for case in banks["calibration"]["cases"]}
    for profile in profiles.values():
        profiles_mod.assert_calibration_sources(profile, allowed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    steps = plan_screen(tasks, int(config.get("seed") or 0))
    _dump(out / "screen_plan.json", {"seed": config.get("seed"), "steps": steps, "fixture_plumbing": fixture_plumbing})
    by_id = task_by_id(banks["tasks"])
    controls = {}
    for task in tasks:
        controls[task["task_id"]] = build_control(
            out / "controls" / task["task_id"],
            task,
            checker_source=Path(config["checker"]) if config.get("checker") else None,
        )
    prior = {(row["task_id"], row["arm"], row["pass_index"]): row for row in _read_jsonl(out / "arm_pass_rows.jsonl")} if resume else {}
    if any(row.get("status") == "in_flight" or (row.get("call_id") and row.get("status") == "usage_unknown") for row in prior.values()):
        raise ResumeError("a sent call is usage_unknown or still in flight; reconcile it before resuming, do not resend")
    rows: list[dict[str, Any]] = []
    drafts: dict[tuple[str, str], dict[str, Any]] = {}
    stopped = False
    stop_reason = None
    model_id = (config.get("model") or {}).get("model_id") if getattr(backend, "name", "") == "single_call" else None
    for step in steps:
        task = by_id[step["task_id"]]
        if step["phase"] == "draft":
            targets = []
            for arm in step["arms"]:
                key = (task["task_id"], arm, 1)
                if key in prior and prior[key].get("status") not in ("planned", None):
                    rows.append(prior[key])
                    targets.append(prior[key])
            if len(targets) == len(step["arms"]):
                drafts[(task["task_id"], step["representation"])] = {"rows": targets, "text": _draft_text(out, task["task_id"], step["representation"])}
                continue
            def make_row(arm: str) -> dict[str, Any]:
                return blank_row(
                    run_id=config.get("run_id"),
                    task_id=task["task_id"],
                    arm=arm,
                    pass_index=1,
                    model_id=model_id,
                    profile_hash=_profile_hash(profiles, step["representation"]),
                    shared_first_draft_group=f"{task['task_id']}:{step['representation']}",
                    representation=step["representation"],
                    fixture_plumbing=fixture_plumbing,
                )
            if stopped:
                for arm in step["arms"]:
                    skipped = make_row(arm)
                    skipped["status"] = "budget_stopped"
                    skipped["error"] = stop_reason
                    skipped["call_id"] = None
                    rows.append(skipped)
                continue
            prompt = draft_prompt(task, profiles, step["representation"], allowed_ids=allowed)
            result = backend.complete(
                prompt["user"], purpose=f"draft:{task['task_id']}:{step['representation']}",
                max_output_tokens=int((config.get("budget") or {}).get("stage2_output_tokens") or 1800),
                system=prompt["system"],
            )
            if not result.get("sent"):
                stopped = True
                stop_reason = result.get("error")
            envelope, error = (None, result.get("error"))
            if result.get("sent") and result.get("status") == "completed":
                envelope, error = parse_envelope(result.get("content") or "")
            artifact = out / "artifacts" / task["task_id"] / step["representation"] / "pass1"
            checked = None
            if envelope:
                write_artifacts(artifact, envelope["memo_markdown"], envelope["plan"])
                checked = _check_row(make_row(step["arms"][0]), Path(controls[task["task_id"]]["control_dir"]), artifact)
                if checked.get("stop"):
                    stopped = True
                    stop_reason = "report_integrity_unknown"
            produced = []
            for arm in step["arms"]:
                row = make_row(arm)
                _apply_call(row, result, prompt)
                if result.get("sent") and result.get("status") == "completed" and envelope is None:
                    row["status"] = "parse_failed"
                    row["error"] = error
                elif checked is not None:
                    _copy_check(row, checked)
                    if row.get("report_integrity") == "report_integrity_unknown":
                        row["status"] = "report_integrity_unknown"
                    row["objective_pass"] = objective_pass(row)
                row["human_acceptance"] = None
                produced.append(row)
                rows.append(row)
            drafts[(task["task_id"], step["representation"])] = {
                "text": result.get("content") or "",
                "checked": checked,
                "artifact": artifact,
                "rows": produced,
            }
            continue
        key = (task["task_id"], step["arm"], 2)
        if key in prior and prior[key].get("status") not in ("planned", None):
            rows.append(prior[key])
            continue
        rep = step["representation"]
        draft_info = drafts.get((task["task_id"], rep), {})
        feedback = None
        if step["arm"] in GATE_ON_ARMS and draft_info.get("checked"):
            feedback = check_lines_from_decision(draft_info["checked"]["decision"], draft_info["checked"]["integrity"].get("report"))
        prompt = revision_prompt(
            task, profiles, rep, draft_info.get("text") or "",
            arm=step["arm"], check_lines=feedback, allowed_ids=allowed,
        )
        row = blank_row(
            run_id=config.get("run_id"),
            task_id=task["task_id"],
            arm=step["arm"],
            pass_index=2,
            model_id=model_id,
            profile_hash=_profile_hash(profiles, rep),
            representation=rep,
            fixture_plumbing=fixture_plumbing,
        )
        if stopped or (hasattr(backend, "ledger") and getattr(backend.ledger, "stopped", False)):
            row["status"] = "budget_stopped"
            row["error"] = stop_reason or getattr(backend.ledger, "stop_reason", None)
            rows.append(row)
            stopped = True
            continue
        result = backend.complete(
            prompt["user"], purpose=f"revise:{task['task_id']}:{step['arm']}",
            max_output_tokens=int((config.get("budget") or {}).get("stage2_output_tokens") or 1800),
            system=prompt["system"],
        )
        _apply_call(row, result, prompt)
        if not result.get("sent"):
            stopped = True
            stop_reason = result.get("error")
            row["status"] = "budget_stopped"
            rows.append(row)
            continue
        if result.get("status") != "completed":
            if result.get("status") in ("usage_unknown", "timeout", "model_failed"):
                stopped = True
                stop_reason = result.get("status")
            rows.append(row)
            continue
        envelope, error = parse_envelope(result.get("content") or "")
        if envelope is None:
            row["status"] = "parse_failed"
            row["error"] = error
            rows.append(row)
            continue
        artifact = out / "artifacts" / task["task_id"] / step["arm"] / "pass2"
        write_artifacts(artifact, envelope["memo_markdown"], envelope["plan"])
        checked = _check_row(row, Path(controls[task["task_id"]]["control_dir"]), artifact)
        if checked.get("stop"):
            stopped = True
            stop_reason = "report_integrity_unknown"
        rows.append(row)
    for row in rows:
        row["human_acceptance"] = None
        problems = validate_run_row(row)
        if problems:
            raise RunnerError("; ".join(problems))
    _jsonl(out / "arm_pass_rows.jsonl", rows)
    calls = []
    if getattr(backend, "ledger", None) is not None:
        calls = backend.ledger.public_rows()
        _jsonl(out / "calls.jsonl", calls)
    return {
        "rows": len(rows),
        "calls": len([call for call in calls if call.get("sent")]),
        "stopped": stopped,
        "stop_reason": stop_reason,
        "metrics": stage2_metrics(rows, [], calls),
        "fixture_plumbing": fixture_plumbing,
        "human_acceptance": None,
    }


def _draft_text(out: Path, task_id: str, representation: str) -> str:
    plan = out / "artifacts" / task_id / representation / "pass1" / "plan.json"
    memo = out / "artifacts" / task_id / representation / "pass1" / "memo.md"
    if not plan.is_file():
        return ""
    return json.dumps({"memo_markdown": memo.read_text(encoding="utf-8"), "plan": json.loads(plan.read_text(encoding="utf-8"))}, ensure_ascii=False)


def _copy_check(row: dict[str, Any], source: dict[str, Any]) -> None:
    if "decision" in source:
        row["contract_status"] = source["outcome"]
        row["check_results"] = [
            {"claim_id": item["claim_id"], "status": item["status"], "detail": item["detail"]}
            for item in source["decision"].get("results") or []
        ]
        row["artifact_hashes"] = dict(source.get("candidate_hashes") or {})
        row["report_integrity"] = "ok" if source["integrity"].get("ok") else "report_integrity_unknown"
        row["objective_pass"] = objective_pass(row)
        return
    for key in ("contract_status", "check_results", "artifact_hashes", "report_integrity", "objective_pass"):
        if key in source:
            row[key] = source[key]


def structural_handler(tasks: dict[str, dict[str, Any]]):
    """管線見證。同一個任務永遠回同一份合法子集，方便測共用首稿與相同 hash。"""

    def handler(prompt: str, *, purpose: str, max_output_tokens: int) -> dict[str, Any]:
        task_id = purpose.split(":")[1]
        task = tasks[task_id]
        plan = structural_plan(task)
        content = json.dumps({
            "memo_markdown": structural_memo(task, plan),
            "plan": plan,
        }, ensure_ascii=False)
        return {"content": content, "status": "completed"}

    return handler


def prediction_plan(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"case_id": case["case_id"], "representation": rep, "status": "planned"}
        for case in cases
        for rep in REPRESENTATIONS
    ]


def execute_predictions(config: dict[str, Any], backend, out_dir: Path, profiles: dict[str, Any], *, resume: bool = True) -> dict[str, Any]:
    banks = load_banks(config)
    allowed = {case["case_id"] for case in banks["calibration"]["cases"]}
    for profile in profiles.values():
        profiles_mod.assert_calibration_sources(profile, allowed)
    pool = join_answers(
        {case["case_id"]: case for case in banks["calibration"]["cases"]},
        load_answers(Path(config["answers"])),
    )
    out = Path(out_dir)
    prior = {(row["case_id"], row["representation"]): row for row in _read_jsonl(out / "predictions.jsonl")} if resume else {}
    if any(row.get("status") in ("in_flight", "usage_unknown") and row.get("sent") for row in prior.values()):
        raise ResumeError("reconcile unknown prediction calls before resuming")
    rows = []
    stopped = False
    for case in banks["holdout"]["cases"]:
        for rep in REPRESENTATIONS:
            key = (case["case_id"], rep)
            if key in prior and prior[key].get("status") not in ("planned",):
                rows.append(prior[key])
                continue
            if stopped or (hasattr(backend, "ledger") and getattr(backend.ledger, "stopped", False)):
                rows.append({"case_id": case["case_id"], "representation": rep, "status": "budget_stopped", "prediction": None, "sent": False})
                stopped = True
                continue
            prompt = prediction_prompt(case, profiles, pool, rep, allowed_ids=allowed)
            result = backend.complete(
                prompt["user"], purpose=f"predict:{case['case_id']}:{rep}",
                max_output_tokens=int((config.get("budget") or {}).get("stage1_output_tokens") or 200),
                system=prompt["system"],
            )
            row = {
                "case_id": case["case_id"],
                "representation": rep,
                "status": "budget_stopped" if not result.get("sent") else result.get("status"),
                "sent": bool(result.get("sent")),
                "call_id": result.get("call_id"),
                "prediction": None,
                "prompt_hash": prompt["prompt_hash"],
                "error": result.get("error"),
                "usage": result.get("usage"),
            }
            if not result.get("sent"):
                stopped = True
            elif result.get("status") == "completed":
                try:
                    parsed = json.loads(result.get("content") or "")
                except json.JSONDecodeError as exc:
                    row["status"] = "parse_failed"
                    row["error"] = str(exc)
                else:
                    problems = validate_prediction(parsed)
                    if problems:
                        row["status"] = "parse_failed"
                        row["error"] = "; ".join(problems)
                    else:
                        row.update(parsed)
            elif result.get("status") in ("usage_unknown", "timeout", "model_failed"):
                stopped = True
            rows.append(row)
    _jsonl(out / "predictions.jsonl", rows)
    return {"cells": len(rows), "planned": 72, "stopped": stopped}


def freeze_manifest(config: dict[str, Any], out_path: Path, *, profiles_dir: Path, answers_path: Path) -> dict[str, Any]:
    """不呼叫模型。缺答案或 profile 就拒絕寫一份看起來完整的 freeze。"""
    if not Path(answers_path).is_file():
        raise RunnerError("calibration answers are missing; refusing to freeze a protocol with no source answers")
    banks = load_banks(config)
    answers = load_answers(Path(answers_path))
    joined = join_answers({case["case_id"]: case for case in banks["calibration"]["cases"]}, answers)
    allowed = {case["case_id"] for case in joined}
    profiles = {}
    for name, filename in (("RAW", "raw.json"), ("SUMMARY", "summary.json"), ("STRUCTURED", "structured.json")):
        path = Path(profiles_dir) / filename
        if not path.is_file():
            raise RunnerError(f"missing {name} profile at {path}")
        profiles[name] = json.loads(path.read_text(encoding="utf-8"))
        profiles_mod.assert_calibration_sources(profiles[name], allowed)
    from .intake_bridge import build_control
    import tempfile
    contracts = {}
    with tempfile.TemporaryDirectory() as tmp:
        for task in banks["tasks"]["tasks"]:
            built = build_control(Path(tmp) / task["task_id"], task, checker_source=Path(config["checker"]) if config.get("checker") else None)
            contracts[task["task_id"]] = built["contract_sha256"]
    manifest = {
        "schema_version": "vacant.personal.freeze.v1",
        "base_commit": BASE_COMMIT,
        "runner_commit": git_head(),
        "bank_sha256": {name: sha256_file(Path(config["bank_dir"]) / f"{name}.json") for name in ("calibration", "holdout", "tasks")},
        "answers_sha256": sha256_file(Path(answers_path)),
        "profile_sha256": {name: sha256_text(json.dumps(profile, ensure_ascii=False, sort_keys=True)) for name, profile in profiles.items()},
        "prompt_sha256": {name: sha256_text(text) for name, text in TEMPLATES.items()},
        "retrieval_method": profiles_mod.RETRIEVAL_METHOD,
        "contract_sha256": contracts,
        "model": {
            "model_id": (config.get("model") or {}).get("model_id"),
            "base_url": (config.get("model") or {}).get("base_url"),
            "pricing": (config.get("model") or {}).get("pricing"),
            "temperature": (config.get("model") or {}).get("temperature"),
        },
        "limits": config.get("budget"),
        "seed": config.get("seed"),
        "thresholds": {
            "stage1_main_cells": 48,
            "stage1_min_definite_labels": 12,
            "stage1_definite_accuracy_min": 0.70,
            "stage1_net_gain_min": 3,
            "note": "exploratory screen, not a statistical proof",
        },
        "missing_data_policy": "missing is not unsure; UNKNOWN is not PASS; do not resend usage_unknown calls",
        "human_answers_present": True,
        "p5_executed": False,
    }
    _dump(Path(out_path), manifest)
    return manifest


def export_blind(run_dir: Path, out_dir: Path, *, seed: int) -> dict[str, Any]:
    rows = _read_jsonl(Path(run_dir) / "arm_pass_rows.jsonl")
    if not rows:
        raise RunnerError("no arm rows to export")
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        digest = json.dumps(row.get("artifact_hashes") or {}, sort_keys=True)
        if not row.get("artifact_hashes"):
            digest = f"missing:{row['task_id']}:{row['arm']}:{row['pass_index']}"
        groups.setdefault(digest, []).append(row)
    rng = random.Random(seed)
    items = list(groups.items())
    rng.shuffle(items)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mapping = []
    parts = ["# 盲評包", "", "每份只含任務、備忘錄與計畫。方法名稱、檢查分數與本人身份不在這份給評讀的文件裡。", ""]
    for index, (digest, members) in enumerate(items, 1):
        blind_id = f"B{index:02d}"
        sample = members[0]
        artifact = _find_artifact(Path(run_dir), sample)
        memo = artifact[0].read_text(encoding="utf-8") if artifact and artifact[0].is_file() else "(沒有備忘錄)"
        plan = artifact[1].read_text(encoding="utf-8") if artifact and artifact[1].is_file() else "(沒有計畫)"
        facts_path = Path(run_dir) / "controls" / sample["task_id"] / "inputs" / "task_facts.json"
        facts = facts_path.read_text(encoding="utf-8") if facts_path.is_file() else sample["task_id"]
        parts.append(f"## {blind_id}")
        parts.append("")
        parts.append("### 任務")
        parts.append(facts)
        parts.append("")
        parts.append("### memo.md")
        parts.append(memo)
        parts.append("")
        parts.append("### plan.json")
        parts.append(plan)
        parts.append("")
        for member in members:
            member["blind_id"] = blind_id
            mapping.append({
                "blind_id": blind_id,
                "task_id": member["task_id"],
                "arm": member["arm"],
                "pass_index": member["pass_index"],
                "call_id": member.get("call_id"),
                "artifact_hashes": member.get("artifact_hashes"),
                "shared_first_draft_group": member.get("shared_first_draft_group"),
            })
    text = "\n".join(parts)
    for token in ("arm A", "arm B", "arm C", "arm D", "GATE-ON", "contract_status"):
        if token in text:
            raise RunnerError(f"blind bundle leaked {token}")
    (out / "bundle.md").write_text(text, encoding="utf-8")
    _dump(out / "mapping.json", {"items": mapping, "display_items": len(items), "row_identities": len(mapping)})
    _jsonl(Path(run_dir) / "arm_pass_rows.jsonl", rows)
    return {"display_items": len(items), "row_identities": len(mapping)}


def _find_artifact(run_dir: Path, row: dict[str, Any]) -> tuple[Path, Path] | None:
    if row["pass_index"] == 1 and row.get("representation"):
        base = run_dir / "artifacts" / row["task_id"] / row["representation"] / "pass1"
    else:
        base = run_dir / "artifacts" / row["task_id"] / row["arm"] / "pass2"
    return base / "memo.md", base / "plan.json"


def write_result(run_dir: Path, out_path: Path, reviews_path: Path | None = None) -> dict[str, Any]:
    rows = _read_jsonl(Path(run_dir) / "arm_pass_rows.jsonl")
    calls = _read_jsonl(Path(run_dir) / "calls.jsonl")
    reviews = _read_jsonl(Path(reviews_path)) if reviews_path and Path(reviews_path).is_file() else []
    metrics = stage2_metrics(rows, reviews, calls) if rows else {}
    decision = "inconclusive"
    reason = "P5 was not run. Human calibration answers, holdout labels, and blind reviews are not in this repository, so no preference result is reported."
    if reviews and rows:
        reason = "Reviews were supplied to this report. The decision stays inconclusive unless a separate screen_decision.md records the stage-1 bar. This command does not invent a go."
    lines = [
        "# personal preference pilot result",
        "",
        f"1. 決策：{decision}。{reason}",
        "這一節若對到 fixture_plumbing 列，那些列只證明管線能跑完；它們不是本人採用，也不是模型試驗。",
        "2. 實驗身份：見 freeze manifest。此報告不填模型試驗的 SHA。",
        f"3. 完成格數：arm rows {len(rows)}。預定 screen 為 48 列、36 個獨立請求。",
        "4. Stage 1：沒有封存的保留標籤，不計算準確率。",
        "5. Stage 2：客觀檢查與本人採用分開。沒有盲評時採用率留空，不填 0。",
        "6. 成本：見 metrics。本地端點不推導美元；沒有成功交付時不填每成功成本 0。",
        "7. 具體改善與失敗：沒有真人試驗，不列假的改善。",
        "8. 限制：N=1 尚未發生。合成任務。沒有無個人資料對照組。非原生工具 agent。",
        "9. 下一步：先由本人填 C01–C16，再跑一次端點相容性預檢。",
        "10. 重算：python -m vacant_network.personal report --run-dir <run>。不需要再呼叫模型。",
        "",
        "## metrics",
        "",
        "```json",
        json.dumps(metrics, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    return {"decision": decision, "metrics": metrics}
