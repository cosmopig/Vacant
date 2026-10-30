from __future__ import annotations

import json
import tarfile
import io
from pathlib import Path

from ops.vlab.tools import (
    dabstep_subset_report,
    disk_report,
    e002_wiring_gauge,
    envelope_compliance,
    growth_report,
    holm_e002,
    p02_carm_audit,
    vacant_growth_log,
)


def test_e002_wiring_gauge_selftest_and_passing_cell_marker(tmp_path: Path) -> None:
    assert e002_wiring_gauge.selftest() == 0

    exp = tmp_path / "exp1"
    # 1) 通過的 polyglot_py C 格（score.json.detail 為 None，但 events.jsonl / vacant_home.tgz 有 *_test.py）
    c_pass = exp / "polyglot_py-pg_affine_cipher-pi-C-r1"
    c_pass.mkdir(parents=True)
    (c_pass / "cell.json").write_text(
        json.dumps({"arm": "C", "agent_rc": 0, "timed_out": False, "install_rc": 0}),
        encoding="utf-8",
    )
    (c_pass / "score.json").write_text(
        json.dumps({"pass": True, "tests_total": 58, "detail": None}),
        encoding="utf-8",
    )
    with tarfile.open(c_pass / "vacant_home.tgz", "w:gz") as tf:
        payload = b'{"cmd": "pytest affine_cipher_test.py"}\n'
        ti = tarfile.TarInfo(".vacant/zero_state.json")
        ti.size = len(payload)
        tf.addfile(ti, io.BytesIO(payload))

    # 2) 未裝 Vacant 的 C 格（無 vacant_home.tgz）即使 score.json tests_total>=1 也必須判 FAIL
    c_uninst = exp / "polyglot_py-pg_beer_song-pi-C-r1"
    c_uninst.mkdir(parents=True)
    (c_uninst / "cell.json").write_text(
        json.dumps({"arm": "C", "agent_rc": 0, "timed_out": False}),
        encoding="utf-8",
    )
    (c_uninst / "score.json").write_text(
        json.dumps({"pass": True, "tests_total": 10, "detail": "beer_song_test.py"}),
        encoding="utf-8",
    )

    # 3) .infra- 重試殘留目錄必須跳過
    c_infra = exp / "polyglot_py-pg_affine_cipher-pi-C-r1.infra-1-999"
    c_infra.mkdir(parents=True)
    (c_infra / "cell.json").write_text(
        json.dumps({"arm": "C", "agent_rc": 1, "timed_out": False}),
        encoding="utf-8",
    )

    recs = e002_wiring_gauge.collect("exp1", tmp_path)
    assert len(recs) == 2
    by = {r["cell"]: r for r in recs}
    assert by["polyglot_py-pg_affine_cipher-pi-C-r1"]["c_gate"] == "PASS"
    assert by["polyglot_py-pg_affine_cipher-pi-C-r1"]["unittest_marker"] is True
    assert by["polyglot_py-pg_beer_song-pi-C-r1"]["c_gate"] == "FAIL"


def test_disk_report_skips_infra_dirs() -> None:
    assert disk_report.selftest() == 0


def test_envelope_compliance_selftest() -> None:
    assert envelope_compliance.selftest() == 0


def test_growth_report_selftest_and_verdict_semantics(tmp_path: Path) -> None:
    """growth_report（主軸 2「一天長多少」量具）：selftest 紅綠對照＋判定口徑。

    紅燈（不能假 PASS）：
    - 無任何點 → UNKNOWN（不是 PASS，也不是 0 用量）；
    - 序列 <20h → UNKNOWN（證據不足）；
    - 最新點超穩態封頂 → FAIL。
    綠燈：≥20h 序列＋在封頂內＋gc ok/target_reached → PASS。
    """
    assert growth_report.selftest() == 0

    def _point(ts: str, total: int, trace: int, gc_status: str = "ok") -> str:
        return json.dumps({"ts": ts, "home": str(tmp_path), "total_bytes": total,
                           "per_dir_bytes": {"trace": trace},
                           "gc_last": {"status": gc_status, "target_reached": True}})

    env = growth_report.ENVELOPE_BYTES
    assert env is not None  # 量具與產品同來源；import 不到時量具自己降級 UNKNOWN

    # UNKNOWN：兩份來源都缺
    r = growth_report.report(home=tmp_path / "nope1", ops_data=tmp_path / "nope2")
    assert r["verdict"] == "UNKNOWN" and r["sources"] == [], r

    # UNKNOWN：只跨 2h（證據不足）
    (tmp_path / "short").mkdir()
    (tmp_path / "short" / "growth.jsonl").write_text(
        _point("2026-10-29T00:00:00+0000", 20 * 1024 * 1024, 10 * 1024 * 1024) + "\n"
        + _point("2026-10-29T02:00:00+0000", 22 * 1024 * 1024, 11 * 1024 * 1024) + "\n", encoding="utf-8")
    r = growth_report.report(home=tmp_path / "short", ops_data=tmp_path / "nope2")
    assert r["verdict"] == "UNKNOWN", r

    # FAIL：最新點超穩態封頂（即使 gc ok 也不能 PASS）
    (tmp_path / "over").mkdir()
    (tmp_path / "over" / "growth.jsonl").write_text(
        _point("2026-10-28T00:00:00+0000", 10 * 1024 * 1024, 5 * 1024 * 1024) + "\n"
        + _point("2026-10-29T00:00:00+0000", env + 1, 5 * 1024 * 1024) + "\n", encoding="utf-8")
    r = growth_report.report(home=tmp_path / "over", ops_data=tmp_path / "nope2")
    assert r["verdict"] == "FAIL", r

    # PASS：26h 3 點、在封頂內、gc ok
    (tmp_path / "ok").mkdir()
    (tmp_path / "ok" / "growth.jsonl").write_text(
        _point("2026-10-28T00:00:00+0000", 20 * 1024 * 1024, 10 * 1024 * 1024) + "\n"
        + _point("2026-10-28T12:00:00+0000", 30 * 1024 * 1024, 15 * 1024 * 1024) + "\n"
        + _point("2026-10-29T02:00:00+0000", 40 * 1024 * 1024, 20 * 1024 * 1024) + "\n", encoding="utf-8")
    r = growth_report.report(home=tmp_path / "ok", ops_data=tmp_path / "nope2")
    assert r["verdict"] == "PASS", r
    # 24h 視窗最大增長：00:00→12:00(+10MiB)、12:00→02:00(+10MiB)；00:00→02:00(+26h) 出窗
    assert r["max_24h_growth_bytes"] == 10 * 1024 * 1024, r


def test_envelope_compliance_verdicts_infra_skip_and_exit_codes(tmp_path: Path) -> None:
    env = 256 * 1024 * 1024  # 與 retention.STABLE_ENVELOPE_BYTES 同值（字面量，避免 import 依賴）
    exp = tmp_path / "exp_env"

    def mk(name: str, cj: dict | None) -> None:
        d = exp / name
        d.mkdir(parents=True)
        if cj is not None:
            (d / "cell.json").write_text(json.dumps(cj), encoding="utf-8")

    mk("c_pass", {"arm": "C", "vacant_home_bytes": 100 * 1024})
    mk("c_fail", {"arm": "C", "vacant_home_bytes": env + 1})
    mk("c_noev", {"arm": "C"})  # 無 vacant_home_bytes → NO_EVIDENCE，不判 FAIL
    mk("a_na", {"arm": "A"})    # 設計上沒裝 Vacant 的臂 → NA
    mk(".infra-c_x", {"arm": "C", "vacant_home_bytes": env + 999})  # 重試副檔 → 跳過

    out = envelope_compliance.evaluate(tmp_path, "exp_env", env, "test")
    by = {c["cell"]: c for c in out["cells"]}
    assert out["n_cells"] == 4  # infra 副檔留痕、不計入
    assert by["c_pass"]["compliance"] == "PASS"
    assert by["c_fail"]["compliance"] == "FAIL"
    assert by["c_noev"]["compliance"] == "NO_EVIDENCE"
    assert by["a_na"]["compliance"] == "NA"
    assert by[".infra-c_x"].get("skipped")  # 不可被計入任何判定
    assert out["verdict"] == "FAIL"
    assert out["by_arm"]["C"]["verdict"] == "FAIL"
    assert out["by_arm"]["A"]["verdict"] == "NA"

    # 移除 FAIL 格 → 整體 PASS（剩餘 C 格皆在封頂內）
    (exp / "c_fail" / "cell.json").unlink()
    out2 = envelope_compliance.evaluate(tmp_path, "exp_env", env, "test")
    assert out2["verdict"] == "PASS"

    # main() 退出碼：FAIL→1、PASS→0（NA/NO_EVIDENCE 不影響退出碼）
    (exp / "c_fail" / "cell.json").write_text(
        json.dumps({"arm": "C", "vacant_home_bytes": env + 1}), encoding="utf-8")
    assert envelope_compliance.main(["exp_env", "--base", str(tmp_path)]) == 1
    (exp / "c_fail" / "cell.json").write_text(
        json.dumps({"arm": "C", "vacant_home_bytes": 1024}), encoding="utf-8")
    assert envelope_compliance.main(["exp_env", "--base", str(tmp_path)]) == 0

    # 輸入不存在 → rc=2，不假 PASS
    assert envelope_compliance.main(["no_such_exp", "--base", str(tmp_path)]) == 2


def test_holm_e002_paired_and_recompute(tmp_path: Path) -> None:
    exp = tmp_path / "e002_test"
    exp.mkdir()
    (exp / "REPORT.json").write_text(
        json.dumps(
            {
                "paired": {
                    "A_vs_C": {"mcnemar_p_two_sided": 0.02},
                    "A_vs_H": {"mcnemar_p_two_sided": 0.50},
                }
            }
        ),
        encoding="utf-8",
    )
    loaded = holm_e002.load_report_p(tmp_path, "e002_test", ("C", "H", "M"))
    assert loaded == {"C": 0.02, "H": 0.50, "M": None}
    assert holm_e002.main(["e002_test", "--base", str(tmp_path)]) == 0


def test_holm_e002_recompute_skips_infra_dirs_and_reads_cell_json(tmp_path: Path) -> None:
    exp = tmp_path / "e002_infra_test"
    exp.mkdir()
    a1 = exp / "polyglot_py-pg_affine_cipher-pi-A-r1"
    a1.mkdir(parents=True)
    (a1 / "cell.json").write_text(json.dumps({"suite": "polyglot_py", "task": "pg_affine_cipher", "agent": "pi", "rep": 1, "arm": "A"}))
    (a1 / "score.json").write_text(json.dumps({"pass": True}))

    c1 = exp / "polyglot_py-pg_affine_cipher-pi-C-r1"
    c1.mkdir(parents=True)
    (c1 / "cell.json").write_text(json.dumps({"suite": "polyglot_py", "task": "pg_affine_cipher", "agent": "pi", "rep": 1, "arm": "C"}))
    (c1 / "score.json").write_text(json.dumps({"pass": False}))

    # .infra- 重試殘留目錄（即使尾巴帶 -C-r1 或內含 score.json pass=True 也必須跳過，不可覆蓋 c1 的 False）
    c_infra = exp / "polyglot_py-pg_affine_cipher-pi-C-r1.infra-retry-C-r1"
    c_infra.mkdir(parents=True)
    (c_infra / "cell.json").write_text(json.dumps({"suite": "polyglot_py", "task": "pg_affine_cipher", "agent": "pi", "rep": 1, "arm": "C"}))
    (c_infra / "score.json").write_text(json.dumps({"pass": True}))

    p2, detail = holm_e002.recompute_pair(tmp_path, "e002_infra_test", "C")
    assert detail == {"n_tasks_common": 1, "b": 0, "c": 1, "n_A": 1, "n_X": 1}
    assert p2 == 1.0


def test_p02_carm_audit_json_newline_false_preserved_continue_and_suite_filter(tmp_path: Path) -> None:
    exp = tmp_path / "exp_p02_bugs"
    # 1) pg_beer_song：events.jsonl 內含 JSON 轉義換行 `\nbeer_song_test.py`，不得誤抓出 `nbeer_song_test.py`；
    #    chain 末筆 review 為 action="continue"（退回後超時），應計入 review_continue 而非 review_other。
    c1 = exp / "polyglot_py-pg_beer_song-pi-C-r1"
    c1.mkdir(parents=True)
    (c1 / "cell.json").write_text(
        json.dumps({"suite": "polyglot_py", "task": "pg_beer_song", "arm": "C", "agent_rc": 124, "timed_out": True, "install_rc": 0}),
        encoding="utf-8",
    )
    (c1 / "score.json").write_text(json.dumps({"pass": False, "tests_passed": 2, "tests_total": 10}), encoding="utf-8")
    (c1 / "events.jsonl").write_text(
        json.dumps({
            "type": "tool_execution_end",
            "args": {"command": "ls -la\npython3 -m unittest beer_song_test.py"},
            "result": {"content": [{"type": "text", "text": "beer_song.py\nbeer_song_test.py\n"}]},
        }) + "\n",
        encoding="utf-8",
    )
    with tarfile.open(c1 / "vacant_home.tgz", "w:gz") as tf:
        payload = json.dumps({"type": "review", "payload": {"action": "continue", "deliverables": ["beer_song.py"], "findings": [{"kind": "failed_step"}]}}).encode()
        ti = tarfile.TarInfo("home/.vacant/trace/p/chain.ndjson")
        ti.size = len(payload)
        tf.addfile(ti, io.BytesIO(payload))

    # 2) pg_uninstalled：已完成但缺 vacant_home.tgz 且無測試執行證據 → per_task 必須是 False 而非 None
    c2 = exp / "polyglot_py-pg_uninstalled-pi-C-r1"
    c2.mkdir(parents=True)
    (c2 / "cell.json").write_text(
        json.dumps({"suite": "polyglot_py", "task": "pg_uninstalled", "arm": "C", "agent_rc": 0, "timed_out": False, "install_rc": 0}),
        encoding="utf-8",
    )
    (c2 / "score.json").write_text(json.dumps({"pass": False, "tests_passed": 0, "tests_total": 5}), encoding="utf-8")
    (c2 / "events.jsonl").write_text(json.dumps({"type": "tool_execution_end", "args": {"command": "ls"}}) + "\n", encoding="utf-8")

    # 3) dabstep 非程式題：在多 suite 實驗（如 e001）預設只審 polyglot_py，不混入 P0-2 34 題表
    d1 = exp / "dabstep-1-pi-C-r1"
    d1.mkdir(parents=True)
    (d1 / "cell.json").write_text(
        json.dumps({"suite": "dabstep", "task": "1", "arm": "C", "agent_rc": 0, "timed_out": False, "install_rc": 0}),
        encoding="utf-8",
    )
    (d1 / "score.json").write_text(json.dumps({"pass": True}), encoding="utf-8")

    rec1 = p02_carm_audit.cell_record(c1)
    assert rec1["test_files_referenced"] == ["beer_song_test.py"]
    assert rec1["test_exec_evidence"] is True

    records = [p02_carm_audit.cell_record(p) for p in sorted(exp.iterdir()) if p.is_dir()]
    poly_records = p02_carm_audit.filter_suite(records, "polyglot_py")
    tasks, _ = p02_carm_audit.expected_tasks(poly_records)
    assert tasks == ["pg_beer_song", "pg_uninstalled"]
    table = p02_carm_audit.per_task_table(poly_records, tasks)
    by_task = {row["task"]: row for row in table}
    assert by_task["pg_uninstalled"]["c_installed_all"] is False
    assert by_task["pg_uninstalled"]["test_exec_evidence_all"] is False

    crit = p02_carm_audit.criteria(poly_records, table)
    assert crit["review_continue"] == 1
    assert crit["review_other"] == 0
    assert p02_carm_audit.selftest() == 0


def test_vacant_growth_log_snapshot_resolves_symlink_and_measures_bytes(tmp_path: Path) -> None:
    # auto/argon symlink 防護：VACANT_HOME 為 symlink 時 snapshot 須解析為真實路徑，
    # 且 total_bytes / objects_files / gc_last 照常度量（tmp_path 隔離，不碰 ~/.vacant）。
    real_home = tmp_path / "real_vacant"
    (real_home / "trace" / "objects").mkdir(parents=True)
    (real_home / "trace" / "objects" / "ab12").write_text("blob-bytes", encoding="utf-8")
    (real_home / "gc_report.json").write_text(
        json.dumps({"status": "ok", "trace": {"target": {"target_reached": True}}}),
        encoding="utf-8",
    )

    sym_home = tmp_path / "sym_vacant"
    sym_home.symlink_to(real_home)

    rec = vacant_growth_log.snapshot(sym_home)
    assert rec["home"] == str(real_home.resolve())
    assert rec["total_bytes"] > 0
    assert rec["objects_files"] == 1
    assert rec["gc_last"]["status"] == "ok"
    assert rec["gc_last"]["target_reached"] is True


def test_dabstep_subset_report_selftest() -> None:
    # 主軸 4（dabstep 資料分析題）：非程式題子集統計量具的離線自測（含預註冊 §3 p 值自校準）
    # 納入常規回歸，守住 McNemar 計算邏輯與 pair 排除規則（pending/infra 不進 p 值）。
    assert dabstep_subset_report.main(["--selftest"]) == 0



