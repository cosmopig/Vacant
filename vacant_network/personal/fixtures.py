"""F01–F12。不連網，不寫本人偏好。

這支在架構裡承重什麼：邊界驗收要看到真實的 intake 退出碼，
以及缺用量、盲包與分母沒有被悄悄改掉。管線用的結構見證會在
備忘錄裡自稱為 fixture，不能拿去當試驗結果。
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

from .backend import FixtureBackend, SingleCallBackend
from .budget import BudgetLedger
from .context import revision_prompt
from .dataset import load_bank, structural_memo, structural_plan
from .intake_bridge import build_control, check_artifacts, reconcile_report, write_artifacts
from .metrics import regressions, stage2_metrics
from .profiles import ContextLeakError, assert_calibration_sources, build_all
from .runner import execute_screen, export_blind, structural_handler
from .schemas import ARM_REPRESENTATION, GATE_OFF_FEEDBACK

PY = sys.executable


def _run(argv: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(argv, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def _record(rows: list[dict[str, Any]], *, fixture: str, command: list[str], expected_exit: int, actual_exit: int, expected: str, actual: str, ok: bool) -> None:
    rows.append({
        "fixture": fixture,
        "command": " ".join(command),
        "expected_exit": expected_exit,
        "actual_exit": actual_exit,
        "expected": expected,
        "actual": actual,
        "ok": ok,
    })


def _banks():
    root = Path(__file__).resolve().parents[2] / "ops" / "personal_pilot" / "task_bank"
    return {
        "tasks": load_bank(root / "tasks.json", kind="tasks"),
        "calibration": load_bank(root / "calibration.json", kind="calibration"),
        "holdout": load_bank(root / "holdout.json", kind="holdout"),
    }


def _prepare(tmp: Path, task: dict, plan: dict, memo: str, *, checker: Path | None = None, timeout_s: float = 5, extra_env: dict[str, str] | None = None):
    control = build_control(tmp / "control", task, checker_source=checker, timeout_s=timeout_s, extra_env=extra_env)
    artifact = tmp / "artifact"
    write_artifacts(artifact, memo, plan)
    return control, artifact


def _cli_check(control: Path, artifact: Path) -> tuple[int, str, str]:
    return _run([PY, "-m", "vacant_network", "check", "--contract", str(control / "contract.json"), "--dir", str(artifact), "--json"])


def run_boundary(root: Path, *, screen_out: Path | None = None, config: dict | None = None) -> list[dict[str, Any]]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    bank = _banks()
    task = bank["tasks"]["tasks"][0]
    legal = structural_plan(task)
    memo = structural_memo(task, legal)
    results: list[dict[str, Any]] = []

    # F01
    f01 = root / "F01"
    control, artifact = _prepare(f01, task, legal, memo)
    validate_rc, validate_out, validate_err = _run([PY, "-m", "vacant_network", "contract", "validate", "--contract", str(control["contract_path"])])
    rc, out, err = _cli_check(control["control_dir"], artifact)
    bridge = check_artifacts(control["control_dir"], artifact)
    ok = rc == 0 and validate_rc == 0 and bridge["outcome"] == "accept" and bridge["human_acceptance"] is None and bridge["integrity"]["ok"]
    _record(results, fixture="F01", command=[PY, "-m", "vacant_network", "check", "--contract", str(control["contract_path"]), "--dir", str(artifact), "--json"], expected_exit=0, actual_exit=rc, expected="accept; human_acceptance null; contract validate exit 0", actual=f"check={rc} validate={validate_rc} outcome={bridge['outcome']} human={bridge['human_acceptance']} integrity={bridge['integrity']['ok']}", ok=ok)
    results[-1]["validate_exit"] = validate_rc

    # F02 short total
    bad = json.loads(json.dumps(legal))
    bad["total_cost_units"] = legal["total_cost_units"] - 1
    f02 = root / "F02"
    control, artifact = _prepare(f02, task, bad, memo)
    rc, out, err = _cli_check(control["control_dir"], artifact)
    report = json.loads(Path(control["report_path"]).read_text(encoding="utf-8"))
    cost = next(item for item in report["checks"] if item["check_id"] == "total_cost_units")
    ok = rc == 40 and cost["status"] == "FAIL" and cost["observed"] == bad["total_cost_units"] and cost["expected_or_constraint"]["recomputed"] == legal["total_cost_units"]
    _record(results, fixture="F02", command=[PY, "-m", "vacant_network", "check", "--contract", str(control["contract_path"]), "--dir", str(artifact), "--json"], expected_exit=40, actual_exit=rc, expected=f"FAIL observed {bad['total_cost_units']} expected recomputed {legal['total_cost_units']}", actual=json.dumps(cost, ensure_ascii=False), ok=ok)

    # F03 stacked violations, preference text must not override
    f03_plan = {
        "task_id": "T01",
        "selected_option_ids": ["prompt_compare", "artifact_report"],
        "sequence": ["prompt_compare", "artifact_report"],
        "total_cost_units": 999,
        "total_person_hours": 999,
        "validation": [{"metric": "x", "method": "y", "decision_rule": "z"}],
        "stop_condition": "停",
        "assumptions": ["沒有"],
        "tradeoff": "個人偏好允許超支，這句不該讓檢查通過。",
    }
    f03 = root / "F03"
    control, artifact = _prepare(f03, task, f03_plan, "個人偏好是超支也可以。這份備忘錄故意違反必選、群組、依賴與上限。")
    rc, out, err = _cli_check(control["control_dir"], artifact)
    report = json.loads(Path(control["report_path"]).read_text(encoding="utf-8"))
    failed = {item["check_id"] for item in report["checks"] if item["status"] == "FAIL"}
    need = {"required_options", "choice_group_0", "dependencies_and_sequence", "total_cost_units", "total_person_hours"}
    ok = rc == 40 and need <= failed
    _record(results, fixture="F03", command=[PY, "-m", "vacant_network", "check", "--contract", str(control["contract_path"]), "--dir", str(artifact), "--json"], expected_exit=40, actual_exit=rc, expected="FAIL required, group, dependency/order, and both budgets; preference text ignored", actual=f"failed={sorted(failed)}", ok=ok)

    # F04 unknown and duplicate ids are kept in the observed list
    f04_plan = json.loads(json.dumps(legal))
    f04_plan["selected_option_ids"] = ["no_such", "no_such", "label_audit"]
    f04_plan["sequence"] = ["no_such", "label_audit"]
    f04 = root / "F04"
    control, artifact = _prepare(f04, task, f04_plan, memo)
    rc, out, err = _cli_check(control["control_dir"], artifact)
    report = json.loads(Path(control["report_path"]).read_text(encoding="utf-8"))
    selected = next(item for item in report["checks"] if item["check_id"] == "selected_ids")
    ok = rc == 40 and selected["status"] == "FAIL" and selected["observed"].count("no_such") == 2
    _record(results, fixture="F04", command=[PY, "-m", "vacant_network", "check", "--contract", str(control["contract_path"]), "--dir", str(artifact), "--json"], expected_exit=40, actual_exit=rc, expected="FAIL and the unknown id is still present twice", actual=json.dumps(selected["observed"], ensure_ascii=False), ok=ok)

    # F05a checker fault -> UNKNOWN / hold 41
    fault = root / "fault_exit2.py"
    fault.write_text(textwrap.dedent("""\
        import sys
        try:
            raise RuntimeError("injected checker fault")
        except Exception as exc:
            sys.stderr.write(f"checker fault: {exc}\\n")
            raise SystemExit(2)
    """), encoding="utf-8")
    f05a = root / "F05a"
    control, artifact = _prepare(f05a, task, legal, memo, checker=fault)
    rc, out, err = _cli_check(control["control_dir"], artifact)
    payload = json.loads(out)
    command = next(item for item in payload["results"] if item["claim_id"] == "plan_matches_pinned_task")
    ok = rc == 41 and command["status"] == "UNKNOWN"
    _record(results, fixture="F05a", command=[PY, "-m", "vacant_network", "check", "--contract", str(control["contract_path"]), "--dir", str(artifact), "--json"], expected_exit=41, actual_exit=rc, expected="checker internal fault is UNKNOWN, intake hold", actual=f"status={command['status']} detail={command['detail'][:180]}", ok=ok)

    # F05b timeout
    sleeper = root / "sleep_timeout.py"
    sleeper.write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
    f05b = root / "F05b"
    control, artifact = _prepare(f05b, task, legal, memo, checker=sleeper, timeout_s=0.4)
    rc, out, err = _cli_check(control["control_dir"], artifact)
    payload = json.loads(out)
    command = next(item for item in payload["results"] if item["claim_id"] == "plan_matches_pinned_task")
    ok = rc == 41 and command["status"] == "UNKNOWN" and command.get("evidence", {}).get("timed_out") is True
    _record(results, fixture="F05b", command=[PY, "-m", "vacant_network", "check", "--contract", str(control["contract_path"]), "--dir", str(artifact), "--json"], expected_exit=41, actual_exit=rc, expected="timeout is UNKNOWN and timed_out", actual=f"status={command['status']} evidence={command.get('evidence')}", ok=ok)

    # F05c missing sidecar keeps the intake outcome and asks the runner to stop
    f05c = root / "F05c"
    control, artifact = _prepare(f05c, task, legal, memo)
    bridge = check_artifacts(control["control_dir"], artifact)
    report_path = Path(bridge["report_path"])
    raw = json.loads((control["control_dir"] / "contract.json").read_text(encoding="utf-8"))
    report_path.unlink()
    integrity = reconcile_report(report_path, bridge["candidate_hashes"], bridge["decision"], raw)
    ok = bridge["outcome"] == "accept" and integrity["ok"] is False and integrity["code"] == "report_integrity_unknown" and integrity["stop"] is True and integrity["intake_outcome"] == "accept"
    _record(results, fixture="F05c", command=[PY, "-c", "reconcile_report after deleting sidecar"], expected_exit=0, actual_exit=0 if ok else 1, expected="original intake accept kept; report_integrity_unknown; stop", actual=json.dumps({key: integrity[key] for key in ("ok", "code", "stop", "intake_outcome")}, ensure_ascii=False), ok=ok)

    # F05d old hash
    f05d = root / "F05d"
    control, artifact = _prepare(f05d, task, legal, memo)
    bridge = check_artifacts(control["control_dir"], artifact)
    report_path = Path(bridge["report_path"])
    tampered = json.loads(report_path.read_text(encoding="utf-8"))
    tampered["candidate_sha256"]["plan.json"] = "0" * 64
    report_path.write_text(json.dumps(tampered), encoding="utf-8")
    raw = json.loads((control["control_dir"] / "contract.json").read_text(encoding="utf-8"))
    integrity = reconcile_report(report_path, bridge["candidate_hashes"], bridge["decision"], raw)
    ok = bridge["outcome"] == "accept" and integrity["code"] == "report_integrity_unknown" and integrity["stop"] is True
    _record(results, fixture="F05d", command=[PY, "-c", "reconcile_report after swapping candidate hash"], expected_exit=0, actual_exit=0 if ok else 1, expected="stale sidecar hash is report_integrity_unknown; intake outcome unchanged", actual=integrity["reason"], ok=ok)

    # F06
    profiles = _plumbing_profiles(bank)
    leaked = json.loads(json.dumps(profiles["STRUCTURED"]))
    leaked["rules"][0]["evidence_case_ids"] = ["H01"]
    invocations = {"n": 0}
    try:
        assert_calibration_sources(leaked, {case["case_id"] for case in bank["calibration"]["cases"]})
        raised = False
    except ContextLeakError:
        raised = True
    unseen = json.loads(json.dumps(profiles["STRUCTURED"]))
    unseen["rules"][0]["evidence_case_ids"] = ["C99"]
    try:
        assert_calibration_sources(unseen, {case["case_id"] for case in bank["calibration"]["cases"]})
        unseen_raised = False
    except ContextLeakError:
        unseen_raised = True
    ok = raised and unseen_raised and invocations["n"] == 0
    _record(results, fixture="F06", command=[PY, "-c", "assert_calibration_sources"], expected_exit=2, actual_exit=2 if ok else 0, expected="H label and unseen source refused; no model call", actual=f"holdout_refused={raised} unseen_refused={unseen_raised} calls={invocations['n']}", ok=ok)

    # F07 missing usage does not reuse the previous one
    class SeqBrain:
        def __init__(self):
            self.last_usage = {"prompt_tokens": 9, "completion_tokens": 9, "total_tokens": 18}
            self.n = 0
            self.max_tokens = None
            self.system = ""

        def generate(self, prompt: str) -> str:
            self.n += 1
            if self.n == 1:
                self.last_usage = {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7}
                return "first"
            return "second"

    ledger = BudgetLedger(pricing="local")
    backend = SingleCallBackend(SeqBrain(), ledger)
    first = backend.complete("p", purpose="probe", max_output_tokens=16, system="s")
    second = backend.complete("p2", purpose="probe", max_output_tokens=16, system="s")
    third = backend.complete("p3", purpose="probe", max_output_tokens=16, system="s")
    ok = (
        first["status"] == "completed" and first["usage"]["prompt_tokens"] == 4
        and second["status"] == "usage_unknown" and second["usage"] is None
        and third["sent"] is False and third["status"] == "budget_stopped"
        and backend.generate_calls == 2
        and ledger.calls[1]["usage"] is None
    )
    _record(results, fixture="F07", command=[PY, "-c", "SingleCallBackend missing usage"], expected_exit=0, actual_exit=0 if ok else 1, expected="second call usage_unknown, old usage not reused, third call not sent", actual=f"first={first['status']} second={second['status']} second_usage={second['usage']} third_sent={third['sent']} generates={backend.generate_calls}", ok=ok)

    # F08 budget and timeout
    class TimeoutBrain:
        def __init__(self):
            self.last_usage = None
            self.max_tokens = None
            self.system = ""
            self.n = 0

        def generate(self, prompt: str) -> str:
            self.n += 1
            raise TimeoutError("model timed out")

    ledger = BudgetLedger({"max_requests": 0}, pricing="local")
    quiet = SingleCallBackend(TimeoutBrain(), ledger)
    blocked = quiet.complete("p", purpose="probe", max_output_tokens=16, system="s")
    ledger2 = BudgetLedger(pricing="local")
    brain = TimeoutBrain()
    timed = SingleCallBackend(brain, ledger2)
    hit = timed.complete("p", purpose="probe", max_output_tokens=16, system="s")
    after = timed.complete("p2", purpose="probe", max_output_tokens=16, system="s")
    ok = blocked["sent"] is False and blocked["status"] == "budget_stopped" and quiet.generate_calls == 0 and hit["status"] == "timeout" and after["sent"] is False and brain.n == 1
    _record(results, fixture="F08", command=[PY, "-c", "BudgetLedger authorize and timeout"], expected_exit=0, actual_exit=0 if ok else 1, expected="no request when the budget is already spent; timeout row kept; no resend", actual=f"blocked={blocked['status']}/{blocked['sent']} timeout={hit['status']} after_sent={after['sent']} generates={brain.n}", ok=ok)

    # F09 regression stays visible
    good = {"task_id": "T01", "arm": "A", "pass_index": 1, "status": "completed", "contract_status": "accept", "check_results": [{"status": "PASS"}], "report_integrity": "ok"}
    worse = {"task_id": "T01", "arm": "A", "pass_index": 2, "status": "completed", "contract_status": "reject", "check_results": [{"status": "FAIL"}], "report_integrity": "ok"}
    found = regressions([good, worse])
    ok = found == [{"task_id": "T01", "arm": "A"}]
    _record(results, fixture="F09", command=[PY, "-c", "metrics.regressions"], expected_exit=0, actual_exit=0 if ok else 1, expected="pass 1 PASS and pass 2 FAIL is a regression, not only the final", actual=json.dumps(found, ensure_ascii=False), ok=ok)

    # F10 gate-off prompt has no checker lines; both arms are still scored offline by the same function
    f10_profiles = profiles
    allowed = {case["case_id"] for case in bank["calibration"]["cases"]}
    off = revision_prompt(task, f10_profiles, "SUMMARY", memo, arm="A", check_lines=["plan_matches_pinned_task: FAIL — total"], allowed_ids=allowed)
    on = revision_prompt(task, f10_profiles, "SUMMARY", memo, arm="C", check_lines=["plan_matches_pinned_task: FAIL — total"], allowed_ids=allowed)
    ok = (
        off["gate"] == "off" and off["feedback"] == GATE_OFF_FEEDBACK and "plan_matches_pinned_task" not in off["user"]
        and on["gate"] == "on" and "plan_matches_pinned_task: FAIL" in on["user"]
        and off["prompt_hash"] != on["prompt_hash"]
    )
    _record(results, fixture="F10", command=[PY, "-c", "revision_prompt gate off versus gate on"], expected_exit=0, actual_exit=0 if ok else 1, expected="gate-off prompt uses the fixed sentence; gate-on includes the checker line", actual=f"off_has_fixed={GATE_OFF_FEEDBACK in off['user']} off_leaked={'FAIL' in off['feedback']} on_has_line={'plan_matches_pinned_task' in on['user']}", ok=ok)

    # F11 denominator
    rows = []
    for index, task_id in enumerate(["T01", "T02", "T03", "T04", "T05", "T06"]):
        for arm in ("A", "B", "C", "D"):
            for pass_index in (1, 2):
                status = "parse_failed" if task_id == "T06" and arm == "A" and pass_index == 2 else "completed"
                rows.append({
                    "task_id": task_id, "arm": arm, "pass_index": pass_index, "status": status,
                    "call_id": f"c{index}{arm}{pass_index}", "shared_first_draft_group": f"{task_id}:{ARM_REPRESENTATION[arm]}" if pass_index == 1 else None,
                    "contract_status": None, "check_results": [], "usage": None, "cost_usd": None,
                    "blind_id": None, "representation": ARM_REPRESENTATION[arm],
                })
    metrics = stage2_metrics(rows, [], [])
    ok = (
        metrics["planned_arm_pass_rows"] == 48
        and metrics["observed_rows"] == 48
        and metrics["per_arm_final"]["A"]["final_denominator"] == 6
        and metrics["per_arm_final"]["A"]["adopt_as_is"] is None
        and "T06" in metrics["per_arm_final"]["A"]["missing_reviews"]
        and any(item.endswith(":A:p2") for item in metrics["failed_rows_kept"])
    )
    _record(results, fixture="F11", command=[PY, "-c", "stage2_metrics incomplete reviews"], expected_exit=0, actual_exit=0 if ok else 1, expected="denominator stays 6 and 48; missing reviews and failed cells are listed, not dropped", actual=f"rows={metrics['observed_rows']} denom={metrics['per_arm_final']['A']['final_denominator']} adopt={metrics['per_arm_final']['A']['adopt_as_is']} missing={metrics['per_arm_final']['A']['missing_reviews']} failed={metrics['failed_rows_kept']}", ok=ok)

    # F12 shared drafts
    if config is not None and screen_out is not None:
        from .backend import FixtureBackend as FB
        tasks = {item["task_id"]: item for item in bank["tasks"]["tasks"]}
        ledger = BudgetLedger(pricing="unset")
        fit = FB(handler=structural_handler(tasks), ledger=ledger)
        summary = execute_screen(config, fit, screen_out, profiles, fixture_plumbing=True, resume=False)
        blind = export_blind(screen_out, screen_out / "blind", seed=int(config.get("seed") or 0))
        produced = summary["metrics"]
        arm_rows = [json.loads(line) for line in (screen_out / "arm_pass_rows.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        calls = [json.loads(line) for line in (screen_out / "calls.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        shared = {}
        for row in arm_rows:
            if row["pass_index"] == 1:
                shared.setdefault(row["shared_first_draft_group"], set()).add(row["call_id"])
        summary_groups = [key for key in shared if key.endswith(":SUMMARY")]
        structured_groups = [key for key in shared if key.endswith(":STRUCTURED")]
        ok = (
            produced["observed_rows"] == 48
            and produced["independent_requests"] == 36
            and len(calls) == 36
            and all(len(ids) == 1 for ids in shared.values())
            and len(summary_groups) == 6
            and len(structured_groups) == 6
            and blind["row_identities"] == 48
            and blind["display_items"] <= 48
            and all(row["human_acceptance"] is None for row in arm_rows)
        )
        _record(results, fixture="F12", command=[PY, "-m", "vacant_network.personal", "fixture-run"], expected_exit=0, actual_exit=0 if ok else 1, expected="36 unique calls, 48 row identities, 6 first drafts per representation, blind bundle may dedupe", actual=f"rows={produced['observed_rows']} calls={produced['independent_requests']} summary_drafts={len(summary_groups)} structured_drafts={len(structured_groups)} blind_display={blind['display_items']} blind_rows={blind['row_identities']}", ok=ok)
    return results


def _plumbing_profiles(bank: dict[str, Any]) -> dict[str, Any]:
    """記憶體內的管線答案。不是本人偏好，不寫進題庫。"""
    from .dataset import join_answers
    answers = []
    for case in bank["calibration"]["cases"]:
        answers.append({
            "schema_version": "vacant.personal.answer.v1",
            "user_id": "fixture-not-a-person",
            "case_id": case["case_id"],
            "choice": "A",
            "reason": "管線用，不是本人回答。",
            "switch_condition": "",
            "seconds_spent": 1,
            "presented_order": ["option_1", "option_2"],
            "answered_at": "2026-11-10T00:00:00Z",
        })
    joined = join_answers({case["case_id"]: case for case in bank["calibration"]["cases"]}, answers)
    return build_all(joined, updated_at="2026-11-10T00:00:00Z", user_id="fixture-not-a-person", profile_version="fixture")


def render_report(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Fixture report — personal preference pilot v0.1",
        "",
        "這些是工程邊界，不是本人偏好，也不是模型試驗。P5 沒有跑。",
        "F01–F05b 的 exit code 是 `python -m vacant_network check` 這個行程的退出碼。",
        "F05c 之後的檢查沒有對應的 intake 退出碼；actual_exit 0 表示觀察與預期一致，1 表示這條夾具沒有對上。",
        "",
        "| Fixture | Exit expected | Exit actual | OK | Command | Expected | Actual |",
        "|---|---:|---:|---|---|---|---|",
    ]
    for row in results:
        lines.append(
            "| {fixture} | {expected_exit} | {actual_exit} | {ok} | `{command}` | {expected} | {actual} |".format(
                fixture=row["fixture"],
                expected_exit=row["expected_exit"],
                actual_exit=row["actual_exit"],
                ok="yes" if row["ok"] else "NO",
                command=row["command"].replace("|", "\\|"),
                expected=row["expected"].replace("|", "\\|"),
                actual=str(row["actual"]).replace("|", "\\|").replace("\n", " "),
            )
        )
    failed = [row["fixture"] for row in results if not row["ok"]]
    lines.extend(["", f"Failed: {failed or 'none'}", ""])
    return "\n".join(lines)
