"""LCB bank v2 的登錄與 fail-closed 驗收（R440，2026-09-04）。

這支在架構裡承重什麼：v2 是**加題**，不是**換題**。E3（`runs/g_r443_gemma_lcb`）
與 R440O／R440T 的所有裁決都釘在 v1 的 sha／91 題上，所以這裡最重要的一條測試
不是「v2 能不能載」，是「v1 的三個釘值一個字都沒被動到、預設也還是 v1」。

其餘照 EvalPlus loader 的同款紀律：sha 篡改拒收、題數不符拒收、未知版本拒收，
外加 LCB 專屬的 arity 檢查（簽名參數個數 == 每一筆測資 args 長度）——R440T 那
兩題「精確解也會被判錯」就是量具覆蓋率不足才漏掉的，arity 這一關要逐題驗滿。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil

import pytest

from ops.gain.verify_lcb_bank import PROBE_PATH, check_arity, signature_of
from vacant.codebench import (
    LCB_BANK_DEFAULT_PATH,
    LCB_BANK_DEFAULT_VERSION,
    LCB_BANK_V1_COUNT,
    LCB_BANK_V1_SHA256,
    LCB_BANK_V2_COUNT,
    LCB_BANK_V2_PATH,
    LCB_BANK_V2_SHA256,
    LCB_BANKS,
    LiveCodeBenchLoader,
)


def _records(path: str) -> list[dict]:
    return [json.loads(ln) for ln in
            pathlib.Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]


# ── v1 不可動（E3 與其上的裁決都釘在這三個常數） ──────────────────────
def test_v1_pins_are_literally_unchanged():
    assert LCB_BANK_DEFAULT_PATH == "ops/gain/data/lcb_bank_v1.jsonl"
    assert LCB_BANK_V1_SHA256 == (
        "eb2a58760818d54b0a0141aa37e1603f875c53ccc76a2d87a6bf044b39a6c659")
    assert LCB_BANK_V1_COUNT == 91
    got = hashlib.sha256(pathlib.Path(LCB_BANK_DEFAULT_PATH).read_bytes()).hexdigest()
    assert got == LCB_BANK_V1_SHA256


def test_default_loader_still_v1(monkeypatch):
    monkeypatch.delenv("VACANT_LCB_VERSION", raising=False)
    monkeypatch.delenv("VACANT_LCB_PATH", raising=False)
    ld = LiveCodeBenchLoader()
    assert LCB_BANK_DEFAULT_VERSION == "v1"
    assert ld.version == "v1"
    assert ld.path == LCB_BANK_DEFAULT_PATH
    assert ld.expected_sha256 == LCB_BANK_V1_SHA256
    assert len(list(ld.iter_tasks("seed"))) == LCB_BANK_V1_COUNT


# ── v2 登錄 ───────────────────────────────────────────────────────────
def test_v2_registered_and_pinned():
    assert LCB_BANKS["v2"] == {"path": LCB_BANK_V2_PATH,
                               "sha256": LCB_BANK_V2_SHA256,
                               "count": LCB_BANK_V2_COUNT}
    got = hashlib.sha256(pathlib.Path(LCB_BANK_V2_PATH).read_bytes()).hexdigest()
    assert got == LCB_BANK_V2_SHA256
    ld = LiveCodeBenchLoader(version="v2")
    assert len(list(ld.iter_tasks("seed"))) == LCB_BANK_V2_COUNT


def test_v2_selectable_by_env(monkeypatch):
    monkeypatch.setenv("VACANT_LCB_VERSION", "v2")
    monkeypatch.delenv("VACANT_LCB_PATH", raising=False)
    ld = LiveCodeBenchLoader()
    assert ld.version == "v2" and ld.path == LCB_BANK_V2_PATH
    assert len(ld._records) == LCB_BANK_V2_COUNT


def test_unknown_version_rejected():
    # round735（R467）：原本這裡寫的是 `version="v3"`——那是 v3 還不存在時寫的。
    # round728 把 v3 建成真的 bank 之後，這條測試就**過期**了（測試過期 ≠ 真缺陷）：
    # 它從 round728 起一直是紅的，而 `tests/` 在這台沒有 pytest、長期沒被真的跑過。
    # 意圖（未知版本要被拒收）原樣保留，改用一個真的不存在的版本；
    # 同時把「v3 現在是合法的」這件事也釘住，免得下次又靠一條過期的紅燈來記錄它。
    with pytest.raises(ValueError):
        LiveCodeBenchLoader(version="v99")
    assert LiveCodeBenchLoader(version="v3").version == "v3"


def test_v2_is_superset_of_v1_and_reuses_v1_records_verbatim():
    """v2 只准**加題**。重疊的題目逐欄相同，否則 E3 的結果就不能跟 v2 對照。"""
    v1 = {r["task_id"]: r for r in _records(LCB_BANK_DEFAULT_PATH)}
    v2 = {r["task_id"]: r for r in _records(LCB_BANK_V2_PATH)}
    assert set(v1) <= set(v2)
    assert len(v2) > len(v1)
    for tid, rec in v1.items():
        assert v2[tid] == rec, tid


# ── fail-closed ───────────────────────────────────────────────────────
def test_tampered_v2_rejected(tmp_path):
    dst = tmp_path / "tampered.jsonl"
    shutil.copy(LCB_BANK_V2_PATH, dst)
    raw = bytearray(dst.read_bytes())
    raw[len(raw) // 2] ^= 0x01          # 只翻一個 bit
    dst.write_bytes(bytes(raw))
    with pytest.raises(ValueError, match="sha256"):
        LiveCodeBenchLoader(path=str(dst), expected_sha256=LCB_BANK_V2_SHA256,
                            expected_count=LCB_BANK_V2_COUNT)


def test_truncated_v2_rejected_on_count(tmp_path):
    """sha 對得上也要擋——這裡故意用被砍過的檔自己的 sha，逼題數那道關出手。"""
    dst = tmp_path / "short.jsonl"
    lines = pathlib.Path(LCB_BANK_V2_PATH).read_text(encoding="utf-8").splitlines()
    dst.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    own = hashlib.sha256(dst.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="題數不符"):
        LiveCodeBenchLoader(path=str(dst), expected_sha256=own,
                            expected_count=LCB_BANK_V2_COUNT)


def test_env_path_alone_cannot_smuggle_v2_under_v1_pins(monkeypatch):
    """VACANT_LCB_PATH 只換路徑、不換釘值：拿 v2 檔配 v1 預設必須被 sha 擋下。"""
    monkeypatch.delenv("VACANT_LCB_VERSION", raising=False)
    monkeypatch.setenv("VACANT_LCB_PATH", LCB_BANK_V2_PATH)
    with pytest.raises(ValueError, match="sha256"):
        LiveCodeBenchLoader()


# ── LCB 專屬：arity 與量具覆蓋率 ──────────────────────────────────────
def test_v2_arity_matches_signature_for_every_task():
    recs = _records(LCB_BANK_V2_PATH)
    ok, bad = check_arity(recs)
    assert not bad, bad[:5]
    assert ok == len(recs) == LCB_BANK_V2_COUNT


def test_v2_entry_point_matches_prompt_signature():
    for rec in _records(LCB_BANK_V2_PATH):
        fn, _params = signature_of(rec)
        assert fn == rec["entry_point"], rec["task_id"]


def test_v2_probe_coverage_at_least_twelve():
    """量具閘門：`--probe-sample 0` 至少要驗到 12 題（R441 手寫解在 v2 仍在池內）。

    R440T 的教訓：12 是**分母不是滿分**，所以這裡連覆蓋率一起釘出來，
    未來覆蓋率掉下去會有人被吵醒。"""
    probes = json.loads(PROBE_PATH.read_text(encoding="utf-8"))
    ids = {r["task_id"] for r in _records(LCB_BANK_V2_PATH)}
    covered = sorted(ids & set(probes))
    assert len(covered) >= 12, covered


def test_v2_hidden_check_embeds_every_visible_case():
    """CONFORM 的無損性論證前提：hidden = visible ⊎ private（R440Q）。

    不是比長度——直接證明 `hidden_check` 內嵌的測資串裡，可見那幾筆逐字都在，
    否則「可見過了 hidden 卻沒過」就不再是模型的錯而是題庫換了語意。"""
    ld = LiveCodeBenchLoader(version="v2")
    for t in ld.iter_tasks("seed"):
        hid = t["hidden_check"]["code"]
        for args in t["behavior_inputs"]:
            assert repr(args) in hid, t["task_id"]
        assert len(t["behavior_inputs"]) >= 1
