"""拍立得（2026-09-26）的判準：長什麼樣、跟電視同一張臉、只發給做成了的那一跑、撤回刪得掉。

裁決：`decisions/DECISION_20260926_TWIN_POLAROID.md`。合成：`ops/exhibit/twin/polaroid.py`。

⚠ 本檔零模型呼叫：分身那一跑用 `tests/test_twin_agent_run.py` 的假上游＋fixture agent
（腳本化、真的經過 `vacant run`、真的簽收據）。**綠燈證明的是機制，不是分身的能力。**
⚠ 每一個綠燈配一個負控制（量具量得到「壞」才算量到「好」）。
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from ops.exhibit.twin import polaroid, qr, twinagent, twinlink, twinvault  # noqa: E402
from ops.exhibit.twin.twinstore import KIND_ERASED, KIND_NOTE, KIND_PUBLISHED, canonical_json  # noqa: E402
# 假上游＋fixture agent＋store（同一套，不另寫一份會漂的）
from test_twin_agent_run import (  # noqa: E402,F401
    DECISION, LETTER, NEED, TRAITS_TEXT, _ingest, env, upstream,
)

PIL = pytest.importorskip("PIL", reason="沒有 Pillow ⇒ 拍立得合成**沒有被驗過**（不是驗過了）")
from PIL import Image  # noqa: E402

EVID = ROOT / "ops" / "exhibit" / "twin" / "evidence_polaroid_20260926" / "v2"
#: 測試輸入用分身真跑寫過的一句（`EVID/runs.json` p1），不用人寫的罐頭句。
AGENT_LINE = "我決定整理一份「週末登山清單」。"

#: v2 那 8 張範例合成的當下（2026-09-26 稍早），只有這 10 位有姿勢圖；`samples.json`
#: 裡的 `meta.figure` 記的是那個時間點的事實，跟後來（其餘 24 位上架後）現在的
#: `polaroid.figure_for()` 不是同一件事，不能互相比對。
_V2_POSE_IDS_AT_GENERATION = ("c02", "c09", "c10", "c17", "c19", "c25", "c28", "c31", "c33", "c40")


def _compose(decision: str = AGENT_LINE, **kw):
    kw.setdefault("cast_id", "c08")
    kw.setdefault("date_str", "2026.09.26")
    kw.setdefault("receipt_short", "0123abcd")
    return polaroid.compose(decision=decision, **kw)


def _chain_blob(st) -> str:
    return "\n".join(canonical_json(e["payload"]) for e in st.events())


# ---------------------------------------------------------------------------
# 一、合成：尺寸、字不出界、截斷、QR
# ---------------------------------------------------------------------------

def test_available_on_this_machine() -> None:
    ok, why = polaroid.available()
    assert ok, why


def test_size_and_everything_stays_inside_its_box() -> None:
    png, meta = _compose()
    im = Image.open(io.BytesIO(png))
    assert im.size == polaroid.CANVAS == tuple(meta["size"])
    assert png.startswith(b"\x89PNG\r\n\x1a\n")

    def inside(a, b):
        return a[0] >= b[0] and a[1] >= b[1] and a[2] <= b[2] and a[3] <= b[3]

    full = (0, 0, *polaroid.CANVAS)
    assert inside(meta["caption_drawn"], meta["caption_box"])
    assert inside(meta["footer_drawn"], meta["footer_box"])
    assert inside(meta["qr_quiet_box"], full)
    assert inside(meta["window"], full)
    # 字不壓到 QR 的靜區（靜區裡有字＝解碼器會失敗）
    for k in ("caption_drawn", "footer_drawn"):
        a, q = meta[k], meta["qr_quiet_box"]
        assert a[2] <= q[0] or a[3] <= q[1] or a[1] >= q[3], k


def test_png_carries_no_metadata_chunks() -> None:
    """分享出去的圖任何人都拿得到——PNG 裡不准夾 tEXt／iTXt／zTXt／eXIf。"""
    png, _ = _compose()
    pos, chunks = 8, []
    while pos < len(png):
        n = int.from_bytes(png[pos:pos + 4], "big")
        chunks.append(png[pos + 4:pos + 8].decode("ascii"))
        pos += 12 + n
    assert not {"tEXt", "iTXt", "zTXt", "eXIf"} & set(chunks), chunks
    assert chunks[0] == "IHDR" and chunks[-1] == "IEND"


def test_long_decision_is_truncated_and_fits() -> None:
    # 截斷的機制測試（字串是測試輸入，不是範例；真跑的八句都沒有長到要截，見 samples.json）
    long = "我決定在房間裡寫一份很長很長的東西，長到兩行都放不下，所以最後一定會被截掉一截才對"
    _png, meta = _compose(long)
    assert meta["caption_truncated"] is True and meta["caption_lines"] == 2
    box = meta["caption_box"]
    d = meta["caption_drawn"]
    assert box[0] <= d[0] and d[2] <= box[2] and box[1] <= d[1] and d[3] <= box[3]
    f = polaroid._font(polaroid.CAPTION_PX)
    lines, cut = polaroid.wrap_caption(f, long, box[2] - box[0])
    assert cut and len(lines) == 2 and lines[-1].endswith("…")
    assert not lines[-1][:-1].endswith(("，", "、", " "))
    assert all(f.getlength(ln) <= box[2] - box[0] for ln in lines)
    # 負控制：不截的話**真的放不下**兩行（這條判準量得到出界）
    assert f.getlength(long) > 2 * (box[2] - box[0])


def test_two_line_wrap_is_balanced_and_respects_quotes() -> None:
    """真跑寫出來的句子多半 16–28 字：要兩行時找最平衡的斷點，不留一個字孤零零在第二行，
    句讀不放行首、開引號不放行尾、能不斷在引號裡就不斷。"""
    f = polaroid._font(polaroid.CAPTION_PX)
    w = polaroid.layout_for()["caption"]
    w = w[2] - w[0]
    lines, cut = polaroid.wrap_caption(f, "我決定寫一份「日文單字記憶小撇步」", w)
    assert not cut and lines == ["我決定寫一份", "「日文單字記憶小撇步」"]
    for text in ("我打算在房間裡建立一份「公園路線導覽」", "我決定為自己寫一份「深夜護理師的放鬆清單」"):
        lines, _ = polaroid.wrap_caption(f, text, w)
        assert len(lines) == 2 and "".join(lines) == text
        assert lines[1][0] not in polaroid._NO_LINE_START and lines[0][-1] not in polaroid._NO_LINE_END
        assert min(len(x) for x in lines) >= 4                     # 沒有孤字
    # 負控制：貪心塞滿第一行的做法**真的會**留下孤字（這把尺量得到）
    text = "我決定寫一份「日文單字記憶小撇步」"
    n = 1
    while n < len(text) and f.getlength(text[:n + 1]) <= w:
        n += 1
    balanced, _ = polaroid.wrap_caption(f, text, w)
    assert len(text) - n <= 3 < min(len(x) for x in balanced)     # 貪心剩 ≤3 字；平衡版每行都比它多


def test_word_boundary_is_preferred_over_a_slightly_more_balanced_midword_split() -> None:
    """2026-09-26：換行不切詞。原本「只看兩行寬度差最小」的版本會把常見兩字詞從中間切開
    （真跑範例 p6：「…關於「如／果恐龍…」，見下一條）。改法：**先**找「斷在標點之後、或
    斷在「的／在／和／與」這類連接字之後、且不在引號裡」的斷點，這一層裡一樣挑最平衡的；
    這種斷點存在時優先用，即使它比「不管切在哪個字中間」的最佳平衡點還不平衡一點。

    這裡用構造出來的句子（不是真跑範例，範例不能為了湊案例去挑或改）：「如果」剛好卡在
    兩行寬度差最小（=0）的那個切點正中間，但往後兩個字有一個「的」，切在它後面兩行還是
    放得下（9 字／7 字），只是差距（88）比切在「如／果」中間（差距 0）大一點。"""
    f = polaroid._font(polaroid.CAPTION_PX)
    w = polaroid.layout_for()["caption"]
    w = w[2] - w[0]
    text = "房間桌椅牆壁窗如果的桌椅牆壁窗戶"
    assert len(text) == 16

    # 負控制：不分詞界、只看平衡的舊算法，這句話**真的會**切在「如｜果」中間。
    def _old_balance_only(text: str, max_w: int) -> tuple[str, str] | None:
        depth = polaroid._quote_depth(text)
        best = None
        for n in range(1, len(text)):
            a, b = text[:n], text[n:].lstrip()
            if not b or b[0] in polaroid._NO_LINE_START or a[-1] in polaroid._NO_LINE_END:
                continue
            wa, wb = f.getlength(a), f.getlength(b)
            if wa > max_w or wb > max_w:
                continue
            cost = abs(wa - wb) + (max_w if depth[n] else 0)
            if best is None or cost < best[0]:
                best = (cost, n)
        return (text[:best[1]], text[best[1]:]) if best else None

    old_a, old_b = _old_balance_only(text, w)
    assert old_a.endswith("如") and old_b.startswith("果"), (old_a, old_b)   # 量得到「舊算法會切詞」

    # 新算法：同一句話，斷點改到「的」後面，不切「如果」。
    lines, cut = polaroid.wrap_caption(f, text, w)
    assert not cut and "".join(lines) == text
    assert not (lines[0].endswith("如") and lines[1].startswith("果"))
    assert lines == ["房間桌椅牆壁窗如果的", "桌椅牆壁窗戶"]
    assert all(f.getlength(ln) <= w for ln in lines)


def test_p6_dinosaur_sentence_the_only_fitting_break_lands_inside_a_word() -> None:
    """誠實記錄一個換行不切詞修不掉的邊界案例：p6 那句在**目前版面寬度**下窮舉找過，
    兩行都放得下的切法只有一種（14 字／14 字），而那個位置剛好卡在「如｜果」中間——
    這不是這次改的斷點邏輯沒生效，是這句話（剛好 28 字、卡面窄到一行只放得下 14 字）
    搭配目前版寬本來就只有這一種切法可選，換哪一種「找斷點」演算法結果都一樣。
    這裡窮舉驗證這個事實（不是憑印象講「修不好」），並確認 wrap_caption 對這句話仍然
    正確退回這唯一的合法切法（不是漏切、不是當機）。"""
    f = polaroid._font(polaroid.CAPTION_PX)
    w = polaroid.layout_for()["caption"]
    w = w[2] - w[0]
    raw = "我決定在房間裡寫一個關於「如果恐龍有外星科技」的奇幻構想。"     # runs.json p6 原句
    text = polaroid.clean_caption(raw)
    assert len(text) == 28 and w // polaroid.CAPTION_PX == 14        # 卡面一行最多 14 字

    fitting = []
    for n in range(1, len(text)):
        a, b = text[:n], text[n:]
        if f.getlength(a) <= w and f.getlength(b) <= w:
            fitting.append(n)
    assert fitting == [14]                                          # 窮舉：唯一一種兩行都放得下的切法

    lines, cut = polaroid.wrap_caption(f, text, w)
    assert not cut and "".join(lines) == text
    assert lines == [text[:14], text[14:]]
    assert lines[0].endswith("如") and lines[1].startswith("果")     # 照實記：這句無解，換不掉


def test_short_decision_is_not_truncated() -> None:
    _png, meta = _compose("我決定寫一份筆記")
    assert meta["caption_truncated"] is False and meta["caption_chars"] == 8
    assert meta["caption_lines"] == 1


def test_nothing_left_to_say_means_a_blank_line_not_a_canned_one() -> None:
    """空的決定、只有 emoji 的決定 ⇒ 留空（拍立得照發）。不補任何人寫的字。"""
    for d in ("", "📦✅", "## 「」"):
        png, meta = _compose(d)
        assert meta["caption_blank"] is True and meta["caption_chars"] == 0, d
        assert _ink_in(png, meta["caption_box"]) == 0, d


def test_glyphs_the_font_cannot_draw_are_dropped_not_tofu() -> None:
    f = polaroid._font(polaroid.CAPTION_PX)
    assert polaroid._has_glyph(f, "寫") and polaroid._has_glyph(f, "A")
    # 負控制：emoji 在這支字型裡畫不出來（量具分得出「有」跟「沒有」）
    assert not polaroid._has_glyph(f, "\U0001F4E6")
    _png, meta = _compose("列一張搬家清單 📦✅")
    assert meta["dropped_glyphs"] == 2


def test_markdown_and_quotes_are_cleaned() -> None:
    assert polaroid.clean_caption("## 「寫一封信」。\n理由") == "寫一封信"
    assert polaroid.clean_caption(None) == ""
    # 句中那一對引號是分身自己打的，不准剝掉半個（v2 修掉的 bug：「週末登山清單 少了 」）
    assert polaroid.clean_caption(AGENT_LINE) == "我決定整理一份「週末登山清單」"
    assert polaroid.clean_caption("「只有開引號") == "只有開引號"


def _ink_in(png: bytes, box) -> int:
    """那一格裡有幾個「墨色」像素（紙色亮度 > 200、墨色 < 120）。"""
    im = Image.open(io.BytesIO(png)).convert("L").crop(tuple(box))
    return sum(im.histogram()[:120])


def test_verbatim_copy_of_the_viewer_text_leaves_the_line_blank() -> None:
    """拍立得上不准出現可識別本人的原文：分身的句子逐字抄了觀眾 8 個字以上 ⇒ **那一行留空**。
    2026-09-26 人類：字要是 agent 生成的 ⇒ 不准換成任何人寫的句子（舊版的中性句已拿掉）。"""
    originals = polaroid.originals_of({"need": NEED}, TRAITS_TEXT)
    leak = "最近一直想寫信給國小導師"                    # TRAITS_TEXT 的連續 12 個字
    png, meta = _compose(leak, originals=originals)
    assert meta["caption_redacted"] is True and meta["caption_blank"] is True
    assert meta["caption_chars"] == 0 and meta["caption_drawn"] is None
    assert _ink_in(png, meta["caption_box"]) == 0                # 那一格真的沒有字
    assert not hasattr(polaroid, "NEUTRAL_CAPTION")
    # 負控制：只共用「國小導師」四個字的正常決定**不會**被誤殺，而且那一格量得到墨色
    png2, meta2 = _compose(DECISION, originals=originals)
    assert meta2["caption_redacted"] is False and meta2["caption_blank"] is False
    assert _ink_in(png2, meta2["caption_box"]) > 500
    assert polaroid.caption_leaks_original(leak, originals)
    assert not polaroid.caption_leaks_original(DECISION, originals)


def test_qr_is_the_site_and_only_the_site() -> None:
    assert polaroid.SITE_URL == "https://vacant.cosmopig.com"
    assert "?" not in polaroid.SITE_URL and "#" not in polaroid.SITE_URL


def _read_modules(png: bytes, meta: dict) -> list[list[int]]:
    im = Image.open(io.BytesIO(png)).convert("L")
    x0, y0, mod, n = meta["qr_box"][0], meta["qr_box"][1], meta["qr_module_px"], meta["qr_modules"]
    return [[1 if im.getpixel((x0 + c * mod + mod // 2, y0 + r * mod + mod // 2)) < 128 else 0
             for c in range(n)] for r in range(n)]


def test_qr_drawn_in_the_png_is_the_site_matrix() -> None:
    """不靠解碼器：從 PNG 的像素把模組讀回來，逐格等於官網網址的矩陣
    （`qr.matrix` 本身對 segno 逐 bit 相同，見 tests/test_qr.py）。"""
    png, meta = _compose()
    got = _read_modules(png, meta)
    assert got == qr.matrix(polaroid.SITE_URL)
    # 負控制：換一個網址，矩陣就不一樣（這個比法分得出內容）
    assert got != qr.matrix("https://vacant.cosmopig.com/?id=x")
    # 靜區是亮的（四個模組寬）
    im = Image.open(io.BytesIO(png)).convert("L")
    q = meta["qr_quiet_box"]
    edge = [im.getpixel((x, q[1] + 2)) for x in range(q[0], q[2], 3)]
    assert min(edge) > 200


def test_qr_decodes_with_an_external_decoder() -> None:
    cv2 = pytest.importorskip("cv2", reason="沒有 OpenCV ⇒ 外部解碼這一格沒有被驗過"
                                            "（證據檔 evidence_polaroid_20260926/v2/qr_decode.json 是開發機跑的）")
    import numpy as np
    png, _ = _compose()
    arr = cv2.cvtColor(np.array(Image.open(io.BytesIO(png)).convert("RGB")), cv2.COLOR_RGB2BGR)
    text, _, _ = cv2.QRCodeDetector().detectAndDecode(arr)
    assert text == polaroid.SITE_URL


def test_evidence_decode_report_says_what_it_says() -> None:
    d = json.loads((EVID / "qr_decode.json").read_text(encoding="utf-8"))
    assert d["expect"] == polaroid.SITE_URL and d["all_ok"] is True
    samples = json.loads((EVID / "samples.json").read_text(encoding="utf-8"))
    by_file = {s["file"]: s for s in samples["samples"]}
    assert set(by_file) == {r["file"] for r in d["results"]}
    for r in d["results"]:
        c = r["cases"]
        assert c["original"]["decoded"] == polaroid.SITE_URL
        assert c["share_thumb"]["decoded"] == polaroid.SITE_URL
        assert c["phone_photo_10cm"]["ok"] is True and c["phone_photo_15cm"]["ok"] is True
        assert c["neg_blanked"]["decoded"] is None               # 負控制：塗掉就解不出
        assert c["neg_other_url"]["not_site"] is True            # 負控制：別的網址解成別的網址
        # 報告講的是**現在這幾張檔**（雜湊對得上），不是別的版本
        p = EVID / r["file"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == r["sha256"] == by_file[r["file"]]["sha256"]
    assert all(s["synthetic"] for s in samples["samples"])
    # QR 模組大小的依據：採用值在 15 cm 全過、下一級（8 px）在這個相框上不是全過
    sw = json.loads((EVID / "qr_sweep.json").read_text(encoding="utf-8"))["rows"]

    def rate(m, dcm):
        rows = [x for x in sw if x["module_px"] == m and x["distance_cm"] == dcm]
        return sum(x["decoded"] for x in rows), sum(x["of"] for x in rows)
    ok, n = rate(polaroid.QR_MODULE_PX, 15)
    assert n > 0 and ok == n
    ok8, n8 = rate(polaroid.QR_MODULE_PX - 1, 15)
    assert ok8 < n8


def test_samples_are_real_agent_runs_not_hand_written() -> None:
    """範例上那一句＝分身真跑一次自己寫的 PLAN.md 第一行（人類 2026-09-26）。
    逐張對回 `runs.json`：engine 是 `vacant_run:pi:*`、有 run_id 與收據鏈頭、收據驗過。"""
    runs = {r["name"]: r for r in json.loads((EVID / "runs.json").read_text(encoding="utf-8"))["runs"]}
    samples = json.loads((EVID / "samples.json").read_text(encoding="utf-8"))
    assert len(samples["samples"]) >= 4
    for s in samples["samples"]:
        r = runs[s["persona"]]
        tw = r["twin"]
        assert r["made"] is True and r["synthetic"] is True and "不是真人" in r["card_text"]
        assert s["decision_by_agent"] == tw["decision"]
        assert tw["decision"] == twinagent.parse_plan(r["plan_md"])[0]   # 就是它寫的第一行
        assert s["engine"] == tw["engine"] and tw["engine"].startswith("vacant_run:pi:")
        assert s["run_id"] == tw["run_id"] and len(tw["run_id"]) == 32
        assert s["verdict_hash"] == tw["verdict_hash"] and s["receipt_short"] == tw["verdict_hash"][:8]
        assert [x["verdict"] for x in r["receipts"]] == ["OK"] and r["receipts"][0]["chain_ok"]
        assert r["wire"]["requests"] >= 1 and tw["requests_seen"] == r["wire"]["requests"]
        assert s["cast_id"] == polaroid.pick_cast_for(r["card"])
        # v2 是 2026-09-26 稍早（只有 10 位有姿勢圖時）合成的；比對「那時候記下來的 figure」
        # 對不對，不能拿**現在**（其餘 24 位上架後）的 figure_for() 活函數比——c08／c38 這兩位
        # 就是這一輪才多了姿勢圖，historical meta 說 cast40 是對的，不是漂了。
        assert s["meta"]["figure"] == ("pose" if s["cast_id"] in _V2_POSE_IDS_AT_GENERATION else "cast40")
    figs = {s["meta"]["figure"] for s in samples["samples"]}
    assert figs == {"pose", "cast40"}, figs                        # 兩種都涵蓋
    # 人寫的範例句不准回來
    assert not hasattr(polaroid, "SAMPLES")
    for s in samples["samples"]:
        assert s["decision_by_agent"] not in ("寫一封謝卡給國小導師", "整理一份給自己的睡前閱讀清單")


# ---------------------------------------------------------------------------
# 一之二、素材：真相框、黏土世界背景、姿勢圖（只認自己的檔名）
# ---------------------------------------------------------------------------

ASSET_SRC = pathlib.Path("/Users/cosmopig/Documents/GitHub/vacant_hm-assets-20260926")


def test_real_frame_is_used_and_fits_the_4_5_card() -> None:
    png, meta = _compose()
    assert meta["frame"].startswith("file:b2faf31d6747") and meta["frame_note"] is None
    assert Image.open(io.BytesIO(png)).size == (1080, 1350)
    assert meta["frame_fit"]["extend_px"] > 0                   # 下緣白邊往下延長，不是壓扁
    fj = json.loads((polaroid.DEFAULT_FRAME_DIR / "polaroid_frame.json").read_text(encoding="utf-8"))
    assert hashlib.sha256((polaroid.DEFAULT_FRAME_DIR / "polaroid_frame.png").read_bytes()
                          ).hexdigest() == fj["sha256"]
    # 相片窗仍是素材那個比例（730:686），沒有被拉歪
    w = meta["window"]
    assert abs((w[2] - w[0]) / (w[3] - w[1]) - 730 / 686) < 0.01
    # 窗格四周是相框的紙（亮），窗格裡是相片（暗）：墊圖真的墊在窗格底下
    im = Image.open(io.BytesIO(png)).convert("L")
    assert im.getpixel((w[0] - 6, (w[1] + w[3]) // 2)) > 200
    assert im.getpixel((w[0] + 12, w[1] + 12)) < 120
    if (ASSET_SRC / "polaroid").is_dir():
        for n in ("polaroid_frame.png", "polaroid_frame.json"):
            assert (polaroid.DEFAULT_FRAME_DIR / n).read_bytes() == (ASSET_SRC / "polaroid" / n).read_bytes()


def test_frame_that_does_not_fit_falls_back_to_placeholder_with_a_reason(tmp_path) -> None:
    """負控制：相框 json 沒有窗、或窗大到下緣沒有白邊 ⇒ 退回佔位相框，frame_note 講為什麼。"""
    src = polaroid.DEFAULT_FRAME_DIR
    (tmp_path / "polaroid_frame.png").write_bytes((src / "polaroid_frame.png").read_bytes())
    (tmp_path / "polaroid_frame.json").write_text('{"note": "no window"}', encoding="utf-8")
    _png, meta = _compose(frame_dir=tmp_path)
    assert meta["frame"] == "placeholder" and meta["frame_note"].startswith("frame_rejected")
    (tmp_path / "polaroid_frame.json").write_text(
        '{"window_px": {"x": 50, "y": 60, "w": 730, "h": 860}}', encoding="utf-8")
    _png, meta = _compose(frame_dir=tmp_path)
    assert meta["frame"] == "placeholder" and "frame_rejected" in meta["frame_note"]


def test_plate_is_pinned_and_has_no_text_or_qr_baked_in() -> None:
    assert hashlib.sha256(polaroid.PLATE_PATH.read_bytes()).hexdigest() == polaroid.PLATE_SHA256
    pj = json.loads(polaroid.PLATE_PATH.with_suffix(".json").read_text(encoding="utf-8"))
    assert pj["sha256"] == polaroid.PLATE_SHA256 and pj["spot_x_px"] == polaroid.PLATE_SPOT_X


# 2026-09-26 晚：素材線把其餘 24 位（cast40 扣掉班底 6 位 c01/c03/c13/c20/c22/c37）也上架了；
# c09／c10／c31 是 eyefix 輪之後的新版（sha256 已經換過，見 assets/poses/manifest.json）。
POSE_IDS = tuple(f"c{i:02d}" for i in range(1, 41)
                 if f"c{i:02d}" not in {"c01", "c03", "c13", "c20", "c22", "c37"})


def test_poses_are_used_for_the_thirty_four_that_have_them_and_nobody_else() -> None:
    have = sorted(p.name[:3] for p in polaroid.DEFAULT_POSES_DIR.glob("c*_show.png"))
    assert tuple(have) == POSE_IDS
    man = json.loads((polaroid.DEFAULT_POSES_DIR / "manifest.json").read_text(encoding="utf-8"))
    for cid in (f"c{i:02d}" for i in range(1, 41)):
        path, kind = polaroid.figure_for(cid)
        if cid in POSE_IDS:
            assert kind == "pose" and path.name == f"{cid}_show.png"
            assert hashlib.sha256(path.read_bytes()).hexdigest() == man["items"][f"{cid}_show"]["sha256"]
        else:
            assert kind == "cast40" and path == polaroid.CAST_DIR / f"{cid}.png"   # 同一位的原圖
        assert path.name.startswith(cid)                         # 永遠是自己的臉


def test_missing_pose_never_borrows_someone_elses_face(tmp_path) -> None:
    """負控制：姿勢資料夾裡只有 c02 的圖，c03 要的時候**不准**拿 c02 頂替，
    連「c03_show.png 其實是指向 c02_show.png 的連結」也不認。"""
    import os as _os
    shutil.copyfile(polaroid.DEFAULT_POSES_DIR / "c02_show.png", tmp_path / "c02_show.png")
    empty = tmp_path / "empty"
    empty.mkdir()
    p, kind = polaroid.figure_for("c03", tmp_path)
    assert kind == "cast40" and p.name == "c03.png"
    a, _ = polaroid.render_scene("c03", (400, 380), poses_dir=tmp_path)
    b, _ = polaroid.render_scene("c03", (400, 380), poses_dir=empty)
    assert a.tobytes() == b.tobytes()                            # c02 的圖在不在，c03 的相片都一樣
    c, info = polaroid.render_scene("c02", (400, 380), poses_dir=tmp_path)
    assert info["figure"] == "pose" and c.tobytes() != b.tobytes()   # 量具分得出「用了姿勢圖」
    _os.symlink(tmp_path / "c02_show.png", tmp_path / "c03_show.png")
    p, kind = polaroid.figure_for("c03", tmp_path)
    assert kind == "cast40" and p.name == "c03.png"
    with pytest.raises(polaroid.PolaroidError):
        polaroid.figure_for("../c02", tmp_path)


def test_detached_specks_in_cast40_are_not_pasted_onto_the_stage() -> None:
    """cast40 的 c20 左緣有一塊脫離本體的碎屑（365 px）；貼到深色舞台上會變一條白線。"""
    from PIL import Image as _I
    spr = _I.open(polaroid.CAST_DIR / "c20.png").convert("RGBA")
    assert spr.getchannel("A").crop((0, 110, 11, 154)).getextrema()[1] > 32      # 碎屑真的在
    clean = polaroid._drop_specks(spr)
    assert clean.getchannel("A").crop((0, 110, 11, 154)).getextrema()[1] <= 32
    # 本體不受影響
    assert clean.getchannel("A").getbbox()[2] >= spr.width - 12


# ---------------------------------------------------------------------------
# 二、cast_id 單一來源：後端 == 電視前端 pickCastFor
# ---------------------------------------------------------------------------

def test_pick_cast_for_known_values() -> None:
    # 圓潤＋暖土＋光滑：c01 與 c08 同分，顏色錨點距離 c08 近（222 < 1994）
    assert polaroid.pick_cast_for({"shape": "圓潤", "color": "暖土", "texture": "光滑"}) == "c08"
    assert polaroid.pick_cast_for({}) == polaroid.pick_cast_for(None) == "c01"


def _frontend() -> tuple[pathlib.Path, pathlib.Path] | None:
    env = os.environ.get("VACANT_HM_DIR")
    cands = [pathlib.Path(env)] if env else []
    for p in [ROOT, *ROOT.parents]:
        cands.append(p.parent / "vacant_hm")
    for c in cands:
        page = c / "world3" / "index.html"
        man = c / "world2" / "sprites" / "cast40" / "manifest.json"
        if page.is_file() and man.is_file():
            return page, man
    return None


def _node_parity(tmp_path, tie: str) -> subprocess.CompletedProcess:
    fe = _frontend()
    if fe is None or shutil.which("node") is None:
        pytest.skip("找不到 vacant_hm（設 VACANT_HM_DIR）或 node ⇒ 前後端對照**沒有被驗過**")
    table = tmp_path / f"par_{tie}.json"
    subprocess.run([sys.executable, str(ROOT / "ops/exhibit/twin/polaroid.py"), "parity-table",
                    "--tie", tie, "--out", str(table)], check=True, capture_output=True)
    return subprocess.run(["node", str(ROOT / "ops/exhibit/twin/cast_parity_node_check.mjs"),
                           str(fe[0]), str(fe[1]), str(table)],
                          capture_output=True, text=True, timeout=60)


def test_cast_id_matches_frontend_pick_cast_for_one_by_one(tmp_path) -> None:
    r = _node_parity(tmp_path, "first")
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert r.returncode == 0 and out["mismatches"] == 0, r.stdout + r.stderr
    # 全表：形狀 6＋3 種怪值＋缺鍵、色系同、質感 4＋3＋缺鍵 ⇒ 10×10×8
    assert out["n"] == 800 and out["manifest_entries"] == 40


def test_cast_id_parity_negative_control_catches_a_wrong_tie_rule(tmp_path) -> None:
    """負控制：把平手規則改錯（取最後一個），對照必須紅——證明它不是恆綠。"""
    r = _node_parity(tmp_path, "last")
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert r.returncode == 1 and out["mismatches"] > 0


def test_vendored_manifest_is_byte_identical_to_the_frontend() -> None:
    mine = (polaroid.CAST_DIR / "manifest.json").read_bytes()
    assert hashlib.sha256(mine).hexdigest() == polaroid.MANIFEST_SHA256
    fe = _frontend()
    if fe is None:
        pytest.skip("找不到 vacant_hm ⇒ 附帶的 manifest 與電視那份沒有對照過")
    assert fe[1].read_bytes() == mine
    for i in range(1, 41):
        name = f"c{i:02d}.png"
        assert (polaroid.CAST_DIR / name).read_bytes() == (fe[1].parent / name).read_bytes(), name


# ---------------------------------------------------------------------------
# 三、產品路徑：生成 → 拍立得 → 送到手機 → 撤回
# ---------------------------------------------------------------------------

def _made(env, monkeypatch) -> tuple:
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    r = twinlink.generate(st, env["upstream"], "m", agent=cfg)
    assert r["generated"] == 1 and r["degraded"] == 0, r
    return st, cfg, sid


def _capture_publish(monkeypatch) -> list[dict]:
    sent: list[dict] = []

    def fake(url, payload=None, timeout=30.0, headers=None):  # noqa: ANN001
        sent.append({"url": url, "payload": payload})
        return 200, {"ok": True}
    monkeypatch.setattr(twinlink, "_http_json", fake)
    return sent


def test_made_run_gets_a_polaroid_in_the_vault_and_only_a_marker_on_chain(env, monkeypatch) -> None:
    st, _cfg, sid = _made(env, monkeypatch)
    out = twinlink.polaroids(st)
    assert out.get("made") == 1, out
    png = st.vault.open_polaroid(sid)
    assert png and png.startswith(b"\x89PNG")
    notes = [e["payload"] for e in st.events(sub_id=sid, kind=KIND_NOTE)
             if e["payload"].get("twinlink_event") == twinlink.POLAROID_MADE]
    assert len(notes) == 1 and notes[0]["qr_text"] == polaroid.SITE_URL
    # 鏈上只有「做了一張」：那句話、特質都不在鏈上
    blob = _chain_blob(st)
    for secret in (DECISION, TRAITS_TEXT, NEED):
        assert secret not in blob
    # 冪等：再跑一次不會多做一張
    assert twinlink.polaroids(st)["todo"] == 0
    # 電視、拍立得、手機同一張臉
    view = twinlink.build_view(st)
    assert view["people"][0]["cast_id"] == notes[0]["cast_id"] \
        == polaroid.pick_cast_for(st.current(sid)["card"])


def test_publish_sends_polaroid_and_hash_only_receipt(env, monkeypatch) -> None:
    st, cfg, sid = _made(env, monkeypatch)
    twinlink.polaroids(st)
    sent = _capture_publish(monkeypatch)
    r = twinlink.publish(st, "http://cloud.invalid", "t")
    assert r["published"] == 1, r
    body = sent[0]["payload"]
    assert body["outcome"] == "made"
    assert base64.b64decode(body["polaroid_png"].split(",", 1)[1]) == st.vault.open_polaroid(sid)
    rc = body["receipt"]
    tw = st.current(sid)["twin"]
    assert rc["head"] == tw["verdict_hash"] and rc["n"] == 2
    # 收據只有雜湊與計數：原文、sub_id 一個都不在裡面
    txt = json.dumps(rc, ensure_ascii=False)
    for bad in (TRAITS_TEXT, NEED, DECISION, LETTER, sid):
        assert bad not in txt
    twinagent.check_receipt_shape(rc["entries"], rc["pub"])
    pub = [e["payload"] for e in st.events(sub_id=sid, kind=KIND_PUBLISHED)][-1]
    assert pub["polaroid"] is True and pub["receipt"] == "sent" and pub["outcome"] == "made"


def test_receipt_with_an_unknown_field_is_not_sent(env, monkeypatch) -> None:
    """白名單不是黑名單：收據裡多一個不認得的欄位（例如有人把原文塞進去）⇒ 整份不發。"""
    st, cfg, sid = _made(env, monkeypatch)
    _ws, rd = twinagent.paths_for(cfg.work_root, sid)
    p = rd / "receipts_RUN-ON.ndjson"
    lines = p.read_text(encoding="utf-8").splitlines()
    e = json.loads(lines[-1])
    e["payload"]["note"] = TRAITS_TEXT
    lines[-1] = json.dumps(e, ensure_ascii=False)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rb = twinagent.receipt_bundle(cfg.work_root, sid)
    assert rb["ok"] is False and rb["why"] == "shape_rejected"
    sent = _capture_publish(monkeypatch)
    twinlink.publish(st, "http://cloud.invalid", "t")
    assert "receipt" not in sent[0]["payload"]
    assert TRAITS_TEXT not in json.dumps(sent[0]["payload"], ensure_ascii=False)


def test_receipt_head_must_match_the_polaroid(env, monkeypatch) -> None:
    st, cfg, sid = _made(env, monkeypatch)
    assert twinagent.receipt_bundle(cfg.work_root, sid, expect_head="0" * 64)["why"] \
        == "head_mismatch"
    # 正控制：對的鏈頭就發
    tw = st.current(sid)["twin"]
    assert twinagent.receipt_bundle(cfg.work_root, sid, expect_head=tw["verdict_hash"])["ok"]


def test_broken_run_gets_no_polaroid_and_the_phone_is_told(env, monkeypatch) -> None:
    """基建壞了（這一跑沒有打到模型）⇒ 不發拍立得，手機上照實說「這一次沒有做成」。"""
    st, cfg = env["store"], env["cfg"]
    monkeypatch.setenv("TWIN_FIXTURE_MODE", "silent")
    sid = _ingest(st, monkeypatch)
    twinlink.generate(st, env["upstream"], "m", agent=cfg)
    assert st.current(sid)["twin"]["engine"] == "fallback_deterministic"
    out = twinlink.polaroids(st)
    assert out.get("skipped") == 1 and not out.get("made")
    assert st.vault.open_polaroid(sid) is None
    sent = _capture_publish(monkeypatch)
    twinlink.publish(st, "http://cloud.invalid", "t")
    body = sent[0]["payload"]
    assert body["outcome"] == "not_made"
    assert "polaroid_png" not in body and "receipt" not in body


def test_no_pillow_means_no_polaroid_and_no_chain_row_then_catches_up(env, monkeypatch) -> None:
    st, _cfg, sid = _made(env, monkeypatch)
    monkeypatch.setattr(polaroid, "available", lambda: (False, "pillow_missing：測試"))
    out = twinlink.polaroids(st)
    assert out.get("unavailable") == 1 and "pillow_missing" in out["unavailable_why"]
    assert twinlink.polaroid_state(st, sid) is None, "做不出來不准寫鏈（裝好之後要補得回來）"
    monkeypatch.undo()
    assert twinlink.polaroids(st).get("made") == 1


def test_withdraw_erases_the_polaroid_and_the_proof_lists_it(env, monkeypatch) -> None:
    st, _cfg, sid = _made(env, monkeypatch)
    twinlink.polaroids(st)
    png = st.vault.open_polaroid(sid)
    path = st.vault.plain_dir / twinvault.slug_for(sid) / "polaroid.png"
    assert path.is_file()
    out = twinlink.withdraw(st, sid)
    assert out["ok"] and not path.exists() and st.vault.open_polaroid(sid) is None
    refs = {e["ref"]: e for e in out["erased"]}
    ref = st.vault.ref(sid, "polaroid.png")
    assert ref in refs and refs[ref]["sha256"] == hashlib.sha256(png).hexdigest()
    # 簽章鏈的 PERSONA_ERASED 也列了它
    audit = st.vault.audit()
    assert ref in audit["subjects"][sid]["erased_refs"]
    # 撤回之後：不再回寫、畫面上沒有臉
    sent = _capture_publish(monkeypatch)
    twinlink.publish(st, "http://cloud.invalid", "t")
    assert sent == []
    assert twinlink.build_view(st)["people"][0]["cast_id"] is None


def test_withdrawn_while_drawing_leaves_no_polaroid_behind(env, monkeypatch) -> None:
    """畫到一半被撤回（serve 那個行程刪了檔案庫）⇒ 剛寫下去的圖當場刪掉。"""
    st, _cfg, sid = _made(env, monkeypatch)
    real = polaroid.compose

    def compose_then_withdrawn(**kw):
        out = real(**kw)
        twinlink.withdraw(st, sid)
        return out
    monkeypatch.setattr(polaroid, "compose", compose_then_withdrawn)
    r = twinlink.make_polaroid(st, sid)
    assert r["state"] == "gone"
    assert not (st.vault.plain_dir / twinvault.slug_for(sid) / "polaroid.png").exists()
    ev = [e["payload"]["twinlink_event"] for e in st.events(sub_id=sid, kind=KIND_NOTE)]
    assert twinlink.LATE_POLAROID_DISCARDED in ev and twinlink.POLAROID_MADE not in ev


def test_cloud_withdrawal_carries_the_cloud_erasure_into_the_proof(env, monkeypatch) -> None:
    """手機上撤回：雲端先刪（含拍立得、收據副本），ingest 帶回來 ⇒ 本機抹除證明列得出來。"""
    st, _cfg, sid = _made(env, monkeypatch)
    twinlink.polaroids(st)

    def fake(url, payload=None, timeout=30.0, headers=None):  # noqa: ANN001
        return 200, {"items": [{"id": sid, "status": "withdrawn", "card": None}],
                     "withdrawals": [{"id": sid, "erased": [
                         {"ref": "card_text", "bytes_n": 30},
                         {"ref": f"polaroids/{sid}.png", "bytes_n": 1234},
                         {"ref": f"receipts/{sid}.json", "bytes_n": 99}],
                         "chain_plaintext_remains": False}]}
    monkeypatch.setattr(twinlink, "_http_json", fake)
    twinlink.ingest(st, "http://cloud.invalid", "t")
    er = [e["payload"] for e in st.events(sub_id=sid, kind=KIND_ERASED)][-1]
    cc = er["cloud_copy"]
    assert cc["by"] == "cloud"
    assert {"ref": "polaroids/<id>.png", "bytes_n": 1234} in cc["erased"]
    assert sid not in json.dumps(cc), "抹除證明的內容不再抄一次撤回的鑰匙"
    assert st.vault.open_polaroid(sid) is None
    # 雲端自己刪的，loop 不會再送一次
    calls = []
    monkeypatch.setattr(twinlink, "_http_json",
                        lambda *a, **k: calls.append(a) or (200, {}))
    assert twinlink.sync_cloud_erasure(st, "http://cloud.invalid", "t")["confirmed"] == 0
    assert calls == []


def test_local_withdrawal_is_sent_to_the_cloud_and_recorded(env, monkeypatch) -> None:
    """會場撤回（紙本／serve）：loop 下一輪用工作人員路徑刪雲端那一份，記一列 cloud_erased。"""
    st, _cfg, sid = _made(env, monkeypatch)
    twinlink.withdraw(st, sid)
    er = [e["payload"] for e in st.events(sub_id=sid, kind=KIND_ERASED)][-1]
    assert er["cloud_copy"] == "not_attempted_no_endpoint"
    calls = []

    def fake(url, payload=None, timeout=30.0, headers=None):  # noqa: ANN001
        calls.append((url, payload))
        return 200, {"ok": True, "already": False, "erased": [
            {"ref": "card_text", "bytes_n": 30}, {"ref": f"polaroids/{sid}.png", "bytes_n": 9}]}
    monkeypatch.setattr(twinlink, "_http_json", fake)
    r = twinlink.sync_cloud_erasure(st, "http://cloud.invalid", "t")
    assert r["confirmed"] == 1
    assert calls[0][0].endswith("/api/withdraw") and calls[0][1] == {"id": sid, "token": "t"}
    note = [e["payload"] for e in st.events(sub_id=sid, kind=KIND_NOTE)
            if e["payload"].get("twinlink_event") == twinlink.CLOUD_ERASED][-1]
    assert {"ref": "polaroids/<id>.png", "bytes_n": 9} in note["erased"]
    # 冪等：下一輪不再送
    calls.clear()
    assert twinlink.sync_cloud_erasure(st, "http://cloud.invalid", "t")["confirmed"] == 0
    assert calls == []


def test_local_withdrawal_retries_when_the_cloud_is_unreachable(env, monkeypatch) -> None:
    """負控制：連不上 ⇒ **不寫鏈**、下一輪再試（不准把「沒送到」記成「刪了」）。"""
    st, _cfg, sid = _made(env, monkeypatch)
    twinlink.withdraw(st, sid)

    def down(*a, **k):  # noqa: ANN001
        raise OSError("down")
    monkeypatch.setattr(twinlink, "_http_json", down)
    r = twinlink.sync_cloud_erasure(st, "http://cloud.invalid", "t")
    assert r["failed"] == 1 and r["confirmed"] == 0
    assert not [e for e in st.events(sub_id=sid, kind=KIND_NOTE)
                if e["payload"].get("twinlink_event") == twinlink.CLOUD_ERASED]


def test_loop_cli_runs_polaroid_before_publish() -> None:
    """產品路徑接上了：loop 的每一輪在 publish **之前**做拍立得（同一輪收成、同一輪送到手機）。"""
    src = (ROOT / "ops/exhibit/twin/twinlink.py").read_text(encoding="utf-8")
    body = src[src.index('if a.cmd == "loop":'):]
    assert body.index('r["polaroid"] = polaroids(st)') < body.index('r["publish"] = publish(')
    assert 'r["cloud_erase"] = sync_cloud_erasure(' in body


# ---------------------------------------------------------------------------
# 四、「自己驗收據」那一頁的驗證邏輯＝twin_viewer 逐字相同
# ---------------------------------------------------------------------------

def _cloud_receipt_pages() -> list[pathlib.Path]:
    env = os.environ.get("VACANT_CLOUD_DIR")
    found: list[pathlib.Path] = []
    if env and (pathlib.Path(env) / "public" / "receipt.html").is_file():
        found.append(pathlib.Path(env) / "public" / "receipt.html")
    for p in [ROOT, *ROOT.parents]:
        found += sorted(p.parent.glob("vacant-world-cloud*/public/receipt.html"))
    return list(dict.fromkeys(found))


def test_cloud_receipt_page_uses_the_viewer_logic_verbatim(tmp_path) -> None:
    pages = _cloud_receipt_pages()
    if not pages:
        pytest.skip("找不到有 receipt.html 的 vacant-world-cloud（設 VACANT_CLOUD_DIR）⇒ 逐字相同**沒有被驗過**")
    tool = ROOT / "ops/exhibit/twin/sync_receipt_logic.py"
    for page in pages:
        r = subprocess.run([sys.executable, str(tool), str(page), "--check"],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"{page}\n{r.stdout}{r.stderr}"
    # 負控制：抄一份、改 LOGIC 裡一個字 ⇒ --check 必須紅
    bad = tmp_path / "receipt.html"
    html = pages[0].read_text(encoding="utf-8")
    i = html.index("/* === LOGIC-BEGIN ===")
    j = html.index("function verifyChain", i)
    bad.write_text(html[:j] + "function verifyChainX" + html[j + len("function verifyChain"):],
                   encoding="utf-8")
    r = subprocess.run([sys.executable, str(tool), str(bad), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "對不上" in r.stdout
