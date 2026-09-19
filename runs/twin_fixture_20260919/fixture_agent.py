"""twin fixture agent —— 零模型、零網路的**腳本化** agent。

它把 `TWIN_FIXTURE_SOURCE` 指到的那一份檔案寫成 `solution.py`，就結束。
那份檔案由 `run_twin.py` 事前從 bank 的 `reference/` 挑好：介面寫明的格挑
`solution.py`（會過），介面被扣住的格挑 `bad_c.py`（名字猜錯，會被擋）。

它存在的理由是**讓收據鏈與閘門在沒有機時的時候也被真的跑一次**。
它不是 agent 的模擬，也不代表任何模型的能力：`requests_seen` 會是 0，
所以 `pack.py` 只會把這種格標成 L-none，頁面上也只會這樣寫。
"""
import os
import pathlib

src = pathlib.Path(os.environ["TWIN_FIXTURE_SOURCE"])
pathlib.Path("solution.py").write_text(src.read_text(encoding="utf-8"),
                                       encoding="utf-8")
