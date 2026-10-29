from __future__ import annotations

import json
import tarfile
import io
from pathlib import Path

from ops.vlab.tools import disk_report, e002_wiring_gauge, holm_e002


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

