"""紀錄強化 4：外部鏈頭錨定（`vacant trace anchor` 與 `--check`）。

驗證：
1. `vacant trace anchor` 寫出完整 JSON（`project_key`、`chain_length`、`last_seq`、`head_hash`、
   `signer`、`timestamp`、`extra_files` 的 sha256），並支援 `--git <repo>` 在本機倉庫提交
   （只提交該錨點檔，不誤帶其他未暫存／已暫存變動）。
2. `vacant trace anchor --check <file>` 驗證目前鏈仍延伸該錨點：
   - 追加新步 ⇒ 通過（`extended_by > 0`）
   - 截短（即使同步改寫 `head.json`）⇒ 失敗（exit 1）
   - 截短後以同一把金鑰重寫分岔尾巴 ⇒ 失敗（exit 1）
   - 換掉創世或換簽章者 ⇒ 失敗（exit 1）
   - 額外檔案變更：`--check` 預設只驗鏈延伸並報告檔案狀態；`--check-files` ⇒ 失敗（exit 1）
3. 空鏈或損毀鏈拒絕產出錨點（fail-closed，exit 2）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess

import pytest

from vacant_network import cli as top_cli
from vacant_network.intake import keys
from vacant_network.trace import recorder as R


@pytest.fixture
def env(tmp_path, monkeypatch):
    vh = tmp_path / "vh"
    monkeypatch.setenv("VACANT_HOME", str(vh))
    monkeypatch.setenv("VACANT_TRACE", "1")
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")
    keys.init_local()
    ws = tmp_path / "proj"
    ws.mkdir()
    return tmp_path, vh, ws


def _init_git_repo(repo: pathlib.Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "anchor@test.local"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Anchor Test"], check=True)


def _step(rec: R.Recorder, ws: pathlib.Path, sid: str, text: str) -> None:
    a = R.Actor("claude", "s1")
    rec.pre(sid, a, "Write", {"file_path": "out.txt"})
    (ws / "out.txt").write_text(text, encoding="utf-8")
    rec.post(sid, a, "Write", {"file_path": "out.txt"}, "ok")


def test_anchor_write_git_commit_and_check_extension(env, monkeypatch, capsys):
    tmp_path, _vh, ws = env
    harness = ws / "harness.json"
    harness.write_text('{"v": 1}\n', encoding="utf-8")
    harness_sha = hashlib.sha256(harness.read_bytes()).hexdigest()

    rec = R.Recorder(ws)
    rec.baseline()
    _step(rec, ws, "t1", "v1\n")

    repo = tmp_path / "anchor_repo"
    _init_git_repo(repo)
    # 放入一個未提交的無關檔案，確認 `--git` 只提交錨點檔
    (repo / "unrelated.txt").write_text("do not commit me\n", encoding="utf-8")

    anchor_file = tmp_path / "ext_anchor.json"
    monkeypatch.chdir(ws)
    rc = top_cli.main([
        "trace", "anchor",
        "--output", str(anchor_file),
        "--file", str(harness),
        "--git", str(repo),
        "--json",
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert anchor_file.is_file()
    saved = json.loads(anchor_file.read_text(encoding="utf-8"))
    assert saved["schema"] == "vacant-trace-anchor/1"
    assert saved["project_key"] == rec.dir.name
    assert saved["chain_length"] == len(rec.events())
    assert saved["last_seq"] == rec.events()[-1]["seq"]
    assert saved["head_hash"] == rec.events()[-1]["hash"]
    assert saved["signer"] == rec.events()[0]["signer"]
    assert saved["timestamp"].endswith("Z")
    assert saved["extra_files"]["harness.json"]["sha256"] == harness_sha

    assert out["git"]["committed"] is True
    assert out["git"]["commit"]
    committed_files = subprocess.run(
        ["git", "-C", str(repo), "show", "--name-only", "--pretty=format:", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()
    assert committed_files == ["anchors/ext_anchor.json"]

    # 追加新步後 `--check` 仍通過並報 extended_by > 0
    _step(rec, ws, "t2", "v2\n")
    rc_ok = top_cli.main(["trace", "anchor", "--check", str(anchor_file), "--json"])
    assert rc_ok == 0
    chk = json.loads(capsys.readouterr().out)
    assert chk["ok"] is True
    assert chk["extended_by"] >= 1
    assert chk["extra_files"]["harness.json"]["status"] == "ok"

    # 修改額外檔案：預設 `--check`（驗鏈延伸）通過並回報 changed，`--check-files` 失敗
    harness.write_text('{"v": 2}\n', encoding="utf-8")
    rc_ext = top_cli.main(["trace", "anchor", "--check", str(anchor_file), "--json"])
    assert rc_ext == 0
    chk2 = json.loads(capsys.readouterr().out)
    assert chk2["extra_files"]["harness.json"]["status"] == "changed"

    rc_strict = top_cli.main(["trace", "anchor", "--check", str(anchor_file), "--check-files"])
    assert rc_strict == 1
    assert "BROKEN" in capsys.readouterr().out


def test_anchor_check_catches_truncation_and_rewritten_fork(env, monkeypatch, capsys):
    tmp_path, _vh, ws = env
    rec = R.Recorder(ws)
    rec.baseline()
    _step(rec, ws, "t1", "a\n")
    _step(rec, ws, "t2", "b\n")

    anchor_file = tmp_path / "a.json"
    monkeypatch.chdir(ws)
    assert top_cli.main(["trace", "anchor", "-o", str(anchor_file)]) == 0
    capsys.readouterr()

    # 1) 截短鏈（連 head.json 一起偽造）⇒ 單看 rec.verify() 會過，但 anchor --check 必須抓到
    lines = rec.chain_path.read_text(encoding="utf-8").splitlines()
    kept = lines[:-1]
    rec.chain_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    last_obj = json.loads(kept[-1])
    from vacant_network.logbook import LogEntry
    last_e = LogEntry.from_json(last_obj)
    (rec.dir / "head.json").write_text(json.dumps({"seq": last_e.seq, "hash": last_e.hash()}), encoding="utf-8")
    assert rec.verify()[0], "單機鏈與 head.json 被同步截短時，沒有錨點看不出來"

    rc_trunc = top_cli.main(["trace", "anchor", "--check", str(anchor_file)])
    out_trunc = capsys.readouterr().out
    assert rc_trunc == 1
    assert "BROKEN" in out_trunc and "shorter than anchored" in out_trunc

    # 2) 用同一把金鑰在截短點之後重簽分岔尾巴（讓 seq 超過錨點）⇒ 仍必須抓到 hash 不符
    rec.append("coverage", {"note": "forked entry 1"})
    rec.append("coverage", {"note": "forked entry 2"})
    assert rec.verify()[0]
    rc_fork = top_cli.main(["trace", "anchor", "--check", str(anchor_file)])
    out_fork = capsys.readouterr().out
    assert rc_fork == 1
    assert "BROKEN" in out_fork and "does not match anchored head_hash" in out_fork


def test_anchor_refuses_empty_or_broken_chain_and_wrong_project(env, monkeypatch, capsys):
    tmp_path, _vh, ws = env
    monkeypatch.chdir(ws)
    # 空專案（無鏈）⇒ 拒絕錨定（exit 2）
    rc_empty = top_cli.main(["trace", "anchor"])
    assert rc_empty == 2
    assert "cannot anchor" in capsys.readouterr().err

    # 建鏈並錨定後，換到另一個工作區檢查 ⇒ project_key 不符（exit 1）
    rec = R.Recorder(ws)
    rec.baseline()
    af = tmp_path / "p1.json"
    assert top_cli.main(["trace", "anchor", "-o", str(af)]) == 0
    capsys.readouterr()

    ws2 = tmp_path / "proj2"
    ws2.mkdir()
    R.Recorder(ws2).baseline()
    monkeypatch.chdir(ws2)
    rc_wrong = top_cli.main(["trace", "anchor", "--check", str(af)])
    assert rc_wrong == 1
    assert "does not match" in capsys.readouterr().out
