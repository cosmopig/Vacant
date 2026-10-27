"""`vacant trace show`（round 27 dogfood：在本機大專案上實跑找到兩處摩擦）。

1. 檔案改動觀察被永久關掉之後（一次增量掃描超過 8s 掛鉤時限 ⇒ recorder 關掃描，
   這是誠實邊界：寧可照實記「沒觀察到」也不擋 agent），`trace blame` 每一筆都回
   unattributable，但 `trace show` 的步驟視圖完全正常、看不出來——coverage 事件被
   靜默丟掉。病歷的主視圖必須把「觀察已停用」這個狀態寫出來（只在 blame 頁的
   小字裡有，等于沒有）。
2. 本機病歷 1900+ 步；看最近幾步只能 `vacant trace show | tail`。加 `--tail N`
   （只影響人的視圖；`--json` 仍是全量記錄）。
3. 本專案病歷 4062 個 bash 步、4055 個沒有歸屬寫入，`trace show` 印出的行是空的
   ——行沒有內容、看不出那步做了什麼（第 92 輪 dogfood）。工具輸入（實際做了什麼）
   存在物件庫裡；沒有歸屬寫入的步，show 印它的一行預覽。blob 被 gc 掉就退回空白行，
   `show` 永遠不因這個失敗（本專案 5094 個輸入 blob 已有 4930 個被 gc）。
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


def test_show_prints_input_preview_when_step_wrote_nothing(proj, capsys, monkeypatch):
    """沒有歸屬寫入的步（bash 99.8%、read 99.7%）：行必須有內容——工具輸入的一行預覽。"""
    p, rec = proj
    monkeypatch.chdir(p)
    actor = R.Actor("pi", "s1")
    rec.pre("b1", actor, "bash", {"command": "echo hello"})
    rec.post("b1", actor, "bash", {"command": "echo hello"}, "hello\n")
    rec.pre("r1", actor, "read", {"path": "data/sales.csv"})
    rec.post("r1", actor, "read", {"path": "data/sales.csv"}, "")
    assert cli.cmd_show(_args()) == 0
    out = capsys.readouterr().out
    bash_line = next(l for l in out.splitlines() if "bash" in l)
    assert "echo hello" in bash_line, f"bash step printed no content:\n{out}"
    read_line = next(l for l in out.splitlines() if " read " in l)
    assert "data/sales.csv" in read_line, f"read step printed no content:\n{out}"


def test_show_input_preview_truncates_long_input(proj, capsys, monkeypatch):
    p, rec = proj
    monkeypatch.chdir(p)
    actor = R.Actor("pi", "s1")
    cmd = "echo " + "x" * 300
    rec.pre("b1", actor, "bash", {"command": cmd})
    rec.post("b1", actor, "bash", {"command": cmd}, "")
    assert cli.cmd_show(_args()) == 0
    out = capsys.readouterr().out
    bash_line = next(l for l in out.splitlines() if "bash" in l)
    assert "x" * 100 not in bash_line           # 不整段貼進來
    assert "…" in bash_line                     # 截斷要看得出


def test_show_survives_gc_of_the_input_blob(proj, capsys, monkeypatch):
    """gc 會把 blob 刪掉（本專案歷史步 96% 的輸入 blob 已不在）：show 退回空白預覽，
    絕不因此失敗。"""
    p, rec = proj
    monkeypatch.chdir(p)
    actor = R.Actor("pi", "s1")
    rec.pre("b1", actor, "bash", {"command": "echo hello"})
    rec.post("b1", actor, "bash", {"command": "echo hello"}, "hello\n")
    sha = next(e["input_blob"] for e in rec.events() if e.get("type") == "step")
    rec.blobs.path(sha).unlink()                # 模擬 gc
    assert cli.cmd_show(_args()) == 0
    out = capsys.readouterr().out
    bash_line = next(l for l in out.splitlines() if "bash" in l)
    assert "echo hello" not in bash_line        # blob 不在 ⇒ 空白，不假裝還有


def test_show_names_the_workspace(proj, capsys, monkeypatch):
    """round 107 dogfood：步驟視圖不說自己是哪個專案的病歷——在錯的 cwd 跑會靜默看到
    別專案的步（no-trace 訊息、verify、dashboard 都帶專案名；show 主視圖沒有）。
    視圖首行必須是專案路徑，看的人才知道這是谁的病歷。"""
    p, rec = proj
    monkeypatch.chdir(p)
    _step(rec, "s1")
    assert cli.cmd_show(_args()) == 0
    out = capsys.readouterr().out
    first = out.splitlines()[0]
    assert str(p) in first, f"trace show does not name its workspace:\n{out}"


def test_show_json_ignores_tail(proj, monkeypatch, capsys):
    p, rec = proj
    monkeypatch.chdir(p)
    for i in range(1, 4):
        _step(rec, f"s{i}")
    assert cli.cmd_show(_args(json=True, tail=1)) == 0
    evs = json.loads(capsys.readouterr().out)
    steps = [e for e in evs if e.get("type") == "step"]
    assert len(steps) == 3                    # --json 是全量記錄，不受視圖參數影響
