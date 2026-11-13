"""intake CLI「找不到 contract」退出碼測試（票 R20261113_0000-1）。

文檔化退出碼表（intake/cli.py 模組文件）：0＝accept、2＝usage/contract error、40–45＝裁決。
「向上找不到 contract」與「--contract 路徑不存在」是同一失敗類別（contract error），皆須 RC 2；
前（bug）：`_contract_path` 用 `raise SystemExit(str)` → 解釋器定 RC 1（未定義碼）；
後（fix）：`raise C.ContractError([...])` → main() 映射 RC 2、stderr 含 no contract found＋init 提示。
以 sys.executable -m 跑（不依賴 PATH 上的 console script）；cwd=無 contract 的 tmp 目錄。
"""
import subprocess
import sys


def _run(cwd, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "vacant_network.cli", *args],
                          capture_output=True, text=True, timeout=60, cwd=cwd)


def test_check_no_contract_rc2(tmp_path):
    p = _run(tmp_path, "check")
    assert p.returncode == 2
    assert "no contract found" in p.stderr
    assert "vacant contract init" in p.stderr


def test_check_no_contract_json_rc2(tmp_path):
    assert _run(tmp_path, "check", "--json").returncode == 2


def test_submit_no_contract_rc2(tmp_path):
    assert _run(tmp_path, "submit").returncode == 2


def test_nonexistent_contract_path_still_rc2(tmp_path):
    # 一致性錨：--contract 路徑不存在 → 同一失敗類別，仍 RC 2（不回歸）
    p = _run(tmp_path, "check", "--contract", str(tmp_path / "nope" / "contract.json"))
    assert p.returncode == 2
