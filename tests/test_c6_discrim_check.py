"""ops/audits/c6_discrim_check.py 的核心邏輯鎖定（vq-ifn，round 1055）。

鎖兩件事（快、決定性、不跑 6000 步）：
1. 裁決表：只有 fixed=PASS 且 unfixed=FAIL 才算鑑別；「兩邊都過」＝非鑑別
   （r1018 教訓：unfixed 也過的門禁 4 次有 3 次放行回歸）。
2. 漂移鎖定：腳本指名要跑的測試函式必須真的在 tests/test_stepchain_sealing.py 裡
   （腳本不重實作協定，直接跑 repo 測試函式本身；函式改名/刪除要在这里先亮紅）。
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops" / "audits" / "c6_discrim_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("c6_discrim_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_classify_only_fixed_pass_unfixed_fail_is_discriminating():
    chk = _load()
    assert chk.classify(True, False) == "DISCRIMINATING"


def test_classify_both_pass_is_not_discriminating_r1018_lesson():
    chk = _load()
    v = chk.classify(True, True)
    assert v.startswith("NOT-DISCRIMINATING")
    assert "兩邊都過" in v    # 必須指名原因（r1018 coin-flip），不許靜默放行


def test_classify_fixed_fail_is_not_discriminating():
    chk = _load()
    assert chk.classify(False, False).startswith("NOT-DISCRIMINATING")
    assert chk.classify(False, True).startswith("NOT-DISCRIMINATING")


def test_named_test_function_exists_and_is_bound_to_injected_recorder():
    """腳本要跑的函式名與測試檔不能漂移；且注入機制要真的把函式綁到指定 recorder。"""
    chk = _load()
    sys.modules.pop("c6check_tss", None)
    spec = importlib.util.spec_from_file_location(
        "c6check_tss", ROOT / "tests" / "test_stepchain_sealing.py")
    tss = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tss)
    fn = getattr(tss, chk.TEST_FN, None)
    assert fn is not None, f"tests/test_stepchain_sealing.py 找不到 {chk.TEST_FN}（改名需同步腳本）"

    # 綁定機制：偽模組掛上後，全新 import 的測試模組 R 必須是它（driver 同款斷言）
    import types
    fake = types.ModuleType("vacant_network.trace.recorder")
    fake.Actor = lambda *a, **k: None    # 測試模組模組層 `MAIN = R.Actor("pi", "s1")` 需要
    import vacant_network.trace as trace_pkg
    old_mod = sys.modules.get("vacant_network.trace.recorder")
    old_attr = getattr(trace_pkg, "recorder", None)
    sys.modules["vacant_network.trace.recorder"] = fake
    trace_pkg.recorder = fake
    try:
        sys.modules.pop("c6check_tss", None)
        spec2 = importlib.util.spec_from_file_location("c6check_tss", ROOT / "tests" / "test_stepchain_sealing.py")
        tss2 = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(tss2)
        assert tss2.R is fake
    finally:
        if old_mod is not None:
            sys.modules["vacant_network.trace.recorder"] = old_mod
        else:
            sys.modules.pop("vacant_network.trace.recorder", None)
        trace_pkg.recorder = old_attr
        sys.modules.pop("c6check_tss", None)


def test_unfixed_ref_is_direct_parent_of_fix_commit():
    """a85dd2a1^ 必須是修復 commit a85dd2a1 的直接父（不是隨便一個舊點）。"""
    import subprocess
    chk = _load()
    parent = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", f"{chk.FIX_COMMIT}^"], text=True).strip()
    actual = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", chk.UNFIXED_REF], text=True).strip()
    assert actual == parent, f"UNFIXED_REF={chk.UNFIXED_REF} 不是 {chk.FIX_COMMIT} 的直接父"
