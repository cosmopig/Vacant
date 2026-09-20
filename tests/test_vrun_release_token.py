"""放行憑證：PASS 才鑄得出來，而且每一道關卡都要擋得住。

⚠ 每一個「會放行」的斷言都配一個「會擋下」的負控制——沒有負控制的綠燈
   跟一個永遠回 ok=True 的 stub 長得一樣。
"""
import pathlib
import time

import pytest

from vacant_network.identity import Identity
from vacant_network.vrun import release as R
from vacant_network import crypto


@pytest.fixture
def ident():
    return Identity.generate()


@pytest.fixture
def pub_hex(ident):
    return crypto.pub_to_hex(ident.pub)


def _summary(accepted=True, **over):
    d = {
        "task_id": "t1", "arm": "RUN-ON", "accepted": accepted,
        "ws_end_sha256": "w" * 64, "verdict_sha256": "v" * 64,
        "visible_passed": 3, "visible_total": 3,
        "model_wire": {"count_semantics": "exact"},
        "attestation": {"enclosure": {"applied": True},
                        "framework_hook": {"canary_fired": True},
                        "reconciled": {"unexplained": 0}},
    }
    d.update(over)
    return d


@pytest.fixture
def art(tmp_path):
    p = tmp_path / "solution.py"
    p.write_text("def add(a, b):\n    return a + b\n")
    return p


# ── 鑄造 ───────────────────────────────────────────────────────────────
def test_pass_mints(ident, art):
    r = R.mint(_summary(True), ident=ident, artifact_path=art)
    assert r["minted"] is True and r["token"]["payload"]["verdict"] == "PASSED"


def test_fail_does_not_mint(ident, art):
    """**負控制**：沒通過就鑄不出來。這是整個設計的重點。"""
    r = R.mint(_summary(False), ident=ident, artifact_path=art)
    assert r["minted"] is False and r["token"] is None
    assert r["verdict"] == "FAILED"


def test_accepted_none_does_not_mint(ident, art):
    """🔴 三態：`--allow-no-suite` 的 `accepted is None` ＝**沒量**，不是通過。"""
    r = R.mint(_summary(None), ident=ident, artifact_path=art)
    assert r["minted"] is False
    assert r["verdict"] == "UNVERIFIED"      # 與 FAILED 分得開
    assert "沒有跑驗收" in r["reason"]


# ── 驗證 ───────────────────────────────────────────────────────────────
def test_happy_path_verifies(ident, pub_hex, art):
    t = R.mint(_summary(), ident=ident, artifact_path=art)["token"]
    v = R.verify(t, pub_hex=pub_hex, artifact_path=art)
    assert v["ok"] is True, v["reasons"]


def test_swapped_artifact_is_rejected(ident, pub_hex, art, tmp_path):
    """**負控制**：憑證對的是另一份東西 ⇒ 擋。"""
    t = R.mint(_summary(), ident=ident, artifact_path=art)["token"]
    other = tmp_path / "other.py"
    other.write_text("def add(a, b):\n    return 999\n")
    v = R.verify(t, pub_hex=pub_hex, artifact_path=other)
    assert v["ok"] is False
    assert any("雜湊對不上" in x for x in v["reasons"])


def test_tampered_payload_is_rejected(ident, pub_hex, art):
    """**負控制**：改一個 byte 就要紅。"""
    t = R.mint(_summary(), ident=ident, artifact_path=art)["token"]
    t["payload"]["verdict"] = "PASSED "          # 多一個空白
    v = R.verify(t, pub_hex=pub_hex, artifact_path=art)
    assert v["ok"] is False
    assert any("簽章不符" in x for x in v["reasons"])


def test_wrong_key_is_rejected(ident, art):
    """**負控制**：別人的公鑰驗不過。"""
    t = R.mint(_summary(), ident=ident, artifact_path=art)["token"]
    v = R.verify(t, pub_hex=crypto.pub_to_hex(Identity.generate().pub),
                 artifact_path=art)
    assert v["ok"] is False


def test_expired_is_rejected(ident, pub_hex, art):
    t = R.mint(_summary(), ident=ident, artifact_path=art, ttl_s=10,
               now=1000.0)["token"]
    assert R.verify(t, pub_hex=pub_hex, artifact_path=art, now=1005.0)["ok"]
    v = R.verify(t, pub_hex=pub_hex, artifact_path=art, now=1011.0)
    assert v["ok"] is False and any("過期" in x for x in v["reasons"])


def test_missing_artifact_fails_closed(ident, pub_hex, art):
    """沒東西可比 ⇒ **不放行**（不是「沒問題所以放行」）。"""
    t = R.mint(_summary(), ident=ident, artifact_path=art)["token"]
    v = R.verify(t, pub_hex=pub_hex)          # 兩個 artifact 參數都不給
    assert v["ok"] is False
    assert any("fail-closed" in x for x in v["reasons"])


# ── coverage 三態 ──────────────────────────────────────────────────────
def test_coverage_none_is_not_achievement(ident, pub_hex, art):
    """🔴 `None` ＝**沒有宣稱**，不可以滿足「要求 enforced」。"""
    s = _summary(attestation={"enclosure": {"applied": None},
                              "framework_hook": {"canary_fired": None},
                              "reconciled": {"unexplained": None}})
    t = R.mint(s, ident=ident, artifact_path=art)["token"]
    assert t["payload"]["coverage"]["network_egress"] is None
    assert t["payload"]["coverage"]["tool_correlation"] is None
    v = R.verify(t, pub_hex=pub_hex, artifact_path=art,
                 require_coverage={"network_egress": "enforced"})
    assert v["ok"] is False
    assert any("沒有宣稱，不是達成" in x for x in v["reasons"])


def test_unenforced_and_unmeasured_are_different(ident, art):
    """`applied is False`（量到沒有）與 `None`（沒量到）不可同形。"""
    a = R.mint(_summary(attestation={"enclosure": {"applied": False}}),
               ident=ident, artifact_path=art)["token"]
    b = R.mint(_summary(attestation={"enclosure": {"applied": None}}),
               ident=ident, artifact_path=art)["token"]
    assert a["payload"]["coverage"]["network_egress"] == "unenforced"
    assert b["payload"]["coverage"]["network_egress"] is None


def test_artifact_externalization_is_always_none(ident, art):
    """🔴 這一層**擋不住呼叫者自己 cp**，所以永遠不准宣稱扣住了交付物。"""
    t = R.mint(_summary(), ident=ident, artifact_path=art)["token"]
    assert t["payload"]["coverage"]["artifact_externalization"] is None


def test_abpi_shaped_run_gets_lower_bound_and_unmeasured(ident, art):
    """用 abpi 那批的真實形狀（C 級、無圍牆、無掛鉤、排空逾時）造一張憑證。

    它應該誠實地說：wire 是下界、出網沒被強制、工具對帳沒量到。
    """
    s = _summary(model_wire={"count_semantics": "lower_bound"},
                 attestation={"enclosure": {"applied": False},
                              "framework_hook": {"canary_fired": None},
                              "reconciled": {"unexplained": None}})
    cov = R.mint(s, ident=ident, artifact_path=art)["token"]["payload"]["coverage"]
    assert cov["model_wire"] == "lower_bound"
    assert cov["network_egress"] == "unenforced"
    assert cov["tool_correlation"] is None
