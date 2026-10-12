#!/usr/bin/env python3
"""原始紀錄打包（root，常駐迴圈）：每 INTERVAL 秒把「跑完、還沒打包」的格子＋代理全文紀錄切成一個 chunk。

    python3 packer.py [--interval 600] [--mirror /content/drive/MyDrive/vacant_colab_20260927] [--once]

一個 chunk＝`/srv/eval/archive/chunk_NNNN.tar.xz`（＋`.sha256`），內容：
- `cells/<格子>/`：整個格子目錄（pi.txt、pi 的 session、~/.vacant、C 組檢查、安裝紀錄、最後的工作區、計分結果、meta）
- `proxy/io_<時間>.jsonl.xz`：代理 `io.jsonl` 從上一個 chunk 到現在的那一段（請求與回應全文；輪替＝改名，代理每寫一筆
  都重新開檔，所以改名之後的下一筆會寫進新的 io.jsonl，不會掉）
- `proxy/ledger.jsonl`、`proxy/summary.json`、`progress.jsonl`：當下的快照（整份，不是增量；最後一個 chunk 的就是完整版）
`/srv/eval/archive/MANIFEST.tsv` 一行一個 chunk：名字、sha256、位元組、格子數、時間。本機同步（sync_from_colab.sh）照這份拉。
有 `--mirror`（例如掛上來的 Google Drive）就再複製一份過去，VM 掛掉時還有第二份。
**這支不讀分數**（score.json 原封不動打進 tar，不解析）。
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import subprocess
import tarfile
import time

EVAL = pathlib.Path("/srv/eval")
ARC = EVAL / "archive"
PROXY = EVAL / "proxy"


def sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def pack_once(mirror: pathlib.Path | None, final: bool = False) -> str | None:
    ARC.mkdir(parents=True, exist_ok=True)
    packed_f = ARC / "packed_cells.txt"
    packed = set(packed_f.read_text().split()) if packed_f.exists() else set()
    cells = sorted(p.name for p in (EVAL / "cells").glob("*") if (p / "DONE").exists() and p.name not in packed)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    rot = []
    io = PROXY / "io.jsonl"
    if io.exists() and io.stat().st_size > 0:
        dst = PROXY / f"io_{stamp}.jsonl"
        io.rename(dst)
        time.sleep(3)                                   # 讓改名那一刻正在寫的那一筆寫完（寫在鎖裡、一筆一開檔）
        subprocess.run(["xz", "-T8", "-6", str(dst)], check=True)
        rot.append(pathlib.Path(str(dst) + ".xz"))
    if not cells and not rot and not final:
        return None
    n = len(list(ARC.glob("chunk_*.tar.xz"))) + 1
    name = f"chunk_{n:04d}.tar.xz"
    tmp = ARC / (name + ".part")
    with tarfile.open(tmp, "w:xz", preset=6) as t:
        for c in cells:
            t.add(EVAL / "cells" / c, arcname=f"cells/{c}")
        for r in rot:
            t.add(r, arcname=f"proxy/{r.name}")
        for extra, arc in ((PROXY / "ledger.jsonl", "proxy/ledger.jsonl"), (PROXY / "summary.json", "proxy/summary.json"),
                           (PROXY / "refusals.jsonl", "proxy/refusals.jsonl"), (EVAL / "progress.jsonl", "progress.jsonl"),
                           (EVAL / "plan.json", "plan.json"), (EVAL / "env_manifest.json", "env_manifest.json")):
            if extra.exists():
                t.add(extra, arcname=arc)
    tmp.rename(ARC / name)
    digest = sha256(ARC / name)
    (ARC / (name + ".sha256")).write_text(f"{digest}  {name}\n")
    with (ARC / "MANIFEST.tsv").open("a") as f:
        f.write(f"{name}\t{digest}\t{(ARC / name).stat().st_size}\t{len(cells)}\t{stamp}\n")
    with packed_f.open("a") as f:
        f.write("".join(c + "\n" for c in cells))
    for r in rot:                                       # 已經進了 chunk（chunk 本身有 sha256）；原檔留在 io_done/ 備查
        (PROXY / "io_done").mkdir(exist_ok=True)
        r.rename(PROXY / "io_done" / r.name)
    if mirror is not None:
        try:
            mirror.mkdir(parents=True, exist_ok=True)
            for f in (name, name + ".sha256", "MANIFEST.tsv"):
                shutil.copy2(ARC / f, mirror / f)
        except OSError as e:
            print(f"mirror failed: {e}", flush=True)
    print(f"{stamp} packed {name} cells={len(cells)} io_pieces={len(rot)} sha256={digest[:12]}", flush=True)
    return name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=600)
    ap.add_argument("--mirror", type=pathlib.Path)
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    if a.once:
        pack_once(a.mirror, final=True)
        return 0
    while True:
        pack_once(a.mirror)
        if (EVAL / "DRIVER_DONE").exists():
            time.sleep(30)
            pack_once(a.mirror, final=True)
            (ARC / "PACKER_DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n")
            print("PACKER_DONE", flush=True)
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    raise SystemExit(main())
