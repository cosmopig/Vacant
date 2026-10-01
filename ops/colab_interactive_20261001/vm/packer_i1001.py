#!/usr/bin/env python3
"""packer_i1001 — 第一批 `packer.py` 的外殼（**函式原樣重用，不改 packer.py**），只改一件事：driver 一寫 `DRIVER_DONE` 就收尾。

    python3 packer_i1001.py [--interval 600] [--mirror /content/drive/MyDrive/vacant_i1001]

為什麼：`packer.py` 自己的迴圈是「打包 → 沒有 DRIVER_DONE 就睡 interval 秒」，driver 在睡眠剛開始時收完的話，要多等最多 10 分鐘才
會做最後一包、寫 PACKER_DONE；G4 每小時 8.9 CU，這 10 分鐘是白燒的（人類的鐵則：用完就關）。這裡把睡眠改成每 `poll_s` 秒看一次
DRIVER_DONE；其餘（打包內容、chunk 命名、MANIFEST.tsv、Drive 鏡像、收尾前等 30 秒再打最後一包、PACKER_DONE）全部呼叫 packer.py 的原函式。
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import packer  # noqa: E402  第一批的 packer.py（逐字複本，見 MANIFEST_REUSED.json）


def run(interval: int = 600, mirror: pathlib.Path | None = None, poll_s: float = 5.0, final_sleep: float = 30.0) -> None:
    while True:
        packer.pack_once(mirror)
        if (packer.EVAL / "DRIVER_DONE").exists():
            time.sleep(final_sleep)                      # 讓最後一批格子的 DONE 與代理的最後一筆落盤（同 packer.py 的 30 秒）
            packer.pack_once(mirror, final=True)
            (packer.ARC / "PACKER_DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n")
            print("PACKER_DONE", flush=True)
            return
        t0 = time.time()
        while time.time() - t0 < interval:
            if (packer.EVAL / "DRIVER_DONE").exists():
                break
            time.sleep(poll_s)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--interval", type=int, default=600)
    ap.add_argument("--mirror", type=pathlib.Path)
    a = ap.parse_args()
    run(a.interval, a.mirror)
    return 0


if __name__ == "__main__":
    sys.exit(main())
