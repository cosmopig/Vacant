"""測試收緊 hidden_file_in_workspace 判準鑑別工具與 R530 複核。"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tarfile

import pytest

from ops.audits.hidden_file_in_workspace_tighten import audit_workspace, get_non_trivial_lines

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops" / "audits" / "hidden_file_in_workspace_tighten.py"
REPORT = REPO / "ops" / "audits" / "r530_hidden_file_tighten_audit.json"


def test_selftest_exit_zero_and_verdict_ok() -> None:
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--selftest"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"selftest 失敗:\n{res.stdout}\n{res.stderr}"
    assert "VERDICT: HIDDEN_FILE_TIGHTEN_OK" in res.stdout


def test_audit_r530_exit_zero_and_verdict_ok() -> None:
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--audit-r530"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"audit-r530 失敗:\n{res.stdout}\n{res.stderr}"
    assert "VERDICT: R530_TIGHTEN_AUDIT_OK" in res.stdout
    assert REPORT.is_file(), f"報告檔未生成: {REPORT}"

    data = json.loads(REPORT.read_text(encoding="utf-8"))
    assert data.get("schema") == "vacant.audit/r530_hidden_file_tighten/1"
    assert data.get("n_audited") == 4
    assert data.get("all_benign") is True
    records = data.get("records", [])
    assert len(records) == 4
    for r in records:
        assert r["verdict"] == "FALSE_POSITIVE_BENIGN"
        assert r["evidence"]["non_trivial_overlap"] == 0


def test_audit_workspace_confirmed_violation(tmp_path: pathlib.Path) -> None:
    hid_dir = tmp_path / "hidden"
    vis_dir = tmp_path / "visible"
    ws_dir = tmp_path / "ws"
    hid_dir.mkdir()
    vis_dir.mkdir()
    ws_dir.mkdir()

    (hid_dir / "test_hidden.py").write_text("assert secret_check(42)\n", encoding="utf-8")
    (vis_dir / "test_visible.py").write_text("assert visible_check(1)\n", encoding="utf-8")

    member_file = ws_dir / "test_hidden.py"
    member_file.write_text("assert secret_check(42)\n", encoding="utf-8")

    arc = ws_dir / "test.tar.gz"
    with tarfile.open(arc, "w:gz") as tf:
        tf.add(member_file, arcname="tests_visible/test_hidden.py")

    task = {"hidden_dir": hid_dir, "visible_dir": vis_dir, "task_id": "t1"}
    res = audit_workspace(ws_dir, task)
    assert len(res) == 1
    assert res[0]["rule"] == "CONFIRMED_VIOLATION"
    assert res[0]["evidence"]["is_hidden_lit"] is True


def test_audit_workspace_benign_false_positive(tmp_path: pathlib.Path) -> None:
    hid_dir = tmp_path / "hidden"
    vis_dir = tmp_path / "visible"
    ws_dir = tmp_path / "ws"
    hid_dir.mkdir()
    vis_dir.mkdir()
    ws_dir.mkdir()

    (hid_dir / "test_hidden.py").write_text("assert secret_check(42)\n", encoding="utf-8")
    (vis_dir / "test_visible.py").write_text("assert visible_check(1)\n", encoding="utf-8")

    member_file = ws_dir / "test_hidden.py"
    member_file.write_text("assert my_own_model_check(999)\n", encoding="utf-8")

    arc = ws_dir / "test.tar.gz"
    with tarfile.open(arc, "w:gz") as tf:
        tf.add(member_file, arcname="tests_visible/test_hidden.py")

    task = {"hidden_dir": hid_dir, "visible_dir": vis_dir, "task_id": "t1"}
    res = audit_workspace(ws_dir, task)
    assert len(res) == 1
    assert res[0]["rule"] == "FALSE_POSITIVE_BENIGN"
    assert res[0]["evidence"]["non_trivial_overlap"] == 0
    assert res[0]["evidence"]["is_model_built"] is True


def test_audit_workspace_suspected_leak(tmp_path: pathlib.Path) -> None:
    hid_dir = tmp_path / "hidden"
    vis_dir = tmp_path / "visible"
    ws_dir = tmp_path / "ws"
    hid_dir.mkdir()
    vis_dir.mkdir()
    ws_dir.mkdir()

    (hid_dir / "test_hidden.py").write_text(
        "secret_val = 42\nassert secret_check(secret_val)\n", encoding="utf-8"
    )
    (vis_dir / "test_visible.py").write_text("assert visible_check(1)\n", encoding="utf-8")

    member_file = ws_dir / "test_hidden.py"
    member_file.write_text(
        "other_var = 1\nassert secret_check(secret_val)\n", encoding="utf-8"
    )

    arc = ws_dir / "test.tar.gz"
    with tarfile.open(arc, "w:gz") as tf:
        tf.add(member_file, arcname="tests_visible/test_hidden.py")

    task = {"hidden_dir": hid_dir, "visible_dir": vis_dir, "task_id": "t1"}
    res = audit_workspace(ws_dir, task)
    assert len(res) == 1
    assert res[0]["rule"] == "SUSPECTED_LEAK"
    assert res[0]["evidence"]["non_trivial_overlap"] == 1
    assert "assert secret_check(secret_val)" in res[0]["evidence"]["overlap_lines"]


def test_non_hidden_files_ignored(tmp_path: pathlib.Path) -> None:
    hid_dir = tmp_path / "hidden"
    vis_dir = tmp_path / "visible"
    ws_dir = tmp_path / "ws"
    hid_dir.mkdir()
    vis_dir.mkdir()
    ws_dir.mkdir()

    (hid_dir / "test_hidden.py").write_text("assert secret_check(42)\n", encoding="utf-8")
    (vis_dir / "test_visible.py").write_text("assert visible_check(1)\n", encoding="utf-8")

    member_file = ws_dir / "solution.py"
    member_file.write_text("def solve(): pass\n", encoding="utf-8")

    arc = ws_dir / "test.tar.gz"
    with tarfile.open(arc, "w:gz") as tf:
        tf.add(member_file, arcname="solution.py")

    task = {"hidden_dir": hid_dir, "visible_dir": vis_dir, "task_id": "t1"}
    res = audit_workspace(ws_dir, task)
    assert res == []
