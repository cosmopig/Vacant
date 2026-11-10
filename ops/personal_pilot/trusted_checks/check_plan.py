#!/usr/bin/env python3
"""可信 checker：依釘住的 task facts 重算 plan.json，並寫一份 sidecar 報告。

這支在架構裡承重什麼：intake 的 command 驗證器只看退出碼。費用、人時、
選項與依賴的逐項結果寫在 sidecar，不另外發明一套放行標準。main 的
ClaimResult 仍是這一條 command 的總結果。

退出碼：0 PASS、1 可證明的作品 FAIL、3 CONFLICT、2 或其他＝UNKNOWN。
內部例外一律改成 2，避免 Python 預設的 1 把檢查器故障記成作品不合格。
只使用標準函式庫。不修改作品與輸入。布林值不是整數。

VACANT_PERSONAL_CHECKER_FAULT=raise 是失敗關閉的故障注入：契約範本不會
設定它。設了就寫一筆 setup UNKNOWN 並以 2 結束，不會變成 PASS。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check(checks: list[dict], check_id: str, status: str, observed, expected, evidence_path: str, error_type: str | None) -> None:
    checks.append({
        "check_id": check_id,
        "status": status,
        "observed": observed,
        "expected_or_constraint": expected,
        "evidence_path": evidence_path,
        "error_type": error_type,
    })


def _write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _report_path(artifact: Path) -> Path | None:
    raw = os.environ.get("VACANT_PERSONAL_CHECK_REPORT")
    if not raw:
        return None
    path = Path(raw).resolve()
    if path == artifact or artifact in path.parents:
        return None
    for key, value in os.environ.items():
        if key.startswith("VACANT_INPUT_") and value:
            other = Path(value).resolve()
            if path == other:
                return None
    return path


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _facts_problems(facts: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(facts, dict):
        return ["task facts must be an object"]
    if not isinstance(facts.get("task_id"), str) or not facts.get("task_id"):
        problems.append("facts.task_id must be a non-empty string")
    for key in ("max_person_hours", "max_cost_units", "min_options", "max_options"):
        if not _is_int(facts.get(key)) or facts.get(key) < 0:
            problems.append(f"facts.{key} must be a non-negative integer")
    options = facts.get("options")
    if not isinstance(options, list) or not options:
        problems.append("facts.options must be a non-empty list")
        options = []
    seen: set[str] = set()
    for index, opt in enumerate(options):
        if not isinstance(opt, dict):
            problems.append(f"facts.options[{index}] must be an object")
            continue
        oid = opt.get("id")
        if not isinstance(oid, str) or not oid:
            problems.append(f"facts.options[{index}].id must be a non-empty string")
        elif oid in seen:
            problems.append(f"duplicate option id {oid}")
        else:
            seen.add(oid)
        for key in ("cost_units", "person_hours"):
            if not _is_int(opt.get(key)) or opt.get(key) < 0:
                problems.append(f"option {oid}: {key} must be a non-negative integer, not a boolean")
        deps = opt.get("depends_on")
        if not isinstance(deps, list) or not all(isinstance(item, str) for item in deps):
            problems.append(f"option {oid}: depends_on must be a list of strings")
        elif isinstance(oid, str):
            for dep in deps:
                if dep not in seen and dep not in {o.get("id") for o in options if isinstance(o, dict)}:
                    problems.append(f"option {oid} depends_on unknown id {dep}")
    required = facts.get("required_option_ids")
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        problems.append("facts.required_option_ids must be a list of strings")
    elif any(item not in seen for item in required):
        problems.append("facts.required_option_ids contains an unknown id")
    groups = facts.get("choice_groups")
    if not isinstance(groups, list):
        problems.append("facts.choice_groups must be a list")
    else:
        for index, group in enumerate(groups):
            if not isinstance(group, dict):
                problems.append(f"choice_groups[{index}] must be an object")
                continue
            ids = group.get("option_ids")
            count = group.get("min_count")
            if not isinstance(ids, list) or not ids or not all(isinstance(item, str) and item in seen for item in ids):
                problems.append(f"choice_groups[{index}].option_ids must be existing ids")
            if not _is_int(count) or count < 1:
                problems.append(f"choice_groups[{index}].min_count must be an integer >= 1")
            elif isinstance(ids, list) and count > len(set(ids)):
                problems.append(f"choice_groups[{index}].min_count exceeds the group")
    if isinstance(facts.get("min_options"), int) and isinstance(facts.get("max_options"), int):
        if facts["min_options"] > facts["max_options"]:
            problems.append("min_options exceeds max_options")
    if not problems and _cycle(facts):
        problems.append("facts dependency graph has a cycle")
    return problems


def _cycle(facts: dict) -> bool:
    by_id = {opt["id"]: opt for opt in facts["options"]}
    state: dict[str, int] = {}

    def visit(node: str) -> bool:
        mark = state.get(node, 0)
        if mark == 1:
            return True
        if mark == 2:
            return False
        state[node] = 1
        for dep in by_id[node]["depends_on"]:
            if dep in by_id and visit(dep):
                return True
        state[node] = 2
        return False

    return any(visit(node) for node in by_id if state.get(node, 0) == 0)


def _evaluate(facts: dict, artifact: Path, checks: list[dict]) -> None:
    memo_path = artifact / "memo.md"
    plan_path = artifact / "plan.json"
    memo_text = ""
    try:
        memo_text = memo_path.read_text(encoding="utf-8")
    except OSError as exc:
        _check(checks, "memo_readable", "FAIL", str(exc), "non-empty readable memo.md", "memo.md", "artifact")
    else:
        if memo_text.strip():
            _check(checks, "memo_readable", "PASS", "non-empty text", "non-empty readable memo.md", "memo.md", None)
        else:
            _check(checks, "memo_readable", "FAIL", "empty", "non-empty readable memo.md", "memo.md", "artifact")
    try:
        plan = _load_json(plan_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _check(checks, "plan_json", "FAIL", f"{type(exc).__name__}: {exc}", "plan.json is a JSON object", "plan.json", "artifact")
        return
    if not isinstance(plan, dict):
        _check(checks, "plan_json", "FAIL", type(plan).__name__, "plan.json is a JSON object", "plan.json", "artifact")
        return
    _check(checks, "plan_json", "PASS", "object", "plan.json is a JSON object", "plan.json", None)
    if plan.get("task_id") == facts["task_id"]:
        _check(checks, "task_id", "PASS", plan.get("task_id"), facts["task_id"], "plan.json#/task_id", None)
    else:
        _check(checks, "task_id", "FAIL", plan.get("task_id"), facts["task_id"], "plan.json#/task_id", "artifact")

    selected = plan.get("selected_option_ids")
    by_id = {opt["id"]: opt for opt in facts["options"]}
    ids_ok = isinstance(selected, list) and all(isinstance(item, str) for item in selected)
    if not ids_ok:
        _check(checks, "selected_ids", "FAIL", selected, "list of option id strings", "plan.json#/selected_option_ids", "artifact")
        return
    observed_ids = list(selected)
    duplicate = len(observed_ids) != len(set(observed_ids))
    unknown = [item for item in observed_ids if item not in by_id]
    if duplicate or unknown:
        _check(
            checks, "selected_ids", "FAIL", observed_ids,
            "no duplicates and every id exists; unknown or duplicate ids are not dropped",
            "plan.json#/selected_option_ids", "artifact",
        )
        _check(
            checks, "totals_not_repaired", "FAIL", observed_ids,
            "cost and hours are not recomputed by discarding bad ids",
            "plan.json#/selected_option_ids", "artifact",
        )
        return
    count = len(observed_ids)
    if facts["min_options"] <= count <= facts["max_options"]:
        _check(checks, "option_count", "PASS", count, f"{facts['min_options']}..{facts['max_options']}", "plan.json#/selected_option_ids", None)
    else:
        _check(checks, "option_count", "FAIL", count, f"{facts['min_options']}..{facts['max_options']}", "plan.json#/selected_option_ids", "artifact")
    missing_required = [item for item in facts["required_option_ids"] if item not in set(observed_ids)]
    if missing_required:
        _check(checks, "required_options", "FAIL", observed_ids, facts["required_option_ids"], "plan.json#/selected_option_ids", "artifact")
    else:
        _check(checks, "required_options", "PASS", observed_ids, facts["required_option_ids"], "plan.json#/selected_option_ids", None)
    chosen = set(observed_ids)
    for index, group in enumerate(facts["choice_groups"]):
        hit = sorted(chosen & set(group["option_ids"]))
        if len(hit) >= group["min_count"]:
            _check(checks, f"choice_group_{index}", "PASS", hit, group, f"facts.choice_groups[{index}]", None)
        else:
            _check(checks, f"choice_group_{index}", "FAIL", hit, group, f"facts.choice_groups[{index}]", "artifact")
    cost = sum(by_id[item]["cost_units"] for item in observed_ids)
    hours = sum(by_id[item]["person_hours"] for item in observed_ids)
    stated_cost = plan.get("total_cost_units")
    stated_hours = plan.get("total_person_hours")
    if _is_int(stated_cost) and stated_cost == cost and stated_cost <= facts["max_cost_units"]:
        _check(checks, "total_cost_units", "PASS", stated_cost, {"recomputed": cost, "max": facts["max_cost_units"]}, "plan.json#/total_cost_units", None)
    else:
        _check(
            checks, "total_cost_units", "FAIL", stated_cost,
            {"recomputed": cost, "max": facts["max_cost_units"], "note": "boolean is not an integer"},
            "plan.json#/total_cost_units", "artifact",
        )
    if _is_int(stated_hours) and stated_hours == hours and stated_hours <= facts["max_person_hours"]:
        _check(checks, "total_person_hours", "PASS", stated_hours, {"recomputed": hours, "max": facts["max_person_hours"]}, "plan.json#/total_person_hours", None)
    else:
        _check(
            checks, "total_person_hours", "FAIL", stated_hours,
            {"recomputed": hours, "max": facts["max_person_hours"], "note": "sum of person_hours is not a calendar duration"},
            "plan.json#/total_person_hours", "artifact",
        )
    missing_deps = []
    for item in observed_ids:
        for dep in by_id[item]["depends_on"]:
            if dep not in chosen:
                missing_deps.append({"option": item, "missing": dep})
    sequence = plan.get("sequence")
    sequence_ok = isinstance(sequence, list) and sequence == list(dict.fromkeys(sequence)) and set(sequence) == chosen and len(sequence) == len(chosen)
    order_bad = []
    if sequence_ok:
        index = {item: pos for pos, item in enumerate(sequence)}
        for item in observed_ids:
            for dep in by_id[item]["depends_on"]:
                if dep not in index:
                    continue
                if index[dep] >= index[item]:
                    order_bad.append({"option": item, "dependency": dep})
    if missing_deps or not sequence_ok or order_bad:
        _check(
            checks, "dependencies_and_sequence", "FAIL",
            {"selected": observed_ids, "sequence": sequence, "missing_deps": missing_deps, "order_bad": order_bad},
            "sequence is a permutation of selected ids; each depends_on is selected and strictly earlier",
            "plan.json#/sequence", "artifact",
        )
    else:
        _check(checks, "dependencies_and_sequence", "PASS", sequence, "topological order only; not a calendar", "plan.json#/sequence", None)
    validation = plan.get("validation")
    text_ok = (
        isinstance(validation, list) and len(validation) >= 1
        and all(isinstance(item, dict) and all(isinstance(item.get(key), str) and item.get(key).strip() for key in ("metric", "method", "decision_rule")) for item in validation)
        and isinstance(plan.get("stop_condition"), str) and plan.get("stop_condition").strip()
        and isinstance(plan.get("tradeoff"), str) and plan.get("tradeoff").strip()
        and isinstance(plan.get("assumptions"), list) and all(isinstance(item, str) and item.strip() for item in plan["assumptions"])
    )
    if text_ok:
        _check(checks, "required_text_fields", "PASS", "present", "non-empty structure only; substance is not judged", "plan.json#/validation", None)
    else:
        _check(checks, "required_text_fields", "FAIL", {"validation": validation, "stop_condition": plan.get("stop_condition"), "tradeoff": plan.get("tradeoff")}, "validation has at least one row; stop_condition and tradeoff are non-empty; non-empty does not mean the prose is good", "plan.json#/validation", "artifact")


def _exit_code(checks: list[dict]) -> int:
    if any(item["status"] == "UNKNOWN" and item.get("error_type") == "setup" for item in checks):
        return 2
    if any(item["status"] == "CONFLICT" for item in checks):
        return 3
    if any(item["status"] == "FAIL" for item in checks):
        return 1
    if any(item["status"] == "UNKNOWN" for item in checks):
        return 2
    return 0


def run() -> int:
    if os.environ.get("VACANT_PERSONAL_CHECKER_FAULT") == "raise":
        raise RuntimeError("injected checker fault")
    artifact_raw = os.environ.get("VACANT_ARTIFACT_DIR")
    facts_raw = os.environ.get("VACANT_INPUT_TASK_FACTS")
    schema_raw = os.environ.get("VACANT_INPUT_PLAN_SCHEMA")
    checker_raw = os.environ.get("VACANT_INPUT_CHECKER")
    if not artifact_raw or not facts_raw or not schema_raw or not checker_raw:
        print("checker missing required VACANT_* paths", file=sys.stderr)
        return 2
    artifact = Path(artifact_raw).resolve()
    report = _report_path(artifact)
    checks: list[dict] = []
    facts_path = Path(facts_raw)
    schema_path = Path(schema_raw)
    checker_path = Path(checker_raw)
    hashes = {
        "task_facts": _sha256(facts_path),
        "plan_schema": _sha256(schema_path),
        "checker": _sha256(checker_path),
    }
    candidates = {
        "memo.md": _sha256(artifact / "memo.md"),
        "plan.json": _sha256(artifact / "plan.json"),
    }
    if hashes["plan_schema"] is None or hashes["checker"] is None or hashes["task_facts"] is None:
        _check(checks, "pinned_inputs_readable", "UNKNOWN", hashes, "task facts, schema, and checker files exist", "inputs", "setup")
        code = 2
        task_id = None
    else:
        try:
            facts = _load_json(facts_path)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            _check(checks, "facts_json", "UNKNOWN", str(exc), "task facts is JSON", "task_facts.json", "setup")
            facts = None
        problems = _facts_problems(facts) if facts is not None else ["unreadable facts"]
        task_id = facts.get("task_id") if isinstance(facts, dict) else None
        if problems:
            _check(checks, "facts_valid", "UNKNOWN", problems, "trial setup error; the candidate is not judged against invalid facts", "task_facts.json", "setup")
        else:
            _check(checks, "facts_valid", "PASS", task_id, "facts shape is valid for this checker", "task_facts.json", None)
            _evaluate(facts, artifact, checks)
        code = _exit_code(checks)
    payload = {
        "task_id": task_id,
        "input_sha256": hashes,
        "candidate_sha256": candidates,
        "checks": checks,
        "exit_code": code,
    }
    if report is None:
        print("checker could not write its report", file=sys.stderr)
        return 2
    try:
        _write_report(report, payload)
    except OSError as exc:
        print(f"checker report write failed: {exc}", file=sys.stderr)
        return 2
    summary = f"task={task_id} exit={code} checks={len(checks)}"
    print(summary[:1500])
    return code


def main() -> int:
    try:
        return run()
    except Exception as exc:  # noqa: BLE001 — 內部錯誤必須是 2，不能落成 Python 的 1
        artifact_raw = os.environ.get("VACANT_ARTIFACT_DIR")
        report = None
        if artifact_raw:
            report = _report_path(Path(artifact_raw).resolve())
        payload = {
            "task_id": None,
            "input_sha256": {},
            "candidate_sha256": {},
            "checks": [{
                "check_id": "checker_internal",
                "status": "UNKNOWN",
                "observed": f"{type(exc).__name__}: {exc}",
                "expected_or_constraint": "checker finishes without an internal exception",
                "evidence_path": "checker",
                "error_type": "setup",
            }],
            "exit_code": 2,
        }
        if report is not None:
            try:
                _write_report(report, payload)
            except OSError:
                pass
        print(f"checker internal error: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
