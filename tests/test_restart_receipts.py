"""零設定重開模式（`vacant do` / `restart.py`）簽章收據測試（W5a，0 次模型呼叫）。

涵蓋：
1. 每次重開模式執行在專案既有 trace 簽章鏈（`$VACANT_HOME/trace/projects/<proj>/chain.ndjson`）
   附加一筆簽章 `restart_receipt`，同時保留 `result.json`；驗證所有必填欄位、快照樹雜湊與寫回雜湊。
2. `Launch.env` 與 `Launch.argv` 中的機密於收據內遮罩，但交給 agent 行程的真實 env 與 argv 一位元不改。
3. 多輪執行同專案接續同一條鏈、確定性快照樹雜湊、`vacant trace verify` 與 `vacant trace show`。
4. 對抗性測試：篡改收據、偽造不同簽章者、截斷鏈（尾端／中段／創世／半行）、對調條目順序、混簽章 fail-open。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import textwrap

import pytest

from vacant_network.adapters import cli as adapters_cli
from vacant_network.adapters import restart as R
from vacant_network.adapters.run import Launch
from vacant_network.canonical import canonical_bytes
from vacant_network.identity import Identity
from vacant_network.intake import keys as _keys
from vacant_network.logbook import Logbook
from vacant_network.trace import cli as trace_cli
from vacant_network.trace.recorder import Recorder, project_key

TEST = textwrap.dedent("""\
    import unittest
    from sol import f
    class T(unittest.TestCase):
        def test_one(self):
            self.assertEqual(f(1), 2)
        def test_two(self):
            self.assertEqual(f(41), 42)
    """)
GOOD = "def f(x):\n    return x + 1\n"
BAD = "def f(x):\n    return x\n"

AGENT = textwrap.dedent("""\
    import json, os, pathlib
    st = pathlib.Path(os.environ["STUB_STATE"])
    n = json.loads(st.read_text())["n"] + 1 if st.exists() else 1
    st.write_text(json.dumps({"n": n}))
    plan = os.environ["STUB_PLAN"].split(",")
    what = plan[min(n, len(plan)) - 1]
    if what == "tamper":
        pathlib.Path("sol_test.py").write_text("import unittest\\nclass T(unittest.TestCase):\\n    def test_a(self):\\n        pass\\n")
        pathlib.Path("sol.py").write_text(%r)
    elif what == "good_plus":
        pathlib.Path("sol.py").write_text(%r)
        pathlib.Path("extra.txt").write_text("added file\\n")
        if pathlib.Path("dropme.txt").exists():
            pathlib.Path("dropme.txt").unlink()
        if pathlib.Path("link").is_symlink():
            os.unlink("link")
            os.mkdir("link")
            pathlib.Path("link/evil.txt").write_text("escape attempt\\n")
    elif what == "good":
        pathlib.Path("sol.py").write_text(%r)
    elif what == "bad":
        pathlib.Path("sol.py").write_text(%r)
    """) % (BAD, GOOD, GOOD, BAD)


@pytest.fixture()
def env_proj(tmp_path, monkeypatch):
    vh = tmp_path / "vacant_home"
    vw = tmp_path / "vacant_work"
    monkeypatch.setenv("VACANT_HOME", str(vh))
    monkeypatch.setenv("VACANT_WORK", str(vw))
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "sol_test.py").write_text(TEST, encoding="utf-8")
    (proj / "sol.py").write_text("def f(x):\n    raise NotImplementedError\n", encoding="utf-8")
    (proj / "dropme.txt").write_text("remove me\n", encoding="utf-8")
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    os.symlink(outside, proj / "link")
    return proj, vh, vw, outside


def _build(tmp_path: pathlib.Path, plan: str, *, extra_env: dict[str, str] | None = None,
           extra_argv: list[str] | None = None, name: str = "agent.py"):
    script = tmp_path / name
    script.write_text(AGENT, encoding="utf-8")
    state = tmp_path / f"{name}.state.json"
    env = {"STUB_STATE": str(state), "STUB_PLAN": plan, **(extra_env or {})}

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=[sys.executable, str(script), *(extra_argv or []), prompt], env=dict(env))

    return build


def _manual_tree_sha(snap_root: pathlib.Path) -> str:
    files: dict[str, str] = {}
    for dp, _dns, fns in os.walk(snap_root):
        for fn in fns:
            p = pathlib.Path(dp) / fn
            rel = p.relative_to(snap_root).as_posix()
            files[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(files[rel].encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def test_restart_run_appends_one_signed_receipt_with_all_fields(env_proj, tmp_path, monkeypatch, capsys):
    proj, vh, _vw, outside = env_proj
    prompt = "make sol.f(x) return x + 1 and add extra.txt"
    res = R.run(proj, _build(tmp_path, "tamper,good_plus"), prompt,
                attempt_timeout_s=20, budget_s=120, agent="stub-agent")

    assert res["accepted"] is True
    assert res["delivered_attempt"] == 2
    assert res["receipt"]["recorded"] is True
    assert res["receipt"]["schema"] == R.RECEIPT_SCHEMA
    assert res["receipt"]["project_key"] == project_key(proj)

    # result.json 完整保留並含 receipt 參照
    result_path = pathlib.Path(res["run_dir"]) / "result.json"
    assert result_path.is_file()
    saved = json.loads(result_path.read_text(encoding="utf-8"))
    assert saved["receipt"] == res["receipt"]

    # 鏈上恰好 1 筆 trace_genesis + 1 筆 restart_receipt
    rec = Recorder(proj)
    assert rec.chain_path.is_file()
    events = rec.events()
    assert [e["type"] for e in events] == ["trace_genesis", "restart_receipt"]
    rcpt = events[1]

    # 逐項核對必填欄位
    assert rcpt["receipt_schema"] == R.RECEIPT_SCHEMA
    assert rcpt["schema"] == "vacant-trace/1"
    assert rcpt["request_sha256"] == hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    assert rcpt["agent"] == "stub-agent"
    assert isinstance(rcpt["argv"], list) and len(rcpt["argv"]) >= 2
    assert rcpt["project_path_sha256"] == hashlib.sha256(str(proj.resolve()).encode("utf-8")).hexdigest()
    assert rcpt["project_key"] == project_key(proj)
    assert rcpt["acceptance"]["kind"] == "python_unittest"
    assert rcpt["acceptance"]["command"]
    assert rcpt["acceptance"]["protected"] == ["sol_test.py"]
    assert rcpt["delivered_attempt"] == 2
    assert rcpt["accepted"] is True

    # 每次嘗試欄位 + 確定性快照樹雜湊
    assert len(rcpt["attempts"]) == 2
    a1, a2 = rcpt["attempts"]
    assert a1["attempt"] == 1 and a1["accept"] is False
    assert a1["rc"] == 0 and a1["timed_out"] is False
    assert a1["passed"] == 0 and a1["run"] == 2 and a1["status"] == "ok"
    assert a1["tests_tampered"] == ["sol_test.py"]
    assert isinstance(a1["wall_s"], (int, float))

    assert a2["attempt"] == 2 and a2["accept"] is True
    assert a2["passed"] == 2 and a2["run"] == 2 and a2["status"] == "ok"
    assert a2["tests_tampered"] == []

    # 獨立從磁碟快照目錄重算 snapshot_tree_sha256 驗證完全一致
    for k, att in enumerate((a1, a2), start=1):
        snap_dirs = list((pathlib.Path(res["run_dir"]) / f"attempt_{k}").glob("snap-*"))
        assert len(snap_dirs) == 1
        assert att["snapshot_tree_sha256"] == _manual_tree_sha(snap_dirs[0])

    # 寫回檔案＋sha256、刪除與跳過路徑
    wb_by_path = {x["path"]: x for x in rcpt["written_back"]}
    assert set(wb_by_path) == {"sol.py", "extra.txt"}
    assert wb_by_path["sol.py"]["op"] == "modified"
    assert wb_by_path["sol.py"]["sha256"] == hashlib.sha256(GOOD.encode("utf-8")).hexdigest()
    assert wb_by_path["extra.txt"]["op"] == "added"
    assert wb_by_path["extra.txt"]["sha256"] == hashlib.sha256(b"added file\n").hexdigest()
    assert rcpt["deleted"] == ["dropme.txt"]
    assert rcpt["skipped"] == ["link/evil.txt"]
    assert list(outside.iterdir()) == []

    # 離線驗章：API + `vacant trace verify` + `vacant trace show`
    ok, why, receipts = R.verify_receipts(proj, state_root=vh, expected_head=res["receipt"])
    assert ok, why
    assert len(receipts) == 1

    monkeypatch.chdir(proj)
    assert trace_cli.main(["trace", "verify"]) == 0
    out_v = capsys.readouterr().out
    assert out_v.startswith("OK ")

    assert trace_cli.main(["trace", "show"]) == 0
    out_s = capsys.readouterr().out
    assert "restart stub-agent PASS" in out_s


def test_receipt_redacts_secrets_in_env_and_argv_without_changing_agent_env(env_proj, tmp_path):
    proj, vh, _vw, _ = env_proj
    seen_file = tmp_path / "agent_seen.json"
    script = tmp_path / "secret_agent.py"
    script.write_text(textwrap.dedent(f"""\
        import json, os, pathlib, sys
        pathlib.Path({str(seen_file)!r}).write_text(json.dumps({{
            "argv": sys.argv,
            "openai": os.environ.get("OPENAI_API_KEY"),
            "token": os.environ.get("MY_AUTH_TOKEN"),
            "pass": os.environ.get("DB_PASSWORD"),
            "bearer": os.environ.get("CUSTOM_HDR"),
            "safe": os.environ.get("SAFE_MODE"),
        }}))
        pathlib.Path("sol.py").write_text({GOOD!r})
        """), encoding="utf-8")

    secret_openai = "sk-proj-supersecretvalue123456"
    secret_token = "ghp_secretTokenValue9876543210"
    secret_pass = "hunter2_very_secret_pw"
    secret_bearer = "Bearer eyJhbGciOiJIUzI1NiJ9.secretpayload"
    secret_argv_tok = "topsecret_cli_token_xyz"
    secret_argv_key = "sk-ant-cliSecretKey999999"

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(
            argv=[
                sys.executable, str(script),
                f"--api-key={secret_argv_key}",
                "--token", secret_argv_tok,
                "--mode", "fast",
                prompt,
            ],
            env={
                "OPENAI_API_KEY": secret_openai,
                "MY_AUTH_TOKEN": secret_token,
                "DB_PASSWORD": secret_pass,
                "CUSTOM_HDR": secret_bearer,
                "SAFE_MODE": "enabled",
            },
        )

    res = R.run(proj, build, "fix sol.py", attempt_timeout_s=20, budget_s=120, agent="secret-test")
    assert res["accepted"] is True

    # HARD RULE：agent 收到的真實 env / argv 完全沒有被改動
    seen = json.loads(seen_file.read_text(encoding="utf-8"))
    assert seen["openai"] == secret_openai
    assert seen["token"] == secret_token
    assert seen["pass"] == secret_pass
    assert seen["bearer"] == secret_bearer
    assert seen["safe"] == "enabled"
    assert f"--api-key={secret_argv_key}" in seen["argv"]
    assert secret_argv_tok in seen["argv"]

    # 收據與整份 chain.ndjson 絕不洩漏任何機密原文
    rec = Recorder(proj)
    raw_chain = rec.chain_path.read_text(encoding="utf-8")
    for s in (secret_openai, secret_token, secret_pass, secret_bearer, secret_argv_tok, secret_argv_key):
        assert s not in raw_chain, f"secret leaked into chain.ndjson: {s}"

    ok, why, receipts = R.verify_receipts(proj, state_root=vh)
    assert ok, why
    rcpt = receipts[0]
    assert rcpt["env"]["OPENAI_API_KEY"] == "[REDACTED]"
    assert rcpt["env"]["MY_AUTH_TOKEN"] == "[REDACTED]"
    assert rcpt["env"]["DB_PASSWORD"] == "[REDACTED]"
    assert rcpt["env"]["CUSTOM_HDR"] == "[REDACTED]"
    assert rcpt["env"]["SAFE_MODE"] == "enabled"
    assert "--api-key=[REDACTED]" in rcpt["argv"]
    tok_idx = rcpt["argv"].index("--token")
    assert rcpt["argv"][tok_idx + 1] == "[REDACTED]"


def test_multiple_runs_append_to_same_chain_and_snapshot_hash_deterministic(env_proj, tmp_path):
    proj, vh, _vw, _ = env_proj
    r1 = R.run(proj, _build(tmp_path, "bad", name="a1.py"), "run 1", max_attempts=1,
               attempt_timeout_s=20, budget_s=120, agent="agent-a")
    r2 = R.run(proj, _build(tmp_path, "good", name="a2.py"), "run 2", max_attempts=1,
               attempt_timeout_s=20, budget_s=120, agent="agent-b")
    assert r1["accepted"] is False and r2["accepted"] is True

    ok, why, receipts = R.verify_receipts(proj, state_root=vh, expected_head=r2["receipt"])
    assert ok, why
    assert len(receipts) == 2
    assert [x["agent"] for x in receipts] == ["agent-a", "agent-b"]
    assert [x["seq"] for x in receipts] == [2, 3]
    # 快照樹雜湊對不同內容產生不同雜湊
    h1 = receipts[0]["attempts"][0]["snapshot_tree_sha256"]
    h2 = receipts[1]["attempts"][0]["snapshot_tree_sha256"]
    assert h1 and h2 and h1 != h2


def test_adversarial_edited_receipt_detected(env_proj, tmp_path, monkeypatch, capsys):
    proj, vh, _vw, _ = env_proj
    res = R.run(proj, _build(tmp_path, "bad"), "fix it", max_attempts=1,
                attempt_timeout_s=20, budget_s=120, agent="stub")
    assert res["accepted"] is False

    rec = Recorder(proj)
    lines = rec.chain_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    tampered = json.loads(lines[1])
    tampered["payload"]["accepted"] = True  # 企圖把失敗偽造成通過
    lines[1] = canonical_bytes(tampered).decode("utf-8")
    rec.chain_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, why, _ = R.verify_receipts(proj, state_root=vh)
    assert ok is False, why

    monkeypatch.chdir(proj)
    assert trace_cli.main(["trace", "verify"]) == 1
    assert "BROKEN" in capsys.readouterr().out


def test_adversarial_forged_receipt_wrong_signer_detected(env_proj, tmp_path, monkeypatch, capsys):
    proj, vh, _vw, _ = env_proj
    res = R.run(proj, _build(tmp_path, "good"), "fix it", max_attempts=1,
                attempt_timeout_s=20, budget_s=120, agent="stub")
    assert res["receipt"]["recorded"] is True

    # 情境 1：攻擊者用自己的 Ed25519 金鑰重簽整條鏈與 head.json（不在 trust.json）
    rec = Recorder(proj)
    attacker = Identity.generate()
    att_pub = _keys.pub_hex(attacker)
    forged = Logbook()
    e1 = forged.append("trace_genesis",
                       {"schema": "vacant-trace/1", "workspace": str(proj), "signer": att_pub},
                       attacker, ts_ms=1700000000000)
    e2 = forged.append("restart_receipt",
                       {"schema": "vacant-trace/1", "receipt_schema": R.RECEIPT_SCHEMA,
                        "agent": "forged", "accepted": True},
                       attacker, ts_ms=1700000000001)
    forged.save(rec.chain_path)
    (rec.dir / "head.json").write_text(json.dumps({"seq": e2.seq, "hash": e2.hash()}), encoding="utf-8")

    ok, why, _ = R.verify_receipts(proj, state_root=vh)
    assert ok is False
    assert "accepted-signer" in why

    monkeypatch.chdir(proj)
    assert trace_cli.main(["trace", "verify"]) == 1
    assert "BROKEN" in capsys.readouterr().out

    # 情境 2：從合法鏈上追加一筆攻擊者簽章的偽造條目
    proj2 = tmp_path / "proj2"
    proj2.mkdir()
    (proj2 / "sol_test.py").write_text(TEST, encoding="utf-8")
    (proj2 / "sol.py").write_text(GOOD, encoding="utf-8")
    R.run(proj2, _build(tmp_path, "good", name="a_legit.py"), "ok", max_attempts=1,
          attempt_timeout_s=20, budget_s=120, agent="legit")
    rec2 = Recorder(proj2)
    book = Logbook.load(rec2.chain_path)
    e_fake = book.append("restart_receipt", {"schema": "vacant-trace/1", "accepted": True},
                         attacker, ts_ms=1700000001000)
    book.save(rec2.chain_path)
    (rec2.dir / "head.json").write_text(json.dumps({"seq": e_fake.seq, "hash": e_fake.hash()}), encoding="utf-8")

    ok2, _why2, _ = R.verify_receipts(proj2, state_root=vh)
    assert ok2 is False
    monkeypatch.chdir(proj2)
    assert trace_cli.main(["trace", "verify"]) == 1


def test_adversarial_truncated_chain_detected(env_proj, tmp_path, monkeypatch, capsys):
    proj, vh, _vw, _ = env_proj
    R.run(proj, _build(tmp_path, "bad", name="t1.py"), "p1", max_attempts=1,
          attempt_timeout_s=20, budget_s=120, agent="a1")
    r2 = R.run(proj, _build(tmp_path, "good", name="t2.py"), "p2", max_attempts=1,
               attempt_timeout_s=20, budget_s=120, agent="a2")

    rec = Recorder(proj)
    orig_chain = rec.chain_path.read_bytes()
    orig_head = (rec.dir / "head.json").read_bytes()
    lines = orig_chain.decode("utf-8").splitlines()
    assert len(lines) == 3

    monkeypatch.chdir(proj)

    # (1) 截掉尾端最後一筆（保留 head.json）
    rec.chain_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    ok, _why, _ = R.verify_receipts(proj, state_root=vh)
    assert ok is False
    assert trace_cli.main(["trace", "verify"]) == 1
    assert "BROKEN" in capsys.readouterr().out

    # (2) 截掉尾端並刪掉 head.json，但以 result.json["receipt"] 當錨點
    (rec.dir / "head.json").unlink()
    ok_a, _why_a, _ = R.verify_receipts(proj, state_root=vh, expected_head=r2["receipt"])
    assert ok_a is False

    # (3) 截掉中段（刪掉第 2 筆）
    (rec.dir / "head.json").write_bytes(orig_head)
    rec.chain_path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")
    assert R.verify_receipts(proj, state_root=vh)[0] is False
    assert trace_cli.main(["trace", "verify"]) == 1

    # (4) 截掉創世（刪掉第 1 筆）
    rec.chain_path.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
    assert R.verify_receipts(proj, state_root=vh)[0] is False
    assert trace_cli.main(["trace", "verify"]) == 1

    # (5) 半行截斷（砍掉結尾 20 bytes）
    rec.chain_path.write_bytes(orig_chain[:-20])
    assert R.verify_receipts(proj, state_root=vh)[0] is False
    assert trace_cli.main(["trace", "verify"]) == 1


def test_adversarial_reordered_entries_detected(env_proj, tmp_path, monkeypatch, capsys):
    proj, vh, _vw, _ = env_proj
    R.run(proj, _build(tmp_path, "bad", name="r1.py"), "p1", max_attempts=1,
          attempt_timeout_s=20, budget_s=120, agent="a1")
    R.run(proj, _build(tmp_path, "good", name="r2.py"), "p2", max_attempts=1,
          attempt_timeout_s=20, budget_s=120, agent="a2")

    rec = Recorder(proj)
    lines = rec.chain_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    # 對調第 2 與第 3 筆
    rec.chain_path.write_text("\n".join([lines[0], lines[2], lines[1]]) + "\n", encoding="utf-8")

    ok, _why, _ = R.verify_receipts(proj, state_root=vh)
    assert ok is False

    monkeypatch.chdir(proj)
    assert trace_cli.main(["trace", "verify"]) == 1
    assert "BROKEN" in capsys.readouterr().out


def test_receipt_fail_open_on_mixed_signer_preserves_delivery(env_proj, tmp_path):
    proj, vh, _vw, _ = env_proj
    # 預先放一條由不同金鑰簽的鏈（觸發 MixedSignerRefused）
    other = Identity.generate()
    rec = Recorder(proj)
    rec.dir.mkdir(parents=True, exist_ok=True)
    book = Logbook()
    e1 = book.append("trace_genesis",
                     {"schema": "vacant-trace/1", "workspace": str(proj), "signer": _keys.pub_hex(other)},
                     other, ts_ms=1700000000000)
    book.save(rec.chain_path)
    (rec.dir / "head.json").write_text(json.dumps({"seq": e1.seq, "hash": e1.hash()}), encoding="utf-8")
    before_chain = rec.chain_path.read_bytes()

    res = R.run(proj, _build(tmp_path, "good"), "fix it", max_attempts=1,
                attempt_timeout_s=20, budget_s=120, agent="stub")
    # 交回正常完成，既有鏈未被污染，receipt 誠實記為未記錄
    assert res["accepted"] is True
    assert (proj / "sol.py").read_text(encoding="utf-8") == GOOD
    assert res["receipt"]["recorded"] is False
    assert "MixedSignerRefused" in res["receipt"]["error"]
    assert rec.chain_path.read_bytes() == before_chain


def test_cli_vacant_do_records_receipt_with_agent_name(env_proj, tmp_path, monkeypatch, capsys):
    proj, vh, _vw, _ = env_proj
    script = tmp_path / "cli_agent.py"
    script.write_text(AGENT, encoding="utf-8")
    monkeypatch.setenv("STUB_STATE", str(tmp_path / "cli_state.json"))
    monkeypatch.setenv("STUB_PLAN", "bad,good")
    monkeypatch.chdir(proj)

    rc = adapters_cli.main([
        "do", "--cmd", f"{sys.executable} {script} {{prompt}}",
        "--prompt", "make tests pass", "--attempt-timeout", "20",
    ])
    assert rc == 0
    capsys.readouterr()

    ok, why, receipts = R.verify_receipts(proj, state_root=vh)
    assert ok, why
    assert len(receipts) == 1
    assert receipts[0]["agent"] == "generic"
    assert receipts[0]["accepted"] is True
    assert receipts[0]["delivered_attempt"] == 2

    assert trace_cli.main(["trace", "verify"]) == 0
    assert capsys.readouterr().out.startswith("OK ")
