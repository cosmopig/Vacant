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
