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


# ── 預算門：放寬預註冊上限必須拒（r1408 vq-1zf.7）──────────────────
# RED 實證（本輪、舊碼）：manifest 寫 max_cells=999／timeout_s_per_round=3000／
# daily_token_cap=2e9，check_budget 全數接受→--plan 印 G3GATE PLAN OK（假綠燈）；
# 而 quota_fail_closed=False 等硬欄位已 fail-closed——三個數值上限是該函式唯一的
# fail-open 項，與函式自身 docstring「任何一項缺失/放寬即拒」及 DEFAULT_BUDGET
# 註解「manifest 可加嚴、不可放寬」矛盾（同族：r1376 UNKNOWN fail-open、r1405
# bool 當 int；ruler 不得信被驗方的自我聲明）。

def test_check_budget_rejects_loosened_cell_ceiling(tmp_path: pathlib.Path):
    """manifest 放寬預註冊 12 格上限（max_cells=999、12 格≤999）必須拒。"""
    plan = _loaded()
    bad = {**plan.raw, "budget": {**plan.budget, "max_cells": 999}}
    p = _tmp_manifest(tmp_path, bad)
    try:
        g3.check_budget(g3.G3Plan.load(p))
    except ValueError as e:
        assert "max_cells" in str(e)
        return
    raise AssertionError("max_cells=999 放寬 12 格預註冊上限必須拒（可加嚴、不可放寬）")


def test_check_budget_rejects_loosened_timeout_ceiling(tmp_path: pathlib.Path):
    """manifest 放寬預註冊 300s/輪上限（timeout_s_per_round=3000）必須拒。"""
    plan = _loaded()
    bad = {**plan.raw, "budget": {**plan.budget, "timeout_s_per_round": 3000}}
    p = _tmp_manifest(tmp_path, bad)
    try:
        g3.check_budget(g3.G3Plan.load(p))
    except ValueError as e:
        assert "timeout_s_per_round" in str(e)
        return
    raise AssertionError("timeout_s_per_round=3000 放寬 300s/輪預註冊上限必須拒")


def test_check_budget_accepts_amend2_pi_timeout_exactly_600(tmp_path: pathlib.Path):
    """正控制：AMEND-2（2026-11-11 人類常設授權）pi 臂每格牆時 cap＝600s＝預註冊
    上限——恰好等於上限不是放寬，必須接受（glm 的 timeout_s_per_round 仍 ≤300s）。"""
    plan = _loaded()
    at = {**plan.raw, "budget": {**plan.budget, "timeout_s_per_round_pi": 600}}
    p = _tmp_manifest(tmp_path, at)
    g3.check_budget(g3.G3Plan.load(p))   # 必須不 raise


def test_check_budget_rejects_loosened_pi_timeout_ceiling(tmp_path: pathlib.Path):
    """manifest 放寬 AMEND-2 預註冊 600s/格上限（timeout_s_per_round_pi=601）必須拒。

    首發後檢（票 P20261111_0645-1）：3× native_pi 格 300s 超時；AMEND-2 把 pi 臂
    每格牆時放到 600s、glm 維持 300s/輪——600 是新的預註冊上限，放寬仍拒（r1408
    同口徑：manifest 可加嚴、不可放寬）。"""
    plan = _loaded()
    bad = {**plan.raw, "budget": {**plan.budget, "timeout_s_per_round_pi": 601}}
    p = _tmp_manifest(tmp_path, bad)
    try:
        g3.check_budget(g3.G3Plan.load(p))
    except ValueError as e:
        assert "timeout_s_per_round_pi" in str(e)
        return
    raise AssertionError("timeout_s_per_round_pi=601 放寬 600s/格預註冊上限必須拒")


def test_check_budget_rejects_missing_pi_timeout_with_pi_arm(tmp_path: pathlib.Path):
    """model_entry=glm+local_pi（pi 臂在場）而 budget.timeout_s_per_round_pi 缺失
    必須拒——per-channel cap 必須在案（fail-closed；與 pi_provider/pi_model 同口徑）。"""
    plan = _loaded()
    raw = {**plan.raw, "budget": {
        k: v for k, v in plan.budget.items() if k != "timeout_s_per_round_pi"}}
    p = _tmp_manifest(tmp_path, raw)
    try:
        g3.check_budget(g3.G3Plan.load(p))
    except ValueError as e:
        assert "timeout_s_per_round_pi" in str(e)
        return
    raise AssertionError("pi 臂在場而 timeout_s_per_round_pi 缺失必須拒")


def test_check_budget_rejects_nonint_pi_timeout(tmp_path: pathlib.Path):
    """timeout_s_per_round_pi 非 int（字串）必須拒——門不得信被驗方的自我聲明（r1405 同族）。"""
    plan = _loaded()
    bad = {**plan.raw, "budget": {**plan.budget, "timeout_s_per_round_pi": "600"}}
    p = _tmp_manifest(tmp_path, bad)
    try:
        g3.check_budget(g3.G3Plan.load(p))
    except ValueError as e:
        assert "timeout_s_per_round_pi" in str(e)
        return
    raise AssertionError("timeout_s_per_round_pi='600'（非 int）必須拒")


def test_check_budget_rejects_loosened_daily_cap_ceiling(tmp_path: pathlib.Path):
    """manifest 放寬預註冊 2M/日上限（daily_token_cap=2e9）必須拒。"""
    plan = _loaded()
    bad = {**plan.raw, "budget": {**plan.budget, "daily_token_cap": 2_000_000_000}}
    p = _tmp_manifest(tmp_path, bad)
    try:
        g3.check_budget(g3.G3Plan.load(p))
    except ValueError as e:
        assert "daily_token_cap" in str(e)
        return
    raise AssertionError("daily_token_cap=2e9 放寬 2M/日預註冊上限必須拒")


def test_check_budget_accepts_exactly_preregistered_ceiling(tmp_path: pathlib.Path):
    """正控制：恰好等於上限（12/300/2M）不是放寬——必須接受。

    live manifest 恰好即此形（test_check_budget_accepts_frozen_plan 亦覆蓋）；
    加嚴方向（max_cells=5、12 格>5 被拒）由 test_check_budget_rejects_over_cell_cap 覆蓋。
    """
    plan = _loaded()
    at = {**plan.raw, "budget": {**plan.budget, "max_cells": 12,
                                 "timeout_s_per_round": 300,
                                 "daily_token_cap": 2_000_000}}
    p = _tmp_manifest(tmp_path, at)
    g3.check_budget(g3.G3Plan.load(p))   # 必須不 raise


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


# ── build_manifest：凍結 manifest 的唯一建造路徑（r1257 前零測試釘住）────

def _synthetic_bank(root: pathlib.Path) -> dict[str, dict[str, str]]:
    """6 題（t01..t06）；t03/t04 含巢狀目錄；回傳逐檔期望 sha256。"""
    files: dict[str, dict[str, str]] = {}
    for i in range(1, 7):
        tid = f"t{i:02d}"
        tdir = root / tid
        tdir.mkdir(parents=True)
        files[tid] = {}
        (tdir / "instruction.txt").write_text(f"task {tid}\n", encoding="utf-8")
        files[tid]["instruction.txt"] = _sha(tdir / "instruction.txt")
        if i in (3, 4):
            sub = tdir / "workspace" / "data"
            sub.mkdir(parents=True)
            (sub / "x.csv").write_text("a,b\n1,2\n", encoding="utf-8")
            files[tid]["workspace/data/x.csv"] = _sha(sub / "x.csv")
    return files


def test_build_manifest_selection_hashes_and_roundtrip(tmp_path: pathlib.Path):
    bank = tmp_path / "bank"
    bank.mkdir()
    expected = _synthetic_bank(bank)
    seen = {"t01", "t02"}
    plan = g3.build_manifest(
        bank, seen, n_tasks=2, ticket="T-BUILD", purpose="builder pin",
        arm_defs={a: f"def {a}" for a in g3.ARM_ORDER},
        budget=dict(g3.DEFAULT_BUDGET), scoring={"mode": "independent"},
        leak_guard="no hidden/scorer", approval={"required": True},
        seen_set_source="synthetic", frozen_at="2026-11-08T12:00:00Z")
    # 1) 選題＝bank 順序未見前 2 題（t03/t04），不是 t05/t06
    assert [t["task_id"] for t in plan["tasks"]] == ["t03", "t04"]
    # 2) 逐檔 sha256（含巢狀目錄）算對
    for t in plan["tasks"]:
        assert t["files"] == expected[t["task_id"]]  # 逐檔比對，非只比 key
    # 3) bank.ordering＝實際目錄全順序（選題可重算）
    assert plan["bank"]["ordering"] == [f"t{i:02d}" for i in range(1, 7)]
    assert plan["bank"]["n_total"] == 6
    # 4) 回圈：load＋verify_frozen＋check_budget 全過（建造→凍結→驗證閉環）
    base = tmp_path / "frozen"
    base.mkdir()
    (base / "manifest.json").write_text(json.dumps(plan, ensure_ascii=False),
                                        encoding="utf-8")
    for t in plan["tasks"]:
        for rel in t["files"]:
            dst = base / "tasks" / t["task_id"] / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((bank / t["task_id"] / rel).read_bytes())
    loaded = g3.G3Plan.load(base / "manifest.json")
    loaded.verify_frozen(base)
    g3.check_budget(loaded)
    assert g3.plan_cells(loaded) == [(tid, arm)
                                     for tid in ("t03", "t04")
                                     for arm in g3.ARM_ORDER]


def test_build_manifest_fail_closed(tmp_path: pathlib.Path):
    bank = tmp_path / "bank"
    (bank / "t01").mkdir(parents=True)
    (bank / "t01" / "instruction.txt").write_text("x", encoding="utf-8")
    (bank / "t02").mkdir()
    (bank / "t02" / "instruction.txt").write_text("y", encoding="utf-8")
    kw = dict(ticket="T", purpose="P",
              budget=dict(g3.DEFAULT_BUDGET), scoring={},
              leak_guard="L", approval={}, seen_set_source="s", frozen_at="f")
    # bank 目錄不存在→fail
    try:
        g3.build_manifest(tmp_path / "no_such_bank", set(), n_tasks=1,
                          arm_defs={a: "d" for a in g3.ARM_ORDER}, **kw)
        raise AssertionError("bank 目錄不存在應 raise")
    except FileNotFoundError:
        pass
    # arm_defs 缺臂→fail（不靜默少臂）
    try:
        g3.build_manifest(bank, set(), n_tasks=1, arm_defs={"native_pi": "d"},
                          **kw)
        raise AssertionError("arm_defs 缺臂應 raise")
    except KeyError:
        pass
    # 未見題不足→fail（不補位、不猜題）
    try:
        g3.build_manifest(bank, {"t01"}, n_tasks=2,
                          arm_defs={a: "d" for a in g3.ARM_ORDER}, **kw)
        raise AssertionError("未見題不足應 raise")
    except ValueError:
        pass


def test_plan_report_machine_readable():
    plan = _loaded()
    r = g3.plan_report(plan)
    assert r["schema"] == g3.PLAN_SCHEMA
    assert r["cells"] == [[t, a] for t in EXPECTED_SELECTION for a in plan.arms]
    assert len(r["cells"]) == 12
    assert "NOT FIRED" in r["state"]          # 報告如實：未發射
    assert r["budget"] == dict(plan.budget)   # 預算原樣帶出（不缺項）
    assert r["tasks"] == EXPECTED_SELECTION


# ── CLI：--fire 持有效核准→RC 3（核准但未接線；不發射、不靜默通過）────

def test_cli_fire_valid_approval_rc3_approved_not_wired(tmp_path: pathlib.Path):
    appr = tmp_path / "approval.json"
    appr.write_text(json.dumps({"schema": g3.APPROVAL_SCHEMA, "approved": True,
                               "epic": "vq-1zf", "by": "human-approver"}),
                    encoding="utf-8")
    r = _run("--fire", "--approval", str(appr))
    # 3＝核准但未接線；不是 0（＝已發射）、不是 2（＝核准被拒）
    assert r.returncode == 3, r.stdout + r.stderr
    assert "APPROVED" in r.stdout
    assert "未接線" in r.stdout                 # 如實：發射是核准後另一步


# ── CLI 負控：篡改 manifest → --plan 必須 RC 1（r1258 前 operator 可見路徑零負控）──

def test_cli_plan_tampered_manifest_rc1_not_ok(tmp_path: pathlib.Path):
    """operator 可見 fail-closed 負控：凍結輸入檔 sha 被篡改→--plan 必須 RC 1。

    r1257 釘住的是 API 層 verify_frozen 負控（test_verify_frozen_detects_tampered_sha）；
    operator 實際執行的 CLI 入口 main() 的 try/except→RC 1 路徑零負控：若未來例外被
    吞（fail-open 化），test_cli_plan_rc0_and_not_fired 仍綠、operator 見假綠。H-0 教訓：
    忘帶旗標得到的綠燈，正是放行洞口的狀態。
    """
    import shutil
    base = tmp_path / "frozen"
    shutil.copytree(BASE, base)
    m = base / "manifest.json"
    raw = json.loads(m.read_text(encoding="utf-8"))
    f0 = list(raw["tasks"][0]["files"])[0]
    raw["tasks"][0]["files"][f0] = "f" * 64    # 只改 hash、檔還在＝純篡改（非缺檔）
    m.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    r = _run("--plan", "--manifest", str(m))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "G3GATE PLAN FAIL" in r.stdout
    assert "hash 不符" in r.stdout              # 拒因如實：hash 不符（非缺檔/非選題）
    assert "G3GATE PLAN OK" not in r.stdout     # 不得假綠


# ── CLI 負控：放寬預算上限的 manifest → --plan 必須 RC 1（r1408 vq-1zf.7）────

def test_cli_plan_loosened_budget_rc1_not_ok(tmp_path: pathlib.Path):
    """operator 可見 fail-closed 負控：manifest 放寬預註冊上限→--plan 必須 RC 1。

    r1258 釘住的是篡改 sha 的 --plan 路徑；放寬預算上限是 operator 可見的同一族假綠燈
    （舊碼對 max_cells=999 印 G3GATE PLAN OK，本輪 RED 實證）。修正後拒因必須點名
    放寬的欄位（max_cells），不得出現 G3GATE PLAN OK。
    """
    import shutil
    base = tmp_path / "frozen"
    shutil.copytree(BASE, base)
    m = base / "manifest.json"
    raw = json.loads(m.read_text(encoding="utf-8"))
    raw["budget"] = {**raw["budget"], "max_cells": 999}   # 放寬 12 格預註冊上限
    m.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    r = _run("--plan", "--manifest", str(m))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "G3GATE PLAN FAIL" in r.stdout
    assert "max_cells" in r.stdout           # 拒因點名放寬的欄位
    assert "G3GATE PLAN OK" not in r.stdout  # 不得假綠


# ── CLI 負控：--fire＋有效核准＋篡改 manifest → 必須 RC 1（完整性先於核准判定）──

def test_cli_fire_tampered_manifest_rejected_before_approval(tmp_path: pathlib.Path):
    """安全排序負控：有效核准文件不得繞過凍結完整性檢查。

    r1258 釘住的是 --plan 路徑（operator 可見 fail-closed）；--fire 路徑零負控：
    若 main() 將核准判定移到 verify_frozen/check_budget 之前、或例外被吞（fail-open），
    `--fire --approval <有效> --manifest <篡改>` 就會對 operator 印 APPROVED／RC 3——
    「核准」在外觀上等同全門通過，但凍結輸入其實已被篡改（H-0 教訓：綠燈＝放行洞口的狀態）。
    正確行為：完整性檢查先於核准判定 → RC 1、印 G3GATE PLAN FAIL＋拒因如實，
    且不得出現 APPROVED、不得出現 G3GATE PLAN OK。
    """
    import shutil
    base = tmp_path / "frozen"
    shutil.copytree(BASE, base)
    m = base / "manifest.json"
    raw = json.loads(m.read_text(encoding="utf-8"))
    f0 = list(raw["tasks"][0]["files"])[0]
    raw["tasks"][0]["files"][f0] = "f" * 64    # 只改 hash、檔還在＝純篡改（非缺檔）
    m.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    appr = tmp_path / "approval.json"
    appr.write_text(json.dumps({"schema": g3.APPROVAL_SCHEMA, "approved": True,
                               "epic": "vq-1zf", "by": "human-approver"}),
                    encoding="utf-8")
    r = _run("--fire", "--approval", str(appr), "--manifest", str(m))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "G3GATE PLAN FAIL" in r.stdout
    assert "hash 不符" in r.stdout              # 拒因如實：hash 不符（非核准門拒）
    assert "APPROVED" not in r.stdout           # 有效核准不得繞過完整性
    assert "G3GATE PLAN OK" not in r.stdout     # 不得假綠
