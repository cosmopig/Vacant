"""hookpolicy 對 vacant 權威指令的重驗矩陣（round 19，2026-10-24）。

BACKLOG 舊項（round 7 實跑）寫：「commit 訊息只是**提到** `vacant flag` 就被 deny
整條命令、`--help` 也被擋」。2026-10 之後 hookpolicy 改為 shlex 分節＋argv 位置分析
（純 `-h/--help` 放行）。本測試把 2026-10-24 對現行代碼逐形狀實跑的矩陣固化：

  只「提到」（字串值／引號內／grep 目標）⇒ allow，共 7 形（A1–A7）
  「位置上是指令」（含 launcher：timeout/uv run/find -exec/bash -c/sh -lc/env 前綴/
  xargs/&& 鏈/python -m）⇒ deny，共 14 形（D1–D14）

探針輸出（全數如上）見 ~/dev/ops/probe_flag_matrix.py。
邊界：這是字串層分析——擋的是**直接的**寫法；繞路（變數拼字、base64）不在保證內
（hookpolicy.py 誠實邊界 1，照錄）。
"""
import dataclasses

import pytest

from vacant_network.adapters import hookpolicy as HP

SHAPES = [
    # ── 只提到、不是指令位置 ⇒ allow ──────────────────────────────
    ("A1", 'git commit -m "per vacant flag note"', "allow"),
    ("A2", 'echo "vacant flag file:1"', "allow"),
    ("A3", 'grep -rn "vacant flag" docs/', "allow"),
    ("A4", 'vacant flag --help', "allow"),
    ("A5", 'vacant --help', "allow"),
    ("A6", 'vacant check', "allow"),
    ("A7", 'vacant check --help', "allow"),
    # ── 位置上真是該指令（含各種 launcher）⇒ deny ────────────────
    ("D1", 'vacant flag src/app.py:12 "wrong"', "deny"),
    ("D2", 'vacant approve', "deny"),
    ("D3", 'vacant release v1', "deny"),
    ("D4", 'vacant withdraw', "deny"),
    ("D5", 'timeout 5 vacant approve', "deny"),
    ("D6", 'uv run vacant approve', "deny"),
    ("D7", 'find . -name x -exec vacant approve {} \\;', "deny"),
    ("D8", "bash -c 'vacant approve'", "deny"),
    ("D9", 'python -m vacant_network.cli flag a:1', "deny"),
    ("D10", 'sh -lc "vacant release v1"', "deny"),
    ("D11", 'VACANT_X=1 vacant approve', "deny"),
    ("D12", 'ls | xargs -I{} vacant approve {}', "deny"),
    ("D13", 'vacant flag ./app.py:3 "bad"', "deny"),
    ("D14", 'true && vacant approve', "deny"),
]


@pytest.mark.parametrize("tag,cmd,want", SHAPES, ids=[s[0] for s in SHAPES])
def test_flag_authority_matrix(tmp_path, tag, cmd, want):
    ev = HP.HookEvent(agent="claude", kind="pre_tool", tool="bash",
                      command=cmd, cwd=str(tmp_path))
    got = HP.decide_pre_tool(ev, None).action
    assert got == want, f"{tag}: {cmd!r} → {got!r}（want {want!r}）"
