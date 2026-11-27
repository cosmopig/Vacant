"""Unit and end-to-end tests for Experiment T (KS-1 templates, 7 arms, yoked G, snapshot pin, Haiku escalation, metrics)."""
from __future__ import annotations

import hashlib
import http.server
import io
import json
import os
import pathlib
import subprocess
import sys
import threading
from typing import Any

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "ops" / "d2") not in sys.path:
    sys.path.insert(0, str(REPO / "ops" / "d2"))

import expT_feedback as FB  # noqa: E402
import expT_metrics as EM  # noqa: E402
import run_expT as RT  # noqa: E402
from vacant_network.identity import Identity  # noqa: E402
from vacant_network.logbook import ChainError, Logbook  # noqa: E402
from vacant_network.memory import assert_ks1_clean as mem_assert_ks1_clean  # noqa: E402
from vacant_network.trace import review as REV  # noqa: E402
from vacant_network.trace.feedback import feedback_ks1_clean  # noqa: E402


def _sample_claims() -> list[dict]:
    return [
        {"id": "c01", "entity": "Alpha", "label": "Price", "template_line": "- Alpha — Price: "},
        {"id": "c02", "entity": "Alpha", "label": "Apps (goals)", "template_line": "- Alpha — Apps (goals): "},
        {"id": "c03", "entity": "Beta", "label": "Version", "template_line": "- Beta — Version: "},
        {"id": "c04", "entity": "Beta", "label": "Seats", "template_line": "- Beta — Seats: "},
    ]


# ---------------------------------------------------------------------------
# Unit tests: KS-1 templates, review.py reuse, WITHHELD replacement
# ---------------------------------------------------------------------------


def test_all_templates_pass_executable_ks1_and_review_reuse():
    rows = FB.verify_all_templates_ks1(actor_tokens={"qwen/qwen3.5-9b", "lms1003q9", "claude-haiku-5-5"})
    assert len(rows) >= 20
    assert all(r["ok"] for r in rows)

    report = FB.format_ks1_check_report()
    assert "所有提示與回饋模板已通過 KS-1 可執行檢查" in report
    assert f"TOTAL: {len(rows)}/{len(rows)} PASS" in report

    for name, tpl in FB.STATIC_TEMPLATES.items():
        mem_assert_ks1_clean(tpl)
        feedback_ks1_clean(tpl, {"qwen/qwen3.5-9b", "lms1003q9", "claude-haiku-5-5"})


def test_T_feedback_reuses_review_line_for_and_withholds_dirty_lines():
    assert FB.render_T_feedback([], ["http://s01.d2-sources.example/p1.html"]) == (None, 0)

    flagged = [
        {"claim_id": "c02", "label": "Alpha — Apps (goals)", "line": 4, "value": None,
         "reasons": [FB.PROBLEM_MISSING], "problem_kind": FB.PROBLEM_MISSING},
        {"claim_id": "c03", "label": "Beta — Version", "line": 5, "value": "v9.9.9",
         "reasons": [FB.PROBLEM_NOT_IN_FETCHED], "problem_kind": FB.PROBLEM_NOT_IN_FETCHED},
        {"claim_id": "c04", "label": "Beta — Seats", "line": 6, "value": "25",
         "reasons": [FB.PROBLEM_CHANGED_NO_SOURCE], "problem_kind": FB.PROBLEM_CHANGED_NO_SOURCE},
    ]
    urls = [
        "http://s01.d2-sources.example/p2.html",
        "http://s01.d2-sources.example/p1.html",
        "http://s01.d2-sources.example/p1.html",
    ]
    msg, withheld = FB.render_T_feedback(flagged, urls, actor_tokens={"qwen/qwen3.5-9b"})
    assert msg is not None
    assert withheld == 0

    expected_unsourced = REV.line_for({"kind": "unsourced", "path": "report.md", "line": 5, "value": "v9.9.9"})
    assert msg.startswith(REV.REVIEW_HEADER + "\n" + REV.PERSONA)
    assert msg.endswith(REV.FOOTER)
    assert FB.NO_VALUE_LINE_TEMPLATE.format(path="report.md", n=4) in msg
    assert expected_unsourced in msg
    assert FB.CHANGED_NO_SOURCE_LINE_TEMPLATE.format(path="report.md", n=6) in msg
    assert "Pages fetched in this task:\n- http://s01.d2-sources.example/p1.html\n- http://s01.d2-sources.example/p2.html" in msg

    # Dirty value containing actor token or KS-1 banned phrase -> replaced by WITHHELD and counted
    dirty_flagged = [
        {"claim_id": "c02", "label": "Alpha — Apps (goals)", "line": 4, "value": None,
         "reasons": [FB.PROBLEM_MISSING]},
        {"claim_id": "c03", "label": "Beta — Version", "line": 5, "value": "agent_secret_model_99",
         "reasons": [FB.PROBLEM_NOT_IN_FETCHED]},
        {"claim_id": "c04", "label": "Beta — Seats", "line": 6, "value": "you will be punished",
         "reasons": [FB.PROBLEM_NOT_IN_FETCHED]},
    ]
    dirty_msg, dirty_withheld = FB.render_T_feedback(
        dirty_flagged, [], actor_tokens={"agent_secret_model_99"},
    )
    assert dirty_msg is not None
    assert dirty_withheld == 2
    assert "agent_secret_model_99" not in dirty_msg
    assert "you will be punished" not in dirty_msg
    assert dirty_msg.count(REV.WITHHELD) == 2
    assert FB.NO_VALUE_LINE_TEMPLATE.format(path="report.md", n=4) in dirty_msg
    assert FB.T_FETCHED_NONE in dirty_msg


def test_TB_blank_only_and_TO_oracle_never_leaks_truth():
    claims = _sample_claims()
    truth_c0 = {"c01": "$40", "c02": "45 (3)", "c03": "v2.1.0", "c04": "25"}
    report = "\n".join([
        "# Report",
        "",
        "- Alpha — Price: $40",           # line 3: correct
        "- Alpha — Apps (goals): ____",   # line 4: missing
        "- Beta — Version: v9.9.9",       # line 5: fabricated
        "- Beta — Seats: 77",             # line 6: wrong_read
    ])

    # TB: flags ONLY line 4 (blank), no URLs, template (a)
    tb_fl = FB.compute_blank_flags(report, claims)
    assert tb_fl["flagged_ids"] == ["c02"]
    assert tb_fl["fetched_urls"] == []
    tb_msg, tb_w = FB.render_TB_feedback(tb_fl["flagged"])
    assert tb_w == 0 and tb_msg is not None
    assert FB.NO_VALUE_LINE_TEMPLATE.format(path="report.md", n=4) in tb_msg
    assert "line 5" not in tb_msg
    assert "line 6" not in tb_msg
    assert "Pages fetched" not in tb_msg

    # TO: flags lines 4, 5, 6 (including wrong_read!), NEVER leaks truth values!
    to_fl = FB.compute_oracle_flags(report, claims, truth_c0)
    assert to_fl["flagged_ids"] == ["c02", "c03", "c04"]
    to_fl_json = json.dumps(to_fl)
    for ans in ("45 (3)", "v2.1.0", "25"):
        assert ans not in to_fl_json
    to_msg, to_w = FB.render_TO_feedback(to_fl["flagged"])
    assert to_w == 0 and to_msg is not None
    for ln_no in (4, 5, 6):
        assert FB.ORACLE_WRONG_LINE_TEMPLATE.format(path="report.md", n=ln_no) in to_msg
    assert "line 3" not in to_msg
    for ans in ("$40", "45 (3)", "v2.1.0", "25"):
        assert ans not in to_msg


def test_G_fixed_prompt_and_ks1_clean():
    msg, w = FB.render_G_feedback(actor_tokens={"qwen/qwen3.5-9b"})
    assert w == 0
    assert msg == FB.GENERIC_REVIEW_PROMPT
    mem_assert_ks1_clean(msg)
    feedback_ks1_clean(msg, {"qwen/qwen3.5-9b"})


def test_compute_line_flags_F1_plaintext_and_F3_no_source_edit():
    claims = _sample_claims()
    html_p1 = "<html><body><h1>Alpha</h1><table><tr><td>Price</td><td>$40</td></tr><tr><td>45</td><td>(3)</td></tr></table></body></html>"
    html_p2 = "<html><body><h1>Beta</h1><table><tr><td>Version</td><td>v2.1.0</td></tr><tr><td>Seats</td><td>25</td></tr></table></body></html>"
    universe = [
        {"seq": 2, "url": "http://s01.d2-sources.example/p1.html", "text": html_p1, "source": "egress"},
        {"seq": 3, "url": "http://s01.d2-sources.example/p2.html", "text": html_p2, "source": "egress"},
    ]
    r0_text = "\n".join([
        "# Report",
        "",
        "- Alpha — Price: $40",
        "- Alpha — Apps (goals): 45 (3)",
        "- Beta — Version: ____",
        "- Beta — Seats: 999",
    ])
    fr0 = FB.compute_line_flags(
        r0_text, claims, universe, round_idx=0, prev_values=None, prev_bound_seq=0, cur_bound_seq=5,
    )
    assert fr0["flagged_ids"] == ["c03", "c04"]
    assert fr0["flags_by_claim"]["c03"]["line"] == 5
    assert fr0["flags_by_claim"]["c04"]["line"] == 6
    assert fr0["supported_count"] == 2
    assert fr0["blank_count"] == 1

    # Round 1 without fetch -> F3 fires on changed lines
    r1_text = "\n".join([
        "# Report",
        "",
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
    assert fr1["flags_by_claim"]["c01"]["F3"] is True

    # Round 1 WITH fetch -> F3 does NOT fire
    fr1_fetched = FB.compute_line_flags(
        r1_text, claims,
        [*universe, {"seq": 6, "url": "http://s01.d2-sources.example/p2.html", "text": html_p2, "source": "egress"}],
        round_idx=1, prev_values=fr0["values"], prev_bound_seq=5, cur_bound_seq=8,
    )
    assert fr1_fetched["flagged_ids"] == []


# ---------------------------------------------------------------------------
# Unit tests: Signed Logbook chain (feedback & escalation) + tamper detection
# ---------------------------------------------------------------------------


def test_signed_feedback_and_escalation_chain_tamper_detection(tmp_path: pathlib.Path):
    ident = Identity.generate()
    book = Logbook()
    flagged = [{"claim_id": "c02", "label": "Alpha — Apps (goals)", "line": 4, "value": None,
                "F1": True, "F3": False, "reasons": [FB.PROBLEM_MISSING], "problem_kind": FB.PROBLEM_MISSING}]
    urls = ["http://s01.d2-sources.example/p1.html"]
    ev1 = FB.make_trigger_evidence("T", 0, {"flagged": flagged, "fetched_urls": urls, "round_fetch_count": 1})
    fb1, w1 = FB.render_T_feedback(flagged, urls)
    FB.feedback_event(book, ident, arm="T", round_idx=1, decision="send_feedback", feedback_text=fb1, evidence=ev1, withheld=w1, ts_ms=1000)
    FB.escalation_event(
        book, ident, arm="TE", decision="escalate_haiku", model="claude-haiku-5-5",
        escalated_claim_ids=["c02"], fetched_urls=urls, prompt_sha256="a" * 64, response_sha256="b" * 64,
        input_tokens=500, output_tokens=50, cost_usd=0.00075, withheld=0, ts_ms=2000,
    )

    chain_path = tmp_path / "feedback_chain.ndjson"
    FB.save_feedback_chain(book, ident, chain_path)

    buf = io.StringIO()
    hist = FB.reconstruct(chain_path, stream=buf)
    assert len(hist) == 2
    assert hist[0]["type"] == FB.EXPT_EVENT_TYPE
    assert hist[1]["type"] == FB.EXPT_ESCALATION_EVENT_TYPE
    assert hist[1]["cost_usd"] == 0.00075
    assert "decision=escalate_haiku" in buf.getvalue()

    # Tamper payload -> ChainError
    raw_lines = chain_path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(raw_lines[1])
    tampered["payload"]["cost_usd"] = 999.0
    tp = tmp_path / "tampered.ndjson"
    tp.write_text(raw_lines[0] + "\n" + json.dumps(tampered) + "\n", encoding="utf-8")
    tp.with_suffix(".pub.json").write_text(chain_path.with_suffix(".pub.json").read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ChainError):
        FB.reconstruct(tp, emit=False)


# ---------------------------------------------------------------------------
# Unit tests: Haiku escalation HTTP call, line replacement, key hygiene, TER selection
# ---------------------------------------------------------------------------


class _FakeAnthropicServer:
    """Loopback fake Anthropic Messages API server for offline testing (never touches real API)."""

    def __init__(self, reply_fn):
        self.reply_fn = reply_fn
        self.requests: list[dict[str, Any]] = []
        self._srv: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self):
        parent = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                parent.requests.append({
                    "path": self.path,
                    "has_api_key": bool(self.headers.get("x-api-key")),
                    "api_key_value": self.headers.get("x-api-key"),
                    "body": body,
                })
                resp_text, in_tok, out_tok = parent.reply_fn(body)
                payload = json.dumps({
                    "id": "msg_fake_001",
                    "type": "message",
                    "role": "assistant",
                    "model": body.get("model", "claude-haiku-5-5"),
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": resp_text}],
                    "usage": {"input_tokens": in_tok, "output_tokens": out_tok},
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self._srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._srv.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}/v1/messages"
        self._thread = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        if self._srv:
            self._srv.shutdown()
            self._srv.server_close()


def test_haiku_escalation_fake_http_key_hygiene_and_strict_line_replacement(monkeypatch, tmp_path: pathlib.Path):
    fake_secret = "sk-ant-test-NEVER-LOG-THIS-SECRET-987654"
    monkeypatch.setenv("ANTHROPIC_API_KEY", fake_secret)

    # Haiku tries to return c01 (NOT escalated!), c02 (found), and c03 (not found in sources)
    def reply_fn(body):
        assert body["model"] == "claude-haiku-5-5"
        return "[c01]: $9999\n[c02]: 120\n[c03]: not found in sources", 1200, 80

    with _FakeAnthropicServer(reply_fn) as srv:
        claims = _sample_claims()
        report = "\n".join([
            "# Verification report",
            "",
            "- Alpha — Price: $40",
            "- Alpha — Apps (goals): ____",
            "- Beta — Version: v9.9.9",
            "- Beta — Seats: 77",
        ]) + "\n"

        sys_p, user_p, w = FB.build_haiku_escalation_prompt(
            [claims[1], claims[2]],
            {"c01": "$40", "c02": None, "c03": "v9.9.9", "c04": "77"},
            [{"url": "http://s01.d2-sources.example/p1.html", "text": "Alpha | Apps (goals) | 120"}],
        )
        assert w == 0
        res = FB.call_haiku_messages_api(
            system_prompt=sys_p, user_prompt=user_p, api_url=srv.url, model="claude-haiku-5-5",
        )
        assert len(srv.requests) == 1
        assert srv.requests[0]["api_key_value"] == fake_secret
        assert fake_secret not in json.dumps(res)
        assert res["input_tokens"] == 1200
        assert res["output_tokens"] == 80
        assert res["cost_usd"] == pytest.approx(0.0016)

        extracted = FB.parse_haiku_escalation_response(res["text"], ["c02", "c03"])
        assert "c01" not in extracted
        assert extracted == {"c02": "120", "c03": None}

        updated = FB.apply_haiku_replacements(report, claims, ["c02", "c03"], extracted)
        lines = updated.splitlines()
        # Non-escalated lines c01 and c04 are byte-for-byte untouched!
        assert lines[2] == "- Alpha — Price: $40"
        assert lines[3] == "- Alpha — Apps (goals): 120"
        assert lines[4] == "- Beta — Version: not found in sources"
        assert lines[5] == "- Beta — Seats: 77"

        # Ledger append contains no key
        ledger = tmp_path / "credit_ledger.jsonl"
        FB.append_credit_ledger(
            ledger, purpose="expT TE/TER", model=res["model"],
            input_tokens=res["input_tokens"], output_tokens=res["output_tokens"],
            cost_usd=res["cost_usd"], cell="syn-s01/r1/TE",
        )
        txt = ledger.read_text(encoding="utf-8")
        assert fake_secret not in txt
        rec = json.loads(txt.strip())
        assert rec["purpose"] == "expT TE/TER"
        assert rec["cell"] == "syn-s01/r1/TE"
        assert rec["cost_usd"] == pytest.approx(0.0016)

    # Deterministic seeded TER sampling
    s1, seed1 = FB.select_TER_claims(_sample_claims(), 2, seed=42, set_id="syn-s01", rep=1)
    s2, seed2 = FB.select_TER_claims(_sample_claims(), 2, seed=42, set_id="syn-s01", rep=1)
    assert seed1 == seed2
    assert [c["id"] for c in s1] == [c["id"] for c in s2]
    assert len(s1) == 2

    # Frozen fetched pages loader ONLY includes pages in this cell's egress fetched_urls
    site_frozen = tmp_path / "site_frozen"
    site_frozen.mkdir()
    (site_frozen / "p1.html").write_text("<html><body>Alpha 120</body></html>", encoding="utf-8")
    (site_frozen / "p2.html").write_text("<html><body>SECRET_UNFETCHED_PAGE 999</body></html>", encoding="utf-8")
    loaded = FB.load_frozen_fetched_pages(["http://syn-s01-r1.d2-sources.example/p1.html"], site_frozen)
    assert len(loaded) == 1
    assert loaded[0]["path"] == "p1.html"
    assert "Alpha 120" in loaded[0]["text"]
    assert all("SECRET_UNFETCHED_PAGE" not in pg["text"] for pg in loaded)


# ---------------------------------------------------------------------------
# End-to-end tests: 1 set x 7 arms (clean draft + flawed draft + snapshot pin + metrics)
# ---------------------------------------------------------------------------


def _make_synthetic_materials(mat_dir: pathlib.Path) -> tuple[pathlib.Path, str]:
    sdir = mat_dir / "sets" / "s01"
    site0 = sdir / "cycle_0" / "site"
    site0.mkdir(parents=True)
    (site0 / "p1.html").write_text(
        "<!doctype html><html><body><h1>Alpha</h1>"
        "<table><tr><td>Price</td><td>$40</td></tr>"
        "<tr><td>Users</td><td>120</td></tr></table></body></html>\n",
        encoding="utf-8",
    )
    (site0 / "p2.html").write_text(
        "<!doctype html><html><body><h1>Beta</h1>"
        "<table><tr><td>Version</td><td>v2.1.0</td></tr>"
        "<tr><td>Seats</td><td>25</td></tr>"
        "<tr><td>Other</td><td>77</td></tr></table></body></html>\n",
        encoding="utf-8",
    )
    # Also create cycle_1 with DIFFERENT content to verify revision-0 snapshot pinning!
    site1 = sdir / "cycle_1" / "site"
    site1.mkdir(parents=True)
    (site1 / "p1.html").write_text(
        "<!doctype html><html><body><h1>Alpha</h1>"
        "<table><tr><td>Price</td><td>$999</td></tr>"
        "<tr><td>Users</td><td>888</td></tr></table></body></html>\n",
        encoding="utf-8",
    )
    (site1 / "p2.html").write_text(
        "<!doctype html><html><body><h1>Beta</h1>"
        "<table><tr><td>Version</td><td>v8.8.8</td></tr>"
        "<tr><td>Seats</td><td>88</td></tr></table></body></html>\n",
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


def test_e2e_clean_draft_yoked_G_zero_rounds_and_zero_haiku_calls(monkeypatch, tmp_path: pathlib.Path):
    """When shared c0 draft has 0 flags: T stops at 0 rounds, G is yoked to 0 rounds, TE/TER make 0 API calls."""
    mat_dir, msha = _make_synthetic_materials(tmp_path / "mat")
    ledger = tmp_path / "ledger.jsonl"

    called_haiku = []

    def fail_if_called(**kwargs):
        called_haiku.append(kwargs)
        raise AssertionError("Haiku must not be called when 0 lines are flagged")

    plan = {
        "schema": "vacant.d2.expT.plan/2",
        "id": "e2e_clean_7arms",
        "seed": 42,
        "arms": ["A", "G", "T", "TB", "TO", "TE", "TER"],
        "reps": 1,
        "max_rounds": 2,
        "agent_timeout_s": 30,
        "budget_s": 90,
        "egress": True,
        "server": {"port": 0},
        "jobs": 1,
        "escalation": {"model": "claude-haiku-5-5", "ledger_path": str(ledger)},
        "model": {"provider": "fake", "model": "fake"},
        "materials": [{"prefix": "syn", "dir": str(mat_dir), "manifest_sha256": msha, "sets": ["s01"]}],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    root = tmp_path / "run_out"

    rc = RT.ExpTRun(plan_path, root, fake=True, haiku_caller=fail_if_called).go()
    assert rc == 0
    assert called_haiku == []
    assert not ledger.exists()

    # T was scheduled before G in arm_orders
    orders = json.loads((root / "arm_orders.json").read_text(encoding="utf-8"))["syn-s01/r1"]
    assert orders.index("T") < orders.index("G")

    for arm in plan["arms"]:
        adir = root / "cells" / "syn-s01" / "r1" / arm
        cell = json.loads((adir / "cell.json").read_text(encoding="utf-8"))
        assert cell["infra_void"] is False
        assert cell["rounds_run"] == 0
        hist = FB.reconstruct(adir / "feedback_chain.ndjson", emit=False)
        assert len(hist) >= 1
        if arm == "G":
            assert cell["stop_reason"] == "stop_yoked_no_flags"
            assert hist[0]["decision"] == "stop_yoked_no_flags"
        elif arm in ("T", "TB", "TO", "TE", "TER"):
            assert cell["stop_reason"] == "stop_no_flags"

    res = EM.analyze_root(root, n_boot=200, seed=7)
    assert res["snapshot_pin"]["ok"] is True
    assert res["readout"]["indistinguishable"] is True  # A = 100% > 85% and T sent feedback in 0% < 25%


def test_e2e_flawed_draft_1set_7arms_snapshot_pin_yoked_G_and_metrics(monkeypatch, tmp_path: pathlib.Path):
    """Full e2e on 1 set x 7 arms x 2 reps:
      - Verifies shared draft, revision-0 snapshot pinning, ANTHROPIC_API_KEY stripped from agent sandbox,
        T (review.py unsourced + template a), yoked G (exact 1 round matching T, triggers harm C->W + B->W),
        TB (blank-only), TO (oracle catches wrong_read without leaking truth), TE & TER via fake HTTP Haiku server
        + credit ledger + signed chains, plus whole-report Haiku reference point and offline draft selection.
    """
    fake_secret = "sk-ant-e2e-SECRET-MUST-NOT-LEAK-42"
    monkeypatch.setenv("ANTHROPIC_API_KEY", fake_secret)
    mat_dir, msha = _make_synthetic_materials(tmp_path / "mat")
    ledger = tmp_path / "credit_ledger.jsonl"

    # Fake agent that also asserts ANTHROPIC_API_KEY is NOT in its sandbox environment!
    fake_script = tmp_path / "flawed_fake_agent.py"
    fake_script.write_text(
        """#!/usr/bin/env python3
import os, pathlib, re, sys, urllib.request

assert "ANTHROPIC_API_KEY" not in os.environ, "ANTHROPIC_API_KEY leaked into agent sandbox!"
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
    urls = sorted(set(re.findall(r"http://[a-z0-9.-]+/p\\d\\.html", prompt)))
    rows = fetch_all(urls)
    # Verify cycle_0 content (never cycle_1 $999!)
    assert rows[("Alpha", "Price")] == "$40"
    out = [
        "# Verification report",
        "",
        f"- Alpha — Price: {rows[('Alpha', 'Price')]}",
        "- Alpha — Users: ____",
        "- Beta — Version: v9.9.9",
        f"- Beta — Seats: {rows[('Beta', 'Other')]}",
    ]
    rep.write_text("\\n".join(out) + "\\n", encoding="utf-8")
elif "review of the recorded steps" in prompt:
    # Arm T: refetch frozen pages and fix ONLY flagged lines (line 4 missing + line 5 unsourced)
    urls = sorted(set(re.findall(r"http://[a-z0-9.-]+/p\\d\\.html", prompt)))
    rows = fetch_all(urls)
    lines = text.splitlines()
    out = []
    for idx, ln in enumerate(lines, start=1):
        if f"report.md line {idx}:" in prompt and ln.startswith("- Alpha — Users:"):
            ln = f"- Alpha — Users: {rows[('Alpha', 'Users')]}"
        elif f"report.md line {idx}:" in prompt and ln.startswith("- Beta — Version:"):
            ln = f"- Beta — Version: {rows[('Beta', 'Version')]}"
        out.append(ln)
    rep.write_text("\\n".join(out) + "\\n", encoding="utf-8")
elif "lines in report.md without values" in prompt:
    # Arm TB: blank-only -> fixes line 4 only (no URLs given)
    lines = text.splitlines()
    out = []
    for idx, ln in enumerate(lines, start=1):
        if f"report.md line {idx}:" in prompt and ln.startswith("- Alpha — Users:"):
            ln = "- Alpha — Users: 120"
        out.append(ln)
    rep.write_text("\\n".join(out) + "\\n", encoding="utf-8")
elif "this value may be wrong" in prompt:
    # Arm TO: oracle flagged lines 4, 5, 6 (including wrong_read line 6!) -> fixes all 3
    lines = text.splitlines()
    out = []
    for idx, ln in enumerate(lines, start=1):
        if f"report.md line {idx}:" in prompt:
            if ln.startswith("- Alpha — Users:"):
                ln = "- Alpha — Users: 120"
            elif ln.startswith("- Beta — Version:"):
                ln = "- Beta — Version: v2.1.0"
            elif ln.startswith("- Beta — Seats:"):
                ln = "- Beta — Seats: 25"
        out.append(ln)
    rep.write_text("\\n".join(out) + "\\n", encoding="utf-8")
elif "Re-check report.md for completeness and correctness" in prompt:
    # Arm G: generic review -> breaks c01 (correct->wrong) AND fills blank c02 with wrong value (blank->wrong)!
    lines = text.splitlines()
    out = []
    for ln in lines:
        if ln.startswith("- Alpha — Price:"):
            ln = "- Alpha — Price: $999"
        elif ln.startswith("- Alpha — Users:") and "____" in ln:
            ln = "- Alpha — Users: 555"
        out.append(ln)
    rep.write_text("\\n".join(out) + "\\n", encoding="utf-8")
""",
        encoding="utf-8",
    )
    fake_script.chmod(0o755)

    # Fake Haiku HTTP endpoint parses the requested lines & frozen page texts strictly
    def haiku_reply(body):
        user_txt = body["messages"][0]["content"]
        ans_map = {"c01": "$40", "c02": "120", "c03": "v2.1.0", "c04": "25"}
        out_lines = []
        for cid in ("c01", "c02", "c03", "c04"):
            if f"- [{cid}]" in user_txt:
                out_lines.append(f"[{cid}]: {ans_map[cid]}")
        return "\n".join(out_lines), 1000, 100

    with _FakeAnthropicServer(haiku_reply) as srv:
        plan = {
            "schema": "vacant.d2.expT.plan/2",
            "id": "e2e_flawed_7arms",
            "seed": 123,
            "arms": ["A", "G", "T", "TB", "TO", "TE", "TER"],
            "reps": 2,
            "max_rounds": 2,
            "agent_timeout_s": 30,
            "budget_s": 90,
            "egress": True,
            "server": {"port": 0},
            "jobs": 1,
            "escalation": {
                "model": "claude-haiku-5-5",
                "api_url": srv.url,
                "max_tokens": 256,
                "price_per_mtok_in": 1.0,
                "price_per_mtok_out": 5.0,
                "ledger_path": str(ledger),
            },
            "model": {"provider": "fake", "model": "fake"},
            "materials": [{"prefix": "syn", "dir": str(mat_dir), "manifest_sha256": msha, "sets": ["s01"]}],
        }
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        root = tmp_path / "run_out"

        rc = RT.ExpTRun(plan_path, root, fake=True, fake_agent_path=fake_script).go()
        assert rc == 0

        # Haiku called once per TE cell (2 reps) + once per TER cell (2 reps) = 4 calls
        assert len(srv.requests) == 4
        ledger_lines = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
        assert len(ledger_lines) == 4
        assert all(x["purpose"] == "expT TE/TER" and x["model"] == "claude-haiku-5-5" for x in ledger_lines)
        assert fake_secret not in ledger.read_text(encoding="utf-8")

    # Verify T ran 1 round & stopped early; G matched T with EXACTLY 1 round (yoked!)
    t_cell = json.loads((root / "cells" / "syn-s01" / "r1" / "T" / "cell.json").read_text(encoding="utf-8"))
    g_cell = json.loads((root / "cells" / "syn-s01" / "r1" / "G" / "cell.json").read_text(encoding="utf-8"))
    assert t_cell["rounds_run"] == 1
    assert t_cell["stop_reason"] == "stop_no_flags"
    assert g_cell["rounds_run"] == 1
    assert g_cell["stop_reason"] == "stop_yoked_rounds_matched"

    # Verify TO feedback never leaked any truth value
    to_fb = (root / "cells" / "syn-s01" / "r1" / "TO" / "round_1" / "feedback.txt").read_text(encoding="utf-8")
    for ans in ("$40", "120", "v2.1.0", "25"):
        assert ans not in to_fb

    # Verify API key never leaked into any file in run_out
    for p in root.rglob("*"):
        if p.is_file():
            assert fake_secret not in p.read_text(encoding="utf-8", errors="ignore")

    # Build a synthetic whole-report Haiku reference root (4/4 correct, $0.01/report)
    hf_root = tmp_path / "haiku_full_ref"
    for rep in (1, 2):
        hdir = hf_root / "cells" / "syn-s01" / f"r{rep}" / "A"
        hdir.mkdir(parents=True)
        (hdir / "report.md").write_text(
            "# Verification report\n\n- Alpha — Price: $40\n- Alpha — Users: 120\n- Beta — Version: v2.1.0\n- Beta — Seats: 25\n",
            encoding="utf-8",
        )
        (hdir / "cell.json").write_text(json.dumps({"cost_usd": 0.01, "total_usage": {"input": 5000, "output": 1000}}), encoding="utf-8")

    out_json = tmp_path / "metrics.json"
    proc = subprocess.run(
        [
            sys.executable, str(REPO / "ops" / "d2" / "expT_metrics.py"),
            str(root), "--haiku-full-root", str(hf_root),
            "--boot", "300", "--json-out", str(out_json),
        ],
        capture_output=True, text=True, check=True,
    )
    assert "Experiment T Metrics" in proc.stdout
    assert "T_vs_G [PRIMARY]" in proc.stdout
    assert "T_vs_TB [PRIMARY]" in proc.stdout
    assert "T_vs_TO [PRIMARY]" in proc.stdout
    assert "TE_vs_TER [PRIMARY]" in proc.stdout
    assert "trading errors for fills" in proc.stdout

    m = json.loads(out_json.read_text(encoding="utf-8"))
    assert m["snapshot_pin"]["ok"] is True
    assert m["snapshot_pin"]["requests_checked"] >= 4

    # Primary metrics (a), (b), (c)
    assert m["by_arm"]["A"]["correct_line_proportion_per_set"] == pytest.approx(0.25)
    assert m["by_arm"]["A"]["filled_precision_per_set"] == pytest.approx(1 / 3, rel=1e-3)
    assert m["by_arm"]["A"]["harm"]["correct_to_wrong_or_deleted"] == 0
    assert m["by_arm"]["A"]["harm"]["blank_to_wrong"] == 0

    assert m["by_arm"]["T"]["correct_line_proportion_per_set"] == pytest.approx(0.75)
    assert m["by_arm"]["T"]["filled_precision_per_set"] == pytest.approx(0.75)
    assert m["by_arm"]["T"]["harm"]["correct_to_wrong_or_deleted"] == 0
    assert m["by_arm"]["T"]["harm"]["blank_to_wrong"] == 0

    assert m["by_arm"]["TB"]["correct_line_proportion_per_set"] == pytest.approx(0.50)
    assert m["by_arm"]["TO"]["correct_line_proportion_per_set"] == pytest.approx(1.00)

    # G caused BOTH harm types: 2 C->W + 2 B->W across 2 reps!
    assert m["by_arm"]["G"]["correct_line_proportion_per_set"] == pytest.approx(0.0)
    assert m["by_arm"]["G"]["harm"]["correct_to_wrong_or_deleted"] == 2
    assert m["by_arm"]["G"]["harm"]["blank_to_wrong"] == 2
    assert "G" in m["readout"]["harm_warnings"]
    assert m["readout"]["harm_warnings"]["G"]["label"] == "trading errors for fills"

    # TE fixed c02 & c03 -> 0.75, cost = $0.0015/report vs $0.01 Haiku-full -> 85% cost saving!
    assert m["by_arm"]["TE"]["correct_line_proportion_per_set"] == pytest.approx(0.75)
    assert m["by_arm"]["TE"]["haiku"]["cost_usd_mean_per_report"] == pytest.approx(0.0015)
    assert m["readout"]["TE_vs_haiku_full"]["provided"] is True
    assert m["readout"]["TE_vs_haiku_full"]["cost_saving_pct"] == pytest.approx(0.85)
    assert m["readout"]["TE_vs_haiku_full"]["correctness_gap_te_minus_haiku_full"] == pytest.approx(-0.25)

    assert m["readout"]["T_vs_G"]["verdict"] == "T_beats_G"
    assert m["readout"]["T_vs_TB"]["verdict"] == "record_adds_value"
    assert m["readout"]["verdict"] == "T_useful_and_record_adds_value"


# ---------------------------------------------------------------------------
# Unit tests: Readout edge cases & secondary offline draft selection
# ---------------------------------------------------------------------------


def test_readout_indistinguishable_and_T_vs_TB_threshold():
    # A > 85% -> indistinguishable
    ro1 = EM.evaluate_readout(
        {"A": {"correct_line_proportion_per_set": 0.90}, "T": {"feedback_sent_rate": 0.80}},
        {"T_vs_G": {"per_set_correct_prop_diff": 0.12, "per_set_correct_prop_diff_ci95": [0.05, 0.20], "harm_not_more_than_control": True}},
    )
    assert ro1["indistinguishable"] is True
    assert ro1["verdict"] == "indistinguishable"

    # A < 10% -> indistinguishable
    ro2 = EM.evaluate_readout(
        {"A": {"correct_line_proportion_per_set": 0.05}, "T": {"feedback_sent_rate": 0.80}},
        {},
    )
    assert ro2["indistinguishable"] is True

    # T sent feedback < 1/4 of cells -> indistinguishable
    ro3 = EM.evaluate_readout(
        {"A": {"correct_line_proportion_per_set": 0.50}, "T": {"feedback_sent_rate": 0.20}},
        {},
    )
    assert ro3["indistinguishable"] is True

    # T vs TB < 5pp -> explicitly says record does not add value
    ro4 = EM.evaluate_readout(
        {"A": {"correct_line_proportion_per_set": 0.50}, "T": {"feedback_sent_rate": 0.60}},
        {
            "T_vs_G": {"per_set_correct_prop_diff": 0.15, "per_set_correct_prop_diff_ci95": [0.05, 0.25], "harm_not_more_than_control": True},
            "T_vs_TB": {"per_set_correct_prop_diff": 0.03, "per_set_correct_prop_diff_ci95": [-0.01, 0.07]},
            "TE_vs_TER": {"per_set_correct_prop_diff": 0.08, "per_set_correct_prop_diff_ci95": [0.02, 0.14]},
        },
    )
    assert ro4["T_vs_TB"]["verdict"] == "record_does_not_add_value"
    assert "does not add value" in ro4["T_vs_TB"]["reason"]
    assert ro4["TE_vs_TER"]["verdict"] == "TE_does_not_beat_TER"
    assert ro4["verdict"] == "T_beats_G_but_indistinguishable_from_TB"


def test_secondary_offline_draft_selection_evidence_score_and_tiebreak():
    drafts_by_set = {
        "s01": [
            # Higher evidence score (3 - 1 = +2) -> picked (correct_prop=0.75)
            {"draft_id": "r1", "supported_count": 3, "unsupported_count": 1, "blank_count": 1, "evidence_score": 2, "correct_prop": 0.75},
            {"draft_id": "r2", "supported_count": 1, "unsupported_count": 3, "blank_count": 2, "evidence_score": -2, "correct_prop": 0.25},
        ],
        "s02": [
            # Exact tie on evidence_score (0 vs 0): tie broken by FEWER BLANKS (0 < 2)!
            {"draft_id": "r1", "supported_count": 2, "unsupported_count": 2, "blank_count": 2, "evidence_score": 0, "correct_prop": 0.50},
            {"draft_id": "r2", "supported_count": 2, "unsupported_count": 2, "blank_count": 0, "evidence_score": 0, "correct_prop": 1.00},
        ],
    }
    res = EM.analyze_draft_selection(drafts_by_set, n_boot=300, seed=11)
    assert res["sets_evaluated"] == 2
    assert res["record_pick_correct_prop"] == pytest.approx(0.875)
    assert res["random_pick_correct_prop"] == pytest.approx(0.625)
    assert res["oracle_best_correct_prop"] == pytest.approx(0.875)
    assert res["record_vs_random_diff"] == pytest.approx(0.25)
    assert res["oracle_hit_rate"] == pytest.approx(1.0)
    by_s = {x["set"]: x for x in res["per_set"]}
    assert by_s["s01"]["record_pick_draft"] == "r1"
    assert by_s["s02"]["record_pick_draft"] == "r2"  # fewer blanks won tie!


# ---------------------------------------------------------------------------
# Plan validation & repo hygiene checks
# ---------------------------------------------------------------------------


def test_plans_structure_7arms_prereg_ks1_verbatim_and_hygiene():
    q9_path = REPO / "ops" / "d2" / "plans" / "expT_qwen9b.json"
    e4_path = REPO / "ops" / "d2" / "plans" / "expT_colab_e4b.json"
    q9 = json.loads(q9_path.read_text(encoding="utf-8"))
    e4 = json.loads(e4_path.read_text(encoding="utf-8"))

    expected_ks1_out = FB.format_ks1_check_report()

    for plan in (q9, e4):
        assert plan["schema"] == "vacant.d2.expT.plan/2"
        assert plan["arms"] == ["A", "G", "T", "TB", "TO", "TE", "TER"]
        assert "T0" not in plan["arms"]
        assert plan["reps"] == 2
        assert plan["max_rounds"] == 2
        assert "haiku_full_root" in plan
        assert plan["escalation"]["model"] == "claude-haiku-5-5"
        assert len(plan["materials"]) == 2
        assert len(plan["materials"][0]["sets"]) == 17
        assert len(plan["materials"][1]["sets"]) == 20

        pr = plan["prereg"]
        assert pr["ks1_check"]["status"] == "所有提示與回饋模板已通過 KS-1 可執行檢查"
        assert pr["ks1_check"]["output"] == expected_ks1_out
        assert pr["ks1_check"]["templates_verbatim"] == FB.STATIC_TEMPLATES

        ro = pr["frozen_readout"]
        for needle in ("T vs G", "T vs TB", "T vs TO", "TE vs TER", "≥5 percentage points", "≥10 pp", "trading errors for fills", ">85%", "<10%", "1/4"):
            assert needle in ro
        assert "vacant-cloud" in pr["recorded_prediction"]
        assert "TB" in pr["recorded_prediction"]
        assert "reduce reps from 2 to 1" in pr["budget_fallback"]
        assert "drop TO" in pr["budget_fallback"]
        assert "never drop G, TB or TER" in pr["budget_fallback"]
        assert "RECORD-ONLY evidence score" in pr["secondary_analysis"]
        assert any("closest passage" in x.lower() for x in pr["later"])

    # Check 9B provider split covers all 37 sets disjointly
    p0, p1 = q9["providers"]
    assert p0["provider"] == "lms1003q9"
    assert p1["provider"] == "lms1004q9"
    s0, s1 = set(p0["sets"]), set(p1["sets"])
    assert len(s0) == 19 and len(s1) == 18 and s0.isdisjoint(s1) and len(s0 | s1) == 37

    # Hygiene check: no absolute home paths or RFC1918/CGNAT internal IPs in any Experiment T file
    abs_home_pat = "/" + "home/"
    priv_ip_pats = ("192" + ".168.", "10" + ".0.", "100" + ".64.")
    for p in (
        q9_path,
        e4_path,
        REPO / "ops" / "d2" / "expT_feedback.py",
        REPO / "ops" / "d2" / "run_expT.py",
        REPO / "ops" / "d2" / "expT_metrics.py",
        REPO / "tests" / "test_expT.py",
    ):
        txt = p.read_text(encoding="utf-8")
        assert abs_home_pat not in txt, f"absolute home path found in {p}"
        for pat in priv_ip_pats:
            assert pat not in txt, f"internal IP found in {p}"
