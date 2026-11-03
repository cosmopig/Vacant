"""e016 C-nf 消融開關：`VACANT_FAILED_STEP_REVIEW=0` 關掉 failed_step(test_failed) 的交件前退回。

- 預設（未設）＝現在的行为、**位元組級不變**（invariant #1：無問題時與沒裝 Vacant 的路徑一致；
  此開關只在 C-nf 實驗臂設定）。
- fail-open：讀取環境出錯一律回預設（on），絕不因此擋住任何一跑。
- 開關只影響「退回給 agent」；chain 記錄（`findings`）、交件說明（left_open）、觀察模式不受影響。
"""
from vacant_network.trace.zerostop import pushable_for

FS = {"finding_id": "fs1", "kind": "failed_step", "sub": "test_failed", "step": 12,
      "cmd": "python -m pytest", "error": "assert 1 == 2"}
U = {"finding_id": "u1", "kind": "unread", "path": "src/x.py"}


def test_default_failed_step_is_pushable():
    assert [f["finding_id"] for f in pushable_for([dict(FS)], used=0, error_stop=False)] == ["fs1"]


def test_default_round_cap_still_one():
    assert pushable_for([dict(FS)], used=1, error_stop=False) == []


def test_switch_off_disables_kickback(monkeypatch):
    monkeypatch.setenv("VACANT_FAILED_STEP_REVIEW", "0")
    assert pushable_for([dict(FS)], used=0, error_stop=False) == []


def test_switch_off_only_affects_failed_step(monkeypatch):
    monkeypatch.setenv("VACANT_FAILED_STEP_REVIEW", "0")
    out = pushable_for([dict(FS), dict(U)], used=0, error_stop=False)
    assert [f["finding_id"] for f in out] == ["u1"]


def test_switch_on_explicit_keeps_current(monkeypatch):
    monkeypatch.setenv("VACANT_FAILED_STEP_REVIEW", "1")
    assert [f["finding_id"] for f in pushable_for([dict(FS)], used=0, error_stop=False)] == ["fs1"]


def test_switch_garbage_value_is_default(monkeypatch):
    monkeypatch.setenv("VACANT_FAILED_STEP_REVIEW", "garbage")
    assert [f["finding_id"] for f in pushable_for([dict(FS)], used=0, error_stop=False)] == ["fs1"]
