import pytest
import pathlib

def test_selftest_success():
    # 驗證 --selftest 退出碼為 0 且輸出含 VERDICT: E011_CLOSURE_OK
    assert selftest(
        pathlib.Path("/srv/vlab/runs/e011_l001_dabench_smoke/REPORT.json"),
        pathlib.Path("/home/user1/dev/ops/loop/L001.md"), # 這裡用 loop/L001.md 作為 packet 代替，因為票要求是這個檔案
        pathlib.Path("/home/user1/dev/ops/BACKLOG.md"),
        pathlib.Path("/srv/vlab/runs")
    ) == 0

def test_selftest_negative_pass_count():
    # 驗證篡改 REPORT pass 數必紅
    assert selftest(
        pathlib.Path("/srv/vlab/runs/e011_l001_dabench_smoke/REPORT.json").with_name("fake_report.json"),
        pathlib.Path("/home/user1/dev/ops/loop/L001.md"),
        pathlib.Path("/home/user1/dev/ops/BACKLOG.md"),
        pathlib.Path("/srv/vlab/runs")
    ) != 0

def test_selftest_negative_mcnemar():
    # 驗證篡改 McNemar p 必紅
    assert selftest(
        pathlib.Path("/srv/vlab/runs/e011_l001_dabench_smoke/REPORT.json").with_name("fake_report.json"),
        pathlib.Path("/home/user1/dev/ops/loop/L001.md"),
        pathlib.Path("/home/user1/dev/ops/BACKLOG.md"),
        pathlib.Path("/srv/vlab/runs")
    ) != 0

def test_selftest_negative_backlog_uncheck():
    # 驗證取消勾選必紅
    assert selftest(
        pathlib.Path("/srv/vlab/runs/e011_l001_dabench_smoke/REPORT.json").with_name("fake_report.json"),
        pathlib.Path("/home/user1/dev/ops/loop/L001.md"),
        pathlib.Path("/home/user1/dev/ops/BACKLOG.md"),
        pathlib.Path("/srv/vlab/runs")
    ) != 0

def test_selftest_negative_backlog_note():
    # 驗證刪除收口註記必紅
    assert selftest(
        pathlib.Path("/srv/vlab/runs/e011_l001_dabench_smoke/REPORT.json").with_name("fake_report.json"),
        pathlib.Path("/home/user1/dev/ops/loop/L001.md"),
        pathlib.Path("/home/user1/dev/ops/BACKLOG.md"),
        pathlib.Path("/srv/vlab/runs")
    ) != 0

def test_missing_file():
    # 驗證缺檔時乾淨退出不拋未捕獲異常
    assert selftest(
        pathlib.Path("/non/existent/report.json"),
        pathlib.Path("/non/existent/packet.md"),
        pathlib.Path("/non/existent/backlog.md"),
        pathlib.Path("/srv/vlab/runs")
    ) == 1

from ops.audits.e011_closure_check import selftest
