"""`vacant trace show`（round 27 dogfood：在本機大專案上實跑找到兩處摩擦）。

1. 檔案改動觀察被永久關掉之後（一次增量掃描超過 8s 掛鉤時限 ⇒ recorder 關掃描，
   這是誠實邊界：寧可照實記「沒觀察到」也不擋 agent），`trace blame` 每一筆都回
   unattributable，但 `trace show` 的步驟視圖完全正常、看不出來——coverage 事件被
   靜默丟掉。病歷的主視圖必須把「觀察已停用」這個狀態寫出來（只在 blame 頁的
   小字裡有，等于沒有）。
2. 本機病歷 1900+ 步；看最近幾步只能 `vacant trace show | tail`。加 `--tail N`
   （只影響人的視圖；`--json` 仍是全量記錄）。
"""
from __future__ import annotations

import argparse
import json

import pytest

from vacant_network.intake import contract as C
from vacant_network.intake import keys
from vacant_network.trace import cli
from vacant_network.trace import recorder as R

SALES = "id,amount\n1,10\n2,20\n3,30\n"


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    keys.init_local()
    p = tmp_path / "proj"
    (p / "data").mkdir(parents=True)
    (p / "data" / "sales.csv").write_text(SALES)
    return p, R.Recorder(p)


def _step(rec: R.Recorder, sid: str, tool: str = "bash", actor: R.Actor | None = None):
    actor = actor or R.Actor("pi", "s1")
    rec.pre(sid, actor, tool, {})
    return rec.post(sid, actor, tool, {}, "")


def _args(**kw) -> argparse.Namespace:
    base = dict(contract=None, json=False, tail=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_show_surfaces_disabled_file_change_observation(proj, capsys, monkeypatch):
    p, rec = proj
    monkeypatch.chdir(p)
    _step(rec, "s1")
    # recorder 的真實停用路徑（recorder.py `_disable_scan`）就是這個事件
    rec._append("coverage", {"scan_disabled": "an incremental scan passed 8s"})
    _step(rec, "s2")
    assert cli.cmd_show(_args()) == 0
    out = capsys.readouterr().out
    line = next((l for l in out.splitlines() if "coverage" in l), None)
    assert line is not None, f"coverage state not surfaced in trace show:\n{out}"
    assert "disabled" in line
    assert "an incremental scan passed 8s" in line
    # 這是**目前狀態**：要印在步驟之前，而不是埋在流中間
    assert out.index(line) < out.index("pi:main")


def test_show_tail_limits_to_last_steps(proj, capsys, monkeypatch):
    p, rec = proj
    monkeypatch.chdir(p)
    for i in range(1, 5):
        _step(rec, f"s{i}")
    assert cli.cmd_show(_args(tail=2)) == 0
    out = capsys.readouterr().out
    step_lines = [l for l in out.splitlines() if "pi:main" in l and "bash" in l]
    assert len(step_lines) == 2
    assert cli.cmd_show(_args(tail=10)) == 0
    out = capsys.readouterr().out
    step_lines = [l for l in out.splitlines() if "pi:main" in l and "bash" in l]
    assert len(step_lines) == 4


def test_show_tail_keeps_gap_context_after_first_shown_step(proj, capsys, monkeypatch):
    p, rec = proj
    monkeypatch.chdir(p)
    _step(rec, "s1")
    rec._append("unrecorded_change", {"changes": [{"kind": "modify", "path": "data/sales.csv"}],
                                      "n": 1, "observed_at": "post_tool"})
    _step(rec, "s2")
    _step(rec, "s3")
    assert cli.cmd_show(_args(tail=2)) == 0
    out = capsys.readouterr().out
    assert "GAP" in out                      # s2 之前的缺口：在顯示窗口內，保留
    assert "pi:main" in out


def test_show_tail_rejects_zero(proj, monkeypatch):
    p, rec = proj
    monkeypatch.chdir(p)
    _step(rec, "s1")
    with pytest.raises(SystemExit, match="--tail"):
        cli.cmd_show(_args(tail=0))


def test_show_json_ignores_tail(proj, monkeypatch, capsys):
    p, rec = proj
    monkeypatch.chdir(p)
    for i in range(1, 4):
        _step(rec, f"s{i}")
    assert cli.cmd_show(_args(json=True, tail=1)) == 0
    evs = json.loads(capsys.readouterr().out)
    steps = [e for e in evs if e.get("type") == "step"]
    assert len(steps) == 3                    # --json 是全量記錄，不受視圖參數影響
