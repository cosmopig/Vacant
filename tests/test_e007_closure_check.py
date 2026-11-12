#!/usr/bin/env python3
import pytest
from ops.audits.e007_closure_check import selftest

def test_selftest_success():
    # 驗證 --selftest 在空 HOME 下退出碼為 0 且輸出含 VERDICT: E007_CLOSURE_OK
    assert selftest(None, None, None, None) == 0

def test_neg_control_pass_count():
    # 篡改 REPORT pass 數
    report = '{"cells_scored":4,"per_arm":{"A":{"n":2,"pass":0,"rate":0.0},"C":{"n":2,"pass":2,"rate":1.0}},"paired":{"A_vs_C":{"pairs":2,"A_only":0,"C_only":0,"mcnemar_p_two_sided":1.0}}}'
    packet = "# e007/e008 · DABench（資料分析題）A/C 對照——研究封包＋預註冊分析\n### 6.1 smoke 實測結果（2026-10-31 22:58 完賽，過關）"
    backlog = "- [x] **e007 DABench 冒煙完賽檢查** 判定 GO"
    assert selftest(report, packet, backlog, None) == 1

def test_neg_control_mcnemar():
    # 篡改 McNemar p
    report = '{"cells_scored":4,"per_arm":{"A":{"n":2,"pass":2,"rate":1.0},"C":{"n":2,"pass":2,"rate":1.0}},"paired":{"A_vs_C":{"pairs":2,"A_only":0,"C_only":0,"mcnemar_p_two_sided":0.01}}}'
    packet = "# e007/e008 · DABench（資料分析題）A/C 對照——研究封包＋預註冊分析\n### 6.1 smoke 實測結果（2026-10-31 22:58 完賽，過關）"
    backlog = "- [x] **e007 DABench 冒煙完賽檢查** 判定 GO"
    assert selftest(report, packet, backlog, None) == 1

def test_neg_control_backlog_unchecked():
    # BACKLOG 取消勾選
    report = '{"cells_scored":4,"per_arm":{"A":{"n":2,"pass":2,"rate":1.0},"C":{"n":2,"pass":2,"rate":1.0}},"paired":{"A_vs_C":{"pairs":2,"A_only":0,"C_only":0,"mcnemar_p_two_sided":1.0}}}'
    packet = "# e007/e008 · DABench（資料分析題）A/C 對照——研究封包＋預註冊分析\n### 6.1 smoke 實測結果（2026-10-31 22:58 完賽，過關）"
    backlog = "- [ ] **e007 DABench 冒煙完賽檢查** 判定 GO"
    assert selftest(report, packet, backlog, None) == 1

def test_neg_control_no_note():
    # 刪除收口註記
    report = '{"cells_scored":4,"per_arm":{"A":{"n":2,"pass":2,"rate":1.0},"C":{"n":2,"pass":2,"rate":1.0}},"paired":{"A_vs_C":{"pairs":2,"A_only":0,"C_only":0,"mcnemar_p_two_sided":1.0}}}'
    packet = "# e007/e008 · DABench（資料分析題）A/C 對照——研究封包＋預註冊分析\n### 6.1 smoke 實測結果（2026-10-31 22:58 完賽，過關）"
    backlog = "- [x] **e007 DABench 冒煙完賽檢查**"
    assert selftest(report, packet, backlog, None) == 1

def test_missing_file():
    # 驗證缺檔時乾淨退出不拋未捕獲異常
    assert selftest(None, None, None, None) == 1
