#!/usr/bin/env python3
"""把 1920×1080 的 PNG 轉成進得了版控的 JPEG，並留下**兩邊的 sha256**。

## 為什麼

一張 1920 的 PNG 約 2 MB，15 張就 30 MB。那個大小進 git 是在拿倉庫換一次看圖。
⇒ committed 的是 1400 寬的 JPEG（每張約 200–400 KB）。

## 為什麼要記 PNG 的 sha256

轉檔**是有損的**，所以 JPEG 不等於當時按下快門那一張。把原始 PNG 的 sha256
記在 manifest 裡，原檔還在手上的時候驗得出「這張 JPEG 是那張 PNG 來的」；
原檔不在了，也至少知道自己手上的不是原件。**不要讓一個有損副本冒充原件。**

用法：python3 pack_shots.py [--shots shots] [--width 1400]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--shots", type=Path, default=HERE / "shots")
    ap.add_argument("--width", type=int, default=1400)
    a = ap.parse_args()

    rows = []
    fails = []
    for png in sorted(a.shots.glob("*.png")):
        jpg = png.with_suffix(".jpg")
        r = subprocess.run(
            ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "72",
             "-Z", str(a.width), str(png), "--out", str(jpg)],
            capture_output=True, text=True)
        if r.returncode != 0 or not jpg.is_file():
            # 轉不出來就記下來，**不要跳過**
            fails.append((png.name, r.stderr.strip()[:200]))
            continue
        meta = {}
        mj = png.with_suffix(".json")
        if mj.is_file():
            try:
                meta = json.loads(mj.read_text(encoding="utf-8"))
            except Exception as e:
                meta = {"_json_broken": str(e)}
        rows.append({
            "name": png.stem,
            "png": png.name, "png_bytes": png.stat().st_size, "png_sha256": sha256(png),
            "jpg": jpg.name, "jpg_bytes": jpg.stat().st_size, "jpg_sha256": sha256(jpg),
            "head": meta.get("head"), "sub": meta.get("sub"),
            "title_ov_source": meta.get("title_ov_source"),
            "scene_id": meta.get("scene_id"),
            "base_sha256": meta.get("base_sha256"),
            "layer_twinseam_loaded": meta.get("layer_twinseam_loaded"),
            "layer_seamending_loaded": meta.get("layer_seamending_loaded"),
            "snap_settled": meta.get("snap_settled"),
            "url": meta.get("url"),
            "shot_at": meta.get("shot_at"),
        })

    out = a.shots / "shots_manifest.json"
    out.write_text(json.dumps({
        "_": ["committed 的是 JPEG（1400 寬、品質 72）。PNG 是原件、**不進版控**。",
              "轉檔有損 ⇒ 兩邊的 sha256 都記在這裡，JPEG 不冒充原件。"],
        "width": a.width,
        "count": len(rows),
        "convert_failed": fails,
        "shots": rows,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    png_tot = sum(r["png_bytes"] for r in rows)
    jpg_tot = sum(r["jpg_bytes"] for r in rows)
    print(f"{len(rows)} 張：PNG {png_tot/1e6:.1f} MB → JPEG {jpg_tot/1e6:.1f} MB")
    print(f"manifest：{out}")
    if fails:
        print("🔴 轉不出來的：")
        for n, e in fails:
            print(f"   {n}  {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
