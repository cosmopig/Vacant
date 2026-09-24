"""`vacant run --events`（`vacant.lifecycle/1`）的擋門測試。

四條各對應 `vacant_network/vrun/lifecycle.py` 的一條誠實邊界：

  · `test_default_writes_nothing_extra`
      沒開事件流 ⇒ 落盤形狀逐字不變（`run_<ARM>.json` 沒有多一個 key）。
  · `test_unwritable_events_path_changes_nothing`
      寫不進去 ⇒ 裁決、退出碼、wire 位元組一個都不動，但 `emit_errors` 看得見。
  · `test_stream_is_valid_and_ties_to_the_receipt`
      事件流過契約自檢，`model_call` 筆數＝`requests_seen`，
      `run_ended.verdict_hash`＝收據鏈最後一筆的雜湊（外面可以拿它去對鏈）。
  · `test_no_content_on_the_stream`
      request body 的任何一段都不准出現在事件流裡。

⚠ 本檔零模型呼叫：上游是本機假 server（借 `test_vacant_run.py` 的那一支）。
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from vacant_network.logbook import LogEntry                             # noqa: E402
from vacant_network.vrun import acceptance, launcher, lifecycle         # noqa: E402
from test_vacant_run import (AGENT_BODY, _agent, _suite, _ws,           # noqa: E402,F401
                             upstream)


def _go(tmp: pathlib.Path, upstream_url: str, monkeypatch, *, mode: str = "good",
        events=None, name: str = "a", vacant_on: bool = True) -> dict:
    monkeypatch.setenv("OPENAI_BASE_URL", upstream_url)
    monkeypatch.delenv(lifecycle.ENV_EVENTS, raising=False)
    ws = _ws(tmp, f"ws_{name}")
    return launcher.run(_agent(tmp, mode), workspace=ws, run_dir=tmp / f"run_{name}",
                        suite_dir=_suite(tmp), vacant_on=vacant_on,
                        task_id=f"lc_{name}", sandbox_name="none",
                        events_path=events,
                        events_caller={"cell_id": f"cell_{name}"})


def test_default_writes_nothing_extra(tmp_path, upstream, monkeypatch):
    s = _go(tmp_path, upstream[0], monkeypatch)
    assert "lifecycle" not in s
    on_disk = json.loads((tmp_path / "run_a" / "run_RUN-ON.json").read_text())
    assert "lifecycle" not in on_disk


def test_env_var_turns_it_on(tmp_path, upstream, monkeypatch):
    p = tmp_path / "env_events.jsonl"
    monkeypatch.setenv("OPENAI_BASE_URL", upstream[0])
    monkeypatch.setenv(lifecycle.ENV_EVENTS, str(p))
    ws = _ws(tmp_path, "ws_env")
    s = launcher.run(_agent(tmp_path, "good"), workspace=ws,
                     run_dir=tmp_path / "run_env", suite_dir=_suite(tmp_path),
                     vacant_on=True, task_id="lc_env", sandbox_name="none")
    assert s["lifecycle"]["emitted"] > 0
    assert lifecycle.read(p)[0]["type"] == "run_started"


@pytest.mark.parametrize("mode,accepted", [("good", True), ("bad", False)])
def test_stream_is_valid_and_ties_to_the_receipt(tmp_path, upstream, monkeypatch,
                                                 mode, accepted):
    p = tmp_path / "events.jsonl"
    s = _go(tmp_path, upstream[0], monkeypatch, mode=mode, events=p)
    evs = lifecycle.read(p)
    assert lifecycle.validate_stream(evs) == []
    types = [e["type"] for e in evs]
    assert types[0] == "run_started" and types[-1] == "run_ended"
    assert types.count("model_call") == s["requests_seen"] >= 1
    assert types.count("gate_ran") == 1
    end = evs[-1]
    assert end["accepted"] is accepted and end["stop_reason"] == s["stop_reason"]
    chain = (tmp_path / "run_a" / "receipts_RUN-ON.ndjson").read_text().splitlines()
    head = LogEntry.from_json(json.loads(chain[-1])).hash()
    assert end["verdict_hash"] == s["verdict_hash"] == head
    assert end["has_receipt"] is True
    assert evs[0]["caller"] == {"cell_id": "cell_a"}
    assert s["lifecycle"]["emitted"] == len(evs) and s["lifecycle"]["emit_errors"] == 0
    # 落盤的摘要也看得到事件流寫了幾筆
    on_disk = json.loads((tmp_path / "run_a" / "run_RUN-ON.json").read_text())
    assert on_disk["lifecycle"]["emitted"] == len(evs)
    if not accepted:
        gate = next(e for e in evs if e["type"] == "gate_ran")
        assert gate["passed"] is False and gate["failed_case"]


def test_off_arm_has_no_gate_and_no_receipt(tmp_path, upstream, monkeypatch):
    p = tmp_path / "events.jsonl"
    _go(tmp_path, upstream[0], monkeypatch, events=p, vacant_on=False)
    evs = lifecycle.read(p)
    assert lifecycle.validate_stream(evs) == []
    assert "gate_ran" not in [e["type"] for e in evs]
    end = evs[-1]
    assert end["accepted"] is None and end["has_receipt"] is False
    assert end["verdict_hash"] is None


def test_no_content_on_the_stream(tmp_path, upstream, monkeypatch):
    p = tmp_path / "events.jsonl"
    _go(tmp_path, upstream[0], monkeypatch, events=p)
    text = p.read_text(encoding="utf-8")
    assert '"messages"' not in text and "zz_last" not in text
    assert AGENT_BODY.decode()[:30] not in text


def test_unwritable_events_path_changes_nothing(tmp_path, upstream, monkeypatch):
    base = _go(tmp_path, upstream[0], monkeypatch, name="base")
    bad_path = tmp_path / "i_am_a_dir"
    bad_path.mkdir()
    s = _go(tmp_path, upstream[0], monkeypatch, name="bad", events=bad_path)
    for k in ("accepted", "refused", "stop_reason", "requests_seen",
              "attempts_used"):
        assert s[k] == base[k], k
    assert launcher.exit_code(s) == launcher.exit_code(base)
    assert s["lifecycle"]["emitted"] == 0 and s["lifecycle"]["emit_errors"] > 0
    assert s["lifecycle"]["last_error"]
    # 兩跑送出去的 body 逐位元相同：觀察者沒有碰 wire
    req = lambda n: sorted((tmp_path / f"run_{n}" / "wire_RUN-ON").glob("*.req.bin"))
    assert [f.read_bytes() for f in req("bad")] == [f.read_bytes() for f in req("base")]


def test_exception_still_ends_the_stream(tmp_path, upstream, monkeypatch):
    """例外打穿 `run()` ⇒ 照樣往上丟，但事件流要先說「結束了，沒有裁決」。"""
    def boom(*a, **k):
        raise RuntimeError("sandbox exploded")
    monkeypatch.setattr(acceptance, "run_suite", boom)
    p = tmp_path / "events.jsonl"
    with pytest.raises(RuntimeError):
        _go(tmp_path, upstream[0], monkeypatch, events=p)
    evs = lifecycle.read(p)
    assert lifecycle.validate_stream(evs) == []
    end = evs[-1]
    assert end["type"] == "run_ended" and end["accepted"] is None
    assert "sandbox exploded" in end["infra_void"]


def test_validate_catches_contract_breaks():
    good = [
        {"schema": lifecycle.SCHEMA, "type": "run_started", "run_id": "r", "seq": 1,
         "ts_ms": 1, "task_id": "t", "arm": "RUN-ON", "vacant": 1, "retry": "none",
         "max_attempts": 1, "feedback_into": "file", "ws_start_sha256": "x",
         "caller": None},
    ]
    assert lifecycle.validate_stream(good) == []
    gap = good + [{**good[0], "type": "model_call", "seq": 3, "attempt": 1,
                   "n_total": 1, "wire": "openai", "blocked": False,
                   "error": False, "elapsed_s": 0.1}]
    assert any("seq" in b for b in lifecycle.validate_stream(gap))
    leak = good + [{**gap[1], "seq": 2, "messages": []}]
    assert any("內容" in b for b in lifecycle.validate_stream(leak))
    missing = [{k: v for k, v in good[0].items() if k != "caller"}]
    assert any("caller" in b for b in lifecycle.validate_stream(missing))
    wrong = [{**good[0], "schema": "vacant.lifecycle/0"}]
    assert lifecycle.validate_stream(wrong)
