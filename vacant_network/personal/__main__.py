"""`python -m vacant_network.personal`。

只有 build-profiles、predict、generate，以及標成相容性預檢的
compat-check，會在設定要求時呼叫模型。validate-data、freeze、
fixture-run、score-predictions、export-blind、report 不連網。
"""

from __future__ import annotations

from .cli import main

raise SystemExit(main())
