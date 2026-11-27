"""Unit and end-to-end tests for Experiment T (feedback builder, signed chains, runner, metrics, plans)."""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "ops" / "d2") not in sys.path:
    sys.path.insert(0, str(REPO / "ops" / "d2"))

import expT_feedback as FB  # noqa: E402
import expT_metrics as EM  # noqa: E402
import run_expT as RT  # noqa: E402
from ops.e1 import assert_ks1_clean as e1_assert_ks1_clean  # noqa: E402
from vacant_network.identity import Identity  # noqa: E402
from vacant_network.logbook import ChainError, Logbook  # noqa: E402
from vacant_network.memory import assert_ks1_clean as mem_assert_ks1_clean  # noqa: E402


def _sample_claims() -> list[dict]:
    return [
        {"id": "c01", "entity": "Alpha", "label": "Price", "template_line": "- Alpha — Price: "},
        {"id": "c02", "entity": "Alpha", "label": "Apps (goals)", "template_line": "- Alpha — Apps (goals): "},
        {"id": "c03", "entity": "Beta", "label": "Version", "template_line": "- Beta — Version: "},
        {"id": "c04", "entity": "Beta", "label": "Seats", "template_line": "- Beta — Seats: "},
    ]


# ---------------------------------------------------------------------------
# Unit tests: G, T, T0 feedback builders & KS-1 compliance
# ---------------------------------------------------------------------------


def test_G_fixed_text_and_ks1_clean():
    expected = "Please re-check your report for completeness and correctness and fix anything that is wrong."
    assert FB.GENERIC_REVIEW_PROMPT == expected
    msg = FB.build_G_feedback()
    assert msg == expected
    assert FB.build_arm_feedback("G") == expected
    FB.assert_ks1_clean(msg)
    mem_assert_ks1_clean(msg)
    e1_assert_ks1_clean(msg)


def test_T_feedback_exact_text_flagged_only_and_stop_when_none():
    assert FB.build_T_feedback([], ["http://s01.d2-sources.example/p1.html"]) is None

    flagged = [
        {"claim_id": "c02", "label": "Alpha — Apps (goals)", "problem_kind": FB.PROBLEM_MISSING},
        {"claim_id": "c03", "label": "Beta — Version", "problem_kind": FB.PROBLEM_NOT_IN_FETCHED},
        {"claim_id": "c04", "label": "Beta — Seats", "problem_kind": FB.PROBLEM_CHANGED_NO_SOURCE},
    ]
    urls = [
        "http://s01.d2-sources.example/p2.html",
        "http://s01.d2-sources.example/p1.html",
        "http://s01.d2-sources.example/p1.html",  # duplicate deduplicated & sorted
    ]
    msg = FB.build_T_feedback(flagged, urls)
    assert msg is not None
    expected = "\n".join([
        FB.T_FEEDBACK_HEADER,
        "- [c02] Alpha — Apps (goals): missing value",
        "- [c03] Beta — Version: value not in any fetched page",
        "- [c04] Beta — Seats: changed without reading a source",
        "",
        "Pages you fetched:",
        "- http://s01.d2-sources.example/p1.html",
        "- http://s01.d2-sources.example/p2.html",
    ])
    assert msg == expected
    assert "c01" not in msg
    assert "Price" not in msg
    FB.assert_ks1_clean(msg)
    mem_assert_ks1_clean(msg)
    e1_assert_ks1_clean(msg)

    # Empty fetched_urls renders explicit "(none)"
    msg_none = FB.build_T_feedback([flagged[0]], [])
    assert msg_none is not None
    assert msg_none.endswith("Pages you fetched: (none)")


def test_T0_feedback_count_only_no_line_ids_and_stop_when_none():
    assert FB.build_T0_feedback([]) is None

    flagged = [
        {"claim_id": "c02", "label": "Alpha — Apps (goals)", "problem_kind": FB.PROBLEM_MISSING},
        {"claim_id": "c03", "label": "Beta — Version", "problem_kind": FB.PROBLEM_NOT_IN_FETCHED},
    ]
    msg = FB.build_T0_feedback(flagged)
    assert msg == "2 lines in your report have no supporting source in what you fetched; please check and fix them."
    assert "c02" not in msg
    assert "c03" not in msg
    assert "Alpha" not in msg
    assert "http://" not in msg
    FB.assert_ks1_clean(msg)
    mem_assert_ks1_clean(msg)
    e1_assert_ks1_clean(msg)


# ---------------------------------------------------------------------------
# Unit tests: record-only F1 & F3 flag computation
# ---------------------------------------------------------------------------


def test_compute_line_flags_F1_plaintext_and_F3_no_source_edit():
    claims = _sample_claims()
    html_p1 = "<html><body><h1>Alpha</h1><table><tr><td>Price</td><td>$40</td></tr><tr><td>45</td><td>(3)</td></tr></table></body></html>"
    html_p2 = "<html><body><h1>Beta</h1><table><tr><td>Version</td><td>v2.1.0</td></tr><tr><td>Seats</td><td>25</td></tr></table></body></html>"
    universe = [
        {"seq": 2, "url": "http://s01.d2-sources.example/p1.html", "text": html_p1, "source": "egress"},
        {"seq": 3, "url": "http://s01.d2-sources.example/p2.html", "text": html_p2, "source": "egress"},
    ]

    # Round 0 (c0):
    # - c01: $40 (in p1) -> OK
    # - c02: 45 (3) (split across adjacent <td> cells in p1 -> plain_contains match per amend1!) -> OK
    # - c03: ____ (missing) -> F1 missing value
    # - c04: 999 (not in any page) -> F1 value not in any fetched page
    r0_text = "\n".join([
        "- Alpha — Price: $40",
        "- Alpha — Apps (goals): 45 (3)",
        "- Beta — Version: ____",
        "- Beta — Seats: 999",
    ])
    fr0 = FB.compute_line_flags(
        r0_text, claims, universe, round_idx=0, prev_values=None, prev_bound_seq=0, cur_bound_seq=5,
    )
    assert fr0["flagged_ids"] == ["c03", "c04"]
    assert fr0["flags_by_claim"]["c01"]["flagged"] is False
    assert fr0["flags_by_claim"]["c02"]["flagged"] is False
    assert fr0["flags_by_claim"]["c03"]["F1"] is True
    assert fr0["flags_by_claim"]["c03"]["problem_kind"] == FB.PROBLEM_MISSING
    assert fr0["flags_by_claim"]["c04"]["F1"] is True
    assert fr0["flags_by_claim"]["c04"]["problem_kind"] == FB.PROBLEM_NOT_IN_FETCHED
    assert fr0["fetched_urls"] == [
        "http://s01.d2-sources.example/p1.html",
        "http://s01.d2-sources.example/p2.html",
    ]

    # Round 1 WITHOUT any new fetch (no entries with seq > 5):
    # - Agent edits c01 from "$40" to "25" (which happens to be on p2 from c0, so F1 is False,
    #   but it changed in a round that fetched NO source -> F3 fires!).
    # - Agent fills c03 with "v2.1.0" (was None, now in p2 -> OK).
    # - Agent changes c04 from "999" to "25" without fetching -> F3 fires!
    r1_text = "\n".join([
        "- Alpha — Price: 25",
        "- Alpha — Apps (goals): 45 (3)",
        "- Beta — Version: v2.1.0",
        "- Beta — Seats: 25",
    ])
    fr1 = FB.compute_line_flags(
        r1_text, claims, universe,
        round_idx=1, prev_values=fr0["values"], prev_bound_seq=5, cur_bound_seq=8,
    )
    assert fr1["round_fetch_count"] == 0
    assert fr1["flagged_ids"] == ["c01", "c04"]
    assert fr1["flags_by_claim"]["c01"]["F1"] is False
    assert fr1["flags_by_claim"]["c01"]["F3"] is True
    assert fr1["flags_by_claim"]["c01"]["problem_kind"] == FB.PROBLEM_CHANGED_NO_SOURCE
    assert fr1["flags_by_claim"]["c04"]["F3"] is True

    # Round 1 WITH a fetch in round 1 (seq 6 > prev_bound_seq 5) -> F3 does NOT fire!
    universe_with_r1 = [
        *universe,
        {"seq": 6, "url": "http://s01.d2-sources.example/p2.html", "text": html_p2, "source": "egress"},
    ]
    fr1_fetched = FB.compute_line_flags(
        r1_text, claims, universe_with_r1,
        round_idx=1, prev_values=fr0["values"], prev_bound_seq=5, cur_bound_seq=8,
    )
    assert fr1_fetched["round_fetch_count"] == 1
    assert fr1_fetched["flagged_ids"] == []
    assert FB.build_T_feedback(fr1_fetched["flagged"], fr1_fetched["fetched_urls"]) is None


# ---------------------------------------------------------------------------
# Unit tests: signed Logbook chain events & reconstruct + tamper detection
# ---------------------------------------------------------------------------


def test_signed_feedback_chain_reconstruct_and_tamper_detection(tmp_path: pathlib.Path):
    ident = Identity.generate()
    book = Logbook()
    flagged = [{"claim_id": "c02", "label": "Alpha — Apps (goals)", "F1": True, "F3": False,
                "reasons": [FB.PROBLEM_MISSING], "problem_kind": FB.PROBLEM_MISSING}]
    urls = ["http://s01.d2-sources.example/p1.html"]
    ev1 = FB.make_trigger_evidence("T", 0, {"flagged": flagged, "fetched_urls": urls, "round_fetch_count": 1})
    fb1 = FB.build_T_feedback(flagged, urls)
    FB.feedback_event(book, ident, arm="T", round_idx=1, decision="send_feedback", feedback_text=fb1, evidence=ev1, ts_ms=1000)

    ev2 = FB.make_trigger_evidence("T", 1, {"flagged": [], "fetched_urls": urls, "round_fetch_count": 1})
    FB.feedback_event(book, ident, arm="T", round_idx=2, decision="stop_no_flags", feedback_text=None, evidence=ev2, ts_ms=2000)

    chain_path = tmp_path / "feedback_chain.ndjson"
    FB.save_feedback_chain(book, ident, chain_path)
    assert chain_path.is_file()
    assert chain_path.with_suffix(".pub.json").is_file()

    buf = io.StringIO()
    hist = FB.reconstruct(chain_path, stream=buf)
    assert len(hist) == 2
    assert hist[0]["arm"] == "T"
    assert hist[0]["round"] == 1
    assert hist[0]["decision"] == "send_feedback"
    assert hist[0]["feedback_text"] == fb1
    assert hist[0]["evidence"]["flagged_ids"] == ["c02"]
    assert hist[0]["evidence"]["fetched_urls"] == urls
    assert hist[1]["decision"] == "stop_no_flags"
    assert hist[1]["feedback_text"] is None
    assert "decision=send_feedback" in buf.getvalue()
    assert "decision=stop_no_flags" in buf.getvalue()

    # Tamper payload -> ChainError
    raw_lines = chain_path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(raw_lines[0])
    tampered["payload"]["feedback_text"] = "TAMPERED"
    tampered_path = tmp_path / "tampered.ndjson"
    tampered_path.write_text(json.dumps(tampered) + "\n" + raw_lines[1] + "\n", encoding="utf-8")
    tampered_path.with_suffix(".pub.json").write_text(chain_path.with_suffix(".pub.json").read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ChainError):
        FB.reconstruct(tampered_path, emit=False)

    # Delete first entry -> ChainError
    deleted_path = tmp_path / "deleted.ndjson"
    deleted_path.write_text(raw_lines[1] + "\n", encoding="utf-8")
    deleted_path.with_suffix(".pub.json").write_text(chain_path.with_suffix(".pub.json").read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ChainError):
        FB.reconstruct(deleted_path, emit=False)


# ---------------------------------------------------------------------------
# End-to-end tests: 1 set x 4 arms (fake_agent.py & flawed-draft fake agent)
# ---------------------------------------------------------------------------


def _make_synthetic_materials(mat_dir: pathlib.Path) -> tuple[pathlib.Path, str]:
    sdir = mat_dir / "sets" / "s01"
    site = sdir / "cycle_0" / "site"
    site.mkdir(parents=True)
    (site / "p1.html").write_text(
        "<!doctype html><html><body><h1>Alpha</h1>"
        "<table><tr><td>Price</td><td>$40</td></tr>"
        "<tr><td>Users</td><td>120</td></tr></table></body></html>\n",
        encoding="utf-8",
    )
    (site / "p2.html").write_text(
        "<!doctype html><html><body><h1>Beta</h1>"
        "<table><tr><td>Version</td><td>v2.1.0</td></tr>"
        "<tr><td>Seats</td><td>25</td></tr>"
        "<tr><td>Other</td><td>77</td></tr></table></body></html>\n",
        encoding="utf-8",
    )
    template = "\n".join([
        "# Verification report",
        "",
        "- Alpha — Price: ____",
        "- Alpha — Users: ____",
        "- Beta — Version: ____",
        "- Beta — Seats: ____",
    ]) + "\n"
    (sdir / "template.md").write_text(template, encoding="utf-8")

    manifest = {
        "schema": "vacant.d2.manifest/1",
        "sets": [{
            "set": "s01",
            "domain": "synthetic",
            "pages": ["p1.html", "p2.html"],
            "index": None,
            "cycles": [],
            "claims": [
                {"id": "c01", "entity": "Alpha", "label": "Price", "template_line": "- Alpha — Price: ", "source_pages": ["p1.html"]},
                {"id": "c02", "entity": "Alpha", "label": "Users", "template_line": "- Alpha — Users: ", "source_pages": ["p1.html"]},
                {"id": "c03", "entity": "Beta", "label": "Version", "template_line": "- Beta — Version: ", "source_pages": ["p2.html"]},
                {"id": "c04", "entity": "Beta", "label": "Seats", "template_line": "- Beta — Seats: ", "source_pages": ["p2.html"]},
            ],
            "truth": [{"c01": "$40", "c02": "120", "c03": "v2.1.0", "c04": "25"}],
        }],
    }
    raw = json.dumps(manifest, indent=2).encode("utf-8")
    (mat_dir / "manifest.json").write_bytes(raw)
    return mat_dir, hashlib.sha256(raw).hexdigest()


def test_e2e_with_existing_fake_agent_1set_4arms(tmp_path: pathlib.Path):
    """End-to-end on 1 set x 4 arms using ops/d2/fake_agent.py, source_server, egress proxy, and expT_metrics."""
    mat_dir, msha = _make_synthetic_materials(tmp_path / "mat")
    plan = {
        "schema": "vacant.d2.expT.plan/1",
        "id": "e2e_fake_agent",
        "seed": 42,
        "arms": ["A", "G", "T", "T0"],
        "reps": 1,
        "max_rounds": 2,
        "agent_timeout_s": 30,
        "budget_s": 90,
        "egress": True,
        "server": {"port": 0},
        "jobs": 1,
        "model": {"provider": "fake", "model": "fake"},
        "materials": [{"prefix": "syn", "dir": str(mat_dir), "manifest_sha256": msha, "sets": ["s01"]}],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    root = tmp_path / "run_out"

    rc = RT.ExpTRun(plan_path, root, fake=True).go()
    assert rc == 0

    # Access log recorded agent fetches through source_server
    access_lines = [json.loads(x) for x in (root / "access.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(access_lines) >= 2
    assert any(x["path"] == "/p1.html" for x in access_lines)
    assert any(x["path"] == "/p2.html" for x in access_lines)

    # Check each arm cell & reconstruct signed feedback chain
    for arm in ("A", "G", "T", "T0"):
        adir = root / "cells" / "syn-s01" / "r1" / arm
        cell = json.loads((adir / "cell.json").read_text(encoding="utf-8"))
        assert cell["infra_void"] is False
        hist = FB.reconstruct(adir / "feedback_chain.ndjson", emit=False)
        assert len(hist) >= 1
        if arm == "A":
            assert cell["rounds_run"] == 0
            assert hist[0]["decision"] == "native_c0"
        elif arm == "G":
            assert cell["rounds_run"] == 2
            sends = [h for h in hist if h["decision"] == "send_feedback"]
            assert len(sends) == 2
            assert all(h["feedback_text"] == FB.GENERIC_REVIEW_PROMPT for h in sends)
        else:
            # fake_agent.py filled all 4 lines accurately from fetched pages -> 0 flagged -> immediate stop!
            assert cell["rounds_run"] == 0
            assert cell["stop_reason"] == "stop_no_flags"
            assert hist[0]["decision"] == "stop_no_flags"
            assert hist[0]["feedback_text"] is None

    # Metrics script runs cleanly
    res = EM.analyze_root(root, n_boot=200, seed=7)
    for arm in ("A", "G", "T", "T0"):
        assert res["by_arm"][arm]["all_correct_set_ratio"] == 1.0
        assert res["by_arm"][arm]["chains_ok"] == 1
        assert res["by_arm"][arm]["chains_bad"] == 0


def test_e2e_flawed_draft_fake_agent_4arms_metrics(tmp_path: pathlib.Path):
    """End-to-end on 1 set x 4 arms x 2 reps where c0 has missing + fabricated + wrong_read errors."""
    mat_dir, msha = _make_synthetic_materials(tmp_path / "mat")

    # Custom deterministic fake agent simulating realistic differences across A, G, T, T0
    fake_script = tmp_path / "flawed_fake_agent.py"
    fake_script.write_text(
        """#!/usr/bin/env python3
import pathlib, re, sys, urllib.request

prompt = sys.argv[1]
rep = pathlib.Path("report.md")
text = rep.read_text(encoding="utf-8")

def fetch_all(urls):
    rows = {}
    for u in urls:
        html = urllib.request.urlopen(u, timeout=10).read().decode("utf-8")
        name = re.search(r"<h1>(.*?)</h1>", html).group(1)
        for lab, val in re.findall(r"<tr><td>(.*?)</td><td>(.*?)</td></tr>", html):
            rows[(name, lab)] = val
    return rows

if "Fill in report.md" in prompt:
    # c0 draft: fetch both pages, fill c01 correct, leave c02 missing, fabricate c03, wrong_read c04 (77 from p2)
    urls = sorted(set(re.findall(r"http://[a-z0-9.-]+/p\\d\\.html", prompt)))
    rows = fetch_all(urls)
    out = [
        "# Verification report",
        "",
        f"- Alpha — Price: {rows[('Alpha', 'Price')]}",
        "- Alpha — Users: ____",
        "- Beta — Version: v9.9.9",
        f"- Beta — Seats: {rows[('Beta', 'Other')]}",
    ]
    rep.write_text("\\n".join(out) + "\\n", encoding="utf-8")
elif "The following lines in report.md could not be verified" in prompt:
    # Arm T: fetch listed pages and fix ONLY the named lines
    urls = sorted(set(re.findall(r"http://[a-z0-9.-]+/p\\d\\.html", prompt)))
    rows = fetch_all(urls)
    lines = text.splitlines()
    out = []
    for ln in lines:
        if "[c02]" in prompt and ln.startswith("- Alpha — Users:"):
            ln = f"- Alpha — Users: {rows[('Alpha', 'Users')]}"
        elif "[c03]" in prompt and ln.startswith("- Beta — Version:"):
            ln = f"- Beta — Version: {rows[('Beta', 'Version')]}"
        out.append(ln)
    rep.write_text("\\n".join(out) + "\\n", encoding="utf-8")
elif "lines in your report have no supporting source" in prompt:
    # Arm T0: count-only feedback (no line ids or URLs) -> fixes c02 only on first call, leaves c03 fabricated
    lines = text.splitlines()
    out = []
    for ln in lines:
        if ln.startswith("- Alpha — Users:") and "____" in ln:
            ln = "- Alpha — Users: 120"
        out.append(ln)
    rep.write_text("\\n".join(out) + "\\n", encoding="utf-8")
elif prompt == "Please re-check your report for completeness and correctness and fix anything that is wrong.":
    # Arm G: generic review -> fixes c02, but breaks c01 (harm!)
    lines = text.splitlines()
    out = []
    for ln in lines:
        if ln.startswith("- Alpha — Price:"):
            ln = "- Alpha — Price: $999"
        elif ln.startswith("- Alpha — Users:") and "____" in ln:
            ln = "- Alpha — Users: 120"
        out.append(ln)
    rep.write_text("\\n".join(out) + "\\n", encoding="utf-8")
""",
        encoding="utf-8",
    )
    fake_script.chmod(0o755)

    plan = {
        "schema": "vacant.d2.expT.plan/1",
        "id": "e2e_flawed_fake",
        "seed": 123,
        "arms": ["A", "G", "T", "T0"],
        "reps": 2,
        "max_rounds": 2,
        "agent_timeout_s": 30,
        "budget_s": 90,
        "egress": True,
        "server": {"port": 0},
        "jobs": 1,
        "model": {"provider": "fake", "model": "fake"},
        "materials": [{"prefix": "syn", "dir": str(mat_dir), "manifest_sha256": msha, "sets": ["s01"]}],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    root = tmp_path / "run_out"

    rc = RT.ExpTRun(plan_path, root, fake=True, fake_agent_path=fake_script).go()
    assert rc == 0

    # Verify Arm T chain and early stop
    t_dir = root / "cells" / "syn-s01" / "r1" / "T"
    t_hist = FB.reconstruct(t_dir / "feedback_chain.ndjson", emit=False)
    assert [h["decision"] for h in t_hist] == ["send_feedback", "stop_no_flags"]
    assert t_hist[0]["evidence"]["flagged_ids"] == ["c02", "c03"]
    assert "[c02]" in t_hist[0]["feedback_text"]
    assert "[c03]" in t_hist[0]["feedback_text"]
    assert "[c01]" not in t_hist[0]["feedback_text"]
    assert "[c04]" not in t_hist[0]["feedback_text"]
    assert "http://syn-s01-r1.d2-sources.example/p1.html" in t_hist[0]["feedback_text"]
    assert "http://syn-s01-r1.d2-sources.example/p2.html" in t_hist[0]["feedback_text"]

    # Verify Arm T0 chain (count-only, no line ids)
    t0_dir = root / "cells" / "syn-s01" / "r1" / "T0"
    t0_hist = FB.reconstruct(t0_dir / "feedback_chain.ndjson", emit=False)
    assert t0_hist[0]["feedback_text"] == (
        "2 lines in your report have no supporting source in what you fetched; please check and fix them."
    )
    assert t0_hist[1]["feedback_text"] == (
        "1 lines in your report have no supporting source in what you fetched; please check and fix them."
    )

    # Verify Arm G chain (exact fixed generic prompt)
    g_dir = root / "cells" / "syn-s01" / "r1" / "G"
    g_hist = FB.reconstruct(g_dir / "feedback_chain.ndjson", emit=False)
    assert [h["decision"] for h in g_hist] == ["send_feedback", "send_feedback", "stop_max_rounds"]
    assert g_hist[0]["feedback_text"] == FB.GENERIC_REVIEW_PROMPT
    assert g_hist[1]["feedback_text"] == FB.GENERIC_REVIEW_PROMPT

    # Run expT_metrics.py CLI and inspect full output
    out_json = tmp_path / "metrics.json"
    proc = subprocess.run(
        [sys.executable, str(REPO / "ops" / "d2" / "expT_metrics.py"), str(root), "--boot", "300", "--json-out", str(out_json)],
        capture_output=True, text=True, check=True,
    )
    assert "Experiment T Metrics" in proc.stdout
    assert "T_vs_G [PRIMARY]" in proc.stdout

    m = json.loads(out_json.read_text(encoding="utf-8"))
    # Across 2 reps (8 total claims per arm):
    # A: 1/4 correct (0.25), errors: missing=2, fabricated=2, wrong_read=2, stale=0
    assert m["by_arm"]["A"]["correct_line_proportion_per_set"] == pytest.approx(0.25)
    assert m["by_arm"]["A"]["error_breakdown_before"]["missing"] == 2
    assert m["by_arm"]["A"]["error_breakdown_before"]["fabricated"] == 2
    assert m["by_arm"]["A"]["error_breakdown_before"]["wrong_read"] == 2
    assert m["by_arm"]["A"]["error_breakdown_before"]["stale"] == 0
    assert m["by_arm"]["A"]["harm"]["broken_after"] == 0

    # T: fixes c02 + c03 -> 3/4 correct (0.75), 0 harm, 100% of c0-flagged fixed, wrong_read remains (blind spot)
    assert m["by_arm"]["T"]["correct_line_proportion_per_set"] == pytest.approx(0.75)
    assert m["by_arm"]["T"]["error_breakdown_after"]["missing"] == 0
    assert m["by_arm"]["T"]["error_breakdown_after"]["fabricated"] == 0
    assert m["by_arm"]["T"]["error_breakdown_after"]["wrong_read"] == 2
    assert m["by_arm"]["T"]["harm"]["broken_after"] == 0
    assert m["by_arm"]["T"]["flagged_fixed"]["c0_flagged_fixed_rate"] == pytest.approx(1.0)
    assert m["by_arm"]["T"]["early_stopped_cells"] == 2

    # T0: fixes c02 only -> 2/4 correct (0.50), 50% of c0-flagged fixed, 0 harm
    assert m["by_arm"]["T0"]["correct_line_proportion_per_set"] == pytest.approx(0.50)
    assert m["by_arm"]["T0"]["flagged_fixed"]["c0_flagged_fixed_rate"] == pytest.approx(0.50)
    assert m["by_arm"]["T0"]["harm"]["broken_after"] == 0

    # G: fixes c02 but breaks c01 -> 1/4 correct (0.25), harm = 2/2 (1.0)
    assert m["by_arm"]["G"]["correct_line_proportion_per_set"] == pytest.approx(0.25)
    assert m["by_arm"]["G"]["harm"]["broken_after"] == 2
    assert m["by_arm"]["G"]["harm"]["harm_rate_over_correct_before"] == pytest.approx(1.0)

    # Paired comparisons
    assert m["comparisons"]["T_vs_G"]["per_set_correct_prop_diff"] == pytest.approx(0.50)
    assert m["comparisons"]["T_vs_G"]["per_set_correct_prop_diff_ci95"] == [0.5, 0.5]
    assert m["comparisons"]["T_vs_G"]["harm_not_more_than_control"] is True
    assert m["comparisons"]["T_vs_A"]["per_set_correct_prop_diff"] == pytest.approx(0.50)
    assert m["comparisons"]["G_vs_A"]["per_set_correct_prop_diff"] == pytest.approx(0.0)
    assert m["comparisons"]["T_vs_T0"]["per_set_correct_prop_diff"] == pytest.approx(0.25)
    assert m["readout"]["verdict"] == "T_useful"


# ---------------------------------------------------------------------------
# Plan validation & repo hygiene checks
# ---------------------------------------------------------------------------


def test_plans_structure_37_sets_and_no_leaks():
    q9_path = REPO / "ops" / "d2" / "plans" / "expT_qwen9b.json"
    e4_path = REPO / "ops" / "d2" / "plans" / "expT_colab_e4b.json"
    q9 = json.loads(q9_path.read_text(encoding="utf-8"))
    e4 = json.loads(e4_path.read_text(encoding="utf-8"))

    for plan in (q9, e4):
        assert plan["schema"] == "vacant.d2.expT.plan/1"
        assert plan["arms"] == ["A", "G", "T", "T0"]
        assert plan["reps"] == 2
        assert plan["max_rounds"] == 2
        assert len(plan["materials"]) == 2
        assert plan["materials"][0]["dir"] == "${D2_PRIVATE}/realrev2_sc"
        assert len(plan["materials"][0]["sets"]) == 17
        assert plan["materials"][1]["dir"] == "${D2_PRIVATE}/realrev2_football"
        assert len(plan["materials"][1]["sets"]) == 20
        ro = plan["prereg"]["frozen_readout"]
        assert "primary T vs G" in ro
        assert "≥10 percentage points" in ro
        assert "wrong_read recall" in ro
        assert "exploratory" in ro

    # Check 9B provider split covers all 37 sets disjointly
    p0, p1 = q9["providers"]
    assert p0["provider"] == "lms1003q9"
    assert p1["provider"] == "lms1004q9"
    s0, s1 = set(p0["sets"]), set(p1["sets"])
    assert len(s0) == 19 and len(s1) == 18
    assert s0.isdisjoint(s1)
    assert len(s0 | s1) == 37

    # Check Colab E4B provider matches ctl12_colab_e4b settings & documents requirements
    ep = e4["providers"][0]
    assert ep["provider"] == "colab-vllm-nothink"
    assert ep["model"] == "gemma-4-e4b-it-qat"
    assert ep["jobs"] == 12
    assert ep["health_url"] == "http://127.0.0.1:8000/v1/models"
    assert len(ep["sets"]) == 37
    assert "colab_requirements" in e4

    # Hygiene check: no absolute home paths or RFC1918/CGNAT internal IPs in any new Experiment T file
    abs_home_pat = "/" + "home/"
    priv_ip_pats = ("192" + ".168.", "10" + ".0.", "100" + ".64.")
    for p in (
        q9_path,
        e4_path,
        REPO / "ops" / "d2" / "expT_feedback.py",
        REPO / "ops" / "d2" / "run_expT.py",
        REPO / "ops" / "d2" / "expT_metrics.py",
    ):
        txt = p.read_text(encoding="utf-8")
        assert abs_home_pat not in txt, f"absolute home path found in {p}"
        for pat in priv_ip_pats:
            assert pat not in txt, f"internal IP found in {p}"
