"""P11：拍立得每個人不一樣——拼貼層的整合測試（假素材，不依賴真素材與 Codex）。

驗：確定性、QR 位置與解碼不變、貼紙不壓字／靜區、素材缺／壞一律退回單一相框版、沒命盤也出、
meta 不洩 sub_id／命盤原值。挑選函式本身的單元測試在 `test_polaroid_layers.py`。
"""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
import shutil
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PIL = pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

from ops.exhibit.twin import polaroid  # noqa: E402
from ops.exhibit.twin import polaroid_layers as L  # noqa: E402

CARD = dict(decision="今天先把信寫好再收進抽屜", cast_id="c01", date_str="2026.10.02",
            receipt_short="0123abcd")
FORT = {"mbti": "INFP", "zodiac": "雙魚", "blood": "AB"}
HINT = {"place": "chain", "kind": "tile"}


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _blob(path: pathlib.Path, color, size=(160, 140), shape="ellipse") -> None:
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    box = [6, 6, size[0] - 7, size[1] - 7]
    (d.ellipse if shape == "ellipse" else d.rectangle)(box, fill=color + (255,))
    im.save(path)


def make_assets(root: pathlib.Path) -> pathlib.Path:
    d = root / "v2"
    for sub in ("bg", "frames", "stickers", "props"):
        (d / sub).mkdir(parents=True)

    def ent(sub: str, name: str) -> dict:
        return {"file": f"{sub}/{name}", "sha256": _sha(d / sub / name)}

    man: dict = {"version": 2, "backgrounds": {}, "frames": {}, "props": {},
                 "stickers": {"mbti": {}, "zodiac": {}, "blood": []}}
    for pi, place in enumerate(L.PLACES):
        for n in (1, 2):
            Image.new("RGB", (256, 256), (30 + pi * 20, 60 + n * 30, 40)).save(d / "bg" / f"{place}{n}.jpg")
            man["backgrounds"].setdefault(place, []).append(ent("bg", f"{place}{n}.jpg"))
    src_png = polaroid.DEFAULT_FRAME_DIR / "polaroid_frame.png"
    src_js = polaroid.DEFAULT_FRAME_DIR / "polaroid_frame.json"
    for ei, el in enumerate(("fire", "earth", "air", "water", "neutral")):
        for n in (1, 2):
            name = f"frame_{el}_{n}"
            im = Image.open(src_png).convert("RGBA")
            tint = Image.new("RGBA", im.size, (255 - ei * 8, 250 - n * 10, 240 - ei * 6, 255))
            Image.alpha_composite(im, Image.blend(Image.new("RGBA", im.size, (0, 0, 0, 0)), tint, 0.0)) \
                if False else None
            r, g, b, a = im.split()
            rgb = Image.merge("RGB", (r, g, b))
            rgb = Image.blend(rgb, tint.convert("RGB"), 0.25)
            Image.merge("RGBA", (*rgb.split(), a)).save(d / "frames" / f"{name}.png")
            shutil.copy(src_js, d / "frames" / f"{name}.json")
            e = ent("frames", f"{name}.png")
            e["json"] = f"frames/{name}.json"
            man["frames"].setdefault(el, []).append(e)
    colors = [(200, 80, 60), (60, 120, 200), (220, 180, 40), (120, 160, 80)]
    for t, tc in zip(("NT", "NF", "SJ", "SP"), range(4)):
        for n in range(4):
            nm = f"mbti_{t}{n}.png"
            _blob(d / "stickers" / nm, colors[(tc + n) % 4])
            man["stickers"]["mbti"].setdefault(t, []).append(ent("stickers", nm))
    for zi, z in enumerate(L.ZODIACS):
        nm = f"zod{zi}.png"
        _blob(d / "stickers" / nm, colors[zi % 4], shape="rect")
        man["stickers"]["zodiac"][z] = ent("stickers", nm)
    for si, sh in enumerate(("round", "square", "scallop", "oval")):
        for tone in ("red", "blue"):
            nm = f"stamp_{sh}_{tone}.png"
            _blob(d / "stickers" / nm, (170, 70, 50) if tone == "red" else (50, 70, 140), size=(180, 180))
            man["stickers"]["blood"].append({**ent("stickers", nm), "shape": sh, "tone": tone})
    for k in L.PROP_KINDS:
        for n in (1, 2):
            nm = f"{k}{n}.png"
            _blob(d / "props" / nm, (210, 190, 150), size=(200, 140), shape="rect")
            man["props"].setdefault(k, []).append(ent("props", nm))
    man["version"] = 2
    (d / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
    return d


@pytest.fixture()
def v2(tmp_path, monkeypatch):
    d = make_assets(tmp_path)
    monkeypatch.setenv(L.V2_ENV, str(d))
    return d


def comp(sub_id="sid-1", **kw):
    args = dict(CARD, sub_id=sub_id, hints=HINT, fortune=FORT)
    args.update(kw)
    return polaroid.compose(**args)


def legacy():
    return polaroid.compose(**CARD)


def test_variety_applies_and_keeps_the_layout(v2) -> None:
    png, meta = comp()
    _, base = legacy()
    var = meta["variety"]
    assert var is not None and var["fallbacks"] == []
    assert var["spec"].get("background") and var["spec"].get("frame")
    assert len(var["stickers"]) >= 2
    for k in ("window", "caption_box", "footer_box", "qr_box", "qr_quiet_box", "qr_module_px", "size"):
        assert meta[k] == base[k], k


def test_deterministic_and_people_differ(v2) -> None:
    a1, _ = comp("p-1")
    a2, _ = comp("p-1")
    assert a1 == a2
    shas = {hashlib.sha256(comp(f"p-{i}")[0]).hexdigest() for i in range(8)}
    assert len(shas) >= 4


def test_stickers_never_touch_text_or_qr_quiet_zone(v2) -> None:
    for i in range(12):
        _, m = comp(f"q-{i}", fortune_line="火象 · 愛思考", fortune_sentence="先看過才動手")
        for s in m["variety"]["stickers"]:
            for k in ("caption_box", "footer_box", "qr_quiet_box"):
                assert not polaroid._overlap(tuple(s["box"]), tuple(m[k])), (s, k)
            band = (m["caption_box"][0], m["window"][3] + 4, m["caption_box"][2], m["caption_box"][1] - 2)
            assert not polaroid._overlap(tuple(s["box"]), band)


def test_qr_still_decodes_with_everything_on(v2) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    for i in range(6):
        png, m = comp(f"d-{i}")
        arr = cv2.cvtColor(np.array(Image.open(io.BytesIO(png)).convert("RGB")), cv2.COLOR_RGB2BGR)
        text, _, _ = cv2.QRCodeDetector().detectAndDecode(arr)
        assert text == polaroid.SITE_URL, (i, m["variety"])


def test_no_assets_falls_back_to_the_single_frame_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(L.V2_ENV, str(tmp_path / "nothing"))
    png, meta = comp()
    png0, _ = legacy()
    assert meta["variety"] is None and png == png0


def test_off_switch(v2, monkeypatch) -> None:
    monkeypatch.setenv(L.V2_ENV, "off")
    png, meta = comp()
    assert meta["variety"] is None and png == legacy()[0]


def test_one_broken_layer_drops_only_that_layer(v2) -> None:
    man = json.loads((v2 / "manifest.json").read_text())
    for lst in man["backgrounds"].values():
        for e in lst:
            (v2 / e["file"]).write_bytes(b"not an image")          # sha 對不上
    png, meta = comp()
    assert any(f.startswith("bg") for f in meta["variety"]["fallbacks"])
    assert meta["variety"]["stickers"], "背景壞了，貼紙與相框仍在"
    assert meta["plate"] == "plate_s00"


def test_corrupt_but_hash_matching_scene_falls_back(v2) -> None:
    man = json.loads((v2 / "manifest.json").read_text())
    for lst in man["backgrounds"].values():
        for e in lst:
            (v2 / e["file"]).write_bytes(b"garbage")
            e["sha256"] = _sha(v2 / e["file"])
    (v2 / "manifest.json").write_text(json.dumps(man))
    png, meta = comp()
    assert any(f.startswith("scene:") for f in meta["variety"]["fallbacks"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_frame_with_a_different_layout_is_refused(v2) -> None:
    man = json.loads((v2 / "manifest.json").read_text())
    for lst in man["frames"].values():
        for e in lst:
            js = json.loads((v2 / e["json"]).read_text())
            js["window_px"] = {"x": 120, "y": 120, "w": 500, "h": 500}
            (v2 / e["json"]).write_text(json.dumps(js))
    _, meta = comp()
    assert any(f.startswith("frame:") for f in meta["variety"]["fallbacks"])
    assert meta["frame"].startswith("file:b2faf31d6747")          # 回到單一相框版


def test_no_fortune_still_makes_a_card_with_place_background(v2) -> None:
    _, meta = comp(fortune=None)
    sp = meta["variety"]["spec"]
    assert sp.get("background") and meta["variety"]["stickers"] == []
    assert (sp.get("element") or "neutral") == "neutral"


def test_meta_does_not_carry_the_seed_or_the_raw_card_values(v2) -> None:
    _, meta = comp("secret-sub-id-123", fortune={"mbti": "INFP", "zodiac": "雙魚", "blood": "AB"})
    s = json.dumps(meta, ensure_ascii=False)
    assert "secret-sub-id-123" not in s and "INFP" not in s and "雙魚" not in s


# ---------------------------------------------------------------------------
# 產品路徑：make_polaroid 帶 sub_id／hints／命盤進來，鏈上只記數字
# ---------------------------------------------------------------------------
sys.path.insert(0, str(ROOT / "tests"))
from test_twin_agent_run import _ingest, env, upstream  # noqa: E402,F401
from ops.exhibit.twin import twinlink  # noqa: E402
from ops.exhibit.twin.twinstore import KIND_NOTE, canonical_json  # noqa: E402


def test_product_path_uses_variety_and_chain_records_only_counts(env, monkeypatch, v2) -> None:
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    assert twinlink.generate(st, env["upstream"], "m", agent=cfg)["generated"] == 1
    out = twinlink.polaroids(st)
    assert out.get("made") == 1, out
    notes = [e["payload"] for e in st.events(sub_id=sid, kind=KIND_NOTE)
             if e["payload"].get("twinlink_event") == twinlink.POLAROID_MADE]
    assert len(notes) == 1
    n = notes[0]
    assert isinstance(n["variety_stickers"], int) and isinstance(n["variety_fallbacks"], int)
    assert n["variety_fallbacks"] == 0
    assert "frame_" not in json.dumps(n) and "bg_" not in json.dumps(n)     # 鏈上不記素材名
    assert n["qr_text"] == polaroid.SITE_URL


def test_withdrawn_person_gets_no_polaroid_even_with_assets(env, monkeypatch, v2) -> None:
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    assert twinlink.generate(st, env["upstream"], "m", agent=cfg)["generated"] == 1
    assert twinlink.withdraw(st, sid)["ok"]
    assert twinlink.make_polaroid(st, sid)["state"] == "gone"
    assert st.vault.open_polaroid(sid) is None
