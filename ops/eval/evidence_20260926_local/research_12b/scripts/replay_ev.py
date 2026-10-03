import json, sys, pathlib, glob
from vacant_network.trace.recorder import Recorder
from vacant_network.trace.evidence import evidence_for
for trial in sys.argv[1:]:
    root = pathlib.Path(trial) / "agent" / "vacant_home" / "trace"
    rec = Recorder("/app", root=root)
    if not rec.chain_path.is_file():
        print(trial, "no chain at", rec.dir); continue
    evs = rec.events()
    sid = next((e.get("session") for e in evs if e.get("type") == "prompt" and e.get("source") == "user"), None)
    res = evidence_for(rec, platform="pi", session=sid)
    ended = [e for e in evs if e.get("type") in ("ended", "nudge", "review")]
    print("==", pathlib.Path(trial).parent.name)
    print("  deliverables:", res.get("deliverables"), "values:", {k: v for k, v in (res.get("values") or {}).items() if not isinstance(v, list)})
    print("  findings:", [(f["kind"], f.get("path"), f.get("value")) for f in res.get("findings") or []])
    print("  not_traced_note_only:", (res.get("values") or {}).get("not_traced_note_only"))
    print("  events:", [(e["type"], e.get("turn"), e.get("action")) for e in ended])
