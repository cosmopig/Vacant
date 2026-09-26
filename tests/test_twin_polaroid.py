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

EVID = ROOT / "ops" / "exhibit" / "twin" / "evidence_polaroid_20260926"


def _compose(decision: str = "寫一封謝卡給國小導師", **kw):
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
    long = "為下週末安排一份慢節奏的散步路線，途中經過三家老書店、一間賣手沖咖啡的小店，最後在河堤看夕陽"
    _png, meta = _compose(long)
    assert meta["caption_truncated"] is True
    box = meta["caption_box"]
    assert meta["caption_drawn"][2] - meta["caption_drawn"][0] <= box[2] - box[0]
    f = polaroid._font(polaroid.CAPTION_PX)
    text, cut = polaroid.fit_text(f, long, box[2] - box[0])
    assert cut and text.endswith("…") and not text[:-1].endswith(("，", "、", " "))
    # 負控制：不截的話那一行**真的放不下**（這條判準量得到出界）
    assert f.getlength(long) > box[2] - box[0]


def test_short_decision_is_not_truncated() -> None:
    _png, meta = _compose("寫一封謝卡")
    assert meta["caption_truncated"] is False and meta["caption_chars"] == 5


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


def test_verbatim_copy_of_the_viewer_text_is_replaced() -> None:
    """拍立得上不准出現可識別本人的原文：分身的句子逐字抄了觀眾 8 個字以上 ⇒ 中性句。"""
    originals = polaroid.originals_of({"need": NEED}, TRAITS_TEXT)
    leak = "最近一直想寫信給國小導師"                    # TRAITS_TEXT 的連續 12 個字
    _png, meta = _compose(leak, originals=originals)
    assert meta["caption_redacted"] is True
    # 負控制：只共用「國小導師」四個字的正常決定**不會**被誤殺
    _png, meta2 = _compose(DECISION, originals=originals)
    assert meta2["caption_redacted"] is False
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
                                            "（證據檔 evidence_polaroid_20260926/qr_decode.json 是開發機跑的）")
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
    for r in d["results"]:
        c = r["cases"]
        assert c["original"]["decoded"] == polaroid.SITE_URL
        assert c["phone_photo_15cm"]["ok"] is True
        assert c["neg_blanked"]["decoded"] is None               # 負控制：塗掉就解不出
        assert c["neg_other_url"]["not_site"] is True            # 負控制：別的網址解成別的網址
        # 報告講的是**現在這幾張檔**（雜湊對得上），不是別的版本
        p = EVID / r["file"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == r["sha256"] == by_file[r["file"]]["sha256"]
    assert all(s["synthetic"] for s in samples["samples"])


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
