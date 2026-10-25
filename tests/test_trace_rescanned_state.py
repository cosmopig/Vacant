"""round 49：rescan 救回之後，用戶看到的觀察狀態必須是「現在時」的。

現場案例（本倉庫自己的病歷，seq 3208→3212）：

- seq 3208  coverage  scan_disabled = "the first scan after `vacant gc` passed 8s"
- seq 3212  coverage  rescanned（自動救回）：25,894 檔 / 13.3s，`was_disabled: true`，
            產出的 index 就是 state.json 現在的 `last_index`
- state.json  `scan_disabled: null`、`auto_rescan: null` —— 觀察**已經活著**

但 `vacant trace show`／`trace blame`／回合結束回饋照樣印：

    coverage: file-change observation is disabled — the first scan after `vacant gc` passed 8s
    … revive it with `vacant trace rescan`

指著一個已經健康的狀態，還建議一個不需要的動作。原因是解讀層只看「最後一筆停用事件」，
不看它之後的 `rescanned`。round 47 之前停用是永久的，這是裝飾問題；round 47 之後
rescan 是正常路徑，stale 的停用狀態變成 `blame_location` 對健康專案回
UNOBSERVED「not observed step by step」的**功能**問題。

修後語義：觀察狀態＝**最後一個改變狀態的** coverage 事件（`scan_disabled` 或
`rescanned`）；`rescanned` 是成功才記進鏈的（`recorder.baseline(refresh=True)` 的
成功分支），所以它之後觀察就是活著。
"""
from __future__ import annotations

import json

import pytest

from vacant_network.intake import contract as C
from vacant_network.intake import keys
from vacant_network.trace import blame as B
from vacant_network.trace import cli
from vacant_network.trace import feedback as F
from vacant_network.trace import recorder as R

INDEX = "4363fb1d6105c4c564c3f1d0d8f9038d0b27d0e09e7b81a56a814dadfc40a9e8"


def _rescanned_payload() -> dict:
    """coverage 事件的 `rescanned` 欄位形狀（`recorder.baseline(refresh=True)` 成功路徑；
    失敗不記進鏈）。"""
    return {"rescanned": {"rescanned": True, "was_disabled": True,
                         "after_unobserved": False, "files": 25894,
                         "index": INDEX, "seconds": 13.3}}


def _cov(rec: R.Recorder, payload: dict) -> None:
    rec._append("coverage", payload)


# ---------------------------------------------------------------- 解讀層（純函式）


def test_last_scan_disabled_rescanned_clears_it():
    evs = [
        {"type": "step", "seq": 1, "n": 1},
        {"type": "coverage", "seq": 2, "scan_disabled": "the first scan after `vacant gc` passed 8s"},
        {"type": "coverage", "seq": 3, **_rescanned_payload()},
    ]
    assert F.last_scan_disabled(evs) is None


def test_last_scan_disabled_still_reports_when_rescan_never_came():
    evs = [
        {"type": "coverage", "seq": 2, "scan_disabled": "the first scan after `vacant gc` passed 8s"},
    ]
    assert F.last_scan_disabled(evs) == "the first scan after `vacant gc` passed 8s"
    assert F.last_scan_disabled([{"type": "step", "seq": 1}]) is None


def test_last_scan_disabled_later_disable_after_rescan_still_reports():
    evs = [
        {"type": "coverage", "seq": 1, **_rescanned_payload()},
        {"type": "coverage", "seq": 2, "scan_disabled": "an incremental scan passed 8s"},
    ]
    assert F.last_scan_disabled(evs) == "an incremental scan passed 8s"


def test_last_scan_disabled_earlier_baseline_does_not_mask_disable():
    # 基線事件在停用**之前**：不能把停用蓋掉（reverse 走會先遇到停用）
    evs = [
        {"type": "coverage", "seq": 1, "baseline": {"index": INDEX, "files": 10, "after_unobserved": False}},
        {"type": "coverage", "seq": 2, "scan_disabled": "an incremental scan passed 8s"},
    ]
    assert F.last_scan_disabled(evs) == "an incremental scan passed 8s"


def test_last_scan_disabled_deferred_then_disable_then_rescanned():
    evs = [
        {"type": "coverage", "seq": 1, "baseline_deferred": "first scan passed its deadline"},
        {"type": "coverage", "seq": 2, "scan_disabled": "the background first look did not finish in 30s"},
        {"type": "coverage", "seq": 3, **_rescanned_payload()},
    ]
    assert F.last_scan_disabled(evs) is None


# ------------------------------------------------------------ coverage_summary


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.delenv("VACANT_TRACE", raising=False)
    keys.init_local()
    p = tmp_path / "proj"
    p.mkdir()
    (p / "a.txt").write_text("hello\n")
    return p, R.Recorder(p)


def test_coverage_summary_no_disabled_after_rescan(proj):
    p, rec = proj
    rec.pre("s1", R.Actor("pi", "s1"), "Bash", {})
    rec.post("s1", R.Actor("pi", "s1"), "Bash", {}, "")
    _cov(rec, {"scan_disabled": "the first scan after `vacant gc` passed 8s"})
    _cov(rec, _rescanned_payload())
    cov = F.coverage_summary(R.Recorder(p))
    assert "scan_disabled" not in cov
    assert cov["steps"] == 1


def test_coverage_summary_disabled_when_rescan_never_came(proj):
    p, rec = proj
    _cov(rec, {"scan_disabled": "an incremental scan passed 8s"})
    cov = F.coverage_summary(R.Recorder(p))
    assert cov.get("scan_disabled") == "an incremental scan passed 8s"


# ------------------------------------------------------------------- blame 層


def test_trace_state_after_rescan_is_healthy(proj):
    p, rec = proj
    _cov(rec, {"baseline_deferred": "first scan passed its deadline"})
    _cov(rec, {"scan_disabled": "the background first look did not finish in 30s"})
    tr = B.Trace(R.Recorder(p))
    assert tr.scan_disabled == "the background first look did not finish in 30s"
    assert tr.first_look_pending is True            # 第一次看還沒完成時
    _cov(R.Recorder(p), _rescanned_payload())
    tr = B.Trace(R.Recorder(p))
    assert tr.scan_disabled is None
    assert tr.first_look_pending is False
    assert tr.initial == INDEX                       # 第一次完整觀察＝rescan 那次


def test_trace_state_still_disabled_without_rescan(proj):
    p, rec = proj
    _cov(rec, {"scan_disabled": "an incremental scan passed 8s"})
    tr = B.Trace(R.Recorder(p))
    assert tr.scan_disabled == "an incremental scan passed 8s"


# ---------------------------------------------------------------------- CLI


def test_show_no_stale_banner_after_rescan(proj, capsys, monkeypatch):
    p, rec = proj
    rec.pre("s1", R.Actor("pi", "s1"), "Bash", {})
    rec.post("s1", R.Actor("pi", "s1"), "Bash", {}, "")
    _cov(rec, {"scan_disabled": "the first scan after `vacant gc` passed 8s"})
    _cov(rec, _rescanned_payload())
    monkeypatch.chdir(p)
    assert cli.main(["trace", "show"]) == 0
    out = capsys.readouterr().out
    assert "observation is disabled" not in out
    assert "vacant trace rescan" not in out


def test_show_banner_still_there_when_still_disabled(proj, capsys, monkeypatch):
    p, rec = proj
    _cov(rec, {"scan_disabled": "the first scan after `vacant gc` passed 8s"})
    monkeypatch.chdir(p)
    assert cli.main(["trace", "show"]) == 0
    out = capsys.readouterr().out
    assert "observation is disabled" in out
    assert "the first scan after `vacant gc` passed 8s" in out
    assert "vacant trace rescan" in out


def _blame_proj(tmp_path, monkeypatch):
    """`trace blame` 要契約（`test_trace_blame_coverage._proj` 的形狀）。"""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.delenv("VACANT_TRACE", raising=False)
    keys.init_local()
    p = tmp_path / "proj"
    (p / ".vacant").mkdir(parents=True)
    monkeypatch.chdir(p)
    (p / "a.txt").write_text("hello\n")
    cp = p / ".vacant" / "contract.json"
    cp.write_text(json.dumps(C.scaffold("cov", deliverable=["a.txt"])))
    C.lock(cp)
    rec = R.Recorder(p)
    rec.pre("s1", R.Actor("claude", "s1"), "Bash", {"command": "ls"})
    rec.post("s1", R.Actor("claude", "s1"), "Bash", {"command": "ls"}, "")
    return p


def test_blame_not_unobserved_after_rescan(tmp_path, monkeypatch, capsys):
    p = _blame_proj(tmp_path, monkeypatch)
    rec = R.Recorder(p)
    _cov(rec, {"scan_disabled": "the first scan after `vacant gc` passed 8s"})
    _cov(rec, _rescanned_payload())
    rc = cli.main(["--contract", str(p / ".vacant/contract.json"), "blame", "a.txt:1"])
    assert rc == 0
    out = capsys.readouterr().out
    # 救回之後：不該再對健康專案回「沒被逐步觀察」＋「去 rescan」
    assert "observation is disabled" not in out
    assert "not observed step by step" not in out


def test_blame_unobserved_when_still_disabled(tmp_path, monkeypatch, capsys):
    p = _blame_proj(tmp_path, monkeypatch)
    _cov(R.Recorder(p), {"scan_disabled": "an incremental scan passed 8s"})
    rc = cli.main(["--contract", str(p / ".vacant/contract.json"), "blame", "a.txt:1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "observation is disabled" in out
    assert "not observed step by step" in out
