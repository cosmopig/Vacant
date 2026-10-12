"""HTTP 收件口與 `vacant` 收件指令。

HTTP 那一半對應外部質疑報告 §06 對 vacant-world-cloud `/api/result` 的三個指摘：
回寫者自帶的 verdict 被採信、`false || null` 混掉「不相符」與「沒評估」、
沒設 token 時有預設值。這裡的收件口：

- 提交者給的 `verdict`／`accepted`／`matched`／`status` 一律忽略（並回報忽略了哪些）
- 裁決四態保留（reject 不會變成 null）
- 沒有 token 就不啟動
- 公開路徑只讀放行過的版本
"""
from __future__ import annotations

import base64
import json
import threading
import urllib.error
import urllib.request

import pytest

from vacant_network import cli as vcli
from vacant_network.intake import contract as C, flow
from vacant_network.intake.server import IntakeApp, make_handler, serve


@pytest.fixture()
def vhome(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vhome"))
    return tmp_path / "vhome"


def _contract(tmp_path):
    proj = tmp_path / "proj"
    (proj / ".vacant").mkdir(parents=True)
    raw = C.scaffold("card-7", deliverable=["card.json"], destination="dir:published")
    raw["claims"] = [
        {"id": "card_schema", "verifier": "json_schema",
         "params": {"path": "card.json", "schema": {
             "type": "object", "required": ["title", "lines"],
             "properties": {"title": {"type": "string", "maxLength": 40},
                            "lines": {"type": "array", "minItems": 2}}}}},
        {"id": "no_raw_phone", "verifier": "text",
         "params": {"path": "card.json", "must_not_contain": [r"\+?886[- ]?9\d{2}"]}}]
    cp = proj / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    flow.lock(cp)
    return cp


@pytest.fixture()
def server(tmp_path, vhome):
    from http.server import ThreadingHTTPServer
    cp = _contract(tmp_path)
    app = IntakeApp([cp], token="s3cret", sandbox="none")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", cp
    httpd.shutdown()
    httpd.server_close()


def _post(url, body, token="s3cret"):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"}
                                             if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _files(obj):
    return {"card.json": base64.b64encode(json.dumps(obj).encode()).decode()}


def test_submitter_cannot_supply_the_verdict(server):
    base, cp = server
    bad = {"title": "hello", "lines": ["only one"]}
    code, res = _post(f"{base}/v1/tasks/card-7/submissions",
                      {"source": "closed-saas", "files": _files(bad),
                       "verdict": "pass", "accepted": True, "matched": True})
    assert code == 200
    assert res["outcome"] == "reject"
    assert set(res["ignored_fields"]) == {"verdict", "accepted", "matched"}
    assert res["published"] is False


def test_token_is_required(server):
    base, _ = server
    code, _ = _post(f"{base}/v1/tasks/card-7/submissions", {"files": _files({})}, token=None)
    assert code == 401
    code, _ = _post(f"{base}/v1/tasks/card-7/submissions", {"files": _files({})}, token="x")
    assert code == 401


def test_only_released_versions_are_public(server):
    base, cp = server
    good = {"title": "hello", "lines": ["a", "b"]}
    code, res = _post(f"{base}/v1/tasks/card-7/submissions", {"files": _files(good)})
    assert res["outcome"] == "accept"
    assert _get(f"{base}/published/card-7/card.json")[0] == 404   # accepted ≠ published
    rel = flow.release(flow.open_task(cp))
    assert rel["released"] is True
    code, body = _get(f"{base}/published/card-7/card.json")
    assert code == 200 and json.loads(body) == good
    assert _get(f"{base}/published/card-7/../../etc/passwd")[0] == 404
    assert _get(f"{base}/published/card-7/.vacant-release.json")[0] == 404


def test_unsafe_paths_are_refused(server):
    base, _ = server
    code, res = _post(f"{base}/v1/tasks/card-7/submissions",
                      {"files": {"../escape.txt": base64.b64encode(b"x").decode()}})
    assert code == 400


def test_server_refuses_to_start_without_a_token(tmp_path, vhome, capsys):
    cp = _contract(tmp_path)
    rc = serve(contracts=[cp], host="127.0.0.1", port=0, token_file=None,
               insecure_no_token=False)
    assert rc == 2
    assert "refusing to start" in capsys.readouterr().err


# ── CLI exit codes ────────────────────────────────────────────────────

def test_cli_exit_codes(tmp_path, vhome, monkeypatch, capsys):
    cp = _contract(tmp_path)
    proj = cp.parent.parent
    monkeypatch.chdir(proj)
    (proj / "card.json").write_text(json.dumps({"title": "t", "lines": ["x"]}))
    assert vcli.main(["check"]) == 40
    assert vcli.main(["submit"]) == 40
    assert vcli.main(["release"]) == 44
    (proj / "card.json").write_text(json.dumps({"title": "t", "lines": ["x", "y"]}))
    assert vcli.main(["check"]) == 0
    assert vcli.main(["submit"]) == 0
    assert vcli.main(["release"]) == 0
    assert (proj / "published" / "card-7" / "card.json").exists()
    assert vcli.main(["task", "status"]) == 0
    assert vcli.main(["task", "verify"]) == 0
    capsys.readouterr()
    assert vcli.main(["task", "report", "--json"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["n_tasks"] == 1 and rep["by_state"]["released"] == 1


def test_cli_contract_init_refuses_overwrite(tmp_path, vhome, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert vcli.main(["contract", "init", "--task", "x1"]) == 0
    with pytest.raises(SystemExit):
        vcli.main(["contract", "init", "--task", "x1"])
    assert vcli.main(["contract", "validate"]) == 0


def test_cli_bad_contract_is_exit_2(tmp_path, vhome, monkeypatch, capsys):
    (tmp_path / ".vacant").mkdir()
    (tmp_path / ".vacant" / "contract.json").write_text(json.dumps({"schema": "nope"}))
    monkeypatch.chdir(tmp_path)
    assert vcli.main(["check"]) == 2
    assert "contract problems" in capsys.readouterr().err


def test_a_failed_submission_says_where_and_what_it_should_be(tmp_path, vhome):
    """HTTP 交來的只有檔案：回應裡有和 agent 回合結束時同一段「哪個檔哪一行、應該是多少」，外加結構化清單；
    沒有任何步驟、沒有行動者；隱藏主張只說沒過（2026-09-25：HTTP 收件口接上追緝的定位那一半）。"""
    from vacant_network.intake import keys
    from vacant_network.trace import feedback as F
    keys.init_local()
    proj = tmp_path / "proj2"
    (proj / ".vacant").mkdir(parents=True)
    (proj / "data").mkdir()
    (proj / "data" / "sales.csv").write_text("id,amount\n1,10\n2,20\n3,39\n")
    raw, _ = C.quick(proj, deliverable=["report.md"], inputs=["data/sales.csv"],
                     must=["Recommendation"], totals=["amount"], task_id="http-q3")
    raw["claims"].append({"id": "secret_rule", "verifier": "text", "hidden": True,
                          "required": True, "authority": "requirement",
                          "params": {"path": "report.md", "must_not_contain": ["North"]}})
    cp = proj / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    flow.lock(cp)
    app = IntakeApp([cp], token="t", sandbox="none")
    body = "# Q3\n\nTotal: 70\n\nNorth did best.\n"
    code, res = app.submit("http-q3", {"source": "saas", "files": {
        "report.md": base64.b64encode(body.encode()).decode()}})
    assert code == 200 and res["outcome"] == "reject"
    fb = res["feedback"]
    assert fb.startswith("The intake's decision for this submission is 'reject'")   # 這就是裁決
    assert "vacant check" not in fb and F.FEEDBACK_HEADER not in fb
    assert 'report.md:3 says "70"' in fb and "expected 69" in fb
    assert 'does not contain "Recommendation"' in fb
    assert "secret_rule: FAIL (details withheld" in fb and "North" not in fb
    assert "step" not in fb                                   # 沒有步驟可說
    iss = {(i["claim_id"], i.get("line")) for i in res["issues"]}
    assert ("total_sales_amount", 3) in iss and not any(c == "secret_rule" for c, _ in iss)
    tot = next(i for i in res["issues"] if i["claim_id"] == "total_sales_amount")
    assert tot["value"] == "70" and float(tot["expected"]) == 69


def test_an_accepted_submission_has_no_feedback(server):
    base, _cp = server
    code, res = _post(f"{base}/v1/tasks/card-7/submissions",
                      {"files": _files({"title": "ok", "lines": ["a", "b"]})})
    assert code == 200 and res["outcome"] == "accept" and "feedback" not in res



# ── 2026-09-25 審查（HTTP 回應裡的定位）的回歸 ─────────────────────────────────────────────

def _app(tmp_path, claims, *, inputs=None, files=None, deliverable=("report.md",)):
    from vacant_network.intake import keys
    keys.init_local()
    proj = tmp_path / "p"
    (proj / ".vacant").mkdir(parents=True, exist_ok=True)
    for rel, text in (files or {}).items():
        (proj / rel).parent.mkdir(parents=True, exist_ok=True)
        (proj / rel).write_text(text)
    raw = C.scaffold("h1", deliverable=list(deliverable), destination="dir:published")
    raw["inputs"] = inputs or {}
    raw["claims"] = claims
    cp = proj / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    flow.lock(cp)
    return IntakeApp([cp], token="t", sandbox="none")


def _sub(app, files):
    return app.submit("h1", {"files": {k: base64.b64encode(v.encode() if isinstance(v, str)
                                                            else v).decode()
                                       for k, v in files.items()}})


def test_locating_a_huge_report_is_bounded(tmp_path, vhome):
    import time
    app = _app(tmp_path, [{"id": "t", "verifier": "csv_total", "authority": "fact",
                           "params": {"csv": "input:s", "column": "a", "report": "report.md"}}],
               inputs={"s": {"path": "s.csv"}}, files={"s.csv": "a\n69\n"})
    t0 = time.time()
    code, res = _sub(app, {"report.md": "Total: 70\n" * 100_000})      # 1 MB，每一行都是同一個錯值
    assert code == 200 and res["outcome"] == "reject"
    assert time.time() - t0 < 20                                           # 修之前約 26 秒
    assert len(res["issues"]) <= 50


def test_traceback_paths_outside_the_submission_are_never_touched(tmp_path):
    from vacant_network.trace import locate as L
    (tmp_path / "main.py").write_text("x = 1\n")
    detail = ('File "/etc/passwd", line 1\nFile "../../etc/hosts", line 1\n'
              f'File "{tmp_path}/../x.py", line 2\nFile "/tmp/run/main.py", line 1\n')
    locs = L._loc_traceback({}, {}, {"detail": detail}, tmp_path)
    assert [(x.path, x.line) for x in locs] == [("main.py", 1)]           # 只有交來的那一個


def test_files_outside_the_deliverable_are_not_cited(tmp_path, vhome):
    app = _app(tmp_path, [{"id": "no_todo", "verifier": "text", "authority": "requirement",
                           "params": {"path": "**/*.md", "must_not_contain": ["TODO"]}}],
               deliverable=("docs/**",))
    code, res = _sub(app, {"docs/a.md": "TODO here\n", "node_modules/x/README.md": "TODO\n"})
    assert code == 200 and res["outcome"] == "reject"
    assert {i["path"] for i in res["issues"]} == {"docs/a.md"}


def test_exists_and_forbid_paths_point_at_the_real_place(tmp_path, vhome):
    app = _app(tmp_path, [
        {"id": "has_data", "verifier": "exists", "authority": "requirement",
         "params": {"paths": ["data/*.csv"]}},
        {"id": "no_env", "verifier": "forbid_paths", "authority": "requirement",
         "params": {"paths": ["**/.env"]}},
        {"id": "utf8", "verifier": "text", "authority": "requirement",
         "params": {"path": "notes.txt", "must_contain": ["x"]}}], deliverable=("**",))
    code, res = _sub(app, {"report.md": "ok\n", "config/.env": "K=v\n",
                           "notes.txt": b"\xff\xfe bad"})
    by = {i["claim_id"]: i for i in res["issues"]}
    assert by["has_data"]["path"] == "data/*.csv"
    assert by["no_env"]["path"] == "config/.env"
    assert by["utf8"]["note"] == "not UTF-8 text"
    assert "report.md" not in {i["path"] for i in res["issues"]}


def test_issue_fields_are_clipped(tmp_path, vhome):
    app = _app(tmp_path, [{"id": "no_x", "verifier": "text", "authority": "requirement",
                           "params": {"path": "report.md", "must_not_contain": ["X+"]}}])
    code, res = _sub(app, {"report.md": "X" * 50_000 + "\n"})
    assert all(len(str(i.get("value") or "")) <= 200 for i in res["issues"])
