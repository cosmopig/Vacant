"""G3 發射前置門（vq-1zf；審查指示 #5「G3 準備工作」；11-06 指示 #5 六要素）。

範圍＝**發射前置**（離線、零模型呼叫、不發射）：
- 選題＝未見任務（bank 順序 − 已見集合，前 4 題，與 vq-1zf 預註冊一致）；
- 任務輸入凍結副本在 repo 內（sha256 可核），verify_frozen 抓篡改/缺檔；
- 預算門（≤12 格、300s/輪、日 ≤2M tok fail-closed、glm 唯一入口、無硬 token 上限→缺值 UNKNOWN）；
- 核准門 fail-closed：無核准信號→RC 2、0 模型呼叫；核准文件不合格→拒。

紅線：核准前禁止任何發射；不讀 /srv/eval hidden 與 scorer.py；缺值＝UNKNOWN 不填 0。
本檔 0 模型呼叫。
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import subprocess
import sys

import vacant_network.reqloop.g3gate as g3

REPO = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = REPO / "ops" / "reqloop" / "g3_gate" / "manifest.json"
BASE = REPO / "ops" / "reqloop" / "g3_gate"
EXPECTED_SELECTION = ["dab_129", "dab_144", "dab_176", "dab_216"]


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _loaded():
    assert MANIFEST.is_file(), "g3_gate manifest 未凍結"
    return g3.G3Plan.load(MANIFEST)


# ── 選題（未見任務）───────────────────────────────────────────────────

def test_unseen_selection_matches_preregistration():
    """選題規則用代碼重算＝vq-1zf 預註冊 4 題（bank 順序前 4 未見）。"""
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    sel = g3.unseen_selection(raw["bank"]["ordering"], set(raw["seen_set"]), 4)
    assert sel == EXPECTED_SELECTION


def test_unseen_selection_is_computation_not_hardcode():
    """同一函數對不同 bank/已見集合給不同結果（不是把 4 題寫死）。"""
    order = ["t1", "t2", "t3", "t4", "t5"]
    assert g3.unseen_selection(order, {"t2"}, 2) == ["t1", "t3"]
    assert g3.unseen_selection(order, {"t1", "t2", "t3"}, 2) == ["t4", "t5"]
    assert g3.unseen_selection(order, set(), 1) == ["t1"]


def test_unseen_selection_insufficient_raises():
    try:
        g3.unseen_selection(["a", "b"], {"a", "b"}, 1)
    except ValueError:
        return
    raise AssertionError("未見題不足必須 raise（fail-closed）")


# ── 凍結副本 ─────────────────────────────────────────────────────────

def test_plan_load_and_verify_frozen():
    plan = _loaded()
    plan.verify_frozen(BASE)   # 16 個輸入檔 sha256 全核＋選題一致性
    assert set(plan.arms) == {"native_pi", "reqlist_only", "full_rloop"}
    assert [t["task_id"] for t in plan.tasks] == EXPECTED_SELECTION


def test_verify_frozen_detects_tampered_sha(tmp_path: pathlib.Path):
    (tmp_path / "tasks" / "t1").mkdir(parents=True)
    f = tmp_path / "tasks" / "t1" / "instruction.txt"
    f.write_text("hi", encoding="utf-8")
    man = {
        "schema": g3.PLAN_SCHEMA,
        "frozen_at": "2026-11-08T00:00:00+0800",
        "ticket": "test",
        "arms": ["a1"],
        "tasks": [{"task_id": "t1", "files": {"instruction.txt": "0" * 64}}],
        "seen_set": [],
        "bank": {"name": "test", "ordering": ["t1"], "n_total": 1},
        "budget": g3.DEFAULT_BUDGET,
        "approval": {"required": True, "epic": "vq-1zf",
                     "schema": g3.APPROVAL_SCHEMA, "mechanism": "test"},
    }
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(man), encoding="utf-8")
    plan = g3.G3Plan.load(p)
    try:
        plan.verify_frozen(tmp_path)
    except ValueError:
        return
    raise AssertionError("篡改 sha 必須被抓（fail-closed）")


def test_verify_frozen_detects_missing_file(tmp_path: pathlib.Path):
    (tmp_path / "tasks" / "t1").mkdir(parents=True)
    f = tmp_path / "tasks" / "t1" / "instruction.txt"
    f.write_text("hi", encoding="utf-8")
    man = {
        "schema": g3.PLAN_SCHEMA,
        "frozen_at": "2026-11-08T00:00:00+0800",
        "ticket": "test",
        "arms": ["a1"],
        "tasks": [{"task_id": "t1",
                   "files": {"instruction.txt": _sha(f), "ghost.csv": "0" * 64}}],
        "seen_set": [],
        "bank": {"name": "test", "ordering": ["t1"], "n_total": 1},
        "budget": g3.DEFAULT_BUDGET,
        "approval": {"required": True, "epic": "vq-1zf",
                     "schema": g3.APPROVAL_SCHEMA, "mechanism": "test"},
    }
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(man), encoding="utf-8")
    plan = g3.G3Plan.load(p)
    try:
        plan.verify_frozen(tmp_path)
    except FileNotFoundError:
        return
    raise AssertionError("缺檔必須被抓（fail-closed）")


# ── 預算門 ────────────────────────────────────────────────────────────

def test_check_budget_accepts_frozen_plan():
    g3.check_budget(_loaded())


def test_check_budget_rejects_over_cell_cap(tmp_path: pathlib.Path):
    plan = _loaded()
    bad = {**plan.raw, "budget": {**plan.budget, "max_cells": 5}}
    p = _tmp_manifest(tmp_path, bad)
    try:
        g3.check_budget(g3.G3Plan.load(p))
    except ValueError:
        return
    raise AssertionError("12 格超上限必須拒")


def test_check_budget_rejects_missing_daily_cap(tmp_path: pathlib.Path):
    plan = _loaded()
    bad = {**plan.raw, "budget": {k: v for k, v in plan.budget.items()
                                  if k != "daily_token_cap"}}
    p = _tmp_manifest(tmp_path, bad)
    try:
        g3.check_budget(g3.G3Plan.load(p))
    except ValueError:
        return
    raise AssertionError("缺日 token 上限必須拒（fail-closed）")


def test_check_budget_rejects_wrong_entry(tmp_path: pathlib.Path):
    plan = _loaded()
    bad = {**plan.raw, "budget": {**plan.budget, "model_entry": "vibe"}}
    p = _tmp_manifest(tmp_path, bad)
    try:
        g3.check_budget(g3.G3Plan.load(p))
    except ValueError:
        return
    raise AssertionError("模型入口不是 glm 必須拒")


def _tmp_manifest(tmp_path: pathlib.Path, raw: dict) -> pathlib.Path:
    d = tmp_path / f"manifest_{abs(hash(json.dumps(raw)))}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "tasks").mkdir(exist_ok=True)
    p = d / "manifest.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    return p


def test_no_leftover_temp_directories_in_tmp(tmp_path: pathlib.Path):
    """_tmp_manifest 不得在 /tmp 根建立 g3gate_* 洩漏目錄。

    r1240 hermetic 修正：舊版斷言 /tmp「絕對乾淨」，但 ci.sh 以共享 worktree 依
    qwen27b→argon→worker 順序跑各分支 HEAD——同一輪 qwen27b 的舊 mkdtemp 版測試先跑，
    殘留 /tmp/g3gate_* 會誤傷 argon 的守衛（e847c56e 實測：1 failed, 5052 passed）。
    改為前後集合差：只在「本 helper 新建洩漏」時失敗，不受既有殘留影響；
    對 mkdtemp 回歸的偵測力不變（負控：還原 mkdtemp 版 _tmp_manifest 時本測試必紅）。
    """
    import glob
    baseline = set(glob.glob("/tmp/g3gate_*"))
    p = _tmp_manifest(tmp_path, {"hermetic_guard": True})
    assert p.is_file()
    new = set(glob.glob("/tmp/g3gate_*")) - baseline
    assert not new, f"_tmp_manifest 在 /tmp 根新建洩漏目錄：{sorted(new)}"


# ── 核准門（fail-closed）─────────────────────────────────────────────

def test_approval_gate_rejects_absent_or_invalid():
    ok, why = g3.approval_gate(None)
    assert not ok and why
    for doc in (
        {"approved": True, "epic": "vq-1zf"},                          # 缺 schema
        {"schema": g3.APPROVAL_SCHEMA, "approved": False,
         "epic": "vq-1zf", "by": "human"},                             # approved≠true
        {"schema": g3.APPROVAL_SCHEMA, "approved": True,
         "epic": "vq-1zf.9", "by": "human"},                           # epic 不符
        {"schema": g3.APPROVAL_SCHEMA, "approved": True,
         "epic": "vq-1zf", "by": ""},                                  # 無核准者
        "not a dict",
    ):
        ok, why = g3.approval_gate(doc)
        assert not ok, f"必須拒：{doc!r}"
        assert why


def test_approval_gate_accepts_valid():
    doc = {"schema": g3.APPROVAL_SCHEMA, "approved": True,
           "epic": "vq-1zf", "by": "human-approver"}
    ok, why = g3.approval_gate(doc)
    assert ok, why


# ── CLI：一條指令 ─────────────────────────────────────────────────────

def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "vacant_network.reqloop.g3gate", *args],
        cwd=str(REPO), capture_output=True, text=True, timeout=120,
    )


def test_cli_plan_rc0_and_not_fired():
    r = _run("--plan")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "12" in r.stdout                       # 12 格
    assert "NOT FIRED" in r.stdout                # 核准前＝未發射
    assert "0 model calls" in r.stdout            # 如實：0 模型呼叫
    assert "G3GATE PLAN OK" in r.stdout


def test_cli_fire_without_approval_rc2_zero_calls():
    r = _run("--fire")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "NOT FIRED" in r.stdout
    assert "0 model calls" in r.stdout


def test_cli_fire_with_invalid_approval_rc2(tmp_path: pathlib.Path):
    bad = tmp_path / "approval.json"
    bad.write_text(json.dumps({"approved": True, "epic": "vq-1zf"}),
                   encoding="utf-8")
    r = _run("--fire", "--approval", str(bad))
    assert r.returncode == 2, r.stdout + r.stderr
    assert "NOT FIRED" in r.stdout
    assert "0 model calls" in r.stdout
