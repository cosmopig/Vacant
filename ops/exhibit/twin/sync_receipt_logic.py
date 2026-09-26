"""twin/sync_receipt_logic — 手機上「自己驗收據」那一頁用的驗證邏輯，**逐字**來自 twin_viewer。

## 這支在架構裡承重什麼

拍立得旁邊有一個小連結「自己驗收據」（`vacant-world-cloud/public/receipt.html`），
在觀眾的瀏覽器裡把那一跑的收據副本從創世重算到鏈頭。人類 2026-09-26 的要求是
「用既有 `examples/twin_viewer.html` 的同一套驗證邏輯」——所以這一頁**不自己寫**
hash／canonical／Ed25519，而是把 twin_viewer 的 `CANON` 與 `LOGIC` 兩段原樣抄過去。

兩個 repo 分開部署，抄過去的那一份會漂。這一支就是那把尺：

    python3 ops/exhibit/twin/sync_receipt_logic.py <cloud>/public/receipt.html          # 抄入
    python3 ops/exhibit/twin/sync_receipt_logic.py <cloud>/public/receipt.html --check  # 驗逐字相同

`--check` 對不上 ⇒ rc 1，並講是哪一段。**不准手改雲端那一頁的那兩段。**
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
VIEWER = REPO / "examples" / "twin_viewer.html"

BLOCKS = (("/* === CANON-BEGIN ===", "/* === CANON-END === */"),
          ("/* === LOGIC-BEGIN ===", "/* === LOGIC-END === */"))


def _block(html: str, begin: str, end: str) -> tuple[int, int]:
    i, j = html.find(begin), html.find(end)
    if i < 0 or j < 0 or j < i:
        raise SystemExit(f"找不到 {begin} … {end}")
    return i, j + len(end)


def blocks_of(html: str) -> list[str]:
    return [html[slice(*_block(html, b, e))] for b, e in BLOCKS]


def sync(page: pathlib.Path) -> str:
    src = VIEWER.read_text(encoding="utf-8")
    html = page.read_text(encoding="utf-8")
    for (b, e), text in zip(BLOCKS, blocks_of(src)):
        i, j = _block(html, b, e)
        html = html[:i] + text + html[j:]
    return html


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="把 twin_viewer 的驗證邏輯逐字抄進手機收據頁")
    ap.add_argument("page")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    page = pathlib.Path(a.page)
    want = blocks_of(VIEWER.read_text(encoding="utf-8"))
    if a.check:
        got = blocks_of(page.read_text(encoding="utf-8"))
        bad = [BLOCKS[k][0] for k in range(len(BLOCKS)) if got[k] != want[k]]
        for k in range(len(BLOCKS)):
            print(f"{BLOCKS[k][0][:22]}  viewer={hashlib.sha256(want[k].encode()).hexdigest()[:12]}"
                  f"  page={hashlib.sha256(got[k].encode()).hexdigest()[:12]}")
        if bad:
            print("✗ 對不上：" + "、".join(bad) + "（重跑不帶 --check 的這一支）")
            return 1
        print("✓ 兩段逐字相同")
        return 0
    page.write_text(sync(page), encoding="utf-8")
    print(f"✓ 抄入 {page}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
