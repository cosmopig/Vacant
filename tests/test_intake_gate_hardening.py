"""收件端的對抗審查回歸（2026-09-24，`decisions/DECISION_20260924_UNIVERSAL_INTAKE.md` §十一）。

每一條都是審查者**真的重現過**、讓不該進目的端的版本進去（或讓紀錄說錯話）的路：

- 同一個 task_id 的第二份契約（放行政策較鬆）⇒ 放得進委託者的目的端
- 冪等路徑（「同一版本已在目的端」）跳過裁決與契約檢查
- 公開端點跟隨任務目錄的符號連結、送出沒被放行的檔案
- 批准綁的是目的端**字串**：相對路徑在另一個目錄解析成另一個地方 ⇒ 單次批准用兩次；
  刪掉目的端的 state.json ⇒ 用過的批准與撤回過的任務復活
- git 目的端只看分支頂端 ⇒ 別的任務發布之後 replace=false 失效
- 帳本截短 ⇒ 被後來的 reject 取代的 accept 復活
- git 讀回沒用 `-z` ⇒ 非 ASCII 檔名永遠「缺檔」
- 放行失敗被記成 `released`（或完全沒記）
- 人工審查沒綁契約雜湊 ⇒ 舊契約下的審查滿足新契約改過定義的主張
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import urllib.request

import pytest

from vacant_network.intake import contract as C
from vacant_network.intake import flow
from vacant_network.intake.recipients import RECORD_NAME


@pytest.fixture()
def vhome(tmp_path, monkeypatch):
    h = tmp_path / "vhome"
    monkeypatch.setenv("VACANT_HOME", str(h))
    return h / "intake"


ME = os.environ.get("USER") or "local"      # keys.init_local 給本機 approver 的名字
EXISTS = [{"id": "has_report", "verifier": "exists", "params": {"paths": ["report.md"]}}]
MUST_BE_GOOD = [{"id": "good", "verifier": "text",
                 "params": {"path": "report.md", "must_contain": ["^GOOD$"]}}]


def _project(root: pathlib.Path, claims: list[dict], *, destination: str,
             release: dict | None = None, task_id: str = "report-001",
             lock: bool = True) -> pathlib.Path:
    (root / ".vacant").mkdir(parents=True, exist_ok=True)
    raw = C.scaffold(task_id, deliverable=["report.md", "**"], destination=destination)
    raw["claims"] = claims
    raw["release"].update(release or {})
    cp = root / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw, indent=2))
    if lock:
        flow.lock(cp)
    return cp


def _ws(root: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    root.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return root


# ── 契約鎖（需求權威）─────────────────────────────────────────────────

def test_a_second_unlocked_contract_cannot_release_into_the_owners_destination(tmp_path, vhome):
    dest = tmp_path / "published"
    cp = _project(tmp_path / "owner", EXISTS, destination=f"dir:{dest}",
                  release={"requires_approval": True, "approvers": ["boss"]})
    rogue = _project(tmp_path / "rogue", EXISTS, destination=f"dir:{dest}",
                     release={"requires_approval": False}, lock=False)
    assert C.load(cp).task_id == C.load(rogue).task_id
    task = flow.open_task(rogue)
    assert flow.submit(task, _ws(tmp_path / "w", {"report.md": "x"}), source="t")["outcome"] \
        == "accept"
    r = flow.release(task)
    assert r["released"] is False and any("never locked" in x for x in r["reasons"])
    assert not (dest / "report-001").exists()


def test_editing_the_contract_after_lock_requires_a_new_lock(tmp_path, vhome):
    cp = _project(tmp_path / "p", EXISTS, destination="dir:pub")
    raw = json.loads(cp.read_text())
    raw["release"]["replace"] = True
    cp.write_text(json.dumps(raw))
    task = flow.open_task(cp)
    flow.submit(task, _ws(tmp_path / "w", {"report.md": "x"}), source="t")
    assert flow.release(task)["released"] is False
    flow.lock(cp)
    assert flow.release(flow.open_task(cp))["released"] is True


# ── 冪等路徑也要過裁決與契約 ───────────────────────────────────────────

def test_already_published_is_not_released_again_under_a_stricter_contract(tmp_path, vhome):
    cp = _project(tmp_path / "p", EXISTS, destination="dir:pub")
    task = flow.open_task(cp)
    flow.submit(task, _ws(tmp_path / "w", {"report.md": "BAD"}), source="t")
    assert flow.release(task)["released"] is True
    raw = json.loads(cp.read_text())
    raw["claims"] = MUST_BE_GOOD
    raw["version"] = 2
    cp.write_text(json.dumps(raw))
    flow.lock(cp)
    task2 = flow.open_task(cp)
    art = flow.latest_artifact(flow.open_task(cp)) or \
        [e for e in task2.ledger.events() if e["type"] == "decision"][-1]["artifact_sha256"]
    assert flow.reverify(task2, art)["outcome"] == "reject"
    r = flow.release(task2, artifact_sha256=art)
    assert r["released"] is False and "not authorized" in r["reasons"][0]
    assert flow.status(task2)["state"] != "released"


def test_a_forged_destination_record_does_not_make_a_rejected_candidate_released(tmp_path,
                                                                                 vhome):
    cp = _project(tmp_path / "p", MUST_BE_GOOD, destination="dir:pub")
    task = flow.open_task(cp)
    res = flow.submit(task, _ws(tmp_path / "w", {"report.md": "BAD"}), source="t")
    assert res["outcome"] == "reject"
    target = tmp_path / "p" / "pub" / "report-001"
    target.mkdir(parents=True)
    (target / "report.md").write_text("BAD")
    (target / RECORD_NAME).write_text(json.dumps({"artifact_sha256": res["artifact_sha256"]}))
    r = flow.release(task, artifact_sha256=res["artifact_sha256"])
    assert r["released"] is False


# ── 批准綁解析後的目的端；nonce／撤回記在帳本 ───────────────────────────

def test_one_approval_cannot_be_spent_at_two_resolved_destinations(tmp_path, vhome):
    rel = {"requires_approval": True, "approvers": [ME]}
    a = _project(tmp_path / "a", EXISTS, destination="dir:published", release=rel)
    task = flow.open_task(a)
    flow.submit(task, _ws(tmp_path / "w", {"report.md": "x"}), source="t")
    appr = flow.approve(task)
    assert appr["payload"]["destination"] == f"dir:{(tmp_path / 'a' / 'published').resolve()}"
    assert flow.release(task, approval_doc=appr)["released"] is True
    # 逐位元相同的契約（同一個雜湊）放在另一個目錄：`dir:published` 解析到別處
    b_root = tmp_path / "b"
    (b_root / ".vacant").mkdir(parents=True)
    (b_root / ".vacant" / "contract.json").write_bytes(a.read_bytes())
    task_b = flow.open_task(b_root / ".vacant" / "contract.json")
    assert task_b.contract.sha256 == task.contract.sha256
    r = flow.release(task_b, artifact_sha256=appr["payload"]["artifact_sha256"],
                     approval_doc=appr)
    assert r["released"] is False and any("destination" in x for x in r["reasons"])


def test_deleting_recipient_state_does_not_revive_a_spent_approval_or_a_withdrawal(tmp_path,
                                                                                   vhome):
    cp = _project(tmp_path / "p", EXISTS, destination="dir:pub",
                  release={"requires_approval": True, "approvers": [ME], "replace": True})
    task = flow.open_task(cp)
    flow.submit(task, _ws(tmp_path / "w", {"report.md": "x"}), source="t")
    appr = flow.approve(task)
    assert flow.release(task, approval_doc=appr)["released"] is True
    flow.withdraw(task, reason="retract")
    state = tmp_path / "p" / "pub" / ".vacant-recipient" / "state.json"
    state.unlink()
    r = flow.release(task, approval_doc=appr)
    assert r["released"] is False
    assert any("withdrawn" in x for x in r["reasons"])
    assert any("already used" in x for x in r["reasons"])


# ── 帳本截短 ───────────────────────────────────────────────────────────

def test_truncating_the_ledger_after_the_recipient_saw_it_is_refused(tmp_path, vhome):
    """accept A（放行）→ B 被 reject、放行被拒（收件端看過這個狀態）→ 有人把帳本截回
    B 之前 ⇒ 收件端看得出來。"""
    cp = _project(tmp_path / "p", MUST_BE_GOOD, destination="dir:pub",
                  release={"replace": True})
    task = flow.open_task(cp)
    a = flow.submit(task, _ws(tmp_path / "w1", {"report.md": "GOOD"}), source="t")
    assert flow.release(task)["released"] is True
    before_b = task.ledger.path.read_text()
    b = flow.submit(task, _ws(tmp_path / "w2", {"report.md": "BAD"}), source="t")
    assert b["outcome"] == "reject"
    assert flow.release(task, artifact_sha256=b["artifact_sha256"])["released"] is False
    task.ledger.path.write_text(before_b)
    r = flow.release(flow.open_task(cp), artifact_sha256=a["artifact_sha256"])
    assert r["released"] is False and any("truncated" in x for x in r["reasons"])


# ── git 目的端 ─────────────────────────────────────────────────────────

def _git_repo(path: pathlib.Path) -> pathlib.Path:
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    return path


def test_git_replace_false_holds_after_another_task_publishes_on_the_branch(tmp_path, vhome):
    repo = _git_repo(tmp_path / "repo")
    t = _project(tmp_path / "t", EXISTS, destination=f"git:{repo}#main:t", task_id="task-t")
    u = _project(tmp_path / "u", EXISTS, destination=f"git:{repo}#main:u", task_id="task-u")
    tt, tu = flow.open_task(t), flow.open_task(u)
    flow.submit(tt, _ws(tmp_path / "a", {"report.md": "A"}), source="t")
    assert flow.release(tt)["released"] is True
    flow.submit(tu, _ws(tmp_path / "c", {"report.md": "C"}), source="t")
    assert flow.release(tu)["released"] is True
    flow.submit(tt, _ws(tmp_path / "b", {"report.md": "B"}), source="t")
    r = flow.release(tt)
    assert r["released"] is False and any("different version" in x for x in r["reasons"])
    shown = subprocess.run(["git", "-C", str(repo), "show", "main:t/report.md"],
                           capture_output=True, text=True).stdout
    assert shown == "A"


def test_git_readback_handles_non_ascii_paths(tmp_path, vhome):
    repo = _git_repo(tmp_path / "repo")
    cp = _project(tmp_path / "p", [{"id": "e", "verifier": "exists",
                                    "params": {"paths": ["報告.md"]}}],
                  destination=f"git:{repo}#main:d")
    task = flow.open_task(cp)
    flow.submit(task, _ws(tmp_path / "w", {"報告.md": "內容"}), source="t")
    r = flow.release(task)
    assert r["released"] is True and r["readback_ok"] is True, r


# ── 放行失敗的標記 ─────────────────────────────────────────────────────

def test_an_unmanaged_directory_at_the_destination_is_a_refusal_not_unconfirmed(tmp_path, vhome):
    cp = _project(tmp_path / "p", EXISTS, destination="dir:pub")
    task = flow.open_task(cp)
    flow.submit(task, _ws(tmp_path / "w", {"report.md": "x"}), source="t")
    (tmp_path / "p" / "pub" / "report-001").mkdir(parents=True)
    r = flow.release(task)
    assert r["released"] is False and not r.get("effect")
    assert flow.status(task)["state"] == "accepted"          # 不是 release_unconfirmed


def test_a_corrupt_recipient_state_is_recorded_as_void(tmp_path, vhome, monkeypatch, capsys):
    from vacant_network.intake import cli as vcli
    cp = _project(tmp_path / "p", EXISTS, destination="dir:pub")
    task = flow.open_task(cp)
    flow.submit(task, _ws(tmp_path / "w", {"report.md": "x"}), source="t")
    st = tmp_path / "p" / "pub" / ".vacant-recipient"
    st.mkdir(parents=True)
    (st / "state.json").write_text("{not json")
    monkeypatch.chdir(tmp_path / "p")
    assert vcli.main(["release"]) == vcli.EXIT["void"]
    assert [e for e in task.ledger.events() if e["type"] == "infra_void"]


# ── 審查綁契約 ─────────────────────────────────────────────────────────

def test_a_review_under_the_old_contract_does_not_satisfy_the_new_one(tmp_path, vhome):
    claims = [{"id": "legal", "verifier": "review", "authority": "quality",
               "description": "typo check"}]
    cp = _project(tmp_path / "p", claims, destination="dir:pub")
    task = flow.open_task(cp)
    flow.submit(task, _ws(tmp_path / "w", {"report.md": "x"}), source="t")
    flow.review(task, claim_id="legal", verdict="pass", reason="no typos")
    assert flow.reverify(task)["outcome"] == "accept"
    raw = json.loads(cp.read_text())
    raw["claims"][0]["description"] = "full legal sign-off"
    raw["version"] = 2
    cp.write_text(json.dumps(raw))
    flow.lock(cp)
    task2 = flow.open_task(cp)
    art = [e for e in task2.ledger.events() if e["type"] == "decision"][-1]["artifact_sha256"]
    assert flow.reverify(task2, art)["outcome"] == "hold"


def test_withdrawal_message_names_the_real_remedy(tmp_path, vhome):
    cp = _project(tmp_path / "p", EXISTS, destination="dir:pub")
    task = flow.open_task(cp)
    flow.submit(task, _ws(tmp_path / "w", {"report.md": "x"}), source="t")
    flow.release(task)
    flow.withdraw(task, reason="r")
    r = flow.release(task)
    assert any("new task_id" in x for x in r["reasons"])


# ── 公開端點 ───────────────────────────────────────────────────────────

@pytest.fixture()
def served(tmp_path, vhome):
    from http.server import ThreadingHTTPServer
    import threading
    from vacant_network.intake.server import IntakeApp, make_handler
    cp = _project(tmp_path / "p", EXISTS, destination="dir:pub")
    task = flow.open_task(cp)
    flow.submit(task, _ws(tmp_path / "w", {"report.md": "released text"}), source="t")
    assert flow.release(task)["released"] is True
    app = IntakeApp([cp], token="t")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", tmp_path / "p" / "pub"
    httpd.shutdown()


def _get(url: str) -> int:
    try:
        with urllib.request.urlopen(url) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_public_endpoint_serves_only_what_the_gate_released(served, tmp_path):
    base, pub = served
    assert _get(f"{base}/published/report-001/report.md") == 200
    (pub / "report-001" / "planted.md").write_text("never released")
    assert _get(f"{base}/published/report-001/planted.md") == 404
    (pub / "report-001" / "report.md").write_text("changed after release")
    assert _get(f"{base}/published/report-001/report.md") == 404


def test_public_endpoint_does_not_follow_a_symlinked_task_directory(served, tmp_path):
    base, pub = served
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "secret.md").write_text("not for the public")
    os.rename(pub / "report-001", tmp_path / "moved")
    os.symlink(elsewhere, pub / "report-001")
    assert _get(f"{base}/published/report-001/secret.md") == 404


# ── 驗證者回報的兩個殘留（同日第二輪）────────────────────────────────

def test_a_configured_remote_owner_is_not_bypassed_by_the_local_owner_key(tmp_path, vhome):
    from vacant_network.identity import Identity
    from vacant_network.intake import keys
    remote = Identity.generate()
    t = keys.Trust.load(vhome / "trust.json")
    t.add("owner", "principal", keys.pub_hex(remote))
    t.save()
    cp = _project(tmp_path / "p", EXISTS, destination="dir:pub")      # 本機金鑰簽的鎖
    task = flow.open_task(cp)
    assert task.trust.name_of("owner", keys.pub_hex(keys.load_or_create("owner"))) is None
    flow.submit(task, _ws(tmp_path / "w", {"report.md": "x"}), source="t")
    r = flow.release(task)
    assert r["released"] is False and any("not a trusted owner" in x for x in r["reasons"])


def test_a_hand_made_record_is_not_served_as_released(served, tmp_path):
    base, pub = served
    cp = tmp_path / "p" / ".vacant" / "contract.json"
    task = flow.open_task(cp)
    rec = json.loads((pub / "report-001" / RECORD_NAME).read_text())
    flow.withdraw(task, reason="retract")
    assert _get(f"{base}/published/report-001/report.md") == 404
    # 有人把撤回的目錄搬回來（紀錄檔、裁決都是真的）——帳本說它已撤回
    moved = next((pub / ".vacant-withdrawn").iterdir())
    os.rename(moved, pub / "report-001")
    assert (pub / "report-001" / RECORD_NAME).is_file() and rec["decision"]
    assert _get(f"{base}/published/report-001/report.md") == 404


# ── 驗證者回報的殘留（同日第三輪）────────────────────────────────────

def test_already_published_needs_an_approval_once_the_contract_requires_one(tmp_path, vhome):
    cp = _project(tmp_path / "p", EXISTS, destination="dir:pub")
    task = flow.open_task(cp)
    flow.submit(task, _ws(tmp_path / "w", {"report.md": "x"}), source="t")
    assert flow.release(task)["released"] is True
    raw = json.loads(cp.read_text())
    raw["release"].update(requires_approval=True, approvers=["nobody"])
    raw["version"] = 2
    cp.write_text(json.dumps(raw))
    flow.lock(cp)
    task2 = flow.open_task(cp)
    art = [e for e in task2.ledger.events() if e["type"] == "decision"][-1]["artifact_sha256"]
    assert flow.reverify(task2, art)["outcome"] == "accept"
    r = flow.release(task2, artifact_sha256=art)
    assert r["released"] is False and any("approval" in x for x in r["reasons"])
    assert flow.status(task2)["state"] != "released" or \
        flow.status(task2).get("live_under_previous_contract")


def test_a_self_signed_local_review_is_marked_same_account(tmp_path, vhome):
    claims = [{"id": "quality", "verifier": "review", "authority": "quality"}]
    cp = _project(tmp_path / "p", claims, destination="dir:pub")
    task = flow.open_task(cp)
    flow.submit(task, _ws(tmp_path / "w", {"report.md": "x"}), source="t")
    flow.review(task, claim_id="quality", verdict="pass", reason="ok")
    res = flow.reverify(task)
    q = [r for r in res["results"] if r["claim_id"] == "quality"][0]
    assert q["status"] == "PASS" and "same account" in q["detail"]
    assert q["evidence"]["independent"] is False
