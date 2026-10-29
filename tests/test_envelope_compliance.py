"""envelope_compliance 量具的紅綠測試（round 169，Axis 2「紀錄檔的真實管理」）。

驗收口徑（ASSIGNMENT 10/28 最優先·條件 1 的格子層證據；round 168 留下的 next）：
  - C 格 `vacant_home_bytes` vs 256 MiB 穩態封頂 → PASS / FAIL；
  - 格完成但 cell.json 無 vacant_home_bytes → NO_EVIDENCE（不變量 5：看不到≠沒有，也不判 FAIL）；
  - 格未完成（無 cell.json）→ NA；A／H／M／S 臂＝沒裝 Vacant，超出封頂口徑 → NA；
  - 有 FAIL ⇒ 退出碼 1；無 FAIL（NA／NO_EVIDENCE 是誠實狀態）⇒ 退出碼 0；
  - selftest ⇒ 退出碼 0。

本測試先於量具存在（紅燈先行）；量具是獨立量具，只讀 runs 下的 cell.json，
不碰 cell.py／labd.py／report.py（共用量具零改動）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "ops" / "vlab" / "tools" / "envelope_compliance.py"
PY = sys.executable


def _mk_exp(base: Path, spec: dict) -> None:
    root = base / "exp_x"
    for name, cj in spec.items():
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        if cj is not None:
            (d / "cell.json").write_text(json.dumps(cj), encoding="utf-8")


def _run(base: Path, exp: str = "exp_x", extra: tuple = ()):
    return subprocess.run(
        [PY, str(TOOL), exp, "--base", str(base), *extra],
        capture_output=True, text=True, timeout=120,
    )


def test_tool_exists() -> None:
    assert TOOL.is_file(), f"量具不存在：{TOOL}（紅燈）"


def test_selftest_green() -> None:
    p = subprocess.run([PY, str(TOOL), "--selftest"], capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr


def test_states_and_exit_code_fail(tmp_path: Path) -> None:
    _mk_exp(tmp_path, {
        "c_ok":       {"arm": "C", "vacant_home_bytes": 1_000_000},
        "c_big":      {"arm": "C", "vacant_home_bytes": 300 * 1024 * 1024},
        "c_noev":     {"arm": "C"},
        "a_base":     {"arm": "A"},
        "h_arm":      {"arm": "H"},
        "incomplete": None,
    })
    p = _run(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr  # c_big ⇒ FAIL ⇒ rc=1
    out = json.loads(p.stdout)
    by = {c["cell"]: c for c in out["cells"]}
    assert by["c_ok"]["compliance"] == "PASS"
    assert by["c_big"]["compliance"] == "FAIL"
    assert by["c_noev"]["compliance"] == "NO_EVIDENCE"
    assert by["a_base"]["compliance"] == "NA"
    assert by["h_arm"]["compliance"] == "NA"
    assert by["incomplete"]["compliance"] == "NA"
    assert out["verdict"] == "FAIL"
    assert out["envelope_bytes"] == 256 * 1024 * 1024


def test_no_fail_means_zero(tmp_path: Path) -> None:
    _mk_exp(tmp_path, {
        "c_ok":       {"arm": "C", "vacant_home_bytes": 1024},
        "c_noev":     {"arm": "C"},
        "a_base":     {"arm": "A"},
        "incomplete": None,
    })
    p = _run(tmp_path)
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)
    assert out["verdict"] == "PASS"
    assert out["by_arm"]["C"]["verdict"] == "PASS"
    assert out["by_arm"]["A"]["verdict"] == "NA"


def test_envelope_override(tmp_path: Path) -> None:
    _mk_exp(tmp_path, {"c_ok": {"arm": "C", "vacant_home_bytes": 1_000_000}})
    p = _run(tmp_path, extra=("--envelope", "1000"))
    assert p.returncode == 1, p.stdout + p.stderr
    out = json.loads(p.stdout)
    assert out["envelope_bytes"] == 1000
    assert out["cells"][0]["compliance"] == "FAIL"


def test_home_missing_is_na_not_error(tmp_path: Path) -> None:
    _mk_exp(tmp_path, {"c_weird": {"arm": "C", "vacant_home_bytes": "not-an-int"}})
    p = _run(tmp_path)
    # 類型異常＝沒有可用數字 → NO_EVIDENCE（誠實），不崩、不判 FAIL
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)
    assert out["cells"][0]["compliance"] == "NO_EVIDENCE"


def test_missing_exp_dir_is_input_error() -> None:
    p = _run(Path("/tmp/definitely_not_here_envelope_test"))
    assert p.returncode == 2, p.stdout + p.stderr


def test_real_e001_no_fail() -> None:
    """e001 C 格真實數據（小工作區）：vacant_home_bytes 全在封頂內 ⇒ 不該有 FAIL。
    若這裡紅了，是真實發現（某格超封頂或量具錯），不是測試寫錯。"""
    base = Path("/srv/vlab/runs")
    if not (base / "e001_pi_AC_baseline").is_dir():
        pytest.skip("本機沒有 /srv/vlab/runs/e001_pi_AC_baseline")
    p = _run(base, exp="e001_pi_AC_baseline")
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)
    cs = [c for c in out["cells"] if c.get("arm") == "C" and c.get("vacant_home_bytes")]
    assert cs, "e001 應至少有 C 格帶 vacant_home_bytes 證據"
