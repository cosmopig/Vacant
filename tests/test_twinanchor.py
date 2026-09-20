"""twinanchor 的判準——「整條重算」這件事偵測得到嗎。

`twinstore.py` 誠實邊界 1 自己承認：拿得到檔案的人可以整條重算，
`verify()` 照樣綠。這一批測試守的就是「那個弱點現在有東西擋著」。

紀律（跟 `test_twinstore.py` 同一套）：
**每一組「應該抓得到」都配一個負控制**，而且這裡多一層——
連「我們抓不到的那一種」也寫成可執行的標本（`test_resign_with_stolen_key_*`），
因為 docstring 裡的誠實邊界如果沒有測試釘住，改碼的人不會知道它是刻意的。
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import twinanchor as ta  # noqa: E402
from ops.exhibit.twin.twinstore import KIND_NOTE, KIND_SUBMITTED, TwinStore  # noqa: E402
from vacant_network.identity import Identity  # noqa: E402

TS0 = 1_700_000_000_000


@pytest.fixture()
def keydir(tmp_path: pathlib.Path) -> pathlib.Path:
    d = tmp_path / "key"
    ta.init_key(d)
    return d


@pytest.fixture()
def ident(keydir: pathlib.Path) -> Identity:
    return ta.load_key(keydir)


def _make_store(path: pathlib.Path, n: int = 8) -> pathlib.Path:
    st = TwinStore(path)
    for i in range(n):
        st.append(KIND_SUBMITTED, f"v{i:02d}",
                  {"card": {"shape": "圓潤", "i": i}, "card_text": f"卡 {i}"},
                  source="test", ts_unix_ms=TS0 + i)
    st.close()
    return path


@pytest.fixture()
def setup(tmp_path: pathlib.Path, ident: Identity):
    """一個有 8 列的 store ＋ 一枚錨。回 (db, anchors, ident, pub)。"""
    db = _make_store(tmp_path / "t.sqlite3")
    an = tmp_path / "anchors.jsonl"
    st = TwinStore(db)
    ta.emit_anchor(st, ident, an, ts_ms=TS0 + 1000)
    st.close()
    return db, an, ident, ta.pub_hex_of(ident_keydir(ident, tmp_path))


def ident_keydir(_ident: Identity, tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path / "key"


# ---------------------------------------------------------------------------
# 對照組：沒被動過的東西要是綠的（否則後面每一條紅燈都沒有意義）
# ---------------------------------------------------------------------------

def test_untouched_chain_is_green(setup) -> None:
    db, an, _ident, pub = setup
    st = TwinStore(db)
    rep = ta.verify_all(st, ta.load_anchors(an), pinned_pub=pub, require_pin=True)
    st.close()
    assert rep["ok"] is True, rep["failures"]
    assert rep["store_verify"]["ok"] is True
    assert rep["pubkey_pinned"] is True
    assert rep["no_rollback"]["ok"] is True


def test_appending_more_rows_keeps_old_anchors_valid(setup) -> None:
    """繼續營業不會讓舊錨失效——錨說的是「到那一刻為止」，不是「到此為止」。"""
    db, an, ident, pub = setup
    st = TwinStore(db)
    st.append(KIND_NOTE, "v99", {"t": "閉館後又來了一位"}, source="test",
              ts_unix_ms=TS0 + 50)
    rep = ta.verify_all(st, ta.load_anchors(an), pinned_pub=pub)
    st.close()
    assert rep["ok"] is True, rep["failures"]


# ---------------------------------------------------------------------------
# 🔴 核心判準：整條重算
# ---------------------------------------------------------------------------

def test_full_rewrite_still_passes_twinstore_verify(tmp_path: pathlib.Path) -> None:
    """**先證明弱點是真的。** 不先證明這個，下一條的紅燈就沒有對象。"""
    db = _make_store(tmp_path / "t.sqlite3")
    ta.simulate_full_rewrite(db, drop_seqs=[4])
    st = TwinStore(db)
    sv = st.verify()
    st.close()
    assert sv["ok"] is True, "如果這裡就紅了，代表重算沒做成功，下一條測的不是我們以為的東西"
    assert sv["checked"] == 7


def test_full_rewrite_is_caught_by_anchor(setup) -> None:
    """🔴 缺口 E 的正題：整條重算被抓到。"""
    db, an, _ident, pub = setup
    ta.simulate_full_rewrite(db, drop_seqs=[4])
    st = TwinStore(db)
    rep = ta.verify_all(st, ta.load_anchors(an), pinned_pub=pub)
    st.close()
    assert rep["ok"] is False
    assert rep["store_verify"]["ok"] is True, "store 自己還是綠的——所以紅燈只能來自錨"
    assert any("驗不過" in f for f in rep["failures"]), rep["failures"]
    assert rep["per_anchor"][0]["ok"] is False


def test_full_rewrite_without_dropping_anything_is_still_caught(setup) -> None:
    """就算一列都沒少、只是重算了一遍，也要抓到（時間戳／來源被改屬於這一類）。"""
    db, an, _ident, pub = setup
    conn = sqlite3.connect(str(db))
    conn.isolation_level = None
    ta._drop_triggers(conn)
    conn.execute("UPDATE twin_event SET source='偽造' WHERE seq=5")
    conn.close()
    ta.simulate_full_rewrite(db)  # 重算一遍讓 twinstore.verify() 重新變綠
    st = TwinStore(db)
    sv = st.verify()
    rep = ta.verify_all(st, ta.load_anchors(an), pinned_pub=pub)
    st.close()
    assert sv["ok"] is True, "重算之後 store 自己應該綠"
    assert rep["ok"] is False, "錨要抓到"


# ---------------------------------------------------------------------------
# 🔴 核心判準：截掉鏈尾
# ---------------------------------------------------------------------------

def test_truncation_still_passes_twinstore_verify(tmp_path: pathlib.Path) -> None:
    """合法前綴。`verify()` 只往前走，不知道原本該走到哪裡。"""
    db = _make_store(tmp_path / "t.sqlite3")
    ta.simulate_truncate(db, 3)
    st = TwinStore(db)
    sv = st.verify()
    st.close()
    assert sv["ok"] is True
    assert sv["checked"] == 5


def test_truncation_is_caught_by_anchor(setup) -> None:
    db, an, _ident, pub = setup
    ta.simulate_truncate(db, 3)
    st = TwinStore(db)
    rep = ta.verify_all(st, ta.load_anchors(an), pinned_pub=pub)
    st.close()
    assert rep["ok"] is False
    assert rep["no_rollback"]["ok"] is False
    assert rep["no_rollback"]["anchored_max_seq"] == 8
    assert rep["no_rollback"]["store_head_seq"] == 5


# ---------------------------------------------------------------------------
# 錨鏈自身（複用 checkpoint.verify_checkpoint_chain）
# ---------------------------------------------------------------------------

def test_anchor_chain_links(tmp_path: pathlib.Path, ident: Identity) -> None:
    db = _make_store(tmp_path / "t.sqlite3")
    an = tmp_path / "a.jsonl"
    st = TwinStore(db)
    a1 = ta.emit_anchor(st, ident, an, ts_ms=TS0 + 1)
    st.append(KIND_NOTE, "x", {"k": 1}, source="t", ts_unix_ms=TS0 + 100)
    a2 = ta.emit_anchor(st, ident, an, ts_ms=TS0 + 2)
    st.close()
    assert a1["prev_checkpoint_sig"] is None
    assert a2["prev_checkpoint_sig"] == a1["sig"]
    assert a2["retro_audits"]["prev_anchor_holds"] is True


def test_removing_a_middle_anchor_turns_red(tmp_path: pathlib.Path,
                                            ident: Identity) -> None:
    """負控制：抽掉中間一枚錨 ⇒ 錨鏈斷。"""
    db = _make_store(tmp_path / "t.sqlite3")
    an = tmp_path / "a.jsonl"
    st = TwinStore(db)
    for k in range(3):
        st.append(KIND_NOTE, f"x{k}", {"k": k}, source="t", ts_unix_ms=TS0 + 200 + k)
        ta.emit_anchor(st, ident, an, ts_ms=TS0 + 10 + k)
    anchors = ta.load_anchors(an)
    assert len(anchors) == 3
    rep_full = ta.verify_all(st, anchors, pinned_pub=ta.pub_hex_of(tmp_path / "key"))
    rep_gap = ta.verify_all(st, [anchors[0], anchors[2]],
                            pinned_pub=ta.pub_hex_of(tmp_path / "key"))
    st.close()
    assert rep_full["ok"] is True, rep_full["failures"]        # 對照組
    assert rep_gap["ok"] is False                              # 負控制
    assert rep_gap["anchor_chain"]["ok"] is False


# ---------------------------------------------------------------------------
# 🔴 誠實邊界 1 的可執行標本：拿到金鑰的人重簽一整條
# ---------------------------------------------------------------------------

def test_resign_with_stolen_key_is_NOT_caught_without_a_pin(setup) -> None:
    """**這是我們擋不住的那一種，測試把它釘死。**

    如果哪天這條測試自己紅了（＝變成抓得到了），那是好消息，但 docstring
    的誠實邊界 1 也必須跟著改——兩邊不准不一致。
    """
    db, an, _ident, _pub = setup
    ta.simulate_full_rewrite(db, drop_seqs=[2])
    attacker = Identity.generate()
    an.unlink()
    st = TwinStore(db)
    ta.emit_anchor(st, attacker, an, ts_ms=TS0 + 9999)
    rep = ta.verify_all(st, ta.load_anchors(an))   # 沒釘公鑰
    st.close()
    assert rep["ok"] is True, "沒有離機的公鑰時，這件事本來就偵測不到"
    assert rep["pubkey_pinned"] is None, "🔴 三態：沒量到寫 null，不是 False"
    assert any("pubkey_pinned=null" in w for w in rep["warnings"])


def test_resign_with_stolen_key_IS_caught_with_an_offmachine_pin(setup) -> None:
    db, an, _ident, pub = setup
    ta.simulate_full_rewrite(db, drop_seqs=[2])
    attacker = Identity.generate()
    an.unlink()
    st = TwinStore(db)
    ta.emit_anchor(st, attacker, an, ts_ms=TS0 + 9999)
    rep = ta.verify_all(st, ta.load_anchors(an), pinned_pub=pub)
    st.close()
    assert rep["ok"] is False
    assert rep["pubkey_pinned"] is False
    assert any("公鑰" in f for f in rep["failures"])


def test_require_pin_turns_the_null_red(setup) -> None:
    db, an, _ident, _pub = setup
    st = TwinStore(db)
    lax = ta.verify_all(st, ta.load_anchors(an))
    strict = ta.verify_all(st, ta.load_anchors(an), require_pin=True)
    st.close()
    assert lax["ok"] is True and lax["pubkey_pinned"] is None   # 對照組
    assert strict["ok"] is False                                # 負控制
    assert any("--require-pin" in f for f in strict["failures"])


def test_mixed_signers_are_caught_even_without_a_pin(setup) -> None:
    """半路換一把金鑰簽（沒有重簽整條）⇒ 不需要離機公鑰就抓得到。"""
    db, an, _ident, _pub = setup
    attacker = Identity.generate()
    st = TwinStore(db)
    st.append(KIND_NOTE, "x", {"k": 1}, source="t", ts_unix_ms=TS0 + 300)
    ta.emit_anchor(st, attacker, an, ts_ms=TS0 + 8888)
    rep = ta.verify_all(st, ta.load_anchors(an))
    st.close()
    assert rep["ok"] is False
    assert rep["single_signer"]["ok"] is False
    assert rep["single_signer"]["distinct"] == 2


# ---------------------------------------------------------------------------
# 紙條 / QR（出口④：唯一連磁碟被整顆換掉都還在的比對點）
# ---------------------------------------------------------------------------

def test_slip_matches_then_stops_matching_after_a_resign(setup) -> None:
    db, an, ident, pub = setup
    good = ta.slip_of(ta.load_anchors(an)[-1])
    st = TwinStore(db)
    rep_ok = ta.verify_all(st, ta.load_anchors(an), pinned_pub=pub, slip=good)
    st.close()
    assert rep_ok["ok"] is True and rep_ok["slip"]["ok"] is True   # 對照組

    ta.simulate_full_rewrite(db, drop_seqs=[3])
    an.unlink()
    st = TwinStore(db)
    ta.emit_anchor(st, ident, an, ts_ms=TS0 + 7777)   # 同一把金鑰重簽
    rep_bad = ta.verify_all(st, ta.load_anchors(an), pinned_pub=pub, slip=good)
    st.close()
    assert rep_bad["pubkey_pinned"] is True, "公鑰這一關擋不住（同一把金鑰）"
    assert rep_bad["ok"] is False
    assert rep_bad["slip"]["ok"] is False, "紙條要擋得住——不然出口④沒有存在意義"


def test_slip_fits_in_a_qr_and_round_trips() -> None:
    from ops.exhibit.twin import qr as qrmod
    anchor = {"stream_id": "a" * 64, "window": [1, 12345], "sig": "b" * 128,
              "pub": "c" * 64, "ts_ms": TS0}
    slip = ta.slip_of(anchor)
    assert len(slip.encode("utf-8")) <= qrmod.MAX_BYTES, slip
    parsed = ta.parse_slip(slip)
    assert parsed["seq"] == 12345
    assert parsed["stream8"] == "a" * 8
    assert len(parsed["digest"]) == ta.SLIP_DIGEST_HEX
    assert qrmod.matrix(slip)  # 畫得出來就好；正確性由 tests/test_qr.py 對照 segno


@pytest.mark.parametrize("bad", ["", "VTA1 abc", "nope a b c", "VTA1 a x c"])
def test_garbage_slip_is_rejected_not_silently_accepted(bad: str) -> None:
    r = ta.check_slip(bad, [])
    assert r["ok"] is False
    assert r["reason"]


# ---------------------------------------------------------------------------
# 跨 store 綁定
# ---------------------------------------------------------------------------

def test_anchors_from_another_store_do_not_graft(tmp_path: pathlib.Path,
                                                 ident: Identity) -> None:
    db_a = _make_store(tmp_path / "a.sqlite3")
    db_b = _make_store(tmp_path / "b.sqlite3")
    an = tmp_path / "a.jsonl"
    st = TwinStore(db_a)
    ta.emit_anchor(st, ident, an, ts_ms=TS0 + 1)
    st.close()
    st = TwinStore(db_b)
    rep = ta.verify_all(st, ta.load_anchors(an),
                        pinned_pub=ta.pub_hex_of(tmp_path / "key"))
    st.close()
    assert rep["ok"] is False
    assert rep["stream_bound"]["ok"] is False


# ---------------------------------------------------------------------------
# fail-closed 與三態
# ---------------------------------------------------------------------------

def test_refuses_to_sign_a_broken_chain(tmp_path: pathlib.Path,
                                        ident: Identity) -> None:
    db = _make_store(tmp_path / "t.sqlite3")
    conn = sqlite3.connect(str(db))
    conn.isolation_level = None
    ta._drop_triggers(conn)
    conn.execute("UPDATE twin_event SET payload_json='{\"x\":1}' WHERE seq=3")
    conn.close()
    st = TwinStore(db)
    with pytest.raises(ta.AnchorRefused):
        ta.emit_anchor(st, ident, tmp_path / "a.jsonl", ts_ms=TS0)
    forced = ta.emit_anchor(st, ident, tmp_path / "a.jsonl", force=True, ts_ms=TS0)
    st.close()
    assert forced["retro_audits"]["twinstore_verify"] is False, \
        "--force 不可以把紅的洗成綠的"


def test_refuses_to_anchor_an_empty_store(tmp_path: pathlib.Path,
                                          ident: Identity) -> None:
    st = TwinStore(tmp_path / "empty.sqlite3")
    with pytest.raises(ta.AnchorRefused):
        ta.emit_anchor(st, ident, tmp_path / "a.jsonl", ts_ms=TS0)
    st.close()


def test_first_anchor_puts_unmeasured_in_missing_not_false(setup) -> None:
    """🔴 三態鐵律。第一枚沒有前一枚可比＝量不到，不是量到 false。"""
    _db, an, _ident, _pub = setup
    a = ta.load_anchors(an)[0]
    assert a["retro_missing"] == ["prev_anchor_holds"]
    assert "prev_anchor_holds" not in a["retro_audits"]
    assert a["retro_audits"]["twinstore_verify"] is True


def test_no_anchors_at_all_reports_null_not_clean(tmp_path: pathlib.Path) -> None:
    """從來沒錨定過 ⇒ 每一關都是 null ＋ 一句警告，不是「乾淨」。"""
    db = _make_store(tmp_path / "t.sqlite3")
    st = TwinStore(db)
    rep = ta.verify_all(st, [])
    st.close()
    assert rep["anchors"] == 0
    for k in ("anchor_chain", "per_anchor", "stream_bound", "no_rollback",
              "single_signer", "pubkey_pinned", "slip"):
        assert rep[k] in (None, []), k
    assert any("從來沒有被錨定過" in w for w in rep["warnings"])


def test_load_key_never_generates_silently(tmp_path: pathlib.Path) -> None:
    with pytest.raises(FileNotFoundError):
        ta.load_key(tmp_path / "nokey")
    assert not (tmp_path / "nokey").exists(), "連目錄都不該被建出來"


def test_init_key_does_not_overwrite(tmp_path: pathlib.Path) -> None:
    d = tmp_path / "k"
    first = ta.init_key(d)
    second = ta.init_key(d)
    assert first["created"] is True and second["created"] is False
    assert first["pub"] == second["pub"], "覆寫會讓所有舊錨變成無主的字串"


def test_private_key_is_0600_and_under_a_gitignored_default() -> None:
    assert ta.DEFAULT_KEYDIR.name == "anchor_key"
    assert ta.DEFAULT_KEYDIR.parent.name == "store"
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "ops/exhibit/twin/store/" in gi, "預設金鑰目錄必須落在 .gitignore 底下"


def test_key_file_permissions(tmp_path: pathlib.Path) -> None:
    d = tmp_path / "k"
    ta.init_key(d)
    assert oct((d / "identity.key").stat().st_mode & 0o777) == "0o600"


# ---------------------------------------------------------------------------
# 錨的窗口語意（累積式）
# ---------------------------------------------------------------------------

def test_window_is_cumulative_so_the_latest_anchor_covers_all_history(
        tmp_path: pathlib.Path, ident: Identity) -> None:
    db = _make_store(tmp_path / "t.sqlite3")
    an = tmp_path / "a.jsonl"
    st = TwinStore(db)
    ta.emit_anchor(st, ident, an, ts_ms=TS0)
    st.append(KIND_NOTE, "x", {"k": 1}, source="t", ts_unix_ms=TS0 + 400)
    last = ta.emit_anchor(st, ident, an, ts_ms=TS0 + 1)
    st.close()
    assert last["window"] == [1, 9]
    # 只留最後一枚，仍然抓得到改第 2 列
    ta.simulate_full_rewrite(db, drop_seqs=[2])
    st = TwinStore(db)
    rep = ta.verify_all(st, [last], pinned_pub=ta.pub_hex_of(tmp_path / "key"))
    st.close()
    assert rep["ok"] is False, "累積窗口的重點：錨鏈少幾枚也還在守"


# ---------------------------------------------------------------------------
# 離機副本（出口②③）
# ---------------------------------------------------------------------------

def test_mirror_to_dir_ships_pub_but_never_the_private_key(setup,
                                                           tmp_path: pathlib.Path):
    _db, an, _ident, pub = setup
    dest = tmp_path / "usb"
    r = ta.mirror_to_dir(an, tmp_path / "key", dest)
    assert r["ok"] is True
    names = sorted(p.name for p in dest.iterdir())
    assert names == sorted(["MIRROR.txt", "anchors.jsonl", ta.PUB_PIN_NAME])
    assert "identity.key" not in names
    assert (dest / ta.PUB_PIN_NAME).read_text().strip() == pub
    assert "沒有私鑰" in (dest / "MIRROR.txt").read_text(encoding="utf-8")


def test_mirrored_pin_actually_catches_a_resign(setup, tmp_path: pathlib.Path):
    """離機副本不是裝飾：拿它當 pin，重簽就紅。"""
    db, an, _ident, _pub = setup
    dest = tmp_path / "usb"
    ta.mirror_to_dir(an, tmp_path / "key", dest)
    pinned = (dest / ta.PUB_PIN_NAME).read_text(encoding="utf-8").strip()

    ta.simulate_full_rewrite(db, drop_seqs=[5])
    an.unlink()
    st = TwinStore(db)
    ta.emit_anchor(st, Identity.generate(), an, ts_ms=TS0 + 5555)
    rep = ta.verify_all(st, ta.load_anchors(an), pinned_pub=pinned)
    st.close()
    assert rep["ok"] is False and rep["pubkey_pinned"] is False


def test_mirror_scp_failure_is_false_with_stderr_not_a_silent_zero(
        setup, tmp_path: pathlib.Path):
    """🔴 不吞 stderr。斷網 ⇒ ok=false ＋ rc ＋ stderr 原文。"""
    _db, an, _ident, _pub = setup
    r = ta.mirror_scp(an, tmp_path / "key",
                      "nobody@203.0.113.1:/tmp/x/", timeout=25.0)
    assert r["ok"] is not True
    if r["ok"] is None:
        pytest.skip("這台沒有 scp ⇒ 這個出口沒量到（不是失敗）")
    assert r["rc"] != 0
    assert r["stderr"], "stderr 必須帶回來，不可以吞掉"


def test_mirror_refuses_when_there_is_nothing_to_ship(tmp_path: pathlib.Path):
    r = ta.mirror_to_dir(tmp_path / "none.jsonl", tmp_path, tmp_path / "usb")
    assert r["ok"] is False


# ---------------------------------------------------------------------------
# CLI（退出碼是展場腳本唯一讀得到的東西）
# ---------------------------------------------------------------------------

def test_cli_exit_codes(tmp_path: pathlib.Path, capsys) -> None:
    db = _make_store(tmp_path / "t.sqlite3")
    an = tmp_path / "a.jsonl"
    kd = tmp_path / "k"
    base = ["--db", str(db), "--anchors", str(an), "--keydir", str(kd)]

    assert ta.main(base + ["init"]) == 0
    assert ta.main(base + ["emit", "--note", "開館前"]) == 0
    capsys.readouterr()

    assert ta.main(base + ["verify"]) == 0                       # 對照組
    assert ta.main(base + ["verify", "--require-pin"]) == 1      # 沒 pin ⇒ 紅
    pub = ta.pub_hex_of(kd)
    assert ta.main(base + ["verify", "--require-pin", "--pub", pub]) == 0
    capsys.readouterr()

    ta.simulate_full_rewrite(db, drop_seqs=[3])
    assert ta.main(base + ["verify", "--pub", pub]) == 1         # 負控制
    capsys.readouterr()


def test_cli_verify_does_not_write_to_the_store(tmp_path: pathlib.Path,
                                                capsys) -> None:
    """稽核不該對真相來源寫東西（`serve` 那個 bug 的同類）。"""
    db = _make_store(tmp_path / "t.sqlite3")
    an = tmp_path / "a.jsonl"
    kd = tmp_path / "k"
    base = ["--db", str(db), "--anchors", str(an), "--keydir", str(kd)]
    ta.main(base + ["init"])
    ta.main(base + ["emit"])
    capsys.readouterr()
    before = db.stat().st_mtime_ns, db.read_bytes()
    assert ta.main(base + ["verify"]) == 0
    capsys.readouterr()
    after = db.stat().st_mtime_ns, db.read_bytes()
    assert before[1] == after[1], "verify 改動了 store 的 bytes"


def test_cli_emit_note_lands_in_the_chain_and_is_covered(tmp_path: pathlib.Path,
                                                         capsys) -> None:
    db = _make_store(tmp_path / "t.sqlite3")
    an = tmp_path / "a.jsonl"
    kd = tmp_path / "k"
    base = ["--db", str(db), "--anchors", str(an), "--keydir", str(kd)]
    ta.main(base + ["init"])
    ta.main(base + ["emit", "--note", "閉館"])
    capsys.readouterr()
    st = TwinStore(db)
    notes = [e for e in st.events(kind=KIND_NOTE)]
    st.close()
    assert notes and notes[-1]["payload"]["text"] == "閉館"
    assert ta.load_anchors(an)[-1]["window"] == [1, 9], "note 必須被這枚錨蓋住"


def test_cli_slip_writes_a_qr(tmp_path: pathlib.Path, capsys) -> None:
    db = _make_store(tmp_path / "t.sqlite3")
    an = tmp_path / "a.jsonl"
    kd = tmp_path / "k"
    base = ["--db", str(db), "--anchors", str(an), "--keydir", str(kd)]
    ta.main(base + ["init"])
    ta.main(base + ["emit"])
    png = tmp_path / "q.png"
    assert ta.main(base + ["slip", "--qr", str(png)]) == 0
    out = capsys.readouterr().out
    assert png.exists() and png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert ta.SLIP_MAGIC in out


# ---------------------------------------------------------------------------
# 複用：確認真的走的是 checkpoint.py，不是抄一份
# ---------------------------------------------------------------------------

def test_it_really_reuses_checkpoint_module(setup) -> None:
    from vacant_network import checkpoint as cp
    _db, an, _ident, _pub = setup
    a = ta.load_anchors(an)[0]
    assert a["v"] == cp.CHECKPOINT_VERSION
    assert a["kind"] == "checkpoint"
    assert set(cp._CLAIM_FIELDS) <= set(a)


def test_the_view_has_no_append_door(setup) -> None:
    """唯讀視圖不可以長出寫入口——那等於在 append-only 的牆上開後門。"""
    db, _an, _i, _p = setup
    st = TwinStore(db)
    view = ta.TwinChainView(st)
    st.close()
    assert not hasattr(view, "append")
    assert not hasattr(view, "save")


def test_view_head_matches_twinstore_head(setup) -> None:
    db, _an, _i, _p = setup
    st = TwinStore(db)
    view = ta.TwinChainView(st)
    head = st.head()
    st.close()
    assert view.head() == head["row_sha256"]
    assert view.stream_id().startswith(view.stream_id()[:8])
    assert view.head_seq() == head["seq"]


def test_anchor_digest_is_deterministic_across_json_round_trip(setup) -> None:
    _db, an, _i, _p = setup
    a = ta.load_anchors(an)[0]
    again = json.loads(json.dumps(a, ensure_ascii=False))
    assert ta.anchor_digest(a) == ta.anchor_digest(again)


def test_mirror_cli_exit_code_is_three_when_unmeasured(setup, tmp_path, monkeypatch,
                                                       capsys) -> None:
    """🔴 三態的退出碼：沒量到走 3，**不可以走 0**。

    負控制在上面 `test_mirror_scp_failure_is_false_with_stderr_not_a_silent_zero`
    （送失敗 ⇒ ok=false）；對照組是 `--dest` 成功 ⇒ 0。
    """
    _db, an, _ident, _pub = setup
    base = ["--anchors", str(an), "--keydir", str(tmp_path / "key")]
    assert ta.main(base + ["mirror", "--dest", str(tmp_path / "usb")]) == 0  # 對照組
    capsys.readouterr()
    monkeypatch.setattr(ta.shutil, "which", lambda _n: None)   # 這台沒有 scp
    rc = ta.main(base + ["mirror", "--scp", "nobody@203.0.113.1:/tmp/x/"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 3, "沒量到走 3"
    assert out["scp"]["ok"] is None, "沒量到寫 null 不是 False"
