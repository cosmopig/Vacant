"""`vacant trace <打錯的詞>`（非病歷子指令）應提示真正的病歷子指令。

round 17 dogfood：`vacant trace overview` →「找不到 trace 檔：overview」rc=1、
沒有任何提示。分派上（cli.main）`vacant trace <show|verify|report|blame|actors>`
走病歷（vacant_network/trace/cli.py），其餘任何詞都被當成 tee-proxy 的 wire.jsonl
檔名走 cmd_trace。使用者打錯子指令時，錯誤訊息應指回子指令清單——但只对
「不像路徑」的名字（不含 `/`）加提示；像路徑的名字維持原來的單純錯誤，
避免把真的「檔不存在」澆上不相干的建議。
"""
import argparse

import pytest

from vacant_network.cli import cmd_trace


def _run(file_name: str, capsys) -> tuple[int, str]:
    rc = cmd_trace(argparse.Namespace(file=file_name))
    out = capsys.readouterr()
    return rc, out.err + out.out


def test_unknown_word_gets_subcommand_hint(capsys):
    rc, text = _run("overview", capsys)
    assert rc == 1
    assert "找不到 trace 檔" in text
    # 提示必須列出病歷子指令（show/verify/report/actors/blame 全在）
    for sub in ("show", "verify", "report", "actors", "blame"):
        assert sub in text, f"提示缺子指令 {sub!r}"


def test_flag_is_pointed_to_the_top_level_command(capsys):
    """round 117 dogfood：`flag` 是頂層指令（`vacant trace --help` 的「人指出錯處：vacant flag」
    很容易被讀成 `vacant trace flag`）。它不存在時，提示必須指回真正的形態，
    而不是把它當成打錯的病歷子指令。"""
    rc, text = _run("flag", capsys)
    assert rc == 1
    assert "vacant flag <file>:<line>" in text


def test_path_like_name_keeps_plain_error(capsys):
    rc, text = _run("/no/such/dir/wire.jsonl", capsys)
    assert rc == 1
    assert "找不到 trace 檔" in text
    # 像路徑的名字：不該被澆上子指令建議（那是另一種用法，不是打錯）
    assert "blame" not in text
