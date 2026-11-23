"""Assemble, validate and verify the experiment's RECORD_SPEC evidence."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from vacant_network import record

import run


def read(path):
    return json.loads(path.read_bytes())


def wire_stats(events):
    payload = b"".join(bytes.fromhex(e["hex"]) for e in events if e["kind"] == "chunk")
    out = Counter(requests=1)
    for line in payload.splitlines():
        if not line.startswith(b"data: "):
            continue
        try:
            event = json.loads(line[6:])
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("usage"):
            out.update({k: event["usage"][k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")})
            out["usage_known"] = 1
            break
    out["missing_usage"] = 1 - out["usage_known"]
    out["interrupted"] = int(events[-1]["kind"] != "eof")
    out["http_success"] = int(any(e["kind"] == "response" and e["status"] == 200 for e in events))
    return out


def archive(root, wire, replay):
    run_meta = read(root / "RUN.json")
    runtime = read(root / "runtime.json")
    if any(runtime["files"].get(str(p.relative_to(run.REPO))) !=
           run.redo.sha256_bytes(p.read_bytes()) for p in run.SCRIPTS):
        raise SystemExit("Frozen inputs differ from the runtime inventory")
    replay_audit = read(replay)
    if not replay_audit["attempts"] or replay_audit["mismatches"]:
        raise SystemExit("Offline grader replay did not match")
    events = []
    ledger = root / "ledger_events.jsonl"
    anomalies = root / "anomalies.md"
    issues = []
    summaries, request_stats = {}, defaultdict(Counter)
    report = read(root / "REPORT.json")
    for path in sorted(root.glob("cells/*/r*/*/cell.json")):
        cell = read(path)
        events.append({"kind": "CELL", "utc": cell["ended"], "file": str(path.relative_to(root)),
                       "id": cell["cell"], "pass": cell.get("pass"), "void": cell["infra_void"]})
        if cell["infra_void"]:
            issues.append(f"{cell['cell']}: {cell['infra_void']}")
        report_task = report["per_task"][cell["task"]]
        key = "paired" if report_task["pairs"] == 1 else "unpaired"
        summaries[cell["cell"]] = {"arm": cell["arm"], "pair_kind": key, "all": Counter(),
                                   "scored_attempts": Counter(), "void_attempts": Counter()}
    int_paths = sorted(root.glob("cells/*/r*/*/*/attempt.json"))
    with (root / "model_io.jsonl").open("w", encoding="utf-8") as target:
        for path in int_paths:
            attempt = read(path)
            name = str(path.parent.relative_to(root))
            cell_id = "/".join(path.relative_to(root).parts[1:4])
            events.append({"kind": "ATTEMPT_START", "utc": attempt["started"], "file": name,
                           "trace_id": attempt["trace_id"], "timeout": attempt["timed_out"],
                           "void": attempt["void"]})
            if attempt["timed_out"]:
                issues.append(f"{name}: agent timed out")
            if attempt["void"]:
                issues.append(f"{name}: {attempt['void']}")
            if not attempt["void"] and attempt["acc"]["accept"] != attempt["grade"]["pass"]:
                issues.append(f"{name}: visible and hidden verdicts differ")
            if cell_id not in summaries:
                continue
            summary = summaries[cell_id]
            arm = summary["arm"]
            group = "void_attempts" if attempt["void"] else "scored_attempts"
            traces = sorted((wire / attempt["trace_id"]).glob("*.jsonl"))
            if not traces and attempt["usage"]:
                raise SystemExit(f"Missing API trace for {name}")
            for source in traces:
                captured = [json.loads(s) for s in source.read_bytes().splitlines()]
                if not captured or captured[0]["kind"] != "request":
                    raise SystemExit(f"Incomplete request trace: {source.name}")
                for entry in captured:
                    target.write(json.dumps({"attempt": name, "request_id": source.stem, **entry}) + "\n")
                stats = wire_stats(captured)
                summary["all"].update(stats)
                summary[group].update(stats)
                request_stats[f"{summary['pair_kind']}/{arm}/{group}"].update(stats)
    ledger.write_text("".join(json.dumps(e) + "\n" for e in sorted(events, key=lambda e: e["utc"])),
                      encoding="utf-8")
    anomalies.write_text("# Anomalies\n\n" + ("\n".join(f"- {x}" for x in issues) if issues else "None.") + "\n",
                         encoding="utf-8")
    run.emit_json(root / "usage_summary.json", {
        "per_cell": summaries,
        "per_arm": request_stats,
        "note": "Requests observed at proxy, including failures. Token totals are sums only where upstream supplied usage.",
    })
    run.emit_json(root / "REPLAY.json", replay_audit)
    record.pack(root, {
        "repo_commit": run_meta["git_head"],
        "utc_start": run_meta["created"],
        "scripts": runtime["files"],
        "model_id": run.MODEL,
        "endpoint": "local llama.cpp via capture proxy",
        "seeds": [run_meta["plan"]["seed"]],
        "trust_arm": "paired A/R3",
        "no_think": True,
        "missing": {"wire.jsonl": "No MCP messages; full local model API I/O is in model_io.jsonl.",
                    "request_random_seeds": "llama.cpp sampled per request, request templates do not transmit explicit seeds."},
    })
    ok, problems = record.check(root)
    if not ok:
        raise SystemExit("\n".join(problems))
    print(f"RECORD_SPEC OK: {len(int_paths)} archived attempt records")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--wire", required=True, type=Path)
    parser.add_argument("--replay", required=True, type=Path)
    args = parser.parse_args()
    archive(args.root, args.wire, args.replay)
