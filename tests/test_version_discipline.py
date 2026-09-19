"""版本紀律：同一個版本字串不准指兩份碼。

這支在架構裡承重什麼：0.8.0 之前 repo 裡有三個「版本」互不相干——git tag 停在
`v0.6.0`、PyPI 是 `0.7.0`、`vacant/__init__.py` 也寫 `0.7.0` 但 HEAD 已經往前跑了。
結果就是 `0.7.0` 這個字串同時指兩份**不同的位元組**（`docs/INSTALL_LOG_20260919.md`
§11 逐字記了這件事：PyPI 的 0.7.0 少了 `upstreams_defaulted` 兩個欄位，repo HEAD 有）。

一個把「判定可被重算」當主張的系統不能容許「版本」是模糊的：拿 `0.7.0` 去重放，
重放不出同一份碼。所以把 repo 內三個版本來源綁成**同一個**，並且 fail-closed：

  1. `vacant_network.__version__`      —— 單一真相
  2. `pyproject.toml` 解析出來的版本   —— 必須 `attr = "vacant_network.__version__"`
  3. `CHANGELOG.md` 最新一個 `## x.y.z` 標題

誠實邊界（改碼時保留這句）：**本檔擋不到 PyPI 與 git tag。** 那兩個在 repo 外面，
由 `.github/workflows/publish.yml` 的 tag 檢查擋（release 觸發時 tag 必須等於
`v$__version__`，否則拒絕 build）。本檔只保證「repo 內部不自相矛盾」——
repo 內一致 ≠ 已發布的那份與這裡一致。
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import vacant_network  # noqa: E402

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_HEADING = re.compile(r"^##\s+(\d+\.\d+\.\d+)\b", re.M)


def test_version_is_semver() -> None:
    assert _SEMVER.match(vacant_network.__version__), (
        f"__version__ = {vacant_network.__version__!r} 不是 x.y.z")


def test_pyproject_points_at_the_single_source() -> None:
    """`pyproject.toml` 不准自己寫死一份版本號——寫死就會漂。"""
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "version" not in cfg["project"], (
        "`[project] version` 寫死了 ⇒ 會跟 `__version__` 漂開。"
        "要用 `dynamic = [\"version\"]` ＋ `[tool.setuptools.dynamic]`。")
    assert "version" in cfg["project"].get("dynamic", [])
    attr = cfg["tool"]["setuptools"]["dynamic"]["version"]["attr"]
    assert attr == "vacant_network.__version__", (
        f"pyproject 的版本來源是 {attr!r}，不是 `vacant_network.__version__`")


def test_changelog_newest_entry_matches_version() -> None:
    """CHANGELOG 最上面那一條就是現在這份碼。忘了寫＝這道門紅。"""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heads = _HEADING.findall(text)
    assert heads, "CHANGELOG.md 裡找不到任何 `## x.y.z` 標題"
    assert heads[0] == vacant_network.__version__, (
        f"CHANGELOG 最新條目是 {heads[0]}，但 __version__ 是 "
        f"{vacant_network.__version__} ⇒ 同一份碼有兩個版本號")


def test_publish_workflow_pins_tag_to_version() -> None:
    """發布路徑上要有「tag ＝ __version__」的擋門，否則 tag 與 PyPI 會再漂開。

    只檢查那段擋門還在（字串比對），不跑 workflow——這是死碼偵測不是 CI 模擬。
    """
    wf = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert "github.event.release.tag_name" in wf and "v$version" in wf, (
        "publish.yml 少了 tag ↔ __version__ 的比對 ⇒ "
        "可以發一個 tag 與版本號不符的 release（0.7.0 就是這樣漂開的）")
