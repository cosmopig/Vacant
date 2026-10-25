"""頂層 `vacant --help` 必須列出**全部**頂層命令（round 34 修）。

背景：`gc`/`usage`/`dashboard`/`flag`/`install`/`do`/`task`/`check`/`contract`…
全部走 `cli.py` `main()` 入口的 raw argv 分派（先於 parse_args），從來不在
`build_parser()` 的 subparser 表裡。結果 `vacant --help` 只列 18 個命令，
其餘只能讀源碼或 STATE 文件才知道存在（round 27 摩擦 5、round 32 dogfood
再確認：「只讀 help 的人永遠不會知道它們存在」）。

`--help` 是人類與 agent 的第一屏；沒列出來＝等於不存在。修法：把每個
頂層命令補進 subparser 表（帶一行說明；`func` 轉發到原分派目標，
所以即便 argparse 真的收到它們——例如 `--root` 排在前面的順序——
也是轉發而不是 AttributeError）。

禁語守門由 test_cleanroom_blockers.py 的 --help 全表掃描負責（它會
自動走到本輪新增的子解析器）。
"""
import re

# 頂層可打的命令全集（以 main() 的 raw 分派為唯一事實來源）。
EXPECTED_TOP_LEVELS = (
    # 原本就在表裡的（防回歸：這些一直在）
    "run", "trace", "bench", "demo", "init",
    # 收件口（任務合約流）
    "contract", "check", "submit", "review", "reverify", "approve",
    "release", "withdraw", "task", "keys", "intake",
    # 適配器（agent 整合）
    "do", "hook", "install", "uninstall", "adapters",
    # 人指出錯處
    "flag",
    # 磁碟
    "gc", "usage",
    # 狀態 / 常駐 / 選單
    "dashboard", "possess", "on",
)


def _help_text() -> str:
    from vacant_network.cli import build_parser

    return build_parser().format_help()


def _choices() -> dict:
    from vacant_network.cli import build_parser

    for a in build_parser()._actions:
        ch = getattr(a, "choices", None)
        if isinstance(ch, dict) and len(ch) >= 10:
            return ch
    raise AssertionError("找不到 subparser choices 表")


def test_every_top_level_command_is_listed_in_help():
    h = _help_text()
    missing = [n for n in EXPECTED_TOP_LEVELS
               if not re.search(rf"^\s{{4}}{re.escape(n)}[ \t]", h, re.M)]
    assert missing == [], (
        "頂層 --help 缺這些命令（只讀 help 的人永遠不會知道它們存在）： "
        + ", ".join(missing))


def test_each_listed_command_carries_a_description():
    """列出來卻沒有說明文字，等同沒列（名字孤零零一列不構成發現性）。"""
    h = _help_text()
    bad = []
    for n in EXPECTED_TOP_LEVELS:
        m = re.search(rf"^\s{{4}}{re.escape(n)}[ \t]+(.*)$", h, re.M)
        if m is None or not m.group(1).strip():
            bad.append(n)
    assert bad == [], f"列了但沒有描述：{bad}"


def test_added_commands_are_real_subparsers_with_forwarding():
    """每個名字都必須是真 subparser（不是純文字）；新增的還要有 func 可轉發
    （萬一 argparse 真收到它們——例如 `--root` 排在命令前面——是轉發，
    不是 AttributeError）。"""
    import argparse

    choices = _choices()
    for n in EXPECTED_TOP_LEVELS:
        sp = choices.get(n)
        assert sp is not None, f"{n} 不在 subparser 表"
        assert isinstance(sp, argparse.ArgumentParser), f"{n} 不是 parser"
    new_ones = ("run", "contract", "check", "submit", "review", "reverify",
                "approve", "release", "withdraw", "task", "keys", "intake",
                "do", "hook", "install", "uninstall", "adapters",
                "flag", "gc", "usage", "dashboard", "possess", "on")
    for n in new_ones:
        f = choices[n]._defaults.get("func")
        assert callable(f), f"{n} 沒有 func（argparse 收到會 AttributeError）"


def test_help_does_not_list_internal_aliases_twice():
    """`clean` 是 `gc` 的別名：help 裡 gc 出現一次即可，描述裡提及別名。"""
    h = _help_text()
    assert len(re.findall(r"^\s{4}gc[ \t]", h, re.M)) == 1
