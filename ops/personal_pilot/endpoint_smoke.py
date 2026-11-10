#!/usr/bin/env python3
"""§14 步驟 2 的那一個相容性預檢。

不帶 --dry-run 會對設定裡的 base URL 送出正好一個請求。
不要在沒有指定端點時執行。import 這個檔案不會連線。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vacant_network.personal.endpoint_smoke import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
