"""Tests for ops/d2/report_d2.py (pure table builders + end-to-end synthetic root)."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
for _p in (str(REPO / "ops" / "d2"), str(REPO / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import analyze_d2 as A  # noqa: E402
import report_d2 as R  # noqa: E402
import score_d2 as S  # noqa: E402
from test_d2_analysis import _make_synthetic  # noqa: E402


# ---------------------------------------------------------------------------
# Pure function unit tests
# ---------------------------------------------------------------------------

def test_conclusion_all_four_verdicts_factual():
    """build_conclusion + render_conclusion produce exact gate values for all 4 verdicts."""
    # 1. EFFECTIVE
    sd_eff, costs_eff = _make_synthetic(n_sets=10)
    an_eff = A.analyze(
        sd_eff, costs_eff,
        {"coverage": {"claims": 200, "with_source": 200, "correct_page": 190}},
        n_boot=300, seed=20261125,
    )
    c_eff = R.build_conclusion(an_eff)
    assert c_eff["verdict"] == "EFFECTIVE"
    assert "EFFECTIVE" in c_eff["sentence"]
    assert "190/200 = 95.00%" in c_eff["sentence"]
    assert "NONINFERIOR" in c_eff["sentence"]
    assert "5.00x" in c_eff["sentence"]
    md_eff = R.render_conclusion(c_eff)
    assert md_eff.startswith("## 1. 一句話結論")

    # 2. FAIL (coverage < 0.80)
    an_fail = A.analyze(
        sd_eff, costs_eff,
        {"coverage": {"claims": 200, "with_source": 180, "correct_page": 150}},
        n_boot=300, seed=20261125,
    )
    c_fail = R.build_conclusion(an_fail)
    assert c_fail["verdict"] == "FAIL"
    assert "150/200 = 75.00%" in c_fail["sentence"]
    assert "FAIL" in c_fail["sentence"]

    # 3. UNRESOLVED (no audit coverage)
    an_unres = A.analyze(sd_eff, costs_eff, audit_data=None, n_boot=300, seed=20261125)
    c_unres = R.build_conclusion(an_unres)
    assert c_unres["verdict"] == "UNRESOLVED"
    assert "無資料" in c_unres["sentence"]

    # 4. INCOMPLETE (missing set/arm/cycle)
    sd_inc, costs_inc = _make_synthetic(n_sets=4)
    sd_inc["rows"] = [r for r in sd_inc["rows"] if not (r["set"] == "s02" and r["arm"] == "d" and r["cycle"] == 3)]
    costs_inc.pop(("s02", "d", 3))
    an_inc = A.analyze(
        sd_inc, costs_inc,
        {"coverage": {"claims": 80, "with_source": 80, "correct_page": 80}},
        n_boot=300, seed=20261125,
    )
    c_inc = R.build_conclusion(an_inc)
    assert c_inc["verdict"] == "INCOMPLETE"
    assert c_inc["missing_count"] == 1
    assert "缺少 1 個 set×arm×cycle" in c_inc["sentence"]


def test_build_and_render_arm_table_and_latency():
    """Pure arm table and latency histogram builders preserve exact numbers and all 13 columns."""
    summary = {
        "c0": {"claims": 40, "correct": 39},
        "arms": {
            "a": {
                "changed_claims": 12, "missed": 12, "miss_rate": 1.0,
                "unchanged_correct_claims": 100, "false_mod": 0,
                "stale_residual_by_cycle": {1: 4, 2: 8, 3: 12},
                "latency_hist": {"None": 12},
                "cost": {
                    "agent_runs": 0, "calls": 0, "tokens_in": 0, "tokens_out": 0,
                    "wall_s": 0.0, "tool_wall_s": 0.0, "usage_unknown": 0,
                    "source_requests_agent": 0, "source_requests_vacant": 0,
                },
            },
            "b": {
                "changed_claims": 12, "missed": 1, "miss_rate": 0.0833,
                "unchanged_correct_claims": 108, "false_mod": 2,
                "stale_residual_by_cycle": {1: 0, 2: 1, 3: 0},
                "latency_hist": {"0": 11, "1": 1},
                "cost": {
                    "agent_runs": 6, "calls": 30, "tokens_in": 12000, "tokens_out": 3000,
                    "wall_s": 90.5, "tool_wall_s": 0.0, "usage_unknown": 1,
                    "source_requests_agent": 30, "source_requests_vacant": 0,
                },
            },
            "c": {
                "changed_claims": 12, "missed": 0, "miss_rate": 0.0,
                "unchanged_correct_claims": 108, "false_mod": 0,
                "stale_residual_by_cycle": {1: 0, 2: 0, 3: 0},
                "latency_hist": {"0": 12},
                "cost": {
                    "agent_runs": 6, "calls": 8, "tokens_in": 2400, "tokens_out": 600,
                    "wall_s": 18.2, "tool_wall_s": 1.4, "usage_unknown": 0,
                    "source_requests_agent": 10, "source_requests_vacant": 30,
                },
            },
            "d": {
                "changed_claims": 12, "missed": 2, "miss_rate": 0.1667,
                "unchanged_correct_claims": 106, "false_mod": 1,
                "stale_residual_by_cycle": {1: 0, 2: 1, 3: 2},
                "latency_hist": {"0": 10, "None": 2},
                "cost": {
                    "agent_runs": 6, "calls": 18, "tokens_in": 6000, "tokens_out": 1500,
                    "wall_s": 42.0, "tool_wall_s": 0.0, "usage_unknown": 0,
                    "source_requests_agent": 15, "source_requests_vacant": 0,
                },
            },
        },
    }
    arm_rows = R.build_arm_rows(summary)
    assert [r["arm"] for r in arm_rows] == ["a", "b", "c", "d"]
    assert arm_rows[1]["false_mod"] == 2
    assert arm_rows[2]["source_requests_vacant"] == 30

    md_arm = R.render_arm_table(arm_rows, summary["c0"])
    header_line = next(ln for ln in md_arm.splitlines() if ln.startswith("| 臂 |"))
    # Exactly 13 columns
    assert len([c for c in header_line.split("|")[1:-1]]) == 13
    assert "39/40 (97.50%)" in md_arm
    assert "12,000" in md_arm
    assert "c1: 4, c2: 8, c3: 12" in md_arm
    assert "2 / 108" in md_arm
    assert "c 臂 1.4 s" in md_arm
    assert "b 臂 1 個 set×cycle" in md_arm

    lat = R.build_latency_table_data(summary)
    assert lat["buckets"] == ["0", "1", "2", "None"]
    assert lat["rows"][0]["counts"] == {"0": 0, "1": 0, "2": 0, "None": 12}
    assert lat["rows"][1]["counts"] == {"0": 11, "1": 1, "2": 0, "None": 0}
    md_lat = R.render_latency_table(lat)
    assert "## 6. 偵測延遲分布" in md_lat
    assert "| b | 11 | 1 | 0 | 0 | 12 |" in md_lat


def test_build_pairwise_and_sources_check_and_audit_pure():
    """Pure pairwise, sources_check (context vs blame + ambiguous), and audit section builders."""
    sd, costs = _make_synthetic(
        n_sets=8,
        miss_fn=lambda si, arm, k, cid: (arm == "a") or (arm == "d" and k == 1 and cid == "p1.price"),
    )
    an = A.analyze(
        sd, costs,
        {"coverage": {"claims": 160, "with_source": 156, "correct_page": 148}},
        n_boot=300, seed=20261125,
    )
    pw = R.build_pairwise_rows(an)
    assert [r["pair"] for r in pw] == ["c vs b", "c vs d", "d vs b"]
    assert pw[0]["token_ratio"]["point"] == pytest.approx(5.0)
    assert pw[1]["token_ratio"]["point"] == pytest.approx(2.5)
    assert pw[2]["token_ratio"]["point"] == pytest.approx(2.0)
    md_pw = R.render_pairwise_table(pw)
    assert "c vs b（主要）" in md_pw
    assert "c vs d（次要）" in md_pw
    assert "d vs b（次要）" in md_pw
    assert "5.00x" in md_pw

    # sources_check summary: mix of context (with ambiguous), blame, unset, and no_source
    checks = {
        "s01": {
            "claims": [
                {"line": 3, "source": {"url": "http://s01/p1.html", "picked_by": "context", "ambiguous": ["http://s01/p2.html"]}},
                {"line": 4, "source": {"url": "http://s01/p1.html", "picked_by": "blame", "ambiguous": None}},
                {"line": 5, "source": {"url": "http://s01/p2.html"}},
                {"line": 6, "source": None},
            ]
        }
    }
    sc_sum = R.summarize_sources_check(checks)
    assert sc_sum["sets"] == 1
    assert sc_sum["claims"] == 4
    assert sc_sum["with_source"] == 3
    assert sc_sum["no_source"] == 1
    assert sc_sum["picked_by_context"] == 1
    assert sc_sum["picked_by_blame"] == 1
    assert sc_sum["picked_by_unset"] == 1
    assert sc_sum["ambiguous"] == 1

    pq = R.build_provenance_quality(
        an, sc_sum,
        {"claims": 160, "value_with_unit_on_another_page": 32, "bare_number_on_another_page": 64,
         "rate_with_unit": 0.2, "rate_bare_number": 0.4},
    )
    md_pq = R.render_provenance_quality(pq)
    assert "148/160 (92.50%)" in md_pq
    assert "1/3 (33.33%)" in md_pq
    assert "32/160" in md_pq
    assert "64/160" in md_pq

    # Audit comparison with a deliberate mismatch
    h_rows = [{"set": "s01", "arm": "b", "cycle": 1, "claim": "p1.price", "status": "correct"}]
    a_rows = [{"set": "s01", "arm": "b", "cycle": 1, "claim": "p1.price", "status": "stale"}]
    hm = R.compare_audit_harness(a_rows, h_rows)
    assert hm["mismatches"] == 1
    assert hm["examples"][0]["audit"] == "stale"
    assert hm["examples"][0]["harness"] == "correct"

    audit_sec = R.build_audit_section_data(
        {
            "record_problems": ["s01/b: seq gap 2→4"],
            "provenance_summary": {
                "a": {"claims": 4, "write_step": 4, "read_step": 4, "server_saw_read": 4},
                "b": {"claims": 4, "write_step": 4, "read_step": 3, "server_saw_read": 3},
                "c": {"claims": 4, "write_step": 4, "read_step": 4, "server_saw_read": 4},
                "d": {"claims": 4, "write_step": 4, "read_step": 4, "server_saw_read": 4},
            },
            "attribution_table": {
                "a": {"miss": {"not maintained (arm a)": 2}},
                "c": {"miss": {"handed to agent, page re-read, not corrected": 1}},
            },
        },
        hm,
    )
    md_au = R.render_audit_section(audit_sec)
    assert "s01/b: seq gap 2→4" in md_au
    assert "s01/b/1/p1.price" in md_au
    assert "handed to agent, page re-read, not corrected" in md_au


# ---------------------------------------------------------------------------
# End-to-end synthetic run root builder & CLI test
# ---------------------------------------------------------------------------

def _put_blob(vh: pathlib.Path, data: bytes) -> str:
    sha = hashlib.sha256(data).hexdigest()
    p = vh / "trace" / "objects" / sha[:2] / sha
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return sha


def _write_chain(vh: pathlib.Path, events: list[dict]) -> None:
    pdir = vh / "trace" / "projects" / "proj0"
    pdir.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e, sort_keys=True) for e in events]
    (pdir / "chain.ndjson").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_step(vh: pathlib.Path, seq: int, step_id: str, session: str, tool: str,
               inp_obj: dict, out_text: str, report_text: str) -> dict:
    in_sha = _put_blob(vh, json.dumps(inp_obj).encode("utf-8"))
    out_sha = _put_blob(vh, out_text.encode("utf-8"))
    rep_sha = _put_blob(vh, report_text.encode("utf-8"))
    idx_sha = _put_blob(vh, json.dumps({"report.md": [rep_sha, len(report_text), 0]}).encode("utf-8"))
    return {
        "seq": seq,
        "prev_hash": f"h{seq - 1}" if seq > 1 else "genesis",
        "type": "step",
        "payload": {
            "step": step_id,
            "tool": tool,
            "actor": {"session": session},
            "input_blob": in_sha,
            "output_blob": out_sha,
            "post_index": idx_sha,
            "writes": [],
        },
    }


def _build_synthetic_root(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    """Build a complete minimal synthetic D2' root + materials + plan in tmp_path."""
    mat_dir = tmp_path / "materials"
    root = tmp_path / "run"
    plan_path = tmp_path / "plan.json"

    # 2 sets: s01, s02; each has 2 claims (p1.price, p2.price)
    # Deliberate value collision in cycle 0: p2.html also mentions "$10" so materials_stats > 0
    sets_manifest = []
    access_lines: list[dict] = []

    for si, sid in enumerate(("s01", "s02"), start=1):
        host = f"{sid}.d2-sources.example"
        claims = [
            {
                "id": "p1.price", "product": "Alpha", "attr": "price",
                "source_page": "p1.html", "template_line": "- Alpha — price: ",
            },
            {
                "id": "p2.price", "product": "Beta", "attr": "price",
                "source_page": "p2.html", "template_line": "- Beta — price: ",
            },
        ]
        # Cycle 0 -> 1: p1.price changes ($10 -> $20)
        # Cycle 1 -> 2: p2.price changes ($30 -> $40)
        # Cycle 2 -> 3: p1.price changes ($20 -> $25)
        truth = [
            {"p1.price": "$10", "p2.price": "$30"},
            {"p1.price": "$20", "p2.price": "$30"},
            {"p1.price": "$20", "p2.price": "$40"},
            {"p1.price": "$25", "p2.price": "$40"},
        ]
        sets_manifest.append({"set": sid, "claims": claims, "truth": truth})

        # Materials cycle_0 site p1..p5.html
        site0 = mat_dir / "sets" / sid / "cycle_0" / "site"
        site0.mkdir(parents=True, exist_ok=True)
        p1_html = f"<p>Alpha price is $10.</p>"
        p2_html = f"<p>Beta price is $30. Compare with $10 starter.</p>"
        (site0 / "p1.html").write_text(p1_html, encoding="utf-8")
        (site0 / "p2.html").write_text(p2_html, encoding="utf-8")
        for pi in (3, 4, 5):
            (site0 / f"p{pi}.html").write_text(f"<p>Product {pi} idle.</p>", encoding="utf-8")

        def _rep(v1: str, v2: str) -> str:
            return f"# Report\n\n- Alpha — price: {v1}\n- Beta — price: {v2}\n"

        rep0 = _rep("$10", "$30")
        c0_dir = root / "cells" / sid / "c0"
        c0_vh = c0_dir / "snapshot" / "vh"
        c0_dir.mkdir(parents=True, exist_ok=True)
        (c0_dir / "report.md").write_text(rep0, encoding="utf-8")

        # c0 chain: fetch p1, fetch p2, write report.md
        t_base = 1795500000.0 + si * 1000.0
        c0_events = [
            _make_step(c0_vh, 1, f"{sid}_c0_r1", "sess_c0", "bash",
                       {"command": f"curl -s http://{host}/p1.html"}, p1_html, ""),
            _make_step(c0_vh, 2, f"{sid}_c0_r2", "sess_c0", "bash",
                       {"command": f"curl -s http://{host}/p2.html"}, p2_html, ""),
            _make_step(c0_vh, 3, f"{sid}_c0_w", "sess_c0", "write",
                       {"path": "report.md"}, "ok", rep0),
        ]
        _write_chain(c0_vh, c0_events)
        (c0_dir / "done.json").write_text(json.dumps({"chain_len": 3}), encoding="utf-8")

        # Record c0 server access matching sha256 of p1_html and p2_html
        access_lines.append({
            "ts": t_base - 10.0, "host": host, "path": "/p1.html",
            "ua": "curl/8.0", "sha256": hashlib.sha256(p1_html.encode()).hexdigest(),
        })
        access_lines.append({
            "ts": t_base - 9.0, "host": host, "path": "/p2.html",
            "ua": "curl/8.0", "sha256": hashlib.sha256(p2_html.encode()).hexdigest(),
        })

        # Each arm starts from c0_events prefix
        for ai, arm in enumerate(("a", "b", "c", "d")):
            adir = root / "cells" / sid / arm
            fin_vh = adir / "final" / "vh"
            # Copy c0 objects into fin_vh so all blobs exist
            for blob_f in (c0_vh / "trace" / "objects").rglob("*"):
                if blob_f.is_file():
                    rel = blob_f.relative_to(c0_vh)
                    dst = fin_vh / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(blob_f.read_bytes())

            events = list(c0_events)
            seq = 3
            prev_rep = rep0

            for k in (1, 2, 3):
                cdir = adir / f"cycle_{k}"
                cdir.mkdir(parents=True, exist_ok=True)
                t0 = t_base + ai * 100.0 + k * 10.0
                t1 = t0 + 5.0
                v1_t, v2_t = truth[k]["p1.price"], truth[k]["p2.price"]

                if arm == "a":
                    rep_k = rep0
                    agent_info = None
                    sc_info = None
                else:
                    # Arm d misses p1.price in cycle 3 on s02 (to exercise attribution + latency None)
                    if arm == "d" and sid == "s02" and k == 3:
                        rep_k = _rep("$20", "$40")
                    else:
                        rep_k = _rep(v1_t, v2_t)

                    # Arm c: emit source_check event + sources_check.json
                    sc_info = None
                    if arm == "c":
                        changed_line = 3 if k in (1, 3) else 4
                        sc_claims = [
                            {
                                "line": 3, "value": truth[k - 1]["p1.price"],
                                "status": "changed" if changed_line == 3 else "unchanged",
                                "source": {
                                    "url": f"http://{host}/p1.html",
                                    "picked_by": "context",
                                    "ambiguous": [f"http://{host}/p2.html"],
                                },
                            },
                            {
                                "line": 4, "value": truth[k - 1]["p2.price"],
                                "status": "changed" if changed_line == 4 else "unchanged",
                                "source": {
                                    "url": f"http://{host}/p2.html",
                                    "picked_by": "blame",
                                    "ambiguous": None,
                                },
                            },
                        ]
                        sc_payload = {
                            "path": "report.md",
                            "claims": sc_claims,
                            "affected_lines": [changed_line],
                            "counts": {"changed": 1, "unchanged": 1},
                        }
                        (cdir / "sources_check.json").write_text(
                            json.dumps(sc_payload, indent=1), encoding="utf-8"
                        )
                        seq += 1
                        events.append({
                            "seq": seq,
                            "prev_hash": f"h{seq - 1}",
                            "type": "source_check",
                            "payload": sc_payload,
                        })
                        sc_info = {"wall_s": 0.5, "affected_lines": [changed_line]}
                        access_lines.append({
                            "ts": t0 + 0.5, "host": host, "path": "/p1.html",
                            "ua": "vacant-source-check", "sha256": "vacant",
                        })

                    # Fetch changed page + write updated report.md
                    pg = "p1.html" if k in (1, 3) else "p2.html"
                    pg_body = f"<p>Alpha price is {v1_t}.</p>" if pg == "p1.html" else f"<p>Beta price is {v2_t}.</p>"
                    sess = f"sess_{arm}_{k}"
                    seq += 1
                    events.append(_make_step(
                        fin_vh, seq, f"{sid}_{arm}_c{k}_r", sess, "bash",
                        {"command": f"curl -s http://{host}/{pg}"}, pg_body, prev_rep,
                    ))
                    access_lines.append({
                        "ts": t0 + 2.0, "host": host, "path": f"/{pg}",
                        "ua": "curl/8.0", "sha256": hashlib.sha256(pg_body.encode()).hexdigest(),
                    })
                    seq += 1
                    events.append(_make_step(
                        fin_vh, seq, f"{sid}_{arm}_c{k}_w", sess, "write",
                        {"path": "report.md"}, "ok", rep_k,
                    ))
                    prev_rep = rep_k

                    tok_in = {"b": 4000, "c": 800, "d": 2000}[arm]
                    tok_out = {"b": 1000, "c": 200, "d": 500}[arm]
                    calls = {"b": 10, "c": 2, "d": 5}[arm]
                    wall = {"b": 30.0, "c": 6.0, "d": 15.0}[arm]
                    agent_info = {
                        "rc": 0, "wall_s": wall,
                        "usage": {"calls": calls, "input": tok_in, "output": tok_out},
                    }

                (cdir / "report.md").write_text(rep_k, encoding="utf-8")
                cyc_doc = {
                    "arm": arm, "cycle": k, "chain_len": seq,
                    "ts_start": "2026-11-25T05:00:00Z", "ts_end": "2026-11-25T05:00:05Z",
                    "t_start": t0, "t_end": t1,
                    "agent": agent_info,
                }
                if sc_info is not None:
                    cyc_doc["sources_check"] = sc_info
                (cdir / "cycle.json").write_text(json.dumps(cyc_doc, indent=1), encoding="utf-8")

            _write_chain(fin_vh, events)
            (adir / "done.json").write_text(json.dumps({"ts": "2026-11-25T05:01:00Z"}), encoding="utf-8")

    manifest = {"schema": "vacant.d2.manifest/1", "seed": 1, "n_sets": 2, "sets": sets_manifest}
    manifest_path = mat_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    (root / "access.jsonl").write_text(
        "\n".join(json.dumps(x) for x in access_lines) + "\n", encoding="utf-8"
    )
    plan_obj = {
        "schema": "vacant.d2.plan/1",
        "id": "synthetic_d2_test",
        "arms": ["a", "b", "c", "d"],
        "materials": {"sets": ["s01", "s02"]},
        "model": {"provider": "test", "model": "mock-9b"},
    }
    plan_path.write_text(json.dumps(plan_obj, indent=1), encoding="utf-8")
    (root / "RUN.json").write_text(json.dumps({"plan_body": plan_obj}, indent=1), encoding="utf-8")
    return root, manifest_path, plan_path


def test_end_to_end_synthetic_root_cli_and_sidecar(tmp_path):
    """Run report_d2.main on a complete synthetic root and verify Markdown + JSON sidecar."""
    root, manifest_path, plan_path = _build_synthetic_root(tmp_path)
    out_md = tmp_path / "out" / "d2_report.md"

    rc = R.main([
        "--root", str(root),
        "--manifest", str(manifest_path),
        "--plan", str(plan_path),
        "--out", str(out_md),
        "--bootstrap", "300",
        "--seed", "20261125",
    ])
    assert rc == 0
    assert out_md.is_file()
    out_json = out_md.with_suffix(".json")
    assert out_json.is_file()

    md = out_md.read_text(encoding="utf-8")
    data = json.loads(out_json.read_text(encoding="utf-8"))

    # Section 1: verdict EFFECTIVE (coverage 4/4=100%, miss c-b=0, token b/c=5.0x)
    assert data["schema"] == "vacant.d2.report/1"
    assert data["conclusion"]["verdict"] == "EFFECTIVE"
    assert "## 1. 一句話結論" in md
    assert "裁決：`EFFECTIVE`" in md
    assert "4/4 = 100.00%" in md
    assert "5.00x" in md

    # Section 2: Per-arm table
    assert "## 2. 每臂彙總" in md
    arms_by_id = {r["arm"]: r for r in data["arms_table"]}
    assert arms_by_id["a"]["missed"] == 6
    assert arms_by_id["b"]["missed"] == 0
    assert arms_by_id["c"]["missed"] == 0
    assert arms_by_id["d"]["missed"] == 1
    assert arms_by_id["c"]["source_requests_vacant"] == 6
    assert arms_by_id["c"]["source_requests_agent"] == 6
    assert arms_by_id["c"]["tool_wall_s"] == pytest.approx(3.0)

    # Section 3: Pairwise comparisons
    assert "## 3. 配對比較" in md
    pw_by_pair = {r["pair"]: r for r in data["pairwise_table"]}
    assert pw_by_pair["c vs b"]["token_ratio"]["point"] == pytest.approx(5.0)
    assert pw_by_pair["c vs d"]["token_ratio"]["point"] == pytest.approx(2.5)
    assert pw_by_pair["d vs b"]["token_ratio"]["point"] == pytest.approx(2.0)

    # Section 4: Provenance quality (coverage, context vs blame, ambiguous, materials collision)
    assert "## 4. 出處品質" in md
    pq = data["provenance_quality"]
    assert pq["coverage"]["correct_page"] == 4
    assert pq["coverage"]["with_source"] == 4
    assert pq["sources_check_c1"]["picked_by_context"] == 2
    assert pq["sources_check_c1"]["picked_by_blame"] == 2
    assert pq["sources_check_c1"]["ambiguous"] == 2
    assert pq["sources_check_c1"]["picked_by_unset"] == 0
    # p1.price ($10) appears on p2.html in both s01 and s02 => 2/4 = 0.5 collision
    assert pq["materials"]["value_with_unit_on_another_page"] == 2
    assert pq["materials"]["rate_with_unit"] == pytest.approx(0.5)

    # Section 5: Audit (0 mismatches, 0 problems, provenance summary, attribution table)
    assert "## 5. 稽核" in md
    au = data["audit"]
    assert au["harness_match"]["mismatches"] == 0
    assert au["record_problems"] == []
    prov_by_arm = {r["arm"]: r for r in au["provenance_rows"]}
    for arm in ("a", "b", "c", "d"):
        assert prov_by_arm[arm]["claims"] == 4
        assert prov_by_arm[arm]["write_step"] == 4
        assert prov_by_arm[arm]["read_step"] == 4
        assert prov_by_arm[arm]["server_saw_read"] == 4
    # Attribution table contains arm a (6 misses) and arm d (1 miss on s02 c3)
    attr_keys = {(r["arm"], r["kind"], r["segment"]): r["count"] for r in au["attribution_rows"]}
    assert attr_keys[("a", "miss", "not maintained (arm a)")] == 6
    assert attr_keys[("d", "miss", "page re-read, not corrected")] == 1

    # Section 6: Detection latency histogram
    assert "## 6. 偵測延遲分布" in md
    lat_by_arm = {r["arm"]: r["counts"] for r in data["latency"]["rows"]}
    assert lat_by_arm["a"]["None"] == 6
    assert lat_by_arm["c"]["0"] == 6
    assert lat_by_arm["d"]["0"] == 5
    assert lat_by_arm["d"]["None"] == 1

    # Section 7: Data sources lists every input file path
    assert "## 7. 資料來源" in md
    ds = data["data_sources"]
    assert str(manifest_path.resolve()) in ds["config_and_manifest"]
    assert str(plan_path.resolve()) in ds["config_and_manifest"]
    assert str((root / "access.jsonl").resolve()) in ds["server_access_log"]
    assert len(ds["materials_pages"]) == 10
    assert len(ds["sources_check"]) == 2
    assert len(ds["audit_chains"]) == 10  # 2 sets × (1 c0 + 4 arms)
    assert str(manifest_path.resolve()) in md
    assert str((root / "cells" / "s01" / "c" / "cycle_1" / "sources_check.json").resolve()) in md


def test_explicit_json_out_and_stdout_mode(tmp_path, capsys):
    """When --out is omitted, Markdown prints to stdout while --json-out writes the JSON sidecar."""
    root, manifest_path, _ = _build_synthetic_root(tmp_path)
    json_out = tmp_path / "custom" / "sidecar.json"
    rc = R.main([
        "--root", str(root),
        "--manifest", str(manifest_path),
        "--json-out", str(json_out),
        "--bootstrap", "200",
        "--seed", "20261125",
    ])
    assert rc == 0
    assert json_out.is_file()
    out = capsys.readouterr().out
    assert out.startswith("# D2′ 實驗報告")
    assert "## 7. 資料來源" in out
    parsed = json.loads(json_out.read_text(encoding="utf-8"))
    assert parsed["conclusion"]["verdict"] == "EFFECTIVE"
