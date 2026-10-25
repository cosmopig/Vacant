"""`trace blame`／`trace flag` 報告的覆蓋率行＝實際病歷（round 27 dogfood 摩擦 3）。

修前：`cmd_blame`／`cmd_flag` 傳空 dict 給 `render_report`，報告永遠寫
`recorded steps: 0; unrecorded changes (gaps): 0`——和 `trace show`（1787 步）字面矛盾，
讓人以為病歷是空的。修後：
- 覆蓋率行照實際病歷算（步數、缺口數、post_missing）
- 觀察被停用時把原因和出路（`vacant trace rescan`）寫進同一行，而不是只留一個 0
- 觀察活著時字樣不變（多出來的句子不該出現）
"""
from __future__ import annotations

import json
import subprocess

import vacant_network.intake.contract as C
import vacant_network.intake.keys as keys
from vacant_network.trace import cli, feedback as F, recorder as R


def _proj(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.delenv("VACANT_TRACE", raising=False)
    keys.init_local()
    p = tmp_path / "proj"
    (p / ".vacant").mkdir(parents=True)
    monkeypatch.chdir(p)  # blame 的相對路徑對 cwd 解析
    (p / "a.txt").write_text("hello\n")
    raw = C.scaffold("cov", deliverable=["a.txt"])
    cp = p / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    C.lock(cp)
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kw: None)
    return p


def _add_steps(p, n: int = 3):
    rec = R.Recorder(p)
    for i in range(n):
        rec.pre(f"t{i}", R.Actor("claude", "s1"), "Bash", {"command": "ls"})
        rec.post(f"t{i}", R.Actor("claude", "s1"), "Bash", {"command": "ls"}, "")
    return rec


def _disable_scan(p, why: str = "an incremental scan passed 8s") -> None:
    """走 recorder 自己的停用路徑（coverage 事件＋state），不手寫事件。"""
    rec = R.Recorder(p)
    st = json.loads(rec.state_path.read_text())
    rec._disable_scan(st, why)
    rec.state_path.write_text(json.dumps(st))


def test_blame_coverage_line_is_real_steps(tmp_path, monkeypatch, capsys):
    p = _proj(tmp_path, monkeypatch)
    _add_steps(p, 3)
    rc = cli.main(["--contract", str(p / ".vacant/contract.json"), "blame", "a.txt:1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "recorded steps: 3" in out
    # 觀察活著：停用那句話不該出現
    assert "observation is disabled" not in out


def test_blame_when_scan_disabled_shows_real_steps_and_exit_path(tmp_path, monkeypatch, capsys):
    p = _proj(tmp_path, monkeypatch)
    _add_steps(p, 2)
    _disable_scan(p)
    rc = cli.main(["--contract", str(p / ".vacant/contract.json"), "blame", "a.txt:1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "recorded steps: 2" in out                    # 不再是永遠的 0
    assert "observation is disabled (an incremental scan passed 8s)" in out
    assert "steps are recorded, but file changes are not attributed step by step" in out
    assert "vacant trace rescan" in out


def test_flag_report_uses_real_coverage(tmp_path, monkeypatch, capsys):
    p = _proj(tmp_path, monkeypatch)
    _add_steps(p, 4)
    _disable_scan(p)
    import argparse
    ns = argparse.Namespace(dismiss=None, where="a.txt:1", value=None,
                            note="looks off", json=False,
                            contract=str(p / ".vacant" / "contract.json"))
    rc = cli.cmd_flag(ns)
    assert rc == 0
    out = capsys.readouterr().out
    assert "recorded steps: 4" in out
    assert "vacant trace rescan" in out


def test_coverage_summary_counts_steps_gaps_and_state(tmp_path, monkeypatch):
    p = _proj(tmp_path, monkeypatch)
    _add_steps(p, 2)
    rec = R.Recorder(p)
    rec._append("unrecorded_change", {"changes": [{"path": "b.txt", "sha256": "x"}], "n": 1,
                                      "before_index": None, "after_index": None,
                                      "observed_at": "test"})
    cov = F.coverage_summary(R.Recorder(p))
    assert cov["steps"] == 2 and cov["gaps"] == 1 and cov["post_missing"] == 0
    assert "scan_disabled" not in cov
    _disable_scan(p, "the last recorded view of the workspace is unreadable (ValueError)")
    cov = F.coverage_summary(R.Recorder(p))
    assert cov["scan_disabled"] == "the last recorded view of the workspace is unreadable (ValueError)"


def test_render_report_scandisabled_annotation_only_when_present():
    base = dict(blames=[], results=[], outcome=None, why_open=None)
    with_sd = F.render_report(coverage={"steps": 5, "gaps": 0, "post_missing": 0,
                                        "scan_disabled": "an incremental scan passed 8s"}, **base)
    assert "recorded steps: 5" in with_sd
    assert "observation is disabled (an incremental scan passed 8s)" in with_sd
    assert "vacant trace rescan" in with_sd
    plain = F.render_report(coverage={"steps": 5, "gaps": 0, "post_missing": 0}, **base)
    assert "recorded steps: 5" in plain
    assert "observation is disabled" not in plain
