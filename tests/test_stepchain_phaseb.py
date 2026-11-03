"""步鏈 Phase B（L2 冷壓縮）測試（DECISION_20261103_STEPCHAIN_SEALING.md §9：B-T1–B-T6）。

範圍：已封印卷 gzip（`chain-NNNNNN.ndjson` → `chain-NNNNNN.ndjson.gz`）、活動卷永不壓、
驗章端 gunzip 後照舊驗（seal payload `sha256_prefix`＝未壓縮流的哈希⇒零語義變化）、
損壞 .gz⇒BROKEN 族（非 UNKNOWN、不崩潰）、fail-open（壓縮失敗⇒留原檔、不擋）、
明文與 .gz 封印卷共存（C2 向後相容）。
"""
from __future__ import annotations

import gzip

import pytest

from vacant_network.intake import keys
from vacant_network.trace import recorder as R


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    keys.init_local()
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "data.csv").write_text("col\nval\n")
    return ws, R.Recorder(ws)


MAIN = R.Actor("pi", "s1")


def _fill(rec: "R.Recorder", ws, n: int = 12, content_len: int = 0) -> None:
    for i in range(n):
        payload: dict = {"file_path": f"f{i}.txt"}
        if content_len:
            payload["content"] = f"row-{i}-" + "x" * content_len
        rec.pre(f"t{i}", MAIN, "Write", payload)
        (ws / f"f{i % 40}.txt").write_text(f"content {i}\n")    # 固定小檔案集：避免 O(n²) 掃描
        rec.post(f"t{i}", MAIN, "Write", payload, "ok")


def _sealed(pdir) -> list:
    return sorted(p for p in pdir.iterdir()
                  if p.is_file() and p.name.startswith("chain-")
                  and (p.name.endswith(".ndjson") or p.name.endswith(".ndjson.gz")))


def _sealed_plain(pdir) -> list:
    return [p for p in _sealed(pdir) if p.name.endswith(".ndjson")]


def test_phase_b_gz_volume_verifies_ok(env):
    """B-T1：封印→壓縮→刪明文→verify⇒OK、事件内容与明文版逐筆一致。"""
    ws, rec = env
    rec.volume_max_entries = 5
    rec.compact_on_seal = False    # 顯式壓縮路徑（封印自動壓縮由 B-T4 覆蓋）
    _fill(rec, ws, 12)
    pdir = rec.dir
    plain = _sealed_plain(pdir)
    assert plain, "expected sealed plaintext volumes"
    vol = plain[0]
    before = rec.events()
    ok, why = R.compact_sealed_volume(vol)
    assert ok, f"compact failed: {why}"
    assert not vol.is_file(), "plaintext sealed volume must be gone after successful compression"
    gz = vol.with_name(vol.name + ".gz")
    assert gz.is_file(), f"expected {gz.name}"
    ok, why = rec.verify()
    assert ok, f"verify failed after compression: {why}"
    after = rec.events()
    assert after == before, "events must be identical before/after compression (gunzip 後照舊讀)"


def test_phase_b_corrupt_gz_is_broken_not_unknown(env):
    """B-T2（C3）：.gz 翻 1 位元組⇒verify⇒BROKEN 族（ok=False、原因非 UNKNOWN、不上拋）。"""
    ws, rec = env
    rec.volume_max_entries = 5
    rec.compact_on_seal = False
    _fill(rec, ws, 12)
    pdir = rec.dir
    vol = _sealed_plain(pdir)[0]
    ok, why = R.compact_sealed_volume(vol)
    assert ok, why
    gz = vol.with_name(vol.name + ".gz")
    data = bytearray(gz.read_bytes())
    data[len(data) // 2] ^= 0xFF
    gz.write_bytes(bytes(data))
    ok2, why2 = rec.verify()
    assert not ok2, "corrupted .gz must not verify"
    assert "UNKNOWN" not in why2, f"corrupt content is BROKEN family, not UNKNOWN: {why2}"


def test_phase_b_ratio_ge_3x(env):
    """B-T3（C3）：合成 JSON 鏈壓縮比實測 ≥3×（預期 3–8×、§3.3；卷大小與真實鏈同量級：
    真實 e014 卷 21.9MB⇒4.01×；本測試 200 筆/卷≈230KB⇒約 3.7×。卷太小時 LZ77 無重複上下文、
    比值被固定開頭（哈希/簽章）稀釋，不代表真實卷）。"""
    ws, rec = env
    rec.volume_max_entries = 200
    rec.compact_on_seal = False
    _fill(rec, ws, 850)
    pdir = rec.dir
    plain = _sealed_plain(pdir)
    assert plain, "expected sealed plaintext volumes"
    ratios = []
    for vol in plain:
        src_size = vol.stat().st_size
        ok, why = R.compact_sealed_volume(vol)
        assert ok, why
        gz_size = vol.with_name(vol.name + ".gz").stat().st_size
        ratios.append(src_size / gz_size)
    assert all(r >= 3.0 for r in ratios), f"ratios {ratios} below 3x"


def test_phase_b_active_volume_never_compressed(env):
    """B-T4：壓縮後活動卷仍明文、仍可 append；對活動卷的壓縮請求被拒。"""
    ws, rec = env
    rec.volume_max_entries = 5
    _fill(rec, ws, 12)
    pdir = rec.dir
    active = pdir / "chain.ndjson"
    assert active.is_file()
    for vol in _sealed_plain(pdir):
        ok, why = R.compact_sealed_volume(vol)
        assert ok, why
    assert active.is_file(), "active volume must remain plaintext"
    assert not (pdir / "chain.ndjson.gz").exists(), "active volume must never be compressed"
    rec.pre("tafter", MAIN, "Write", {"file_path": "fafter.txt"})
    (ws / "fafter.txt").write_text("x\n")
    rec.post("tafter", MAIN, "Write", {"file_path": "fafter.txt"}, "ok")
    ok, why = rec.verify()
    assert ok, why
    ok2, why2 = R.compact_sealed_volume(active)
    assert not ok2, f"compacting the active volume must be refused: {why2}"
    assert active.is_file() and active.stat().st_size > 0, "active volume must be intact"


def test_phase_b_fail_open(env):
    """B-T5（C5 精神）：壓縮失敗（.gz 目標已存在⇒拒）⇒原檔原封＋無例外上拋＋append/verify 照常。"""
    ws, rec = env
    rec.volume_max_entries = 5
    rec.compact_on_seal = False
    _fill(rec, ws, 12)
    pdir = rec.dir
    vol = _sealed_plain(pdir)[0]
    src = vol.read_bytes()
    vol.with_name(vol.name + ".gz").write_bytes(gzip.compress(b""))
    ok, why = R.compact_sealed_volume(vol)
    assert not ok, f"must refuse when the .gz already exists: {why}"
    assert vol.read_bytes() == src, "original sealed volume must be intact"
    rec.pre("tfo", MAIN, "Write", {"file_path": "tfo.txt"})
    (ws / "tfo.txt").write_text("y\n")
    rec.post("tfo", MAIN, "Write", {"file_path": "tfo.txt"}, "ok")
    okv, whv = rec.verify()
    assert okv, f"verify must still pass with the plaintext volume in place: {whv}"


def test_phase_b_mixed_fleet(env):
    """B-T6：明文封印卷＋.gz 封印卷共存⇒verify OK（C2 向後相容；Phase A 回歸見 test_stepchain_sealing）。"""
    ws, rec = env
    rec.volume_max_entries = 5
    rec.compact_on_seal = False
    _fill(rec, ws, 12)
    pdir = rec.dir
    plain = _sealed_plain(pdir)
    assert len(plain) >= 2, "need at least two sealed volumes for a mixed fleet"
    ok, why = R.compact_sealed_volume(plain[0])
    assert ok, why
    assert _sealed_plain(pdir), "the remaining sealed volume must stay plaintext"
    rec.pre("tmix", MAIN, "Write", {"file_path": "tmix.txt"})
    (ws / "tmix.txt").write_text("z\n")
    rec.post("tmix", MAIN, "Write", {"file_path": "tmix.txt"}, "ok")
    okv, whv = rec.verify()
    assert okv, whv
    ok2, why2 = rec.verify()
    assert ok2, why2
