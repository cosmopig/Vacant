from __future__ import annotations

import json
import tarfile
import io
from pathlib import Path

from ops.vlab.tools import (
    dabstep_subset_report,
    disk_report,
    e002_carm_failures,
    e002_wiring_gauge,
    envelope_compliance,
    growth_report,
    holm_e002,
    noncode_cell_audit,
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


def test_noncode_cell_audit_selftest() -> None:
    # 主軸 4（通用任務 noncode 資料分析題驗證）：noncode 審計量具的離線自測
    # 納入常規回歸，守住 zero/delivery 證據抽取與表格解析不變量。
    assert noncode_cell_audit.main(["--selftest"]) == 0


def test_vacant_growth_log_cli_json_mode(tmp_path: Path, capsys) -> None:
    # P20261030_0906-1（ASSIGNMENT 驗收 a＋審查 §四-1）：人手觸發快照量具的 CLI 入口
    # main(["--home", ..., "--json"]) 在 symlink 狀態目錄下須解析實體路徑、只印 JSON、
    # 回 0、不寫任何檔案（--json 分支在 a.out 寫入前就 return）。
    real_home = tmp_path / "real_vacant"
    (real_home / "trace" / "objects").mkdir(parents=True)
    (real_home / "trace" / "objects" / "ab12").write_text("blob-bytes", encoding="utf-8")

    sym_home = tmp_path / "sym_vacant"
    sym_home.symlink_to(real_home)

    rc = vacant_growth_log.main(["--home", str(sym_home), "--json"])
    assert rc == 0

    rec = json.loads(capsys.readouterr().out)
    assert rec["home"] == str(real_home.resolve())
    assert rec["total_bytes"] > 0
    assert rec["objects_files"] == 1


def test_envelope_compliance_cli(tmp_path: Path, capsys) -> None:
    # P20261030_0906-2（ASSIGNMENT 驗收 b：實驗室格子封頂合規量具）：CLI 入口
    # main(["<exp>", "--base", ...]) 在空實驗目錄下須回 0 且印出 JSON，其中
    # verdict=NA（無格子＝誠實狀態，非合規）與 envelope_bytes=256 MiB
    # （retention.STABLE_ENVELOPE_BYTES 穩態封頂常數，_load_envelope 正常載入）。
    (tmp_path / "exp_test").mkdir()

    rc = envelope_compliance.main(["exp_test", "--base", str(tmp_path)])
    assert rc == 0

    out = capsys.readouterr().out
    assert '"verdict": "NA"' in out
    assert '"envelope_bytes": 268435456' in out


def test_growth_report_cli(tmp_path: Path, capsys) -> None:
    # P20261030_0921-1（ASSIGNMENT 驗收 a：~/.vacant 增長量具守護）：CLI 入口
    # main(["--home", ..., "--ops-data", ..., "--json"]) 接收合格資料（跨 26h 的 3 點、
    # 未超穩態封頂、最新 gc status=ok）時須回 0 且 stdout 為合法 JSON：
    # verdict=PASS 且 n_points=3（自動化腳本調用量具的命令列契約）。
    home = tmp_path / "home"
    home.mkdir()
    pt = lambda ts, total: json.dumps({"ts": ts, "total_bytes": total,
                                       "per_dir_bytes": {"trace": total // 2},
                                       "gc_last": {"status": "ok", "target_reached": True}})
    (home / "growth.jsonl").write_text("\n".join([
        pt("2026-10-28T00:00:00+0000", 20 * 1024 * 1024),
        pt("2026-10-28T12:00:00+0000", 30 * 1024 * 1024),
        pt("2026-10-29T02:00:00+0000", 40 * 1024 * 1024)]) + "\n", encoding="utf-8")
    (tmp_path / "empty_ops").mkdir()
    rc = growth_report.main(["--home", str(home),
                             "--ops-data", str(tmp_path / "empty_ops"), "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["verdict"] == "PASS"
    assert data["n_points"] == 3


def test_disk_report_cli_empty_dir_exit_code(tmp_path: Path, capsys) -> None:
    (tmp_path / "runs" / "empty_exp").mkdir(parents=True)
    rc = disk_report.main(["empty_exp", "--base", str(tmp_path / "runs")])
    assert rc == 1
    assert "找不到任何 cell.json" in capsys.readouterr().err


def test_dabstep_subset_report_cli_missing_cells_exit_code(tmp_path: Path, capsys) -> None:
    (tmp_path / "runs" / "exp_none").mkdir(parents=True)
    rc = dabstep_subset_report.main(["exp_none", "--base", str(tmp_path / "runs")])
    assert rc == 1
    assert "no dabstep cells under" in capsys.readouterr().err


def test_growth_report_cli_missing_points_unknown_exit_code(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "growth.jsonl").write_text("", encoding="utf-8")
    ops_data = tmp_path / "ops_data"
    ops_data.mkdir()
    rc = growth_report.main(["--home", str(home),
                             "--ops-data", str(ops_data), "--json"])
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert data["verdict"] == "UNKNOWN"


def test_disk_report_cli_normal_run(tmp_path: Path, capsys) -> None:
    cell = tmp_path / "runs" / "exp_norm" / "cell_c1"
    cell.mkdir(parents=True)
    (cell / "cell.json").write_text(
        json.dumps({"arm": "C", "vacant_home_bytes": 50000}), encoding="utf-8")
    rc = disk_report.main(["exp_norm", "--base", str(tmp_path / "runs")])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["n_cells"] == 1
    assert data["by_arm"]["C"]["n"] == 1
    assert data["by_arm"]["C"]["home_bytes"]["min"] == 50000


def test_noncode_cell_audit_cli_missing_cells_exit_code(tmp_path: Path, capsys) -> None:
    (tmp_path / "runs" / "empty_exp").mkdir(parents=True)
    rc = noncode_cell_audit.main(["empty_exp", "--base", str(tmp_path / "runs")])
    assert rc == 1
    assert "找不到任何 cell.json" in capsys.readouterr().err


def test_p02_carm_audit_cli_missing_dir_exit_code(tmp_path: Path, capsys) -> None:
    rc = p02_carm_audit.main(["non_existent_exp", "--base", str(tmp_path)])
    assert rc == 2
    assert "找不到執行目錄" in capsys.readouterr().err


def test_growth_report_cli_over_envelope_fail_exit_code(tmp_path: Path, capsys) -> None:
    """growth_report CLI：最新點超 256 MiB 穩態封頂 → verdict=FAIL 且 exit 1（嚴防超標假 PASS）。"""
    home = tmp_path / "home"
    home.mkdir()
    # 兩筆跨 26h（≥ MIN_EVIDENCE_HOURS=20h）；最新點 total 270 MiB > 封頂 268435456
    p1 = {"ts": "2026-10-28T12:00:00+00:00", "total_bytes": 100 * 1024 * 1024,
          "gc_last": {"status": "ok", "target_reached": True}}
    p2 = {"ts": "2026-10-29T14:00:00+00:00", "total_bytes": 270 * 1024 * 1024,
          "gc_last": {"status": "ok", "target_reached": True}}
    (home / "growth.jsonl").write_text(
        json.dumps(p1) + "\n" + json.dumps(p2) + "\n", encoding="utf-8")
    rc = growth_report.main(["--home", str(home),
                             "--ops-data", str(tmp_path / "empty_ops"), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert data["verdict"] == "FAIL"
    assert data["peak_overrun"]["over_stable_envelope"] is True


def test_disk_report_cli_table_and_out_file(tmp_path: Path, capsys) -> None:
    """disk_report CLI：--table 印人讀統計表格（Arm/n/home min 等欄位）＋JSON 完整另存 --out 檔案。"""
    cell = tmp_path / "runs" / "exp_tbl" / "cell_c1"
    cell.mkdir(parents=True)
    (cell / "cell.json").write_text(
        json.dumps({"arm": "C", "vacant_home_bytes": 12345}), encoding="utf-8")
    rc = disk_report.main(["exp_tbl", "--base", str(tmp_path / "runs"),
                           "--table", "--out", str(tmp_path / "out.json")])
    assert rc == 0
    assert (tmp_path / "out.json").is_file()
    data = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert data["n_cells"] == 1
    out = capsys.readouterr().out
    assert "arm" in out
    assert "home min" in out
def test_no_leading_hyphen_files_in_repo_root() -> None:
    """Repo 根目錄不得存在以 '-' 開頭的檔案（如 -findings.md），否則 *.md / * 萬用字元展開時會觸發 POSIX 參數注入。"""
    repo_root = Path(__file__).resolve().parent.parent
    bad = [p.name for p in repo_root.iterdir() if p.name.startswith("-")]
    assert bad == [], f"Leading-hyphen files in repo root break shell globs: {bad}"


def test_e002_carm_failures_cli_and_zero_rounds_accounting(tmp_path: Path, capsys) -> None:
    """e002_carm_failures：
    1) --selftest 回傳 0；缺目錄回傳 exit 2（非 SystemExit 字串導致的 1）；
    2) 當 vacant_home.tgz 的 events.jsonl / chain.ndjson 已明確記錄 stop/review rounds_used=0
       （因 zerostop 在無 finding 時會 unlink 暫存的 rounds_*.json，如 pg_zipper），
       rejections 必須算為 0（int）且 stop_checks=1，不得誤報為 null (UNKNOWN)；
    3) 牆鐘逾時未觸發 stop 的格（events.jsonl 存在但無 stop 事件），rejections=0 且 stop_checks=0；
    4) 真正缺 vacant_home.tgz 的格，rejections 與 stop_checks 誠實為 None (UNKNOWN)。
    """
    assert e002_carm_failures.main(["--selftest"]) == 0
    capsys.readouterr()

    rc_missing = e002_carm_failures.main(["--base", str(tmp_path / "no_such_base")])
    assert rc_missing == 2
    assert "找不到 run 目錄" in capsys.readouterr().err

    run = tmp_path / "runs" / "e002_hypothesis_arms"
    # (a) 0 rejections with stop check (like pg_zipper: rounds_*.json absent, events.jsonl & chain.ndjson have rounds_used=0)
    c_zero = run / "polyglot_py-pg_zipper-pi-C-r1"
    c_zero.mkdir(parents=True)
    (c_zero / "cell.json").write_text(
        json.dumps({"task": "pg_zipper", "timed_out": False, "agent_rc": 0, "wall_s": 100.0}),
        encoding="utf-8",
    )
    (c_zero / "score.json").write_text(
        json.dumps({"pass": False, "tests_passed": 9, "tests_total": 14}),
        encoding="utf-8",
    )
    with tarfile.open(c_zero / "vacant_home.tgz", "w:gz") as tf:
        ev_bytes = (json.dumps({
            "agent": "pi", "event": "stop", "kind": "stop", "action": "allow",
            "zero": {"ran": True, "rounds_used": 0, "left_open": 0}, "zero_ran": True,
        }) + "\n").encode("utf-8")
        ti = tarfile.TarInfo(".vacant/intake/hooks/events.jsonl")
        ti.size = len(ev_bytes)
        tf.addfile(ti, io.BytesIO(ev_bytes))
        deliv_bytes = json.dumps({"findings": [], "unverified": [], "deliverables": ["zipper.py"]}).encode("utf-8")
        ti2 = tarfile.TarInfo(".vacant/trace/projects/p1/delivery.json")
        ti2.size = len(deliv_bytes)
        tf.addfile(ti2, io.BytesIO(deliv_bytes))

    # (b) timeout before any stop check (like pg_forth: events.jsonl has tool events only)
    c_to = run / "polyglot_py-pg_forth-pi-C-r1"
    c_to.mkdir(parents=True)
    (c_to / "cell.json").write_text(
        json.dumps({"task": "pg_forth", "timed_out": True, "agent_rc": 124, "wall_s": 1800.0}),
        encoding="utf-8",
    )
    (c_to / "score.json").write_text(
        json.dumps({"pass": False, "tests_passed": 52, "tests_total": 54}),
        encoding="utf-8",
    )
    with tarfile.open(c_to / "vacant_home.tgz", "w:gz") as tf:
        ev_bytes = (json.dumps({"agent": "pi", "event": "pre_tool", "kind": "pre_tool", "action": "allow"}) + "\n").encode("utf-8")
        ti = tarfile.TarInfo(".vacant/intake/hooks/events.jsonl")
        ti.size = len(ev_bytes)
        tf.addfile(ti, io.BytesIO(ev_bytes))

    # (c) missing vacant_home.tgz -> truly UNKNOWN (None)
    c_unk = run / "polyglot_py-pg_unknown-pi-C-r1"
    c_unk.mkdir(parents=True)
    (c_unk / "cell.json").write_text(
        json.dumps({"task": "pg_unknown", "timed_out": False, "agent_rc": 0, "wall_s": 10.0}),
        encoding="utf-8",
    )
    (c_unk / "score.json").write_text(
        json.dumps({"pass": False, "tests_passed": 0, "tests_total": 5}),
        encoding="utf-8",
    )

    rc = e002_carm_failures.main(["--base", str(tmp_path / "runs")])
    assert rc == 0
    rep = json.loads(capsys.readouterr().out)
    by_task = {c["task"]: c for c in rep["cells"]}
    assert by_task["pg_zipper"]["rejections"] == 0
    assert by_task["pg_zipper"]["stop_checks"] == 1
    assert by_task["pg_forth"]["rejections"] == 0
    assert by_task["pg_forth"]["stop_checks"] == 0
    assert by_task["pg_unknown"]["rejections"] is None
    assert by_task["pg_unknown"]["stop_checks"] is None


def test_envelope_compliance_cli_over_envelope_fail_exit_code(tmp_path: Path, capsys) -> None:
    """envelope_compliance CLI：C 臂格子 vacant_home_bytes 超標（300MiB > 256MiB）→ verdict FAIL、main 回 1（不假裝通過）。"""
    cell = tmp_path / "runs" / "exp_over" / "cell_c1"
    cell.mkdir(parents=True)
    (cell / "cell.json").write_text(
        json.dumps({"arm": "C", "vacant_home_bytes": 300 * 1024 * 1024}), encoding="utf-8")
    rc = envelope_compliance.main(["exp_over", "--base", str(tmp_path / "runs")])
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert data["verdict"] == "FAIL"


def test_dabstep_subset_report_cli_normal_run_and_files(tmp_path: Path, capsys) -> None:
    """dabstep_subset_report CLI：有 1 個 C 臂 scored 格子 → main 回 0、--out/--md 皆產出、stdout JSON n_cells/n_scored 皆 1。"""
    cell = tmp_path / "runs" / "exp_dab" / "cell1"
    cell.mkdir(parents=True)
    (cell / "cell.json").write_text(
        json.dumps({"suite": "dabstep", "task": "t1", "arm": "C"}), encoding="utf-8")
    (cell / "score.json").write_text(json.dumps({"pass": True}), encoding="utf-8")
    rc = dabstep_subset_report.main([
        "exp_dab", "--base", str(tmp_path / "runs"),
        "--out", str(tmp_path / "out.json"),
        "--md", str(tmp_path / "out.md"),
    ])
    assert rc == 0
    assert (tmp_path / "out.json").is_file()
    assert (tmp_path / "out.md").is_file()
    data = json.loads(capsys.readouterr().out)
    assert data["n_cells"] == 1
    assert data["n_scored"] == 1


def test_envelope_compliance_cli_normal_pass_and_out_file(tmp_path: Path, capsys) -> None:
    """envelope_compliance CLI：C 臂格子 vacant_home_bytes 合規（100MiB ≤ 256MiB）→ verdict PASS、main 回 0、--out 另存 JSON。"""
    cell = tmp_path / "runs" / "exp_pass" / "cell_c1"
    cell.mkdir(parents=True)
    (cell / "cell.json").write_text(
        json.dumps({"arm": "C", "vacant_home_bytes": 100 * 1024 * 1024}), encoding="utf-8")
    rc = envelope_compliance.main([
        "exp_pass", "--base", str(tmp_path / "runs"),
        "--out", str(tmp_path / "out.json"),
    ])
    assert rc == 0
    assert (tmp_path / "out.json").is_file()
    assert '"verdict": "PASS"' in capsys.readouterr().out
    assert '"verdict": "PASS"' in (tmp_path / "out.json").read_text(encoding="utf-8")


def test_noncode_cell_audit_cli_table_and_out_file(tmp_path: Path, capsys) -> None:
    """noncode_cell_audit CLI：有格子資料時 --table 印人讀表格至 stdout＋JSON 另存 --out 檔案、main 回 0。

    與既有缺格子 exit 1（test_noncode_cell_audit_cli_missing_cells_exit_code）形成雙向契約。
    """
    cell = tmp_path / "runs" / "exp_nc" / "cell1"
    cell.mkdir(parents=True)
    (cell / "cell.json").write_text(
        json.dumps({"suite": "dabstep", "task": "t1", "arm": "C"}), encoding="utf-8")
    (cell / "score.json").write_text(json.dumps({"pass": True}), encoding="utf-8")
    rc = noncode_cell_audit.main([
        "exp_nc", "--base", str(tmp_path / "runs"),
        "--table", "--out", str(tmp_path / "out.json"),
    ])
    assert rc == 0
    assert (tmp_path / "out.json").is_file()
    data = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert data["cells"][0]["cell"] == "cell1"
    out = capsys.readouterr().out
    assert "cell" in out
    assert "zero_ran" in out


def test_vacant_growth_log_cli_append_and_overwrite(tmp_path: Path, capsys) -> None:
    """vacant_growth_log CLI：--out 寫 JSONL 快照、stdout 印 recorded、main 回 0；同一分鐘重複跑覆蓋最後一筆（防濫記），不追加第二行。"""
    h = tmp_path / "home"
    (h / "trace" / "objects").mkdir(parents=True)
    (h / "trace" / "objects" / "blob0").write_text("x", encoding="utf-8")
    out_log = tmp_path / "data" / "growth.jsonl"

    rc = vacant_growth_log.main(["--home", str(h), "--out", str(out_log)])
    assert rc == 0
    assert out_log.is_file()
    lines = out_log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["total_bytes"] >= 1
    assert "recorded" in capsys.readouterr().out

    # 同一分鐘內重複執行：覆蓋最後一筆，行數維持 1（防濫記契約）
    rc = vacant_growth_log.main(["--home", str(h), "--out", str(out_log)])
    assert rc == 0
    assert len(out_log.read_text(encoding="utf-8").splitlines()) == 1





def test_e002_wiring_gauge_cli_missing_cells_exit_code(tmp_path: Path, capsys) -> None:
    """e002_wiring_gauge CLI：給定無格子之實驗目錄，main 輸出 {"error": "no cells"} 至 stderr 且回傳 1（輸入缺失之命令列邊界契約）。"""
    (tmp_path / "runs" / "exp_empty").mkdir(parents=True)

    rc = e002_wiring_gauge.main(["exp_empty", "--base", str(tmp_path / "runs")])
    assert rc == 1
    assert "no cells" in capsys.readouterr().err


def test_p02_carm_audit_cli_normal_run_and_out_file(tmp_path: Path, capsys) -> None:
    good = tmp_path / "runs" / "exp_p02" / "polyglot_py-pg_demo-pi-C-r1"
    good.mkdir(parents=True)
    (good / "cell.json").write_text(json.dumps(
        {"suite": "polyglot_py", "arm": "C", "agent_rc": 0, "timed_out": False, "install_rc": 0}),
        encoding="utf-8")
    (good / "score.json").write_text(json.dumps(
        {"pass": True, "tests_passed": 1, "tests_total": 1}), encoding="utf-8")
    (good / "vacant_home.tgz").write_bytes(b"")
    out = tmp_path / "out.json"
    rc = p02_carm_audit.main(["exp_p02", "--base", str(tmp_path / "runs"),
                             "--out", str(out)])
    assert rc == 0
    assert out.is_file()
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["n_cells"] == 1
    assert "\"n_cells\": 1" in capsys.readouterr().out


def test_e002_wiring_gauge_cli_normal_run_and_out_file(tmp_path: Path, capsys) -> None:
    """e002_wiring_gauge CLI：A/C 格皆合法且無線路 FAIL 時，main 回 0 且 --out 另存可解析 JSON（與缺格 exit 1 契約閉環）。"""
    a = tmp_path / "runs" / "exp_w" / "polyglot_py-task1-pi-A-r1-g1"
    a.mkdir(parents=True)
    (a / "cell.json").write_text(json.dumps(
        {"arm": "A", "agent_rc": 0, "timed_out": False, "append_system": None}), encoding="utf-8")
    (a / "score.json").write_text(json.dumps({"pass": True, "tests_total": 2}), encoding="utf-8")
    c = tmp_path / "runs" / "exp_w" / "polyglot_py-task1-pi-C-r1-g2"
    c.mkdir(parents=True)
    (c / "cell.json").write_text(json.dumps(
        {"arm": "C", "agent_rc": 0, "timed_out": False, "append_system": None, "install_rc": 0}),
        encoding="utf-8")
    (c / "score.json").write_text(json.dumps({"pass": True, "tests_total": 2}), encoding="utf-8")
    (c / "vacant_home.tgz").write_bytes(b"")
    out = tmp_path / "out.json"
    rc = e002_wiring_gauge.main(["exp_w", "--base", str(tmp_path / "runs"), "--out", str(out)])
    assert rc == 0
    assert out.is_file()
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["n_cells"] == 2
    assert "\"n_cells\": 2" in capsys.readouterr().out


def test_growth_report_cli_out_file(tmp_path: Path) -> None:
    # P20261030_1130-1（ASSIGNMENT 驗收 a：真機用量報告量具守護）：CLI --out 雙通道契約。
    # 合格序列（跨 26h 的 3 點、未超穩態封頂、最新 gc status=ok）時 main 須回 0，
    # 且 --out 把完整 JSON 報告寫入指定路徑：可解析、verdict=PASS、n_points=3
    #（與既有 --json stdout 契約 test_growth_report_cli 形成閉環）。
    home = tmp_path / "home"
    home.mkdir()
    pt = lambda ts, total: json.dumps({"ts": ts, "total_bytes": total,
                                       "per_dir_bytes": {"trace": total // 2},
                                       "gc_last": {"status": "ok", "target_reached": True}})
    (home / "growth.jsonl").write_text("\n".join([
        pt("2026-10-28T00:00:00+0000", 20 * 1024 * 1024),
        pt("2026-10-28T12:00:00+0000", 30 * 1024 * 1024),
        pt("2026-10-29T02:00:00+0000", 40 * 1024 * 1024)]) + "\n", encoding="utf-8")
    (tmp_path / "empty_ops").mkdir()
    out = tmp_path / "growth_out.json"
    rc = growth_report.main(["--home", str(home),
                             "--ops-data", str(tmp_path / "empty_ops"),
                             "--out", str(out)])
    assert rc == 0
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["verdict"] == "PASS"
    assert data["n_points"] == 3


def test_holm_e002_cli_missing_cells_exit_code(tmp_path: Path, capsys) -> None:
    # P20261030_1146-2（ASSIGNMENT 主軸 3：e002 多重檢驗校正量具常規回歸）：CLI 空資料契約。
    # 實驗目錄無 REPORT.json 且無原始格子可重算時，main 須把「無事可做」警示寫到
    # stderr 並回傳 exit code 1（fail-open 的對偶：無事可做不是 PASS，也不是崩潰）。
    empty_base = tmp_path / "runs"
    (empty_base / "exp_empty").mkdir(parents=True)
    rc = holm_e002.main(["exp_empty", "--base", str(empty_base)])
    assert rc == 1
    assert "無事可做" in capsys.readouterr().err


def test_holm_e002_cli_normal_run_and_out_file(tmp_path: Path, capsys) -> None:
    # P20261030_1146-3（ASSIGNMENT 主軸 3：e002 多重檢驗校正量具常規回歸）：CLI 正常執行契約。
    # REPORT.json 含配對 p 時，main 須把合法 JSON 輸出至 stdout（schema vacant.holm/1、m=1）、
    # 支援 --out 另存且以 exit code 0 退出——與 1146-2「無事可做 exit 1」構成雙向契約閉環。
    exp_dir = tmp_path / "runs" / "exp_norm"
    exp_dir.mkdir(parents=True)
    (exp_dir / "REPORT.json").write_text(
        json.dumps({"paired": {"A_vs_C": {"mcnemar_p_two_sided": 0.05}}}),
        encoding="utf-8")
    out = tmp_path / "out.json"
    rc = holm_e002.main(["exp_norm", "--base", str(tmp_path / "runs"), "--out", str(out)])
    assert rc == 0
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema"] == "vacant.holm/1"
    assert data["m"] == 1
    assert "vacant.holm/1" in capsys.readouterr().out


def test_holm_e002_cli_baseline_arm_error(capsys) -> None:
    # P20261030_1202-2（ASSIGNMENT 主軸 3：e002 多重檢驗校正量具邊界守護）：CLI 基線臂契約。
    # --arms 包含基線臂 A 時，argparse 解析階段須立即報錯（exit 2、stderr 點名原因），
    # 防止把基準對照組誤納入多重校正集。
    try:
        holm_e002.main(["exp_any", "--arms", "A,C"])
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert exc.code == 2
    assert "A 是基線臂，不進校正組" in capsys.readouterr().err


def test_growth_report_load_points_dedup_and_invalid_lines(tmp_path: Path) -> None:
    # P20261030_1301-2（ASSIGNMENT 🔴最優先 驗收 a：真機 ~/.vacant 增長歷史多來源讀取與去重容錯契約）：
    # load_points 面對多份 JSONL 時——缺檔跳過、損毀行與缺欄位行安全略過、
    # 同 (ts, total_bytes) 重複點只留一筆且 _src 記錄先讀到之檔案。
    f1 = tmp_path / "g1.jsonl"
    f2 = tmp_path / "g2.jsonl"
    f3 = tmp_path / "missing.jsonl"  # 不存在：必須被跳過，不拋異常
    f1.write_text(
        json.dumps({"ts": "2026-10-28T00:00:00+0000", "total_bytes": 1000}) + "\n"
        + "bad json line\n"
        + json.dumps({"ts": "2026-10-28T01:00:00+0000"}) + "\n",
        encoding="utf-8")
    f2.write_text(
        json.dumps({"ts": "2026-10-28T00:00:00+0000", "total_bytes": 1000}) + "\n"
        + json.dumps({"ts": "2026-10-28T02:00:00+0000", "total_bytes": 2000}) + "\n",
        encoding="utf-8")
    pts = growth_report.load_points(f1, f2, f3)
    assert len(pts) == 2
    assert [p["total_bytes"] for p in pts] == [1000, 2000]
    dup = next(p for p in pts if p["total_bytes"] == 1000)
    assert dup["_src"] == str(f1)


def test_holm_e002_cli_recompute_cells_fallback(tmp_path: Path, capsys) -> None:
    # P20261030_1301-3（ASSIGNMENT 主軸 3：e002 多重檢驗校正量具回退重算路徑）：
    # 無 REPORT.json 但存在原始格子（A 臂與 C 臂 score.json）時，main 須從格子
    # 重算 A_vs_C 的 McNemar 雙尾 p、以 exit 0 正常結束，且輸出標記
    # "source": "recomputed"（與主路徑 "report_json" 區分），完成雙路徑契約閉環。
    exp_dir = tmp_path / "runs" / "exp_fb"
    a_cell = exp_dir / "polyglot_py-task1-pi-A-r1"
    c_cell = exp_dir / "polyglot_py-task1-pi-C-r1"
    a_cell.mkdir(parents=True)
    c_cell.mkdir(parents=True)
    (a_cell / "score.json").write_text(json.dumps({"pass": False}), encoding="utf-8")
    (c_cell / "score.json").write_text(json.dumps({"pass": True}), encoding="utf-8")
    rc = holm_e002.main(["exp_fb", "--base", str(tmp_path / "runs"), "--arms", "C"])
    out = capsys.readouterr().out
    assert rc == 0
    assert '"schema": "vacant.holm/1"' in out
    assert '"source": "recomputed"' in out


def test_holm_e002_cli_absent_arm_excluded_from_holm_set(tmp_path: Path, capsys) -> None:
    # P20261030_1301-4（ASSIGNMENT 主軸 3：e002 缺臂不進校正組之邊界契約）：
    # 指定臂 S 在 REPORT.json 沒有 A_vs_S 的 p、也沒有原始格子可重算時，main 須將
    # S 歸入 absent_pairs 排除於 Holm 校正集外（「未測」是 UNKNOWN，不是 p=1.0，
    # 也不崩潰），C 臂照常校正，m 只數有 p 的組，exit 0。
    exp_dir = tmp_path / "runs" / "exp_abs"
    exp_dir.mkdir(parents=True)
    (exp_dir / "REPORT.json").write_text(
        json.dumps({"paired": {"A_vs_C": {"mcnemar_p_two_sided": 0.04}}}),
        encoding="utf-8")
    rc = holm_e002.main(["exp_abs", "--base", str(tmp_path / "runs"), "--arms", "C,S"])
    doc = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert doc["m"] == 1
    assert "C" in doc["pairs"]
    assert "S" in doc["absent_pairs"]
