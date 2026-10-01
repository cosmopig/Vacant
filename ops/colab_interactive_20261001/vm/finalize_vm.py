#!/usr/bin/env python3
"""finalize_vm — 收尾（VM 常駐，root）：等 packer 寫 PACKER_DONE ⇒ 逐個核對 Drive 鏡像的 chunk（存在、sha256 對）⇒ 寫旗標。

    python3 finalize_vm.py --mirror /content/drive/MyDrive/vacant_i1001 [--eval-root /srv/eval] [--interval 20]

寫出（本機的 autostop／sync 會讀）：
  /srv/eval/archive/MIRROR_OK        鏡像裡每個 chunk 都在、sha256 與 MANIFEST.tsv 一致（內容＝每個 chunk 的核對結果）
  /srv/eval/archive/MIRROR_BAD       有缺或不符（內容＝逐項原因）；鏡像資料夾不存在（Drive 沒掛）也算
  /srv/eval/ALL_DONE                 {driver_done, packer_done, mirror_ok}（本機看到這個才知道 VM 這邊真的收完了）
為什麼要有：人類的兩個要求「資料備份到那個帳號的雲端」與「用完就關機」互相拉扯——本機同步沒追上（Mac 睡著）時，
autostop 要知道 Drive 那份是不是完整，才敢在本機沒驗完時照樣關機；而不是賭。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time


def sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def verify_mirror(manifest: pathlib.Path, mirror: pathlib.Path) -> dict:
    res: dict = {"mirror": str(mirror), "chunks": 0, "bad": []}
    if not mirror.is_dir():
        res["bad"].append("mirror directory does not exist (Drive not mounted?)")
        return res
    for line in manifest.read_text().splitlines():
        parts = line.split("\t")
        if len(parts) < 2 or not parts[0]:
            continue
        name, digest = parts[0], parts[1]
        res["chunks"] += 1
        p = mirror / name
        if not p.is_file():
            res["bad"].append(f"{name}: missing in mirror")
        elif sha256(p) != digest:
            res["bad"].append(f"{name}: sha256 differs in mirror")
    if not (mirror / "MANIFEST.tsv").is_file():
        res["bad"].append("MANIFEST.tsv: missing in mirror")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mirror", type=pathlib.Path, required=True)
    ap.add_argument("--eval-root", type=pathlib.Path, default=pathlib.Path("/srv/eval"))
    ap.add_argument("--interval", type=int, default=20)
    a = ap.parse_args()
    arc = a.eval_root / "archive"
    while not (arc / "PACKER_DONE").exists():
        time.sleep(a.interval)
    for f in ("MIRROR_OK", "MIRROR_BAD"):
        (arc / f).unlink(missing_ok=True)
    res = verify_mirror(arc / "MANIFEST.tsv", a.mirror)
    ok = not res["bad"] and res["chunks"] > 0
    if res["chunks"] == 0 and not res["bad"]:
        res["bad"].append("no chunks in MANIFEST.tsv")
        ok = False
    (arc / ("MIRROR_OK" if ok else "MIRROR_BAD")).write_text(json.dumps(res, indent=1) + "\n")
    (a.eval_root / "ALL_DONE").write_text(json.dumps({
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "driver_done": (a.eval_root / "DRIVER_DONE").exists(),
        "packer_done": True, "mirror_ok": ok, "chunks": res["chunks"]}) + "\n")
    print(json.dumps({"mirror_ok": ok, "chunks": res["chunks"], "bad": res["bad"][:5]}), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
