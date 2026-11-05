#!/usr/bin/env python3
"""vq-ifn — C6-FLAT 門禁鑑別力檢查：一條指令，兩邊各跑一次，給一個裁決。

背景（r1018–r1054）：
  - 舊 C6 P99 門禁（tests/test_stepchain_sealing.py::test_g3_c6_append_p99_delta_le_10pct）
    分不出「per-append 成本隨活動卷增長」：r1018 在 unfixed 上 4 次有 3 次 xpass（coin-flip）；
    r1052/1053 對比 dabstep-23/dab_378 仍 xpass（3.0/3.6% vs 門檻 10%）。
  - 新候選門禁 test_g3_c6_append_cost_flat_with_volume_growth（c32f3a16，r1054 入庫）：
    6000 步、早期窗 [600,1000) vs 晚期窗 [5600,6000) 中位 append 成本差 ≤ 1.5 ms/step，
    封印事件結構性排除（vol_max_bytes=1e12）、entry 觸發器照啟用（掃描路徑照跑）。
  - 本檔把「鑑別力實證」收進 repo：兩邊都跑 **repo 內那條測試函式本身**
    （不平行重實作協定 ⇒ 零漂移），各給 PASS/FAIL，再合成一個裁決。
    取代 round 1054 的 workspace 暫行腳本（~/dev/ops/audits/c6_discrim_check.py、
    c6_unfixed_test_driver.py，保留作歷史證據）。

鑑別標準（vq-ifn 驗收準則）：
  新測試在 **unfixed** recorder（a85dd2a1^＝a85dd2a1 的直接父，per-append O(卷大小) 重數行）上 FAIL，
  且在 **fixed**（a85dd2a1+ 現行碼）上 PASS  ⇒  DISCRIMINATING（exit 0）。
  其餘任何組合都是 NOT-DISCRIMINATING（exit 1）——含「兩邊都過」：
  r1018 教訓：unfixed 也過的門禁＝非鑑別（4 次有 3 次放行回歸）。

紅線（redlines）：
  - 對 repo 唯讀（git show 取 unfixed 源碼；不 checkout、不改檔）。
  - 不讀 /srv/eval hidden／scorer.py；不觸碰凍結批次（effects_20261105、contrast378_20261105）。
  - 門檻 1.5 ms/step 跟隨測試檔（改門檻＝改預註冊準則，需審查輪，本腳本不帶 --threshold）。
  - 取不到 unfixed 源碼或測試函式不存在 ⇒ 印 UNKNOWN、exit 2（UNKNOWN ≠ PASS，不硬裁）。

用法：
  python3 ops/audits/c6_discrim_check.py        # 固定邊 + unfixed 邊各一次，末行是裁決
  rc=0 DISCRIMINATING；rc=1 NOT-DISCRIMINATING；rc=2 UNKNOWN（環境/引用問題，不是裁決）
"""
from __future__ import annotations

import importlib.util
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import types

UNFIXED_REF = "a85dd2a1^"          # 修復 commit a85dd2a1（r1015）的直接父
FIX_COMMIT = "a85dd2a1"            # 僅供印證
TEST_FILE = "tests/test_stepchain_sealing.py"
TEST_FN = "test_g3_c6_append_cost_flat_with_volume_growth"


def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


def load_unfixed_recorder(root: pathlib.Path) -> types.ModuleType:
    """git show 取 a85dd2a1^ 的 recorder.py，載入為 vacant_network.trace.recorder。

    a85dd2a1 只改 recorder.py 一檔，其餘依賴（canonical/keys）用已安裝的現行版——
    與 round 1054 的 driver 同一機制（已實證：測試模組確實綁到 unfixed 模組）。
    """
    src = subprocess.check_output(
        ["git", "-C", str(root), "show", f"{UNFIXED_REF}:vacant_network/trace/recorder.py"],
        text=True,
    )
    mod = types.ModuleType("vacant_network.trace.recorder")
    mod.__package__ = "vacant_network.trace"
    mod.__file__ = f"<unfixed {UNFIXED_REF}>"
    exec(compile(src, f"<unfixed {UNFIXED_REF}>", "exec"), mod.__dict__)
    return mod


def run_repo_test(recorder_module: types.ModuleType, label: str) -> tuple[bool, str]:
    """在給定 recorder 模組上跑 repo 測試函式本身。回傳 (passed, detail)。

    機制：把該模組掛到 sys.modules['vacant_network.trace.recorder']＋包屬性，再全新
    import 測試模組（模組名 c6check_tss，避免與 pytest 的 import 撞），執行後還原。
    """
    import vacant_network.trace as trace_pkg

    root = repo_root()
    td = pathlib.Path(tempfile.mkdtemp(prefix=f"c6_{label}_"))
    old_mod = sys.modules.get("vacant_network.trace.recorder")
    saved_attr = getattr(trace_pkg, "recorder", None)
    sys.modules["vacant_network.trace.recorder"] = recorder_module
    trace_pkg.recorder = recorder_module
    try:
        spec = importlib.util.spec_from_file_location("c6check_tss", root / TEST_FILE)
        tss = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tss)
        if tss.R is not recorder_module:
            return False, f"INTERNAL: 測試模組沒有綁到 {label} recorder（import 機制失靈）"
        fn = getattr(tss, TEST_FN, None)
        if fn is None:
            return False, f"INTERNAL: {TEST_FILE} 找不到 {TEST_FN}"
        try:
            fn(td)
            return True, ""
        except AssertionError as e:
            return False, str(e)
    finally:
        if old_mod is not None:
            sys.modules["vacant_network.trace.recorder"] = old_mod
        else:
            sys.modules.pop("vacant_network.trace.recorder", None)
        trace_pkg.recorder = saved_attr
        sys.modules.pop("c6check_tss", None)
        shutil.rmtree(td, ignore_errors=True)


def classify(fixed_passed: bool, unfixed_passed: bool) -> str:
    """裁決表（vq-ifn 驗收準則）：只有 fixed=PASS 且 unfixed=FAIL 才算鑑別。"""
    if fixed_passed and not unfixed_passed:
        return "DISCRIMINATING"
    if not fixed_passed:
        return "NOT-DISCRIMINATING (fixed 邊 FAIL＝現行碼回歸，先修)"
    return "NOT-DISCRIMINATING (兩邊都過＝非鑑別，r1018 教訓)"


def main() -> int:
    root = repo_root()
    t0 = time.time()
    print(f"# C6-FLAT 門禁鑑別力檢查（vq-ifn；repo={root.name}；"
          f"測試={TEST_FILE}::{TEST_FN}；unfixed={UNFIXED_REF}）")
    try:
        fixed_rec = importlib.import_module("vacant_network.trace.recorder")
        unfixed_rec = load_unfixed_recorder(root)
    except Exception as e:  # 環境/引用問題：UNKNOWN，不是裁決
        print(f"UNKNOWN: 無法載入兩邊 recorder（{type(e).__name__}: {e}）")
        return 2

    fixed_ok, fixed_detail = run_repo_test(fixed_rec, "fixed")
    print(f"fixed   [{FIX_COMMIT}+ 現行碼]: {'PASS' if fixed_ok else 'FAIL'}"
          + (f"  — {fixed_detail[:160]}" if fixed_detail else ""))
    unfixed_ok, unfixed_detail = run_repo_test(unfixed_rec, "unfixed")
    print(f"unfixed [{UNFIXED_REF} O(卷)重數行]: {'PASS' if unfixed_ok else 'FAIL'}"
          + (f"  — {unfixed_detail[:160]}" if unfixed_detail else ""))

    verdict = classify(fixed_ok, unfixed_ok)
    print(f"VERDICT: {verdict}   （{time.time() - t0:.0f}s）")
    return 0 if verdict == "DISCRIMINATING" else 1


if __name__ == "__main__":
    sys.exit(main())
