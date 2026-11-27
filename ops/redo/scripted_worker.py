#!/usr/bin/env python3
"""scripted_worker — 零成本的腳本化 worker（DECISION 修正 4 步驟 5）：在真題庫的真測試上讓控制器規則被觸發。
依 REDO_ATTEMPT 寫不同版本：1、2＝永遠回 "Whatever."（過一部分、同一失敗簽章），其後＝參考解。"""
import os, pathlib, sys
att = int(os.environ.get("REDO_ATTEMPT", "1"))
ref = pathlib.Path(sys.argv[1]).read_text()
pathlib.Path("bob.py").write_text(ref if att >= 3 else 'def response(hey_bob):\n    return "Whatever."\n')
