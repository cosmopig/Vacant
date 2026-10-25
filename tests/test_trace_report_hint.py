"""`vacant trace report` 沒有 report 時提示「or run with --check」要帶前提。

round 17 dogfood：本專案沒有任務契約，照提示跑 `--check` 直接
`vacant trace report --check needs a task contract`（rc=1）——提示帶了不成立的前提。
提示應附上「--check 需要本工作區的任務契約」。
"""
import argparse
import os

from vacant_network.trace.cli import cmd_report


def test_no_report_hint_states_check_prerequisite(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = cmd_report(argparse.Namespace(contract=None, check=False))
    text = capsys.readouterr().out
    assert rc == 0
    assert "no report yet" in text
    assert "--check" in text
    # 提示若帶 --check，就得同時說清楚它需要任務契約（否則照做會撞 rc=1）
    assert "contract" in text.lower(), f"提示未帶 --check 的前提（contract）: {text!r}"


def test_check_without_contract_still_explains(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    try:
        cmd_report(argparse.Namespace(contract=None, check=True))
    except SystemExit as e:
        assert "needs a task contract" in str(e)
    else:
        raise AssertionError("expected SystemExit")
