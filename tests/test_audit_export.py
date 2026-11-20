"""Synthetic fixture tests for `vacant_network/audit_export.py` and `vacant audit`.

Zero model calls, zero network, fully isolated temporary directories.
Covers all five sources (`trace`, `intake_ledger`, `vrun`, `restart`, `possess_wire`),
signature verification, edited chains, truncated chains (mid-line torn, head mismatch,
ledger-anchored, and vrun verdict-missing), missing/corrupt fields (strictly `None` /
`"unknown"` / `"unreadable"`, never `0` or `False`), all CLI filters, JSONL export,
read-only guarantee, wording boundaries, and legacy `vacant --root ... audit <name>`.
"""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

import pytest

from vacant_network import audit_export as AE
from vacant_network.cli import main as cli_main
from vacant_network.crypto import pub_to_hex
from vacant_network.identity import Identity
from vacant_network.intake import keys as intake_keys
from vacant_network.intake.ledger import Ledger
from vacant_network.logbook import Logbook
from vacant_network.trace.recorder import TRACE_SCHEMA, project_key
from vacant_network.vrun import receipts as vrun_receipts


# ── Synthetic Fixture Builders (0 model calls) ────────────────────────────────

def _init_trust(vacant_home: pathlib.Path) -> tuple[Identity, intake_keys.Trust]:
    intake_root = vacant_home / "intake"
    intake_root.mkdir(parents=True, exist_ok=True)
    ident = Identity.generate()
    ident.save(intake_root / "keys" / "verifier")
    trust = intake_keys.Trust(intake_root / "trust.json", {})
    trust.add("verifier", "local", pub_to_hex(ident.pub))
    trust.save()
    return ident, trust


def _make_trace_project(
    vacant_home: pathlib.Path,
    ident: Identity,
    workspace: pathlib.Path,
    *,
    platform: str = "pi",
    ts_base: int = 1_760_000_000_000,
    with_review_sent_back: bool = True,
    final_allow: bool = True,
    with_gap: bool = True,
    with_post_missing: bool = False,
    with_open_flag: bool = False,
    scan_disabled: str | None = None,
) -> tuple[str, pathlib.Path, Logbook]:
    workspace.mkdir(parents=True, exist_ok=True)
    pkey = project_key(workspace)
    pdir = vacant_home / "trace" / "projects" / pkey
    pdir.mkdir(parents=True, exist_ok=True)
    book = Logbook()
    book.append(
        "trace_genesis",
        {"schema": TRACE_SCHEMA, "workspace": str(workspace), "signer": pub_to_hex(ident.pub)},
        ident,
        ts_ms=ts_base,
    )
    book.append(
        "session_seen",
        {"schema": TRACE_SCHEMA, "actor": {"platform": platform, "session": "s1"}},
        ident,
        ts_ms=ts_base + 1000,
    )
    step_payload: dict[str, Any] = {
        "schema": TRACE_SCHEMA,
        "step": "st1",
        "n": 1,
        "actor": {"platform": platform, "session": "s1"},
        "tool": "edit",
        "writes": [{"kind": "modified", "path": "app.py"}],
        "observed_by": "agent_hook",
    }
    if with_post_missing:
        step_payload["post_missing"] = "turn_end"
    book.append("step", step_payload, ident, ts_ms=ts_base + 2000)

    if with_gap:
        book.append(
            "unrecorded_change",
            {
                "schema": TRACE_SCHEMA,
                "changes": [{"kind": "modified", "path": "notes.txt"}],
                "n": 1,
                "observed_at": "pre_tool",
            },
            ident,
            ts_ms=ts_base + 2500,
        )
    if with_open_flag:
        book.append(
            "flag",
            {"schema": TRACE_SCHEMA, "flag_id": "h_abc123", "note": "wrong value"},
            ident,
            ts_ms=ts_base + 2600,
        )
    if with_review_sent_back:
        book.append(
            "review",
            {
                "schema": TRACE_SCHEMA,
                "mode": "evidence",
                "session": f"{platform}:s1",
                "action": "continue",
                "round": 1,
                "findings": [{"finding_id": "f1", "kind": "unverified_claim"}],
                "sent": ["f1"],
            },
            ident,
            ts_ms=ts_base + 3000,
        )
    if final_allow:
        book.append(
            "review",
            {
                "schema": TRACE_SCHEMA,
                "mode": "evidence",
                "session": f"{platform}:s1",
                "action": "allow",
                "rounds_used": 1 if with_review_sent_back else 0,
                "findings": [],
                "left_open": [],
            },
            ident,
            ts_ms=ts_base + 4000,
        )

    chain_p = pdir / "chain.ndjson"
    book.save(chain_p)
    last = book.entries[-1]
    (pdir / "head.json").write_text(
        json.dumps({"seq": last.seq, "hash": last.hash()}), encoding="utf-8"
    )
    state: dict[str, Any] = {
        "workspace": str(workspace),
        "n_steps": 1,
        "sessions": {f"{platform}:s1": {"closed": True}},
    }
    if scan_disabled:
        state["scan_disabled"] = scan_disabled
    (pdir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return pkey, pdir, book


def _make_intake_ledger(
    vacant_home: pathlib.Path,
    ident: Identity,
    task_id: str,
    project: pathlib.Path,
    *,
    agent: str = "claude",
    ts_base: int = 1_760_100_000_000,
    outcome: str = "accept",
    include_reject_first: bool = True,
    released: bool = False,
    workspace_escape: bool = False,
    trace_anchor: tuple[str, int, str] | None = None,
) -> pathlib.Path:
    intake_root = vacant_home / "intake"
    ldir = intake_root / "ledger"
    ldir.mkdir(parents=True, exist_ok=True)
    book = Logbook()
    book.append(
        "ledger_genesis",
        {"schema": "vacant-ledger/1", "task_id": task_id, "signer": pub_to_hex(ident.pub)},
        ident,
        ts_ms=ts_base,
    )
    book.append(
        "task_opened",
        {
            "schema": "vacant-ledger/1",
            "task_id": task_id,
            "contract_sha256": "c" * 64,
            "contract_path": str(project / ".vacant" / "contract.json"),
        },
        ident,
        ts_ms=ts_base + 100,
    )
    book.append(
        "attempt_started",
        {"schema": "vacant-ledger/1", "task_id": task_id, "attempt": 1, "agent": agent, "workspace": str(project)},
        ident,
        ts_ms=ts_base + 200,
    )
    book.append(
        "attempt_ended",
        {
            "schema": "vacant-ledger/1",
            "task_id": task_id,
            "attempt": 1,
            "rc": 0,
            "workspace_escape": workspace_escape,
        },
        ident,
        ts_ms=ts_base + 300,
    )
    if include_reject_first:
        book.append(
            "decision",
            {
                "schema": "vacant-ledger/1",
                "task_id": task_id,
                "contract_sha256": "c" * 64,
                "artifact_sha256": "a" * 64,
                "outcome": "reject",
                "reasons": ["claim tests failed"],
                "results": [
                    {"id": "tests", "status": "FAIL"},
                    {"id": "lint", "status": "PASS"},
                ],
            },
            ident,
            ts_ms=ts_base + 400,
        )
        book.append(
            "attempt_started",
            {"schema": "vacant-ledger/1", "task_id": task_id, "attempt": 2, "agent": agent, "workspace": str(project)},
            ident,
            ts_ms=ts_base + 500,
        )
    book.append(
        "decision",
        {
            "schema": "vacant-ledger/1",
            "task_id": task_id,
            "contract_sha256": "c" * 64,
            "artifact_sha256": "b" * 64,
            "outcome": outcome,
            "reasons": [] if outcome == "accept" else [f"outcome is {outcome}"],
            "results": [
                {"id": "tests", "status": "PASS" if outcome == "accept" else "FAIL"},
                {"id": "lint", "status": "PASS"},
            ],
        },
        ident,
        ts_ms=ts_base + 600,
    )
    if released:
        book.append(
            "released",
            {
                "schema": "vacant-ledger/1",
                "task_id": task_id,
                "contract_sha256": "c" * 64,
                "artifact_sha256": "b" * 64,
                "destination": "dir:published",
                "readback_ok": True,
            },
            ident,
            ts_ms=ts_base + 700,
        )
    if trace_anchor is not None:
        pk, aseq, ahash = trace_anchor
        book.append(
            "trace_head",
            {"schema": "vacant-ledger/1", "task_id": task_id, "project": pk, "seq": aseq, "hash": ahash},
            ident,
            ts_ms=ts_base + 800,
        )
    out = ldir / f"{task_id}.ndjson"
    book.save(out)
    return out


def _make_vrun_dir(
    vrun_root: pathlib.Path,
    run_name: str,
    *,
    task_id: str = "vr_task_1",
    arm: str = "RUN-ON",
    agent: str = "codex",
    workspace: pathlib.Path | None = None,
    accepted: bool | None = True,
    stop_reason: str = "visible_pass",
    requests_seen: int | None = 4,
    tier: str | None = "A",
    attempts_used: int = 2,
    max_attempts: int = 3,
    ts_base: int = 1_760_200_000_000,
    infra_void: str | None = None,
) -> pathlib.Path:
    run_dir = vrun_root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    ws = str(workspace or (vrun_root / "ws_vrun"))

    att_doc: dict[str, Any] | None = None
    att_sha: str | None = None
    if tier is not None:
        att_doc = {
            "schema": "vacant-attest/1",
            "run_id": task_id,
            "agent": agent,
            "tier": tier,
            "attested": tier == "A",
            "enclosure": {"applied": tier in ("A", "B")},
            "framework_hook": {"agent": agent, "canary_fired": tier in ("A", "B'")},
            "reconciled": {"relay_calls": requests_seen, "hook_events": requests_seen, "unexplained": 0 if tier == "A" else 1},
            "assembled_at": ts_base / 1000.0,
        }
        att_sha = hashlib.sha256(
            json.dumps(att_doc, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    attempts_list = [
        {"attempt": i, "feedback_delivery": "prompt" if i > 1 else None, "failures": "assert 1==2" if i == 1 else ""}
        for i in range(1, attempts_used + 1)
    ]
    summary: dict[str, Any] = {
        "task_id": task_id,
        "arm": arm,
        "vacant": 1,
        "workspace": ws,
        "accepted": accepted,
        "refused": (accepted is False),
        "stop_reason": stop_reason,
        "infra_void": infra_void,
        "visible_passed": 3 if accepted is True else (1 if accepted is False else None),
        "visible_total": 3 if accepted is not None else None,
        "requests_seen": requests_seen,
        "retry": "revise" if max_attempts > 1 else "none",
        "max_attempts": max_attempts,
        "attempts_used": attempts_used,
        "attempts": attempts_list,
        "feedback_into": "prompt",
        "attestation": att_doc,
        "failures": "" if accepted is True else "AssertionError: mismatch",
        "model_wire": {"wire_quiesced": True, "count_semantics": "exact"},
    }

    row = {"task_id": task_id, "arm": arm, "accepted": accepted, "stop_reason": stop_reason}
    (run_dir / "rows.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    if not infra_void:
        ident = Identity.generate()
        book = Logbook()
        for i in range(1, attempts_used + 1):
            book.append(
                vrun_receipts.WS_ATTEMPT,
                {
                    "task_id": task_id,
                    "arm": arm,
                    "attempt": i,
                    "gate_round": i,
                    "ws_sha256": "1" * 64,
                    "verdict_sha256": "2" * 64,
                    "conversation_sha256": "3" * 64,
                    "requests_seen": requests_seen,
                    "feedback_delivery": "prompt" if i > 1 else None,
                },
                ident,
                ts_ms=ts_base + i * 1000,
            )
        verdict_payload: dict[str, Any] = {
            "task_id": task_id,
            "arm": arm,
            "accepted": bool(accepted),
            "accepted_is_null": (accepted is None),
            "ws_start_sha256": "0" * 64,
            "ws_end_sha256": "1" * 64,
            "verdict_sha256": "2" * 64,
            "conversation_sha256": "3" * 64,
            "stop_reason": stop_reason,
            "attempts_used": attempts_used,
            "max_attempts": max_attempts,
            "wire_quiesced": True,
        }
        if requests_seen is not None:
            verdict_payload["requests_seen"] = requests_seen
        if tier is not None:
            verdict_payload["tier"] = tier
            verdict_payload["attested"] = (tier == "A")
            verdict_payload["attestation_sha256"] = att_sha
            verdict_payload["unexplained"] = 0 if tier == "A" else 1
        ve = book.append(vrun_receipts.WS_VERDICT, verdict_payload, ident, ts_ms=ts_base + 9000)
        summary["verdict_hash"] = ve.hash()
        book.save(run_dir / f"receipts_{arm}.ndjson")
        (run_dir / f"receipts_{arm}.pub.json").write_text(
            json.dumps({"vacant_id": ident.vacant_id, "pub_hex": pub_to_hex(ident.pub)}),
            encoding="utf-8",
        )

    (run_dir / f"run_{arm}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_dir / "possess.json").write_text(
        json.dumps({"possess_agent": agent, "cwd": ws, "stop_reason": stop_reason}),
        encoding="utf-8",
    )
    return run_dir


def _make_restart_run(
    work_root: pathlib.Path,
    dirname: str,
    payload: dict[str, Any] | str,
) -> pathlib.Path:
    d = work_root / dirname
    d.mkdir(parents=True, exist_ok=True)
    p = d / "result.json"
    if isinstance(payload, str):
        p.write_text(payload, encoding="utf-8")
    else:
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def _make_possess_wire(possess_home: pathlib.Path, lines: list[str]) -> pathlib.Path:
    wdir = possess_home / "proxyd" / "wire"
    wdir.mkdir(parents=True, exist_ok=True)
    p = wdir / "index.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (possess_home / "state.json").write_text(
        json.dumps({"channel": {"pi": {"ok": True}, "codex": {"ok": True}}}),
        encoding="utf-8",
    )
    return p


def _run_cli(argv: list[str], monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> tuple[int, str, str]:
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli_main(argv)
    return rc, out.getvalue(), err.getvalue()


# ── 1. All Five Sources Normalized Cleanly ────────────────────────────────────

def test_collect_all_five_sources_and_export_jsonl(tmp_path: pathlib.Path):
    vh = tmp_path / ".vacant"
    wr = tmp_path / ".vacant-work"
    vr = tmp_path / ".vacant-run"
    ph = vh / "possess"

    ident, _ = _init_trust(vh)

    proj_a = tmp_path / "proj_alpha"
    proj_b = tmp_path / "proj_beta"
    proj_c = tmp_path / "proj_gamma"

    # 1. trace
    pkey, _, _ = _make_trace_project(
        vh, ident, proj_a, platform="pi", with_review_sent_back=True, final_allow=True, with_gap=True
    )
    # 2. intake_ledger
    _make_intake_ledger(vh, ident, "task_beta", proj_b, agent="claude", outcome="accept", released=True)
    # 3. vrun
    _make_vrun_dir(vr, "run_gamma", task_id="vr_gamma", agent="codex", workspace=proj_c, accepted=True, tier="A")
    # 4. restart
    _make_restart_run(
        wr,
        "restart-20261119T100000-123-abc",
        {
            "mode": "restart",
            "project": str(proj_a),
            "protected": ["test_mod.py"],
            "acceptance": {"kind": "python_pytest", "command": "pytest"},
            "max_attempts": 3,
            "accepted": False,
            "delivered_attempt": 2,
            "attempts": [
                {"attempt": 1, "accept": False, "passed": 1, "run": 4, "status": "ok", "tests_tampered": ["test_mod.py"], "first_problem": "assert 1==2", "timed_out": False, "spawn_error": None},
                {"attempt": 2, "accept": False, "passed": 3, "run": 4, "status": "ok", "tests_tampered": [], "first_problem": "assert 3==4", "timed_out": False, "spawn_error": None},
            ],
            "changed": {"added": [], "modified": ["mod.py"], "deleted": [], "skipped": []},
            "agent_wall_s": 12.3,
            "total_wall_s": 15.0,
        },
    )
    # 5. possess_wire
    _make_possess_wire(
        ph,
        [
            json.dumps({"call_id": "c1", "ts": 1_760_300_000.0, "wire": "openai", "method": "POST", "path": "/v1/responses", "status": 200, "blocked": False, "refused_path": False}),
            json.dumps({"call_id": "c2", "ts": 1_760_300_010.0, "wire": "anthropic", "method": "POST", "path": "/v1/messages", "status": 502, "blocked": True, "refused_path": False}),
        ],
    )

    records = AE.collect_all(vacant_home=vh, work_root=wr, vrun_dirs=[vr], possess_home=ph)
    by_kind = {r["kind"]: r for r in records}
    assert set(by_kind) == set(AE.KINDS)

    # Every record carries schema version and required top-level fields
    for r in records:
        assert r["schema"] == AE.AUDIT_RECORD_SCHEMA
        assert isinstance(r["signature"], dict)
        assert "verified" in r["signature"] and "reason" in r["signature"]

    # trace checks
    tr = by_kind["trace"]
    assert tr["record_id"] == f"trace:{pkey}"
    assert tr["agent"] == "pi"
    assert tr["project"] == str(proj_a)
    assert tr["attempts"]["count"] == 2  # 2 review rounds
    assert tr["acceptance"]["result"] == "accepted"
    assert tr["acceptance"]["passed"] is True
    assert tr["sent_back"]["count"] == 1
    assert tr["signature"]["verified"] is True
    assert any(g["code"] == "unrecorded_change" for g in tr["gaps"])

    # intake_ledger checks
    il = by_kind["intake_ledger"]
    assert il["task"] == "task_beta"
    assert il["agent"] == "claude"
    assert il["project"] == str(proj_b)
    assert il["attempts"]["count"] == 2
    assert il["acceptance"]["result"] == "released"
    assert il["acceptance"]["passed"] is True
    assert il["acceptance"]["checks_passed"] == 2
    assert il["acceptance"]["checks_total"] == 2
    assert il["sent_back"]["count"] == 1  # initial reject before accept
    assert il["signature"]["verified"] is True

    # vrun checks
    vrec = by_kind["vrun"]
    assert vrec["task"] == "vr_gamma"
    assert vrec["agent"] == "codex"
    assert vrec["attempts"]["count"] == 2
    assert vrec["attempts"]["max"] == 3
    assert vrec["acceptance"]["result"] == "accepted"
    assert vrec["acceptance"]["checks_passed"] == 3
    assert vrec["sent_back"]["count"] == 1  # prompt retry feedback
    assert vrec["signature"]["verified"] is True
    assert vrec["signature"]["scheme"] == "ed25519_ephemeral_chain"

    # restart checks
    rs = by_kind["restart"]
    assert rs["project"] == str(proj_a)
    assert rs["agent"] is None  # never filled with ""
    assert rs["task"] is None
    assert rs["attempts"]["count"] == 2
    assert rs["attempts"]["delivered"] == 2
    assert rs["acceptance"]["result"] == "rejected"
    assert rs["acceptance"]["passed"] is False
    assert rs["acceptance"]["checks_passed"] == 3
    assert rs["acceptance"]["checks_total"] == 4
    assert rs["signature"]["verified"] is None
    assert rs["signature"]["status"] == "unsigned"
    gap_codes = {g["code"] for g in rs["gaps"]}
    assert "unsigned_source" in gap_codes
    assert "tests_tampered" in gap_codes

    # possess_wire checks
    pw = by_kind["possess_wire"]
    assert pw["agent"] is None
    assert pw["project"] is None
    assert pw["task"] is None
    assert pw["attempts"]["count"] is None  # never filled with 0
    assert pw["acceptance"]["result"] == "unchecked"
    assert pw["acceptance"]["passed"] is None
    assert pw["sent_back"]["count"] is None
    assert pw["signature"]["verified"] is None
    assert pw["details"]["requests_total"] == 2
    assert pw["details"]["blocked_n"] == 1
    assert any(g["code"] == "wire_blocked" for g in pw["gaps"])

    # JSONL roundtrip
    jsonl = AE.export_jsonl(records)
    parsed = [json.loads(line) for line in jsonl.splitlines()]
    assert len(parsed) == 5
    assert all(p["schema"] == "vacant-audit-record/1" for p in parsed)


# ── 2. Edited Chains -> verified=False with reason, NOT dropped ───────────────

def test_edited_chains_reported_as_verified_false_not_dropped(tmp_path: pathlib.Path):
    vh = tmp_path / ".vacant"
    vr = tmp_path / ".vacant-run"
    ident, _ = _init_trust(vh)

    # Edited trace chain
    pkey, pdir, _ = _make_trace_project(vh, ident, tmp_path / "p_trace", platform="pi")
    chain_p = pdir / "chain.ndjson"
    lines = chain_p.read_text(encoding="utf-8").splitlines()
    obj = json.loads(lines[2])
    obj["payload"]["tool"] = "tampered_tool"
    lines[2] = json.dumps(obj, separators=(",", ":"), sort_keys=True)
    chain_p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Edited intake ledger
    led_p = _make_intake_ledger(vh, ident, "task_edited", tmp_path / "p_led", agent="claude")
    llines = led_p.read_text(encoding="utf-8").splitlines()
    lobj = json.loads(llines[-1])
    lobj["payload"]["outcome"] = "reject"
    llines[-1] = json.dumps(lobj, separators=(",", ":"), sort_keys=True)
    led_p.write_text("\n".join(llines) + "\n", encoding="utf-8")

    # Edited vrun receipt chain
    vdir = _make_vrun_dir(vr, "run_edited", task_id="vr_edited", agent="codex")
    vchain = vdir / "receipts_RUN-ON.ndjson"
    vlines = vchain.read_text(encoding="utf-8").splitlines()
    vobj = json.loads(vlines[0])
    vobj["payload"]["ws_sha256"] = "f" * 64
    vlines[0] = json.dumps(vobj, separators=(",", ":"), sort_keys=True)
    vchain.write_text("\n".join(vlines) + "\n", encoding="utf-8")

    records = AE.collect_all(vacant_home=vh, work_root=tmp_path / "w", vrun_dirs=[vr], possess_home=vh / "possess")
    by_id = {r["record_id"]: r for r in records}

    assert f"trace:{pkey}" in by_id
    assert by_id[f"trace:{pkey}"]["signature"]["verified"] is False
    assert by_id[f"trace:{pkey}"]["signature"]["reason"]
    assert any(g["code"] == "signature_failed" for g in by_id[f"trace:{pkey}"]["gaps"])

    assert "intake_ledger:task_edited" in by_id
    assert by_id["intake_ledger:task_edited"]["signature"]["verified"] is False
    assert "does not verify" in by_id["intake_ledger:task_edited"]["signature"]["reason"].lower()

    assert "vrun:run_edited:RUN-ON" in by_id
    assert by_id["vrun:run_edited:RUN-ON"]["signature"]["verified"] is False
    assert "bad_signature" in by_id["vrun:run_edited:RUN-ON"]["signature"]["reason"]


# ── 3. Truncated Chains -> verified=False with reason, NOT dropped ────────────

def test_truncated_chains_all_variants_reported_not_dropped(tmp_path: pathlib.Path):
    vh = tmp_path / ".vacant"
    vr = tmp_path / ".vacant-run"
    ident, _ = _init_trust(vh)

    # 3a. Mid-line torn trace chain (must NOT be masked as verified=True!)
    pk_torn, dir_torn, _ = _make_trace_project(vh, ident, tmp_path / "p_torn", platform="pi")
    raw = (dir_torn / "chain.ndjson").read_bytes()
    (dir_torn / "chain.ndjson").write_bytes(raw[:-25])  # cut mid-line

    # 3b. Tail-truncated trace chain caught by head.json
    pk_head, dir_head, _ = _make_trace_project(vh, ident, tmp_path / "p_head", platform="opencode")
    hlines = (dir_head / "chain.ndjson").read_text(encoding="utf-8").splitlines()
    (dir_head / "chain.ndjson").write_text("\n".join(hlines[:-2]) + "\n", encoding="utf-8")

    # 3c. Tail-truncated trace chain with head.json DELETED, caught by intake ledger trace_head anchor!
    pk_anch, dir_anch, anch_book = _make_trace_project(vh, ident, tmp_path / "p_anch", platform="claude")
    last_e = anch_book.entries[-1]
    _make_intake_ledger(
        vh,
        ident,
        "task_anchor",
        tmp_path / "p_anch",
        agent="claude",
        trace_anchor=(pk_anch, last_e.seq, last_e.hash()),
    )
    alines = (dir_anch / "chain.ndjson").read_text(encoding="utf-8").splitlines()
    (dir_anch / "chain.ndjson").write_text("\n".join(alines[:-2]) + "\n", encoding="utf-8")
    (dir_anch / "head.json").unlink()

    # 3d. Mid-line truncated intake ledger
    led_trunc = _make_intake_ledger(vh, ident, "task_led_trunc", tmp_path / "p_lt", agent="pi")
    lraw = led_trunc.read_bytes()
    led_trunc.write_bytes(lraw[: len(lraw) // 2])

    # 3e. Tail-truncated vrun receipt chain (verdict line removed; rows.jsonl + verdict_hash catch it)
    vdir_t = _make_vrun_dir(vr, "run_vtrunc", task_id="vr_trunc", agent="codex")
    vlines = (vdir_t / "receipts_RUN-ON.ndjson").read_text(encoding="utf-8").splitlines()
    (vdir_t / "receipts_RUN-ON.ndjson").write_text("\n".join(vlines[:-1]) + "\n", encoding="utf-8")

    # 3f. Mid-line truncated vrun receipt chain
    vdir_m = _make_vrun_dir(vr, "run_vmid", task_id="vr_mid", agent="codex")
    vraw = (vdir_m / "receipts_RUN-ON.ndjson").read_bytes()
    (vdir_m / "receipts_RUN-ON.ndjson").write_bytes(vraw[:-30])

    records = AE.collect_all(vacant_home=vh, work_root=tmp_path / "w", vrun_dirs=[vr], possess_home=vh / "possess")
    by_id = {r["record_id"]: r for r in records}

    for rid in (
        f"trace:{pk_torn}",
        f"trace:{pk_head}",
        f"trace:{pk_anch}",
        "intake_ledger:task_led_trunc",
        "vrun:run_vtrunc:RUN-ON",
        "vrun:run_vmid:RUN-ON",
    ):
        assert rid in by_id, f"truncated record {rid} was dropped!"
        rec = by_id[rid]
        assert rec["signature"]["verified"] is False, f"{rid} unexpectedly verified: {rec['signature']}"
        assert rec["signature"]["reason"], f"{rid} missing failure reason"
        assert any(g["code"] == "chain_truncated" for g in rec["gaps"]), (
            f"{rid} missing chain_truncated gap: {rec['gaps']}"
        )

    # Anchored trace specifically reports anchor_checked=True
    assert by_id[f"trace:{pk_anch}"]["signature"]["anchor_checked"] is True
    assert "anchored entry" in by_id[f"trace:{pk_anch}"]["signature"]["reason"]


# ── 4. Missing Fields & Corrupt Files: Never Fill with 0 or False ─────────────

def test_missing_fields_never_filled_with_zero_or_false(tmp_path: pathlib.Path):
    vh = tmp_path / ".vacant"
    wr = tmp_path / ".vacant-work"
    vr = tmp_path / ".vacant-run"
    ph = vh / "possess"
    _init_trust(vh)

    # 4a. Unreadable intake ledger -> attempts.count is None (NOT 0!), result is unreadable
    ldir = vh / "intake" / "ledger"
    ldir.mkdir(parents=True, exist_ok=True)
    (ldir / "task_corrupt.ndjson").write_text("{not valid json\n", encoding="utf-8")

    # 4b. Restart result.json missing 'accepted', 'attempts', 'agent', 'task'
    _make_restart_run(wr, "restart-notimestamp", {"mode": "restart", "project": str(tmp_path / "p_min")})

    # 4c. Corrupt restart result.json
    _make_restart_run(wr, "restart-20261119T110000-1-aaa", "{broken json")

    # 4d. Restart with accepted=None (no_tests -> unchecked, passed=None, checks=None)
    _make_restart_run(
        wr,
        "restart-20261119T120000-1-bbb",
        {
            "mode": "restart",
            "project": str(tmp_path / "p_notests"),
            "acceptance": {"kind": "none", "reason": "no test runner"},
            "max_attempts": 1,
            "accepted": None,
            "delivered_attempt": 1,
            "attempts": [{"attempt": 1, "accept": None, "passed": None, "run": None, "status": "no_tests", "tests_tampered": []}],
        },
    )

    # 4e. Legacy vrun without requests_seen or tier, and missing pub.json
    vdir = _make_vrun_dir(
        vr,
        "run_legacy",
        task_id="vr_legacy",
        requests_seen=None,
        tier=None,
        accepted=None,
        stop_reason="ungated",
    )
    (vdir / "receipts_RUN-ON.pub.json").unlink()

    # 4f. Possess wire with a malformed line and missing ts
    _make_possess_wire(ph, ["not-json-line", json.dumps({"call_id": "x1", "wire": "openai", "method": "POST", "path": "/v1/models"})])

    records = AE.collect_all(vacant_home=vh, work_root=wr, vrun_dirs=[vr], possess_home=ph)
    by_id = {r["record_id"]: r for r in records}

    # Corrupt ledger
    lc = by_id["intake_ledger:task_corrupt"]
    assert lc["signature"]["verified"] is False
    assert lc["acceptance"]["result"] == "unreadable"
    assert lc["acceptance"]["passed"] is None
    assert lc["attempts"]["count"] is None
    assert lc["sent_back"]["count"] is None
    assert lc["sent_back"]["items"] is None

    # Minimal restart (missing fields)
    rmin = by_id["restart:restart-notimestamp"]
    assert rmin["timestamp_ms"] is None
    assert rmin["agent"] is None
    assert rmin["task"] is None
    assert rmin["attempts"]["count"] is None
    assert rmin["attempts"]["max"] is None
    assert rmin["attempts"]["delivered"] is None
    assert rmin["acceptance"]["result"] == "unknown"
    assert rmin["acceptance"]["passed"] is None
    assert rmin["acceptance"]["checks_passed"] is None
    assert rmin["acceptance"]["checks_total"] is None
    assert rmin["sent_back"]["count"] is None
    assert any(g["code"] == "missing_fields" for g in rmin["gaps"])

    # Corrupt restart
    rcor = by_id["restart:restart-20261119T110000-1-aaa"]
    assert rcor["acceptance"]["result"] == "unreadable"
    assert rcor["attempts"]["count"] is None
    assert rcor["project"] is None
    assert any(g["code"] == "unreadable_source" for g in rcor["gaps"])

    # Unchecked restart
    runc = by_id["restart:restart-20261119T120000-1-bbb"]
    assert runc["acceptance"]["result"] == "unchecked"
    assert runc["acceptance"]["passed"] is None
    assert runc["acceptance"]["checks_passed"] is None
    assert runc["acceptance"]["checks_total"] is None
    assert any(g["code"] == "unchecked" for g in runc["gaps"])

    # Legacy vrun without pubkey, requests_seen, tier
    vleg = by_id["vrun:run_legacy:RUN-ON"]
    assert vleg["signature"]["verified"] is False
    assert vleg["signature"]["status"] == "unverifiable"
    assert "pubkey_file_missing" in vleg["signature"]["reason"]
    assert vleg["details"]["mediated"] is None  # not False!
    assert vleg["details"]["tier"] is None
    assert vleg["details"]["requests_seen"] is None  # not 0!
    assert vleg["acceptance"]["result"] == "unchecked"
    assert vleg["acceptance"]["passed"] is None

    # Possess wire with malformed entry & missing ts
    pw = by_id["possess_wire:proxyd"]
    assert pw["timestamp_ms"] is None
    assert pw["attempts"]["count"] is None
    assert pw["sent_back"]["count"] is None
    assert any(g["code"] == "malformed_entries" and g["count"] == 1 for g in pw["gaps"])


# ── 5. Filters & CLI (`list`, `show`, `export --jsonl`) ───────────────────────

def test_cli_list_show_export_and_filters(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    vh = tmp_path / ".vacant"
    wr = tmp_path / ".vacant-work"
    vr = tmp_path / ".vacant-run"
    ph = vh / "possess"
    ident, _ = _init_trust(vh)

    pk, _, _ = _make_trace_project(vh, ident, tmp_path / "proj_one", platform="pi", ts_base=1_760_000_000_000)
    _make_intake_ledger(vh, ident, "task_two", tmp_path / "proj_two", agent="claude", ts_base=1_760_500_000_000, outcome="reject")
    _make_vrun_dir(vr, "run_three", task_id="vr_three", agent="codex", workspace=tmp_path / "proj_three", ts_base=1_761_000_000_000, accepted=True)
    _make_vrun_dir(vr, "run_void", task_id="vr_void", agent="codex", workspace=tmp_path / "proj_three", ts_base=1_761_100_000_000, infra_void="agent_spawn_failed")

    env = {
        "VACANT_HOME": str(vh),
        "VACANT_WORK": str(wr),
        "VACANT_RUN_DIR": str(vr),
        "VACANT_POSSESS_HOME": str(ph),
    }

    # list (human-readable)
    rc, out, err = _run_cli(["audit", "list"], monkeypatch, env)
    assert rc == 0, err
    assert "RECORD_ID" in out
    assert "tamper-evident" in out.lower() and "re-verifiable" in out.lower()
    assert "not guaranteed to be complete" in out.lower()

    # filter --agent claude
    rc, out, err = _run_cli(["audit", "export", "--jsonl", "--agent", "claude"], monkeypatch, env)
    assert rc == 0, err
    rows = [json.loads(x) for x in out.splitlines() if x.strip()]
    assert [r["record_id"] for r in rows] == ["intake_ledger:task_two"]

    # filter --project proj_one
    rc, out, err = _run_cli(["audit", "export", "--jsonl", "--project", "proj_one"], monkeypatch, env)
    assert rc == 0, err
    rows = [json.loads(x) for x in out.splitlines() if x.strip()]
    assert [r["record_id"] for r in rows] == [f"trace:{pk}"]

    # filter --kind vrun --result void
    rc, out, err = _run_cli(["audit", "export", "--jsonl", "--kind", "vrun", "--result", "void"], monkeypatch, env)
    assert rc == 0, err
    rows = [json.loads(x) for x in out.splitlines() if x.strip()]
    assert [r["record_id"] for r in rows] == ["vrun:run_void:RUN-ON"]
    assert rows[0]["signature"]["status"] == "unsigned"
    assert rows[0]["signature"]["verified"] is None

    # filter --since (epoch seconds)
    rc, out, err = _run_cli(["audit", "export", "--jsonl", "--since", "1760900000"], monkeypatch, env)
    assert rc == 0, err
    rows = [json.loads(x) for x in out.splitlines() if x.strip()]
    assert {r["record_id"] for r in rows} == {"vrun:run_three:RUN-ON", "vrun:run_void:RUN-ON"}

    # export --jsonl --out FILE
    out_file = tmp_path / "exported.jsonl"
    rc, out, err = _run_cli(["audit", "export", "--jsonl", "--out", str(out_file)], monkeypatch, env)
    assert rc == 0, err
    assert out == ""
    assert len(out_file.read_text(encoding="utf-8").splitlines()) == 4

    # show by exact id and unique prefix
    rc, out, err = _run_cli(["audit", "show", "intake_ledger:task_two"], monkeypatch, env)
    assert rc == 0, err
    assert "task_two" in out and "rejected" in out
    rc, out, err = _run_cli(["audit", "show", f"trace:{pk[:8]}", "--json"], monkeypatch, env)
    assert rc == 0, err
    shown = json.loads(out)
    assert shown["record_id"] == f"trace:{pk}"

    # invalid --since -> exit 2
    rc, out, err = _run_cli(["audit", "list", "--since", "not-a-date"], monkeypatch, env)
    assert rc == 2
    assert "invalid --since" in err


def test_parse_since_formats():
    now = 1_760_000_000_000
    assert AE.parse_since("24h", now_ms=now) == now - 24 * 3600 * 1000
    assert AE.parse_since("7d", now_ms=now) == now - 7 * 86400 * 1000
    assert AE.parse_since("1760000000") == 1_760_000_000_000
    assert AE.parse_since("1760000000000") == 1_760_000_000_000
    assert AE.parse_since("2026-11-01T00:00:00Z") == 1_793_491_200_000
    assert AE.parse_since("2026-11-01") == 1_793_491_200_000
    with pytest.raises(ValueError):
        AE.parse_since("yesterday")


# ── 6. Read-Only Guarantee, Wording Rule & Legacy `vacant audit <name>` ──────

def test_collect_all_is_strictly_readonly(tmp_path: pathlib.Path):
    vh = tmp_path / ".vacant"
    wr = tmp_path / ".vacant-work"
    vr = tmp_path / ".vacant-run"
    ident, _ = _init_trust(vh)
    _make_trace_project(vh, ident, tmp_path / "p_ro")
    _make_intake_ledger(vh, ident, "task_ro", tmp_path / "p_ro")
    _make_vrun_dir(vr, "run_ro")

    def _snapshot(root: pathlib.Path) -> dict[str, bytes]:
        if not root.exists():
            return {}
        return {
            str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*"))
            if p.is_file()
        }

    before = (_snapshot(vh), _snapshot(wr), _snapshot(vr))
    recs = AE.collect_all(vacant_home=vh, work_root=wr, vrun_dirs=[vr], possess_home=vh / "possess")
    after = (_snapshot(vh), _snapshot(wr), _snapshot(vr))
    assert len(recs) == 3
    assert before == after


def test_wording_rule_and_no_banned_terms():
    banned = ("信任", "trust layer", "trusted layer", "信任層")
    help_text = AE.build_parser().format_help()
    assert "tamper-evident" in help_text.lower()
    assert "re-verifiable" in help_text.lower()
    assert "never guaranteed to be complete" in help_text.lower()
    for w in banned:
        assert w not in help_text

    doc = (pathlib.Path(__file__).resolve().parents[1] / "docs" / "AUDIT_RECORD_V1.md").read_text(encoding="utf-8")
    assert "tamper-evident" in doc.lower()
    assert "re-verifiable" in doc.lower()
    assert "never guaranteed to be complete" in doc.lower()
    for w in banned:
        assert w not in doc


def test_accountability_gaps_untrusted_signer_unmediated_and_not_certified(tmp_path: pathlib.Path):
    vh = tmp_path / ".vacant"
    vr = tmp_path / ".vacant-run"
    ident, _ = _init_trust(vh)
    rogue = Identity.generate()

    # Trace signed by a key NOT in trust.json -> verified=False
    pk_rogue, _, _ = _make_trace_project(
        vh, rogue, tmp_path / "p_rogue", platform="pi", with_post_missing=True, with_open_flag=True, scan_disabled="timeout"
    )
    # Intake ledger signed by rogue key + workspace_escape
    _make_intake_ledger(vh, rogue, "task_rogue", tmp_path / "p_rogue", agent="claude", workspace_escape=True, outcome="hold")
    # vrun with requests_seen=0 (unmediated) + tier B (unattested + unexplained_calls) + tampered attestation
    vdir_b = _make_vrun_dir(vr, "run_tier_b", task_id="vr_b", agent="codex", accepted=False, stop_reason="visible_fail", requests_seen=0, tier="B")
    # Edit run_RUN-ON.json attestation after signing -> attestation_sha256_mismatch
    rpath = vdir_b / "run_RUN-ON.json"
    rdata = json.loads(rpath.read_text(encoding="utf-8"))
    rdata["attestation"]["tier"] = "A"
    rpath.write_text(json.dumps(rdata), encoding="utf-8")

    # vrun NOT_CERTIFIED.json (tier C, no receipt chain)
    vdir_c = vr / "run_tier_c"
    vdir_c.mkdir(parents=True, exist_ok=True)
    (vdir_c / "NOT_CERTIFIED.json").write_text(
        json.dumps(
            {
                "not_a_receipt": True,
                "tier": "C",
                "diagnostics": {"possess_agent": "pi", "cwd": str(tmp_path / "p_c"), "stop_reason": "visible_fail"},
            }
        ),
        encoding="utf-8",
    )

    records = AE.collect_all(vacant_home=vh, work_root=tmp_path / "w", vrun_dirs=[vr], possess_home=vh / "possess")
    by_id = {r["record_id"]: r for r in records}

    # Rogue trace
    tr = by_id[f"trace:{pk_rogue}"]
    assert tr["signature"]["verified"] is False
    assert "accepted-signer" in tr["signature"]["reason"]
    t_gaps = {g["code"] for g in tr["gaps"]}
    assert {"signature_failed", "post_missing", "open_flags", "scan_disabled"} <= t_gaps

    # Rogue ledger with workspace escape + hold
    il = by_id["intake_ledger:task_rogue"]
    assert il["signature"]["verified"] is False
    assert il["acceptance"]["result"] == "held"
    assert il["acceptance"]["passed"] is None
    assert any(g["code"] == "workspace_escape" for g in il["gaps"])

    # vrun tier B with unmediated + unexplained + attestation digest mismatch
    vb = by_id["vrun:run_tier_b:RUN-ON"]
    assert vb["signature"]["verified"] is False
    assert "attestation_sha256_mismatch" in vb["signature"]["reason"]
    vb_gaps = {g["code"] for g in vb["gaps"]}
    assert {"signature_failed", "unmediated", "unattested", "unexplained_calls"} <= vb_gaps

    # vrun NOT_CERTIFIED (tier C)
    vc = by_id["vrun:run_tier_c:default"]
    assert vc["signature"]["verified"] is None
    assert vc["signature"]["status"] == "unsigned"
    assert vc["agent"] == "pi"
    assert any(g["code"] == "unattested" for g in vc["gaps"])


def test_legacy_vacant_audit_body_still_works(tmp_path: pathlib.Path):
    body_root = tmp_path / "bodies"
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc1 = cli_main(["--root", str(body_root), "init", "alice"])
    assert rc1 == 0, err.getvalue()

    out2, err2 = io.StringIO(), io.StringIO()
    with redirect_stdout(out2), redirect_stderr(err2):
        rc2 = cli_main(["--root", str(body_root), "audit", "alice"])
    assert rc2 == 0, err2.getvalue()
    assert "alice" in out2.getvalue()
    assert "沒有東西可驗" in out2.getvalue()
