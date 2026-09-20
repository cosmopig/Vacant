"""出口：沒有有效憑證就發不出去，而且它不看退出碼。

🔴 最重要的那條是 `test_publisher_signature_has_no_exit_code_parameter`——
   它守的不是行為而是**介面**：只要沒有 rc 參數，呼叫者就無從「忘記檢查」。
   abpi 那批的 `abpi_cell.sh:112` 不是惡意的，它只是沒想到要看 rc。
"""
import inspect
import pathlib

import pytest

from vacant_network import crypto
from vacant_network.identity import Identity
from vacant_network.vrun import publish as P
from vacant_network.vrun import release as R


@pytest.fixture
def ident():
    return Identity.generate()


@pytest.fixture
def pub_hex(ident):
    return crypto.pub_to_hex(ident.pub)


@pytest.fixture
def src(tmp_path):
    p = tmp_path / "solution.py"
    p.write_text("def add(a, b):\n    return a + b\n")
    return p


def _sum(accepted=True):
    return {"task_id": "t", "arm": "RUN-ON", "accepted": accepted,
            "ws_end_sha256": "w" * 64, "verdict_sha256": "v" * 64,
            "model_wire": {"count_semantics": "exact"},
            "attestation": {"enclosure": {"applied": True},
                            "framework_hook": {"canary_fired": True},
                            "reconciled": {"unexplained": 0}}}


def _tok(ident, src, accepted=True, **kw):
    return R.mint(_sum(accepted), ident=ident, artifact_path=src, **kw)["token"]


# ── 介面本身就是判準 ───────────────────────────────────────────────────
def test_publisher_signature_has_no_exit_code_parameter():
    """🔴 `publish()` 不准有任何 rc／returncode／exit 參數。

    這條是設計約束不是實作細節：只要那個參數不存在，
    「呼叫者忘了檢查退出碼」這個失效模式就**不可表達**。
    """
    params = set(inspect.signature(P.publish).parameters)
    for bad in ("rc", "returncode", "exit_code", "status", "agent_rc"):
        assert bad not in params, f"publish() 不該收 {bad}"


# ── 放行 ───────────────────────────────────────────────────────────────
def test_valid_token_publishes(ident, pub_hex, src, tmp_path):
    dest = tmp_path / "out" / "solution.py"
    r = P.publish(src, dest, _tok(ident, src), pub_hex=pub_hex)
    assert r["published"] is True and r["exit_code"] == P.EXIT_PUBLISHED
    assert dest.read_text() == src.read_text()


# ── 擋下（每一條都是負控制）─────────────────────────────────────────────
def test_no_token_no_publish(pub_hex, src, tmp_path):
    dest = tmp_path / "out" / "solution.py"
    r = P.publish(src, dest, None, pub_hex=pub_hex)
    assert r["published"] is False and r["exit_code"] == P.EXIT_NO_TOKEN
    assert not dest.exists()


def test_failed_run_cannot_even_get_a_token(ident, src):
    """沒過 ⇒ 鑄不出憑證 ⇒ **根本沒有東西可以拿去叫 publisher**。"""
    assert R.mint(_sum(False), ident=ident, artifact_path=src)["token"] is None


def test_tampered_token_no_publish(ident, pub_hex, src, tmp_path):
    t = _tok(ident, src)
    t["payload"]["verdict"] = "PASSED "
    dest = tmp_path / "out" / "solution.py"
    r = P.publish(src, dest, t, pub_hex=pub_hex)
    assert r["published"] is False and r["exit_code"] == P.EXIT_REJECTED
    assert not dest.exists()


def test_token_for_a_different_artifact_no_publish(ident, pub_hex, src, tmp_path):
    """憑證對的是 A，卻拿去發 B ⇒ 擋。"""
    t = _tok(ident, src)
    other = tmp_path / "other.py"
    other.write_text("def add(a, b):\n    return 999\n")
    dest = tmp_path / "out" / "x.py"
    r = P.publish(other, dest, t, pub_hex=pub_hex)
    assert r["published"] is False and not dest.exists()
    assert any("雜湊對不上" in x for x in r["reasons"])


def test_expired_token_no_publish(ident, pub_hex, src, tmp_path):
    t = _tok(ident, src, ttl_s=10, now=1000.0)
    dest = tmp_path / "out" / "solution.py"
    r = P.publish(src, dest, t, pub_hex=pub_hex, now=1011.0)
    assert r["published"] is False and not dest.exists()


def test_coverage_requirement_can_block(ident, pub_hex, tmp_path):
    """要求 `network_egress=enforced` 而那一跑沒有圍牆 ⇒ 擋。"""
    src = tmp_path / "s.py"; src.write_text("x = 1\n")
    s = _sum(True); s["attestation"] = {"enclosure": {"applied": False}}
    t = R.mint(s, ident=ident, artifact_path=src)["token"]
    dest = tmp_path / "out" / "s.py"
    r = P.publish(src, dest, t, pub_hex=pub_hex,
                  require_coverage={"network_egress": "enforced"})
    assert r["published"] is False and not dest.exists()


def test_existing_dest_is_refused_by_default(ident, pub_hex, src, tmp_path):
    """覆寫是不可逆的外部效應 ⇒ 預設拒絕。"""
    dest = tmp_path / "out" / "solution.py"
    dest.parent.mkdir()
    dest.write_text("原本就有的東西\n")
    r = P.publish(src, dest, _tok(ident, src), pub_hex=pub_hex)
    assert r["published"] is False and r["exit_code"] == P.EXIT_DEST_EXISTS
    assert dest.read_text() == "原本就有的東西\n"      # 沒被動到
    r2 = P.publish(src, dest, _tok(ident, src), pub_hex=pub_hex, overwrite=True)
    assert r2["published"] is True and dest.read_text() == src.read_text()


def test_no_force_escape_hatch():
    """🔴 `--force` 刻意不存在。可以繞過的閘門在需要它的那天一定會被繞過。"""
    params = set(inspect.signature(P.publish).parameters)
    assert "force" not in params and "skip_verify" not in params


def test_rejected_publish_leaves_no_partial_file(ident, pub_hex, src, tmp_path):
    """被擋下來時，目的地目錄裡不准留下任何半成品。"""
    t = _tok(ident, src); t["payload"]["verdict"] = "NOPE"
    dest = tmp_path / "out" / "solution.py"
    P.publish(src, dest, t, pub_hex=pub_hex)
    assert not dest.exists()
    assert not list((tmp_path / "out").glob("*")) if (tmp_path / "out").exists() else True


def test_dry_run_verifies_without_writing(ident, pub_hex, src, tmp_path):
    dest = tmp_path / "out" / "solution.py"
    r = P.publish(src, dest, _tok(ident, src), pub_hex=pub_hex, dry_run=True)
    assert r["published"] is False and r["exit_code"] == P.EXIT_PUBLISHED
    assert r["verify"]["ok"] is True
    assert not dest.exists()
