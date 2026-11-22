"""全套測試的狀態隔離（2026-11-22）：每個測試都在自己的暫存目錄裡跑，不讀、也不寫使用者真的狀態目錄。

起因：rc5 的 auto_gc 也會清 `$VACANT_WORK`（預設 `~/.vacant-work`），而幾個 retention 測試沒有覆寫它——
跑測試會讀到使用者真的 `~/.vacant-work`，清理類測試理論上也動得到它。所以這裡一律（autouse）把下面這些指到
每個測試自己的 tmp_path 底下：

- `HOME`：產品碼有幾處直接用 `Path.home()`（`~/.vacant`、`~/.vacant-mcp`、`~/.vacant-run/<task>`、demo gate），
  只設環境變數蓋不到；子行程也會繼承這個 HOME。
- `VACANT_HOME`、`VACANT_WORK`：狀態目錄與 `vacant do` 工作區根目錄。
- 測試自己用 monkeypatch 設的值照樣優先（monkeypatch 在這之後執行）。

驗收（見 docs/RC5_CHANGES_VS_RC4.md 的 rc6 節）：真的家目錄裡有東西／沒東西時全套結果相同；跑全套前後
`~/.vacant`、`~/.vacant-work`、`~/.vacant-run`、`~/.vacant-mcp` 的清單逐項相同。
"""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile

import pytest

# 工具鏈與快取需要的真實位置（不是 Vacant 的狀態）：保留給子行程用，避免 npm／pip／node 因為新 HOME 找不到東西
_REAL_HOME = os.environ.get("VACANT_TEST_REAL_HOME") or os.path.expanduser("~")
#: 刻意讀本機真資料的測試（只讀，例如真鏈驗收）用這個找回真的家目錄
os.environ["VACANT_TEST_REAL_HOME"] = _REAL_HOME

# session 層級（第二次查證 P6）：conftest 匯入時就把環境換掉——在任何測試模組匯入、任何 module／session
# 範圍的 fixture 執行之前。否則匯入時算好的家目錄常數、module fixture 裡的呼叫（例如 test_twin_sidecar）
# 看到的還是真的家目錄。每個測試另外再疊自己的 tmp（下面的 autouse fixture）。
_SESSION_ROOT = tempfile.mkdtemp(prefix="vacant-tests-home-")
_SESSION_HOME = os.path.join(_SESSION_ROOT, "home")
os.makedirs(_SESSION_HOME)
os.environ["HOME"] = _SESSION_HOME
os.environ["VACANT_HOME"] = os.path.join(_SESSION_HOME, ".vacant")
os.environ["VACANT_WORK"] = os.path.join(_SESSION_HOME, ".vacant-work")
os.environ.setdefault("npm_config_cache", os.path.join(_REAL_HOME, ".npm"))
os.environ.setdefault("PIP_CACHE_DIR", os.path.join(_REAL_HOME, ".cache", "pip"))
atexit.register(shutil.rmtree, _SESSION_ROOT, True)


@pytest.fixture(autouse=True)
def _isolate_vacant_state(tmp_path_factory):
    # 用自己的 MonkeyPatch，不用測試共用的 `monkeypatch` fixture：有測試會呼叫 `monkeypatch.undo()`，
    # 共用的話會連這裡的隔離一起撤掉、HOME 變回真的家目錄（2026-11-22 隔離驗收時抓到）。
    root = tmp_path_factory.mktemp("isolated_home")
    home = root / "home"
    home.mkdir()
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HOME", str(home))
        mp.setenv("VACANT_HOME", str(home / ".vacant"))
        mp.setenv("VACANT_WORK", str(home / ".vacant-work"))
        # npm／pip 的快取與設定照用真的（離線測試需要），但它們不是 Vacant 的狀態
        mp.setenv("npm_config_cache", os.environ.get("npm_config_cache", os.path.join(_REAL_HOME, ".npm")))
        mp.setenv("PIP_CACHE_DIR", os.environ.get("PIP_CACHE_DIR", os.path.join(_REAL_HOME, ".cache", "pip")))
        yield
