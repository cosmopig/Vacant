#!/usr/bin/env python3
"""V1／V2 重試迴圈的政策層。**實作已搬進 `vacant/vrun/retry.py`。**

這支在架構裡承重什麼：**維持 `ops.vacantrun.retry` 這個 import 路徑**。
2026-09-18 判斷層搬進套件（`vacant.vrun.retry`），理由是 `pip install
vacant-network` 的人也要跑得動 `vacant demo gate` 與 `vacant run`——`ops/` 不進
wheel，所以判斷層留在 `ops/` 底下就等於「下載的人拿不到閘門」。
`retry` 這一支跟著 `launcher` 走：`vacant/vrun/launcher.py` 直接 `from . import
retry`，留在 `ops/` 就會讓套件反過來依賴 `ops/`
（`tests/test_vrun_reexport.py::test_vrun_is_self_contained` 擋的正是這件事）。

⚠ **這是 re-export，不是第二份。** `sys.modules[__name__] = _impl` 讓
`ops.vacantrun.retry` 與 `vacant.vrun.retry` 在同一個行程裡是**同一個 module 物件**
（`importlib._bootstrap._load` 明文支援模組替換自己），所以
`isinstance`、模組級狀態、常數全都對得起來，而且**沒有第二把會漂的尺**
（`vacant/suitegauge.py` 的 docstring 與 `conform_failure_detail` 兩處都禁止這件事）。
`RETRY_ARMS`、`FEEDBACK_TEMPLATE`、`PROMPT_PLACEHOLDER` 這些封閉集合只有一份，
所以「多一條臂」這種規格變更不可能只改到其中一邊。

搬的是**位置不是判準**：改到的只有 import 那幾行（`sys.path` 開機碼換成
package-relative import），政策、回饋模板、重置語意、KS-1 擋門一個字沒動。
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from vacant.vrun import retry as _impl                        # noqa: E402

sys.modules[__name__] = _impl
