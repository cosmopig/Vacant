#!/usr/bin/env python3
"""從一個或多個 twin2k-run 目錄寫 result.md。不呼叫模型。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vacant_network.personal.twin_report import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
