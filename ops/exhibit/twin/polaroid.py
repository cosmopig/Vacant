"""twin/polaroid — 分身那一跑做完之後，**給觀眾帶走的那一張拍立得**。

## 這支在架構裡承重什麼

人類 2026-09-26：「最後一定要有可以給使用者回饋到他手機上的類似拍立得的東西，
讓他可以分享。」同一天：「現在每個畫面一堆資料，要最小程度的留下東西。」
裁決：`decisions/DECISION_20260926_TWIN_POLAROID.md`。

一張直式白邊相片卡，上面**只有四樣東西**：

1. 他的分身（黏土小人，`cast_id` → `assets/cast40/cNN.png`）在做事的樣子；
2. 白邊下緣一行手寫感的字：**他的分身決定做的那件事**（短句，過長截斷）；
3. 一行小字：日期 · 展名 · 收據短碼（收據鏈頭 `verdict_hash` 前 8 碼）；
4. 右下角一個 QR：**官網網址本身**（`SITE_URL`），不帶任何參數。

**不放**判決長文、統計、說明、記號、觀眾打的任何一個字。

## `cast_id` 的單一來源（`pick_cast_for`）

電視（`vacant_hm/world3/index.html::pickCastFor`）原本在前端自己算分身長什麼樣。
拍立得在後端生成，手機拿的是後端的圖——兩邊各算一次就有兩張臉的風險。
所以這裡**逐字移植**那一支（形狀 ＋3、顏色 ＋2、質感 ＋1、平手看 `COLOR_ANCHOR`
的 RGB 距離、再平手取 manifest 裡的第一個），`build_view` 的 `people[]` 帶出
`cast_id`，電視那一側改成「有 `cast_id` 就用它」（另一條線）。
判準是**逐一相等**：`tests/test_twin_polaroid.py::test_cast_id_matches_frontend_*`
用 node 真的跑前端那一段 JS，對 cast40 全表 × 卡上所有特質組合比對。

## 依賴（寫明理由，因為 CLAUDE.md 說 runtime 依賴只有 `cryptography`）

* **Pillow**：合成 PNG 要貼有 alpha 的精靈圖、要把中文字點陣化——後者 stdlib 做不到
  （要自己寫 TrueType 輪廓解析＋掃描線光柵化）。無頭瀏覽器更重（VM 上要一整個 Chrome）。
  所以這一支（`ops/` 腳本，不是 `vacant_network/` 套件）用 Pillow，**而且是可選的**：
  `available()` 回 `(False, 理由)` 時 twinlink **不發拍立得、照實記一筆**，
  分身照樣上螢幕、手機照樣拿到結果——少的是那張圖，不是整條線。
  ⚠ 2026-09-26 查過：vacant-dev（VM）的系統 python3 **沒有 Pillow**。
  上線前要裝（`apt install python3-pil` 或 venv 裡 `pip install pillow`），見裁決檔。
* **字型**：`assets/fonts/jf-openhuninn-2.0.ttf`（jf 粉圓，SIL OFL 1.1，原樣附上）。
  放進 repo 是為了離線紅線（CLAUDE.md 硬約束 2）：展場不能假設 VM 上有中文字型。
  sha256 釘死在 `FONT_SHA256`，對不上就當成不可用（不要用別的字型偷偷湊）。
* **QR**：`ops/exhibit/twin/qr.py`（stdlib，外部對照在 `tests/test_qr.py`）。

## 誠實邊界（改碼時保留）

1. **拍立得上那句話是分身的決定，不是觀眾的話**——但它是從觀眾特質衍生的東西。
   所以它照鏈外原文的規格處理：住在 twinvault（`plain/<slug>/polaroid.png`），
   撤回時一起 `unlink()`，被刪位元組的 sha256 簽進 `PERSONA_ERASED`。
2. **「不出現可識別本人的原文」是一把尺不是一道牆。** `caption_leaks_original`
   擋的是**逐字**抄錄（連續 `LEAK_WINDOW` 個字元以上與觀眾原文相同 ⇒ 改用中性句）；
   它擋不住改寫、擋不住模型自己編的名字。分身的系統提示詞已經要求不逐字抄 TRAITS.md，
   這一把是第二層，不是保證。
3. **掃得到是量出來的，不是「應該掃得到」。** 範例圖本身拿外部解碼器解過
   （`evidence_polaroid_20260926/qr_decode.json`），手機拍螢幕那一格是**模擬**
   （縮到手機顯示尺寸＋模糊＋JPEG），不是真的拿兩支手機對拍——那一格要現場實測。
4. **分享出去的圖，我們收不回來。** 撤回刪得掉的是會場 VM 與雲端上的那一份；
   觀眾自己存下來、傳出去的那幾份不在射程內。所以圖上從一開始就不放可識別本人的東西。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import pathlib
import re
import sys
from typing import Any, Iterable

HERE = pathlib.Path(__file__).resolve()
TWIN = HERE.parent
REPO = TWIN.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ops.exhibit.twin import qr  # noqa: E402

ASSETS = TWIN / "assets"
CAST_DIR = ASSETS / "cast40"
FONT_PATH = ASSETS / "fonts" / "jf-openhuninn-2.0.ttf"
#: 字型與 manifest 的 sha256。**對不上就不可用**——不要讓一個被換掉的檔悄悄改掉畫面。
FONT_SHA256 = "eec8b0b68c34b9166ae37bed839b6126116b225d97f21a5954bb542b9fd1e68c"
#: 與 `vacant_hm/world2/sprites/cast40/manifest.json` 逐 byte 相同（node 對照會驗）。
MANIFEST_SHA256 = "d0b1aecee81b40760e1b693d8ce48f1be455f0fea75832111dbb3ff491c10fdb"

#: A 線（Flow 生的拍立得相框）交件的地方。有 `polaroid_frame.png`＋`.json` 就用它，
#: 沒有就用程式畫的佔位相框。環境變數優先（素材暫存區在 repo 外）。
FRAME_ENV = "VACANT_POLAROID_FRAME_DIR"
DEFAULT_FRAME_DIR = ASSETS / "polaroid"

#: QR 的內容：**官網網址本身**。不帶 sub_id、記號、utm 或任何可追蹤參數——
#: 分享出去的圖任何人都看得到（人類 2026-09-26）。改這個值要重跑 QR 解碼驗收。
SITE_URL = "https://vacant.cosmopig.com"
#: 展名（手機頁 `<title>`：「VACANT · 世界需要一個你」）。
EXHIBIT_NAME = "VACANT"

# ── 版面（佔位相框；單位 px）──────────────────────────────────────────────
#: 經典拍立得是 88×107 mm（0.82）；取 1080×1350（4:5，0.80）——差一點點，
#: 換來的是社群直式貼文的原生比例（分享出去不被裁），而且下緣白邊夠放 v3 的 QR。
CANVAS = (1080, 1350)
#: 相片窗（左、上、右、下）。下緣白邊比較厚，字與 QR 住那裡。
WINDOW = (60, 60, 1020, 1020)
#: 那一行字的字級與框高（框的位置由 `_derive_layout` 從相片窗與 QR 推出來；
#: 「字不出界」的判準就是那個框）。
CAPTION_PX = 48
CAPTION_BOX_H = 64
#: 小字。**右端停在 QR 靜區左邊**。
FOOTER_PX = 26
FOOTER_BOX_H = 36
#: QR：官網網址 27 bytes ⇒ v3-M ＝ 29 模組。每模組 8 px ⇒ 232 px，靜區 4 模組（規格要求）。
#: 右緣對齊相片窗、下緣離紙邊 48 px。**8 不是拍腦袋**：6 px 時模擬「手機拍螢幕」
#: 在 15 cm 距離只解得開約一半（裁決檔 §四的掃描表），8 px 全過。低於 6 的相框素材一律退回。
QR_MODULE_PX = 8
QR_MIN_MODULE_PX = 6
QR_QUIET_MODULES = 4
QR_EDGE_BOTTOM = 48

#: 字與紙的顏色。
INK = (43, 38, 34)
INK_SOFT = (122, 112, 102)
PAPER = (248, 245, 239)
QR_DARK = (24, 21, 19)

#: 「逐字抄錄」的判準：分身的句子裡有**連續這麼多個字元**與觀眾原文相同 ⇒ 換成中性句。
LEAK_WINDOW = 8
NEUTRAL_CAPTION = "他在這裡完成了一件事"

#: 電視那一支的顏色錨點（`vacant_hm/world3/index.html` `COLOR_ANCHOR`，逐字）。
COLOR_ANCHOR: dict[str, tuple[int, int, int]] = {
    "暖土": (160, 115, 75), "赭紅": (155, 85, 70), "奶油": (225, 210, 185),
    "灰藍": (115, 120, 130), "苔綠": (125, 128, 82), "沙金": (195, 155, 88),
}


class PolaroidError(RuntimeError):
    """拍立得做不出來（素材壞、版面放不下）。呼叫端記一筆、不發，不要湊一張。"""


# ---------------------------------------------------------------------------
# cast_id：電視 `pickCastFor` 的逐字移植
# ---------------------------------------------------------------------------

_MANIFEST: dict[str, dict[str, Any]] | None = None


def load_manifest(path: pathlib.Path | None = None) -> dict[str, dict[str, Any]]:
    """cast40 的 manifest。**保留檔案裡的鍵順序**（平手時取第一個，順序就是規格）。"""
    global _MANIFEST
    if path is None and _MANIFEST is not None:
        return _MANIFEST
    p = path or (CAST_DIR / "manifest.json")
    m = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(m, dict) or not m:
        raise PolaroidError(f"manifest 不是非空物件：{p}")
    if path is None:
        _MANIFEST = m
    return m


def _truthy(v: Any) -> bool:
    """JS 的 truthiness（`card.shape && …` 那一段）。卡上的值只會是字串或 null。"""
    if v is None or v is False:
        return False
    if isinstance(v, str):
        return v != ""
    if isinstance(v, (int, float)):
        return v != 0 and v == v        # NaN 是 falsy
    return True


def pick_cast_for(card: Any, manifest: dict[str, dict[str, Any]] | None = None, *,
                  _tie: str = "first") -> str:
    """卡上的形狀／顏色／質感 → cast40 的哪一張（`cNN`）。

    逐字對照 `vacant_hm/world3/index.html` 的 `pickCastFor(card)`：

    ```js
    const anchor = COLOR_ANCHOR[card.color] || null;
    let best = null, bestKey = [-1, Infinity];
    for (const [id, m] of Object.entries(manifest)){
      let sc = 0;
      if (card.shape && m.shape === card.shape) sc += 3;
      if (card.color && m.color === card.color) sc += 2;
      if (card.texture && m.texture === card.texture) sc += 1;
      let cd = 0;
      if (anchor && m.avg_rgb){ cd = Σ (m.avg_rgb[i]-anchor[i])**2 }
      if (sc > bestKey[0] || (sc === bestKey[0] && cd < bestKey[1])){ bestKey=[sc,cd]; best=id; }
    }
    ```

    `card=None` 當成 `{}`（電視那一側一律 `pickCastFor(card || {})`）。
    `_tie="last"` 只給負控制用：把平手規則改錯，對照測試必須紅。

    ⚠ 誠實邊界：`COLOR_ANCHOR[card.color]` 在 JS 裡對 `"constructor"` 之類的
      原型鍵會拿到函式（`NaN` 距離）。卡上的色系是伺服器收斂過的枚舉（或 null），
      那種值進不來；這裡不去模仿那個怪行為。
    """
    m_all = manifest if manifest is not None else load_manifest()
    c = card if isinstance(card, dict) else {}
    shape, color, texture = c.get("shape"), c.get("color"), c.get("texture")
    anchor = COLOR_ANCHOR.get(color) if isinstance(color, str) else None
    best: str | None = None
    best_sc, best_cd = -1, float("inf")
    for cid, m in m_all.items():
        m = m if isinstance(m, dict) else {}
        sc = 0
        if _truthy(shape) and m.get("shape") == shape:
            sc += 3
        if _truthy(color) and m.get("color") == color:
            sc += 2
        if _truthy(texture) and m.get("texture") == texture:
            sc += 1
        cd = 0
        rgb = m.get("avg_rgb")
        if anchor and rgb:
            cd = sum((rgb[i] - anchor[i]) ** 2 for i in range(3))
        better_tie = cd < best_cd if _tie == "first" else cd <= best_cd
        if sc > best_sc or (sc == best_sc and better_tie):
            best_sc, best_cd, best = sc, cd, cid
    assert best is not None          # manifest 非空 ⇒ 第一張就一定贏過 -1
    return best


# ---------------------------------------------------------------------------
# 可用性
# ---------------------------------------------------------------------------

def _sha256_file(p: pathlib.Path) -> str | None:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def available() -> tuple[bool, str]:
    """這一台做得出拍立得嗎。**做不出來要講為什麼**（twinlink 會照實記）。"""
    try:
        import PIL  # noqa: F401
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    except ImportError:
        return False, "pillow_missing：這台 python 沒有 Pillow（apt install python3-pil 或 pip install pillow）"
    if _sha256_file(FONT_PATH) != FONT_SHA256:
        return False, f"font_mismatch：{FONT_PATH.name} 不在或 sha256 對不上"
    if _sha256_file(CAST_DIR / "manifest.json") != MANIFEST_SHA256:
        return False, "manifest_mismatch：cast40/manifest.json 不在或 sha256 對不上"
    return True, "ok"


# ---------------------------------------------------------------------------
# 那一行字
# ---------------------------------------------------------------------------

_MD_NOISE = re.compile(r"[#*_`>~|\[\]]")
_QUOTES = "「」『』“”\"'‘’《》〈〉"


def clean_caption(decision: Any) -> str:
    """PLAN.md 的第一行 → 一句乾淨的短句（去 markdown、引號、多餘空白、句尾句號）。"""
    s = str(decision or "")
    s = s.splitlines()[0] if s.strip() else ""
    s = " ".join(_MD_NOISE.sub("", s).split())
    prev = None
    while s != prev:                     # 「寫一封信」。 ⇒ 句號與引號交替剝，剝到不動為止
        prev = s
        s = s.strip().strip(_QUOTES).strip().rstrip("。．.！!；;，,、：:").rstrip()
    return s


def _norm_for_leak(s: str) -> str:
    return "".join(ch for ch in str(s) if not ch.isspace()
                   and ch not in "，。、！？：；,.!?:;「」『』\"'（）()")


def caption_leaks_original(caption: str, originals: Iterable[Any],
                           window: int = LEAK_WINDOW) -> bool:
    """分身的句子裡有沒有**連續 `window` 個字元**逐字來自觀眾原文。

    比對前去掉空白與標點（改個逗號不算沒抄）。短於 `window` 的句子不可能命中。
    """
    cap = _norm_for_leak(caption)
    if len(cap) < window:
        return False
    hay = [_norm_for_leak(o) for o in originals if isinstance(o, str) and o]
    hay = [h for h in hay if len(h) >= window]
    if not hay:
        return False
    for i in range(len(cap) - window + 1):
        piece = cap[i:i + window]
        if any(piece in h for h in hay):
            return True
    return False


def originals_of(card: Any, card_text: Any) -> list[str]:
    """觀眾原文裡**自由文字**的那幾格（枚舉類別不是原文，不算）。"""
    out: list[str] = []
    if isinstance(card, dict):
        for k in ("need", "vibe", "first_line"):
            v = card.get(k)
            if isinstance(v, str) and v:
                out.append(v)
    if isinstance(card_text, str) and card_text:
        out.append(card_text)
    return out


# ---------------------------------------------------------------------------
# 合成
# ---------------------------------------------------------------------------

_FONTS: dict[int, Any] = {}


def _font(px: int):
    """同一個字級只開一次（`_has_glyph` 的快取以字型物件為鍵，物件要活著才不會撞 id）。"""
    f = _FONTS.get(px)
    if f is None:
        from PIL import ImageFont
        f = _FONTS[px] = ImageFont.truetype(str(FONT_PATH), px,
                                            layout_engine=ImageFont.Layout.BASIC)
    return f


_GLYPH_CACHE: dict[tuple[int, str], bool] = {}
_NOTDEF_CACHE: dict[int, bytes] = {}


def _has_glyph(font: Any, ch: str) -> bool:
    """字型畫不畫得出這個字（畫不出來的會變成 .notdef 豆腐框）。

    做法：把這個字跟一個一定不存在的碼位（U+10FFFD）各畫一次，**點陣一樣 ⇒ 沒有這個字**。
    空白字元一律算有（它本來就畫不出東西）。
    """
    if ch.isspace():
        return True
    key = (id(font), ch)
    if key in _GLYPH_CACHE:
        return _GLYPH_CACHE[key]
    from PIL import Image, ImageDraw

    def render(c: str) -> bytes:
        im = Image.new("L", (96, 96), 0)
        ImageDraw.Draw(im).text((8, 8), c, font=font, fill=255)
        return im.tobytes()

    notdef = _NOTDEF_CACHE.get(id(font))
    if notdef is None:
        notdef = _NOTDEF_CACHE[id(font)] = render("\U0010FFFD")
    ok = render(ch) != notdef
    _GLYPH_CACHE[key] = ok
    return ok


def _drop_missing(font: Any, text: str) -> tuple[str, int]:
    kept, dropped = [], 0
    for ch in text:
        if _has_glyph(font, ch):
            kept.append(ch)
        else:
            dropped += 1
    return " ".join("".join(kept).split()), dropped


def fit_text(font: Any, text: str, max_w: int) -> tuple[str, bool]:
    """放得進 `max_w` 就原樣；放不進就從尾巴截、補「…」。回（字, 有沒有截）。"""
    if font.getlength(text) <= max_w:
        return text, False

    def cut(n: int) -> str:              # 截在標點或空白上就把它也拿掉（不要「，…」）
        return text[:n].rstrip(" 　，。、；：,.;:!！?？「『（(") + "…"

    lo, hi = 0, len(text)
    while lo < hi:                       # 找最長的前綴，使得 前綴＋… 放得下
        mid = (lo + hi + 1) // 2
        if font.getlength(cut(mid)) <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return cut(lo), True


def _vgrad(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]):
    from PIL import Image
    w, h = size
    col = Image.new("RGB", (1, h))
    px = col.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(int(round(top[i] + (bottom[i] - top[i]) * t)) for i in range(3))
    return col.resize((w, h))


def render_scene(cast_id: str, size: tuple[int, int]):
    """相片窗裡那一格：**他的分身在做事**——站在一張小桌旁，桌上是他寫的那張紙。

    佔位畫法（程式畫的）。A 線的素材到了之後，換的是相框，不是這一格。
    """
    from PIL import Image, ImageDraw, ImageFilter
    ww, wh = size
    img = _vgrad(size, (236, 223, 202), (214, 192, 160)).convert("RGBA")
    d = ImageDraw.Draw(img)
    floor_y = int(wh * 0.80)
    # 地板：略深、從牆腳往下漸層
    floor = _vgrad((ww, wh - floor_y), (200, 172, 134), (184, 154, 116)).convert("RGBA")
    img.alpha_composite(floor, (0, floor_y))
    d.line([(0, floor_y), (ww, floor_y)], fill=(176, 146, 110, 255), width=3)
    # 窗光（左上一塊亮）
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([-ww * 0.2, -wh * 0.35, ww * 0.55, wh * 0.45],
                                 fill=(255, 246, 228, 90))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(ww * 0.06)))

    # 桌子（右邊）
    tx0, tx1 = int(ww * 0.56), int(ww * 0.93)
    ty = int(wh * 0.585)
    th = int(wh * 0.035)
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([tx0 - 10, floor_y - 14, tx1 + 10, floor_y + 22], fill=(60, 40, 20, 70))
    fig_cx = int(ww * 0.34)
    sd.ellipse([fig_cx - ww * 0.17, floor_y - 16, fig_cx + ww * 0.17, floor_y + 26],
               fill=(60, 40, 20, 90))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(12)))
    d = ImageDraw.Draw(img)
    leg_w = max(10, int(ww * 0.018))
    for lx in (tx0 + int(ww * 0.03), tx1 - int(ww * 0.03) - leg_w):
        d.rounded_rectangle([lx, ty + th - 4, lx + leg_w, floor_y + 6], radius=5,
                            fill=(150, 104, 70, 255))
    d.rounded_rectangle([tx0, ty, tx1, ty + th], radius=10, fill=(178, 128, 88, 255))
    d.rounded_rectangle([tx0 + 4, ty + 3, tx1 - 4, ty + th * 0.45], radius=8,
                        fill=(196, 148, 106, 255))

    # 桌上那張紙（他寫的東西），略斜
    pw, ph = int(ww * 0.20), int(wh * 0.12)
    paper = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    pd = ImageDraw.Draw(paper)
    pd.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=6, fill=(252, 249, 242, 255),
                         outline=(214, 204, 188, 255), width=2)
    for i in range(5):
        y = int(ph * (0.2 + i * 0.15))
        x1 = int(pw * (0.85 if i < 4 else 0.55))
        pd.line([(int(pw * 0.12), y), (x1, y)], fill=(150, 140, 128, 255), width=3)
    paper = paper.rotate(-8, resample=Image.BICUBIC, expand=True)
    # 紙平放在桌面上：只露出上緣一截的透視感用壓扁表現
    paper = paper.resize((paper.width, max(1, int(paper.height * 0.42))), Image.LANCZOS)
    img.alpha_composite(paper, (int(ww * 0.62), ty - paper.height + int(th * 0.35)))
    # 鉛筆
    pen = Image.new("RGBA", (int(ww * 0.13), 14), (0, 0, 0, 0))
    pn = ImageDraw.Draw(pen)
    pn.rectangle([0, 2, pen.width - 22, 11], fill=(232, 182, 60, 255))
    pn.polygon([(pen.width - 22, 2), (pen.width - 1, 7), (pen.width - 22, 11)],
               fill=(222, 196, 150, 255))
    pn.polygon([(pen.width - 7, 5), (pen.width - 1, 7), (pen.width - 7, 9)],
               fill=(60, 52, 46, 255))
    pen = pen.rotate(14, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(pen, (int(ww * 0.585), ty - pen.height + 6))

    # 分身本人
    sprite_p = CAST_DIR / f"{cast_id}.png"
    if not re.fullmatch(r"c\d{2}", cast_id or "") or not sprite_p.is_file():
        raise PolaroidError(f"cast_id 不合法或精靈圖不在：{cast_id!r}")
    spr = Image.open(sprite_p).convert("RGBA")
    bbox = spr.getbbox() or (0, 0, spr.width, spr.height)
    spr = spr.crop(bbox)
    # 精靈圖是去背出來的，邊上有一圈淺色毛邊；alpha 往內收 1 px 再縮放。
    spr.putalpha(spr.getchannel("A").filter(ImageFilter.MinFilter(3)))
    target_h = int(wh * 0.56)
    scale = target_h / spr.height
    spr = spr.resize((max(1, int(spr.width * scale)), target_h), Image.LANCZOS)
    img.alpha_composite(spr, (fig_cx - spr.width // 2, floor_y + 8 - spr.height))

    # 輕微暗角
    vig = Image.new("L", size, 0)
    ImageDraw.Draw(vig).rectangle([0, 0, ww, wh], outline=255, width=int(ww * 0.05))
    vig = vig.filter(ImageFilter.GaussianBlur(ww * 0.06))
    dark = Image.new("RGBA", size, (70, 50, 30, 0))
    dark.putalpha(vig.point(lambda v: int(v * 0.35)))
    img.alpha_composite(dark)
    return img.convert("RGB")


def _box(v: Any) -> tuple[int, int, int, int] | None:
    """`[x0,y0,x1,y1]` 或 `{"x","y","w","h"}` → tuple。不合法 ⇒ None。"""
    try:
        if isinstance(v, dict):
            x, y, w, h = (int(v[k]) for k in ("x", "y", "w", "h"))
            return (x, y, x + w, y + h)
        if isinstance(v, (list, tuple)) and len(v) == 4:
            x0, y0, x1, y1 = (int(t) for t in v)
            return (x0, y0, x1, y1)
    except (KeyError, TypeError, ValueError):
        return None
    return None


def _inside(inner: tuple[int, int, int, int], outer: tuple[int, int, int, int]) -> bool:
    return (inner[0] >= outer[0] and inner[1] >= outer[1]
            and inner[2] <= outer[2] and inner[3] <= outer[3])


def _overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _qr_at(x0: int, y0: int, module: int, quiet: int = QR_QUIET_MODULES,
           text: str = SITE_URL) -> dict[str, Any]:
    m = qr.matrix(text)
    n = len(m)
    size = n * module
    q = quiet * module
    return {"matrix": m, "n": n, "box": (x0, y0, x0 + size, y0 + size),
            "quiet_box": (x0 - q, y0 - q, x0 + size + q, y0 + size + q), "module": module}


def _derive_layout(canvas: tuple[int, int], win: tuple[int, int, int, int],
                   module: int = QR_MODULE_PX) -> dict[str, Any]:
    """從「紙多大、相片窗在哪」推出字框與 QR 的位置（佔位相框與沒給框的素材共用）。

    QR 貼右下角：右緣對齊相片窗右緣、下緣離紙邊 `QR_EDGE_BOTTOM`。
    那一行字與小字住在 QR **左邊**那一欄：右端停在靜區左邊 20 px。
    """
    n = len(qr.matrix(SITE_URL))
    size = n * module
    x1 = win[2]
    y1 = canvas[1] - QR_EDGE_BOTTOM
    g = _qr_at(x1 - size, y1 - size, module)
    col_x1 = g["quiet_box"][0] - 20
    band_top = win[3]
    cap_y0 = band_top + int((g["box"][1] - band_top) * 0.5) + 14
    cap = (win[0] + 12, cap_y0, col_x1, cap_y0 + CAPTION_BOX_H)
    foot = (win[0] + 12, y1 - FOOTER_BOX_H, col_x1, y1)
    return {"canvas": canvas, "window": win, "caption": cap, "footer": foot, "qr": g}


def _layout_problems(lay: dict[str, Any]) -> list[str]:
    cw, ch = lay["canvas"]
    win, cap, foot, g = lay["window"], lay["caption"], lay["footer"], lay["qr"]
    full = (0, 0, cw, ch)
    problems = []
    if cap[3] - cap[1] < CAPTION_PX or cap[2] - cap[0] < CAPTION_PX * 8:
        problems.append("caption 框放不下八個字")
    for name, b in (("window", win), ("caption", cap), ("footer", foot),
                    ("qr_quiet", g["quiet_box"])):
        if not _inside(b, full):
            problems.append(f"{name} 出紙")
    for a, b, name in ((cap, g["quiet_box"], "caption×qr"),
                       (foot, g["quiet_box"], "footer×qr"),
                       (win, g["quiet_box"], "window×qr"),
                       (cap, win, "caption×window"),
                       (cap, foot, "caption×footer")):
        if _overlap(a, b):
            problems.append(f"{name} 重疊")
    if g["module"] < QR_MIN_MODULE_PX:
        problems.append(f"QR 模組小於 {QR_MIN_MODULE_PX} px（掃不到的風險，見裁決 §四）")
    return problems


def layout_for(frame_dir: pathlib.Path | None = None, *,
               module: int = QR_MODULE_PX) -> dict[str, Any]:
    """用哪一個相框、版面長怎樣。**不合格的相框退回佔位相框，並且講為什麼。**

    A 線交件的 json 至少要有 `window`（`[x0,y0,x1,y1]` 或 `{x,y,w,h}`）；可選 `caption`、
    `footer`、`qr`（同格式；`qr` 是碼本身的外框，模組大小＝寬度 ÷ 模組數）。
    缺的就用 `_derive_layout` 從相片窗推。放不下（字框太小、靜區出紙、互相重疊、
    模組太小）⇒ 退回佔位相框，`frame_note` 寫理由。
    """
    base = {**_derive_layout(CANVAS, WINDOW, module), "frame_png": None,
            "frame": "placeholder", "frame_note": None}
    d = frame_dir
    if d is None:
        env = os.environ.get(FRAME_ENV, "").strip()
        d = pathlib.Path(env) if env else DEFAULT_FRAME_DIR
    png, js = d / "polaroid_frame.png", d / "polaroid_frame.json"
    if not png.is_file() or not js.is_file():
        base["frame_note"] = "no_frame_file"
        return base
    try:
        from PIL import Image
        spec = json.loads(js.read_text(encoding="utf-8"))
        with Image.open(png) as im:
            canvas = im.size
        win = _box(spec.get("window"))
        if win is None:
            raise ValueError("json 沒有合法的 window")
        lay = _derive_layout(canvas, win, module)
        lay["caption"] = _box(spec.get("caption")) or lay["caption"]
        lay["footer"] = _box(spec.get("footer")) or lay["footer"]
        qspec = _box(spec.get("qr"))
        if qspec is not None:
            mod = max(1, (qspec[2] - qspec[0]) // lay["qr"]["n"])
            lay["qr"] = _qr_at(qspec[0], qspec[1], mod)
        problems = _layout_problems(lay)
        if problems:
            raise ValueError("；".join(problems))
    except Exception as exc:                              # noqa: BLE001
        base["frame_note"] = f"frame_rejected：{type(exc).__name__}: {exc}"[:300]
        return base
    return {**lay, "frame_png": png, "frame": "file:" + (_sha256_file(png) or "?")[:12],
            "frame_note": None}


def _placeholder_frame(canvas: tuple[int, int], window: tuple[int, int, int, int]):
    """程式畫的白邊：紙色＋一點點紙紋＋相片窗內緣一圈細陰影。"""
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.new("RGB", canvas, PAPER)
    d = ImageDraw.Draw(img)
    # 紙邊一圈極淡的灰，截圖放在白底上看得出邊界
    d.rectangle([0, 0, canvas[0] - 1, canvas[1] - 1], outline=(226, 221, 212), width=2)
    inner = Image.new("L", canvas, 0)
    ImageDraw.Draw(inner).rectangle(
        [window[0] - 3, window[1] - 3, window[2] + 3, window[3] + 3], fill=90)
    inner = inner.filter(ImageFilter.GaussianBlur(4))
    shade = Image.new("RGB", canvas, (180, 170, 156))
    img = Image.composite(shade, img, inner)
    return img


def compose(*, decision: str, cast_id: str, date_str: str, receipt_short: str,
            originals: Iterable[Any] = (), frame_dir: pathlib.Path | None = None,
            qr_module_px: int = QR_MODULE_PX, _sweep_only: bool = False
            ) -> tuple[bytes, dict[str, Any]]:
    """做一張拍立得。回（PNG bytes, meta）。meta 只有版面與旗標，**不含那句話本身**。

    `originals` ＝ 觀眾原文的自由文字格（`originals_of`）：拿來擋逐字抄錄，不會被畫出來。
    `qr_module_px`／`_sweep_only` 只給掃描實驗用（量最小模組尺寸，`_sweep_only` 讓
    低於下限的模組也畫得出來以便量到懸崖在哪）。產品路徑一律用預設值。
    """
    ok, why = available()
    if not ok:
        raise PolaroidError(why)
    from PIL import Image, ImageDraw
    if not re.fullmatch(r"[0-9a-f]{8}", receipt_short or ""):
        raise PolaroidError("收據短碼要是 8 個小寫十六進位字元（verdict_hash 前 8 碼）")
    lay = layout_for(frame_dir, module=qr_module_px)
    probs = [p for p in _layout_problems(lay)
             if not (_sweep_only and p.startswith("QR 模組小於"))]
    if lay["frame_png"] is None and probs:
        raise PolaroidError("佔位版面放不下：" + "；".join(probs))
    canvas, win = lay["canvas"], lay["window"]
    cap_box, foot_box, g = lay["caption"], lay["footer"], lay["qr"]

    if lay["frame_png"] is not None:
        img = Image.open(lay["frame_png"]).convert("RGB")
    else:
        img = _placeholder_frame(canvas, win)
    scene = render_scene(cast_id, (win[2] - win[0], win[3] - win[1]))
    img.paste(scene, (win[0], win[1]))
    d = ImageDraw.Draw(img)

    # ── 那一行字 ──
    f_cap = _font(CAPTION_PX)
    caption = clean_caption(decision)
    redacted = False
    if caption and caption_leaks_original(caption, originals):
        caption, redacted = NEUTRAL_CAPTION, True
    caption, dropped = _drop_missing(f_cap, caption)
    if not caption:
        caption = NEUTRAL_CAPTION
    caption, truncated = fit_text(f_cap, caption, cap_box[2] - cap_box[0])
    cx = (cap_box[0] + cap_box[2]) // 2
    cy = (cap_box[1] + cap_box[3]) // 2
    d.text((cx, cy), caption, font=f_cap, fill=INK, anchor="mm")
    cap_drawn = d.textbbox((cx, cy), caption, font=f_cap, anchor="mm")

    # ── 小字 ──
    f_foot = _font(FOOTER_PX)
    footer = f"{date_str} · {EXHIBIT_NAME} · 收據 {receipt_short}"
    footer, _ = fit_text(f_foot, footer, foot_box[2] - foot_box[0])
    fy = (foot_box[1] + foot_box[3]) // 2
    d.text((foot_box[0], fy), footer, font=f_foot, fill=INK_SOFT, anchor="lm")
    foot_drawn = d.textbbox((foot_box[0], fy), footer, font=f_foot, anchor="lm")

    # ── QR（官網本身）──
    qb, qq, mod = g["box"], g["quiet_box"], g["module"]
    # 靜區塗紙色（不是純白）：紙色夠亮（亮度 ≈ 245），解碼器認得；
    # 塗純白會在紙上浮出一塊「貼紙」，而版面要的是只有那個碼。
    d.rectangle(qq, fill=PAPER)
    for r, row in enumerate(g["matrix"]):
        for c, v in enumerate(row):
            if v:
                x, y = qb[0] + c * mod, qb[1] + r * mod
                d.rectangle([x, y, x + mod - 1, y + mod - 1], fill=QR_DARK)

    full = (0, 0, canvas[0], canvas[1])
    problems = []
    if not _inside(cap_drawn, cap_box):
        problems.append("caption 出框")
    if not _inside(foot_drawn, foot_box):
        problems.append("footer 出框")
    if not _inside(qq, full):
        problems.append("QR 靜區出紙")
    if _overlap(cap_drawn, qq) or _overlap(foot_drawn, qq):
        problems.append("字壓到 QR 靜區")
    if problems:
        raise PolaroidError("版面放不下：" + "；".join(problems))

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    png = buf.getvalue()
    meta = {
        "v": 1, "size": list(canvas), "cast_id": cast_id,
        "window": list(win),
        "caption_box": list(cap_box), "caption_drawn": list(cap_drawn),
        "caption_truncated": truncated, "caption_redacted": redacted,
        "caption_chars": len(caption), "dropped_glyphs": dropped,
        "footer_box": list(foot_box), "footer_drawn": list(foot_drawn),
        "qr_text": SITE_URL, "qr_version": (g["n"] - 17) // 4, "qr_modules": g["n"],
        "qr_module_px": mod, "qr_box": list(qb), "qr_quiet_box": list(qq),
        "frame": lay["frame"], "frame_note": lay["frame_note"],
        "bytes_n": len(png),
    }
    return png, meta


# ---------------------------------------------------------------------------
# 自檢用的合成範例（**合成特質**，不是真人）
# ---------------------------------------------------------------------------

#: 範例：合成特質 → 合成的分身決定。**沒有一筆來自真人**。
SAMPLES: tuple[dict[str, Any], ...] = (
    {"name": "short", "card": {"shape": "圓潤", "color": "暖土", "texture": "光滑"},
     "decision": "寫一封謝卡給國小導師"},
    {"name": "long_truncated", "card": {"shape": "修長", "color": "苔綠", "texture": "斑駁"},
     "decision": "為下週末安排一份慢節奏的散步路線，途中經過三家老書店、一間賣手沖咖啡的小店，最後在河堤看夕陽"},
    {"name": "mixed_emoji", "card": {"shape": "方正", "color": "赭紅", "texture": "指紋"},
     "decision": "## 列一張「搬家 checklist」✅ 給室友 📦"},
    {"name": "no_traits", "card": {},
     "decision": "整理一份給自己的睡前閱讀清單"},
)


def _cli_sample(out: pathlib.Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for i, s in enumerate(SAMPLES):
        cid = pick_cast_for(s["card"])
        rshort = hashlib.sha256(f"synthetic-{i}".encode()).hexdigest()[:8]
        png, meta = compose(decision=s["decision"], cast_id=cid, date_str="2026.09.26",
                            receipt_short=rshort, originals=())
        p = out / f"polaroid_{i + 1}_{s['name']}.png"
        p.write_bytes(png)
        index.append({"file": p.name, "synthetic": True, "card": s["card"],
                      "decision_in": s["decision"], "cast_id": cid,
                      "receipt_short": rshort, "sha256": hashlib.sha256(png).hexdigest(),
                      "meta": meta})
    (out / "samples.json").write_text(
        json.dumps({"note": "合成特質、合成決定、合成收據短碼；沒有任何一筆來自真人",
                    "samples": index}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "n": len(index)}, ensure_ascii=False))
    return 0


def parity_cards() -> list[dict[str, Any]]:
    """cast 對照測試用的卡：三個枚舉各自 ×（全部合法值＋null＋空字串＋不存在的值＋缺鍵）。"""
    from ops.exhibit.twin.twinlink import COLORS, SHAPES, TEXTURES
    MISSING = object()
    shapes = list(SHAPES) + [None, "", "不存在的形狀", MISSING]
    colors = list(COLORS) + [None, "", "紫", MISSING]
    textures = list(TEXTURES) + [None, "", "亮面", MISSING]
    cards = []
    for s in shapes:
        for c in colors:
            for t in textures:
                card: dict[str, Any] = {}
                for k, v in (("shape", s), ("color", c), ("texture", t)):
                    if v is not MISSING:
                        card[k] = v
                cards.append(card)
    return cards


def _cli_parity(out: pathlib.Path, manifest: pathlib.Path | None, tie: str) -> int:
    man = load_manifest(manifest) if manifest else load_manifest()
    rows = [{"card": c, "cast_id": pick_cast_for(c, man, _tie=tie)} for c in parity_cards()]
    out.write_text(json.dumps({"tie": tie, "rows": rows}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "n": len(rows), "out": str(out)}, ensure_ascii=False))
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="twin/polaroid — 拍立得")
    s = ap.add_subparsers(dest="cmd", required=True)
    s.add_parser("check")
    sp = s.add_parser("sample", help="用合成特質產範例拍立得")
    sp.add_argument("--out", required=True)
    pp = s.add_parser("parity-table", help="cast_id 對照表（給 node 對照前端 pickCastFor）")
    pp.add_argument("--out", required=True)
    pp.add_argument("--manifest", default=None)
    pp.add_argument("--tie", choices=("first", "last"), default="first",
                    help="last ＝ 負控制：故意把平手規則改錯")
    a = ap.parse_args(list(argv) if argv is not None else None)
    if a.cmd == "check":
        ok, why = available()
        print(json.dumps({"available": ok, "why": why}, ensure_ascii=False))
        return 0 if ok else 1
    if a.cmd == "sample":
        return _cli_sample(pathlib.Path(a.out))
    if a.cmd == "parity-table":
        return _cli_parity(pathlib.Path(a.out),
                           pathlib.Path(a.manifest) if a.manifest else None, a.tie)
    return 2


if __name__ == "__main__":
    sys.exit(main())
