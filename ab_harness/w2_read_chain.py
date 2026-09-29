#!/usr/bin/env python3
"""Read the trace chain and the delivery note from the opencode run that fired a
stop event, and report what the record says.

This reads Vacant's own signed record rather than anything the test harness
observed, so the claim does not depend on the harness plumbing being right.
"""
import json
import pathlib
import sys

PROJ = pathlib.Path("/home/user1/.vacant/trace/projects")


def main() -> int:
    best = None
    for d in sorted(PROJ.iterdir()):
        chain = d / "chain.ndjson"
        perf = d / "perf.jsonl"
        if not chain.exists() or not perf.exists():
            continue
        try:
            events = [json.loads(l) for l in
                      chain.read_text(errors="replace").splitlines() if l.strip()]
        except Exception:
            continue
        kinds = [e.get("type") for e in events]
        # the run we care about: a stop check that actually pushed back
        if "stop" in kinds or any(e.get("type") == "finding" for e in events):
            if best is None or len(kinds) > len(best[1]):
                best = (d, events)
    if best is None:
        print("no chain with a stop/finding event found under", PROJ)
        return 1
    d, events = best
    print("project:", d.name)
    print()
    print("--- chain event types ---")
    import collections
    print(" ", dict(collections.Counter(e.get("type") for e in events)))
    print()
    print("--- the non-step events, in order ---")
    for e in events:
        t = e.get("type")
        if t in ("step", "trace_genesis"):
            continue
        payload = {k: v for k, v in e.items() if k not in ("schema", "signature")}
        s = json.dumps(payload, ensure_ascii=False)
        print(f"  [{t}] {s[:700]}")
    print()
    for name in ("delivery.md", "delivery.json"):
        f = d / name
        if f.exists():
            print(f"--- {name} ---")
            print(f.read_text(errors="replace")[:1500])
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
