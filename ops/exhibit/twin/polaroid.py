"""twin/polaroid — 分身那一跑做完之後，**給觀眾帶走的那一張拍立得**。

## 這支在架構裡承重什麼

人類 2026-09-26：「最後一定要有可以給使用者回饋到他手機上的類似拍立得的東西，
讓他可以分享。」同一天：「現在每個畫面一堆資料，要最小程度的留下東西。」
裁決：`decisions/DECISION_20260926_TWIN_POLAROID.md`。

一張直式白邊相片卡，上面**只有四樣東西**：

1. 他的分身站在黏土世界的舞台上（`cast_id` → 有 `assets/poses/cNN_show.png`
   就用「舉著寫好的紙給人看」那一張，沒有就用 `assets/cast40/cNN.png`；背景是電視那一套的
   `s00` 空舞台板）；
2. 白邊下緣最多兩行手寫感的字：**他的分身自己寫在 PLAN.md 第一行的決定**（過長截斷；
   逐字抄了觀眾原文 ⇒ **那一行留空**，不換成任何人寫的句子）；
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
   擋的是**逐字**抄錄（連續 `LEAK_WINDOW` 個字元以上與觀眾原文相同 ⇒ **那一行留空**，
   拍立得照發、只少那一句；2026-09-26 人類：字要是 agent 生成的，不准拿人寫的罐頭句頂替）；
   它擋不住改寫、擋不住模型自己編的名字。分身的系統提示詞已經要求不逐字抄 TRAITS.md，
   這一把是第二層，不是保證。
3. **掃得到是量出來的，不是「應該掃得到」。** 範例圖本身拿外部解碼器解過
   （`evidence_polaroid_20260926/v2/qr_decode.json`），手機拍螢幕那一格是**模擬**
   （縮到手機顯示尺寸＋模糊＋JPEG），不是真的拿兩支手機對拍——那一格要現場實測。
4. **分享出去的圖，我們收不回來。** 撤回刪得掉的是會場 VM 與雲端上的那一份；
   觀眾自己存下來、傳出去的那幾份不在射程內。所以圖上從一開始就不放可識別本人的東西。
5. **姿勢圖只認自己的檔名。** `figure_for` 只找 `<cast_id>_show.png`，沒有就退回
   **同一位**的 cast40 原圖——絕不拿別位的姿勢頂替（那是別人的臉）。它擋的是程式選錯檔，
   擋不住素材線把圖存錯名字（那一層靠 `assets/poses/manifest.json` 的來源紀錄與人眼）。
6. **相框不是照原比例用的。** 素材相框 829×930（0.89），卡面 1080×1350（4:5）：
   按寬度縮放後，**下緣白邊往下延長**（取白邊中段、上下鏡射接續），版面理由見裁決檔。
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

#: A 線（素材線）交件的拍立得相框：`polaroid_frame.png`＋`.json`（2026-09-26 交件，
#: 829×930、中央窗格透明；逐 byte 抄自 `vacant_hm-assets-20260926/polaroid/`）。
#: 沒有就用程式畫的佔位相框。環境變數優先（素材暫存區在 repo 外）。
FRAME_ENV = "VACANT_POLAROID_FRAME_DIR"
DEFAULT_FRAME_DIR = ASSETS / "polaroid"
#: 相框素材說「圖從窗格底下墊進去、四邊各多墊 4 px 以免露縫」（素材原生像素）。
FRAME_UNDERLAY_PX = 4

#: 分身姿勢圖（舉著寫好的紙給人看）。**只認 `<cast_id>_show.png`**，沒有就退回同一位的
#: cast40 原圖（誠實邊界 5）。環境變數給另一條線交件前的暫存區用。
POSES_ENV = "VACANT_POLAROID_POSES_DIR"
DEFAULT_POSES_DIR = ASSETS / "poses"
POSE_SUFFIX = "_show"

#: 相片窗的背景：電視那一套的 `s00` 空舞台（無文字、無 QR、沒有烤進去的生物）。
#: sha256 釘死（對不上＝不可用，與字型同一條規則）。`PLATE_SPOT_X` 是頂光中心欄（原圖 px），
#: 相片窗從那裡置中裁切。
PLATE_PATH = ASSETS / "polaroid" / "plate_s00.jpg"
PLATE_SHA256 = "b39e0074b472ed30bc882c9bec26c81e363c19a4ecd16427a73ef3936fc7a053"
PLATE_SPOT_X = 812
#: 分身在相片窗裡的大小與站位（相片窗高／寬的比例）。寬的（c19 大碗）由寬度上限收住。
FIG_H_FRAC = 0.50
FIG_W_MAX_FRAC = 0.52
FEET_Y_FRAC = 0.86

#: QR 的內容：**官網網址本身**。不帶 sub_id、記號、utm 或任何可追蹤參數——
#: 分享出去的圖任何人都看得到（人類 2026-09-26）。改這個值要重跑 QR 解碼驗收。
SITE_URL = "https://vacant.cosmopig.com"
#: 展名（手機頁 `<title>`：「VACANT · 世界需要一個你」）。
EXHIBIT_NAME = "VACANT"

# ── 版面（佔位相框；單位 px）──────────────────────────────────────────────
#: 經典拍立得是 88×107 mm（0.82）；取 1080×1350（4:5，0.80）——差一點點，
#: 換來的是社群直式貼文的原生比例（分享出去不被裁），而且下緣白邊夠放 v3 的 QR。
CANVAS = (1080, 1350)
#: 佔位相框的相片窗（左、上、右、下）。下緣白邊比較厚，字與 QR 住那裡。
#: v2 下緣 1020 → 980：QR 改 9 px 之後靜區上緣在 1005，窗要讓出來（素材相框的窗下緣在 976）。
WINDOW = (60, 60, 1020, 980)
#: 那一行字的字級與框高（框的位置由 `_derive_layout` 從相片窗與 QR 推出來；
#: 「字不出界」的判準就是那個框）。
#: 2026-09-26 v2：分身自己寫的句子實測 16–30 字（`evidence_polaroid_20260926/v2/runs.json`），
#: 單行 48 px 只放得下 13 字 ⇒ 六張範例全被截。改成**最多兩行、44 px**（一行約 15 字）。
CAPTION_PX = 44
CAPTION_LINES = 2
CAPTION_LINE_H = 60
CAPTION_BOX_H = CAPTION_LINES * CAPTION_LINE_H + 4
#: 小字。**右端停在 QR 靜區左邊**。
FOOTER_PX = 26
FOOTER_BOX_H = 36
#: QR：官網網址 27 bytes ⇒ v3-M ＝ 29 模組。每模組 9 px ⇒ 261 px，靜區 4 模組（規格要求）。
#: 右緣對齊相片窗、下緣離紙邊 48 px。**9 不是拍腦袋**（`evidence_polaroid_20260926/v2/qr_sweep.json`）：
#: v1 佔位相框上 8 px 在模擬「手機拍 15 cm」16/16；換上素材相框（紙色較深、有紙紋）後
#: 8 px 掉到 14/16（另一組 80 次：素材相框 70/80、佔位相框 80/80），9 px 回到 16/16、
#: 連 20 cm 也 16/16。低於 `QR_MIN_MODULE_PX` 的相框素材一律退回。
QR_MODULE_PX = 9
QR_MIN_MODULE_PX = 8
QR_QUIET_MODULES = 4
QR_EDGE_BOTTOM = 48

#: 字與紙的顏色。
INK = (43, 38, 34)
INK_SOFT = (122, 112, 102)
PAPER = (248, 245, 239)
QR_DARK = (24, 21, 19)

#: 「逐字抄錄」的判準：分身的句子裡有**連續這麼多個字元**與觀眾原文相同 ⇒ 那一行留空。
#: ⚠ 2026-09-26 以前這裡會換成一句人寫的中性句；人類：「那個字是不是應該要讓他是 AI agent
#:   生成的，不要隨便刻板」⇒ 拿掉。**不准再加任何罐頭句**（測試守著：留空時圖上那一格沒有字）。
LEAK_WINDOW = 8
#: 白邊下緣的 QR 靜區**不塗色**（保留相框的紙紋）；但要先確認那一塊夠亮，
#: 不夠亮（例如佔位相框的窗緣陰影）才塗紙色。
QR_QUIET_MIN_L = 200

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
    if _sha256_file(PLATE_PATH) != PLATE_SHA256:
        return False, f"plate_mismatch：{PLATE_PATH.name} 不在或 sha256 對不上"
    return True, "ok"


# ---------------------------------------------------------------------------
# 那一行字
# ---------------------------------------------------------------------------

_MD_NOISE = re.compile(r"[#*_`>~|\[\]]")
_QUOTES = "「」『』“”\"'‘’《》〈〉"
_QUOTE_PAIRS = {"「": "」", "『": "』", "“": "”", "‘": "’", "《": "》", "〈": "〉",
                '"': '"', "'": "'"}


def clean_caption(decision: Any) -> str:
    """PLAN.md 的第一行 → 一句乾淨的短句（去 markdown、引號、多餘空白、句尾句號）。"""
    s = str(decision or "")
    s = s.splitlines()[0] if s.strip() else ""
    s = " ".join(_MD_NOISE.sub("", s).split())
    prev = None
    while s != prev:                     # 「寫一封信」。 ⇒ 句號與成對的外引號交替剝，剝到不動為止
        prev = s
        s = s.strip().rstrip("。．.！!；;，,、：:").rstrip()
        if len(s) >= 2 and _QUOTE_PAIRS.get(s[0]) == s[-1] and s[0] not in s[1:-1]:
            s = s[1:-1]                  # 整句被一對引號包住才剝（「週末登山清單」在句中不動）
        elif s and s[0] in _QUOTES and not any(c in s[1:] for c in _QUOTES):
            s = s[1:]                    # 落單的開引號
        elif s and s[-1] in _QUOTES and not any(c in s[:-1] for c in _QUOTES):
            s = s[:-1]                   # 落單的閉引號
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


#: 不放在行首的字（句讀、閉引號）與不放在行尾的字（開引號）。
_NO_LINE_START = "，。、；：！？）」』》〉,.;:!?)…"
_NO_LINE_END = "（「『《〈("

#: 換行不切詞（2026-09-26）：優先斷在這些字之後——標點（斷完自然是下一個詞的開頭）、
#: 閉引號（一段話說完了）、或「的／在／和／與」這類常見連接字之後（後面接的通常是新詞的
#: 開頭，不會把「如果」「因為」這種兩字常見詞從中間切開）。這是簡單規則，不是斷詞器；
#: 找不到這種斷點時 `wrap_caption` 會退回原本只看平衡、不管字義的那條路。
_PREFER_BREAK_AFTER = "，。、；：！？」』）》〉,.;:!?)" + "的在和與"


def _quote_depth(text: str) -> list[int]:
    """每個字元位置前面還有幾層沒關的引號（`「」『』（）《》`）。"""
    pairs = {"「": "」", "『": "』", "（": "）", "《": "》", "(": ")"}
    closers = set(pairs.values())
    out, depth = [], 0
    for ch in text:
        out.append(depth)
        if ch in pairs:
            depth += 1
        elif ch in closers and depth:
            depth -= 1
    out.append(depth)
    return out


def wrap_caption(font: Any, text: str, max_w: int,
                 max_lines: int = CAPTION_LINES) -> tuple[list[str], bool]:
    """那一句 → 最多 `max_lines` 行（逐字斷行，中文不靠空白）。放不下的尾巴截掉補「…」。

    一行放得下就一行。要兩行時**先找「換行不切詞」的斷點**（2026-09-26）：斷在標點之後、
    或斷在「的／在／和／與」這類常見連接字之後、且不在引號裡（`_PREFER_BREAK_AFTER`），
    這幾種位置後面接的多半是下一個詞的開頭，不會把「如果」「因為」這種兩字常見詞從中間切開。
    這一層裡一樣**找最平衡的斷點**（兩行寬度差最小）。**找不到**符合這一層的斷點，才退回
    原本「不管切在哪個字中間、只看最平衡」那一條路（歷史行為不變）。
    其餘既有規則照舊：句讀／閉引號不放行首、開引號不放行尾、盡量不斷在引號裡面
    （斷在引號裡加一大筆成本，真的沒別處可斷才用）。
    兩行都放不下 ⇒ 第一行塞滿、第二行截斷補「…」。回（行, 有沒有截）。
    """
    if font.getlength(text) <= max_w or max_lines <= 1:
        last, cut = fit_text(font, text, max_w)
        return [last], cut
    depth = _quote_depth(text)

    def scan(require_word_boundary: bool) -> tuple[float, int] | None:
        best: tuple[float, int] | None = None
        for n in range(1, len(text)):
            a, b = text[:n], text[n:].lstrip()
            if not b or b[0] in _NO_LINE_START or a[-1] in _NO_LINE_END:
                continue
            if require_word_boundary and (depth[n] or a[-1] not in _PREFER_BREAK_AFTER):
                continue
            wa, wb = font.getlength(a), font.getlength(b)
            if wa > max_w or wb > max_w:
                continue
            cost = abs(wa - wb) + (max_w if depth[n] else 0)
            if best is None or cost < best[0]:
                best = (cost, n)
        return best

    best = scan(True) or scan(False)
    if best is not None:
        n = best[1]
        return [text[:n], text[n:].lstrip()], False
    # 兩行放不下：第一行貪心塞滿（守避頭尾），剩下的交給 fit_text 截斷
    n = 1
    while n < len(text) and font.getlength(text[:n + 1]) <= max_w:
        n += 1
    while 1 < n < len(text) and (text[n] in _NO_LINE_START or text[n - 1] in _NO_LINE_END):
        n -= 1
    last, cut = fit_text(font, text[n:].lstrip(), max_w)
    return [text[:n], last], cut


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


def figure_for(cast_id: str, poses_dir: pathlib.Path | None = None
               ) -> tuple[pathlib.Path, str]:
    """這一位分身在相片裡用哪一張圖。回（路徑, "pose" | "cast40"）。

    **只認自己的檔名**：`<poses>/<cast_id>_show.png`；沒有 ⇒ `cast40/<cast_id>.png`。
    不找最像的、不找同形狀的、不拿別位頂替——那是別人的臉（誠實邊界 5）。
    姿勢檔若是指向**別的檔名**的連結（例如 c05_show.png → c02_show.png）也不認。
    """
    if not re.fullmatch(r"c\d{2}", cast_id or ""):
        raise PolaroidError(f"cast_id 不合法：{cast_id!r}")
    d = poses_dir
    if d is None:
        env = os.environ.get(POSES_ENV, "").strip()
        d = pathlib.Path(env) if env else DEFAULT_POSES_DIR
    want = f"{cast_id}{POSE_SUFFIX}.png"
    p = d / want
    if p.is_file() and p.resolve().name == want:
        return p, "pose"
    q = CAST_DIR / f"{cast_id}.png"
    if q.is_file():
        return q, "cast40"
    raise PolaroidError(f"cast_id 的精靈圖不在：{cast_id!r}")


def _drop_specks(spr: Any, thresh: int = 32, keep_frac: float = 0.02) -> Any:
    """去背圖邊上脫離本體的碎屑（cast40 裡 c01／c02／c20／c21／c34 各有一小塊，
    貼到深色舞台上會變成一條白線）。alpha 連通塊面積 < 最大塊的 `keep_frac` ⇒ 清掉。"""
    a = spr.getchannel("A")
    w, h = a.size
    px = a.load()
    seen = bytearray(w * h)
    blobs: list[list[int]] = []
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if seen[i] or px[x, y] <= thresh:
                continue
            seen[i] = 1
            stack, members = [i], []
            while stack:
                j = stack.pop()
                members.append(j)
                jx, jy = j % w, j // w
                for nx, ny in ((jx + 1, jy), (jx - 1, jy), (jx, jy + 1), (jx, jy - 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        k = ny * w + nx
                        if not seen[k] and px[nx, ny] > thresh:
                            seen[k] = 1
                            stack.append(k)
            blobs.append(members)
    if len(blobs) <= 1:
        return spr
    big = max(len(b) for b in blobs)
    out = spr.copy()
    oa = out.getchannel("A")
    opx = oa.load()
    for b in blobs:
        if len(b) < big * keep_frac:
            for j in b:
                opx[j % w, j // w] = 0
    out.putalpha(oa)
    return out


def _grade(spr: Any) -> Any:
    """精靈圖是中性白光下拍的；舞台是頂上一盞暖燈。乘一層「上亮下暗、偏暖」的漸層，
    讓他站進那一束光裡而不是貼在上面。只動 RGB，alpha 原樣。"""
    from PIL import Image, ImageChops
    w, h = spr.size
    col = Image.new("RGB", (1, h))
    px = col.load()
    for y in range(h):
        k = 1.0 - 0.20 * (y / max(1, h - 1))           # 頭頂 1.00 → 腳底 0.80
        px[0, y] = (int(255 * k), int(255 * k * 0.95), int(255 * k * 0.85))
    rgb = ImageChops.multiply(spr.convert("RGB"), col.resize((w, h)))
    rgb.putalpha(spr.getchannel("A"))
    return rgb


def render_scene(cast_id: str, size: tuple[int, int], *,
                 poses_dir: pathlib.Path | None = None) -> tuple[Any, dict[str, Any]]:
    """相片窗裡那一格：**他的分身站在黏土世界的舞台上**（有姿勢圖＝舉著寫好的紙）。

    背景＝`s00` 空舞台板，從頂光中心欄置中裁成相片窗的比例；分身腳踩在光圈裡，
    底下一圈柔和的接觸陰影。回（RGB 圖, 用了哪些素材）。
    """
    from PIL import Image, ImageDraw, ImageFilter
    ww, wh = size
    plate = Image.open(PLATE_PATH).convert("RGB")
    pw, ph = plate.size
    ch = ph
    cw = int(round(ph * ww / wh))
    if cw > pw:                                         # 相片窗比板還寬：改裁高度
        cw, ch = pw, int(round(pw * wh / ww))
    x0 = max(0, min(pw - cw, PLATE_SPOT_X - cw // 2))
    y0 = ph - ch
    img = plate.crop((x0, y0, x0 + cw, y0 + ch)).resize(size, Image.LANCZOS).convert("RGBA")

    fig_p, kind = figure_for(cast_id, poses_dir)
    spr = _drop_specks(Image.open(fig_p).convert("RGBA"))
    bbox = spr.getchannel("A").point(lambda v: 255 if v > 32 else 0).getbbox()
    spr = spr.crop(bbox or (0, 0, spr.width, spr.height))
    # 去背圖邊上有一圈淺色毛邊；alpha 往內收 1 px 再縮放。
    spr.putalpha(spr.getchannel("A").filter(ImageFilter.MinFilter(3)))
    scale = min(wh * FIG_H_FRAC / spr.height, ww * FIG_W_MAX_FRAC / spr.width)
    spr = spr.resize((max(1, int(spr.width * scale)), max(1, int(spr.height * scale))),
                     Image.LANCZOS)
    spr = _grade(spr)
    cx, feet = ww // 2, int(wh * FEET_Y_FRAC)
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse(
        [cx - spr.width * 0.55, feet - wh * 0.02, cx + spr.width * 0.55, feet + wh * 0.018],
        fill=(20, 10, 0, 150))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(max(2, wh * 0.016))))
    img.alpha_composite(spr, (cx - spr.width // 2, feet - spr.height))
    return img.convert("RGB"), {"figure": kind, "figure_file": fig_p.name,
                                "plate": PLATE_PATH.stem}


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


def _frame_fit(opaque: tuple[int, int, int, int], win_native: tuple[int, int, int, int],
               canvas: tuple[int, int] = CANVAS) -> dict[str, Any]:
    """素材相框 → 卡面的幾何。**按寬度縮放，下緣白邊往下延長**（不壓扁、不裁掉紙）。

    * 先裁到不透明外框（素材外圍有幾 px 透明邊）；
    * 寬度縮到卡面寬 ⇒ 高度 `h0`；比卡面高就不收（退回佔位相框）；
    * 缺的 `extra` 高度由下緣白邊的**中段**（白邊上下各留 1/4 不動：窗緣陰影與圓角）
      上下鏡射接續補滿——紙紋是細雜訊，鏡射接縫看不出來，也不會把紙紋拉長變形。
    """
    ox0, oy0, ox1, oy1 = opaque
    s = canvas[0] / (ox1 - ox0)
    h0 = int(round((oy1 - oy0) * s))
    if h0 > canvas[1]:
        raise ValueError(f"相框按寬度縮放後高 {h0} px，比卡面 {canvas[1]} 高")
    win = (int(round((win_native[0] - ox0) * s)), int(round((win_native[1] - oy0) * s)),
           int(round((win_native[2] - ox0) * s)), int(round((win_native[3] - oy0) * s)))
    band = h0 - win[3]
    if band <= 8:
        raise ValueError("相框下緣沒有白邊可以延長")
    cut = (win[3] + band // 4, h0 - band // 4)
    return {"crop": opaque, "scale": s, "h0": h0, "window": win,
            "extend_px": canvas[1] - h0, "cut": cut,
            "underlay_px": max(1, int(round(FRAME_UNDERLAY_PX * s)))}


def _build_frame(png: pathlib.Path, fit: dict[str, Any], canvas: tuple[int, int] = CANVAS):
    """照 `_frame_fit` 的幾何做出卡面大小的相框（RGBA）＋紙色（白邊中段的中位數）。"""
    from PIL import Image, ImageStat
    w = canvas[0]
    im = Image.open(png).convert("RGBA").crop(fit["crop"]).resize((w, fit["h0"]), Image.LANCZOS)
    c0, c1 = fit["cut"]
    mid = im.crop((0, c0, w, c1))
    paper = tuple(int(v) for v in ImageStat.Stat(
        mid.convert("RGB").crop((w // 8, 0, w - w // 8, mid.height))).median)
    if fit["extend_px"] <= 0:
        return im, paper
    need = mid.height + fit["extend_px"]
    strip = Image.new("RGBA", (w, need))
    y, flip = 0, False
    while y < need:
        strip.paste(mid.transpose(Image.FLIP_TOP_BOTTOM) if flip else mid, (0, y))
        y += mid.height
        flip = not flip
    out = Image.new("RGBA", canvas, (0, 0, 0, 0))
    out.paste(im.crop((0, 0, w, c0)), (0, 0))
    out.paste(strip, (0, c0))
    out.paste(im.crop((0, c1, w, fit["h0"])), (0, c0 + need))
    return out, paper


def layout_for(frame_dir: pathlib.Path | None = None, *,
               module: int = QR_MODULE_PX) -> dict[str, Any]:
    """用哪一個相框、版面長怎樣。**不合格的相框退回佔位相框，並且講為什麼。**

    素材 json 至少要有 `window`（或素材線的 `window_px`；`[x0,y0,x1,y1]` 或 `{x,y,w,h}`，
    **素材原生座標**）。相框一律照 `_frame_fit` 放進卡面 `CANVAS`（不是照素材原尺寸輸出：
    素材比例 0.89 的下緣白邊放不下 8 px 模組的 QR＋字，理由見裁決檔）。可選 `caption`、
    `footer`、`qr`（**卡面座標**；`qr` 是碼本身的外框，模組大小＝寬度 ÷ 模組數）。
    缺的就用 `_derive_layout` 從相片窗推。放不下（字框太小、靜區出紙、互相重疊、
    模組太小、相框縮放後比卡面高）⇒ 退回佔位相框，`frame_note` 寫理由。
    """
    base = {**_derive_layout(CANVAS, WINDOW, module), "frame_png": None, "frame_fit": None,
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
            size = im.size
            alpha = im.convert("RGBA").getchannel("A")
        opaque = alpha.point(lambda v: 255 if v >= 128 else 0).getbbox() or (0, 0, *size)
        win_n = _box(spec.get("window")) or _box(spec.get("window_px"))
        if win_n is None:
            raise ValueError("json 沒有合法的 window／window_px")
        if not _inside(win_n, opaque):
            raise ValueError("window 不在相框的紙裡")
        fit = _frame_fit(opaque, win_n, CANVAS)
        lay = _derive_layout(CANVAS, fit["window"], module)
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
    return {**lay, "frame_png": png, "frame_fit": fit,
            "frame": "file:" + (_sha256_file(png) or "?")[:12], "frame_note": None}


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
            poses_dir: pathlib.Path | None = None,
            qr_module_px: int = QR_MODULE_PX, _sweep_only: bool = False
            ) -> tuple[bytes, dict[str, Any]]:
    """做一張拍立得。回（PNG bytes, meta）。meta 只有版面與旗標，**不含那句話本身**。

    `decision` ＝ 分身自己寫的 PLAN.md 第一行（`twinagent.parse_plan`）。這裡只清掉
    markdown／引號、畫不出的字、放不下的尾巴；**不改寫、不補字**。清完是空的、或逐字抄了
    觀眾原文 ⇒ 那一行留空（`caption_blank`），拍立得照發。
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
        # 素材相框：紙色墊底 → 相片從窗格底下墊進去（四邊多墊一點）→ 相框蓋上去
        fit = lay["frame_fit"]
        frame, paper = _build_frame(lay["frame_png"], fit, canvas)
        u = fit["underlay_px"]
        scene, fig = render_scene(cast_id, (win[2] - win[0] + 2 * u, win[3] - win[1] + 2 * u),
                                  poses_dir=poses_dir)
        img = Image.new("RGBA", canvas, paper + (255,))
        img.paste(scene, (win[0] - u, win[1] - u))
        img.alpha_composite(frame)
        img = img.convert("RGB")
    else:
        paper = PAPER
        img = _placeholder_frame(canvas, win)
        scene, fig = render_scene(cast_id, (win[2] - win[0], win[3] - win[1]),
                                  poses_dir=poses_dir)
        img.paste(scene, (win[0], win[1]))
    d = ImageDraw.Draw(img)

    # ── 那一行字：分身自己寫的，不補字 ──
    f_cap = _font(CAPTION_PX)
    caption = clean_caption(decision)
    redacted = False
    if caption and caption_leaks_original(caption, originals):
        caption, redacted = "", True             # 留空。不換成任何人寫的句子。
    caption, dropped = _drop_missing(f_cap, caption)
    truncated = False
    cap_drawn = None
    lines: list[str] = []
    if caption:
        lines, truncated = wrap_caption(f_cap, caption, cap_box[2] - cap_box[0])
        caption = "".join(lines)
        cx = (cap_box[0] + cap_box[2]) // 2
        y = (cap_box[1] + cap_box[3]) // 2 - (len(lines) - 1) * CAPTION_LINE_H // 2
        boxes = []
        for ln in lines:
            d.text((cx, y), ln, font=f_cap, fill=INK, anchor="mm")
            boxes.append(d.textbbox((cx, y), ln, font=f_cap, anchor="mm"))
            y += CAPTION_LINE_H
        cap_drawn = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                     max(b[2] for b in boxes), max(b[3] for b in boxes))

    # ── 小字 ──
    f_foot = _font(FOOTER_PX)
    footer = f"{date_str} · {EXHIBIT_NAME} · 收據 {receipt_short}"
    footer, _ = fit_text(f_foot, footer, foot_box[2] - foot_box[0])
    fy = (foot_box[1] + foot_box[3]) // 2
    d.text((foot_box[0], fy), footer, font=f_foot, fill=INK_SOFT, anchor="lm")
    foot_drawn = d.textbbox((foot_box[0], fy), footer, font=f_foot, anchor="lm")

    # ── QR（官網本身）──
    qb, qq, mod = g["box"], g["quiet_box"], g["module"]
    # 靜區保留相框的紙紋（塗一塊平的色會在紙上浮出一張「貼紙」）；
    # 但先量：那一塊有任何一點不夠亮（< QR_QUIET_MIN_L）就塗紙色，解碼器要的是亮的靜區。
    quiet_min_l = min(img.crop(qq).convert("L").getextrema())
    quiet_painted = quiet_min_l < QR_QUIET_MIN_L
    if quiet_painted:
        d.rectangle(qq, fill=paper)
    for r, row in enumerate(g["matrix"]):
        for c, v in enumerate(row):
            if v:
                x, y = qb[0] + c * mod, qb[1] + r * mod
                d.rectangle([x, y, x + mod - 1, y + mod - 1], fill=QR_DARK)

    full = (0, 0, canvas[0], canvas[1])
    problems = []
    if cap_drawn is not None and not _inside(cap_drawn, cap_box):
        problems.append("caption 出框")
    if not _inside(foot_drawn, foot_box):
        problems.append("footer 出框")
    if not _inside(qq, full):
        problems.append("QR 靜區出紙")
    if (cap_drawn is not None and _overlap(cap_drawn, qq)) or _overlap(foot_drawn, qq):
        problems.append("字壓到 QR 靜區")
    if problems:
        raise PolaroidError("版面放不下：" + "；".join(problems))

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    png = buf.getvalue()
    fit = lay.get("frame_fit")
    meta = {
        "v": 2, "size": list(canvas), "cast_id": cast_id,
        "figure": fig["figure"], "figure_file": fig["figure_file"], "plate": fig["plate"],
        "window": list(win),
        "caption_box": list(cap_box),
        "caption_drawn": list(cap_drawn) if cap_drawn is not None else None,
        "caption_blank": not caption,
        "caption_truncated": truncated, "caption_redacted": redacted,
        "caption_chars": len(caption), "caption_lines": len(lines),
        "dropped_glyphs": dropped,
        "footer_box": list(foot_box), "footer_drawn": list(foot_drawn),
        "qr_text": SITE_URL, "qr_version": (g["n"] - 17) // 4, "qr_modules": g["n"],
        "qr_module_px": mod, "qr_box": list(qb), "qr_quiet_box": list(qq),
        "qr_quiet_min_l": quiet_min_l, "qr_quiet_painted": quiet_painted,
        "frame": lay["frame"], "frame_note": lay["frame_note"],
        "frame_fit": ({"scale": round(fit["scale"], 4), "extend_px": fit["extend_px"]}
                      if fit else None),
        "bytes_n": len(png),
    }
    return png, meta


# ---------------------------------------------------------------------------
# 範例
# ---------------------------------------------------------------------------
# ⚠ 2026-09-26 以前這裡有一組**人寫死的分身決定**（`SAMPLES`，「寫一封謝卡給國小導師」…）。
#   人類：「那個字是不是應該要讓他是 AI agent 生成的，不要隨便刻板」⇒ 拿掉。
#   範例改由 `polaroid_realrun.py`（合成特質 → 分身真跑 → 它自己寫的 PLAN.md 第一行）產生，
#   每一張都記 engine／model／run_id／收據鏈頭。**不要在這裡再放任何寫死的決定句。**


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
    if a.cmd == "parity-table":
        return _cli_parity(pathlib.Path(a.out),
                           pathlib.Path(a.manifest) if a.manifest else None, a.tie)
    return 2


if __name__ == "__main__":
    sys.exit(main())
