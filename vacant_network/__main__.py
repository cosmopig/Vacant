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

from .cli import main

raise SystemExit(main())
