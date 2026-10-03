"""`python -m vacant_network` 的進入點——**撞名時最後一條打不歪的路**。

這支在架構裡承重什麼：0.8.0 把 import 名從 `vacant` 改成 `vacant_network`
（見 `pyproject.toml` `[project.scripts]` 的註解）。改名之後兩個套件不再共用
任何檔案路徑，**除了 `bin/vacant` 這支 console script**——同名腳本誰後裝誰贏，
這一條修不掉。所以使用者手上要有一條**不經過 `bin/` 的**入口：

    python3 -m vacant_network --help        # 直接走 import 名，沒有腳本可被覆蓋
    vacant-network --help                   # 第二指令名，import 的是 vacant_network.cli
    vacant --help                           # 主指令，**這一支可能被對方蓋掉**

誠實邊界（改碼時保留這句）：本檔擋的是「腳本被同名套件覆蓋」，不是
「套件被覆蓋」。有人把 `vacant_network/` 本身覆蓋掉的話這支一樣沒救——
只是 PyPI 上目前沒有第二個叫 `vacant-network` 的套件。
"""
from __future__ import annotations

import sys

# `vacant hook …` 在 agent 的**每一次工具呼叫**前都會執行：不經過 `cli`（它在頂層
# import 整套 eco），直接進掛鉤模組，省下啟動時間。
if sys.argv[1:2] == ["hook"]:
    from .adapters.hook import main as _hook_main
    raise SystemExit(_hook_main(sys.argv[2:]))

from .cli import main  # noqa: E402

raise SystemExit(main())
