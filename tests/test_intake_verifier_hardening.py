"""驗證器的對抗審查回歸（2026-09-24，`decisions/DECISION_20260924_UNIVERSAL_INTAKE.md` §十一）。

每一條都是審查者**真的重現過**的一個「不合格的成果被判過」或「設定錯被怪到成果頭上」：

- 成果帶的 `.bash_profile`／`usercustomize` 在驗證器之前執行、決定裁決
- `command` 驗證器在沙箱裡拿不到文件寫的環境變數
- NaN／inf 讓任何數字都「相符」；`1,5` 被當成 15；`Subtotal` 被當成 total
- 巢狀 `.env` 沒被預設的禁止項抓到
- 引用只靠成果自己的 sources.json 卻被標成獨立證據；空白引文；多重引用沒被檢查
- JSON 的 NaN 過得了數值界限；`format` 沒檢查；draft-07 的關鍵字被安靜忽略
- 字串型的清單參數被逐字元迭代；空的禁止清單變成 PASS；圍欄程式碼裡的 `#` 算標題
- 驗證器設定錯記成 FAIL（成果的錯）而不是 UNKNOWN
- 隱藏主張的細節出現在 `vacant check` 的輸出與帳本裡
"""
from __future__ import annotations

import json
import pathlib

import pytest

from vacant_network.intake import contract as C
from vacant_network.intake import flow
from vacant_network.intake.artifact import ArtifactError, Store, glob_to_regex


@pytest.fixture()
def vhome(tmp_path, monkeypatch):
    h = tmp_path / "vhome"
    monkeypatch.setenv("VACANT_HOME", str(h))
    return h / "intake"


def _contract(tmp_path: pathlib.Path, claims: list[dict], *, inputs: dict | None = None,
              include: list[str] | None = None) -> C.Contract:
    proj = tmp_path / "proj"
    (proj / ".vacant").mkdir(parents=True, exist_ok=True)
    raw = C.scaffold("hardening", deliverable=include or ["**"], destination="dir:pub")
    raw["claims"] = claims
    raw["inputs"] = inputs or {}
    p = proj / ".vacant" / "contract.json"
    p.write_text(json.dumps(raw, indent=2))
    if inputs:
        C.lock(p)
    return C.load(p)


def _ws(tmp_path: pathlib.Path, files: dict[str, str], name: str = "ws") -> pathlib.Path:
    ws = tmp_path / name
    ws.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return ws


def _status(res: dict, cid: str) -> str:
    return {r["claim_id"]: r["status"] for r in res["results"]}[cid]


def _detail(res: dict, cid: str) -> str:
    return {r["claim_id"]: r["detail"] for r in res["results"]}[cid]


# ── 成果的啟動檔不能決定裁決 ───────────────────────────────────────────

def test_deliverable_bash_profile_cannot_turn_a_failing_command_into_pass(tmp_path, vhome):
    c = _contract(tmp_path, [{"id": "owner_cmd", "verifier": "command",
                              "params": {"argv": ["bash", "-c", "exit 1"],
                                         "sandbox": "none"}}])
    clean = flow.check(c, _ws(tmp_path, {"report.md": "x"}, "a"), sandbox="none")
    assert _status(clean, "owner_cmd") == "FAIL"
    c2 = _contract(tmp_path, [{"id": "owner_cmd", "verifier": "command",
                               "params": {"argv": ["bash", "-c", "exit 1"], "sandbox": "auto"}}])
    forged = flow.check(c2, _ws(tmp_path, {"report.md": "x", ".bash_profile": "exit 0\n",
                                           ".bashrc": "exit 0\n", ".profile": "exit 0\n"}, "b"),
                        sandbox="none")
    assert _status(forged, "owner_cmd") in ("FAIL", "UNKNOWN")   # UNKNOWN only if no sandbox
    assert forged["outcome"] != "accept"


def test_sandboxed_command_sees_the_documented_environment(tmp_path, vhome):
    sales = tmp_path / "proj" / "sales.csv"
    sales.parent.mkdir(parents=True, exist_ok=True)
    sales.write_text("amount\n1\n")
    script = ('test -n "$VACANT_ARTIFACT_DIR" && test -f "$VACANT_ARTIFACT_DIR/report.md" '
              '&& test -f "$VACANT_INPUT_SALES" && test "$MODE" = strict '
              '&& ! grep -rq AKIA "$VACANT_ARTIFACT_DIR"')
    c = _contract(tmp_path, [{"id": "no_keys", "verifier": "command",
                              "params": {"argv": ["bash", "-c", script], "sandbox": "auto",
                                         "env": {"MODE": "strict"}}}],
                  inputs={"sales": {"path": "sales.csv"}})
    ok = flow.check(c, _ws(tmp_path, {"report.md": "fine"}, "a"))
    leak = flow.check(c, _ws(tmp_path, {"report.md": "KEY=AKIAIOSFODNN7EXAMPLE"}, "b"))
    if _status(ok, "no_keys") == "UNKNOWN" and "sandbox unavailable" in _detail(ok, "no_keys"):
        pytest.skip("no sandbox backend on this machine")
    assert _status(ok, "no_keys") == "PASS", _detail(ok, "no_keys")
    assert _status(leak, "no_keys") == "FAIL"


def test_command_on_an_unpinned_or_changed_input_is_unknown_not_fail(tmp_path, vhome):
    data = tmp_path / "proj" / "data.txt"
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_text("v1")
    c = _contract(tmp_path, [{"id": "cmd", "verifier": "command",
                              "params": {"argv": ["bash", "-c", "cat \"$VACANT_INPUT_DATA\""]}}],
                  inputs={"data": {"path": "data.txt"}})
    data.write_text("v2 — changed after lock")
    res = flow.check(c, _ws(tmp_path, {"report.md": "x"}), sandbox="none")
    assert _status(res, "cmd") == "UNKNOWN"


def test_sandbox_hermetic_mode_skips_profiles_and_user_site(tmp_path):
    from vacant_network.vrun.sandbox import make_sandbox
    ws = _ws(tmp_path, {".bash_profile": "echo PROFILE; exit 0\n",
                        ".local/lib/python3.11/site-packages/usercustomize.py":
                            "print('USERCUSTOMIZE')\n"})
    sb, _ = make_sandbox("none", workdir=str(tmp_path))
    sb.hermetic = True
    r = sb.run('python3 -c "print(1)"; echo "HOME=$HOME"; exit 1', workspace=ws)
    assert r.rc == 1
    assert "PROFILE" not in r.stdout and "USERCUSTOMIZE" not in r.stdout
    home = r.stdout.split("HOME=")[1].strip()
    assert not home.startswith(str(ws))                   # HOME 不在成果裡
    sb.hermetic = False                                   # vrun 的舊行為不變（歸檔 run 可比）
    assert "PROFILE" in sb.run("true", workspace=ws).stdout


# ── 數值重算 ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("csv_text,report,want", [
    ("region,amount\nN,100\nS,NaN\nE,50\n", "Total revenue: 999,999", "UNKNOWN"),
    ("region,amount\nN,inf\nS,-inf\n", "Total: 5", "UNKNOWN"),
    ("region;amount\nN;1,5\nS;1,5\n", "Total: 30", "UNKNOWN"),          # 小數逗號不是千分位
    ("region,amount\nN,100\n", "Subtotal (north): 100\nGrand total: 12,345", "FAIL"),
    ("region,amount\nN,1000\nS,1000\n", "Total: 2,000.00", "PASS"),
    ("region,amount\nN,10\nS,20\n", "Total cost: 30\nTotal revenue: 45", "UNKNOWN"),
])
def test_csv_total_is_strict_about_numbers(tmp_path, vhome, csv_text, report, want):
    (tmp_path / "proj").mkdir(parents=True, exist_ok=True)
    (tmp_path / "proj" / "sales.csv").write_text(csv_text)
    delim = ";" if ";" in csv_text.splitlines()[0] else ","
    c = _contract(tmp_path, [{"id": "t", "verifier": "csv_total", "authority": "fact",
                              "params": {"csv": "input:sales", "column": "amount",
                                         "report": "report.md", "delimiter": delim}}],
                  inputs={"sales": {"path": "sales.csv"}})
    assert _status(flow.check(c, _ws(tmp_path, {"report.md": report})), "t") == want


def test_csv_total_relative_tolerance_accepts_float_drift(tmp_path, vhome):
    (tmp_path / "proj").mkdir(parents=True, exist_ok=True)
    (tmp_path / "proj" / "s.csv").write_text("amount\n" + "0.01\n" * 100_000)
    c = _contract(tmp_path, [{"id": "t", "verifier": "csv_total",
                              "params": {"csv": "input:s", "column": "amount",
                                         "report": "report.md"}}],
                  inputs={"s": {"path": "s.csv"}})
    assert _status(flow.check(c, _ws(tmp_path, {"report.md": "Total: 1,000.00"})), "t") == "PASS"


def test_default_total_pattern_is_not_quadratic_on_hostile_text(tmp_path, vhome):
    import time
    (tmp_path / "proj").mkdir(parents=True, exist_ok=True)
    (tmp_path / "proj" / "s.csv").write_text("amount\n1\n")
    c = _contract(tmp_path, [{"id": "t", "verifier": "csv_total",
                              "params": {"csv": "input:s", "column": "amount",
                                         "report": "report.md"}}],
                  inputs={"s": {"path": "s.csv"}})
    t0 = time.time()
    flow.check(c, _ws(tmp_path, {"report.md": "total " * 20000}))
    assert time.time() - t0 < 5


# ── 路徑樣式 ───────────────────────────────────────────────────────────

def test_default_contract_forbids_nested_env_files(tmp_path, vhome):
    raw = C.scaffold("x")
    forbid = [cl for cl in raw["claims"] if cl["verifier"] == "forbid_paths"][0]
    c = _contract(tmp_path, [forbid])
    res = flow.check(c, _ws(tmp_path, {"report.md": "x", "backend/.env": "SECRET=1",
                                       "cfg/.env.production": "SECRET=2"}))
    assert res["outcome"] == "reject"


def test_leading_slash_anchors_instead_of_never_matching():
    assert glob_to_regex("/secrets.json").match("secrets.json")
    assert not glob_to_regex("secrets.json").match("sub/secrets.json")   # 錨定在根目錄
    assert glob_to_regex("**/.env").match(".env")
    assert glob_to_regex("**/.env").match("a/b/.env")


# ── 引用 ──────────────────────────────────────────────────────────────

SNAP = "Independent review: the pilot reduced handling time by 12 percent."


def test_citations_from_the_deliverable_alone_are_not_independent(tmp_path, vhome):
    c = _contract(tmp_path, [{"id": "cites", "verifier": "citations_resolve", "authority": "fact",
                              "params": {"path": "report.md", "sources": "sources.json"}}])
    res = flow.check(c, _ws(tmp_path, {
        "report.md": "Claim [@smith2020].",
        "sources.json": json.dumps([{"id": "smith2020", "url": "https://example.invalid/x"}])}))
    assert _status(res, "cites") == "UNKNOWN"          # 事實主張＋不獨立 ⇒ 不能 PASS


def test_citations_whitespace_quote_and_multi_cites(tmp_path, vhome):
    snaps = tmp_path / "proj" / "snaps"
    snaps.mkdir(parents=True)
    (snaps / "real.txt").write_text(SNAP)
    claim = {"id": "cites", "verifier": "citations_resolve", "authority": "fact",
             "params": {"path": "report.md", "sources": "sources.json",
                        "require_quotes": True, "snapshots_input": "snaps"}}
    c = _contract(tmp_path, [claim], inputs={"snaps": {"path": "snaps"}})
    real = {"id": "real", "url": "https://e.org/r", "quote": "reduced handling time"}
    blank = {"id": "real", "url": "https://e.org/r", "quote": "   "}
    good = flow.check(c, _ws(tmp_path, {"report.md": "It worked [@real].",
                                        "sources.json": json.dumps([real])}, "g"))
    assert _status(good, "cites") == "PASS"
    ws_blank = _ws(tmp_path, {"report.md": "It worked [@real].",
                              "sources.json": json.dumps([blank])}, "b")
    assert _status(flow.check(c, ws_blank), "cites") == "FAIL"
    multi = _ws(tmp_path, {"report.md": "It worked [@real]. Also [@fake; @real, p. 3].",
                           "sources.json": json.dumps([real])}, "m")
    res = flow.check(c, multi)
    assert _status(res, "cites") == "FAIL" and "fake" in _detail(res, "cites")


# ── JSON Schema ────────────────────────────────────────────────────────

@pytest.mark.parametrize("schema,doc", [
    ({"type": "object", "properties": {"accuracy": {"type": "number", "minimum": 0.9}}},
     '{"accuracy": NaN}'),
    ({"type": "object", "properties": {"when": {"type": "string", "format": "date"}}},
     '{"when": "not-a-date"}'),
    ({"$schema": "http://json-schema.org/draft-07/schema#",
      "dependencies": {"card": ["billing_address"]}}, '{"card": "1234"}'),
])
def test_json_schema_rejects_what_it_used_to_wave_through(tmp_path, vhome, schema, doc):
    c = _contract(tmp_path, [{"id": "js", "verifier": "json_schema",
                              "params": {"path": "m.json", "schema": schema}}])
    assert _status(flow.check(c, _ws(tmp_path, {"m.json": doc})), "js") == "FAIL"


# ── 參數型別與設定錯 ───────────────────────────────────────────────────

@pytest.mark.parametrize("claim", [
    {"id": "c", "verifier": "text", "params": {"path": "report.md", "must_contain": "Conclusion"}},
    {"id": "c", "verifier": "forbid_paths", "params": {"paths": "id_rsa"}},
    {"id": "c", "verifier": "forbid_paths", "params": {}},
    {"id": "c", "verifier": "sha256_pin", "params": {"path": "report.md"}},
    {"id": "c", "verifier": "json_schema", "params": {"schema": {"type": "object"}}},
    {"id": "c", "verifier": "review", "params": {"min_reviews": 0}},
])
def test_contract_mistakes_are_unknown_not_blamed_on_the_deliverable(tmp_path, vhome, claim):
    c = _contract(tmp_path, [claim])
    res = flow.check(c, _ws(tmp_path, {"report.md": "Cool solutions, no clue", "id_rsa": "k"}))
    assert _status(res, "c") == "UNKNOWN", _detail(res, "c")


def test_headings_inside_code_fences_do_not_count(tmp_path, vhome):
    c = _contract(tmp_path, [{"id": "h", "verifier": "text",
                              "params": {"path": "r.md", "required_headings": ["Risks"]}}])
    fenced = "# Plan\n\n```bash\n# Risks\necho hi\n```\n"
    lone = "# Plan\n#\nRisks are low.\n"
    assert _status(flow.check(c, _ws(tmp_path, {"r.md": fenced}, "f")), "h") == "FAIL"
    assert _status(flow.check(c, _ws(tmp_path, {"r.md": lone}, "l")), "h") == "FAIL"
    ok = "# Plan\n\n## Risks\nlow\n"
    assert _status(flow.check(c, _ws(tmp_path, {"r.md": ok}, "o")), "h") == "PASS"


# ── 隱藏主張 ───────────────────────────────────────────────────────────

def test_hidden_claim_details_do_not_reach_the_deliverables_author(tmp_path, vhome):
    c = _contract(tmp_path, [{"id": "secret_rule", "verifier": "text", "hidden": True,
                              "params": {"path": "report.md",
                                         "must_contain": ["HIDDEN-TOKEN-7731"]}}])
    ws = _ws(tmp_path, {"report.md": "nothing"})
    res = flow.check(c, ws)
    blob = json.dumps(res)
    assert res["outcome"] == "reject" and "HIDDEN-TOKEN-7731" not in blob
    assert "HIDDEN-TOKEN-7731" in json.dumps(flow.check(c, ws, reveal_hidden=True))
    task = flow.open_task(c)
    sub = flow.submit(task, ws, source="test")
    assert "HIDDEN-TOKEN-7731" not in json.dumps(sub)
    assert "HIDDEN-TOKEN-7731" not in task.ledger.path.read_text()


# ── 隔離區清單與提交路徑 ───────────────────────────────────────────────

def test_a_hand_made_manifest_with_traversal_is_refused_before_any_write(tmp_path):
    store = Store(tmp_path / "store")
    m = store.freeze_blobs({"ok.md": b"x"}, task_id="t", source="s", include=["**"], exclude=[])
    evil = dict(m)
    evil["files"] = [{**m["files"][0], "path": "../../escaped.md"}]
    from vacant_network.intake.artifact import artifact_digest
    evil["artifact_sha256"] = artifact_digest(evil["files"])
    (store.candidates / f"{evil['artifact_sha256']}.json").write_text(json.dumps(evil))
    with pytest.raises(ArtifactError):
        store.load_manifest(evil["artifact_sha256"])
    with pytest.raises(ArtifactError):
        store.materialize(evil, tmp_path / "out" / "a")
    assert not (tmp_path / "escaped.md").exists() and not (tmp_path / "out" / "escaped.md").exists()


@pytest.mark.parametrize("blobs", [
    {"report.md": b"x", "report.md/y": b"y"},
    {"a/b.md": b"1", "a//b.md": b"2"},
])
def test_colliding_submission_paths_are_a_reject_not_a_void(tmp_path, vhome, blobs):
    c = _contract(tmp_path, [{"id": "e", "verifier": "exists", "params": {"paths": ["**"]}}])
    task = flow.open_task(c)
    res = flow.submit_blobs(task, blobs, source="http:test")
    assert res["outcome"] == "reject" and not res.get("void")
