"""步驟邊界不變量（`trace/guard.py`）：在 `Recorder.post` 當下、在完整輸出上判定，回合結束只讀帳。

量測與對照：`ops/accountability/guard_bench.py`（同一組劇本、`VACANT_GUARD=0` 對照）。"""
import hashlib
import json

import pytest

from ops.accountability import guard_bench as B
from vacant_network.adapters import install as INS
from vacant_network.trace import blame
from vacant_network.trace import guard as G


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_GUARD"):
        monkeypatch.delenv(k, raising=False)
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
    return tmp_path


def _agent(env, files=None):
    p = env / "work" / "proj"
    p.mkdir(parents=True)
    for rel, c in (files or {}).items():
        (p / rel).parent.mkdir(parents=True, exist_ok=True)
        (p / rel).write_text(c)
    return B.Agent(p)


def _steps(a):
    return blame.Trace(a.recorder()).steps


# ── I1：測試結論在步驟邊界、完整輸出上判定 ─────────────────────────

@pytest.mark.parametrize("out,outcome", [
    ("5 passed in 0.1s", "passed"),
    ("1 failed, 4 passed", "failed"),
    ("Ran 5 tests\n\nFAILED (failures=1)", "failed"),
    ("collecting ...", "unreadable"),
])
def test_signal_test_outcome(out, outcome):
    sig = G.signal("Bash", {"command": "python -m pytest -q"}, out.encode(), None)
    assert sig["kind"] == "test" and sig["outcome"] == outcome


def test_signal_ignores_non_shell_tools():
    assert G.signal("Read", {"file_path": "/x"}, b"1 failed", None) is None


def test_grep_without_a_match_is_not_a_failure():
    sig = G.signal("Bash", {"command": "grep -n retry data.csv"}, b"", "exit 1")
    assert sig["kind"] == "shell" and sig["outcome"] == "ok" and not sig["shell_failed"]


def test_failure_summary_after_2mb_is_recorded_on_the_step(env):
    a = _agent(env, B.APP)
    B.s_huge_pytest_fail(a)
    g = _steps(a)[-1].guard
    assert g["kind"] == "test" and g["outcome"] == "failed"
    assert g["tail"][-1].startswith("1 failed")


# ── 精簡：大輸出只留頭＋尾＋出處（大小與 sha256） ─────────────────────

def test_compact_keeps_tail_and_provenance():
    data = (B.NOISE + "1 failed, 4 passed").encode()
    assert len(data) > G.MAX_OUTPUT_BLOB
    out = G.compact_output(data)
    assert len(out) < G.COMPACT_HEAD + G.COMPACT_TAIL + 400
    assert out.endswith(b"1 failed, 4 passed")
    assert out.startswith(data[:G.MAX_OUTPUT_BLOB])       # 舊的前 2MB 一個位元組都不少
    assert hashlib.sha256(data).hexdigest().encode() in out
    assert str(len(data)).encode() in out


def test_compact_is_identity_below_threshold():
    assert G.compact_output(b"small") == b"small"


def test_guard_off_keeps_the_old_truncation(monkeypatch):
    monkeypatch.setenv("VACANT_GUARD", "0")
    data = (B.NOISE + "1 failed").encode()
    assert G.compact_output(data) == data[:G.MAX_OUTPUT_BLOB]


# ── I2／I3：帳本 ────────────────────────────────────────────────────

def test_ledger_open_failure_closes_on_green_rerun():
    led: dict = {}
    fail = G.signal("Bash", {"command": "python3 build.py"}, b"Traceback (most recent call last):\nKeyError", None)
    G.ledger_update(led, 1, "python3 build.py", fail, [])
    assert [v["invariant"] for v in G.violations(led)] == ["open_failure"]
    ok = G.signal("Bash", {"command": "python3  build.py"}, b"2045.0", None)
    G.ledger_update(led, 2, "python3  build.py", ok, [])
    assert G.violations(led) == []


def test_ledger_stale_green_after_code_write():
    led: dict = {}
    G.ledger_update(led, 1, "pytest", G.signal("Bash", {"command": "pytest"}, b"3 passed", None), [])
    assert G.violations(led) == []
    G.ledger_update(led, 2, "", None, [{"path": "app.py"}])
    assert [v["invariant"] for v in G.violations(led)] == ["stale_green"]
    G.ledger_update(led, 3, "", None, [{"path": "README.md"}])
    G.ledger_update(led, 4, "pytest", G.signal("Bash", {"command": "pytest"}, b"3 passed", None), [])
    assert G.violations(led) == []


def test_recorder_keeps_a_per_session_ledger_and_a_new_prompt_resets_it(env):
    a = _agent(env, B.APP)
    B.s_stale(a)
    led = a.recorder().guard_ledger("claude", a.s)
    assert [v["invariant"] for v in G.violations(led)] == ["stale_green"]
    a.ask("Something else.")
    assert a.recorder().guard_ledger("claude", a.s) == {}


# ── 相容：沒有 guard 欄位的舊病歷照舊重新解析 ───────────────────────

def test_old_traces_without_guard_still_work(env, monkeypatch):
    monkeypatch.setenv("VACANT_GUARD", "0")
    a = _agent(env, B.APP)
    B.s_small_fail(a)
    assert all(s.guard is None for s in _steps(a))


# ── 精簡版病歷：沒有原始輸出，留結論、失敗尾巴與 sha256 ─────────────

def test_digest_is_small_and_keeps_failure_signal(env):
    a = _agent(env, B.APP)
    B.s_huge_pytest_fail(a)
    d = G.digest(a.recorder().events())
    blob = json.dumps(d, ensure_ascii=False)
    assert len(blob) < 4000
    last = d["steps"][-1]
    assert last["outcome"] == "failed" and "1 failed" in last["tail"]
    assert "heartbeat" not in blob


# ── 量測：同一組劇本，guard 對照舊行為 ──────────────────────────────

def test_bench_guard_beats_baseline_without_false_positives():
    res = B.run_all()
    b, g = res["baseline"], res["guard"]
    assert g["detected"] == g["positives"] and g["false_positives"] == 0
    assert b["false_positives"] == 0 and b["detected"] < g["detected"]
    assert g["pass_rate"] > b["pass_rate"]
