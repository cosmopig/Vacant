"""`ops/exhibit/twin/assets/polaroid_v2/` 真素材的可執行判準。

## 這一支與別支的分工

`tests/test_polaroid_layers.py` 證明的是**挑款與查核的機制**（manifest 與 PNG 全是
測試內現造的假物，零真素材）。`tests/test_twin_polaroid.py` 證明的是**合成會照原樣出圖**。
中間那一塊沒有被驗過：**真的那 200 幾張素材本身合不合格**。這一支補那個洞——
它不造假物，只讀 `assets/polaroid_v2/` 底下的真檔。

⚠ `polaroid_layers.py` 的誠實邊界第 4 條寫著「**這支不驗素材長相**，只驗 sha256」。
所以這一支是那條邊界的對面：**驗長相，不驗機制**。兩支合起來才是完整的
「素材可被挑、素材也可被驗」。

## 驗什麼（七項，逐項對應到素材會壞在哪裡）

1. **manifest 讀得到**：`load_manifest()` 回 `None` 的時候 `pick_layers()` 會整層退回
   單一相框版——**不是報錯，是靜靜地變普通**。所以這一項必須是綠的。
2. **張數下限**：40 個人不能長得跟排印機印的一樣。某個地點只有 1 張背景板，
   那 5 個人就共用同一張——**「多樣」是數量性質，少一張就是少一種**。所以每一層
   都有下界，不是「有就算了」。
3. **每一筆 entry 都解得出來**：`resolve_file()` 現算 sha256，對不上就回 `None`。
   這一項等於**素材與 manifest 之間沒有漂移**。
4. **背景板 1024x1024**：`polaroid.py` 依 1024 量窗，尺寸不對會被裁掉或留白。
5. **相框的相片窗與下方白邊**：窗內必須**全透明**（不透明就會蓋掉真人照），
   下方白邊必須**不透明且夠亮**（半透明會透出背景板，字會消失在板上）。
   829x930 是與 `polaroid_frame.json` 對齊後的尺寸。
6. **每個相框 json 的 `window_px`** 與 png 上的窗一致——**量窗程式讀的是 json，
   不是 png**；兩者不同步就是量錯窗，錯窗＝照片被裁掉。
7. **貼紙與道具的 alpha 品質**：RGBA、最長邊 <=400（大了會在成品上糊成方塊）、
   不透明面積占比夠（太空的貼紙貼上去像一張空白）、**邊緣不能有綠邊**（素材是綠幕
   去背來的，邊緣沒去乾淨就會有一圈螢光綠）、**不能有殘塊**（去背時把一張圖切成
   兩塊，貼上去會多出一坨不該在那裡的東西）。

⚠ **門檻不放寬。** 素材真的不合格就是不合格，這一支要把它原樣喊出來，不是讓它綠。
每一個測項都帶檔名，失敗訊息指得出是哪一張。
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import polaroid_layers as L  # noqa: E402

PIL = pytest.importorskip("PIL", reason="沒有 Pillow ⇒ 真素材**沒有被驗過**（不是驗過了）")
from PIL import Image  # noqa: E402

ASSET_DIR = ROOT / "ops" / "exhibit" / "twin" / "assets" / "polaroid_v2"

# ---------------------------------------------------------------------------
# 門檻（全部寫成常數，失敗訊息會把它印出來）
# ---------------------------------------------------------------------------

BG_SIZE = (1024, 1024)
FRAME_SIZE = (829, 930)
#: 相片窗：`polaroid.py` 量窗與相框 json 必須同意的同一組值。
WINDOW = {"x": 50, "y": 60, "w": 730, "h": 686}
#: 窗下白邊（相框 png 上，閉區間）。字印在這裡，所以它必須不透明且夠亮。
BOTTOM = (40, 786, 790, 907)
BOTTOM_MIN_LUMA = 150

MIN_BG_PER_PLACE = 3
MIN_FRAME_PER_ELEMENT = 3
MIN_MBTI_PER_TEMPERAMENT = 4
MIN_PROP_PER_KIND = 2

MAX_CUTOUT_SIDE = 400
MIN_OPAQUE_FRACTION = 0.15
MAX_GREEN_EDGE_FRACTION = 0.02
MIN_MAIN_BLOB_FRACTION = 0.97
MIN_BLOB_FRACTION = 0.015
#: 設計上就是分開幾件的素材（檔名）：雙魚（兩條魚）、鉛筆旁的削屑。
MULTI_PART_BY_DESIGN = {"sheet_zodiac_2_r1_5.png", "sheet_props_tile_pencil_3.png"}

#: 綠邊的判法（寫在這裡，失敗訊息才不會含糊）：半透明邊緣像素裡，
#: 綠色比紅藍都高出 60 以上、而且綠本身已經很亮的算「綠色過強」。
GREEN_OVER = 60
GREEN_FLOOR = 150
EDGE_ALPHA_HI = 235
OPAQUE_ALPHA = 200
BLOB_ALPHA = 128


# ---------------------------------------------------------------------------
# manifest 與 entry 索引
# ---------------------------------------------------------------------------

def _load_manifest_without_env() -> dict | None:
    """`monkeypatch.delenv(V2_ENV)` 後再 `load_manifest(d)`。

    `d` 明確給了，所以環境變數本來就輪不到它；`delenv` 是為了**不讓測試繼承別人
    設的 `VACANT_POLAROID_V2_DIR`**（展場那台機器上常常是 `off`）。
    """
    mp = pytest.MonkeyPatch()
    try:
        mp.delenv(L.V2_ENV, raising=False)
        return L.load_manifest(ASSET_DIR)
    finally:
        mp.undo()


MANIFEST = _load_manifest_without_env()


def _entries(section: object, key: object) -> list[dict]:
    """manifest 一層底下的清單（壞結構回空清單，不丟例外）。"""
    return L._entries(L._sect(section).get(key))


def _frame_entries() -> list[tuple[str, dict, str]]:
    """`(元素代碼, entry, 檔名)`。**表的東西不能用抽樣驗**，所以列全。"""
    out = []
    for el in ("fire", "earth", "air", "water", "neutral"):
        for e in _entries(MANIFEST.get("frames"), el):
            out.append((el, e, e.get("file", f"<{el} entry 無 file>")))
    return out


def _collect_sha() -> dict[str, str]:
    """manifest 裡每個檔名釘的 sha256（貼紙／道具／背景／相框）。"""
    out: dict[str, str] = {}

    def walk(v: object) -> None:
        if isinstance(v, dict):
            if isinstance(v.get("file"), str) and isinstance(v.get("sha256"), str):
                out[v["file"]] = v["sha256"]
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(MANIFEST)
    return out


_SHA_BY_FILE = _collect_sha()


def _cutout_entries() -> list[tuple[str, str]]:
    """`(層／類別, 檔名)`——所有需要驗 alpha 品質的貼紙與道具。"""
    stick = L._sect(MANIFEST.get("stickers"))
    out: list[tuple[str, str]] = []
    for t in ("NT", "NF", "SJ", "SP"):
        for e in _entries(stick.get("mbti"), t):
            out.append((f"stickers.mbti/{t}", e.get("file", f"<mbti {t} entry 無 file>")))
    for z in L.ZODIACS:
        e = L._entry(L._sect(stick.get("zodiac")).get(z))
        out.append((f"stickers.zodiac/{z}", (e or {}).get("file", f"<zodiac {z} 無 entry>")))
    for i, e in enumerate(_entries(stick, "blood")):
        out.append((f"stickers.blood/{i}", e.get("file", f"<blood {i} 無 file>")))
    props = L._sect(MANIFEST.get("props"))
    for k in L.PROP_KINDS:
        for e in _entries(props, k):
            out.append((f"props/{k}", e.get("file", f"<props {k} entry 無 file>")))
    return out


def _all_checked_entries() -> list[tuple[str, dict]]:
    """每一筆該被 `resolve_file()` 驗的 entry（含相框的 json 側車檔）。"""
    out: list[tuple[str, dict]] = []
    for code in L.PLACES:
        for e in _entries(MANIFEST.get("backgrounds"), code):
            out.append((f"backgrounds/{code}", e))
    for el, e, fname in _frame_entries():
        out.append((f"frames/{el}", e))
        out.append((f"frames/{el} json", {"file": e.get("json"), "sha256": e.get("json_sha256")}))
    for label, fname in _cutout_entries():
        out.append((label, {"file": fname, "sha256": _SHA_BY_FILE.get(fname)}))   # 要連 sha256 一起驗
    return out


#: 檔名 → 真實路徑（測試自己解一次，不走 manifest 的 sha 檢查路徑）
_PATHS: dict[str, pathlib.Path] = {}


def _real(rel: object) -> pathlib.Path:
    """manifest 記的相對路徑 → 磁碟上的檔（**不用** `resolve_file`：
    那一支是「有沒有解得出來」的判準，這裡要能對**壞掉的**素材也取得路徑）。"""
    name = str(rel)
    if name not in _PATHS:
        _PATHS[name] = ASSET_DIR.joinpath(*pathlib.PurePosixPath(name).parts)
    return _PATHS[name]


# ---------------------------------------------------------------------------
# 1. manifest 讀得到
# ---------------------------------------------------------------------------

def test_manifest_loads(monkeypatch):
    """`load_manifest()` 回 `None` 時加分層會靜靜退成單一相框版——所以必須是綠的。"""
    monkeypatch.delenv(L.V2_ENV, raising=False)
    mf = L.load_manifest(ASSET_DIR)
    assert mf is not None, (
        f"load_manifest({ASSET_DIR}) 回 None：manifest 讀不到／壞 JSON／version != 2。"
        f"回 None 的後果不是報錯，是加分層整層退回單一相框版。"
    )
    assert mf.get("version") == 2, f"manifest.version = {mf.get('version')!r}，應為 2"
    for sect in ("backgrounds", "frames", "stickers", "props"):
        assert sect in mf, f"manifest 缺 `{sect}` 這一層（present: {sorted(mf)}）"


# ---------------------------------------------------------------------------
# 2. 張數下限
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("place", L.PLACES)
def test_background_count_per_place(place):
    """一個地點只有 1 張背景板 ⇒ 那個地點的每個人都長一樣。"""
    n = len(_entries(MANIFEST.get("backgrounds"), place))
    assert n >= MIN_BG_PER_PLACE, (
        f"backgrounds/{place} 只有 {n} 張，門檻 {MIN_BG_PER_PLACE} 張。"
        f"少一張就是少一種樣子，而 P11 存在的理由就是不要每個人都一樣。"
    )


@pytest.mark.parametrize("element", ["fire", "earth", "air", "water", "neutral"])
def test_frame_count_per_element(element):
    """元素層（含 `neutral` 保底層）少一張，該元素的人就共用同一個框。"""
    n = len(_entries(MANIFEST.get("frames"), element))
    assert n >= MIN_FRAME_PER_ELEMENT, (
        f"frames/{element} 只有 {n} 張，門檻 {MIN_FRAME_PER_ELEMENT} 張"
        f"（`neutral` 是保底層，缺了元素層空掉時沒有退路）。"
    )


@pytest.mark.parametrize("temperament", ["NT", "NF", "SJ", "SP"])
def test_mbti_count_per_temperament(temperament):
    """`pick_layers()` 一個人會取 1–2 張 MBTI 貼紙，池子太小就會用同一張取兩次。"""
    n = len(_entries(L._sect(MANIFEST.get("stickers")).get("mbti"), temperament))
    assert n >= MIN_MBTI_PER_TEMPERAMENT, (
        f"stickers.mbti/{temperament} 只有 {n} 張，門檻 {MIN_MBTI_PER_TEMPERAMENT} 張"
        f"（`MAX_MBTI_STICKERS=2`，池子 < 4 就開始重複）。"
    )


def test_zodiac_covers_all_twelve_exactly():
    """十二星座是**表**，不是抽樣：不多不少全部要有，缺一個那個人的層就是空的。"""
    keys = L._sect(L._sect(MANIFEST.get("stickers")).get("zodiac"))
    got, want = set(keys), set(L.ZODIACS)
    assert got == want, (
        f"stickers.zodiac 的 key 與 ZODIACS 不一致："
        f"缺 {sorted(want - got)}、多 {sorted(got - want)}"
    )


def test_blood_stamps_eight_two_per_shape_red_and_blue():
    """血型印章：4 形狀 × 2 色 ＝ 8。少一格就是那個血型退回沒有印章。"""
    stamps = _entries(L._sect(MANIFEST.get("stickers")), "blood")
    assert len(stamps) == 8, f"stickers.blood 有 {len(stamps)} 筆，應為 8 筆（4 形狀 × 2 色）"

    shapes = Counter(e.get("shape") for e in stamps)
    for shape in L.BLOOD_SHAPE:
        assert shapes.get(shape) == 2, (
            f"shape={shape} 有 {shapes.get(shape, 0)} 個，應為 2 個"
            f"（現況 {dict(shapes)}）"
        )
    assert set(shapes) == set(L.BLOOD_SHAPE), f"出現了表外形狀：{sorted(set(shapes) - set(L.BLOOD_SHAPE))}"

    tones = Counter(e.get("tone") for e in stamps)
    assert set(tones) == {"red", "blue"}, f"tone 應為 red/blue，現況 {dict(tones)}"
    for tone in ("red", "blue"):
        assert tones.get(tone) == 4, f"tone={tone} 有 {tones.get(tone, 0)} 個，應為 4 個（每色四形狀）"


@pytest.mark.parametrize("kind", L.PROP_KINDS)
def test_prop_count_per_kind(kind):
    """地上道具十類每類至少 2 張，否則那類的道具每次都一樣。"""
    n = len(_entries(MANIFEST.get("props"), kind))
    assert n >= MIN_PROP_PER_KIND, f"props/{kind} 只有 {n} 張，門檻 {MIN_PROP_PER_KIND} 張"


# ---------------------------------------------------------------------------
# 3. 每一筆 entry 都解得出來（檔在，且 sha256 對）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "label,entry", _all_checked_entries(),
    ids=[f"{label}:{(e.get('file') or '?')}" for label, e in _all_checked_entries()],
)
def test_every_entry_resolves(label, entry):
    """`resolve_file()` 回 `None` = 檔不在或 sha256 對不上 = 那一層不能用。"""
    got = L.resolve_file(MANIFEST, entry)
    assert got is not None, (
        f"{label} 的 entry {entry.get('file')!r} 解不出來："
        f"檔不存在，或 sha256 對不上（素材與 manifest 之間有漂移）。"
        f"這一筆在那張卡上會被靜靜跳過。"
    )


# ---------------------------------------------------------------------------
# 4. 背景板尺寸
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "place,entry",
    [(p, e) for p in L.PLACES for e in _entries(MANIFEST.get("backgrounds"), p)],
    ids=[e.get("file", "?") for p in L.PLACES for e in _entries(MANIFEST.get("backgrounds"), p)],
)
def test_background_is_square_1024(place, entry):
    """`polaroid.py` 依 1024 量窗：尺寸不對就是被裁掉或留白。"""
    name = entry["file"]
    with Image.open(_real(name)) as im:
        assert im.size == BG_SIZE, f"{name}（backgrounds/{place}）尺寸 {im.size}，應為 {BG_SIZE}"


# ---------------------------------------------------------------------------
# 5. 相框 png：格式、相片窗全透明、窗下白邊不透明且夠亮
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "element,entry,name", _frame_entries(),
    ids=[name for _, _, name in _frame_entries()],
)
def test_frame_png_geometry_and_window(element, entry, name):
    """窗內全透明（不透明會蓋掉真人照）；窗下白邊不透明且夠亮（字要看得見）。"""
    with Image.open(_real(name)) as im0:
        im = im0.convert("RGBA")
    assert im.size == FRAME_SIZE, f"{name}（frames/{element}）尺寸 {im.size}，應為 {FRAME_SIZE}"

    alpha = im.getchannel("A")
    win = alpha.crop((WINDOW["x"], WINDOW["y"],
                      WINDOW["x"] + WINDOW["w"], WINDOW["y"] + WINDOW["h"]))
    n_win = WINDOW["w"] * WINDOW["h"]
    nonzero = n_win - win.histogram()[0]
    assert nonzero == 0, (
        f"{name}（frames/{element}）相片窗 {WINDOW} 內有 {nonzero}/{n_win} 像素 alpha != 0："
        f"窗不透明就會蓋掉真人照。"
    )

    bx0, by0, bx1, by1 = BOTTOM
    band_a = alpha.crop(BOTTOM)
    n_band = (bx1 - bx0) * (by1 - by0)
    n_opaque = band_a.histogram()[255]
    assert n_opaque == n_band, (
        f"{name}（frames/{element}）窗下白邊 x{bx0}..{bx1 - 1} y{by0}..{by1 - 1} 有 "
        f"{n_band - n_opaque}/{n_band} 像素 alpha != 255：下半截字會透出背景板。"
    )
    luma = im.crop(BOTTOM).convert("L").histogram()      # ITU-R 601-2: 0.299R+0.587G+0.114B
    present = [v for v, c in enumerate(luma) if c]
    min_luma = min(present)
    assert min_luma >= BOTTOM_MIN_LUMA, (
        f"{name}（frames/{element}）窗下白邊最暗處亮度 {min_luma} < {BOTTOM_MIN_LUMA}："
        f"白邊不夠白，字會糊在紙上。"
    )


# ---------------------------------------------------------------------------
# 6. 相框 json 的 window_px 與 png 的窗一致
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "element,entry,name", _frame_entries(),
    ids=[f"{e.get('json') or '?'}" for _, e, _ in _frame_entries()],
)
def test_frame_json_window_matches(element, entry, name):
    """量窗程式讀的是 **json**，不是 png。json 與 png 不同步＝量錯窗＝照片被裁掉。"""
    side = entry.get("json")
    assert isinstance(side, str) and side, f"相框 {name} 沒有 `json` 側車檔欄位"
    data = json.loads(_real(side).read_text(encoding="utf-8"))
    assert data.get("window_px") == WINDOW, (
        f"{side} 的 window_px = {data.get('window_px')!r}，應為 {WINDOW}"
        f"（對應的 png 是 {name}）"
    )


# ---------------------------------------------------------------------------
# 7. 貼紙與道具的 alpha 品質
# ---------------------------------------------------------------------------

def _rgba_stats(rel: str) -> dict:
    """一張切好的素材的實測值。全部用 bytes/histogram，不逐像素走 Python 物件。"""
    with Image.open(_real(rel)) as im0:
        src = im0
        mode = im0.mode
        size = im0.size
        rgba = im0.convert("RGBA")
    raw = rgba.tobytes()
    a = raw[3::4]
    g = raw[1::4]
    r = raw[0::4]
    b = raw[2::4]

    n = size[0] * size[1]
    hist_a = rgba.getchannel("A").histogram()
    opaque = sum(hist_a[OPAQUE_ALPHA + 1:])

    edge_total = sum(hist_a[1:EDGE_ALPHA_HI])              # 0 < alpha < 235
    green = 0
    for i in range(n):
        if 0 < a[i] < EDGE_ALPHA_HI and g[i] - (r[i] if r[i] > b[i] else b[i]) > GREEN_OVER \
                and g[i] > GREEN_FLOOR:
            green += 1

    return {
        "mode": mode,
        "size": size,
        "opaque_fraction": opaque / n if n else 0.0,
        "green_fraction": (green / edge_total) if edge_total else 0.0,
        "main_blob_fraction": _main_blob_fraction(rgba, size),
        "edge_pixels": edge_total,
    }


#: 最近一次 `_main_blob_fraction` 量到的各塊面積占比（給「沒有小殘塊」那條用）。
_LAST_AREAS: list[float] = []


def _main_blob_fraction(rgba: Image.Image, size: tuple[int, int]) -> float:
    """`alpha > 128` 的 4 連通塊裡，最大那一塊佔全部不透明面積的比率。

    自己寫 BFS（**不新增任何依賴**）：`alpha.point` 出 0/255 的 L 影像，
    `tobytes()` 之後以索引做 4 連通，避免 tuple 的雜湊成本。
    """
    w, h = size
    mask = rgba.getchannel("A").point(lambda v: 255 if v > BLOB_ALPHA else 0).tobytes()
    total = mask.count(255)
    if not total:
        return 0.0
    buf = bytearray(mask)
    best = 0
    areas: list[int] = []
    last_row = (h - 1) * w
    for seed in range(w * h):
        if not buf[seed]:
            continue
        buf[seed] = 0
        stack = [seed]
        area = 0
        while stack:
            i = stack.pop()
            area += 1
            x = i % w
            if x and buf[i - 1]:
                buf[i - 1] = 0
                stack.append(i - 1)
            if x < w - 1 and buf[i + 1]:
                buf[i + 1] = 0
                stack.append(i + 1)
            if i >= w and buf[i - w]:
                buf[i - w] = 0
                stack.append(i - w)
            if i < last_row and buf[i + w]:
                buf[i + w] = 0
                stack.append(i + w)
        if area > best:
            best = area
        areas.append(area)
    _LAST_AREAS[:] = [a / total for a in areas]
    return best / total


def test_cutout_entries_are_well_formed():
    """先確認切檔集合抓得到東西——沒有素材時下面那些檢查會「全部通過」而什麼都沒驗。"""
    entries = _cutout_entries()
    assert entries, "stickers/props 一筆都抓不到：下面那些 alpha 檢查會空跑而變綠"


@pytest.mark.parametrize(
    "label,rel", _cutout_entries(),
    ids=[f"{label}:{rel}" for label, rel in _cutout_entries()],
)
def test_cutout_is_rgba_and_small_enough(label, rel):
    """RGBA（有 alpha 才貼得上去）且最長邊 <=400（大了在成品上糊成方塊）。"""
    with Image.open(_real(rel)) as im:
        mode, size = im.mode, im.size
    assert mode == "RGBA", f"{rel}（{label}）mode={mode}，應為 RGBA（沒有 alpha 就貼不上底）"
    assert max(size) <= MAX_CUTOUT_SIDE, (
        f"{rel}（{label}）尺寸 {size}，最長邊 {max(size)} > {MAX_CUTOUT_SIDE}"
    )


@pytest.mark.parametrize(
    "label,rel", _cutout_entries(),
    ids=[f"{label}:{rel}" for label, rel in _cutout_entries()],
)
def test_cutout_has_enough_opaque_area(label, rel):
    """`alpha>200` 的像素要佔夠多：太空的貼紙貼上去就是一片空白。"""
    s = _rgba_stats(rel)
    assert s["opaque_fraction"] >= MIN_OPAQUE_FRACTION, (
        f"{rel}（{label}）alpha>200 的像素只佔 {s['opaque_fraction']:.1%}，"
        f"門檻 {MIN_OPAQUE_FRACTION:.0%}：這張貼上去會看起來是空的。"
    )


@pytest.mark.parametrize(
    "label,rel", _cutout_entries(),
    ids=[f"{label}:{rel}" for label, rel in _cutout_entries()],
)
def test_cutout_edge_has_no_green_fringe(label, rel):
    """素材是綠幕去背來的：邊緣沒去乾淨會留一圈螢光綠。

    比例的分母是**半透明邊緣像素**（`0<alpha<235`），不是整張圖——
    否則一張大圖會靠中間的實心把邊緣稀釋掉。
    """
    s = _rgba_stats(rel)
    assert s["edge_pixels"] > 0, f"{rel}（{label}）沒有半透明邊緣像素，這項檢查量不到東西"
    assert s["green_fraction"] < MAX_GREEN_EDGE_FRACTION, (
        f"{rel}（{label}）邊緣半透明像素裡有 {s['green_fraction']:.2%} 綠色過強"
        f"（g-max(r,b)>{GREEN_OVER} 且 g>{GREEN_FLOOR}），門檻 {MAX_GREEN_EDGE_FRACTION:.0%}"
        f"（共 {s['edge_pixels']} 個邊緣像素）：這是綠幕沒去乾淨。"
    )


@pytest.mark.parametrize(
    "label,rel", _cutout_entries(),
    ids=[f"{label}:{rel}" for label, rel in _cutout_entries()],
)
def test_cutout_has_no_orphan_blobs(label, rel):
    """去背不能把一張圖切出殘塊：貼上去會多出一坨不該在那裡的東西。

    兩層：(1) **任何一塊都不准小於不透明面積的 1.5%**（殘塊／碎屑）；(2) 除了「設計上就是分開的幾件」
    （雙魚＝兩條魚、鉛筆旁的削屑），最大那一塊要占 97% 以上。
    """
    s = _rgba_stats(rel)
    smalls = [a for a in _LAST_AREAS if a < MIN_BLOB_FRACTION]
    assert not smalls, (
        f"{rel}（{label}）有 {len(smalls)} 個小於 {MIN_BLOB_FRACTION:.1%} 的殘塊（最大 {max(smalls):.2%}）：去背沒清乾淨。"
    )
    if rel.rsplit("/", 1)[-1] in MULTI_PART_BY_DESIGN:
        return
    assert s["main_blob_fraction"] >= MIN_MAIN_BLOB_FRACTION, (
        f"{rel}（{label}）alpha>{BLOB_ALPHA} 的最大 4 連通塊只佔全部不透明面積的 "
        f"{s['main_blob_fraction']:.1%}，門檻 {MIN_MAIN_BLOB_FRACTION:.0%}：有殘塊／去背切壞了。"
    )
