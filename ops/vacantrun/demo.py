#!/usr/bin/env python3
"""`vacant demo gate` 的第一幕。**實作已搬進 `vacant/vrun/demo.py`。**

這支在架構裡承重什麼：**維持 `ops.vacantrun.demo` 這個 import 路徑**。
2026-09-18 判斷層搬進套件（`vacant.vrun.demo`），理由是 `pip install
vacant-network` 的人也要跑得動 `vacant demo gate` 與 `vacant run`——`ops/` 不進
wheel，所以判斷層留在 `ops/` 底下就等於「下載的人拿不到閘門」。

⚠ **這是 re-export，不是第二份。** `sys.modules[__name__] = _impl` 讓
`ops.vacantrun.demo` 與 `vacant.vrun.demo` 在同一個行程裡是**同一個 module 物件**
（`importlib._bootstrap._load` 明文支援模組替換自己），所以
`isinstance`、模組級狀態、常數全都對得起來，而且**沒有第二把會漂的尺**
（`vacant/suitegauge.py` 的 docstring 與 `conform_failure_detail` 兩處都禁止這件事）。

搬的是**位置不是判準**：改到的只有 import 那幾行與「`__file__` 往上數幾層」
（搬家的必要結果，每一處都在新檔的 docstring 裡寫明），判準一個字沒動。
R530／R531／R534 的既有引用
（`from ops.vacantrun.demo import …`、`python3 ops/vacantrun/demo.py`）照樣可用。
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from vacant.vrun import demo as _impl                    # noqa: E402

if __name__ == "__main__":
    raise SystemExit(_impl.main())

sys.modules[__name__] = _impl
