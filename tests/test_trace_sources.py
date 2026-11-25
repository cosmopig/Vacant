"""Tests for vacant_network/trace/sources.py (claims_in, provenance, check)."""
from __future__ import annotations

import hashlib

import pytest

from vacant_network.intake import keys
from vacant_network.trace import recorder as R
from vacant_network.trace import sources as S

MAIN = R.Actor("pi", "s1")
PAGE_URL = "http://s01.d2-sources.example/p1.html"
PAGE_HTML = (
    "<!doctype html><html><body>\n"
    "<h1>Nimbra Cloud</h1>\n"
    "<p>Plans start at $32 per seat per month.</p>\n"
    "<table><tr><td>monthly price per seat</td><td>$32</td></tr>"
    "<tr><td>latest version</td><td>v5.7.9</td></tr>"
    "<tr><td>API rate limit</td><td>1,200 requests per minute</td></tr></table>\n"
    "</body></html>\n"
)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    keys.init_local()
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "report.md").write_text(
        "# Product comparison\n\n"
        "- X — price: ____\n",
        encoding="utf-8",
    )
    return ws, R.Recorder(ws)


def _step(rec: R.Recorder, sid: str, tool: str, inp: dict, out="", write=None):
    rec.pre(sid, MAIN, tool, inp)
    if write is not None:
        path, text = write
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return rec.post(sid, MAIN, tool, inp, out)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def test_claims_in_numbers_versions_and_skips():
    text = (
        "# Heading 999 v1.2.3\n"
        "## Section $50\n"
        "\n"
        "   \n"
        "- X — price: ____\n"
        "- X — pending: TODO 42\n"
        "- X — other: TBD $100\n"
        "- X — monthly price per seat: $32\n"
        "- X — API rate limit: 1,200 requests per minute\n"
        "- X — latest version: v5.7.9\n"
        "- X — bare semver: 2.14.0 and $1,250.50\n"
    )
    got = [{"line": c["line"], "value": c["value"]} for c in S.claims_in(text)]
    assert got == [
        {"line": 8, "value": "$32"},
        {"line": 9, "value": "1,200"},
        {"line": 10, "value": "v5.7.9"},
        {"line": 11, "value": "2.14.0"},
        {"line": 11, "value": "$1,250.50"},
    ]
    # Version strings like v5.7.9 are NOT double-counted as numbers (e.g. 5.7 / 9)
    assert [c for c in got if c["line"] == 10] == [{"line": 10, "value": "v5.7.9"}]


def test_provenance_from_curl_stdout_and_edit(env):
    ws, rec = env
    _step(rec, "t1", "Bash", {"command": f"curl -s {PAGE_URL}"}, PAGE_HTML)
    new_report = "# Product comparison\n\n- X — price: $32\n"
    _step(
        rec, "t2", "Edit",
        {"file_path": str(ws / "report.md"),
         "old_string": "- X — price: ____",
         "new_string": "- X — price: $32"},
        "ok",
        write=(ws / "report.md", new_report),
    )

    prov = S.provenance(ws, "report.md")
    assert len(prov) == 1
    entry = prov[0]
    assert entry["line"] == 3
    assert entry["value"] == "$32"
    assert entry["written_by_step"] == "t2"
    assert entry["source"] is not None
    assert entry["source"]["url"] == PAGE_URL
    assert entry["source"]["step"] == "t1"
    assert entry["source"]["observed"] is True
    assert entry["source"]["seen_sha256"] == _sha(PAGE_HTML)


def test_check_unchanged_changed_unknown_and_no_source(env):
    ws, rec = env
    _step(rec, "t1", "Bash", {"command": f"curl -s {PAGE_URL}"}, PAGE_HTML)
    new_report = (
        "# Product comparison\n\n"
        "- X — price: $32\n"
        "- Y — internal estimate: $777\n"
    )
    _step(
        rec, "t2", "Edit",
        {"file_path": str(ws / "report.md"),
         "old_string": "- X — price: ____",
         "new_string": "- X — price: $32\n- Y — internal estimate: $777"},
        "ok",
        write=(ws / "report.md", new_report),
    )

    # (a) fetch returns the same page -> $32 is unchanged, $777 is no_source
    res_same = S.check(ws, "report.md", fetch=lambda u: PAGE_HTML, record=False)
    by_val = {c["value"]: c for c in res_same["claims"]}
    assert by_val["$32"]["status"] == "unchanged"
    assert by_val["$32"]["source"]["now_sha256"] == _sha(PAGE_HTML)
    assert by_val["$777"]["status"] == "no_source"
    assert by_val["$777"]["source"] is None
    assert res_same["changed_lines"] == []
    assert res_same["affected_lines"] == [4]  # line 4 has no_source

    # (b) fetch returns a page where the "$32" line changed -> changed
    updated_page = PAGE_HTML.replace("$32", "$49")
    res_changed = S.check(ws, "report.md", fetch=lambda u: updated_page, record=False)
    by_val = {c["value"]: c for c in res_changed["claims"]}
    assert by_val["$32"]["status"] == "changed"
    assert by_val["$32"]["source"]["now_sha256"] == _sha(updated_page)
    assert res_changed["changed_lines"] == [3]
    assert res_changed["affected_lines"] == [3, 4]

    # (c) fetch raises -> unknown
    def _boom(url: str) -> str:
        raise OSError("connection refused")

    res_err = S.check(ws, "report.md", fetch=_boom, record=False)
    by_val = {c["value"]: c for c in res_err["claims"]}
    assert by_val["$32"]["status"] == "unknown"
    assert "OSError" in by_val["$32"]["error"]
    assert by_val["$777"]["status"] == "no_source"
    assert res_err["affected_lines"] == [3, 4]


def test_check_record_true_appends_source_check_and_chain_verifies(env):
    ws, rec = env
    _step(rec, "t1", "Bash", {"command": f"curl -s {PAGE_URL}"}, PAGE_HTML)
    new_report = "# Product comparison\n\n- X — price: $32\n"
    _step(
        rec, "t2", "Edit",
        {"file_path": str(ws / "report.md"),
         "old_string": "- X — price: ____",
         "new_string": "- X — price: $32"},
        "ok",
        write=(ws / "report.md", new_report),
    )

    res = S.check(ws, "report.md", fetch=lambda u: PAGE_HTML, record=True)
    assert res["counts"] == {"unchanged": 1}

    rec2 = R.Recorder(ws)
    sc_events = [e for e in rec2.events() if e.get("type") == "source_check"]
    assert len(sc_events) == 1
    assert sc_events[0]["schema"] == "vacant-source-check/1"
    assert sc_events[0]["path"] == "report.md"
    assert sc_events[0]["counts"] == {"unchanged": 1}
    # Full body text is NOT stored inside the signed event; only hashes
    assert "_seen" not in sc_events[0]["claims"][0]
    ok, why = rec2.verify()
    assert ok, why


def test_provenance_curl_redirect_to_file_then_read(env):
    """The agent saves a page via `curl -s URL > p1.html` and then reads `p1.html` (common real-model pattern).

    Before 2026-11-25 `seen` was the (empty) stdout of the curl step, so every such claim came out "changed".
    Now `blame` reports `into` and `sources` takes the file the fetch wrote as what the agent saw."""
    ws, rec = env
    _step(
        rec, "t1", "Bash",
        {"command": f"curl -s {PAGE_URL} > p1.html"},
        "",
        write=(ws / "p1.html", PAGE_HTML),
    )
    _step(rec, "t2", "Read", {"file_path": str(ws / "p1.html")}, PAGE_HTML)
    new_report = "# Product comparison\n\n- X — price: $32\n"
    _step(
        rec, "t3", "Edit",
        {"file_path": str(ws / "report.md"),
         "old_string": "- X — price: ____",
         "new_string": "- X — price: $32"},
        "ok",
        write=(ws / "report.md", new_report),
    )

    prov = S.provenance(ws, "report.md")
    assert len(prov) == 1
    entry = prov[0]
    assert entry["value"] == "$32"
    assert entry["written_by_step"] == "t3"
    assert entry["confidence"] == "heuristic"
    assert entry["source"] is not None
    assert entry["source"]["url"] == PAGE_URL
    assert entry["source"]["step"] == "t1"
    assert entry["source"]["observed"] is False
    # 2026-11-25 修正後：「當時看到的」是 t1 導出來的 p1.html（不是空的 stdout）
    assert entry["source"]["into"] == "p1.html"
    assert entry["source"]["seen_sha256"] == _sha(PAGE_HTML)

    # 同一頁 ⇒ unchanged；值所在的片段改了 ⇒ changed
    res = S.check(ws, "report.md", fetch=lambda u: PAGE_HTML, record=False)
    assert res["claims"][0]["status"] == "unchanged"
    assert res["claims"][0]["source"]["url"] == PAGE_URL
    res2 = S.check(ws, "report.md", fetch=lambda u: PAGE_HTML.replace("$32", "$64"), record=False)
    assert res2["claims"][0]["status"] == "changed"
    assert res["claims"][0]["source"]["now_sha256"] == _sha(PAGE_HTML)
