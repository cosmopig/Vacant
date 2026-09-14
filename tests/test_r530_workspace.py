"""R530：樹雜湊、工作區生命週期、沙箱。

這一批測的是**承重件**不是便利函式：
E-1（所有工作區起點雜湊相同）與 §五-3 第 1 條（隱藏驗收永遠不進工作區）
兩條擋門，在程式碼裡就是這幾個斷言。
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain.r530 import openwork_arms as oa  # noqa: E402
from ops.gain.r530 import sandbox as sb  # noqa: E402
from ops.gain.r530 import tasks as taskmod  # noqa: E402
from ops.gain.r530 import wshash  # noqa: E402


# ── 樹雜湊 ────────────────────────────────────────────────────────────────
def _mk(base: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    base.mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return base


def test_tree_hash_is_deterministic(tmp_path):
    d = _mk(tmp_path / "a", {"x.py": "print(1)\n", "sub/y.txt": "hello"})
    assert wshash.tree_hash(d) == wshash.tree_hash(d)


def test_tree_hash_ignores_mtime(tmp_path):
    """`cp -a` 保留 mtime，而每一格的建立時間不同——mtime 不准進雜湊。"""
    a = _mk(tmp_path / "a", {"x.py": "print(1)\n"})
    b = tmp_path / "b"
    subprocess.run(["cp", "-a", f"{a}/.", str(b)], check=True)
    import os
    import time
    os.utime(b / "x.py", (time.time() - 99999, time.time() - 99999))
    assert wshash.tree_hash(a) == wshash.tree_hash(b)


def test_tree_hash_changes_on_content_and_exec_bit(tmp_path):
    a = _mk(tmp_path / "a", {"x.py": "print(1)\n"})
    h0 = wshash.tree_hash(a)
    (a / "x.py").write_text("print(2)\n", encoding="utf-8")
    assert wshash.tree_hash(a) != h0
    (a / "x.py").write_text("print(1)\n", encoding="utf-8")
    assert wshash.tree_hash(a) == h0
    (a / "x.py").chmod(0o755)
    assert wshash.tree_hash(a) != h0, "chmod +x 改變行為卻不改變內容，必須看得見"


def test_tree_hash_excludes_git(tmp_path):
    """`git init` 的 object 帶時間戳；算進去會讓 108 格得到 108 個起始雜湊。"""
    a = _mk(tmp_path / "a", {"x.py": "print(1)\n"})
    before = wshash.tree_hash(a)
    subprocess.run(["git", "init", "-q", str(a)], check=True)
    assert wshash.tree_hash(a) == before


def test_tree_hash_sees_added_and_removed_files(tmp_path):
    a = _mk(tmp_path / "a", {"x.py": "1\n"})
    h0 = wshash.tree_hash(a)
    (a / "new.txt").write_text("n", encoding="utf-8")
    assert wshash.tree_hash(a) != h0
    (a / "new.txt").unlink()
    assert wshash.tree_hash(a) == h0


def test_diff_leaves_names_what_changed(tmp_path):
    a = _mk(tmp_path / "a", {"x.py": "1\n", "y.py": "2\n"})
    before = wshash.tree_leaves(a)
    (a / "x.py").write_text("9\n", encoding="utf-8")
    (a / "y.py").unlink()
    (a / "z.py").write_text("3\n", encoding="utf-8")
    d = wshash.diff_leaves(before, wshash.tree_leaves(a))
    assert d == {"added": ["z.py"], "removed": ["y.py"], "changed": ["x.py"]}


# ── 工作區生命週期 ────────────────────────────────────────────────────────
def test_prepare_workspace_reproduces_the_template_hash(tmp_path):
    """E-1 的可執行版本：`cp -a` 出來的每一格起點必須是**同一個**雜湊。"""
    tpl = taskmod.load_task("ow_01_csvjson")["template_dir"]
    tpl_hash = wshash.tree_hash(tpl)
    hashes = set()
    for i in range(3):
        man = oa.prepare_workspace(tpl, tmp_path / f"cell{i}")
        hashes.add(man["ws_sha256"])
    assert hashes == {tpl_hash}, (
        "108 格的起始樹雜湊必須全部相同，而且等於樣板本身（E-1）")


def test_prepare_workspace_resets_back_to_the_template(tmp_path):
    """`A-CONF` 的「重置回樣板」必須是冪等的，否則第 5 份與第 1 份不同起點。"""
    tpl = taskmod.load_task("ow_02_ratelimit")["template_dir"]
    cell = tmp_path / "cell"
    h0 = oa.prepare_workspace(tpl, cell)["ws_sha256"]
    (cell / "solution.py").write_text("garbage\n", encoding="utf-8")
    (cell / "goal.md").write_text("tampered\n", encoding="utf-8")
    assert wshash.tree_hash(cell) != h0
    h1 = oa.prepare_workspace(tpl, cell)["ws_sha256"]
    assert h1 == h0


def test_prepare_workspace_makes_an_empty_git_start(tmp_path):
    tpl = taskmod.load_task("ow_01_csvjson")["template_dir"]
    cell = tmp_path / "cell"
    oa.prepare_workspace(tpl, cell)
    assert (cell / ".git").is_dir()
    r = subprocess.run(["git", "-C", str(cell), "status", "--porcelain"],
                       capture_output=True, text=True)
    assert r.stdout.strip() == "", "樣板複製完應該是一個乾淨的 commit"


def test_archive_workspace_keeps_git(tmp_path):
    """封存留 `.git`（樹雜湊排除它）——兩個用途不同，不是矛盾。"""
    import tarfile
    tpl = taskmod.load_task("ow_01_csvjson")["template_dir"]
    cell = tmp_path / "cell"
    oa.prepare_workspace(tpl, cell)
    arc = tmp_path / "cell.tar.gz"
    sha = oa.archive_workspace(cell, arc)
    assert len(sha) == 64
    with tarfile.open(arc) as tf:
        names = tf.getnames()
    assert any("/.git/" in n for n in names)


def test_no_hidden_file_ever_lands_in_a_template():
    """結構性紅線：樣板裡不准有任何看起來像隱藏驗收的東西。"""
    for tid in taskmod.task_ids():
        t = taskmod.load_task(tid)
        for leaf in wshash.tree_leaves(t["template_dir"]):
            low = leaf["path"].lower()
            assert "hidden" not in low and "rubric" not in low, \
                f"{tid} 的樣板裡有 {leaf['path']}"


# ── 沙箱 ──────────────────────────────────────────────────────────────────
def test_none_backend_is_honest_about_having_no_isolation(tmp_path):
    """`none` 不是「沙箱的弱版本」，它不是沙箱——名字與 meta 都要這樣寫。"""
    s, meta = sb.make_sandbox("none", workdir=str(tmp_path / "probe"))
    assert meta["backend"] == "none"
    assert meta["network_isolated"] is False or meta["network_isolated"] is None
    assert "不是沙箱" in meta["honest_bound"]
    assert meta["write_confined"] is False


def test_sandbox_runs_a_command_and_captures_output(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    s = sb.NoneSandbox()
    r = s.run("echo hello; echo bad >&2; exit 3", workspace=ws, timeout_s=20)
    assert r.rc == 3 and "hello" in r.stdout and "bad" in r.stderr
    assert r.timed_out is False


def test_sandbox_timeout_is_not_an_exit_code(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    s = sb.NoneSandbox()
    r = s.run("sleep 30", workspace=ws, timeout_s=1)
    assert r.timed_out is True and r.rc is None, \
        "逾時是一個獨立的 outcome，不是「跑出某個 rc」"


@pytest.mark.skipif(not shutil.which("bwrap"), reason="這台機器沒有 bwrap")
def test_bwrap_backend_blocks_the_network_when_it_is_available(tmp_path):
    """bwrap 起得來的機器上，**網路必須真的不通**。

    起不來（Ubuntu 24.04 的 AppArmor 擋非特權 userns）就 skip——
    那件事由 `backend_meta.tried` 記錄，不由這條測試判。
    """
    s = sb.BwrapSandbox()
    ok, _why = s.available()
    if not ok:
        pytest.skip("bwrap 在這台機器上起不來（AppArmor／userns）")
    meta = s.probe(tmp_path / "probe")
    assert meta["network_isolated"] is True
    assert meta["write_confined"] is True
    assert meta["repo_hidden_from_sandbox"] is True, \
        "最小 rootfs 之下 repo（裡面有 hidden/）在沙箱裡不該存在"
