#!/usr/bin/env python3
"""analyze.py — re-runnable analysis of `vacant run` live batches (ops/realrun).

P1 line "drive resample/feedback with real signals, not the scorer": this script
nails down what a live batch actually shows, from the on-disk evidence only:

  1. REAL-SIGNAL INVARIANTS, per run (falsifiable, checked from artifacts):
     I1 vocabulary   every stop_reason is in {visible_pass, visible_fail,
                     attempts_exhausted} — there is no hidden-suite signal in
                     the decision vocabulary at all.
     I2 no artifacts no file under the run dir, and no suite path, contains a
                     hidden-suite artifact.
     I3 mediation    requests_seen >= 1 — the model channel was actually
                     mediated (the wire log exists).
     I4 chain        the run's receipt chain verifies with vacant_network's own
                     Logbook.verify_chain and the run's public key.
     I5 resample-on-visible-fail-only (resample arms): the attempt sequence is
                     a prefix of visible_fail, then visible_pass or
                     attempts_exhausted. A resample was therefore triggered by
                     a visible-suite failure, never by anything else.
     I6 consistency  summary.accepted iff the final stop_reason is visible_pass.

  2. FAILURE-MODE SPLIT, per attempt, from evidence:
     ws_sha256 (receipts) == ws_start_sha256 (summary)  ->  no_model_content
       (the agent never wrote the file — e.g. the model spent its budget on
       reasoning and returned empty content)
     ws_sha256 != ws_start_sha256                        ->  code_written
       (the agent delivered code; the visible suite rejected it)
     These two are different measurements. "no_model_content" is an
     agent/model-config failure; "code_written" + visible_fail is the real
     signal doing its job.

  3. HONEST READOUT: accepted/total per arm WITH denominators. n is small by
     construction (a smoke, not a measurement): no effect-size claim may be
     made from it (H-12 style discipline). The effect-size estimate comes from
     the offline replay on ref/c37_final.json (real-signal column, n=331).

Usage:
  python3 ops/realrun/analyze.py [--root runs] [--json]
  python3 ops/realrun/analyze.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

# vacant_network is importable from the repo root (this file lives in ops/).
try:
    import vacant_network  # noqa: F401
except ImportError:  # pragma: no cover - depends on install layout
    sys.path.insert(0, str(HERE.parent.parent))

from vacant_network import crypto  # noqa: E402
from vacant_network.identity import Identity, PublicIdentity  # noqa: E402
from vacant_network.logbook import Logbook  # noqa: E402

STOP_VOCAB = {"visible_pass", "visible_fail", "attempts_exhausted"}
MODE_NO_CONTENT = "no_model_content"
MODE_CODE_WRITTEN = "code_written"


def _load_summary(run_dir: Path) -> dict | None:
    for f in sorted(run_dir.glob("run_*.json")):
        if "receipts" in f.name:
            continue
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
    return None


def _receipt_files(run_dir: Path) -> tuple[Path | None, Path | None]:
    nd = sorted(run_dir.glob("receipts_*.ndjson"))
    pub = sorted(run_dir.glob("receipts_*.pub.json"))
    return (nd[0] if nd else None, pub[0] if pub else None)


def _verify_chain(ndjson: Path, pubjson: Path) -> tuple[bool, str]:
    try:
        book = Logbook.load(ndjson)
        who = PublicIdentity.from_hex(**json.loads(pubjson.read_text(encoding="utf-8")))
        return bool(book.verify_chain(who)), f"{len(book)} entries"
    except Exception as e:  # a chain we cannot parse is a chain we cannot trust
        return False, f"error: {e!r}"


def _attempt_ws(run_dir: Path) -> list[dict]:
    """Per-attempt receipt payloads (attempt is not None), in chain order."""
    nd, _pub = _receipt_files(run_dir)
    if nd is None:
        return []
    out = []
    for line in nd.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        p = json.loads(line).get("payload", {})
        if p.get("attempt") is not None:
            out.append(p)
    return out


def analyze_run(arm: str, task: str, run_dir: Path) -> dict:
    summary = _load_summary(run_dir) or {}
    attempts = summary.get("attempts") or []
    ws_start = summary.get("ws_start_sha256")

    stops = [a.get("stop_reason") for a in attempts] + [summary.get("stop_reason")]
    i1 = all(s in STOP_VOCAB for s in stops if s is not None)

    bad_names = [p.name for p in run_dir.rglob("*") if "hidden" in p.name.lower()]
    suite_path = str((summary.get("suite") or {}).get("path") or "")
    i2 = not bad_names and "hidden" not in suite_path.lower()

    reqs = sum(a.get("requests_seen") or 0 for a in attempts)
    i3 = reqs >= 1

    nd, pub = _receipt_files(run_dir)
    if nd is not None and pub is not None:
        i4, i4_detail = _verify_chain(nd, pub)
    else:
        i4, i4_detail = False, "no receipt files"

    # I5: the attempt sequence is a prefix of visible_fail, then the terminal.
    i5 = True
    seen_terminal = False
    for s in [a.get("stop_reason") for a in attempts]:
        if s in ("visible_pass", "attempts_exhausted"):
            seen_terminal = True
        elif s == "visible_fail":
            if seen_terminal:
                i5 = False
        else:
            i5 = False
    if seen_terminal and summary.get("stop_reason") not in ("visible_pass", "attempts_exhausted"):
        i5 = False
    if summary.get("stop_reason") is None:
        i5 = False

    i6 = (summary.get("accepted") is True) == (summary.get("stop_reason") == "visible_pass")

    # failure-mode split, from ws evidence in the receipts
    modes = []
    for p in _attempt_ws(run_dir):
        w = p.get("ws_sha256")
        modes.append(MODE_NO_CONTENT if w in (None, ws_start) else MODE_CODE_WRITTEN)

    return {
        "arm": arm,
        "task": task,
        "accepted": summary.get("accepted"),
        "refused": summary.get("refused"),
        "infra_void": summary.get("infra_void"),
        "stop_reason": summary.get("stop_reason"),
        "n_attempts": len(attempts),
        "requests_seen": reqs,
        "final_mode": modes[-1] if modes else None,
        "attempt_modes": modes,
        "chain_ok": i4,
        "chain_detail": i4_detail,
        "invariants": {
            "I1_stop_vocabulary_visible_only": i1,
            "I2_no_hidden_artifacts": i2,
            "I3_channel_mediated": i3,
            "I4_receipt_chain_verifies": i4,
            "I5_resample_only_on_visible_fail": i5,
            "I6_summary_consistent": i6,
        },
    }


def analyze_root(root: Path) -> dict:
    runs = []
    for arm_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for task_dir in sorted(p for p in arm_dir.iterdir() if p.is_dir()):
            run_dir = task_dir / "run"
            if run_dir.is_dir():
                runs.append(analyze_run(arm_dir.name, task_dir.name, run_dir))

    arms = {}
    for r in runs:
        a = arms.setdefault(r["arm"], {"total": 0, "accepted": 0,
                                      MODE_NO_CONTENT: 0, MODE_CODE_WRITTEN: 0})
        a["total"] += 1
        if r["accepted"] is True:
            a["accepted"] += 1
        elif r["final_mode"] in a:
            a[r["final_mode"]] += 1

    inv_keys = sorted(runs[0]["invariants"]) if runs else []
    all_inv = {k: all(r["invariants"].get(k) for r in runs) for k in inv_keys}
    return {
        "root": str(root),
        "n_runs": len(runs),
        "per_arm": arms,
        "invariants_all_runs": all_inv,
        "runs": runs,
        "readout": (
            "n is small by construction: this is a pipeline smoke, not a "
            "measurement. No effect-size claim from these numbers (H-12 style). "
            "Effect-size estimate: offline replay, real-signal column, n=331."
        ),
    }


def selftest() -> int:
    """Build a synthetic batch; assert the analyzer sees exactly what we planted.

    Includes negative controls: a tampered receipt chain must FAIL I4, and a
    foreign stop_reason ('hidden_fail') must FAIL I1 — so the guards are shown
    to catch something before they are pointed at real runs.
    """
    me = Identity.generate()
    pub = {"vacant_id": me.vacant_id, "pub_hex": crypto.pub_to_hex(me.pub)}
    ws_start = "0" * 64
    ws_code = "1" * 64

    def mk_run(base: Path, arm: str, task: str, entries: list[dict], summary: dict) -> Path:
        rd = base / arm / task / "run"
        rd.mkdir(parents=True)
        book = Logbook()
        for p in entries:
            book.append("attempt", p, me, ts_ms=int(1792000000000 + 1000 * p.get("gate_round", 1)))
        book.save(rd / "receipts_RUN-ON.ndjson")
        (rd / "receipts_RUN-ON.pub.json").write_text(json.dumps(pub), encoding="utf-8")
        (rd / "run_RUN-ON.json").write_text(json.dumps(summary), encoding="utf-8")
        return rd

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        # run1: one-shot, code written, visible pass
        s1 = {"accepted": True, "refused": False, "infra_void": None,
              "stop_reason": "visible_pass", "ws_start_sha256": ws_start,
              "requests_seen": 1, "suite": {"path": "suite/test_visible.py"},
              "attempts": [{"attempt": 1, "stop_reason": "visible_pass", "requests_seen": 1}]}
        mk_run(base, "A_none", "t_pass",
               [{"attempt": 1, "gate_round": 1, "ws_sha256": ws_code,
                 "stop_reason": "visible_pass", "requests_seen": 1}], s1)
        # run2: resample x3, two empty replies then code that fails the suite
        s2 = {"accepted": False, "refused": True, "infra_void": None,
              "stop_reason": "attempts_exhausted", "ws_start_sha256": ws_start,
              "requests_seen": 3, "suite": {"path": "suite/test_visible.py"},
              "attempts": [{"attempt": i, "stop_reason": "visible_fail", "requests_seen": 1}
                           for i in (1, 2, 3)]}
        mk_run(base, "B_resample3", "t_fail",
               [{"attempt": 1, "gate_round": 1, "ws_sha256": ws_start,
                 "stop_reason": "visible_fail", "requests_seen": 1},
                {"attempt": 2, "gate_round": 2, "ws_sha256": ws_start,
                 "stop_reason": "visible_fail", "requests_seen": 1},
                {"attempt": 3, "gate_round": 3, "ws_sha256": ws_code,
                 "stop_reason": "visible_fail", "requests_seen": 1},
                {"attempt": None, "stop_reason": "attempts_exhausted", "requests_seen": 3}], s2)
        # run3: NEGATIVE CONTROL — tamper the first entry's payload
        rd3 = mk_run(base, "B_resample3", "t_tampered",
                     [{"attempt": 1, "gate_round": 1, "ws_sha256": ws_code,
                       "stop_reason": "visible_pass", "requests_seen": 1}], s1)
        lines = rd3.joinpath("receipts_RUN-ON.ndjson").read_text(encoding="utf-8").splitlines()
        d = json.loads(lines[0])
        d["payload"]["accepted"] = False  # break the signature
        lines[0] = json.dumps(d)
        rd3.joinpath("receipts_RUN-ON.ndjson").write_text("\n".join(lines) + "\n", encoding="utf-8")
        # run4: NEGATIVE CONTROL — a hidden-suite stop_reason must be caught by I1
        mk_run(base, "A_none", "t_foreign_stop",
               [{"attempt": 1, "gate_round": 1, "ws_sha256": ws_code,
                 "stop_reason": "hidden_fail", "requests_seen": 1}],
               {"accepted": False, "refused": True, "infra_void": None,
                "stop_reason": "hidden_fail", "ws_start_sha256": ws_start,
                "requests_seen": 1, "suite": {"path": "suite/test_visible.py"},
                "attempts": [{"attempt": 1, "stop_reason": "hidden_fail", "requests_seen": 1}]})

        rep = analyze_root(base)
        by_task = {r["task"]: r for r in rep["runs"]}

        r1 = by_task["t_pass"]
        assert r1["accepted"] is True and r1["final_mode"] == MODE_CODE_WRITTEN
        assert all(r1["invariants"].values()), r1["invariants"]

        r2 = by_task["t_fail"]
        assert r2["attempt_modes"] == [MODE_NO_CONTENT, MODE_NO_CONTENT, MODE_CODE_WRITTEN]
        assert r2["final_mode"] == MODE_CODE_WRITTEN
        assert all(r2["invariants"].values()), r2["invariants"]

        r3 = by_task["t_tampered"]
        assert r3["invariants"]["I4_receipt_chain_verifies"] is False, "negative control: tamper not caught"
        assert r3["chain_ok"] is False

        r4 = by_task["t_foreign_stop"]
        assert r4["invariants"]["I1_stop_vocabulary_visible_only"] is False, \
            "negative control: foreign stop_reason not caught"

        assert rep["per_arm"]["A_none"] == {"total": 2, "accepted": 1,
                                            MODE_NO_CONTENT: 0, MODE_CODE_WRITTEN: 1}
        # t_tampered still records accepted=True in its summary (the point is
        # that I4 now fails); t_fail ended code_written after 3 visible_fail
        assert rep["per_arm"]["B_resample3"] == {"total": 2, "accepted": 1,
                                                 MODE_NO_CONTENT: 0, MODE_CODE_WRITTEN: 1}
        print("selftest: PASS (4 synthetic runs; tamper + foreign-stop negative controls caught)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(HERE / "runs"))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    rep = analyze_root(Path(a.root))
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        print(f"root: {rep['root']}  runs: {rep['n_runs']}")
        for arm, stat in rep["per_arm"].items():
            print(f"  {arm}: accepted {stat['accepted']}/{stat['total']}  "
                  f"failures: {MODE_NO_CONTENT}={stat[MODE_NO_CONTENT]} "
                  f"{MODE_CODE_WRITTEN}={stat[MODE_CODE_WRITTEN]}")
        for k, v in rep["invariants_all_runs"].items():
            print(f"  {'PASS' if v else 'FAIL'}  {k}")
        for r in rep["runs"]:
            print(f"  {r['arm']}/{r['task']}: stop={r['stop_reason']} "
                  f"attempts={r['n_attempts']} modes={r['attempt_modes']} chain_ok={r['chain_ok']}")
        print("  readout: " + rep["readout"])
    ok = all(rep["invariants_all_runs"].values()) and rep["n_runs"] > 0
    if not a.json:
        print("VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
