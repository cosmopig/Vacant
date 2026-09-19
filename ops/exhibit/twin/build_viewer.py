"""twin/build_viewer — 把資料與素材組進 `examples/twin_viewer.html`（展件：一天的收據）。

## 這支在架構裡承重什麼

形狀逐條照 `ops/gain/replay/build_multiparty_viewer.py`（三把金鑰的收據），
理由也一樣：展件那一頁必須離線、`file://` 直開、零外部資源，所以資料只能內嵌；
而內嵌之後就需要一支「這一頁裡的那一份，與磁碟上的來源逐位元組相同」的檢查器。

內嵌三塊：

  twin-pack     `ops/exhibit/twin/twin_pack.json`（`pack.py` 的輸出，逐位元組相同）
  twin-assets   `ops/exhibit/twin/assets/*.png` → base64 data URI（**推導**，標示得出來）
  CANON 區段    從 `examples/receipt_viewer.html` **原封複製**

CANON 為什麼要複製而不是重寫：兩頁的正規化與 hash 佈局必須是同一份位元組，
否則 `ops/gain/replay/receipt_viewer_node_check.mjs` 的 N1–N5b 只覆蓋得到其中一頁。
一把會 PASS 的瞎尺比沒有尺更糟。

## 誠實邊界

1. 本支**只做搬運與可重現的推導**。頁面上每一個數字都由頁內 JS 從內嵌資料算出來，
   不是這裡算好貼進去的。
2. `--check` 比的是「頁面裡的那一份」與「磁碟上的來源」。它證明不了資料本身對，
   只證明頁面沒有偷偷跟來源分岔。

用法：
    python3 ops/exhibit/twin/build_viewer.py
    python3 ops/exhibit/twin/build_viewer.py --check   # 只檢查、不寫
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

TWIN = HERE.parent
PACK = TWIN / "twin_pack.json"
ASSETS = TWIN / "assets"
VIEWER = REPO / "examples" / "twin_viewer.html"
SOURCE_VIEWER = REPO / "examples" / "receipt_viewer.html"

CANON_BEGIN = "/* === CANON-BEGIN ==="
CANON_END = "/* === CANON-END === */"
CANON_COPY_BEGIN = "/* CANON-COPY-BEGIN"
CANON_COPY_END = "/* CANON-COPY-END */"

#: 內嵌區塊 id → 來源檔（None ＝ 推導出來的，不是原檔）。
BLOCKS: dict[str, str | None] = {
    "twin-pack": "twin_pack.json",
    "twin-assets": None,
}

#: 允許進頁面的素材副檔名。只有 PNG——展件的人物是去背 PNG（`ops/exhibit/PLAN.md` B2）。
ASSET_SUFFIX = ".png"


def assets_block() -> str:
    """素材 → `{名字: data URI}`。名字就是檔名去掉 `.png`。

    為什麼是 data URI 而不是 `<img src="檔名">`：實體場地不能假設網路，也不能
    假設檔案被一起搬過去。整頁一個檔，`file://` 直開。
    """
    out: dict[str, str] = {}
    for p in sorted(ASSETS.glob("*" + ASSET_SUFFIX)):
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        out[p.stem] = "data:image/png;base64," + b64
    return json.dumps(out, ensure_ascii=False, sort_keys=True)


def expected_block(block_id: str) -> str:
    src = BLOCKS[block_id]
    if src is None:
        if block_id == "twin-assets":
            return assets_block()
        raise KeyError(block_id)
    return (TWIN / src).read_text(encoding="utf-8").strip("\n")


def expected_canon() -> str:
    html = SOURCE_VIEWER.read_text(encoding="utf-8")
    i, j = html.find(CANON_BEGIN), html.find(CANON_END)
    if i < 0 or j < 0:
        raise SystemExit("examples/receipt_viewer.html 裡找不到 CANON-BEGIN／CANON-END")
    return html[i:j + len(CANON_END)]


def extract_block(html: str, block_id: str) -> str:
    m = re.search(r'<script[^>]*id="%s"[^>]*>\n(.*?)\n</script>' % re.escape(block_id),
                  html, re.S)
    if not m:
        raise ValueError(f"頁面裡找不到 id={block_id} 的內嵌區塊")
    return m.group(1)


def extract_canon(html: str) -> str:
    i, j = html.find(CANON_COPY_BEGIN), html.find(CANON_COPY_END)
    if i < 0 or j < 0:
        raise ValueError("頁面裡找不到 CANON-COPY-BEGIN／CANON-COPY-END")
    i = html.index("\n", i) + 1
    return html[i:j].rstrip("\n")


def build(html: str) -> str:
    for block_id in BLOCKS:
        body = expected_block(block_id)
        pat = re.compile(r'(<script[^>]*id="%s"[^>]*>\n)(.*?)(\n</script>)'
                         % re.escape(block_id), re.S)
        if not pat.search(html):
            raise ValueError(f"頁面裡找不到 id={block_id} 的內嵌區塊")
        # repl 傳函式 ⇒ 回傳值原樣使用，不做 \1 這類反向引用展開（資料裡有反斜線）。
        html = pat.sub(lambda m: m.group(1) + body + m.group(3), html, count=1)
    i, j = html.find(CANON_COPY_BEGIN), html.find(CANON_COPY_END)
    if i < 0 or j < 0:
        raise ValueError("頁面裡找不到 CANON-COPY-BEGIN／CANON-COPY-END")
    i = html.index("\n", i) + 1
    return html[:i] + expected_canon() + "\n" + html[j:]


def check(html: str) -> list[str]:
    bad = []
    for block_id in BLOCKS:
        try:
            got = extract_block(html, block_id)
        except ValueError as exc:
            bad.append(str(exc))
            continue
        if got != expected_block(block_id):
            bad.append(f"{block_id}：內嵌內容與來源不同")
    try:
        if extract_canon(html) != expected_canon():
            bad.append("CANON 區段與 examples/receipt_viewer.html 不同")
    except ValueError as exc:
        bad.append(str(exc))
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="組裝／檢查 examples/twin_viewer.html")
    ap.add_argument("--check", action="store_true", help="只檢查內嵌資料是否與來源相同")
    a = ap.parse_args(argv)
    html = VIEWER.read_text(encoding="utf-8")
    if a.check:
        bad = check(html)
        for b in bad:
            print("[BROKEN] " + b)
        print("總判定：%s（%d 個內嵌區塊）" % ("OK" if not bad else "BROKEN", len(BLOCKS)))
        return 0 if not bad else 1
    out = build(html)
    VIEWER.write_text(out, encoding="utf-8")
    n = len(out.encode("utf-8"))
    print("寫出 %s：%.2f MB" % (VIEWER.relative_to(REPO), n / 1024 / 1024))
    for block_id in BLOCKS:
        body = extract_block(out, block_id)
        print("  %-14s %9d bytes  %s"
              % (block_id, len(body.encode("utf-8")), BLOCKS[block_id] or "（推導）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
