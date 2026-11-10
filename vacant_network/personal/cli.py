"""個人試驗的命令列。§12.1 列出的命令都在這裡。

只有 build-profiles、predict、generate，以及標成 §14 步驟 2 的
compat-check，會依設定呼叫模型。其餘命令不連網。
真人答案不在倉庫裡；缺了就停，不補造。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .backend import FixtureBackend, SingleCallBackend, brain_from_config
from .budget import BudgetLedger
from .dataset import (
    assert_banks_separated,
    join_answers,
    load_answers,
    load_bank,
)
from .fixtures import render_report, run_boundary
from .metrics import score_predictions, stage1_screen
from .profiles import build_all
from .prompts import TEMPLATES
from .runner import (
    RunnerError,
    execute_predictions,
    execute_screen,
    export_blind,
    freeze_manifest,
    git_head,
    load_banks,
    load_config,
    prediction_plan,
    structural_handler,
    write_result,
)
from . import BASE_COMMIT


def _config(path: str) -> dict[str, Any]:
    return load_config(Path(path))


def _banks_ok(config: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    banks = load_banks(config)
    problems = assert_banks_separated(banks["calibration"], banks["holdout"], banks["tasks"])
    return banks, problems


def cmd_validate_data(args) -> int:
    config = _config(args.config)
    banks, problems = _banks_ok(config)
    from .dataset import legal_subsets
    counts = {task["task_id"]: len(legal_subsets(task)) for task in banks["tasks"]["tasks"]}
    documented = banks["tasks"].get("documented_legal_subset_counts") or {}
    report = {
        "ok": not problems and counts == documented,
        "base_commit": BASE_COMMIT,
        "runner_commit": git_head(),
        "calibration_cases": len(banks["calibration"]["cases"]),
        "holdout_cases": len(banks["holdout"]["cases"]),
        "tasks": len(banks["tasks"]["tasks"]),
        "legal_subset_counts": counts,
        "documented_legal_subset_counts": documented,
        "problems": problems,
        "human_answers_in_repo": False,
        "labels_path_read": False,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 2


def cmd_fixture_run(args) -> int:
    config = _config(args.config)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results = run_boundary(out / "work", screen_out=out / "examples" / "screen", config=config)
    report = render_report(results)
    (out / "fixture_report.md").write_text(report, encoding="utf-8")
    screen = out / "examples" / "screen"
    examples = out / "examples"
    examples.mkdir(parents=True, exist_ok=True)
    for name in ("calls.jsonl", "arm_pass_rows.jsonl"):
        source = screen / name
        if source.is_file():
            (examples / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    print(report)
    return 0 if all(row["ok"] for row in results) else 1


def cmd_build_profiles(args) -> int:
    config = _config(args.config)
    if not args.answers:
        print("calibration answers are required; a blank form is not an answer file", file=sys.stderr)
        return 2
    banks, problems = _banks_ok(config)
    if problems:
        print("; ".join(problems), file=sys.stderr)
        return 2
    answers = load_answers(Path(args.answers))
    joined = join_answers({case["case_id"]: case for case in banks["calibration"]["cases"]}, answers)
    out = Path(args.out or (config.get("private_pilot_root") or ""))
    if not str(out):
        print("pass --out or set private_pilot_root", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    if config.get("backend", "fixture") == "fixture":
        built = build_all(joined, updated_at=args.updated_at, user_id=config.get("user_id") or "pilot-owner", profile_version=args.profile_version)
        for name, filename in (("RAW", "raw.json"), ("SUMMARY", "summary.json"), ("STRUCTURED", "structured.json")):
            (out / filename).write_text(json.dumps(built[name], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"model_calls": 0, "builder": "deterministic_transcript", "out": str(out)}, ensure_ascii=False))
        return 0
    if config.get("backend") != "openai":
        print("backend must be fixture or openai", file=sys.stderr)
        return 2
    return _build_with_model(config, joined, out, args)


def _build_with_model(config, joined, out: Path, args) -> int:
    """SUMMARY 與 STRUCTURED 各一次。格式不對再修一次，然後停。不讀保留題。"""
    from .prompts import SUMMARY_BUILD, STRUCTURED_BUILD, SYSTEM
    model = config.get("model") or {}
    if model.get("pricing") not in ("local", "rated"):
        print("pricing must be local or rated before a model call", file=sys.stderr)
        return 2
    ledger = BudgetLedger(config.get("budget"), pricing=model["pricing"], rates=model)
    backend = SingleCallBackend(brain_from_config(model), ledger)
    blob = json.dumps(joined, ensure_ascii=False)
    summary_prompt = SUMMARY_BUILD.format(calibration_cases_joined_with_answers=blob)
    structured_prompt = STRUCTURED_BUILD.format(calibration_cases_joined_with_answers=blob)
    cap = int((config.get("budget") or {}).get("profile_output_tokens") or 2200)
    calls = 0
    for purpose, prompt, filename in (
        ("profile-summary", summary_prompt, "summary_raw_model.txt"),
        ("profile-structured", structured_prompt, "structured_raw_model.txt"),
    ):
        result = backend.complete(prompt, purpose=purpose, max_output_tokens=cap, system=SYSTEM)
        calls += 1 if result.get("sent") else 0
        (out / filename).write_text(result.get("content") or "", encoding="utf-8")
        if result.get("status") != "completed":
            print(json.dumps({"profile_build_failed": True, "status": result.get("status"), "calls": calls}, ensure_ascii=False))
            return 1
        try:
            json.loads(result["content"])
        except json.JSONDecodeError as exc:
            repair = backend.complete(
                prompt + "\n\n先前的輸出不是 JSON：" + str(exc) + "\n只重送一個 JSON object。",
                purpose="profile-repair", max_output_tokens=cap, system=SYSTEM,
            )
            calls += 1 if repair.get("sent") else 0
            (out / (filename + ".repair")).write_text(repair.get("content") or "", encoding="utf-8")
            print(json.dumps({"profile_build_failed": repair.get("status") != "completed", "calls": calls, "note": "one format repair then stop"}, ensure_ascii=False))
            return 0 if repair.get("status") == "completed" else 1
    print(json.dumps({"model_calls": calls, "out": str(out), "note": "raw model text saved; deterministic builder was not used"}, ensure_ascii=False))
    return 0


def cmd_freeze(args) -> int:
    config = _config(args.config)
    try:
        manifest = freeze_manifest(config, Path(args.out), profiles_dir=Path(args.profiles), answers_path=Path(args.answers))
    except (RunnerError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"froze": args.out, "p5_executed": manifest["p5_executed"]}, ensure_ascii=False))
    return 0


def _load_frozen_profiles(args, config) -> dict[str, Any]:
    manifest = json.loads(Path(args.freeze).read_text(encoding="utf-8"))
    profiles = {}
    for name, filename in (("RAW", "raw.json"), ("SUMMARY", "summary.json"), ("STRUCTURED", "structured.json")):
        path = Path(args.profiles) / filename
        profiles[name] = json.loads(path.read_text(encoding="utf-8"))
        import hashlib
        digest = hashlib.sha256(json.dumps(profiles[name], ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        if digest != manifest["profile_sha256"][name]:
            raise RunnerError(f"{name} profile hash does not match the freeze; no model call was sent")
    return profiles


def _backend(config):
    kind = config.get("backend", "fixture")
    model = config.get("model") or {}
    if kind == "fixture":
        return FixtureBackend(), "fixture"
    if kind != "openai":
        raise RunnerError("backend must be fixture or openai")
    if model.get("pricing") not in ("local", "rated"):
        raise RunnerError("pricing must be local or rated before a model call")
    ledger = BudgetLedger(config.get("budget"), pricing=model["pricing"], rates=model)
    return SingleCallBackend(brain_from_config(model), ledger), "openai"


def cmd_predict(args) -> int:
    config = _config(args.config) if args.config else None
    if config is None:
        print("--config is required", file=sys.stderr)
        return 2
    config["answers"] = args.answers
    try:
        profiles = _load_frozen_profiles(args, config)
        backend, kind = _backend(config)
        if kind == "fixture":
            banks = load_banks(config)
            # 沒有模型時不填預測。結構見證只用於產物管線，不能冒充保留題選擇。
            print("fixture backend does not invent holdout predictions; use backend=openai after a freeze", file=sys.stderr)
            plan = prediction_plan(banks["holdout"]["cases"])
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            (out / "prediction_plan.json").write_text(json.dumps({"cells": len(plan), "status": "planned", "predictions_filled": False}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"planned_cells": len(plan), "sent": 0}, ensure_ascii=False))
            return 0
        summary = execute_predictions(config, backend, Path(args.out), profiles)
    except (RunnerError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False))
    return 0


def cmd_score(args) -> int:
    config = _config(args.config) if args.config else None
    bank_dir = Path(config["bank_dir"]) if config else None
    if args.bank:
        bank_dir = Path(args.bank)
    if bank_dir is None:
        print("pass --config or --bank", file=sys.stderr)
        return 2
    holdout = load_bank(bank_dir / "holdout.json", kind="holdout")
    predictions = [json.loads(line) for line in Path(args.run_dir, "predictions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    labels = load_answers(Path(args.labels))
    cases = {case["case_id"]: case for case in holdout["cases"]}
    scored = score_predictions(predictions, labels, cases)
    screen = stage1_screen(scored, complete_main_cells=len(predictions) >= 48, usage_unknown=sum(1 for row in predictions if row.get("status") == "usage_unknown"))
    payload = {"scored": scored, "screen": screen, "note": "screen is exploratory; F3 is separate"}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


def cmd_generate(args) -> int:
    if args.batch != "screen":
        print("T07–T12 need a separately recorded extension budget. Refusing to run them in this batch.", file=sys.stderr)
        return 2
    config = _config(args.config) if args.config else None
    if config is None:
        print("--config is required", file=sys.stderr)
        return 2
    if config.get("extension_budget_authorized") and args.batch != "screen":
        print("extension flag does not apply to an unnamed batch", file=sys.stderr)
        return 2
    try:
        profiles = _load_frozen_profiles(args, config)
        backend, kind = _backend(config)
        if kind == "fixture":
            banks = load_banks(config)
            tasks = {item["task_id"]: item for item in banks["tasks"]["tasks"]}
            ledger_backend = FixtureBackend(handler=structural_handler(tasks), ledger=BudgetLedger(pricing="unset"))
            summary = execute_screen(config, ledger_backend, Path(args.out), profiles, fixture_plumbing=True)
        else:
            summary = execute_screen(config, backend, Path(args.out), profiles, fixture_plumbing=False)
    except (RunnerError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"rows": summary["rows"], "calls": summary["calls"], "fixture_plumbing": summary["fixture_plumbing"], "human_acceptance": None}, ensure_ascii=False))
    return 0


def cmd_export_blind(args) -> int:
    try:
        result = export_blind(Path(args.run_dir), Path(args.out or (Path(args.run_dir) / "blind")), seed=args.seed)
    except (RunnerError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


def cmd_report(args) -> int:
    out = Path(args.out or (Path(args.run_dir) / "result.md"))
    payload = write_result(Path(args.run_dir), out, Path(args.reviews) if args.reviews else None)
    print(json.dumps({"decision": payload["decision"], "out": str(out)}, ensure_ascii=False))
    return 0


def cmd_compat(args) -> int:
    from .endpoint_smoke import main as smoke_main
    argv = ["--config", args.config]
    if args.out:
        argv.extend(["--out", args.out])
    if args.dry_run:
        argv.append("--dry-run")
    return smoke_main(argv)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m vacant_network.personal")
    sub = parser.add_subparsers(dest="cmd", required=True)

    validate = sub.add_parser("validate-data", help="check the synthetic banks; does not call a model")
    validate.add_argument("--config", required=True)
    validate.add_argument("--out")
    validate.set_defaults(func=cmd_validate_data)

    fixture = sub.add_parser("fixture-run", help="run F01–F12 offline and write fixture_report.md")
    fixture.add_argument("--config", required=True)
    fixture.add_argument("--out", required=True)
    fixture.set_defaults(func=cmd_fixture_run)

    build = sub.add_parser("build-profiles", help="build RAW, SUMMARY, and STRUCTURED representations")
    build.add_argument("--config", required=True)
    build.add_argument("--answers", required=True)
    build.add_argument("--out")
    build.add_argument("--updated-at", required=True)
    build.add_argument("--profile-version", default="p001")
    build.set_defaults(func=cmd_build_profiles)

    freeze = sub.add_parser("freeze", help="write a freeze manifest; does not call a model")
    freeze.add_argument("--config", required=True)
    freeze.add_argument("--answers", required=True)
    freeze.add_argument("--profiles", required=True)
    freeze.add_argument("--out", required=True)
    freeze.set_defaults(func=cmd_freeze)

    predict = sub.add_parser("predict", help="stage-1 predictions; openai backend calls the model")
    predict.add_argument("--config", required=True)
    predict.add_argument("--freeze", required=True)
    predict.add_argument("--profiles", required=True)
    predict.add_argument("--answers", required=True)
    predict.add_argument("--out", required=True)
    predict.set_defaults(func=cmd_predict)

    score = sub.add_parser("score-predictions", help="score sealed labels; does not call a model")
    score.add_argument("--config")
    score.add_argument("--bank")
    score.add_argument("--run-dir", required=True)
    score.add_argument("--labels", required=True)
    score.add_argument("--out")
    score.set_defaults(func=cmd_score)

    generate = sub.add_parser("generate", help="stage-2 screen batch; extension batch is refused")
    generate.add_argument("--config", required=True)
    generate.add_argument("--freeze", required=True)
    generate.add_argument("--profiles", required=True)
    generate.add_argument("--out", required=True)
    generate.add_argument("--batch", default="screen")
    generate.set_defaults(func=cmd_generate)

    blind = sub.add_parser("export-blind", help="write a blind bundle; does not call a model")
    blind.add_argument("--run-dir", required=True)
    blind.add_argument("--out")
    blind.add_argument("--seed", type=int, default=20261109)
    blind.set_defaults(func=cmd_export_blind)

    report = sub.add_parser("report", help="write result.md; does not call a model")
    report.add_argument("--run-dir", required=True)
    report.add_argument("--reviews")
    report.add_argument("--out")
    report.set_defaults(func=cmd_report)

    compat = sub.add_parser("compat-check", help="§14 Step 2 compatibility pre-check; one request unless --dry-run")
    compat.add_argument("--config", required=True)
    compat.add_argument("--out")
    compat.add_argument("--dry-run", action="store_true")
    compat.set_defaults(func=cmd_compat)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BrokenPipeError:
        return 0


# 讓靜態檢查看得到模板被這個套件帶著走。
_ = TEMPLATES
