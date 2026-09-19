"""`vacant run --help` 要看得到**收件口**那條路。

這支在架構裡承重什麼
────────────────────
`vacant run` 有兩種模式，分水嶺是 argv 裡有沒有 `--`（`cli.main()`）：

- **有 `--`** ⇒ 收件口（`vacant/vrun/launcher.py`）——包住任意 CLI agent、
  中介模型通道、行程結束跑驗收、簽收據、沒過擋下交付（exit 20）。
  **那是 0.7.0 的主要功能。**
- **沒有 `--`** ⇒ 舊的 eco 版。

⚠ **argparse 在看到 `--help` 時就停了**，所以 `vacant run --help` 只印得出
其中一個——而它印的是**舊的那個**。2026-09-19 從 PyPI 裝 0.7.0 之後實測：

```
$ vacant run --help
usage: vacant run [-h] [--task-file TASK_FILE] [--root ECO_ROOT] …
                  [--agent {none,hermes}] [--hermes-bin HERMES_BIN]
```

功能**在**（同一份安裝跑 `vacant run --workspace … --suite … -- bash -lc true`
拿到 `visible_pass`／exit 0，改錯答案拿到 `visible_fail`／**exit 20**），
但**外人照著 `--help` 讀永遠找不到它**。

⇒ 修法是把另一條路寫進 `description`。這支釘住那段不會被拿掉。
"""
from __future__ import annotations

import subprocess
import sys

import pytest


def _help() -> str:
    r = subprocess.run([sys.executable, "-m", "vacant.cli", "run", "--help"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_help_mentions_the_dash_dash_mode():
    out = _help()
    assert "`--`" in out or " -- " in out, "沒講 `--` 是分水嶺"
    assert "--workspace" in out and "--suite" in out, (
        "沒列出收件口的旗標——外人不知道要打什麼")


def test_help_shows_a_runnable_example():
    """要有**可以照抄的一行**，不是只說「有另一種模式」。"""
    out = _help()
    assert "vacant run --workspace" in out, f"沒有可照抄的例子：\n{out[:600]}"
    assert " -- " in out


def test_help_points_at_the_full_flag_list():
    """argparse 印不出那一組 ⇒ 必須告訴讀者去哪裡看完整的。"""
    out = _help()
    assert "vacant.vrun.launcher" in out, (
        "沒指向 `python -m vacant.vrun.launcher --help`——"
        "讀者看到這裡會以為那幾個旗標就是全部")


def test_the_two_modes_really_are_split_by_dash_dash():
    """判準不是文件寫了什麼，是 `main()` 真的這樣分。"""
    from vacant import cli
    src = cli.__loader__.get_source("vacant.cli") or ""
    assert 'raw[:1] == ["run"] and "--" in raw[1:]' in src, (
        "分水嶺的實作變了——上面那些 help 文字會變成假的")


@pytest.mark.parametrize("flag", ["--retry", "--feedback-into", "--sandbox"])
def test_help_names_the_v1_v2_flags(flag):
    """V1／V2 是 0.7.0 的新東西，help 不提的話等於沒發。"""
    assert flag in _help(), f"{flag} 沒出現在 `vacant run --help` 裡"
