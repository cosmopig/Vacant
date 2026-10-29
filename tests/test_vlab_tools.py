from __future__ import annotations

import json
import tarfile
import io
from pathlib import Path

from ops.vlab.tools import disk_report, e002_wiring_gauge, holm_e002, p02_carm_audit


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



