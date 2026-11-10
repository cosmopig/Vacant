"""把 memo.md／plan.json 送進既有 intake。

這支在架構裡承重什麼：契約用主線 `contract.parse` 與 `flow.check`，
不重寫 accept。三條主張只用 exists／json_schema／command 已經接受的
參數。quote、evidence、confidence 留在 sidecar，不塞進 claim params。

accept 只表示這份契約的必要檢查過了。human_acceptance 維持 null。
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from vacant_network.intake.cli import EXIT
from vacant_network.intake.contract import parse, path_sha256
from vacant_network.intake.flow import check as intake_check
from vacant_network.intake.verifiers import COMMAND_EXIT, VERIFIERS

from .schemas import plan_json_schema

CLAIM_IDS = ("deliverables_present", "plan_schema", "plan_matches_pinned_task")
ALLOWED_PARAMS = {name: set(spec.params) for name, spec in VERIFIERS.items()}


class BridgeError(RuntimeError):
    pass


def _checker_source(explicit: Path | None) -> Path:
    if explicit is not None:
        return Path(explicit)
    here = Path(__file__).resolve()
    candidate = here.parents[2] / "ops" / "personal_pilot" / "trusted_checks" / "check_plan.py"
    if candidate.is_file():
        return candidate
    raise BridgeError(f"pinned checker is not at {candidate}")


def supported_param_problems(raw: dict[str, Any]) -> list[str]:
    problems = []
    for index, claim in enumerate(raw.get("claims") or []):
        verifier = claim.get("verifier")
        allowed = ALLOWED_PARAMS.get(verifier)
        if allowed is None:
            problems.append(f"claims[{index}] verifier {verifier!r} is not in the intake set")
            continue
        extra = sorted(set(claim.get("params") or {}) - allowed)
        if extra:
            problems.append(f"claims[{index}] {verifier} has unsupported params {extra}")
    return problems


def build_control(control_dir: Path, task: dict[str, Any], *, checker_source: Path | None = None, timeout_s: float = 5, extra_env: dict[str, str] | None = None, python_executable: str | None = None) -> dict[str, Any]:
    """初次釘住。之後驗收只讀這份 contract，不重算釘子來洗掉差異。"""
    control = Path(control_dir).resolve()
    if control.exists():
        shutil.rmtree(control)
    inputs = control / "inputs"
    checker_dir = control / "trusted_checks"
    sidecar_dir = control / "sidecars"
    inputs.mkdir(parents=True)
    checker_dir.mkdir(parents=True)
    sidecar_dir.mkdir(parents=True)
    facts_path = inputs / "task_facts.json"
    schema_path = inputs / "plan.schema.json"
    checker_path = checker_dir / "check_plan.py"
    facts_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    schema_path.write_text(json.dumps(plan_json_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(_checker_source(checker_source), checker_path)
    report_path = sidecar_dir / "check_report.tmp.json"
    env = {"VACANT_PERSONAL_CHECK_REPORT": str(report_path)}
    if extra_env:
        for key, value in extra_env.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise BridgeError("command env values must be strings")
            env[key] = value
    executable = python_executable or sys.executable
    raw: dict[str, Any] = {
        "schema": "vacant-contract/1",
        "task_id": f"personal-pilot-{task['task_id']}",
        "version": 1,
        "objective": "依固定任務事實交付 memo.md 與 plan.json",
        "owner": "pilot-owner",
        "deliverable": {"include": ["memo.md", "plan.json"], "exclude": []},
        "inputs": {
            "task_facts": {"path": "inputs/task_facts.json"},
            "plan_schema": {"path": "inputs/plan.schema.json"},
            "checker": {"path": "trusted_checks/check_plan.py"},
        },
        "claims": [
            {
                "id": "deliverables_present",
                "verifier": "exists",
                "params": {"paths": ["memo.md", "plan.json"]},
                "required": True,
                "authority": "requirement",
            },
            {
                "id": "plan_schema",
                "verifier": "json_schema",
                "params": {"path": "plan.json", "schema_input": "plan_schema"},
                "required": True,
                "authority": "requirement",
            },
            {
                "id": "plan_matches_pinned_task",
                "verifier": "command",
                "params": {
                    "argv": [executable, "-I", str(checker_path.resolve())],
                    "timeout_s": timeout_s,
                    "sandbox": "none",
                    "env": env,
                },
                "required": True,
                "authority": "fact",
            },
        ],
        "unknown_policy": "hold",
        "conflict_policy": "escalate",
    }
    problems = supported_param_problems(raw)
    if problems:
        raise BridgeError("; ".join(problems))
    for spec in raw["inputs"].values():
        spec["sha256"] = path_sha256((control / spec["path"]).resolve())
    contract_path = control / "contract.json"
    contract = parse(raw, path=contract_path, base_dir=control, known_verifiers=set(VERIFIERS))
    contract_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    freeze = {"contract_sha256": contract.sha256, "task_id": task["task_id"]}
    (control / "freeze.json").write_text(json.dumps(freeze, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    argv_checker = Path(raw["claims"][2]["params"]["argv"][2]).resolve()
    pinned_checker = (control / raw["inputs"]["checker"]["path"]).resolve()
    if argv_checker != pinned_checker:
        raise BridgeError("command argv does not resolve to the pinned checker")
    return {"control_dir": control, "contract_path": contract_path, "report_path": report_path, "contract_sha256": contract.sha256, "raw": raw}


def _file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path_sha256(path)


def reconcile_report(report_path: Path, candidate_hashes: dict[str, str | None], decision: dict[str, Any], contract_raw: dict[str, Any]) -> dict[str, Any]:
    """核對 sidecar 與 command 總結果。不一致就標 report_integrity_unknown，不改 intake 裁決。"""
    command = next((row for row in decision.get("results") or [] if row.get("claim_id") == "plan_matches_pinned_task"), None)
    if command is None:
        return {"ok": False, "code": "report_integrity_unknown", "reason": "command claim missing", "stop": True, "intake_outcome": decision.get("outcome")}
    detail = str(command.get("detail") or "")
    evidence = command.get("evidence") or {}
    explained = command.get("status") == "UNKNOWN" and (
        "unverified inputs" in detail or "not pinned" in detail or "cannot run the command" in detail
    )
    if explained:
        return {"ok": True, "explained_absence": True, "reason": detail, "stop": False, "intake_outcome": decision.get("outcome"), "report": None}
    if not report_path.is_file():
        return {
            "ok": False,
            "code": "report_integrity_unknown",
            "reason": "sidecar missing",
            "stop": True,
            "intake_outcome": decision.get("outcome"),
            "command_status": command.get("status"),
        }
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "code": "report_integrity_unknown", "reason": f"sidecar unreadable: {exc}", "stop": True, "intake_outcome": decision.get("outcome")}
    problems = []
    pins = {name: spec.get("sha256") for name, spec in (contract_raw.get("inputs") or {}).items()}
    got_inputs = report.get("input_sha256") or {}
    for name in ("task_facts", "plan_schema", "checker"):
        if got_inputs.get(name) != pins.get(name):
            problems.append(f"input hash {name} does not match the contract pin")
    if report.get("candidate_sha256") != candidate_hashes:
        problems.append("candidate file hashes do not match the files submitted to this check")
    exit_code = report.get("exit_code")
    expected_status = "UNKNOWN" if evidence.get("timed_out") or evidence.get("rc") is None else COMMAND_EXIT.get(evidence.get("rc"), "UNKNOWN")
    if exit_code not in (0, 1, 2, 3):
        problems.append(f"sidecar exit_code {exit_code!r} is not 0, 1, 2, or 3")
    elif COMMAND_EXIT.get(exit_code, "UNKNOWN") != command.get("status") and not (evidence.get("timed_out") and command.get("status") == "UNKNOWN"):
        problems.append(f"sidecar exit {exit_code} does not match command status {command.get('status')}")
    if evidence.get("rc") is not None and exit_code != evidence.get("rc"):
        problems.append(f"sidecar exit {exit_code} does not match command rc {evidence.get('rc')}")
    if expected_status != command.get("status"):
        problems.append("command evidence rc does not match its status")
    if problems:
        return {
            "ok": False,
            "code": "report_integrity_unknown",
            "reason": "; ".join(problems),
            "stop": True,
            "intake_outcome": decision.get("outcome"),
            "report": report,
            "command_status": command.get("status"),
        }
    return {"ok": True, "explained_absence": False, "reason": "", "stop": False, "intake_outcome": decision.get("outcome"), "report": report, "command_status": command.get("status")}


def check_artifacts(control_dir: Path, artifact_dir: Path) -> dict[str, Any]:
    control = Path(control_dir).resolve()
    artifact = Path(artifact_dir).resolve()
    contract_path = control / "contract.json"
    freeze = json.loads((control / "freeze.json").read_text(encoding="utf-8"))
    raw = json.loads(contract_path.read_text(encoding="utf-8"))
    contract = parse(raw, path=contract_path, base_dir=control, known_verifiers=set(VERIFIERS))
    if contract.sha256 != freeze["contract_sha256"]:
        raise BridgeError("contract differs from the frozen protocol")
    report_path = Path(raw["claims"][2]["params"]["env"]["VACANT_PERSONAL_CHECK_REPORT"]).resolve()
    try:
        report_path.relative_to((control / "sidecars").resolve())
    except ValueError as exc:
        raise BridgeError("report path is not inside the controller sidecar directory") from exc
    report_path.unlink(missing_ok=True)
    candidate_hashes = {
        "memo.md": _file_hash(artifact / "memo.md"),
        "plan.json": _file_hash(artifact / "plan.json"),
    }
    decision = intake_check(contract, artifact, sandbox="auto")
    integrity = reconcile_report(report_path, candidate_hashes, decision, raw)
    outcome = decision.get("outcome")
    return {
        "outcome": outcome,
        "exit_code": EXIT.get(str(outcome), 2),
        "decision": decision,
        "integrity": integrity,
        "contract_sha256": contract.sha256,
        "artifact_sha256": decision.get("artifact_sha256"),
        "candidate_hashes": candidate_hashes,
        "human_acceptance": None,
        "report_path": str(report_path),
        "stop": bool(integrity.get("stop")),
    }


def write_artifacts(artifact_dir: Path, memo: str, plan: dict[str, Any]) -> None:
    artifact = Path(artifact_dir)
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / "memo.md").write_text(memo, encoding="utf-8")
    (artifact / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
