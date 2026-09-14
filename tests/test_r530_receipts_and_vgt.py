"""R530：收據型別、V/GT 新形狀（含負控）、整條迴圈的三種結局。"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain import harness_vgt_audit as vgt  # noqa: E402
from ops.gain.r530 import openwork_arms as oa  # noqa: E402
from ops.gain.r530 import receipts, tasks as taskmod  # noqa: E402
from ops.gain.replay.verify_run_receipts import (ATTEMPT_TYPES,  # noqa: E402
                                                 VERDICT_TYPES, verify_arm)
from vacant.crypto import pub_to_hex  # noqa: E402
from vacant.identity import Identity  # noqa: E402
from vacant.logbook import MAX_PAYLOAD_BYTES, Logbook  # noqa: E402


# ── 收據型別 ──────────────────────────────────────────────────────────────
def test_verifier_knows_the_two_new_types():
    assert receipts.WS_VERDICT in VERDICT_TYPES
    assert receipts.WS_ATTEMPT in ATTEMPT_TYPES


def test_receipt_payload_is_digest_only_and_fits_the_64k_cap():
    """簽 digest 不簽全文——`logbook.MAX_PAYLOAD_BYTES` 是硬限制（§五-4）。"""
    from vacant.canonical import canonical_bytes
    ident = Identity.generate()
    book = Logbook()
    entry = receipts.append_attempt(
        book, ident, task_id="ow_01_csvjson", arm="A-GATE", attempt=1,
        gate_round=1, ws_sha256="a" * 64, verdict_sha256="b" * 64,
        conversation_sha256="c" * 64, visible_passed=1, visible_total=3)
    assert len(canonical_bytes(entry.payload)) < MAX_PAYLOAD_BYTES // 4


def test_receipt_requires_the_load_bearing_fields():
    ident = Identity.generate()
    book = Logbook()
    with pytest.raises(ValueError):
        receipts._append(book, ident, receipts.WS_VERDICT,
                         {"task_id": "t"}, receipts.VERDICT_FIELDS)


def test_conversation_digest_ignores_transport_fields():
    a = [{"role": "user", "content": "x", "tool_call_id": "1"}]
    b = [{"role": "user", "content": "x"}]
    assert receipts.conversation_digest(a) == receipts.conversation_digest(b)
    c = [{"role": "user", "content": "y"}]
    assert receipts.conversation_digest(a) != receipts.conversation_digest(c)


def test_chain_with_r530_types_reconciles_against_rows(tmp_path):
    ident = Identity.generate()
    book = Logbook()
    for tid in ("ow_01_csvjson", "ow_02_ratelimit"):
        receipts.append_attempt(book, ident, task_id=tid, arm="A-GATE",
                                attempt=1, gate_round=1, ws_sha256="a" * 64,
                                verdict_sha256="b" * 64,
                                conversation_sha256="c" * 64)
        receipts.append_verdict(book, ident, task_id=tid, arm="A-GATE",
                                accepted=True, ws_start_sha256="d" * 64,
                                ws_end_sha256="e" * 64,
                                verdict_sha256="b" * 64,
                                conversation_sha256="c" * 64,
                                stop_reason="visible_pass")
    book.save(tmp_path / "receipts_A-GATE.ndjson")
    (tmp_path / "receipts_A-GATE.pub.json").write_text(json.dumps(
        {"vacant_id": ident.vacant_id, "pub_hex": pub_to_hex(ident.pub)}),
        encoding="utf-8")
    rows = [{"arm": "A-GATE", "task_id": t}
            for t in ("ow_01_csvjson", "ow_02_ratelimit")]
    rec = verify_arm(tmp_path, "A-GATE", rows)
    assert rec["verdict"] == "OK", rec["failures"]
    assert rec["verdict_n"] == 2 and rec["attempt_n"] == 2


def test_verify_run_receipts_selftest_still_passes():
    r = subprocess.run(
        [sys.executable, "ops/gain/replay/verify_run_receipts.py", "--selftest"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout


# ── V/GT：新形狀 ──────────────────────────────────────────────────────────
def test_tool_header_matches_the_arms_module():
    """兩份副本漂掉就會讓 `role=tool` 的文字被當成 harness 寫的 user 文字。"""
    assert vgt.R530_TOOL_HEADER == oa.TOOL_RESULT_HEADER


def test_r530_scope_is_registered():
    assert "r530" in vgt.AUDIT_SCOPES


def test_python_literals_collects_values_not_identifiers():
    lits = vgt.python_literals("def check_x():\n    assert f('a,b') == ['q', 1]\n")
    assert "'a,b'" in lits and "['q', 1]" in lits
    assert "check_x" not in lits and "'check_x'" not in lits


def test_hidden_needles_exclude_visible_and_task_prose():
    task = taskmod.load_task("ow_01_csvjson")
    needles, skipped = vgt.r530_hidden_needles(task)
    assert needles, "隱藏側應該有可用的 needle"
    vis = (task["visible_dir"] / "test_visible.py").read_text(encoding="utf-8")
    vis_lits = vgt.python_literals(vis)
    assert not (set(needles) & vis_lits), \
        "可見驗收的字面值不是 GT（D7 在 R530 的對應物）"
    assert all(not vgt.is_trivial_needle(n) for n in needles)
    assert isinstance(skipped, list)


def test_hidden_needles_fail_closed_on_an_unknown_shape(tmp_path):
    """認不出形狀不是通過，是停（既有兩種 dialect 的同一條紀律）。"""
    empty = tmp_path / "hidden_empty"
    empty.mkdir()
    task = dict(taskmod.load_task("ow_01_csvjson"))
    task["hidden_dir"] = empty
    with pytest.raises(SystemExit):
        vgt.r530_hidden_needles(task)


def test_classify_texts_r530_recognises_the_tool_role():
    rec = {"system": "sys", "messages": [
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": "```bash\nls\n```"},
        {"role": "user", "content": oa.TOOL_RESULT_HEADER + "\n\n$ ls\nexit=0"},
    ]}
    roles = [r for r, _i, _t in vgt.classify_texts_r530(rec)]
    assert roles == ["system", "user", "assistant", "tool"]


def _fake_run(tmp_path, texts_by_role: list[tuple[str, str]], task_id: str):
    run = tmp_path / "run"
    (run / "ws").mkdir(parents=True)
    msgs = []
    system = "sys"
    for role, text in texts_by_role:
        if role == "system":
            system = text
        else:
            msgs.append({"role": "user" if role == "tool" else role,
                         "content": text})
    rec = {"meta": {"arm": "A-GATE", "task_id": task_id},
           "system": system, "messages": msgs}
    (run / "calls.jsonl").write_text(json.dumps(rec, ensure_ascii=False) + "\n",
                                     encoding="utf-8")
    return run


def test_vgt_negative_control_a_real_hidden_literal_in_a_user_message(tmp_path):
    """**負控**：真的把一條隱藏驗收的字面值塞進 harness 寫的 user 訊息 ⇒ VIOLATION。

    放寬偵測面（tool role 記錄不判定、題目原文豁免）而沒有這一條，
    等於把稽核關掉（round460e 的教訓逐字適用）。
    """
    task = taskmod.load_task("ow_01_csvjson")
    needles, _ = vgt.r530_hidden_needles(task)
    needle = needles[0]
    leak = f"hint: the expected value is {needle}"
    run = _fake_run(tmp_path, [("system", "sys"), ("user", leak)],
                    task["task_id"])
    out = vgt.audit_run_r530(run, {task["task_id"]: task})
    assert out["verdict"] == "VIOLATION"
    assert any(v["needle"] == needle and v["role"] == "user"
               for v in out["violations"])


def test_vgt_negative_control_system_message_gets_no_excuse(tmp_path):
    task = taskmod.load_task("ow_02_ratelimit")
    needles, _ = vgt.r530_hidden_needles(task)
    run = _fake_run(tmp_path, [("system", f"persona {needles[0]}"),
                               ("user", "task")], task["task_id"])
    out = vgt.audit_run_r530(run, {task["task_id"]: task})
    assert out["verdict"] == "VIOLATION"
    assert any(v["role"] == "system" for v in out["violations"])


def test_vgt_tool_output_is_recorded_not_judged(tmp_path):
    """工具輸出的命中進 `excused`（留證不靜音），不算違規。"""
    task = taskmod.load_task("ow_01_csvjson")
    needles, _ = vgt.r530_hidden_needles(task)
    tool_text = (oa.TOOL_RESULT_HEADER + "\n\n$ python3 -c x\nexit=0\n"
                 "--- stdout ---\n" + needles[0] + "\n--- stderr ---\n")
    run = _fake_run(tmp_path, [("system", "sys"), ("user", "task"),
                               ("tool", tool_text)], task["task_id"])
    out = vgt.audit_run_r530(run, {task["task_id"]: task})
    assert out["verdict"] == "CLEAN"
    assert out["excused_by_rule"][vgt.R530_TOOL_ECHO] >= 1
    assert out["excused"], "被豁免的命中要逐筆留著，不是只留一個總數"


def test_vgt_assistant_text_is_not_scanned(tmp_path):
    task = taskmod.load_task("ow_01_csvjson")
    needles, _ = vgt.r530_hidden_needles(task)
    run = _fake_run(tmp_path, [("system", "sys"), ("user", "task"),
                               ("assistant", f"I will try {needles[0]}")],
                    task["task_id"])
    out = vgt.audit_run_r530(run, {task["task_id"]: task})
    assert out["verdict"] == "CLEAN" and not out["violations"]


def test_vgt_zero_records_is_unverifiable_not_clean(tmp_path):
    task = taskmod.load_task("ow_01_csvjson")
    run = tmp_path / "run"
    run.mkdir()
    (run / "calls.jsonl").write_text("", encoding="utf-8")
    out = vgt.audit_run_r530(run, {task["task_id"]: task})
    assert out["verdict"] == "UNVERIFIABLE", \
        "一筆都沒稽核到不是 CLEAN——量具沒接上不是通過"


def test_vgt_hidden_file_inside_a_workspace_archive_is_a_violation(tmp_path):
    """結構性紅線：隱藏驗收出現在工作區封存裡 ⇒ 整個 run 作廢。"""
    import tarfile
    task = taskmod.load_task("ow_01_csvjson")
    run = _fake_run(tmp_path, [("system", "sys"), ("user", "task")],
                    task["task_id"])
    stage = tmp_path / "stage" / f"{task['task_id']}__A-GATE__a1"
    (stage / "hidden").mkdir(parents=True)
    (stage / "hidden" / "test_hidden.py").write_text("x", encoding="utf-8")
    arc = run / "ws" / f"{task['task_id']}__A-GATE__a1.tar.gz"
    with tarfile.open(arc, "w:gz") as tf:
        tf.add(stage, arcname=stage.name)
    out = vgt.audit_run_r530(run, {task["task_id"]: task})
    assert out["verdict"] == "VIOLATION"
    assert any(v["rule"] == "hidden_file_in_workspace" for v in out["violations"])
    assert out["structural_violations_n"] >= 1


def test_vgt_counts_deny_hidden_read_attempts(tmp_path):
    task = taskmod.load_task("ow_01_csvjson")
    run = _fake_run(tmp_path, [("system", "sys"), ("user", "task")],
                    task["task_id"])
    with (run / "calls.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": "tool", "blocked": True,
                            "deny_tag": "r530_hidden_read",
                            "command": "cat hidden/x.py"}) + "\n")
    out = vgt.audit_run_r530(run, {task["task_id"]: task})
    assert out["deny_hidden_read_n"] == 1
    assert out["deny_counts"]["r530_hidden_read"] == 1


# ── 冒煙檢核表（§三-6 C1–C8）──────────────────────────────────────────────
def _stub_smoke(tmp_path):
    """用替身後端跑一份真的冒煙，回 run 目錄。"""
    import os
    from ops.gain.r530.run_r530 import main as run_main
    out = f"runs/_smoke/checklist_probe_{tmp_path.name}"
    old = os.environ.get("VACANT_R530_WORK")
    os.environ["VACANT_R530_WORK"] = str(tmp_path / "work")
    try:
        rc = run_main(["--out", out, "--task-set",
                       "ow_01_csvjson,ow_02_ratelimit", "--seed", "smoke-cl",
                       "--backend", "none", "--brain", "stub", "--smoke"])
    finally:
        if old is None:
            os.environ.pop("VACANT_R530_WORK", None)
        else:
            os.environ["VACANT_R530_WORK"] = old
    assert rc == 0
    return ROOT / out


def test_smoke_checklist_passes_on_a_clean_stub_run(tmp_path):
    from ops.gain.r530 import smoke_checklist as sc
    run = _stub_smoke(tmp_path)
    try:
        out = sc.check(run)
        assert out["verdict"] == "PASS", json.dumps(out["checks"],
                                                    ensure_ascii=False)[:1500]
        assert set(out["checks"]) == set(sc.CHECKS)
    finally:
        import shutil
        shutil.rmtree(run, ignore_errors=True)


def test_smoke_checklist_has_teeth(tmp_path):
    """**負控**：檢核表要抓得到壞掉的那一格，否則它只是在蓋章。

    三種壞法各對應一格：呼叫數對不上（C1）、隱藏條數對不上（C4）、
    收據被竄改（C6）。
    """
    import shutil
    from ops.gain.r530 import smoke_checklist as sc
    run = _stub_smoke(tmp_path)
    try:
        rows = [json.loads(l) for l in (run / "rows.jsonl").open(encoding="utf-8")
                if l.strip()]
        # C1：把某一格的 calls 改大 ⇒ 與 calls.jsonl 對不上
        rows[0]["calls"] += 7
        # C4：把隱藏條數改掉 ⇒ 與題庫對不上
        rows[1]["hidden_total"] += 1
        (run / "rows.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
            encoding="utf-8")
        # C6：竄改一條收據的 payload ⇒ 簽章驗不過
        chain = next(run.glob("receipts_*.ndjson"))
        lines = chain.read_text(encoding="utf-8").splitlines()
        e = json.loads(lines[0])
        e["payload"]["ws_sha256"] = "0" * 64
        lines[0] = json.dumps(e, ensure_ascii=False, separators=(",", ":"),
                              sort_keys=True)
        chain.write_text("\n".join(lines) + "\n", encoding="utf-8")

        out = sc.check(run)
        assert out["verdict"] == "FAIL"
        assert not out["checks"]["C1"]["ok"], "呼叫數對不上要被抓到"
        assert not out["checks"]["C4"]["ok"], "隱藏條數對不上要被抓到"
        assert not out["checks"]["C6"]["ok"], "收據被竄改要被抓到"
    finally:
        shutil.rmtree(run, ignore_errors=True)


# ── E-9／E-10（Fable 2026-09-14）──────────────────────────────────────────
def test_e9_blocks_launch_when_the_repo_is_visible_from_the_sandbox():
    from ops.gain.r530 import gates
    bad = gates.e9_sandbox_gate({"sandbox": "unshare", "network_isolated": True,
                                 "write_confined": True,
                                 "repo_hidden_from_sandbox": False})
    assert bad["ok"] is False
    assert "abort_repo_visible_from_sandbox" in bad["reason"]
    good = gates.e9_sandbox_gate({"sandbox": "unshare", "network_isolated": True,
                                  "write_confined": True,
                                  "repo_hidden_from_sandbox": True})
    assert good["ok"] is True and "reason" not in good


def test_e9_warns_but_does_not_block_when_writes_are_unconfined():
    from ops.gain.r530 import gates
    rec = gates.e9_sandbox_gate({"repo_hidden_from_sandbox": True,
                                 "write_confined": False})
    assert rec["ok"] is True
    assert "outside_new_files" in rec["warning"]


def test_e9_treats_unknown_as_red_not_as_green():
    """**量不到不是通過**：沒有量過那一格 ⇒ 紅。"""
    from ops.gain.r530 import gates
    assert gates.e9_sandbox_gate({})["ok"] is False
    assert gates.e9_sandbox_gate(
        {"repo_hidden_from_sandbox": None})["ok"] is False


def test_e10_flags_the_arm_whose_cells_did_nothing():
    from ops.gain.r530 import gates
    rows = ([{"arm": "A-SOLO", "task_id": f"t{i}", "seed": "s",
              "noop_cell": i < 3, "stop_reason": "nudge_exhausted"}
             for i in range(10)]
            + [{"arm": "A-GATE", "task_id": f"t{i}", "seed": "s",
                "noop_cell": False, "stop_reason": "visible_pass"}
               for i in range(10)])
    out = gates.e10_noop_gate(rows)
    assert out["ok"] is False
    assert out["arms_over_threshold"] == ["A-SOLO"]
    assert out["per_arm"]["A-SOLO"]["rate"] == 0.3
    assert len(out["offending_cells"]) == 3, "壞掉的格子要逐格記名"
    assert all(c["task_id"] for c in out["offending_cells"])


def test_e10_passes_at_or_below_the_threshold():
    from ops.gain.r530 import gates
    rows = [{"arm": "A-GATE", "task_id": f"t{i}", "seed": "s",
             "noop_cell": i < 2} for i in range(10)]
    out = gates.e10_noop_gate(rows)
    assert out["ok"] is True and out["per_arm"]["A-GATE"]["rate"] == 0.2


def test_e10_threshold_is_declared_as_a_convention_not_a_measurement():
    from ops.gain.r530 import gates
    out = gates.e10_noop_gate([{"arm": "A", "noop_cell": False}])
    assert "約定" in out["honest_bound"] and "不是從任何實測" in out["honest_bound"]


def test_c9_fails_when_the_gated_arms_never_actually_fired(tmp_path):
    """C9 負控：`A-CONF` 沒抽到第二份、`A-GATE` 沒進回饋輪 ⇒ **不准發射**。

    這一條擋的是第五輪推翻的那個死法：預算不夠時兩條有閘門的臂在資料上與
    `A-SOLO` 無法區分，而那**不會有任何錯誤訊息**，只會安靜地產出一個
    `INCONCLUSIVE`。沒有這條負控，C9 只是在蓋章。
    """
    import shutil
    from ops.gain.r530 import smoke_checklist as sc
    run = _stub_smoke(tmp_path)
    try:
        assert sc.check(run)["checks"]["C9"]["ok"] is True, "先確認乾淨路徑是綠的"
        rows = [json.loads(l) for l in (run / "rows.jsonl").open(encoding="utf-8")
                if l.strip()]
        for r in rows:
            if r["arm"] == "A-CONF":
                r["attempts_n"] = 1            # 只抽到第一份
            if r["arm"] == "A-GATE":
                for a in r.get("attempts") or []:
                    a["gate_rounds"] = []      # 一輪回饋都沒跑到
        (run / "rows.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
            encoding="utf-8")
        out = sc.check(run)
        assert out["checks"]["C9"]["ok"] is False
        assert out["checks"]["C9"]["detail"]["conf_cells_with_a_second_draw"] == []
        assert out["checks"]["C9"]["detail"][
            "gate_cells_that_reached_a_feedback_round"] == []
        assert out["verdict"] == "FAIL"
        assert "證不了" in out["checks"]["C9"]["detail"]["honest_bound"]
    finally:
        shutil.rmtree(run, ignore_errors=True)


def test_checklist_reports_seconds_per_call(tmp_path):
    """§七-2b 的時程公式要填 T，所以 T 要是檢核表的產物不是事後手算。"""
    import shutil
    from ops.gain.r530 import smoke_checklist as sc
    run = _stub_smoke(tmp_path)
    try:
        out = sc.check(run)
        tpc = out["seconds_per_call"]
        assert set(tpc["per_arm"]) == {"A-SOLO", "A-CONF", "A-GATE"}
        assert all(v is None or v >= 0 for v in tpc["per_arm"].values())
        assert tpc["overall"] is not None
        assert "併發之下 T 會變大" in tpc["note"], "拿它推時程要帶著那個未知數"
    finally:
        shutil.rmtree(run, ignore_errors=True)


# ── 檢核表吃多個 run 目錄（冒煙為了用兩顆後端會被切成兩塊）────────────────
def _stub_smoke_one(tmp_path, tag, task):
    import os
    from ops.gain.r530.run_r530 import main as run_main
    out = f"runs/_smoke/mr_{tmp_path.name}_{tag}"
    old = os.environ.get("VACANT_R530_WORK")
    os.environ["VACANT_R530_WORK"] = str(tmp_path / f"work_{tag}")
    try:
        assert run_main(["--out", out, "--task-set", task, "--seed",
                         f"smoke-mr-{tag}", "--backend", "none", "--brain",
                         "stub", "--smoke"]) == 0
    finally:
        if old is None:
            os.environ.pop("VACANT_R530_WORK", None)
        else:
            os.environ["VACANT_R530_WORK"] = old
    return ROOT / out


def test_checklist_merges_two_blocks(tmp_path):
    """C9 是**整份冒煙**的性質：`A-CONF` 的第二份可能只在難的那一題出現，
    `A-GATE` 的回饋輪可能只在另一題出現。逐塊判會把「兩件事都發生過、
    只是不在同一塊」判成紅。"""
    import shutil
    from ops.gain.r530 import smoke_checklist as sc
    a = _stub_smoke_one(tmp_path, "a", "ow_01_csvjson")
    b = _stub_smoke_one(tmp_path, "b", "ow_02_ratelimit")
    try:
        out = sc.check([a, b])
        assert out["runs"] == [str(a), str(b)]
        assert out["rows_n"] == 6, "兩塊各三格 ⇒ 合起來是六格"
        # 逐塊的 C6／C8／E9 都要綠，而且是**逐塊**記的
        assert set(out["checks"]["C6"]["detail"]) == {a.name, b.name}
        assert set(out["checks"]["C8"]["detail"]) == {a.name, b.name}
        assert set(out["checks"]["E9"]["detail"]) == {a.name, b.name}
        # T 跨塊加總
        assert set(out["seconds_per_call"]["per_arm"]) == {
            "A-SOLO", "A-CONF", "A-GATE"}
    finally:
        for d in (a, b):
            shutil.rmtree(d, ignore_errors=True)


def test_checklist_c7_catches_two_blocks_run_under_different_sandboxes(tmp_path):
    """多塊之下 C7 變**更嚴**：兩塊的沙箱身分不同 ⇒ 那 6 格不是同一個實驗條件。"""
    import shutil
    from ops.gain.r530 import smoke_checklist as sc
    a = _stub_smoke_one(tmp_path, "a", "ow_01_csvjson")
    b = _stub_smoke_one(tmp_path, "b", "ow_02_ratelimit")
    try:
        assert sc.check([a, b])["checks"]["C7"]["ok"] is True
        sm = json.loads((b / "summary.json").read_text(encoding="utf-8"))
        sm["backend_meta"]["sandbox"] = "bwrap"      # 假裝第二塊換了沙箱
        (b / "summary.json").write_text(json.dumps(sm, ensure_ascii=False),
                                        encoding="utf-8")
        out = sc.check([a, b])
        assert out["checks"]["C7"]["ok"] is False
        assert len(out["checks"]["C7"]["detail"]["per_run_signature"]) == 2
    finally:
        for d in (a, b):
            shutil.rmtree(d, ignore_errors=True)


# ── E-11：推論模式必須一致（Fable 2026-09-14 第六輪）──────────────────────
def _call(reasoning=0, completion=100, arm="A-GATE", ok=True, field=True):
    det = {"reasoning_tokens": reasoning} if field else {}
    return {"ok": ok, "meta": {"arm": arm, "task_id": "t"},
            "usage": {"completion_tokens": completion,
                      "completion_tokens_details": det}}


def test_e11_preflight_passes_only_when_every_endpoint_reports_zero():
    from ops.gain.r530 import gates
    good = {"reasoning_tokens_all_zero": True, "reasoning_tokens": [0, 0],
            "prefill_ms_per_1k_prompt": 121.0}
    bad = {"reasoning_tokens_all_zero": False, "reasoning_tokens": [0, 44],
           "prefill_ms_per_1k_prompt": 807.0}
    assert gates.e11_preflight_gate({"a": good})["ok"] is True
    out = gates.e11_preflight_gate({"a": good, "b": bad})
    assert out["ok"] is False
    assert "abort_reasoning_tokens_nonzero" in out["reason"]


def test_e11_preflight_treats_a_missing_probe_as_red():
    """**沒有量過的那一台不能假設它一樣**（R529 §十一 的整個教訓）。"""
    from ops.gain.r530 import gates
    assert gates.e11_preflight_gate({})["ok"] is False
    unknown = {"reasoning_tokens_all_zero": None, "error": "timeout"}
    assert gates.e11_preflight_gate({"a": unknown})["ok"] is False


def test_e11_preflight_surfaces_the_prefill_spread_without_blocking():
    """prefill 差距**不擋發射**，但要被看見——它會讓 budget_wall 咬到不同地方。"""
    from ops.gain.r530 import gates
    out = gates.e11_preflight_gate({
        "1003": {"reasoning_tokens_all_zero": True,
                 "prefill_ms_per_1k_prompt": 807.0},
        "1004": {"reasoning_tokens_all_zero": True,
                 "prefill_ms_per_1k_prompt": 121.0}})
    assert out["ok"] is True, "吞吐差距不是發射擋門"
    assert out["prefill_spread"]["max_over_min"] == round(807.0 / 121.0, 2)
    assert "二次地慢" in out["prefill_spread"]["warning"]


def test_e11_closeout_marks_the_block_broken_when_reasoning_was_burned():
    from ops.gain.r530 import gates
    clean = gates.e11_closeout_gate([_call() for _ in range(5)], block="b1")
    assert clean["ok"] is True and clean["verdict"] == "ok"
    assert clean["reasoning_share"] == 0.0

    dirty = gates.e11_closeout_gate(
        [_call(), _call(reasoning=30), _call()], block="b1")
    assert dirty["ok"] is False
    assert dirty["verdict"] == gates.E11_BROKEN
    assert dirty["reasoning_share"] > 0
    assert "不進分析" in dirty["reason"]


def test_e11_closeout_treats_a_missing_field_as_red_not_as_zero():
    """欄位不存在與 0 是兩件事。量不到不是通過。"""
    from ops.gain.r530 import gates
    out = gates.e11_closeout_gate([_call(), _call(field=False)], block="b1")
    assert out["ok"] is False
    assert out["calls_without_the_field"] == 1
    assert "量不到不是通過" in out["reason"]


def test_e11_closeout_zero_calls_is_not_a_pass():
    from ops.gain.r530 import gates
    out = gates.e11_closeout_gate([], block="b1")
    assert out["ok"] is False and out["calls_audited"] == 0


def test_e11_closeout_ignores_failed_attempts_and_non_arm_calls():
    """重試失敗的那幾筆與探針本身不算——它們不是實驗呼叫。"""
    from ops.gain.r530 import gates
    calls = [_call(), _call(ok=False, reasoning=999),
             {"ok": True, "meta": {}, "usage": {"completion_tokens": 10,
              "completion_tokens_details": {"reasoning_tokens": 999}}}]
    out = gates.e11_closeout_gate(calls, block="b1")
    assert out["calls_audited"] == 1 and out["ok"] is True
