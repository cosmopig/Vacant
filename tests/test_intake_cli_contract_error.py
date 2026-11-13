import subprocess
import os
import tempfile
from pathlib import Path

def test_no_contract_found():
    # Create a temporary directory with no .vacant folder
    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{tmpdir}:" # This is wrong, we need the actual project root in PYTHONPATH
        # Actually, let's just use a real directory from our repo that doesn't have .vacant/contract.json
        pass

def test_no_contract_found_real():
    # Use current dir which has no contract (or at least we can control it)
    # But the prompt says "cd <無 contract 目錄>"
    # Let's create a dummy one
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = ["python3", "-m", "vacant_network.cli", "check"]
        result = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True)
        assert result.returncode == 1
        assert "no contract found" in result.stderr

def test_contract_not_found_path():
    # vacant check --contract /nonexistent/contract.json -> RC 2
    cmd = ["python3", "-m", "vacant_network.cli", "check", "--contract", "/nonexistent/contract.json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 2
    assert "cannot read contract" in result.stderr

def test_no_contract_found_rc2():
    # The goal is to make 'vacant check' (without --contract) return RC 2
    # when no contract is found.
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = ["python3", "-m", "vacant_network.cli", "check"]
        result = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True)
        assert result.returncode == 2
        assert "no contract found" in result.stderr

