"""`ops/exhibit/twin/polaroid_layers.py` 的可執行判準。

## 這一支在架構裡承重什麼

拍立得 P11 的全部價值是「40 個人不能長得跟排印機印的一樣」。這件事只靠一件
**可被推翻的東西**撐著：挑款必須**確定性**（同一個 `sub_id` 挑同一組），素材必須
**逐檔驗 sha256**。兩件任何一件壞掉，畫面還是會照出來，只是變成同一張、或變成
被換掉的素材——所以這兩件事不是品質問題，是**機制問題**。

## 判準怎麼分層（哪一層被驗到什麼程度）

1. **確定性與分佈**：同一輸入連呼三次全等；200 個不同 `sub_id` 下 background
   至少 2 種、frame 至少 2 種——**只驗「不是同一張」不夠**，所以另外驗分佈下界。
2. **四個小分類器全表**：16 型 MBTI 的 temperament 表逐型列出（不是抽樣）、12 星座
   的元素逐個列出、四血型的印章形狀逐個對上。**表驅動的東西不能用抽樣驗**。
3. **退路存在**：元素沒給 → `neutral`；某元素的清單缺 → 退 `neutral`；地點認不出
   → `drop`。**每一層都要有一個明確的退路，而且退路要真的被走到過**。
4. **不丟例外**：`hints_from_steps()` 與 `pick_layers()` 餵垃圾輸入必須回預設值。
   加分層的失敗會被 `polaroid.py::_variety_plan` 記成 `fallbacks`，但只有
   **不炸**才記得到——炸了就是整張拍立得沒了。
5. **不外洩**：`spec` 會印進 meta，所以 `json.dumps()` 之後不得含 `sub_id`、
   MBTI 四字母、星座與血型原值。這是**隱私邊界**，不是格式偏好。
6. **manifest 查核**：`"off"`／缺檔／`version` 錯 → `None`；sha 對不上 → `None`；
   `..` 路徑 → `None`。**負控制是這一支存在的原因**：量具量得到「壞」才算量到「好」。

⚠ 本檔**零 Pillow、零真素材**：manifest 與 PNG 全是測試內現造的假物。
綠燈證明的是**挑款與查核的機制**，不是素材本身好不好看（那是
`tests/test_twin_polaroid.py` 的事，而且那一支沒有 Pillow 就整個 skip）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import polaroid_layers as L  # noqa: E402

# ---------------------------------------------------------------------------
# 測試內現造的假 manifest（每類 3–4 筆假 entry，**檔名即可**，沒有真的檔）
# ---------------------------------------------------------------------------

#: 假 sha：只求「是 64 個 hex」且每筆不同，`resolve_file()` 會現算比對。
def _fake_sha(tag: str) -> str:
    return hashlib.sha256(("fake:" + tag).encode("utf-8")).hexdigest()


def _entry(tag: str, **extra) -> dict:
    return {"file": f"{tag}.png", "sha256": _fake_sha(tag), **extra}


def _backgrounds() -> dict:
    # 八個地點代碼，每個 3 筆（第三個地點留 4 筆，測分佈下界用）
    return {p: [_entry(f"bg/{p}_{i}") for i in range(4 if p == "drop" else 3)]
            for p in L.PLACES}


def _frames() -> dict:
    f = {e: [_entry(f"fr/{e}_{i}") for i in range(3)] for e in ("fire", "earth", "air", "water")}
    f["neutral"] = [_entry(f"fr/neutral_{i}") for i in range(3)]
    return f


def _stickers() -> dict:
    return {
        "mbti": {t: [_entry(f"sk/{t}_{i}") for i in range(3)] for t in ("NT", "NF", "SJ", "SP")},
        "zodiac": {z: _entry(f"sk/z{ i + 1:02d}") for i, z in enumerate(L.ZODIACS)},
        # 四形狀 × 兩色 = 8 筆（manifest 契約說 8 筆）
        "blood": [_entry(f"sk/blood_{shape}_{tone}", shape=shape, tone=tone)
                  for shape in L.BLOOD_SHAPE for tone in ("red", "blue")],
    }


def _props() -> dict:
    return {k: [_entry(f"pr/{k}_{i}") for i in range(3)] for k in L.PROP_KINDS}


@pytest.fixture()
def fake_manifest() -> dict:
    """**刻意不放 `_dir`****：`pick_layers()` 不碰檔案，目錄與它無關。"""
    return {"version": 2, "backgrounds": _backgrounds(), "frames": _frames(),
            "stickers": _stickers(), "props": _props()}


def _pick(m, **over):
    kw = {"sub_id": "sub-0001", "cast_id": "c08", "place": "投遞口", "element": "牡羊",
          "mbti": "INTJ", "zodiac": "牡羊", "blood": "AB", "kind": "letter"}
    kw.update(over)
    return L.pick_layers(m, **kw)


def _step(path: str, ok=True, tool="ws_read") -> dict:
    return {"tool": tool, "path": path, "ok": ok}


# ---------------------------------------------------------------------------
# 一、常數與挑款碼
# ---------------------------------------------------------------------------

def test_constants_are_the_contract():
    assert L.V2_ENV == "VACANT_POLAROID_V2_DIR"
    assert L.DEFAULT_V2_DIR == pathlib.Path(L.__file__).resolve().parent / "assets" / "polaroid_v2"
    assert L.PLACES == ("drop", "clay", "longtable", "gate", "chain", "draft", "cards", "easel")
    assert len(L.PLACE_CODE) == 8 and len(L.PLACES) == 8
    assert L.ELEMENT_CODE == {"火": "fire", "土": "earth", "風": "air", "水": "water"}
    assert L.ZODIACS == ("牡羊", "金牛", "雙子", "巨蟹", "獅子", "處女", "天秤", "天蠍",
                         "射手", "摩羯", "水瓶", "雙魚")
    assert len(L.ZODIACS) == 12
    assert L.PROP_KINDS == ("letter", "card", "tile", "pencil", "jar", "scroll",
                            "paperball", "clay", "stamp", "receipt")
    # 關鍵字表的**順序**是平手優先序（刻意不等於 PROP_KINDS 的目錄順序）
    assert [k for k, _ in L.PROP_KEYWORDS] == ["letter", "receipt", "stamp", "scroll",
                                              "paperball", "pencil", "card", "tile",
                                              "jar", "clay"]
    assert {k for k, _ in L.PROP_KEYWORDS} == set(L.PROP_KINDS)
    assert dict(L.PROP_KEYWORDS)["letter"] == ("信", "信封", "托盤")
    assert dict(L.PROP_KEYWORDS)["receipt"] == ("收據",)
    assert dict(L.PROP_KEYWORDS)["stamp"] == ("印", "手印")
    assert dict(L.PROP_KEYWORDS)["scroll"] == ("紙捲", "畫架")
    assert dict(L.PROP_KEYWORDS)["paperball"] == ("紙團",)
    assert dict(L.PROP_KEYWORDS)["pencil"] == ("鉛筆", "筆")
    assert dict(L.PROP_KEYWORDS)["card"] == ("卡", "格狀圖", "退回紙")
    assert dict(L.PROP_KEYWORDS)["tile"] == ("片", "帳本", "鏈", "陶片")
    assert dict(L.PROP_KEYWORDS)["jar"] == ("罐",)
    assert dict(L.PROP_KEYWORDS)["clay"] == ("土", "捏")


def test_seed_is_the_documented_formula():
    import hashlib as _h
    expect = int(_h.sha256("a\x1fb".encode("utf-8")).hexdigest()[:12], 16)
    assert L.seed("a", "b") == expect
    assert L.seed("a", "b") == L.seed("a", "b") != L.seed("a", "c")
    # 分隔符擋的是「切分位置不同」的碰撞
    assert L.seed("a", "bc") != L.seed("ab", "c")
    assert L.seed("a", "b") != L.seed("a", "b", "c")
    # 非字串也要收（呼叫端常傳 None／數字），而且是 str() 之後才算
    assert L.seed("a", None) == L.seed("a", "None")
    assert L.seed() == L.seed("")


# ---------------------------------------------------------------------------
# 二、確定性：同一輸入三呼全等，而且要真的散開
# ---------------------------------------------------------------------------

def test_same_input_same_output_three_times(fake_manifest):
    a, b, c = (_pick(fake_manifest) for _ in range(3))
    assert a == b == c
    # 純函式的反面：不得把 manifest 改掉（改了就會污染下一次呼叫）
    assert fake_manifest == {"version": 2, "backgrounds": _backgrounds(), "frames": _frames(),
                             "stickers": _stickers(), "props": _props()}


def test_two_hundred_sub_ids_actually_vary_background_and_frame(fake_manifest):
    bgs, frames = set(), set()
    for i in range(200):
        pk = _pick(fake_manifest, sub_id=f"sub-{i:04d}")
        assert pk["background"] is not None and pk["frame"] is not None
        bgs.add(pk["background"]["file"])
        frames.add(pk["frame"]["file"])
    assert len(bgs) >= 2, f"背景只有一種 ⇒ 這個 sub_id 沒進挑款：{bgs}"
    assert len(frames) >= 2, f"相框只有一種 ⇒ 這個 sub_id 沒進挑款：{frames}"


def test_side_and_rot_are_in_range_and_vary(fake_manifest):
    sides, rots = set(), set()
    for i in range(50):
        pk = _pick(fake_manifest, sub_id=f"sub-{i:04d}")
        sides.add(pk["prop_side"])
        assert len(pk["rot"]) == 5 and all(isinstance(r, float) for r in pk["rot"])
        assert all(-12.0 <= r <= 12.0 for r in pk["rot"])
        rots.add(tuple(pk["rot"]))
    assert sides == {"left", "right"}
    assert len(rots) >= 2


def test_rot_matches_the_formula(fake_manifest):
    sub = "sub-0001"
    expect = [-12 + 24 * ((L.seed("rot", sub, i) % 1000) / 999) for i in range(5)]
    assert _pick(fake_manifest, sub_id=sub)["rot"] == expect


# ---------------------------------------------------------------------------
# 三、temperament：16 型全表 + 壞輸入
# ---------------------------------------------------------------------------

TEMPERAMENT_TABLE = {
    "INTJ": "NT", "INTP": "NT", "ENTJ": "NT", "ENTP": "NT",
    "INFJ": "NF", "INFP": "NF", "ENFJ": "NF", "ENFP": "NF",
    "ISTJ": "SJ", "ISFJ": "SJ", "ESTJ": "SJ", "ESFJ": "SJ",
    "ISTP": "SP", "ISFP": "SP", "ESTP": "SP", "ESFP": "SP",
}


@pytest.mark.parametrize("mbti,expect", sorted(TEMPERAMENT_TABLE.items()))
def test_temperament_all_sixteen(mbti, expect):
    assert L.temperament(mbti) == expect


def test_temperament_table_is_the_whole_16():
    assert len(TEMPERAMENT_TABLE) == 16
    assert set(TEMPERAMENT_TABLE.values()) == {"NT", "NF", "SJ", "SP"}


@pytest.mark.parametrize("bad", [None, "", "INT", "INTJx", "intj", "ZZZZ", "ZZZZZZZZ",
                                 "1234", 1234, "INTJ ", ["INTJ"], {"mbti": "INTJ"}, 3.5])
def test_temperament_bad_input_is_none(bad):
    assert L.temperament(bad) is None


# ---------------------------------------------------------------------------
# 四、element_code：12 星座全表
# ---------------------------------------------------------------------------

ELEMENT_TABLE = {
    "牡羊": "fire", "金牛": "earth", "雙子": "air", "巨蟹": "water",
    "獅子": "fire", "處女": "earth", "天秤": "air", "天蠍": "water",
    "射手": "fire", "摩羯": "earth", "水瓶": "air", "雙魚": "water",
}


@pytest.mark.parametrize("zodiac,expect", sorted(ELEMENT_TABLE.items()))
def test_element_code_all_twelve(zodiac, expect):
    assert L.element_code(zodiac) == expect


def test_element_table_covers_exactly_the_twelve():
    assert set(ELEMENT_TABLE) == set(L.ZODIACS)
    assert set(ELEMENT_TABLE.values()) == set(L.ELEMENT_CODE.values())


@pytest.mark.parametrize("bad", [None, "", "天狼星", "牡", "牡羊座", 7, ["牡羊"]])
def test_element_code_unknown_is_neutral(bad):
    assert L.element_code(bad) == "neutral"


def test_element_code_also_takes_the_element_characters():
    for ch, code in L.ELEMENT_CODE.items():
        assert L.element_code(ch) == code


# ---------------------------------------------------------------------------
# 五、place_code：中文名與代碼都吃，認不出來回 drop
# ---------------------------------------------------------------------------

def test_place_code_accepts_chinese_and_code():
    for zh, code in L.PLACE_CODE.items():
        assert L.place_code(zh) == code
        assert L.place_code(code) == code
    assert L.place_code("長桌廣場") == "longtable"


@pytest.mark.parametrize("bad", [None, "", "地下室", "DROP", 42, ["drop"]])
def test_place_code_unknown_is_drop(bad):
    assert L.place_code(bad) == "drop"


# ---------------------------------------------------------------------------
# 六、退路：元素沒給 → neutral；某元素缺 → 退 neutral
# ---------------------------------------------------------------------------

def test_no_element_gives_neutral_frame(fake_manifest):
    pk = _pick(fake_manifest, element=None)
    assert pk["frame"] in fake_manifest["frames"]["neutral"]
    assert pk["spec"]["element"] == "neutral"


def test_missing_element_list_falls_back_to_neutral(fake_manifest):
    m = fake_manifest
    m["frames"].pop("fire")
    pk = _pick(m, element="牡羊")
    assert pk["frame"] in m["frames"]["neutral"]
    assert pk["frame"] is not None


def test_empty_element_list_falls_back_to_neutral(fake_manifest):
    m = fake_manifest
    m["frames"]["fire"] = []
    assert _pick(m, element="牡羊")["frame"] in m["frames"]["neutral"]


def test_no_neutral_either_gives_none(fake_manifest):
    m = fake_manifest
    m["frames"].pop("fire")
    m["frames"].pop("neutral")
    assert _pick(m, element="牡羊")["frame"] is None


def test_unknown_place_uses_the_drop_background(fake_manifest):
    pk = _pick(fake_manifest, place="地下室")
    assert pk["background"] in fake_manifest["backgrounds"]["drop"]
    assert pk["spec"]["place"] == "drop"


def test_missing_place_background_is_none(fake_manifest):
    m = fake_manifest
    m["backgrounds"].pop("drop")
    assert _pick(m, place="投遞口")["background"] is None


# ---------------------------------------------------------------------------
# 七、血型印章：四型形狀對得上、非法血型 → None
# ---------------------------------------------------------------------------

def test_blood_shape_matches_the_blood_type(fake_manifest):
    for blood, shape in zip(("A", "B", "O", "AB"), L.BLOOD_SHAPE):
        pk = _pick(fake_manifest, blood=blood)
        stamp = pk["blood_stamp"]
        assert stamp is not None, f"{blood} 沒挑到印章"
        assert stamp["shape"] == shape, f"{blood} 的形狀不對"
        assert stamp["tone"] in ("red", "blue")
        assert stamp["blood"] == blood
        assert stamp["file"] in {e["file"] for e in fake_manifest["stickers"]["blood"]}


def test_blood_tone_follows_the_seed(fake_manifest):
    for blood in ("A", "B", "O", "AB"):
        want = "red" if L.seed("tone", "sub-0001", blood) % 2 == 0 else "blue"
        assert _pick(fake_manifest, blood=blood)["blood_stamp"]["tone"] == want


@pytest.mark.parametrize("bad", [None, "", "C", "AB+", "abb", 42, ["A"], "a"])
def test_invalid_blood_is_none(fake_manifest, bad):
    assert _pick(fake_manifest, blood=bad)["blood_stamp"] is None


def test_stamp_tone_mismatch_falls_back_to_same_shape(fake_manifest):
    """**負控制**：形狀對、色不對時要退到同形狀的第一筆，不是回 None，也不是換形狀。"""
    m = fake_manifest
    blood, shape = "O", L.BLOOD_SHAPE[("A", "B", "O", "AB").index("O")]
    want_tone = "red" if L.seed("tone", "sub-0001", blood) % 2 == 0 else "blue"
    m["stickers"]["blood"] = [e for e in m["stickers"]["blood"] if e["tone"] != want_tone]
    stamp = _pick(m, blood=blood)["blood_stamp"]
    assert stamp is not None and stamp["shape"] == shape


def test_stamp_shape_absent_is_none(fake_manifest):
    m = fake_manifest
    m["stickers"]["blood"] = [e for e in m["stickers"]["blood"] if e["shape"] != "scallop"]
    assert _pick(m, blood="O")["blood_stamp"] is None


# ---------------------------------------------------------------------------
# 八、MBTI 與星座貼紙
# ---------------------------------------------------------------------------

def test_mbti_stickers_from_that_temperament(fake_manifest):
    for mbti, t in sorted(TEMPERAMENT_TABLE.items()):
        pk = _pick(fake_manifest, mbti=mbti)
        st = pk["mbti_stickers"]
        assert 1 <= len(st) <= 2, f"{mbti} 挑了 {len(st)} 張"
        files = [e["file"] for e in st]
        assert len(set(files)) == len(files), f"{mbti} 挑到重複的：{files}"
        pool = {e["file"] for e in fake_manifest["stickers"]["mbti"][t]}
        assert set(files) <= pool, f"{mbti} 挑到別的 temperament 的貼紙"


def test_mbti_sticker_count_is_one_or_two_by_the_seed(fake_manifest):
    for i in range(60):
        mbti = "INTJ"
        want = 1 + L.seed("mbti_n", f"sub-{i:04d}", mbti) % 2
        assert len(_pick(fake_manifest, sub_id=f"sub-{i:04d}")["mbti_stickers"]) == want


def test_bad_mbti_gives_no_mbti_sticker(fake_manifest):
    for bad in (None, "", "ZZZZ", "intj", "INT"):
        assert _pick(fake_manifest, mbti=bad)["mbti_stickers"] == []
    m = fake_manifest
    m["stickers"]["mbti"]["NT"] = []
    assert _pick(m, mbti="INTJ")["mbti_stickers"] == []


def test_zodiac_sticker(fake_manifest):
    for z in L.ZODIACS:
        pk = _pick(fake_manifest, zodiac=z)
        assert pk["zodiac_sticker"] == fake_manifest["stickers"]["zodiac"][z]
    for bad in (None, "", "天狼星", "牡羊座"):
        assert _pick(fake_manifest, zodiac=bad)["zodiac_sticker"] is None


def test_prop_picks_from_that_kind(fake_manifest):
    for kind in L.PROP_KINDS:
        pk = _pick(fake_manifest, kind=kind)
        prop = pk["prop"]
        assert prop is not None and prop["kind"] == kind
        assert prop["file"] in {e["file"] for e in fake_manifest["props"][kind]}
    for bad in (None, "", "石頭", "LETTER"):
        assert _pick(fake_manifest, kind=bad)["prop"] is None
    m = fake_manifest
    m["props"]["jar"] = []
    assert _pick(m, kind="jar")["prop"] is None


# ---------------------------------------------------------------------------
# 九、spec：不外洩 sub_id / MBTI 四字母 / 星座 / 血型
# ---------------------------------------------------------------------------

def test_spec_carries_no_privacy_bearing_values(fake_manifest):
    sub = "sub-9f3a-secret"
    pk = _pick(fake_manifest, sub_id=sub, mbti="INTJ", zodiac="牡羊", blood="AB",
               place="投遞口", element="牡羊", kind="letter")
    blob = json.dumps(pk["spec"], ensure_ascii=False)
    assert sub not in blob
    assert "sub-9f3a" not in blob
    assert "INTJ" not in blob
    assert "牡羊" not in blob
    assert "AB" not in blob
    # 但 place/element 代碼與檔名要真的在裡面（不然這張 meta 沒東西可看）
    assert pk["spec"]["place"] == "drop"
    assert pk["spec"]["element"] == "fire"
    assert pk["spec"]["background"] == pk["background"]["file"].rsplit("/", 1)[-1]
    assert pk["spec"]["frame"] and pk["spec"]["prop"] and pk["spec"]["blood_stamp"]
    assert len(pk["spec"]["mbti_stickers"]) == len(pk["mbti_stickers"])


def test_spec_paths_are_basenames_only(fake_manifest):
    """**只有檔名**：`file` 是含目錄的相對路徑，`spec` 不得把整條路徑印出去。"""
    pk = _pick(fake_manifest)
    for v in [pk["spec"]["background"], pk["spec"]["frame"], pk["spec"]["prop"]]:
        assert "/" not in v


def test_spec_on_empty_manifest_is_all_none(fake_manifest):
    pk = _pick({"version": 2})
    assert pk["spec"]["background"] is None and pk["spec"]["frame"] is None
    assert pk["spec"]["mbti_stickers"] == [] and pk["spec"]["prop"] is None
    assert pk["background"] is None and pk["mbti_stickers"] == []


# ---------------------------------------------------------------------------
# 十、hints_from_steps：多數決、平手取最早、ok False 不算、垃圾不炸
# ---------------------------------------------------------------------------

def test_place_majority():
    rows = [_step(f"地上/{zh}/x{i}.txt") for i, zh in
            enumerate(["捏土處"] * 3 + ["帳本鏈"] * 2 + ["投遞口"])]
    assert L.hints_from_steps(rows)["place"] == "clay"


def test_place_tie_takes_the_earliest():
    rows = [_step("地上/畫架與長椅/a.txt"), _step("地上/草稿角/b.txt"),
            _step("地上/畫架與長椅/c.txt"), _step("地上/草稿角/d.txt")]
    assert L.hints_from_steps(rows)["place"] == "easel"


def test_place_no_ground_steps_is_drop():
    assert L.hints_from_steps([])["place"] == "drop"
    assert L.hints_from_steps(None)["place"] == "drop"
    assert L.hints_from_steps([_step("天台/投遞口/a.txt")])["place"] == "drop"
    assert L.hints_from_steps([_step("地上/地下室/a.txt")])["place"] == "drop"
    assert L.hints_from_steps([_step("地上")])["place"] == "drop"


def test_failed_steps_do_not_count():
    rows = [_step("地上/帳本鏈/a.txt"), _step("地上/帳本鏈/b.txt"),
            _step("地上/草稿角/c.txt", ok=False), _step("地上/草稿角/d.txt", ok=False)]
    assert L.hints_from_steps(rows)["place"] == "chain"
    # 兩筆失敗步驟的檔名**沒被數進 kind**；kind 只由還活著的兩筆帳本鏈檔名決定
    assert L.hints_from_steps(rows)["kind"] is None
    assert L.hints_from_steps(rows, ("格狀圖",))["kind"] == "card"   # 成品名稱可以加票
    # ok 是 None（不知道成沒成）要算
    rows2 = [_step("地上/草稿角/c.txt", ok=None), _step("地上/帳本鏈/d.txt", ok=None)]
    assert L.hints_from_steps(rows2)["place"] == "draft"


def test_artifact_names_join_the_kind_vote():
    assert L.hints_from_steps([], ("地上/草稿角/紙團_乙.txt",))["kind"] == "paperball"
    assert L.hints_from_steps([], ["收據_甲.txt", "收據_乙.txt"])["kind"] == "receipt"


def test_kind_keywords_from_real_paths():
    assert L.hints_from_steps([_step("地上/投遞口/托盤_半封信.txt")])["kind"] == "letter"
    assert L.hints_from_steps([_step("地上/草稿角/紙團_乙.txt")])["kind"] == "paperball"
    assert L.hints_from_steps([_step("地上/帳本鏈/尾段_418到447片.txt")])["kind"] == "tile"
    assert L.hints_from_steps([_step("地上/捏土處/土團_三")])["kind"] == "clay"
    assert L.hints_from_steps([_step("地上/畫架與長椅/紙捲_甲")])["kind"] == "scroll"
    assert L.hints_from_steps([_step("地上/紙卡地/格狀圖_甲")])["kind"] == "card"
    assert L.hints_from_steps([_step("地上/石頭閘門/手印_甲")])["kind"] == "stamp"


def test_kind_tie_takes_the_earlier_keyword():
    """平手時較前面的 kind 贏：`信封`（letter，第 1 順位）壓過 `卡`（card，第 7 順位）。"""
    rows = [_step("地上/投遞口/信封_甲.txt"), _step("地上/紙卡地/卡_乙.txt")]
    assert L.hints_from_steps(rows)["kind"] == "letter"


def test_kind_none_when_nothing_matches():
    assert L.hints_from_steps([_step("地上/投遞口/天氣_甲.txt")])["kind"] is None
    assert L.hints_from_steps([], ("天氣",))["kind"] is None
    assert L.hints_from_steps([], ())["kind"] is None


def test_hints_never_raise_on_garbage():
    for rows in (None, 7, "地上/投遞口/a.txt", {"path": "地上/草稿角/a.txt"},
                 [None, 7, [], {"path": None}, {"path": 42}, {"ok": False},
                  {"tool": "ws_read"}, {"path": "地上/投遞口"}, {"path": "地上//a.txt"}]):
        got = L.hints_from_steps(rows)
        assert got == {"place": "drop", "kind": None}, rows
    for names in (None, 7, [None, 7, {}, ""]):
        assert L.hints_from_steps([], names) == {"place": "drop", "kind": None}
    # 一個字串被當成單一名字，而不是被拆成一個字一個字
    assert L.hints_from_steps([], "紙團")["kind"] == "paperball"


def test_hints_returns_both_keys_always():
    for rows in ([], None, [{"path": "地上/捏土處/土.txt"}]):
        got = L.hints_from_steps(rows)
        assert set(got) == {"place", "kind"}


# ---------------------------------------------------------------------------
# 十一、pick_layers 不丟例外
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("m", [None, 7, "manifest", [], {"backgrounds": "x", "frames": 3,
                                                         "stickers": None, "props": []},
                               {"version": 2, "backgrounds": {"drop": [None, 7, "x"]},
                                "frames": {"fire": [{"file": None}]}}])
def test_pick_layers_never_raises(m):
    full = {"sub_id": "sub-0001", "cast_id": "c08", "place": "投遞口", "element": "牡羊",
            "mbti": "INTJ", "zodiac": "牡羊", "blood": "AB", "kind": "letter"}
    for over in (full, {**full, "place": ["長桌廣場"], "element": 7, "mbti": object(),
                        "zodiac": None, "blood": 3, "kind": {"a": 1}, "sub_id": None,
                        "cast_id": ["c08"]}):
        pk = L.pick_layers(m, **over)
        assert set(pk) == {"background", "frame", "mbti_stickers", "zodiac_sticker",
                           "blood_stamp", "prop", "prop_side", "rot", "spec"}
        assert pk["prop_side"] in ("left", "right")
        assert len(pk["rot"]) == 5


def test_pick_layers_does_not_mutate_the_manifest(fake_manifest):
    before = json.dumps(fake_manifest, sort_keys=True, ensure_ascii=False)
    _pick(fake_manifest, mbti="ENFP", blood="O", zodiac="天蠍", kind="tile", place="捏土處")
    assert json.dumps(fake_manifest, sort_keys=True, ensure_ascii=False) == before


# ---------------------------------------------------------------------------
# 十二、load_manifest：off／缺檔／version 錯／壞 JSON → None
# ---------------------------------------------------------------------------

def test_load_manifest_off(tmp_path, monkeypatch):
    monkeypatch.setenv(L.V2_ENV, "off")
    assert L.load_manifest() is None
    assert L.load_manifest("off") is None
    monkeypatch.setenv(L.V2_ENV, "OFF")           # 大寫也關（展場手滑不算理由）
    assert L.load_manifest() is None


def test_load_manifest_env_points_at_the_dir(tmp_path, monkeypatch):
    (tmp_path / "manifest.json").write_text(json.dumps({"version": 2, "hello": 1}), encoding="utf-8")
    monkeypatch.setenv(L.V2_ENV, str(tmp_path))
    m = L.load_manifest()
    assert m["version"] == 2 and m["hello"] == 1
    assert m["_dir"] == str(tmp_path)
    # 空白字串＝用預設目錄（把預設指到 tmp_path 才測得到，不必真的在 repo 裡放素材）
    monkeypatch.setenv(L.V2_ENV, "")
    monkeypatch.setattr(L, "DEFAULT_V2_DIR", tmp_path)
    assert (L.load_manifest() or {}).get("hello") == 1
    # 變數沒設＝同一條路
    monkeypatch.delenv(L.V2_ENV, raising=False)
    assert (L.load_manifest() or {}).get("hello") == 1


def test_load_manifest_missing_file(tmp_path, monkeypatch):
    monkeypatch.delenv(L.V2_ENV, raising=False)
    assert L.load_manifest(tmp_path) is None            # 沒有 manifest.json
    assert L.load_manifest(tmp_path / "nope") is None   # 連目錄都沒有


@pytest.mark.parametrize("body", ['{"version": 1, "x": 1}', '{"version": "2"}', '{"version": 3}',
                                  "[]", '"v2"', "{這不是 JSON}", "", "null"])
def test_load_manifest_rejects_bad_version_or_json(tmp_path, body):
    (tmp_path / "manifest.json").write_text(body, encoding="utf-8")
    assert L.load_manifest(tmp_path) is None


def test_load_manifest_ok(tmp_path):
    body = {"version": 2, "backgrounds": {"drop": []}, "_dir": "不該被信任"}
    (tmp_path / "manifest.json").write_text(json.dumps(body), encoding="utf-8")
    m = L.load_manifest(tmp_path)
    assert m is not None
    assert m["_dir"] == str(tmp_path)     # 磁碟上的值蓋掉 manifest 裡自稱的那個


# ---------------------------------------------------------------------------
# 十三、resolve_file：sha 對得上才回路徑；對不上／`..`／缺檔 → None
# ---------------------------------------------------------------------------

def _png_manifest(tmp_path: pathlib.Path, name: str, payload: bytes) -> dict:
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return {"version": 2, "_dir": str(tmp_path),
            "backgrounds": {"drop": [{"file": name, "sha256": hashlib.sha256(payload).hexdigest()}]}}


def test_resolve_file_ok(tmp_path):
    m = _png_manifest(tmp_path, "bg/a.png", b"fake-png-bytes")
    assert L.resolve_file(m, m["backgrounds"]["drop"][0]) == tmp_path / "bg/a.png"


def test_resolve_file_sha_mismatch_is_none(tmp_path):
    m = _png_manifest(tmp_path, "bg/a.png", b"fake-png-bytes")
    entry = dict(m["backgrounds"]["drop"][0], sha256="0" * 64)
    assert L.resolve_file(m, entry) is None


def test_resolve_file_content_swapped_under_the_same_name_is_none(tmp_path):
    """**負控制**：檔名還在、sha 也沒換，是**內容**被換掉 ⇒ 必須抓到。"""
    m = _png_manifest(tmp_path, "bg/a.png", b"fake-png-bytes")
    (tmp_path / "bg/a.png").write_bytes(b"swapped-after-manifest")
    assert L.resolve_file(m, m["backgrounds"]["drop"][0]) is None


def test_resolve_file_missing_file_is_none(tmp_path):
    m = _png_manifest(tmp_path, "bg/a.png", b"fake-png-bytes")
    (tmp_path / "bg/a.png").unlink()
    assert L.resolve_file(m, m["backgrounds"]["drop"][0]) is None


@pytest.mark.parametrize("bad", ["../outside.png", "bg/../../outside.png", "/etc/passwd",
                                 "..", "bg/..", "../"])
def test_resolve_file_refuses_to_escape(tmp_path, bad):
    (tmp_path.parent / "outside.png").write_bytes(b"outside")
    m = _png_manifest(tmp_path, "bg/a.png", b"fake-png-bytes")
    assert L.resolve_file(m, {"file": bad, "sha256": "0" * 64}) is None


def test_resolve_file_without_a_pinned_sha_is_none(tmp_path):
    m = _png_manifest(tmp_path, "bg/a.png", b"fake-png-bytes")
    assert L.resolve_file(m, {"file": "bg/a.png"}) is None
    assert L.resolve_file(m, {"file": "bg/a.png", "sha256": ""}) is None


@pytest.mark.parametrize("entry", [None, 7, "bg/a.png", [], {}, {"file": None},
                                   {"file": 7, "sha256": "0" * 64}])
def test_resolve_file_bad_entry_is_none(tmp_path, entry):
    assert L.resolve_file({"_dir": str(tmp_path)}, entry) is None


def test_resolve_file_cache_follows_the_content(tmp_path):
    """**負控制**：快取 key 是 `(path, mtime, size)`。同 key 可以吃快取；key 變了就得重算。"""
    payload = b"fake-png-bytes"
    m = _png_manifest(tmp_path, "a.png", payload)
    entry = m["backgrounds"]["drop"][0]
    before = len(L._SHA_CACHE)
    assert L.resolve_file(m, entry) == tmp_path / "a.png"
    assert len(L._SHA_CACHE) == before + 1          # 模組層 dict 確實被用了
    assert L.resolve_file(m, entry) == tmp_path / "a.png"      # 再問一次：同 key，快取命中
    assert len(L._SHA_CACHE) == before + 1
    (tmp_path / "a.png").write_bytes(payload + b"x")             # size 變了 ⇒ 不能吃快取
    assert L.resolve_file(m, entry) is None
    import os
    assert os.path.isfile(tmp_path / "a.png")