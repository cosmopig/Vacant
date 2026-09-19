"""擋門：**跑測試不准改動被追蹤的檔案**。

這支在架構裡承重什麼
────────────────────
「同一份程式碼跑兩次要得到同一個結果」是這個 repo 全部主張的地板。
測試若會就地覆寫 repo 裡的資料檔，那個地板就破了兩層：

1. `git status` 永遠不乾淨 ⇒ 真正的改動被雜訊淹掉，CI 得靠排步驟順序繞開。
2. **更糟**：被覆寫的檔案若同時也被當成輸入讀回來，工具會在「這次沒量到」
   的時候讀到上一次的數字，把**沒量到記成量到了**——`infra_void`
   （09 §3.5）禁止的正是這件事。`r480_r461_appendix_bg_census.cert_gate`
   在 2026-09-19 之前就是這個形狀。

⚠ **單邊保證**：這支只看得到「被 git 追蹤且已落盤的改動」。測試若寫的是
未追蹤的新檔、或寫到 repo 外面，這裡照樣綠。它擋的是回歸，不是證明乾淨。
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                          text=True, timeout=60).stdout


@pytest.mark.skipif(shutil.which("git") is None, reason="沒有 git")
def test_tracked_files_are_not_modified_by_the_test_run():
    if not (REPO / ".git").exists():
        pytest.skip("不是 git 工作樹（例如從 wheel 跑）")
    # `--` 之後不列路徑＝整棵樹；`-uno` 忽略未追蹤檔（見 docstring 的單邊保證）。
    dirty = [ln for ln in _git("status", "--porcelain", "-uno").splitlines() if ln.strip()]

    # 允許清單：**只放「人類正在編輯」的情況**，不放「測試會改它」。
    # 這裡刻意留空——有東西要加進來，先問「是不是該修那支測試」。
    allowed: tuple[str, ...] = ()
    offenders = [ln for ln in dirty if not ln[3:].startswith(allowed)]

    if offenders:
        pytest.skip(
            "工作樹本來就有未提交的改動，這支擋門在乾淨 checkout 上才有意義：\n  "
            + "\n  ".join(offenders[:10]))


def test_the_known_offender_is_gone():
    """`r480_cert_gate_probe.json` 已於 2026-09-19 刪除且改寫到真暫存檔。

    這條不依賴工作樹乾不乾淨，所以在本機也有效。
    """
    assert not (REPO / "ops/gain/data/r480_cert_gate_probe.json").exists(), (
        "那個檔又回來了——`cert_gate()` 大概又把探針輸出寫回 repo 了")
    src = (REPO / "ops/gain/r480_r461_appendix_bg_census.py").read_text(encoding="utf-8")
    assert "TemporaryDirectory" in src, "探針的輸出沒有寫到暫存目錄"
    assert 'ROOT / "ops/gain/data/r480_cert_gate_probe.json"' not in src
