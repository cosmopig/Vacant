"""X1 TrustConfig — 信任前緣的 minimal 設定測試。

對應任務 X3-trust-frontier：建立 trust on/off、central、cost-aligned 的信任前緣。
此檔僅驗證 TrustConfig 資料類別的行為，不宣稱任何 effect。
"""

import pytest

from vacant.x1 import TrustConfig


# --- 基本建構與預設值 ---------------------------------------------------------

def test_trustconfig_defaults():
    """TrustConfig 所有欄位都有合理預設值。"""
    c = TrustConfig()
    assert c.mode == "on"
    assert c.central is True
    assert c.cost_aligned is True


def test_trustconfig_explicit_fields():
    """可明確指定所有欄位。"""
    c = TrustConfig(mode="off", central=False, cost_aligned=False)
    assert c.mode == "off"
    assert c.central is False
    assert c.cost_aligned is False


# --- mode 驗證 ---------------------------------------------------------------

def test_trustconfig_mode_on():
    """mode='on' 合法。"""
    c = TrustConfig(mode="on")
    assert c.mode == "on"


def test_trustconfig_mode_off():
    """mode='off' 合法。"""
    c = TrustConfig(mode="off")
    assert c.mode == "off"


def test_trustconfig_invalid_mode_raises():
    """非法 mode 值應拋出 ValueError。"""
    with pytest.raises(ValueError, match="必須是 'on' 或 'off'"):
        TrustConfig(mode="maybe")

    with pytest.raises(ValueError, match="必須是 'on' 或 'off'"):
        TrustConfig(mode="ON")

    with pytest.raises(ValueError, match="必須是 'on' 或 'off'"):
        TrustConfig(mode="")


# --- immutable（frozen）------------------------------------------------------

def test_trustconfig_is_frozen():
    """TrustConfig 應為 frozen dataclass，不可修改。"""
    c = TrustConfig()
    with pytest.raises(Exception):  # FrozenInstanceError
        c.mode = "off"


# --- central / cost_aligned 布林值 -------------------------------------------

def test_trustconfig_central_true():
    """central=True 合法。"""
    c = TrustConfig(central=True)
    assert c.central is True


def test_trustconfig_central_false():
    """central=False 合法。"""
    c = TrustConfig(central=False)
    assert c.central is False


def test_trustconfig_cost_aligned_true():
    """cost_aligned=True 合法。"""
    c = TrustConfig(cost_aligned=True)
    assert c.cost_aligned is True


def test_trustconfig_cost_aligned_false():
    """cost_aligned=False 合法。"""
    c = TrustConfig(cost_aligned=False)
    assert c.cost_aligned is False


# --- 組合測試 ----------------------------------------------------------------

def test_trustconfig_all_combinations():
    """mode × central × cost_aligned 的完整組合（2×2×2＝8 種）。"""
    for mode in ("on", "off"):
        for central in (True, False):
            for cost_aligned in (True, False):
                c = TrustConfig(mode=mode, central=central, cost_aligned=cost_aligned)
                assert c.mode == mode
                assert c.central is central
                assert c.cost_aligned is cost_aligned


# --- 驗證命令 ----------------------------------------------------------------

def test_trustconfig_verification_on_central_cost():
    """對應 verification command：from vacant.x1 import TrustConfig; c = TrustConfig(mode='on', central=True, cost_aligned=True); assert c.mode == 'on'"""
    from vacant.x1 import TrustConfig as TC
    c = TC(mode="on", central=True, cost_aligned=True)
    assert c.mode == "on"


def test_trustconfig_verification_off():
    """對應 verification command 的 off 變體。"""
    from vacant.x1 import TrustConfig as TC
    c = TC(mode="off", central=False, cost_aligned=False)
    assert c.mode == "off"
