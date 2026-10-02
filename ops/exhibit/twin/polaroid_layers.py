#!/usr/bin/env python3
"""twin/polaroid_layers — P11 拼貼層的**挑款與查核**，一格都不畫。

## 這支承重什麼

拍立得 P11 要的只有一句：**40 個人不能長得跟排印機印的一樣**。版面、字、QR、光源
全站著不動，換的是相片窗底下那幾層——背景板、相框、貼紙（MBTI temperament／
星座／血型印章）、地上道具。而「依這個人的資料」這個決定，就是這一支做的。
它承重的是兩件事，兩件都跟畫圖無關：

1. **決定性**：同一個 `sub_id` ＋ 同一份 manifest ⇒ 同一組素材。挑款全部走
   `seed()`（sha256 前 12 碼轉整數），**不碰 `random`、不碰時鐘、不碰 manifest
   以外的任何狀態**，也不在這裡讀任何檔案。同一張卡重跑一次，長得一樣。
   ⚠ 這是**必備**而不是潔癖：拍立得會被重算（撤回重發、補印、跨機重算），
   每次不一樣就是「同一個人的卡會長得不同」，觀眾一眼看得出來。
2. **查核**：`manifest.json` 每個 entry 都釘 sha256。`resolve_file()` **每次現算**
   （快取只認 `(path, mtime, size)`，內容換掉就重算），對不上或檔不在就回 `None`——
   那一層退回單一相框版，理由記進 meta 的 `fallbacks`。素材被換掉 ⇒ 畫面**不會**跟著
   變，會變成「照舊出圖、但那層掉了，而且是可查的掉」。

⚠ **這一支沒有 Pillow 依賴、只用 stdlib**，因為挑款與查核必須在沒有影像庫的機器上
也成立（CI、素材還沒生完的那台、只想驗 sha256 的稽核機）。合成在 `polaroid.py`，
兩件事分開才能各自驗、各自壞。

## 誠實邊界（改碼時保留）

1. **確定性不是隨機性。** 同一個 `sub_id` 永遠挑同一組，所以**看得見的資訊就是可推回
   的鍵**。因此 `pick_layers()["spec"]`（唯一會印進 meta 的部分）**只放檔名與
   place/element 代碼**：不放 `sub_id`、不放 MBTI 四字母、不放星座／血型原值。
   ⚠ 檔名由 manifest 決定——素材若命名成 `zodiac_牡羊.png`，那個「牡羊」是 manifest
   洩漏的，不是這裡的。要不要收緊由 manifest 那條線負責。
2. **manifest 壞掉一律回 `None`／空層，不在這裡猜。** 缺檔、壞 JSON、
   `version != 2`、sha 對不上、檔被刪——全部交給呼叫端決定退回哪一層。
   加分層不准拖垮拍立得（`polaroid.py::_variety_plan` 的 `except` 就是這條的保險）。
3. **`seed()` 只取 sha256 前 12 碼（48 bits）**，夠分層挑款；它是**挑款碼不是密碼**，
   不要拿來證明任何事。
4. **這支不驗素材長相**（畫風、對不對、糊不糊），只驗 sha256。素材對不對是
   `polaroid.py` 量窗與 `tests/test_twin_polaroid.py` 的事。
5. `hints_from_steps()` 只是**從步驟裡數出地點與物件類別的多數決**——它讀的是
   分身自己寫下的操作紀錄，不讀觀眾原文。讀不出來就回 `{"place": "drop",
   "kind": None}`（`drop` ＝ 預設台），**不猜**。
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import pathlib
from typing import Any, Iterable, Mapping

#: 素材目錄的環境變數。空字串＝用 `DEFAULT_V2_DIR`；`off`＝**關掉**（回 None），
#: 展場要能一個 env 關掉 P11 而不必改檔。
V2_ENV = "VACANT_POLAROID_V2_DIR"

#: 沒有 manifest 時的素材位置（`polaroid_v2/` 還沒生出來時這裡不存在，
#: `load_manifest()` 照樣回 None，不會自己去別處找）。
DEFAULT_V2_DIR = pathlib.Path(__file__).resolve().parent / "assets" / "polaroid_v2"

#: 地上八個地點 → 背景板代碼。**同時是 `place_code()` 的合法中文名與合法代碼**。
PLACE_CODE = {
    "投遞口": "drop",
    "捏土處": "clay",
    "長桌廣場": "longtable",
    "石頭閘門": "gate",
    "帳本鏈": "chain",
    "草稿角": "draft",
    "紙卡地": "cards",
    "畫架與長椅": "easel",
}
#: manifest 裡 `backgrounds` 必須有這八個 key（缺的那個地點退回單一背景板）。
PLACES = tuple(PLACE_CODE.values())

#: 元素中文字 → 相框代碼。`element_code()` 也認這四個字，所以 `element` 欄位
#: 傳「火」或傳「牡羊」都對得起來。
ELEMENT_CODE = {"火": "fire", "土": "earth", "風": "air", "水": "water"}

#: 十二星座，順序＝`assets/polaroid_v2/` 產生時的順序（manifest 靠名字索引，這裡
#: 只是給人看與給檢查用）。
ZODIACS = ("牡羊", "金牛", "雙子", "巨蟹", "獅子", "處女", "天秤", "天蠍", "射手",
           "摩羯", "水瓶", "雙魚")

#: 星座 → 相框元素（`element_code()` 的第一層查表）。
ZODIAC_ELEMENT = {
    "牡羊": "fire", "獅子": "fire", "射手": "fire",
    "金牛": "earth", "處女": "earth", "摩羯": "earth",
    "雙子": "air", "天秤": "air", "水瓶": "air",
    "巨蟹": "water", "天蠍": "water", "雙魚": "water",
}

#: manifest `props` 的十類地上物件（**素材檔名的目錄順序**）。
PROP_KINDS = ("letter", "card", "tile", "pencil", "jar", "scroll", "paperball",
              "clay", "stamp", "receipt")

#: (kind, 關鍵字) 有序表。**順序有意義**：數量平手時較前面的贏（見
#: `hints_from_steps()`）。關鍵字是檔名的子字串比對，不是詞典比對——
#: 因為來源是 `地上/帳本鏈/尾段_418到447片.txt` 這種實實在在的檔名。
PROP_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("letter", ("信", "信封", "托盤")),
    ("receipt", ("收據",)),
    ("stamp", ("印", "手印")),
    ("scroll", ("紙捲", "畫架")),
    ("paperball", ("紙團",)),
    ("pencil", ("鉛筆", "筆")),
    ("card", ("卡", "格狀圖", "退回紙")),
    ("tile", ("片", "帳本", "鏈", "陶片")),
    ("jar", ("罐",)),
    ("clay", ("土", "捏")),
)

#: 血型 → 印章形狀（順序即血型的字母順序 A=0、B=1、O=2、AB=3）。
BLOODS = ("A", "B", "O", "AB")
BLOOD_SHAPE = ("round", "square", "scallop", "oval")

#: 貼紙數上限與旋轉角度範圍（±12 度）。五個角度：星座、MBTI 0、MBTI 1、
#: （留一格）、血型印章。角度只是「手貼上去」的錯位感，**不是版面依賴**。
MAX_MBTI_STICKERS = 2
ROT_SLOTS = 5
ROT_SPAN = 12.0

#: 合法的 16 型 MBTI。`temperament()` 只認這 16 個字串——長度不對、大小寫不對、
#: 不在表內都回 `None`（寧可沒貼紙，也不要貼錯 temperament）。
_MBTI_TYPES = frozenset(
    a + b + c + d for a, b, c, d in itertools.product("EI", "SN", "TF", "JP")
)


# ---------------------------------------------------------------------------
# 挑款碼
# ---------------------------------------------------------------------------

def seed(*parts: Any) -> int:
    """挑款碼：sha256 前 12 碼（48 bits）當整數。**沒有 `random`、沒有時鐘**。

    分隔符 `\x1f` 是刻意的：它擋的是**切分位置不同**的碰撞——`("a", "bc")` 與
    `("ab", "c")` 算出不同、`("a", "b")` 與 `("a", "b", "c")` 也不同。
    （它擋不了 `("a", "b")` 與 `("a\\x1fb",)` 那一種，那是同一串字，本來就該同款。）
    """
    joined = "\x1f".join(str(p) for p in parts)
    return int(hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12], 16)


def _pick(lst: list[Any], i: int) -> Any | None:
    return lst[i % len(lst)] if lst else None


def _entries(v: Any) -> list[Mapping[str, Any]]:
    """manifest 裡的一層：只認 dict，別的（None、字串、數字、dict 的 list 以外）丟掉。"""
    if not isinstance(v, (list, tuple)):
        return []
    return [e for e in v if isinstance(e, Mapping)]


def _sect(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _entry(v: Any) -> Mapping[str, Any] | None:
    """單張（`stickers.zodiac` 那種 `[entry]` 與 `entry` 兩種寫法都吃）。"""
    if isinstance(v, Mapping):
        return v
    if isinstance(v, (list, tuple)):
        return next((e for e in v if isinstance(e, Mapping)), None)
    return None


def _text(v: Any) -> str:
    """只收字串；`None`／數字／list 一律當空字串（**不 `str()` 亂轉**）。"""
    return v.strip() if isinstance(v, str) else ""


def _stem_of(name: str) -> str:
    """檔名去掉副檔名（`尾段_418到447片.txt` → `尾段_418到447片`）。"""
    try:
        return pathlib.PurePosixPath(name.replace("\\", "/")).stem or name
    except Exception:  # noqa: BLE001 — 純字串操作，理論上不會炸；炸了也不該拖垮推導
        return name


def _basename(entry: Any) -> str | None:
    """給 `spec` 用的檔名（**只有檔名，沒有整條相對路徑**——路徑裡可能帶著地點）。"""
    f = entry.get("file") if isinstance(entry, Mapping) else None
    if not isinstance(f, str) or not f:
        return None
    return pathlib.PurePosixPath(f.replace("\\", "/")).name or None


# ---------------------------------------------------------------------------
# 四個小分類器（純函式，壞輸入回預設值）
# ---------------------------------------------------------------------------

def temperament(mbti: Any) -> str | None:
    """16 型 MBTI → 四種 temperament（NT／NF／SJ／SP）。**不對就回 `None`**。

    規則：`NT`＝N 且 T、`NF`＝N 且 F（看第 2、3 個字母）；`SJ`／`SP`＝S 且
    J／P（看第 2、4 個字母）。第 3 字母是同一個維度、第 4 字母是同一個維度，
    所以 N 型不看 J／P、S 型不看 T／F——四個 temperament 就是這樣把 16 型切開的。
    必須字面命中 16 型之一，所以 `None`、`"INT"`、`"intj"`、`"ZZZZ"` 都回 `None`
    （寧可沒貼紙，也不要貼錯）。
    """
    if not isinstance(mbti, str) or mbti not in _MBTI_TYPES:
        return None
    if mbti[1] == "N":
        return "NT" if mbti[2] == "T" else "NF"
    return "SJ" if mbti[3] == "J" else "SP"


def element_code(zodiac: Any) -> str:
    """星座（或元素中文字）→ 相框代碼。**認不出來回 `"neutral"`**，不丟例外。

    十二星座各歸火／土／風／水；也認 `火 土 風 水` 這四個字（`ELEMENT_CODE`）。
    剩下的（含 `None`、空字串、`"天狼星"`）一律 `neutral`——`neutral` 那層是
    `frames` 的保底層，沒有它就不會有回退。
    """
    z = _text(zodiac)
    return ZODIAC_ELEMENT.get(z) or ELEMENT_CODE.get(z) or "neutral"


def place_code(place: Any) -> str:
    """中文地點名或已是代碼都吃；**認不出來回 `"drop"`**（預設台，投遞口）。"""
    p = _text(place)
    if p in PLACE_CODE:
        return PLACE_CODE[p]
    return p if p in PLACES else "drop"


# ---------------------------------------------------------------------------
# 從操作步驟推出「他主要待在哪、地上都是什麼」
# ---------------------------------------------------------------------------

def _ground_steps(rows: Any) -> tuple[list[str], list[str]]:
    """（出現順序的地點代碼、地上物件檔名）。**只數 `ok is not False` 的地上步驟。**

    `ok is False`（步驟失敗）不算：失敗的 `ws_read` 只是打不開，不代表他不在那兒
    做過事。`ok is None` 算——不知道成沒成，不能當成沒去過。
    只認 `地上/<地點>/<檔名>`：第二段不認得的（`地上/未知/...`）整步丟掉，因為
    地點與物件都要從**同一批**步驟推出來，兩邊不同批會互相矛盾。
    """
    places: list[str] = []
    names: list[str] = []
    if not isinstance(rows, (list, tuple)):
        return places, names
    for row in rows:
        if not isinstance(row, Mapping) or row.get("ok") is False:
            continue
        path = row.get("path")
        if not isinstance(path, str):
            continue
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        if len(parts) < 2 or parts[0] != "地上":
            continue
        code = PLACE_CODE.get(parts[1])
        if code is None:
            continue
        places.append(code)
        if len(parts) >= 3:
            names.append(_stem_of(parts[-1]))
    return places, names


def hints_from_steps(rows: Any, artifact_names: Iterable[Any] = ()) -> dict[str, Any]:
    """從分身那一跑的操作紀錄推出 `{"place": 代碼, "kind": 類別或 None}`。

    `rows` 是 `twinagent` 記的步驟（每筆有 `tool`／`path`／`ok`）；
    `artifact_names` 是這一跑留下的成品檔名（外掛，不受 `ok` 與地點過濾）。

    * **place**：多數決，**平手取最早出現者**（不是字典序、不是最後一次）。
    * **kind**：把地上物件檔名與成品檔名全部攤平，依 `PROP_KEYWORDS` 的優先序數
      「有幾個名字含它的任一關鍵字」，取數量最多者；**平手取較前面的 kind**。
      一個都沒數到 → `None`（不要為了湊一個 kind 而亂指）。

    **永遠不丟例外**：垃圾輸入 → `{"place": "drop", "kind": None}`。
    """
    places, names = _ground_steps(rows)
    counts: dict[str, int] = {}
    best: str | None = None
    for c in places:
        counts[c] = counts.get(c, 0) + 1
        if best is None or counts[c] > counts[best]:       # 嚴格大於 ⇒ 平手留最早的
            best = c

    flat = list(names)
    if isinstance(artifact_names, str):
        artifact_names = (artifact_names,)
    if not isinstance(artifact_names, (list, tuple, set, frozenset)):
        artifact_names = ()
    for a in artifact_names:
        if isinstance(a, str) and a:
            flat.append(a)

    kind: str | None = None
    top = 0
    for k, keywords in PROP_KEYWORDS:
        n = sum(1 for nm in flat if any(kw in nm for kw in keywords))
        if n > top:                                        # 嚴格大於 ⇒ 平手留較前面的
            kind, top = k, n
    return {"place": best or "drop", "kind": kind}


# ---------------------------------------------------------------------------
# manifest：讀取與查核
# ---------------------------------------------------------------------------

#: sha256 快取：`(path, mtime_ns, size)` → hexdigest。**只快取成功值**，
#: 而且 key 帶 mtime／size，內容換掉（連同時間戳或大小）就重算。
_SHA_CACHE: dict[tuple[str, int, int], str] = {}


def _sha256_file(p: pathlib.Path) -> str | None:
    """現算 sha256（`polaroid.py::_sha256_file` 的快取版）。讀不到回 `None`。"""
    try:
        st = p.stat()
        key = (str(p), st.st_mtime_ns, st.st_size)
    except OSError:
        return None
    hit = _SHA_CACHE.get(key)
    if hit is not None:
        return hit
    try:
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None
    _SHA_CACHE[key] = digest
    return digest


def load_manifest(d: Any = None) -> dict[str, Any] | None:
    """讀 `d/manifest.json`。**回 `None` 的情況只有一種，沒有例外**：

    * `d` 沒給 → 環境變數 `V2_ENV`；空字串 → `DEFAULT_V2_DIR`；**值是 `off`
      → `None`**（展場一個 env 就能關掉 P11）。
    * 檔不在／不是合法 JSON／不是 dict／`version != 2` → `None`。

    成功回 manifest 本身**加一個 `_dir`**（那個目錄的字串），給 `resolve_file()`
    當唯一的路徑基準。**不在這裡驗每個 entry 的 sha256**（挑款不該碰檔案）。
    """
    try:
        raw = os.environ.get(V2_ENV, "") if d is None else d
        s = "" if raw is None else str(raw).strip()
        if s.lower() == "off":
            return None
        base = pathlib.Path(s) if s else DEFAULT_V2_DIR
        mf = base / "manifest.json"
        if not mf.is_file():
            return None
        data = json.loads(mf.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 2:
            return None
        out = dict(data)
        out["_dir"] = str(base)
        return out
    except Exception:  # noqa: BLE001 — 素材讀不到只該讓那一層消失，不該讓拍立得爆炸
        return None


def resolve_file(manifest: Any, entry: Any) -> pathlib.Path | None:
    """把 manifest entry 換成真的路徑，**並當場驗 sha256**。任何不對 → `None`。

    * 檔不在 → `None`；sha256 對不上 → `None`；**沒釘 sha256 也算 `None`**
      （沒釀過的東西不拿來畫——這是 `polaroid.py`「sha 對不上＝不可用」的同一條規則）。
    * 路徑**不准跳出 `_dir`**：`..`、絕對路徑、以及 resolve 後落在 `_dir` 外的
      （**含 symlink 指出去**）都回 `None`。
    """
    try:
        rel = _entry(entry)
        if rel is None:
            return None
        name = rel.get("file")
        want = _text(rel.get("sha256")).lower()
        if not isinstance(name, str) or not name or not want:
            return None
        sub = pathlib.PurePosixPath(name.replace("\\", "/"))
        if sub.is_absolute() or ".." in sub.parts:
            return None
        base_dir = _text(_sect(manifest).get("_dir")) or str(DEFAULT_V2_DIR)
        base = pathlib.Path(base_dir)
        target = base.joinpath(*sub.parts)
        root, real = base.resolve(), target.resolve()
        if real != root and root not in real.parents:      # symlink 指出去也算跳出
            return None
        if not target.is_file():
            return None
        return target if _sha256_file(target) == want else None
    except Exception:  # noqa: BLE001 — 同上：查核失敗＝那一層沒有
        return None


# ---------------------------------------------------------------------------
# 挑款
# ---------------------------------------------------------------------------

def _rot(sub_id: Any) -> list[float]:
    """五個 ±12 度的旋轉角（純裝飾）。順序：星座、MBTI 0、MBTI 1、留一格、血型印章。"""
    return [-ROT_SPAN + 2 * ROT_SPAN * ((seed("rot", sub_id, i) % 1000) / 999.0)
            for i in range(ROT_SLOTS)]


def pick_layers(manifest: Any, *, sub_id: Any, cast_id: Any, place: Any, element: Any,
                mbti: Any, zodiac: Any, blood: Any, kind: Any) -> dict[str, Any]:
    """依這個人的資料**確定性**挑出各層。**純函式、不讀檔案、永遠不丟例外。**

    回的每一個值都是「manifest 裡被選中的那一筆 entry」（`blood_stamp` 與 `prop`
    多帶 `blood`／`kind`；`mbti_stickers` 是 0–2 筆的清單），挑不到就是 `None`／`[]`。
    **能不能用、sha 對不對得上是 `resolve_file()` 的事**，這裡不碰檔案。

    * `background`：地點代碼那層的第 `seed("bg", sub_id, cast_id, place) % len` 筆。
    * `frame`：元素代碼那層；**該元素空或缺 → 退 `neutral`；再沒有 → `None`**。
    * `mbti_stickers`：`temperament(mbti)` 那層，張數 `1 + seed % 2`（一或兩張），
      逐張用 `seed("mbti_pick", sub_id, mbti, i)` 從**剩下的**裡挑（不重複）。
    * `zodiac_sticker`：星座在 `stickers.zodiac` 裡就是那一筆。
    * `blood_stamp`：血型的**位置**決定形狀（A→round、B→square、O→scallop、
      AB→oval），`seed("tone", sub_id, blood) % 2` 決定紅或藍。先找形狀＋顏色都對的
      第一筆，沒有就退形狀對的，**再沒有 → `None`**（不要拿別的形狀頂替）。
    * `prop`：類別那層的第 `seed("prop", sub_id, kind) % len` 筆。
    * `prop_side`：道具放左邊還是右邊。
    * `rot`：五個 ±12 度。
    * `spec`：會印進 meta 的小 dict，**只有檔名與 place/element 代碼**
      （不放 `sub_id`、不放 MBTI 四字母、不放星座／血型原值）。
    """
    p_code = place_code(place)
    e_code = element_code(element)
    out: dict[str, Any] = {
        "background": None,
        "frame": None,
        "mbti_stickers": [],
        "zodiac_sticker": None,
        "blood_stamp": None,
        "prop": None,
        "prop_side": "left" if seed("side", sub_id, cast_id) % 2 == 0 else "right",
        "rot": _rot(sub_id),
        "spec": {"place": p_code, "element": e_code, "background": None, "frame": None,
                 "mbti_stickers": [], "zodiac_sticker": None, "blood_stamp": None,
                 "prop": None},
    }
    try:
        m = _sect(manifest)
        bgs, frames = _sect(m.get("backgrounds")), _sect(m.get("frames"))
        stick, props = _sect(m.get("stickers")), _sect(m.get("props"))

        out["background"] = _pick(_entries(bgs.get(p_code)),
                                  seed("bg", sub_id, cast_id, place))
        fl = _entries(frames.get(e_code)) or _entries(frames.get("neutral"))
        out["frame"] = _pick(fl, seed("frame", sub_id, cast_id, element))

        t = temperament(mbti)
        pool = _entries(_sect(stick.get("mbti")).get(t)) if t else []
        want = 1 + seed("mbti_n", sub_id, mbti) % MAX_MBTI_STICKERS
        for i in range(min(want, len(pool))):
            out["mbti_stickers"].append(pool.pop(seed("mbti_pick", sub_id, mbti, i) % len(pool)))

        zs = _sect(stick.get("zodiac"))
        zkey = _text(zodiac)
        out["zodiac_sticker"] = _entry(zs.get(zkey)) if zkey in zs else None

        bkey = _text(blood)
        if bkey in BLOODS:
            shape = BLOOD_SHAPE[BLOODS.index(bkey)]
            tone = "red" if seed("tone", sub_id, blood) % 2 == 0 else "blue"
            stamps = _entries(stick.get("blood"))
            hit = next((e for e in stamps if e.get("shape") == shape and e.get("tone") == tone), None)
            if hit is None:
                hit = next((e for e in stamps if e.get("shape") == shape), None)
            if hit is not None:
                out["blood_stamp"] = {**hit, "blood": bkey}

        kkey = _text(kind)
        pe = _pick(_entries(props.get(kkey)), seed("prop", sub_id, kind)) if kkey in props else None
        out["prop"] = {**pe, "kind": kkey} if pe is not None else None

        out["spec"] = {
            "place": p_code, "element": e_code,
            "background": _basename(out["background"]),
            "frame": _basename(out["frame"]),
            "mbti_stickers": [_basename(e) for e in out["mbti_stickers"]],
            "zodiac_sticker": _basename(out["zodiac_sticker"]),
            "blood_stamp": _basename(out["blood_stamp"]),
            "prop": _basename(out["prop"]),
        }
    except Exception:  # noqa: BLE001 — 加分層壞掉不准拖垮拍立得：形狀照舊、內容留空
        pass
    return out